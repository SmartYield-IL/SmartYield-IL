import streamlit as st
import pandas as pd
import sqlite3
from bs4 import BeautifulSoup
import re
from datetime import datetime

# --- הגדרת עמוד ---
st.set_page_config(page_title="SmartYield Ultimate", layout="wide")

# --- CSS מקצועי ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700;800&display=swap');
    html, body, .stApp { font-family: 'Assistant', sans-serif; direction: rtl; text-align: right; }
    .block-container { padding-top: 2rem; max-width: 95% !important; }
    
    /* עיצוב כרטיסי דראג-אנד-דרופ */
    .stFileUploader { text-align: center; }
    div[data-testid="stFileUploader"] section { background-color: #f8f9fa; border: 2px dashed #1e3a8a; }
</style>
""", unsafe_allow_html=True)

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_pro_source.db')
    cursor = conn.cursor()
    # מבנה טבלה מדויק
    cursor.execute("""CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY, city TEXT, street TEXT, type TEXT, 
        rooms REAL, floor INTEGER, price INTEGER, sqm INTEGER, ppm INTEGER, 
        profit REAL, confidence INTEGER, date TEXT
    )""")
    
    # בנצ'מרק
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

# --- המוח: מפרק קוד HTML (לא טקסט!) ---
def parse_html_file(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    listings = []
    
    # זיהוי "כרטיסי" מודעות לפי מבנה נפוץ של אתרי נדל"ן (יד2/מדלן)
    # אסטרטגיה: חיפוש אלמנטים שמכילים מחיר, ואז חפירה פנימה
    
    # ננסה לתפוס את כל הבלוקים שיכולים להיות מודעה
    # ביד2 זה בדרך כלל feeditem, במדלן זה bullet
    potential_cards = soup.find_all(['div', 'li'], class_=re.compile(r'(feed_item|card|listing|bullet)', re.IGNORECASE))
    
    for card in potential_cards:
        try:
            text_blob = card.get_text(" ", strip=True) # המרת הכרטיס לטקסט נקי עם רווחים
            
            # --- שליפת מחיר מדויקת ---
            # מחפש אלמנט שיש בו סימן שקל או מחיר
            price = 0
            price_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*₪?', text_blob)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                if price_str.isdigit():
                    price = int(price_str)
            
            if not (600000 < price < 50000000): continue # סינון מחירים לא הגיוניים

            # --- שליפת עיר ורחוב ---
            city = "כללי"
            street = "לא צוין"
            cities_list = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד"]
            
            for c in cities_list:
                if c in text_blob:
                    city = c
                    # ניסיון לחלץ רחוב מהטקסט שצמוד לעיר
                    parts = text_blob.split(c)
                    if len(parts) > 0:
                        prev_words = parts[0].split()[-4:] # 4 מילים אחרונות לפני העיר
                        street = " ".join(prev_words).replace("רחוב", "").replace("ב", "").strip()
                    break

            # --- שליפת חדרים ---
            rooms = 0
            # ב-HTML המספר לרוב יושב באלמנט נפרד ליד המילה "חדרים"
            rooms_match = re.search(r'(\d+(?:\.\d+)?)\s*חד', text_blob)
            if rooms_match:
                rooms = float(rooms_match.group(1))

            # --- שליפת קומה (מדויק!) ---
            floor = 0
            floor_match = re.search(r'קומה\s*(\d+)', text_blob)
            if floor_match:
                floor = int(floor_match.group(1))
                if floor > 50: floor = 0 # הגנה משגיאות

            # --- שליפת מ"ר ---
            sqm = 0
            # כאן היתרון של HTML - המ"ר לרוב מופרד
            sqm_matches = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', text_blob)
            for m in sqm_matches:
                val = int(m.group(1))
                if 30 < val < 500: # טווח הגיוני
                    # בדיקה שהמספר הוא לא המחיר בטעות
                    if price / val > 4000: 
                        sqm = val
                        break

            # --- חישוב רווח ---
            ppm = 0
            profit = 0
            if sqm > 0 and price > 0:
                ppm = price // sqm
                conn = sqlite3.connect('smartyield_pro_source.db')
                cur = conn.cursor()
                cur.execute("SELECT avg_ppm FROM benchmarks WHERE city=?", (city,))
                res = cur.fetchone()
                conn.close()
                
                if res:
                    avg = res[0]
                    # פקטור פנטהאוז
                    factor = 1.0
                    if "פנטהאוז" in text_blob: factor = 1.35
                    if "גן" in text_blob: factor = 1.25
                    
                    target = avg * factor
                    profit = ((target - ppm) / target) * 100

            # שמירה
            listings.append((city, street, "דירה", rooms, floor, price, sqm, ppm, profit, 90, datetime.now().strftime("%d/%m/%Y")))
            
        except Exception as e:
            continue # אם כרטיס אחד נכשל, ממשיכים לאחרים

    return listings

def save_to_db(listings):
    if not listings: return 0
    conn = sqlite3.connect('smartyield_pro_source.db')
    cursor = conn.cursor()
    count = 0
    for l in listings:
        cursor.execute("INSERT INTO listings (city, street, type, rooms, floor, price, sqm, ppm, profit, confidence, date) VALUES (?,?,?,?,?,?,?,?,?,?,?)", l)
        count += 1
    conn.commit()
    conn.close()
    return count

init_db()

# --- ממשק המשתמש ---
st.title("🏙️ SmartYield Pro - מנתח קבצי מקור")
st.markdown("### המערכת המקצועית לניתוח דפי נדל\"ן ללא שגיאות טקסט")

tab1, tab2 = st.tabs(["📂 טעינת קובץ נתונים", "📊 דשבורד עסקאות"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.info("💡 **איך עובדים כמו מקצוענים?**\n1. כנס לאתר (יד2 / מדלן).\n2. לחץ `Ctrl + S` ושמור את הדף במחשב.\n3. גרור את הקובץ לכאן.")
        
        uploaded_file = st.file_uploader("גרור לכאן את קובץ ה-HTML ששמרת", type=['html', 'htm'])
        
        if uploaded_file is not None:
            with st.spinner('מפרק את קוד האתר לגורמים...'):
                html_content = uploaded_file.read().decode("utf-8")
                listings = parse_html_file(html_content)
                count = save_to_db(listings)
                
            if count > 0:
                st.success(f"✅ הצלחנו! חולצו {count} נכסים מדויקים מתוך הקוד.")
                st.balloons()
            else:
                st.warning("לא נמצאו נכסים בקובץ. וודא ששמרת דף עם תוצאות חיפוש.")

with tab2:
    conn = sqlite3.connect('smartyield_pro_source.db')
    try:
        df = pd.read_sql("SELECT * FROM listings ORDER BY profit DESC", conn)
        conn.close()
        
        if not df.empty:
            # מטריקות
            m1, m2, m3 = st.columns(3)
            m1.metric("נכסים במאגר", len(df))
            m2.metric("רווח ממוצע", f"{df['profit'].mean():.1f}%")
            m3.metric("עיר מובילה", df['city'].mode()[0])
            
            st.divider()
            
            st.dataframe(
                df[["city", "street", "rooms", "floor", "sqm", "price", "ppm", "profit"]],
                column_config={
                    "city": "עיר",
                    "street": st.column_config.TextColumn("רחוב", width="medium"),
                    "rooms": st.column_config.NumberColumn("חד'", format="%.1f"),
                    "floor": st.column_config.NumberColumn("קומה", format="%d"),
                    "sqm": st.column_config.NumberColumn("מ\"ר", format="%d"),
                    "price": st.column_config.NumberColumn("מחיר", format="%d ₪"),
                    "ppm": st.column_config.NumberColumn("למ\"ר", format="%d ₪"),
                    "profit": st.column_config.ProgressColumn("פוטנציאל רווח", format="%.1f%%", min_value=-15, max_value=45),
                },
                use_container_width=True,
                hide_index=True,
                height=600
            )
        else:
            st.info("המאגר ריק. טען קובץ HTML בלשונית הראשונה.")
    except:
        st.write("אין נתונים.")

# כפתור ניקוי בצד
with st.sidebar:
    if st.button("🗑️ איפוס מלא"):
        c = sqlite3.connect('smartyield_pro_source.db')
        c.execute("DELETE FROM listings")
        c.commit()
        c.close()
        st.rerun()
