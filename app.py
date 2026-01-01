import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime

# --- 1. עיצוב ---
st.set_page_config(page_title="SmartYield Israel", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { color: #1e3a8a; font-size: 36px; font-weight: 800; text-align: center; direction: rtl; }
    </style>
    <div class="main-header">📊 SmartYield Israel | ניתוח נדל״ן חכם</div>
    """, unsafe_allow_html=True)

# --- 2. בסיס נתונים ---
def init_db():
    conn = sqlite3.connect('israel_invest.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS listings 
                      (id INTEGER PRIMARY KEY, city TEXT, price INTEGER, sqm INTEGER, 
                       price_per_meter INTEGER, is_renewal INTEGER, timestamp TEXT)''')
    
    city_data = [
        ("תל אביב", 65000), ("ירושלים", 42000), ("נתניה", 32000), 
        ("חיפה", 24000), ("באר שבע", 18000), ("חולון", 36000),
        ("רמת גן", 48000), ("גבעתיים", 52000), ("אשדוד", 28000), 
        ("רעננה", 45000), ("הוד השרון", 42000), ("ראשון לציון", 33000),
        ("פתח תקווה", 30000), ("הרצליה", 50000), ("רחובות", 27000)
    ]
    cursor.execute('CREATE TABLE IF NOT EXISTS city_benchmarks (city TEXT PRIMARY KEY, avg_sqm_price INTEGER)')
    cursor.executemany('INSERT OR REPLACE INTO city_benchmarks VALUES (?, ?)', city_data)
    conn.commit()
    conn.close()

# --- 3. מנוע סריקה משופר (Deep Scan) ---
def parse_and_store(text):
    conn = sqlite3.connect('israel_invest.db')
    cursor = conn.cursor()
    
    # רשימת ערים מורחבת
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "חולון", "רמת גן", 
              "גבעתיים", "אשדוד", "רעננה", "ראשון לציון", "פתח תקווה", "הרצליה", "רחובות"]
    
    # ניקוי פסיקים ממספרים כדי להקל על הזיהוי
    text = text.replace(',', '')
    
    # חיפוש כל המחירים בטקסט (5-8 ספרות)
    prices = re.findall(r'(\d{6,8})', text)
    added_count = 0
    
    # לכל מחיר שנמצא, נחפש את העיר הקרובה אליו ביותר בטקסט
    for p in prices:
        price = int(p)
        if 500000 < price < 20000000:
            # מציאת המיקום של המחיר בטקסט
            pos = text.find(p)
            # לקיחת "רדיוס" של 200 תווים סביב המחיר לחיפוש עיר
            context = text[max(0, pos-150) : min(len(text), pos+150)]
            
            city_detected = "אחר"
            for c in cities:
                if c in context:
                    city_detected = c
                    break
            
            if city_detected != "אחר":
                # זיהוי מ"ר באותו רדיוס
                sqm_match = re.search(r'(\d{2,3})\s*(?:מ"ר|מר|מטר)', context)
                sqm = int(sqm_match.group(1)) if sqm_match else 100
                
                is_renewal = 1 if any(w in context for w in ["פינוי", "תמא", "תמ״א", "התחדשות"]) else 0
                
                cursor.execute('''INSERT INTO listings (city, price, sqm, price_per_meter, is_renewal, timestamp) 
                                  VALUES (?, ?, ?, ?, ?, ?)''', 
                               (city_detected, price, sqm, price // sqm, is_renewal, datetime.now().strftime("%Y-%m-%d")))
                added_count += 1
                
    conn.commit()
    conn.close()
    return added_count

# --- 4. ממשק ---
init_db()

with st.sidebar:
    st.header("📥 הזנת נתונים")
    raw_input = st.text_area("הדבק כאן את כל עמוד המודעות:", height=300)
    if st.button("🚀 נתח נתונים"):
        if raw_input:
            count = parse_and_store(raw_input)
            if count > 0:
                st.success(f"הצלחנו! נמצאו {count} נכסים.")
                st.rerun()
            else:
                st.error("לא נמצאו נכסים. נסה להעתיק שוב, וודא שיש מחירים בטקסט.")

    if st.button("🗑️ ניקוי מאגר"):
        conn = sqlite3.connect('israel_invest.db')
        conn.execute("DELETE FROM listings")
        conn.commit()
        conn.close()
        st.rerun()

# --- 5. דאשבורד ---
try:
    conn = sqlite3.connect('israel_invest.db')
    df = pd.read_sql('''SELECT l.*, b.avg_sqm_price, 
                        ((b.avg_sqm_price - l.price_per_meter) * 100.0 / b.avg_sqm_price) as profit_pct
                        FROM listings l JOIN city_benchmarks b ON l.city = b.city''', conn)
    conn.close()
except:
    df = pd.DataFrame()

if not df.empty:
    st.subheader("📋 הזדמנויות שאותרו")
    st.dataframe(df.sort_values("profit_pct", ascending=False), use_container_width=True, hide_index=True)
else:
    st.info("המערכת ריקה. הדבק נתונים בצד.")
