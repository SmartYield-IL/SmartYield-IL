import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime

# --- 1. הגדרות תצוגה ועיצוב ---
st.set_page_config(page_title="SmartYield Israel", layout="wide")

# עיצוב בסיסי ונקי
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { color: #1e3a8a; font-size: 36px; font-weight: 800; text-align: center; margin-bottom: 25px; direction: rtl; }
    .stMetric { border-right: 5px solid #b8860b; background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    <div class="main-header">📊 SmartYield Israel | ניתוח עסקאות נדל״ן</div>
    """, unsafe_allow_html=True)

# --- 2. ניהול בסיס הנתונים ---
def init_db():
    conn = sqlite3.connect('israel_invest.db')
    cursor = conn.cursor()
    # יצירת טבלת נכסים
    cursor.execute('''CREATE TABLE IF NOT EXISTS listings 
                      (id INTEGER PRIMARY KEY, city TEXT, price INTEGER, sqm INTEGER, 
                       price_per_meter INTEGER, is_renewal INTEGER, timestamp TEXT)''')
    
    # טבלת ייחוס ארצית (ממוצעי מ"ר 2026)
    city_data = [
        ("תל אביב", 65000), ("ירושלים", 42000), ("נתניה", 32000), 
        ("חיפה", 24000), ("באר שבע", 18000), ("חולון", 36000),
        ("רמת גן", 48000), ("גבעתיים", 52000), ("אשדוד", 28000), 
        ("רעננה", 45000), ("הוד השרון", 42000), ("ראשון לציון", 33000)
    ]
    cursor.execute('CREATE TABLE IF NOT EXISTS city_benchmarks (city TEXT PRIMARY KEY, avg_sqm_price INTEGER)')
    cursor.executemany('INSERT OR REPLACE INTO city_benchmarks VALUES (?, ?)', city_data)
    conn.commit()
    conn.close()

# --- 3. מנוע חילוץ נתונים ---
def parse_and_store(text):
    conn = sqlite3.connect('israel_invest.db')
    cursor = conn.cursor()
    keywords = ["פינוי בינוי", "תמא", "תמ״א", "התחדשות", "הריסה", "פוטנציאל"]
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "חולון", "רמת גן", "גבעתיים", "אשדוד", "רעננה", "ראשון לציון"]
    
    raw_ads = text.split('₪')
    added_count = 0
    for ad in raw_ads:
        price_match = re.search(r'(\d[\d,]{5,8})', ad)
        if not price_match: continue
        price = int(price_match.group(1).replace(',', ''))
        if price < 400000: continue
        
        sqm_match = re.search(r'(\d{2,3})\s*(?:מ"ר|מר|מטר)', ad)
        sqm = int(sqm_match.group(1)) if sqm_match else 100
        price_per_meter = price // sqm
        
        city_detected = "אחר"
        for c in cities:
            if c in ad:
                city_detected = c
                break
        
        is_renewal = 1 if any(word in ad for word in keywords) else 0
        cursor.execute('''INSERT INTO listings (city, price, sqm, price_per_meter, is_renewal, timestamp) 
                          VALUES (?, ?, ?, ?, ?, ?)''', 
                       (city_detected, price, sqm, price_per_meter, is_renewal, datetime.now().strftime("%Y-%m-%d")))
        added_count += 1
        
    conn.commit()
    conn.close()
    return added_count

# --- 4. ממשק המשתמש ---
init_db()

with st.sidebar:
    st.header("📥 הזנת נתונים")
    raw_input = st.text_area("הדבק נתונים גולמיים ממדלן/יד2:", height=300)
    if st.button("🚀 נתח נתונים"):
        if raw_input:
            count = parse_and_store(raw_input)
            st.success(f"עובדו {count} נכסים בהצלחה")
            st.rerun()
    
    if st.button("🗑️ איפוס מאגר"):
        conn = sqlite3.connect('israel_invest.db')
        conn.execute("DELETE FROM listings")
        conn.commit()
        conn.close()
        st.rerun()

# --- 5. הצגת נתונים וניתוח ---
# הגנה מפני טבלה ריקה בשימוש ראשון
try:
    conn = sqlite3.connect('israel_invest.db')
    query = '''
        SELECT l.city as עיר, l.price as מחיר, l.sqm as "מ\"ר", 
               l.price_per_meter as "מחיר למ\"ר", 
               b.avg_sqm_price as "ממוצע עיר",
               ((b.avg_sqm_price - l.price_per_meter) * 100.0 / b.avg_sqm_price) as "פער רווח %",
               l.is_renewal as "פינוי בינוי"
        FROM listings l
        JOIN city_benchmarks b ON l.city = b.city
    '''
    df = pd.read_sql(query, conn)
    conn.close()
except:
    df = pd.DataFrame()

if not df.empty:
    # הצגת נתונים אם המאגר לא ריק
    c1, c2, c3 = st.columns(3)
    c1.metric("נכסים במערכת", len(df))
    c2.metric("רווח ממוצע", f"{df['פער רווח %'].mean():.1f}%")
    c3.metric("הזדמנות שיא", f"{df['פער רווח %'].max():.1f}%")

    st.subheader("📋 עסקאות מאומתות")
    cities_sel = st.multiselect("סנן לפי ערים", df['עיר'].unique(), default=df['עיר'].unique())
    filtered = df[df['עיר'].isin(cities_sel)]

    st.dataframe(
        filtered.sort_values("פער רווח %", ascending=False).style.format({
            "מחיר": "{:,.0f} ₪", "מחיר למ\"ר": "{:,.0f} ₪", "ממוצע עיר": "{:,.0f} ₪", "פער רווח %": "{:.1f}%"
        }).background_gradient(subset=['פער רווח %'], cmap='RdYlGn'),
        use_container_width=True, hide_index=True
    )
else:
    # הודעה ידידותית בשימוש ראשון
    st.info("👋 ברוך הבא ל-SmartYield! המערכת מוכנה לשימוש. אנא הדבק נתונים גולמיים בתפריט הצד כדי להתחיל בניתוח.")
