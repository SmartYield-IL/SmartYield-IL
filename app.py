import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime

# --- 1. מיתוג ועיצוב קצה (High-End UI) ---
st.set_page_config(page_title="SmartYield IL | Alpha Terminal", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@200;400;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Assistant', sans-serif; direction: rtl; text-align: right; }
    .stApp { background: #0f172a; color: #f8fafc; }
    
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #334155;
        text-align: center;
    }
    .main-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e1b4b 100%);
        padding: 2.5rem;
        border-radius: 20px;
        margin-bottom: 30px;
        border-bottom: 4px solid #b8860b;
    }
    </style>
    
    <div class="main-header">
        <h1 style='font-size: 3rem; font-weight: 800; color: #ffffff;'>SmartYield <span style='color:#fbbf24'>PRO</span></h1>
        <p style='font-size: 1.2rem; color: #cbd5e1;'>מערכת ניתוח ארביטראז' נדל"ן - גרסת אלפא 2026</p>
    </div>
    """, unsafe_allow_html=True)

# --- 2. מנוע בינה מלאכותית לזיהוי נכסים (Logic) ---
def init_db():
    conn = sqlite3.connect('smartyield_v2.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS listings 
                      (id INTEGER PRIMARY KEY, city TEXT, type TEXT, price INTEGER, sqm INTEGER, 
                       ppm INTEGER, confidence INTEGER, is_renewal INTEGER, date TEXT)''')
    
    # בנצ'מרק ארצי - מחיר למ"ר ממוצע (דירת 4 חד' סטנדרטית)
    benchmarks = [
        ("תל אביב", 68000), ("נתניה", 33000), ("ירושלים", 45000), 
        ("חיפה", 25000), ("באר שבע", 19000), ("רמת גן", 50000),
        ("גבעתיים", 54000), ("הרצליה", 55000), ("ראשון לציון", 35000)
    ]
    cursor.execute('CREATE TABLE IF NOT EXISTS benchmarks (city TEXT PRIMARY KEY, avg_ppm INTEGER)')
    cursor.executemany('INSERT OR REPLACE INTO benchmarks VALUES (?, ?)', benchmarks)
    conn.commit()
    conn.close()

def deep_scan(text):
    conn = sqlite3.connect('smartyield_v2.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", "הרצליה", "ראשון לציון"]
    
    # מילון זיהוי סוגי נכס ופקטורי תיקון מחיר
    types = {
        "פנטהאוז": 1.35, "דירת גן": 1.25, "וילה": 1.50, "דו משפחתי": 1.40, "קוטג'": 1.40, "דירה": 1.0
    }
    
    text = text.replace(',', '')
    raw_ads = text.split('₪')
    count = 0
    
    for ad in raw_ads:
        price_match = re.search(r'(\d{6,8})', ad)
        if not price_match: continue
        price = int(price_match.group(1))
        if not (650000 < price < 25000000): continue
        
        # זיהוי עיר וסוג נכס
        city = next((c for c in cities if c in ad), None)
        p_type = next((t for t in types if t in ad), "דירה")
        
        if city:
            sqm_m = re.search(r'(\d{2,3})\s*(?:מ"ר|מר|מטר)', ad)
            sqm = int(sqm_m.group(1)) if sqm_m else 100
            ppm = price // sqm
            
            # חישוב מדד ביטחון
            confidence = 60
            if sqm_m: confidence += 20
            if "קומה" in ad: confidence += 10
            if len(ad) > 100: confidence += 10
            
            is_ren = 1 if any(w in ad for w in ["פינוי", "תמא", "התחדשות"]) else 0
            
            cursor.execute("INSERT INTO listings (city, type, price, sqm, ppm, confidence, is_renewal, date) VALUES (?,?,?,?,?,?,?,?)",
                           (city, p_type, price, sqm, ppm, confidence, is_ren, datetime.now().strftime("%Y-%m-%d")))
            count += 1
            
    conn.commit() ; conn.close()
    return count

# --- 3. ממשק המערכת ---
init_db()

with st.sidebar:
    st.markdown("### 🎛️ בקרה והזנה")
    raw_input = st.text_area("הדבק עמוד מודעות מלא:", height=200)
    if st.button("🚀 ניתוח עומק"):
        if raw_input:
            c = deep_scan(raw_input)
            st.success(f"נותחו {c} נכסים")
            st.rerun()
    
    if st.button("🗑️ איפוס מערכת"):
        conn = sqlite3.connect('smartyield_v2.db')
        conn.execute("DELETE FROM listings")
        conn.commit() ; conn.close()
        st.rerun()

# --- 4. תצוגת נתונים חכמה ---
try:
    conn = sqlite3.connect('smartyield_v2.db')
    # שאילתה חכמה שמשקללת סוג נכס
    query = '''
        SELECT l.*, b.avg_ppm,
        CASE 
            WHEN l.type = 'פנטהאוז' THEN b.avg_ppm * 1.35
            WHEN l.type = 'דירת גן' THEN b.avg_ppm * 1.25
            WHEN l.type = 'וילה' THEN b.avg_ppm * 1.50
            ELSE b.avg_ppm
        END as adjusted_benchmark
        FROM listings l JOIN benchmarks b ON l.city = b.city
    '''
    df = pd.read_sql(query, conn)
    df['profit'] = ((df['adjusted_benchmark'] - df['ppm']) * 100.0 / df['adjusted_benchmark'])
    conn.close()
except:
    df = pd.DataFrame()

if not df.empty:
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card'><h4>סה\"כ עסקאות</h4><h2>{len(df)}</h2></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><h4>רווח ממוצע</h4><h2 style='color:#10b981'>{df['profit'].mean():.1f}%</h2></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><h4>מדד ביטחון ממוצע</h4><h2 style='color:#fbbf24'>{df['confidence'].mean():.0f}%</h2></div>", unsafe_allow_html=True)

    st.markdown("### 🎯 הזדמנויות השקעה מבוססות AI")
    
    # הצגת הטבלה המקצועית
    st.dataframe(
        df.sort_values("profit", ascending=False),
        column_config={
            "city": "עיר",
            "type": "סוג נכס",
            "price": st.column_config.NumberColumn("מחיר", format="%d ₪"),
            "ppm": st.column_config.NumberColumn("₪/מ\"ר", format="%d"),
            "profit": st.column_config.ProgressColumn("פוטנציאל רווח", format="%.1f%%", min_value=-20, max_value=50),
            "confidence": st.column_config.NumberColumn("מדד ביטחון", format="%d%%"),
            "is_renewal": st.column_config.CheckboxColumn("פינוי בינוי")
        },
        use_container_width=True, hide_index=True
    )
else:
    st.info("המערכת ריקה. הדבק נתוני שוק כדי להתחיל.")
