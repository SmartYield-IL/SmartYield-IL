import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles

# --- הגדרת רוחב מלא (Wide Mode) ---
st.set_page_config(page_title="SmartYield Pro", layout="wide")

# הפעלת העיצוב
styles.apply_styles()

# --- CSS כפוי להרחבת הטבלה למקסימום ---
st.markdown("""
<style>
    /* הרחבת הקונטיינר הראשי */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 100% !important;
    }
    /* ביטול גלילה מיותרת בטבלה */
    div[data-testid="stDataFrame"] {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v11_clean.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS listings (id INTEGER PRIMARY KEY, city TEXT, type TEXT, price INTEGER, sqm INTEGER, ppm INTEGER, confidence INTEGER, is_renewal INTEGER, address TEXT, date TEXT)")
    
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

# --- פונקציית צייד הכתובות ---
def extract_clean_address(text_segment):
    # 1. רשימת מילים "אסורות" (זבל מאתרי אינטרנט)
    blacklist = ["נגיש", "בקליק", "תפריט", "צור קשר", "whatsapp", "פייסבוק", "דירה למכירה", "נדל\"ן", "טלפון", "קישורים"]
    
    # 2. ניסיון למצוא תבנית של רחוב
    # מחפש: רחוב/שד/דרך + מילים + מספר אופציונלי
    street_match = re.search(r"(?:רחוב|רח'|שד'|שדרות|דרך|סמטת|שכונת)\s+([\u0590-\u05FF\"']+(?:\s+[\u0590-\u05FF\"']+)*\s*\d*)", text_segment)
    
    if street_match:
        address = street_match.group(0).strip()
        # בדיקה שהכתובת לא מכילה מילה אסורה
        if not any(bad_word in address for bad_word in blacklist):
            return address

    # 3. אם לא מצא רחוב, נסה לקחת משפט קצר ונקי
    clean_lines = []
    for line in text_segment.split('\n'):
        line = line.strip()
        if len(line) > 4 and len(line) < 40 and not any(bad in line for bad in blacklist):
            clean_lines.append(line)
    
    if clean_lines:
        return clean_lines[0] # מחזיר את השורה הנקייה הראשונה שנמצאה
    
    return "כתובת כללית"

# --- 2. מנוע סריקה ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v11_clean.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", 
              "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד"]
    
    text = text.replace(',', '')
    raw_ads = text.split('₪')
    count = 0
    
    for i, ad in enumerate(raw_ads):
        price_match = re.search(r'(\d{6,8})', ad)
        if not price_match: continue
        price = int(price_match.group(1))
        
        city = next((c for c in cities if c in ad), None)
        
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
            if len(ad) > 80: conf += 25
            
            is_ren = 0
            if "תמא" in ad or "פינוי" in ad or "התחדשות" in ad: is_ren = 1
            
            # שליחת הטקסט לניקוי יסודי
            # אנו שולחים את 150 התווים שלפני המחיר ואחריו לניתוח
            context = ad[:150]
            clean_addr = extract_clean_address(context)

            sql = "INSERT INTO listings (city, type, price, sqm, ppm, confidence, is_renewal, address, date) VALUES (?,?,?,?,?,?,?,?,?)"
            val = (city, p_type, price, sqm, price // sqm, conf, is_ren, clean_addr, datetime.now().strftime("%d/%m/%Y"))
            cursor.execute(sql, val)
            count += 1
            
    conn.commit()
    conn.close()
    return count

init_db()

# --- 3. ממשק ---
tab1, tab2, tab3 = st.tabs(["🚀 ניתוח נכסים", "📊 מאגר הזדמנויות", "⚙️ ניהול"])

with tab1:
    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
    st.subheader("הזנת נתונים")
    st.info("המערכת מסננת אוטומטית טקסטים של נגישות ותפריטים.")
    raw_input = st.text_area("הדבק עמוד מודעות מלא:", height=250)
    if st.button("בצע ניתוח שוק"):
        if raw_input:
            c = smart_parse(raw_input)
            st.success(f"הניתוח הושלם. {c} נכסים נקלטו.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    try:
        conn = sqlite3.connect('smartyield_v11_clean.db')
        df = pd.read_sql("SELECT * FROM listings", conn)
        bench_df = pd.read_sql("SELECT * FROM benchmarks", conn)
        conn.close()

        if not df.empty:
            df = df.merge(bench_df, on='city', how='left')
            
            def get_factor(t):
                if t == "פנטהאוז": return 1.35
                if t == "דירת גן": return 1.25
                if t == "וילה": return 1.55
                return 1.0

            df['factor'] = df['type'].apply(get_factor)
            df['adj_bench'] = df['avg_ppm'] * df['factor']
            df['profit'] = ((df['adj_bench'] - df['ppm']) * 100.0 / df['adj_bench'])
            
            display_df = df.rename(columns={
                "city": "עיר", "address": "כתובת/אזור", "type": "סוג", "price": "מחיר", 
                "sqm": "מ\"ר", "ppm": "למ\"ר", "profit": "רווח %", 
                "confidence": "ביטחון", "is_renewal": "התחדשות"
            })

            c1, c2, c3 = st.columns(3)
            c1.metric("נכסים", len(df))
            c2.metric("רווח ממוצע", f"{df['profit'].mean():.1f}%")
            c3.metric("ביטחון", f"{df['confidence'].mean():.0f}%")

            st.markdown("---")
            
            # שימוש בהגדרות עמודה כדי למנוע גלילה
            st.dataframe(
                display_df[["עיר", "כתובת/אזור", "סוג", "מחיר", "מ\"ר", "למ\"ר", "רווח %", "ביטחון", "התחדשות"]].sort_values("רווח %", ascending=False),
                column_config={
                    "עיר": st.column_config.TextColumn(width="small"),
                    "כתובת/אזור": st.column_config.TextColumn(width="large"), # העמודה הרחבה ביותר
                    "סוג": st.column_config.TextColumn(width="small"),
                    "מחיר": st.column_config.NumberColumn(format="%d ₪", width="medium"),
                    "למ\"ר": st.column_config.NumberColumn(format="%d ₪", width="small"),
                    "רווח %": st.column_config.ProgressColumn(format="%.1f%%", min_value=-10, max_value=40, width="medium"),
                    "ביטחון": st.column_config.NumberColumn(format="%d%%", width="small"),
                    "התחדשות": st.column_config.CheckboxColumn(width="small")
                },
                use_container_width=True, # מתיחה לכל הרוחב
                hide_index=True,
                height=700
            )
        else:
            st.info("המאגר ריק.")
    except Exception as e:
        st.error(f"שגיאה: {e}")

with tab3:
    if st.button("🗑️ איפוס מאגר נתונים"):
        conn = sqlite3.connect('smartyield_v11_clean.db')
        conn.execute("DELETE FROM listings")
        conn.commit()
        conn.close()
        st.rerun()
