import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles

# הפעלת עיצוב פרימיום
styles.apply_styles()

# --- 1. מסד נתונים (כולל עמודת תיאור חדשה) ---
def init_db():
    conn = sqlite3.connect('smartyield_v10_pro.db')
    cursor = conn.cursor()
    # הוספנו את עמודת 'description' לזיהוי הנכס
    cursor.execute("CREATE TABLE IF NOT EXISTS listings (id INTEGER PRIMARY KEY, city TEXT, type TEXT, price INTEGER, sqm INTEGER, ppm INTEGER, confidence INTEGER, is_renewal INTEGER, description TEXT, date TEXT)")
    
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

# --- 2. מנוע סריקה חכם (כולל חילוץ הקשר) ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v10_pro.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", 
              "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד"]
    
    # ניקוי בסיסי
    text = text.replace(',', '')
    raw_ads = text.split('₪') # פיצול לפי מחיר
    count = 0
    
    for i, ad in enumerate(raw_ads):
        # זיהוי מחיר
        price_match = re.search(r'(\d{6,8})', ad)
        if not price_match: continue
        price = int(price_match.group(1))
        
        # זיהוי עיר
        city = next((c for c in cities if c in ad), None)
        
        # זיהוי סוג נכס
        p_type = "דירה"
        if "פנטהאוז" in ad: p_type = "פנטהאוז"
        elif "דירת גן" in ad: p_type = "דירת גן"
        elif "וילה" in ad: p_type = "וילה"
        elif "דו משפחתי" in ad: p_type = "דו משפחתי"
        
        if city and (600000 < price < 35000000):
            sqm_match = re.search(r'(\d{2,3})\s*(?:מ"ר|מר|מטר)', ad)
            sqm = int(sqm_match.group(1)) if sqm_match else 100
            
            conf = 50
            if sqm_match: conf += 25
            if len(ad) > 100: conf += 25
            
            is_ren = 0
            if "תמא" in ad or "פינוי" in ad or "התחדשות" in ad: is_ren = 1
            
            # --- הפיצ'ר החדש: חילוץ תיאור/רחוב ---
            # אנחנו לוקחים את 80 התווים שלפני המחיר ואחריו כדי לתת הקשר
            # ומנקים שורות חדשות כדי שייראה יפה בטבלה
            desc = ad[:100].replace('\n', ' ').strip()
            if len(desc) < 5: desc = "פרטים לא זוהו"

            sql = "INSERT INTO listings (city, type, price, sqm, ppm, confidence, is_renewal, description, date) VALUES (?,?,?,?,?,?,?,?,?)"
            val = (city, p_type, price, sqm, price // sqm, conf, is_ren, desc, datetime.now().strftime("%d/%m/%Y"))
            cursor.execute(sql, val)
            count += 1
            
    conn.commit()
    conn.close()
    return count

init_db()

# --- 3. ממשק משתמש ---
tab1, tab2, tab3 = st.tabs(["🚀 ניתוח נכסים", "📊 מאגר הזדמנויות", "⚙️ ניהול"])

with tab1:
    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
    st.subheader("הזנת נתונים")
    st.info("טיפ: העתק את כל הטקסט (כולל רחובות ותיאור) כדי שהמערכת תזהה את הדירה.")
    raw_input = st.text_area("הדבק עמוד מודעות מלא:", height=250)
    if st.button("בצע ניתוח שוק"):
        if raw_input:
            c = smart_parse(raw_input)
            st.success(f"הניתוח הושלם. {c} נכסים התווספו למאגר.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    try:
        conn = sqlite3.connect('smartyield_v10_pro.db')
        df = pd.read_sql("SELECT * FROM listings", conn)
        bench_df = pd.read_sql("SELECT * FROM benchmarks", conn)
        conn.close()

        if not df.empty:
            df = df.merge(bench_df, on='city', how='left')
            
            # חישוב רווח חכם
            def get_factor(t):
                if t == "פנטהאוז": return 1.35
                if t == "דירת גן": return 1.25
                if t == "וילה": return 1.55
                return 1.0

            df['factor'] = df['type'].apply(get_factor)
            df['adj_bench'] = df['avg_ppm'] * df['factor']
            df['profit'] = ((df['adj_bench'] - df['ppm']) * 100.0 / df['adj_bench'])
            
            # שינוי שמות עמודות לתצוגה סופית
            display_df = df.rename(columns={
                "city": "עיר", "description": "זיהוי/רחוב", "type": "סוג", "price": "מחיר", 
                "sqm": "מ\"ר", "ppm": "למ\"ר", "profit": "רווח %", 
                "confidence": "ביטחון", "is_renewal": "התחדשות"
            })

            # כרטיסי מידע למעלה
            c1, c2, c3 = st.columns(3)
            c1.metric("נכסים", len(df))
            c2.metric("רווח ממוצע", f"{df['profit'].mean():.1f}%")
            c3.metric("ביטחון", f"{df['confidence'].mean():.0f}%")

            st.markdown("---")
            
            # --- הטבלה הגדולה ---
            # כאן הגדרנו את סדר העמודות ורוחב מלא
            st.dataframe(
                display_df[["עיר", "זיהוי/רחוב", "סוג", "מחיר", "מ\"ר", "למ\"ר", "רווח %", "ביטחון", "התחדשות"]].sort_values("רווח %", ascending=False),
                column_config={
                    "מחיר": st.column_config.NumberColumn(format="%d ₪"),
                    "למ\"ר": st.column_config.NumberColumn(format="%d ₪"),
                    "רווח %": st.column_config.ProgressColumn(format="%.1f%%", min_value=-15, max_value=45),
                    "ביטחון": st.column_config.NumberColumn(format="%d%%"),
                    "התחדשות": st.column_config.CheckboxColumn(),
                    "זיהוי/רחוב": st.column_config.TextColumn(width="large") # עמודה רחבה לטקסט
                },
                use_container_width=True, # רוחב מלא של המסך!
                hide_index=True,
                height=600 # טבלה גבוהה יותר
            )
        else:
            st.info("המאגר ריק. בצע ניתוח חדש.")
    except Exception as e:
        st.error(f"שגיאה: {e}")

with tab3:
    if st.button("🗑️ איפוס מאגר נתונים"):
        conn = sqlite3.connect('smartyield_v10_pro.db')
        conn.execute("DELETE FROM listings")
        conn.commit()
        conn.close()
        st.rerun()
