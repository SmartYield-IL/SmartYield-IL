import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles

st.set_page_config(page_title="SmartYield Pro", layout="wide")
styles.apply_styles()

st.markdown("""
<style>
    .block-container { max_width: 100% !important; padding: 1rem; }
    div[data-testid="stDataFrame"] { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 1. מסד נתונים (V14 - Logic Shield) ---
def init_db():
    conn = sqlite3.connect('smartyield_v14_failsafe.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS listings (id INTEGER PRIMARY KEY, city TEXT, type TEXT, price INTEGER, sqm INTEGER, ppm INTEGER, confidence INTEGER, is_renewal INTEGER, address TEXT, original_text TEXT, date TEXT)")
    
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

def extract_clean_address(text_segment):
    blacklist = ["נגיש", "בקליק", "תפריט", "צור קשר", "whatsapp", "פייסבוק", "נדל\"ן", "טלפון"]
    street_match = re.search(r"(?:רחוב|רח'|שד'|שדרות|דרך|סמטת|שכונת)\s+([\u0590-\u05FF\"']+(?:\s+[\u0590-\u05FF\"']+)*\s*\d*)", text_segment)
    if street_match:
        address = street_match.group(0).strip()
        if not any(bad in address for bad in blacklist): return address
    clean_lines = [line.strip() for line in text_segment.split('\n') if 4 < len(line.strip()) < 40 and not any(bad in line for bad in blacklist)]
    return clean_lines[0] if clean_lines else "אזור כללי"

# --- פונקציית ניקוי מ"ר מתקדמת ---
def extract_smart_sqm(text, price):
    # שלב 1: מחיקת מרחקים ידועים (מנקה את הטקסט מ"רעש")
    # מסיר: "150 מטר מהים", "מרחק 100 מ'", "2 דקות", "קומה 15"
    clean_text = re.sub(r'(?:מרחק|כ-|הליכה)\s*\d+\s*(?:מ"ר|מטר|מ\'|מ)', '', text)
    clean_text = re.sub(r'\d+\s*(?:מטר|מ"ר|מ\'|מ)\s*(?:מהים|מהרכבת|מהפארק|מהקניון|מהחוף)', '', clean_text)
    
    # שלב 2: מציאת כל המספרים החשודים כמ"ר
    matches = re.findall(r'(\d{2,3})\s*(?:מ"ר|מר|מטר)', clean_text)
    
    if not matches:
        return 0 # לא נמצא גודל
        
    # שלב 3: בחירת המספר ההגיוני ביותר
    # אם יש כמה מספרים, נבדוק איזה מהם נותן מחיר למ"ר הגיוני (מעל 10,000 ש"ח)
    # למשל: אם המערכת מוצאת "150" וגם "80", והמחיר הוא 2 מיליון:
    # 2,000,000 / 150 = 13,333 (גבולי/נמוך)
    # 2,000,000 / 80 = 25,000 (הגיוני)
    
    best_sqm = 0
    for m in matches:
        sqm_candidate = int(m)
        if sqm_candidate == 0: continue
        ppm = price / sqm_candidate
        
        # פילטר היגיון: מחיר למ"ר לא יכול להיות נמוך מ-7000 (אלא אם זה חורבה) ולא גבוה מ-150,000
        if 7000 < ppm < 150000:
            return sqm_candidate
            
    # אם שום דבר לא הגיוני, נחזיר את הראשון שנמצא אבל נסמן כחשוד
    return int(matches[0])

# --- 2. מנוע סריקה ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v14_failsafe.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", 
              "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד"]
    
    text = text.replace(',', '')
    raw_ads = text.split('₪')
    count = 0
    
    for ad in raw_ads:
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
            # שימוש בפונקציה החדשה לחילוץ מ"ר
            sqm = extract_smart_sqm(ad, price)
            
            # אם לא נמצא מ"ר הגיוני, נקבע ברירת מחדל כדי לא לשבור את המתמטיקה, אבל נוריד ביטחון
            if sqm == 0:
                sqm = 1 # ערך דמי כדי לא לחלק ב-0
                conf = 10 # ביטחון אפסי
                ppm = 0
            else:
                ppm = price // sqm
                conf = 50
                if len(ad) > 80: conf += 25
            
            is_ren = 1 if any(w in ad for w in ["תמא", "פינוי", "התחדשות"]) else 0
            
            context = ad[:150]
            clean_addr = extract_clean_address(context)
            proof_snippet = ad[:100].replace('\n', ' ')

            sql = "INSERT INTO listings (city, type, price, sqm, ppm, confidence, is_renewal, address, original_text, date) VALUES (?,?,?,?,?,?,?,?,?,?)"
            val = (city, p_type, price, sqm, ppm, conf, is_ren, clean_addr, proof_snippet, datetime.now().strftime("%d/%m/%Y"))
            cursor.execute(sql, val)
            count += 1
            
    conn.commit()
    conn.close()
    return count

init_db()

# --- 3. ממשק ---
tab1, tab2, tab3 = st.tabs(["🚀 ניתוח נכסים", "📊 מאגר והוכחות", "⚙️ ניהול"])

with tab1:
    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
    st.subheader("הזנת נתונים")
    raw_input = st.text_area("הדבק עמוד מודעות מלא:", height=250)
    if st.button("בצע ניתוח שוק"):
        if raw_input:
            c = smart_parse(raw_input)
            st.success(f"הניתוח הושלם. {c} נכסים נקלטו.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    try:
        conn = sqlite3.connect('smartyield_v14_failsafe.db')
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
            # טיפול במקרים של מ"ר שגוי (חלוקה ב-1)
            df['profit'] = df.apply(lambda row: ((row['adj_bench'] - row['ppm']) * 100.0 / row['adj_bench']) if row['sqm'] > 1 else 0, axis=1)
            
            display_df = df.rename(columns={
                "city": "עיר", "address": "כתובת/אזור", "type": "סוג", "price": "מחיר", 
                "sqm": "מ\"ר", "ppm": "למ\"ר", "profit": "רווח %", 
                "confidence": "ביטחון", "original_text": "אימות נתונים"
            })

            c1, c2, c3 = st.columns(3)
            c1.metric("נכסים", len(df))
            c2.metric("רווח ממוצע", f"{df[df['sqm'] > 1]['profit'].mean():.1f}%")
            c3.metric("ביטחון", f"{df['confidence'].mean():.0f}%")

            st.markdown("---")
            
            st.dataframe(
                display_df[["עיר", "כתובת/אזור", "סוג", "מחיר", "מ\"ר", "למ\"ר", "רווח %", "ביטחון", "אימות נתונים"]].sort_values("רווח %", ascending=False),
                column_config={
                    "עיר": st.column_config.TextColumn(width="small"),
                    "כתובת/אזור": st.column_config.TextColumn(width="medium"),
                    "סוג": st.column_config.TextColumn(width="small"),
                    "מחיר": st.column_config.NumberColumn(format="%d ₪", width="small"),
                    "מ\"ר": st.column_config.NumberColumn(format="%d", width="small"), # הסרתנו את ה-₪ מהמ"ר
                    "למ\"ר": st.column_config.NumberColumn(format="%d ₪", width="small"),
                    "רווח %": st.column_config.ProgressColumn(format="%.1f%%", min_value=-10, max_value=40, width="small"),
                    "ביטחון": st.column_config.NumberColumn(format="%d%%", width="small"),
                    "אימות נתונים": st.column_config.TextColumn(width="large", help="טקסט המקור")
                },
                use_container_width=True,
                hide_index=True,
                height=700
            )
        else:
            st.info("המאגר ריק.")
    except Exception as e:
        st.error(f"שגיאה: {e}")

with tab3:
    if st.button("🗑️ איפוס מאגר נתונים"):
        conn = sqlite3.connect('smartyield_v14_failsafe.db')
        conn.execute("DELETE FROM listings")
        conn.commit()
        conn.close()
        st.rerun()
