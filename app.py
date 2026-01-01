import streamlit as st
import pandas as pd
import sqlite3
from bs4 import BeautifulSoup
import re
from datetime import datetime

# --- הגדרת עמוד ---
st.set_page_config(page_title="SmartYield Pro", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@400;700;800&display=swap');
    html, body, .stApp { font-family: 'Assistant', sans-serif; direction: rtl; text-align: right; }
    .block-container { padding-top: 1rem; max-width: 100% !important; }
    div[data-testid="stMetric"] { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
</style>
""", unsafe_allow_html=True)

# --- מוח גיאוגרפי: מפת היוקרה של ישראל ---
# המערכת מחפשת את המילים האלו בכתובת. אם מוצאת, היא מכפילה את שווי השוק בפקטור.
# בסיס (1.0) = הממוצע של העיר.
ZONE_MULTIPLIERS = {
    "נתניה": {
        "עיר ימים": 1.6, "פולג": 1.45, "רמת פולג": 1.45, "אגמים": 1.25, "ניצה": 1.3, # יוקרה
        "קרית השרון": 1.15, "מרכז העיר": 1.0, # בינוני
        "דורה": 0.75, "רמת ידין": 0.75, "סלע": 0.8, "נאות שקד": 0.85 # זול
    },
    "תל אביב": {
        "נווה צדק": 1.8, "רמת אביב": 1.5, "הצפון הישן": 1.4, "לב העיר": 1.4, "שרונה": 1.5, # יוקרה
        "פלורנטין": 1.1, "יד אליהו": 0.95, # בינוני
        "התקווה": 0.7, "נווה שאנן": 0.65, "יפו ד": 0.7 # זול
    },
    "חיפה": {
        "דניה": 1.6, "כרמל": 1.4, "מרכז הכרמל": 1.35, "אחוזה": 1.25, # יוקרה
        "נווה שאנן": 1.0, "רמות רמז": 1.0, # בינוני
        "הדר": 0.7, "העיר התחתית": 0.8, "נווה דוד": 0.75 # זול
    },
    "הרצליה": {
        "הרצליה פיתוח": 2.2, "הירוקה": 1.2,
        "מרכז": 1.0, "יד התשעה": 0.8
    }
}

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v24_zones.db')
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY, city TEXT, street TEXT, type TEXT, 
        rooms REAL, floor INTEGER, price INTEGER, sqm INTEGER, ppm INTEGER, 
        profit REAL, zone_factor REAL, confidence INTEGER, date TEXT
    )""")
    
    # בנצ'מרק בסיס (מחיר ממוצע לעיר ללא שכונות יוקרה)
    benchmarks = [
        ("תל אביב", 55000), # הבסיס ירד כי הפרדנו את היוקרה
        ("ירושלים", 38000), 
        ("נתניה", 27000),   # בסיס נתניה (ללא עיר ימים)
        ("חיפה", 21000),    # בסיס חיפה (ללא דניה)
        ("באר שבע", 16000), ("רמת גן", 42000),
        ("גבעתיים", 48000), ("הרצליה", 45000), ("ראשון לציון", 29000),
        ("פתח תקווה", 28000), ("חולון", 32000), ("אשדוד", 26000),
        ("בת ים", 31000), ("רעננה", 41000), ("כפר סבא", 34000)
    ]
    cursor.execute("CREATE TABLE IF NOT EXISTS benchmarks (city TEXT PRIMARY KEY, avg_ppm INTEGER)")
    cursor.executemany("INSERT OR REPLACE INTO benchmarks VALUES (?, ?)", benchmarks)
    conn.commit()
    conn.close()

# --- לוגיקה חכמה ---
def calculate_smart_value(city, address_text, price, sqm, p_type):
    if sqm == 0: return 0, 0, 0, 1.0, "לא זוהה"
    
    ppm = price / sqm
    
    conn = sqlite3.connect('smartyield_v24_zones.db')
    cursor = conn.cursor()
    cursor.execute("SELECT avg_ppm FROM benchmarks WHERE city=?", (city,))
    res = cursor.fetchone()
    conn.close()
    
    if not res: return ppm, 0, 0, 1.0, "עיר לא נתמכת"
    
    base_market_price = res[0]
    zone_factor = 1.0
    zone_name = "אזור רגיל"
    
    # 1. בדיקת שכונה (התיקון הגדול)
    if city in ZONE_MULTIPLIERS:
        # מחפש כל שכונה ברשימה בתוך הטקסט של הכתובת
        for neighborhood, factor in ZONE_MULTIPLIERS[city].items():
            if neighborhood in address_text:
                zone_factor = factor
                zone_name = neighborhood
                break # מצאנו שכונה, עוצרים
    
    # 2. בדיקת סוג נכס
    type_factor = 1.0
    if p_type == "פנטהאוז": type_factor = 1.3
    if p_type == "דירת גן": type_factor = 1.15
    if p_type == "בית פרטי": type_factor = 1.4
    
    # חישוב שווי הוגן משוקלל
    final_target_ppm = base_market_price * zone_factor * type_factor
    fair_value = final_target_ppm * sqm
    
    profit_percent = ((fair_value - price) / fair_value) * 100
    
    return ppm, profit_percent, fair_value, zone_factor, zone_name

# --- מוח: ניתוח HTML ---
def parse_html_file(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    listings = []
    potential_cards = soup.find_all(['div', 'li'], class_=re.compile(r'(feed_item|card|listing|bullet)', re.IGNORECASE))
    
    for card in potential_cards:
        try:
            text_blob = card.get_text(" ", strip=True)
            
            # חילוץ מחיר
            price = 0
            price_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*₪?', text_blob)
            if price_match:
                p_str = price_match.group(1).replace(',', '')
                if p_str.isdigit(): price = int(p_str)
            
            if not (600000 < price < 50000000): continue

            # עיר ורחוב
            city = "כללי"
            street = text_blob # כברירת מחדל כל הטקסט הוא הכתובת לבדיקת שכונה
            cities_list = list(ZONE_MULTIPLIERS.keys()) + ["באר שבע", "רמת גן", "גבעתיים", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד", "רעננה", "כפר סבא", "ירושלים"]
            
            for c in cities_list:
                if c in text_blob:
                    city = c
                    # מנסים לחלץ רחוב נקי לתצוגה
                    parts = text_blob.split(c)
                    if len(parts) > 0:
                        street = parts[0][-50:] # לוקחים הקשר סביב העיר
                    break

            # חדרים וקומה
            rooms = 0
            r_match = re.search(r'(\d+(?:\.\d+)?)\s*חד', text_blob)
            if r_match: rooms = float(r_match.group(1))

            floor = 0
            f_match = re.search(r'קומה\s*(\d+)', text_blob)
            if f_match: floor = int(f_match.group(1))

            # מ"ר
            sqm = 0
            s_matches = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', text_blob)
            for m in s_matches:
                val = int(m.group(1))
                if 30 < val < 500 and (price/val > 4000):
                    sqm = val
                    break

            # סוג
            p_type = "דירה"
            if "פנטהאוז" in text_blob: p_type = "פנטהאוז"
            if "גן" in text_blob: p_type = "דירת גן"
            if "וילה" in text_blob or "פרטי" in text_blob: p_type = "בית פרטי"

            # חישוב חכם
            if sqm > 0:
                ppm, profit, fair_val, z_factor, z_name = calculate_smart_value(city, street, price, sqm, p_type)
                listings.append((city, z_name, p_type, rooms, floor, price, sqm, ppm, profit, z_factor, datetime.now().strftime("%d/%m/%Y")))
            
        except: continue
    return listings

def save_to_db(listings):
    if not listings: return 0
    conn = sqlite3.connect('smartyield_v24_zones.db')
    cursor = conn.cursor()
    c = 0
    for l in listings:
        cursor.execute("INSERT INTO listings (city, street, type, rooms, floor, price, sqm, ppm, profit, zone_factor, date) VALUES (?,?,?,?,?,?,?,?,?,?,?)", l)
        c += 1
    conn.commit()
    conn.close()
    return c

init_db()

# --- ממשק משתמש ---
st.title("🏙️ SmartYield - מערכת נדל\"ן מבוססת מיקום")

mode = st.radio("", ["מחשבון עסקה (מהיר)", "סריקת קבצים (מקצועי)"], horizontal=True)
st.divider()

if mode == "מחשבון עסקה (מהיר)":
    col1, col2 = st.columns(2)
    with col1:
        city_in = st.selectbox("עיר", list(ZONE_MULTIPLIERS.keys()) + ["ערים נוספות..."])
        street_in = st.text_input("רחוב / שכונה (חשוב לדיוק!)", placeholder="למשל: עיר ימים / דורה / הדר")
    with col2:
        sqm_in = st.number_input("מ\"ר", 30, 500, 100)
        price_in = st.number_input("מחיר", 500000, 50000000, 2000000, step=50000)
        type_in = st.selectbox("סוג", ["דירה", "פנטהאוז", "דירת גן", "בית פרטי"])

    if st.button("בצע הערכת שווי", type="primary", use_container_width=True):
        ppm, profit, fair_val, z_factor, z_name = calculate_smart_value(city_in, street_in, price_in, sqm_in, type_in)
        
        # תצוגת זיהוי שכונה
        if z_factor > 1.0:
            st.success(f"💎 **זוהה אזור יוקרה:** {z_name} (שווי שוק הותאם ב- {int((z_factor-1)*100)}% למעלה)")
        elif z_factor < 1.0:
            st.info(f"📉 **זוהה אזור מוזל:** {z_name} (שווי שוק הותאם בהתאם)")
        else:
            st.warning("📍 **אזור רגיל / לא זוהה:** החישוב מתבסס על ממוצע עירוני כללי.")

        c1, c2, c3 = st.columns(3)
        c1.metric("מחיר למ\"ר מחושב", f"{int(ppm):,} ₪")
        c2.metric("פער משווי הוגן", f"{profit:.1f}%", delta_color="normal" if profit > 0 else "off")
        c3.metric("שווי הוגן (מותאם שכונה)", f"{int(fair_val):,} ₪")

elif mode == "סריקת קבצים (מקצועי)":
    tab_scan, tab_res = st.tabs(["טעינה", "תוצאות"])
    with tab_scan:
        st.info("שמור דף מיד2 (Ctrl+S) וגרור לכאן.")
        up = st.file_uploader("HTML File", type=['html', 'htm'])
        if up:
            with st.spinner('מנתח שכונות ומחירים...'):
                raw = up.read().decode("utf-8")
                res = parse_html_file(raw)
                cnt = save_to_db(res)
            if cnt: st.success(f"נקלטו {cnt} נכסים")
    
    with tab_res:
        conn = sqlite3.connect('smartyield_v24_zones.db')
        try:
            df = pd.read_sql("SELECT * FROM listings ORDER BY profit DESC", conn)
            if not df.empty:
                st.dataframe(
                    df[["city", "street", "type", "rooms", "sqm", "price", "ppm", "profit"]],
                    column_config={
                        "street": "אזור/שכונה",
                        "price": st.column_config.NumberColumn(format="%d ₪"),
                        "profit": st.column_config.ProgressColumn("רווח %", format="%.1f%%", min_value=-20, max_value=40)
                    }, use_container_width=True, hide_index=True
                )
            else: st.info("ריק")
        except: pass
        conn.close()
        
    if st.button("איפוס"):
        c = sqlite3.connect('smartyield_v24_zones.db')
        c.execute("DELETE FROM listings") ; c.commit() ; c.close() ; st.rerun()
