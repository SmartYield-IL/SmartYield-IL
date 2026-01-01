import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime

# --- הגדרת עמוד ---
st.set_page_config(page_title="SmartYield Ultimate", layout="wide")

# --- CSS נקי ומקצועי ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700;800&display=swap');
    html, body, .stApp { 
        font-family: 'Assistant', sans-serif; 
        direction: rtl; 
        text-align: right; 
    }
    .block-container { padding-top: 1rem; max-width: 100% !important; }
    /* הדגשת נתונים בטבלה */
    td { font-size: 1.1rem !important; }
</style>
""", unsafe_allow_html=True)

# --- קבועים לביצועים ---
CITIES = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", 
          "גבעתיים", "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד", 
          "רעננה", "כפר סבא", "הוד השרון", "בת ים", "רחובות", "חדרה"]

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v22_ultimate.db')
    cursor = conn.cursor()
    
    # טבלה נקייה
    sql = """CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY, city TEXT, street TEXT, type TEXT, 
        rooms REAL, floor INTEGER, price INTEGER, sqm INTEGER, ppm INTEGER, 
        profit REAL, confidence INTEGER, date TEXT, original_snippet TEXT
    )"""
    cursor.execute(sql)
    
    # בנצ'מרק מעודכן
    benchmarks = [
        ("תל אביב", 68000), ("ירושלים", 45000), ("נתניה", 33000), 
        ("חיפה", 25000), ("באר שבע", 19000), ("רמת גן", 50000),
        ("גבעתיים", 54000), ("הרצליה", 55000), ("ראשון לציון", 35000),
        ("פתח תקווה", 31000), ("חולון", 36000), ("אשדוד", 29000),
        ("בת ים", 34000), ("רעננה", 46000), ("כפר סבא", 38000)
    ]
    cursor.execute("CREATE TABLE IF NOT EXISTS benchmarks (city TEXT PRIMARY KEY, avg_ppm INTEGER)")
    cursor.executemany("INSERT OR REPLACE INTO benchmarks VALUES (?, ?)", benchmarks)
    conn.commit()
    conn.close()

# --- המוח החדש: מנרמל טקסט ---
def normalize_text(text):
    """
    מפריד הדבקות נפוצות כמו 'קומה2' או '85מ"ר' או '3חד'
    זהו המפתח למניעת שגיאות כמו 'קומה 285'
    """
    # הפרד מספר ממילה בעברית (למשל: 3חדרים -> 3 חדרים)
    text = re.sub(r'(\d+)([א-ת])', r'\1 \2', text)
    # הפרד מילה בעברית ממספר (למשל: קומה2 -> קומה 2)
    text = re.sub(r'([א-ת])(\d+)', r'\1 \2', text)
    # נקה תווים מיוחדים מציקים
    text = text.replace('|', ' ').replace('-', ' ').replace('\n', ' ')
    return text

def extract_street_context(text, city_name):
    """
    מחפש את העיר, ולוקח את 4-5 המילים שלפניה.
    ברוב האתרים המבנה הוא: רחוב הרצל 50, נתניה
    """
    try:
        # מחפש איפה העיר נמצאת בטקסט
        idx = text.find(city_name)
        if idx == -1: return "לא צוין"
        
        # לוקח את הטקסט שלפני העיר (עד 40 תווים אחורה)
        pre_text = text[max(0, idx-40):idx].strip()
        
        # מנקה מילים לא רלוונטיות
        bad_words = ["דירה", "למכירה", "ב", "של", "פרויקט", "חדשה", "משופצת", "מ"]
        words = pre_text.split()
        
        # לוקח את ה-3 מילים האחרונות לפני העיר
        street_candidate = " ".join(words[-4:])
        
        # ניקוי סופי
        for w in bad_words:
            if street_candidate.startswith(w + " "):
                street_candidate = street_candidate.replace(w + " ", "")
        
        clean_s = street_candidate.replace(",", "").strip()
        return clean_s if len(clean_s) > 2 else "כללי"
    except:
        return "כללי"

# --- המנוע הראשי ---
def smart_parse(raw_text):
    conn = sqlite3.connect('smartyield_v22_ultimate.db')
    cursor = conn.cursor()
    
    # 1. נירמול ראשוני של כל הדף
    clean_page = normalize_text(raw_text.replace(',', ''))
    
    # 2. פיצול לפי סימן השקל (העוגן הכי חזק)
    ads = clean_page.split('₪')
    count = 0
    
    for ad in ads:
        # חילוץ מחיר (חובה)
        p_match = re.search(r'(\d{6,9})', ad) # 6-9 ספרות
        if not p_match: continue
        
        # כאן אנחנו לוקחים את המחיר שנמצא בסוף הבלוק (לפני ה-₪ שנחתך)
        # זה בדרך כלל המחיר הנכון
        price = int(p_match.group(1))
        
        # זיהוי עיר
        city = None
        for c in CITIES:
            if c in ad:
                city = c
                break
        
        if not city: continue # בלי עיר אין עסקה
        
        # זיהוי רחוב חכם (לפי מיקום העיר)
        street = extract_street_context(ad, city)
        
        # זיהוי סוג נכס
        p_type = "דירה"
        if any(x in ad for x in ["מגרש", "קרקע", "להריסה"]): p_type = "קרקע"
        elif "פנטהאוז" in ad: p_type = "פנטהאוז"
        elif "גן" in ad: p_type = "דירת גן"
        elif any(x in ad for x in ["וילה", "קוטג", "פרטי", "דו משפחתי"]): p_type = "בית פרטי"
        
        # זיהוי חדרים (חייב להיות מספר קטן הגיוני)
        rooms = 0
        r_match = re.search(r'(\d+(?:\.\d+)?)\s*חד', ad)
        if r_match:
            r = float(r_match.group(1))
            if 1 <= r <= 12: rooms = r # מסנן רעשים כמו "100 חדרים"
            
        # זיהוי קומה (הפרדנו את המספרים בנרמול, אז זה קל יותר)
        floor = 0
        f_match = re.search(r'קומה\s*(\d{1,2})', ad) # מקסימום 2 ספרות לקומה! מונע 285
        if f_match: floor = int(f_match.group(1))
        
        # זיהוי מ"ר (מנגנון אנטי-רעש)
        sqm = 0
        # מחק מרחקים לפני חיפוש
        ad_no_dist = re.sub(r'(מרחק|הליכה)\s*\d+', '', ad)
        s_matches = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', ad_no_dist)
        
        possible_sqms = []
        for m in s_matches:
            val = int(m.group(1))
            # פילטרים:
            if p_type == "קרקע": possible_sqms.append(val)
            elif 30 <= val <= 400: # דירה נורמלית
                # בדיקת היתכנות כלכלית
                if (price / val) > 5000: 
                    possible_sqms.append(val)
        
        if possible_sqms:
            sqm = possible_sqms[0] # לוקח את הראשון שנמצא תקין
        
        # חישוב רווח (רק אם יש נתונים)
        ppm = 0
        profit = 0
        conf = 50
        
        if sqm > 0 and price > 0 and p_type != "קרקע":
            ppm = price // sqm
            
            # שליפת בנצ'מרק
            cursor.execute("SELECT avg_ppm FROM benchmarks WHERE city=?", (city,))
            res = cursor.fetchone()
            if res:
                avg_city = res[0]
                # פקטורים
                factor = 1.0
                if p_type == "פנטהאוז": factor = 1.3
                if p_type == "דירת גן": factor = 1.15
                if p_type == "בית פרטי": factor = 1.4
                
                target_price = avg_city * factor
                profit = ((target_price - ppm) / target_price) * 100
                conf = 80
        
        # שמירה (רק אם המחיר הגיוני לנדל"ן)
        if 500000 < price < 50000000:
            snippet = ad[:80].replace('\n', ' ') # הוכחה
            vals = (city, street, p_type, rooms, floor, price, sqm, ppm, profit, conf, datetime.now().strftime("%d/%m/%Y"), snippet)
            cursor.execute("INSERT INTO listings (city, street, type, rooms, floor, price, sqm, ppm, profit, confidence, date, original_snippet) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", vals)
            count += 1
            
    conn.commit()
    conn.close()
    return count

init_db()

# --- ממשק משתמש ---
st.title("🤖 SmartYield Ultimate")
st.write("המערכת פועלת במצב 'חכם' - מפרידה מילים דבוקות ומסננת רעשי רקע.")

tab1, tab2, tab3 = st.tabs(["📥 הזנה", "📊 תוצאות", "⚙️ איפוס"])

with tab1:
    txt = st.text_area("הדבק כאן (Ctrl+V):", height=200)
    if st.button("בצע ניתוח", type="primary"):
        if txt:
            c = smart_parse(txt)
            if c > 0: st.success(f"זוהו {c} נכסים בהצלחה!")
            else: st.error("לא זוהו נכסים. וודא שהעתקת מחירים וערים.")

with tab2:
    conn = sqlite3.connect('smartyield_v22_ultimate.db')
    try:
        df = pd.read_sql("SELECT * FROM listings ORDER BY profit DESC", conn)
        if not df.empty:
            # עיצוב הטבלה
            st.dataframe(
                df[["city", "street", "type", "rooms", "floor", "sqm", "price", "ppm", "profit", "original_snippet"]],
                column_config={
                    "city": "עיר",
                    "street": st.column_config.TextColumn("רחוב/אזור", width="medium"),
                    "type": "סוג",
                    "rooms": st.column_config.NumberColumn("חד'", format="%.1f"),
                    "floor": st.column_config.NumberColumn("קומה", format="%d"),
                    "sqm": st.column_config.NumberColumn("מ\"ר", format="%d"),
                    "price": st.column_config.NumberColumn("מחיר", format="%d ₪"),
                    "ppm": st.column_config.NumberColumn("למ\"ר", format="%d ₪"),
                    "profit": st.column_config.ProgressColumn("פוטנציאל", format="%.1f%%", min_value=-20, max_value=40),
                    "original_snippet": st.column_config.TextColumn("מקור לבדיקה", width="large")
                },
                use_container_width=True,
                hide_index=True,
                height=600
            )
        else:
            st.info("אין נתונים להצגה.")
    except:
        st.error("שגיאה בטעינת הנתונים.")
    conn.close()

with tab3:
    if st.button("נקה הכל"):
        c = sqlite3.connect('smartyield_v22_ultimate.db')
        c.execute("DELETE FROM listings")
        c.commit()
        c.close()
        st.rerun()
