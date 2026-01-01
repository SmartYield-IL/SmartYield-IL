import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles

# הפעלת שכבת העיצוב היוקרתית
styles.apply_styles()

# --- 1. הגדרת בסיס נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v6_pro.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS listings 
                      (id INTEGER PRIMARY KEY, city TEXT, type TEXT, price INTEGER, sqm INTEGER, 
                       ppm INTEGER, confidence INTEGER, is_renewal INTEGER, date TEXT)''')
    
    # בנצ'מרק ארצי - נתוני 2026
    benchmarks = [
        ("תל אביב", 68000), ("ירושלים", 45000), ("נתניה", 33000), 
        ("חיפה", 25000), ("באר שבע", 19000), ("רמת גן", 50000),
        ("גבעתיים", 54000), ("הרצליה", 55000), ("ראשון לציון", 35000),
        ("פתח תקווה", 31000), ("חולון", 36000), ("אשדוד", 29000)
    ]
    cursor.execute('CREATE TABLE IF NOT EXISTS benchmarks (city TEXT PRIMARY KEY, avg_ppm INTEGER)')
    cursor.executemany('INSERT OR REPLACE INTO benchmarks VALUES (?, ?)', benchmarks)
    conn.commit()
    conn.close()

# --- 2. מנוע סריקה וניתוח (The Genius Engine) ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v6_pro.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד"]
    # פקטורי תיקון לפי סוג נכס
    property_factors = {"פנטהאוז": 1.35, "דירת גן": 1.25, "וילה": 1.55, "דו משפחתי": 1.40, "דירה": 1.0}
    
    text = text.replace(',', '')
    raw_ads = text.split('₪')
    count = 0
    
    for ad in raw_ads:
        price_match = re.search(r'(\d{6,8})', ad)
        if not price_match: continue
        price = int(price_match.group(1))
        
        city = next((c for c in cities if c in ad), None)
        p_type = next((t for t in property_factors if t in ad), "דירה")
        
        if city and (600000 < price < 30000000):
            sqm_match = re.search(r'(\d{2,3})\s*(?:מ"ר|מר|מטר)', ad)
            sqm = int(sqm_match.group(1)) if sqm_match else 100
            
            # חישוב מדד ביטחון
            conf = 50 + (25 if sqm_match else 0) + (25 if len(ad) > 130 else 0)
            is_ren = 1 if any(w in ad for w in ["תמא", "פינוי", "התחדשות"]) else 0
            
            cursor.execute("""INSERT INTO listings (city, type, price, sqm, ppm, confidence, is_renewal, date) 
                              VALUES (?,?,?,?,?,?,?,?)""",
                           (city, p_type, price, sqm, price // sqm, conf, is_ren, datetime.now().strftime("%d/%m/%Y")))
            count += 1
            
    conn.commit()
    conn.close()
    return count

init_db()

# --- 3. ממשק משתמש (Tabs) ---
tab1, tab2, tab3 = st.tabs(["🚀 ניתוח נכסים", "📊 מאגר הזדמנויות", "⚙️ ניהול"])

with tab1:
    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
    st.subheader("הזנת נתונים גולמיים")
    raw_input = st.text_area("הדבק עמוד מודעות מלא:", height=250, placeholder="הדבק כאן...")
    if st.button("בצע ניתוח שוק"):
        if raw_input:
            c = smart_parse(raw_input)
            st.success(f"הניתוח הושלם. {c} נכסים התווספו למאגר.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    try:
        conn = sqlite3.connect('smartyield_v6_pro.db')
        # השאילתה רצה באנגלית נקייה כדי למנוע שגיאות סינטקס
        query = "SELECT city, type, price, sqm, ppm, confidence, is_renewal FROM listings"
        df = pd.read_sql(query, conn)
        
        # משיכת הבנצ'מרקים לחישוב
        bench_df = pd.read_sql("SELECT * FROM benchmarks", conn)
        conn.close()

        if not df.empty:
            # חיבור נתונים וחישוב רווח מבוסס סוג נכס
            df = df.merge(bench_df, on='city', how='left')
            
            # פקטורי תיקון לחישוב רווח ריאלי
            factors = {"פנטהאוז
