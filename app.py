import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime

# --- הגדרת עמוד חייבת להיות ראשונה ---
st.set_page_config(page_title="SmartYield Pro", layout="wide")

# --- CSS ליישור ועיצוב ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;700;800&display=swap');
    html, body, [class*="css"] { 
        font-family: 'Assistant', sans-serif; 
        direction: rtl; 
        text-align: right; 
    }
    .block-container { 
        padding-top: 1rem; 
        max-width: 100% !important;
    }
</style>
""", unsafe_allow_html=True)

# --- ביטויים רגולריים מוגדרים מראש (למניעת שגיאות) ---
# 1. תבנית לזיהוי מחיר (6-8 ספרות)
PRICE_PATTERN = r'(\d{6,8})'

# 2. תבנית לזיהוי מ"ר (מספר ואחריו מ"ר/מטר) - מוגדר כמשתנה למניעת שבירת שורה
SQM_PATTERN = r"(\d{2,4})\s*(?:מ\"ר|מר|מטר)"

# 3. תבנית לזיהוי חדרים
ROOMS_PATTERN = r"(\d+(?:\.\d+)?)\s*(?:חדרים|חד\b|חד\')"

# 4. תבנית לניקוי מרחקים (מחיקת '100 מטר מהים')
DIST_PATTERN = r"(?:מרחק|כ-|הליכה)\s*\d+\s*(?:מטר|מ\"ר|מ\'|מ)"

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v20.db')
    cursor = conn.cursor()
    
    # יצירת טבלה בחלקים
    sql = "CREATE TABLE IF NOT EXISTS listings ("
    sql += "id INTEGER PRIMARY KEY, city TEXT, type TEXT, "
    sql += "rooms REAL, price INTEGER, sqm INTEGER, ppm INTEGER, "
    sql += "confidence INTEGER, is_renewal INTEGER, "
    sql += "address TEXT, original_text TEXT, date TEXT)"
    
    cursor.execute(sql)
    
    benchmarks = [
        ("תל אביב", 68000), ("ירושלים", 45000), ("נתניה", 33000), 
        ("חיפה", 25000), ("באר שבע", 19000), ("רמת גן", 50000),
        ("גבעתיים", 54000), ("הרצליה", 55000), ("ראשון לציון", 35000),
        ("פתח תקווה", 31000), ("חולון", 36000), ("אשדוד", 29000)
    ]
    cursor.execute("CREATE TABLE IF NOT EXISTS benchmarks (city TEXT PRIMARY KEY, avg_ppm INTEGER)")
    cursor.executemany("INSERT OR REPLACE INTO benchmarks VALUES (?, ?)", benchmarks)
    conn.commit()
    conn.close()

# --- פונקציות עזר ---
def clean_address(text):
    bad = ["נגיש", "תפריט", "צור קשר", "whatsapp", "פייסבוק", "נדל\"ן"]
    # חיפוש רחוב
    street_p = r"(?:רחוב|רח'|שד'|שדרות|דרך|סמטת|שכונת)\s+([\u0590-\u05FF\"']+(?:\s+[\u0590-\u05FF\"']+)*\s*\d*)"
    match = re.search(street_p, text)
    if match:
        a = match.group(0).strip()
        if not any(b in a for b in bad): return a
    
    # חיפוש שורה נקייה
    lines = text.split('\n')
    for l in lines:
        l = l.strip()
        if 4 < len(l) < 40 and not any(b in l for b in bad):
            return l
    return "אזור כללי"

def get_sqm(text, price, p_type):
    # שימוש במשתנים המוגדרים למעלה
    clean = re.sub(DIST_PATTERN, '', text)
    matches = re.finditer(SQM_PATTERN, clean)
    
    for m in matches:
        val = int(m.group(1))
        
        if p_type == "מגרש/קרקע": return val
        if val > 350 and p_type == "דירה": continue
        if (price / val) < 6000: continue # סינון לפי מחיר לא הגיוני
        
        return val
    return 0

# --- המנוע ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v20.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", 
              "גבעתיים", "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד"]
    
    text = text.replace(',', '')
    ads = text.split('₪')
    count = 0
    
    for ad in ads:
        # זיהוי מחיר
        p_match = re.search(PRICE_PATTERN, ad)
        if not p_match: continue
        price = int(p_match.group(1))
        
        # זיהוי עיר
        city = None
        for c in cities:
            if c in ad:
                city = c
                break
        
        # זיהוי סוג
        p_type = "דירה"
        if "מגרש" in ad or "קרקע" in ad: p_type = "מגרש/קרקע"
        elif "פנטהאוז" in ad: p_type = "פנטהאוז"
        elif "דירת גן" in ad: p_type = "דירת גן"
        elif "וילה" in ad: p_type = "וילה/בית פרטי"
        elif "דו משפחתי" in ad: p_type = "דו משפחתי"
        
        # זיהוי חדרים
        r_match = re.search(ROOMS_PATTERN, ad)
        rooms = float(r_match.group(1)) if r_match else 0
        
        if city and (600000 < price < 50000000):
            sqm = get_sqm(ad, price, p_type)
            
            if sqm == 0:
                sqm = 1
                ppm = 0
                conf = 10
            else:
                ppm = price // sqm
                conf = 60
                if rooms > 0: conf += 20
            
            is_ren = 1 if "תמא" in ad or "פינוי" in ad else 0
            addr = clean_address(ad[:150])
            proof = ad[:100].replace('\n', ' ')

            # הכנסה למסד נתונים בצורה מוגנת
            sql = "INSERT INTO listings (city, type, rooms, price, sqm, ppm, "
            sql += "confidence, is_renewal, address, original_text, date) "
            sql += "VALUES (?,?,?,?,?,?,?,?,?,?,?)"
            
            vals = (city, p_type, rooms, price, sqm, ppm, conf, is_ren, addr, proof, datetime.now().strftime("%d/%m/%Y"))
            cursor.execute(sql, vals)
            count += 1
            
    conn.commit()
    conn.close()
    return count

init_db()

# --- ממשק ---
st.title("📊 SmartYield Pro")

tab1, tab2, tab3 = st.tabs(["🚀 הדבקת נתונים", "📈 טבלת תוצאות", "⚙️ איפוס"])

with tab1:
    st.write("הדבק נתונים כאן:")
    raw_input = st.text_area("input_area", height=300, label_visibility="collapsed")
    if st.button("🚀 בצע ניתוח", type="primary"):
        if raw_input:
            c = smart_parse(raw_input)
            st.success(f"נקלטו {c} נכסים")

with tab2:
    try:
        conn = sqlite3.connect('smartyield_v20.db')
        df = pd.read_sql("SELECT * FROM listings", conn)
        bench = pd.read_sql("SELECT * FROM benchmarks", conn)
        conn.close()

        if not df.empty:
            df = df.merge(bench, on='city', how='left')
            
            def calc_profit(row):
                if row['type'] == "מגרש/קרקע": return 0
                f = 1.0
                if row['type'] == "פנטהאוז": f = 1.35
                if row['type'] == "דירת גן": f = 1.25
                if "וילה" in row['type']: f = 1.55
                bench_p = row['avg_ppm'] * f
                if row['sqm'] > 1 and row['ppm'] > 0:
                    return ((bench_p - row['ppm']) * 100.0 / bench_p)
                return 0

            df['profit'] = df.apply(calc_profit, axis=1)
            
            cols = ["city", "address", "type", "rooms", "price", "sqm", "ppm", "profit", "confidence", "original_text"]
            show_df = df[cols].sort_values("profit", ascending=False)
            
            show_df.columns = ["עיר", "כתובת", "סוג", "חדרים", "מחיר", "מ\"ר", "למ\"ר", "רווח %", "ביטחון", "מקור"]

            st.dataframe(
                show_df,
                column_config={
                    "מחיר": st.column_config.NumberColumn(format="%d ₪"),
                    "למ\"ר": st.column_config.NumberColumn(format="%d ₪"),
                    "רווח %": st.column_config.ProgressColumn(format="%.1f%%", min_value=-10, max_value=40),
                    "ביטחון": st.column_config.NumberColumn(format="%d%%"),
                },
                use_container_width=True,
                hide_index=True,
                height=700
            )
        else:
            st.info("המאגר ריק.")
    except Exception as e:
        st.error(f"שגיאה: {e}")

with tab3:
    if st.button("🗑️ איפוס הכל"):
        conn = sqlite3.connect('smartyield_v20.db')
        conn.execute("DELETE FROM listings")
        conn.commit()
        conn.close()
        st.rerun()
