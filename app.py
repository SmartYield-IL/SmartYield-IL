import streamlit as st
import pandas as pd
import sqlite3
from bs4 import BeautifulSoup
import re
from datetime import datetime

# --- הגדרת עמוד ---
st.set_page_config(page_title="SmartYield Pro", layout="wide")

# --- CSS עיצוב ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700;800&display=swap');
    html, body, .stApp { font-family: 'Assistant', sans-serif; direction: rtl; text-align: right; }
    .block-container { padding-top: 1rem; max-width: 100% !important; }
    
    /* עיצוב כרטיסי תוצאות */
    div[data-testid="stMetric"] {
        background-color: #f0f9ff;
        border: 1px solid #bae6fd;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v23_complete.db')
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY, city TEXT, street TEXT, type TEXT, 
        rooms REAL, floor INTEGER, price INTEGER, sqm INTEGER, ppm INTEGER, 
        profit REAL, confidence INTEGER, date TEXT
    )""")
    
    # בנצ'מרק מעודכן (מחיר ממוצע למ"ר)
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

# --- לוגיקה עסקית ---
def calculate_deal(city, price, sqm, p_type):
    if sqm == 0: return 0, 0, 0
    
    ppm = price / sqm
    
    conn = sqlite3.connect('smartyield_v23_complete.db')
    cursor = conn.cursor()
    cursor.execute("SELECT avg_ppm FROM benchmarks WHERE city=?", (city,))
    res = cursor.fetchone()
    conn.close()
    
    if not res: return ppm, 0, 0 # עיר לא מוכרת
    
    avg_market = res[0]
    
    # התאמת מחיר השוק לסוג הנכס
    factor = 1.0
    if p_type == "פנטהאוז": factor = 1.35
    if p_type == "דירת גן": factor = 1.25
    if p_type == "בית פרטי": factor = 1.4
    if p_type == "מרתף/מחסן": factor = 0.6
    
    target_price_ppm = avg_market * factor
    fair_value = target_price_ppm * sqm
    
    # אחוז הרווח (ההפרש בין השווי ההוגן למחיר המבוקש)
    profit_percent = ((fair_value - price) / fair_value) * 100
    
    return ppm, profit_percent, fair_value

# --- מוח: ניתוח HTML ---
def parse_html_file(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    listings = []
    
    # ניסיון לתפוס כרטיסים גנריים
    potential_cards = soup.find_all(['div', 'li'], class_=re.compile(r'(feed_item|card|listing|bullet)', re.IGNORECASE))
    
    for card in potential_cards:
        try:
            text_blob = card.get_text(" ", strip=True)
            
            # מחיר
            price = 0
            price_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*₪?', text_blob)
            if price_match:
                p_str = price_match.group(1).replace(',', '')
                if p_str.isdigit(): price = int(p_str)
            
            if not (600000 < price < 50000000): continue

            # עיר
            city = "כללי"
            street = "לא צוין"
            cities_list = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד", "רעננה", "כפר סבא"]
            
            for c in cities_list:
                if c in text_blob:
                    city = c
                    parts = text_blob.split(c)
                    if len(parts) > 0:
                        prev = parts[0].split()[-4:]
                        street = " ".join(prev).replace("רחוב", "").strip()
                    break

            # פרטים טכניים
            rooms = 0
            r_match = re.search(r'(\d+(?:\.\d+)?)\s*חד', text_blob)
            if r_match: rooms = float(r_match.group(1))

            floor = 0
            f_match = re.search(r'קומה\s*(\d+)', text_blob)
            if f_match: floor = int(f_match.group(1))

            sqm = 0
            s_matches = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', text_blob)
            for m in s_matches:
                val = int(m.group(1))
                if 30 < val < 500 and (price/val > 4000):
                    sqm = val
                    break

            # חישוב רווח
            p_type = "דירה"
            if "פנטהאוז" in text_blob: p_type = "פנטהאוז"
            if "גן" in text_blob: p_type = "דירת גן"
            
            ppm, profit, fair_val = calculate_deal(city, price, sqm, p_type)

            if sqm > 0:
                listings.append((city, street, p_type, rooms, floor, price, sqm, ppm, profit, 90, datetime.now().strftime("%d/%m/%Y")))
            
        except: continue

    return listings

def save_to_db(listings):
    if not listings: return 0
    conn = sqlite3.connect('smartyield_v23_complete.db')
    cursor = conn.cursor()
    c = 0
    for l in listings:
        cursor.execute("INSERT INTO listings (city, street, type, rooms, floor, price, sqm, ppm, profit, confidence, date) VALUES (?,?,?,?,?,?,?,?,?,?,?)", l)
        c += 1
    conn.commit()
    conn.close()
    return c

init_db()

# --- ממשק משתמש ---
st.title("🏡 SmartYield - מערכת קבלת החלטות בנדל\"ן")

# בחירת מצב עבודה
mode = st.radio("בחר כיצד תרצה לעבוד:", 
         ["מחשבון עסקה בודדת (מהיר)", "סריקת שוק המונית (מקצועי)"], 
         horizontal=True)

st.divider()

# --- מצב 1: מחשבון מהיר לאדם הפשוט ---
if mode == "מחשבון עסקה בודדת (מהיר)":
    st.subheader("בדיקת כדאיות מיידית")
    st.write("ראית דירה? הזן את הפרטים וקבל ניתוח שוק מיידי.")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        city_input = st.selectbox("עיר", ["נתניה", "תל אביב", "חיפה", "ירושלים", "באר שבע", "רמת גן", "גבעתיים", "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד", "כפר סבא", "רעננה"])
    with col2:
        type_input = st.selectbox("סוג נכס", ["דירה", "פנטהאוז", "דירת גן", "בית פרטי"])
    with col3:
        sqm_input = st.number_input("מ\"ר בנוי", min_value=30, max_value=500, value=100)
    with col4:
        price_input = st.number_input("מחיר מבוקש (₪)", min_value=500000, step=50000, value=2000000)
        
    if st.button("📊 נתח עסקה", type="primary", use_container_width=True):
        ppm, profit, fair_val = calculate_deal(city_input, price_input, sqm_input, type_input)
        
        st.markdown("---")
        
        # תוצאות ויזואליות
        m1, m2, m3 = st.columns(3)
        m1.metric("מחיר למ\"ר שלך", f"{int(ppm):,} ₪")
        
        # צבע לרווח
        profit_color = "normal"
        if profit > 5: profit_color = "off" # ירוק בהיפוך של סטרימליט או פשוט נשתמש בטקסט
        
        delta_color = "normal"
        if profit > 0: delta_color = "inverse" # חיובי = ירוק
        elif profit < 0: delta_color = "off" # שלילי = אדום
            
        m2.metric("פער ממחיר השוק", f"{profit:.1f}%", delta=f"{profit:.1f}%", delta_color=delta_color)
        m3.metric("שווי הוגן מוערך", f"{int(fair_val):,} ₪")
        
        if profit > 10:
            st.success("🔥 **עסקה לוהטת!** הנכס מתומחר משמעותית מתחת למחיר השוק.")
        elif profit > 0:
            st.info("✅ **עסקה טובה.** המחיר הוגן ואטרקטיבי.")
        elif profit > -10:
            st.warning("⚠️ **מחיר שוק.** אין כאן הנחה מיוחדת.")
        else:
            st.error("🛑 **יקר מדי!** המחיר גבוה משמעותית מהממוצע באזור.")

# --- מצב 2: סורק קבצים למקצוענים ---
elif mode == "סריקת שוק המונית (מקצועי)":
    st.subheader("ניתוח דפי תוצאות (יד2 / מדלן)")
    
    tab_scan, tab_results = st.tabs(["📂 טעינת קובץ", "📈 טבלת הזדמנויות"])
    
    with tab_scan:
        st.info("כדי לסרוק עשרות דירות בבת אחת: שמור את דף התוצאות במחשב (Ctrl+S) וגרור לכאן.")
        uploaded = st.file_uploader("גרור קובץ HTML", type=['html', 'htm'])
        if uploaded:
            with st.spinner('מנתח נתונים...'):
                html = uploaded.read().decode("utf-8")
                lst = parse_html_file(html)
                cnt = save_to_db(lst)
            if cnt: st.success(f"נקלטו {cnt} דירות!")
            else: st.error("לא נמצאו נתונים בקובץ.")

    with tab_results:
        conn = sqlite3.connect('smartyield_v23_complete.db')
        try:
            df = pd.read_sql("SELECT * FROM listings ORDER BY profit DESC", conn)
            if not df.empty:
                st.dataframe(
                    df[["city", "street", "type", "rooms", "floor", "sqm", "price", "ppm", "profit"]],
                    column_config={
                        "city": "עיר", "street": "רחוב", "type": "סוג", 
                        "rooms": "חדרים", "floor": "קומה", "sqm": "מ\"ר",
                        "price": st.column_config.NumberColumn("מחיר", format="%d ₪"),
                        "ppm": st.column_config.NumberColumn("למ\"ר", format="%d ₪"),
                        "profit": st.column_config.ProgressColumn("רווח %", format="%.1f%%", min_value=-20, max_value=40)
                    }, use_container_width=True, hide_index=True, height=600
                )
            else: st.info("המאגר ריק.")
        except: st.write("אין נתונים.")
        conn.close()
        
    if st.button("נקה מאגר"):
        c = sqlite3.connect('smartyield_v23_complete.db')
        c.execute("DELETE FROM listings") ; c.commit() ; c.close()
        st.rerun()
