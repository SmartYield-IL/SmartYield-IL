import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles

# הפעלת העיצוב (הלשוניות למעלה והכותרת היוקרתית)
styles.apply_styles()

# --- לוגיקה עסקית ומסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v4.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS listings 
                      (id INTEGER PRIMARY KEY, city TEXT, type TEXT, price INTEGER, sqm INTEGER, 
                       ppm INTEGER, confidence INTEGER, is_renewal INTEGER, date TEXT)''')
    
    # רשימת בנצ'מרק מורחבת (ממוצע מ"ר 2026)
    benchmarks = [
        ("תל אביב", 68000), ("ירושלים", 45000), ("נתניה", 33000), 
        ("חיפה", 25000), ("באר שבע", 19000), ("רמת גן", 50000),
        ("גבעתיים", 54000), ("הרצליה", 55000), ("ראשון לציון", 35000),
        ("פתח תקווה", 31000), ("אשדוד", 28500), ("חולון", 36000),
        ("בת ים", 34000), ("רעננה", 46000), ("חדרה", 22000)
    ]
    cursor.execute('CREATE TABLE IF NOT EXISTS benchmarks (city TEXT PRIMARY KEY, avg_ppm INTEGER)')
    cursor.executemany('INSERT OR REPLACE INTO benchmarks VALUES (?, ?)', benchmarks)
    conn.commit()
    conn.close()

def smart_parse(text):
    conn = sqlite3.connect('smartyield_v4.db')
    cursor = conn.cursor()
    # רשימת ערים לזיהוי בטקסט
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", 
              "הרצליה", "ראשון לציון", "פתח תקווה", "אשדוד", "חולון", "בת ים", "רעננה", "חדרה"]
    
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
        
        if city and (500000 < price < 30000000):
            sqm_m = re.search(r'(\d{2,3})\s*(?:מ"ר|מר|מטר)', ad)
            sqm = int(sqm_m.group(1)) if sqm_m else 100
            ppm = price // sqm
            
            # חישוב מדד ביטחון
            conf = 50 + (25 if sqm_m else 0) + (25 if len(ad) > 120 else 0)
            is_ren = 1 if any(w in ad for w in ["תמא", "פינוי", "התחדשות"]) else 0
            
            cursor.execute("""INSERT INTO listings (city, type, price, sqm, ppm, confidence, is_renewal, date) 
                              VALUES (?,?,?,?,?,?,?,?)""",
                           (city, p_type, price, sqm, ppm, conf, is_ren, datetime.now().strftime("%d/%m/%Y")))
            count += 1
            
    conn.commit()
    conn.close()
    return count

init_db()

# --- מבנה לשוניות ---
tab1, tab2, tab3 = st.tabs(["🚀 ניתוח והזנה", "📈 מאגר הזדמנויות", "ℹ️ ניהול מערכת"])

with tab1:
    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
    st.subheader("מרכז ניתוח נתונים גולמיים")
    raw_input = st.text_area("הדבק כאן עמוד שלם ממדלן או יד2:", height=250, placeholder="המערכת תסנן כותרות ורעשי רקע לבד...")
    
    if st.button("בצע ניתוח עומק"):
        if raw_input:
            c = smart_parse(raw_input)
            if c > 0:
                st.success(f"הניתוח הושלם: {c} נכסים התווספו למאגר.")
                # הבלונים הוסרו לבקשתך
            else:
                st.warning("לא זוהו נכסים תקינים בטקסט. וודא שיש מחיר ושם עיר.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    try:
        conn = sqlite3.connect('smartyield_v4.db')
        # שימוש ב-LEFT JOIN כדי להבטיח שכל המודעות יופיעו גם אם אין בנצ'מרק
        query = '''
            SELECT l.city as "עיר", l.type as "סוג נכס", l.price as "מחיר", 
                   l.sqm as "מ\"ר", l.ppm as "מחיר למ\"ר", l.confidence as "ביטחון",
                   l.is_renewal as "התחדשות", b.avg_ppm as "ממוצע_עיר"
            FROM listings l 
            LEFT JOIN benchmarks b ON l.city = b.city
        '''
        df = pd.read_sql(query, conn)
        
        # חישוב רווח מותאם לסוג נכס (עם טיפול בערכים חסרים)
        df['ממוצע_עיר'] = df['ממוצע_עיר'].fillna(df['מחיר למ\"ר']) # אם אין בנצ'מרק, אל תראה רווח
        df['פוטנציאל רווח'] = ((df['ממוצע_עיר'] - df['מחיר למ\"ר']) * 100.0 / df['ממוצע_עיר'])
        conn.close()
    except Exception as e:
        st.error(f"שגיאת מאגר: {e}")
        df = pd.DataFrame()

    if not df.empty:
        # מטריקות עליונות
        m1, m2, m3 = st.columns(3)
        m1.metric("נכסים במאגר", len(df))
        m2.metric("רווח פוטנציאלי ממוצע", f"{df['פוטנציאל רווח'].mean():.1f}%")
        m3.metric("מדד ביטחון דאטה", f"{df['ביטחון'].mean():.0f}%")

        st.markdown("---")
        # טבלה מקצועית
        st.dataframe(
            df[["עיר", "סוג נכס", "מחיר", "מ\"ר", "מחיר למ\"ר", "פוטנציאל רווח", "ביטחון", "התחדשות"]].sort_values("פוטנציאל רווח", ascending=False),
            column_config={
                "מחיר": st.column_config.NumberColumn(format="%d ₪"),
                "מחיר למ\"ר": st.column_config.NumberColumn(format="%d ₪"),
                "פוטנציאל רווח": st.column_config.ProgressColumn(format="%.1f%%", min_value=-15, max_value=45),
                "ביטחון": st.column_config.NumberColumn(format="%d%%"),
                "התחדשות": st.column_config.CheckboxColumn()
            },
            use_container_width=True, hide_index=True
        )
    else:
        st.info("המאגר ריק כרגע. עבור ללשונית הניתוח והזן נתונים.")

with tab3:
    st.subheader("הגדרות וניהול")
    if st.button("🗑️ מחק את כל היסטוריית הניתוחים"):
        conn = sqlite3.connect('smartyield_v4.db')
        conn.execute("DELETE FROM listings")
        conn.commit() ; conn.close()
        st.rerun()
