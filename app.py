import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles  # <--- הייבוא של קובץ העיצוב החדש

# הפעלת העיצוב
styles.apply_styles()

# --- פונקציות ליבה ---
def init_db():
    conn = sqlite3.connect('smartyield_pro.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS listings 
                      (id INTEGER PRIMARY KEY, city TEXT, type TEXT, price INTEGER, sqm INTEGER, 
                       ppm INTEGER, confidence INTEGER, is_renewal INTEGER, date TEXT)''')
    
    benchmarks = [
        ("תל אביב", 68000), ("ירושלים", 45000), ("נתניה", 33000), 
        ("חיפה", 25000), ("באר שבע", 19000), ("רמת גן", 50000),
        ("גבעתיים", 54000), ("הרצליה", 55000), ("ראשון לציון", 35000)
    ]
    cursor.execute('CREATE TABLE IF NOT EXISTS benchmarks (city TEXT PRIMARY KEY, avg_ppm INTEGER)')
    cursor.executemany('INSERT OR REPLACE INTO benchmarks VALUES (?, ?)', benchmarks)
    conn.commit() ; conn.close()

def smart_parse(text):
    conn = sqlite3.connect('smartyield_pro.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", "הרצליה", "ראשון לציון"]
    types = {"פנטהאוז": 1.35, "דירת גן": 1.25, "וילה": 1.50, "דו משפחתי": 1.40, "דירה": 1.0}
    
    text = text.replace(',', '')
    raw_ads = text.split('₪')
    count = 0
    for ad in raw_ads:
        price_match = re.search(r'(\d{6,8})', ad)
        if not price_match: continue
        price = int(price_match.group(1))
        city = next((c for c in cities if c in ad), None)
        p_type = next((t for t in types if t in ad), "דירה")
        
        if city and (600000 < price < 25000000):
            sqm_m = re.search(r'(\d{2,3})\s*(?:מ"ר|מר|מטר)', ad)
            sqm = int(sqm_m.group(1)) if sqm_m else 100
            conf = 50 + (25 if sqm_m else 0) + (25 if len(ad) > 150 else 0)
            cursor.execute("INSERT INTO listings (city, type, price, sqm, ppm, confidence, is_renewal, date) VALUES (?,?,?,?,?,?,?,?)",
                           (city, p_type, price, sqm, price // sqm, conf, 1 if "תמא" in ad or "פינוי" in ad else 0, datetime.now().strftime("%d/%m/%Y")))
            count += 1
    conn.commit() ; conn.close()
    return count

# --- ממשק משתמש ---
init_db()

with st.sidebar:
    st.markdown("### 📥 הזנת נתונים")
    raw_input = st.text_area("הדבק נתונים גולמיים:", height=200)
    if st.button("בצע ניתוח שוק"):
        if raw_input:
            c = smart_parse(raw_input)
            st.success(f"נותחו {c} נכסים")
            st.rerun()
    
    if st.button("🗑️ איפוס מאגר"):
        conn = sqlite3.connect('smartyield_pro.db')
        conn.execute("DELETE FROM listings")
        conn.commit() ; conn.close()
        st.rerun()

# --- דאשבורד ---
try:
    conn = sqlite3.connect('smartyield_pro.db')
    df = pd.read_sql('''
        SELECT l.city as "עיר", l.type as "סוג נכס", l.price as "מחיר", 
               l.sqm as "מ\"ר", l.ppm as "מחיר למ\"ר", l.confidence as "ביטחון",
               l.is_renewal as "התחדשות", b.avg_ppm as "ממוצע_עיר"
        FROM listings l JOIN benchmarks b ON l.city = b.city
    ''', conn)
    df['פוטנציאל רווח'] = ((df['ממוצע_עיר'] - df['מחיר למ\"ר']) * 100.0 / df['ממוצע_עיר'])
    conn.close()
except:
    df = pd.DataFrame()

if not df.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("נכסים שנותחו", len(df))
    c2.metric("רווח ממוצע", f"{df['פוטנציאל רווח'].mean():.1f}%")
    c3.metric("ציון ביטחון", f"{df['ביטחון'].mean():.0f}%")

    st.markdown("---")
    st.subheader("📋 הזדמנויות שאותרו")
    st.dataframe(
        df[["עיר", "סוג נכס", "מחיר", "מ\"ר", "מחיר למ\"ר", "פוטנציאל רווח", "ביטחון", "התחדשות"]].sort_values("פוטנציאל רווח", ascending=False),
        column_config={
            "מחיר": st.column_config.NumberColumn(format="%d ₪"),
            "מחיר למ\"ר": st.column_config.NumberColumn(format="%d ₪"),
            "פוטנציאל רווח": st.column_config.ProgressColumn(format="%.1f%%", min_value=-10, max_value=40),
            "ביטחון": st.column_config.NumberColumn(format="%d%%"),
            "התחדשות": st.column_config.CheckboxColumn()
        },
        use_container_width=True, hide_index=True
    )
else:
    st.info("המערכת מוכנה. הדבק נתונים בסרגל הצד.")
