import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles

st.set_page_config(page_title="SmartYield Pro", layout="wide")
styles.apply_styles()

# CSS לרוחב מלא ועיצוב טבלה מקצועי
st.markdown("""
<style>
    .block-container { max_width: 100% !important; padding: 1rem; }
    div[data-testid="stDataFrame"] { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 1. מסד נתונים (V16 - Pro Hierarchy) ---
def init_db():
    conn = sqlite3.connect('smartyield_v16_pro.db')
    cursor = conn.cursor()
    # הוספנו עמודת 'rooms' (חדרים)
    cursor.execute("CREATE TABLE IF NOT EXISTS listings (id INTEGER PRIMARY KEY, city TEXT, type TEXT, rooms REAL, price INTEGER, sqm INTEGER, ppm INTEGER, confidence INTEGER, is_renewal INTEGER, address TEXT, original_text TEXT, date TEXT)")
    
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
    blacklist = ["נגיש", "בקליק", "תפריט", "צור קשר", "whatsapp", "פייסבוק", "נדל\"ן", "טלפון", "משרד", "תיווך"]
    street_match = re.search(r"(?:רחוב|רח'|שד'|שדרות|דרך|סמטת|שכונת)\s+([\u0590-\u05FF\"']+(?:\s+[\u0590-\u05FF\"']+)*\s*\d*)", text_segment)
    if street_match:
        address = street_match.group(0).strip()
        if not any(bad in address for bad in blacklist): return address
    clean_lines = [line.strip() for line in text_segment.split('\n') if 4 < len(line.strip()) < 40 and not any(bad in line for bad in blacklist)]
    return clean_lines[0] if clean_lines else "אזור כללי"

# --- מנוע זיהוי נדל"ן מתקדם ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v16_pro.db')
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
        
        # --- 1. זיהוי סוג נכס מדויק ---
        p_type = "דירה"
        if "מגרש" in ad or "קרקע" in ad: p_type = "מגרש/קרקע"
        elif "פנטהאוז" in ad or "גג" in ad: p_type = "פנטהאוז"
        elif "דירת גן" in ad or "גן" in ad: p_type = "דירת גן"
        elif "וילה" in ad or "פרטי" in ad or "קוטג" in ad: p_type = "וילה/בית פרטי"
        elif "דו משפחתי" in ad: p_type = "דו משפחתי"
        
        # --- 2. זיהוי חדרים (כולל חצאי חדרים) ---
        # מחפש תבניות כמו: "4 חדרים", "3.5 חד'", "5 חד"
        rooms_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:חדרים|חד\b|חד\')', ad)
        rooms = float(rooms_match.group(1)) if rooms_match else 0
        
        if city and (600000 < price < 50000000):
            # --- 3. חילוץ מ"ר חכם (מתעלם ממגרשים בחישוב דירות) ---
            
            # ניקוי רעשי מרחקים
            clean_text = re.sub(r'(?:מרחק|כ-|הליכה)\s*\d+\s*(?:מטר|מ"ר|מ\'|מ)', '', ad)
            
            # מציאת מספרים
            sqm_matches = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', clean_text)
            sqm = 0
            
            for m in sqm_matches:
                val = int(m.group(1))
                # אם זה מגרש, אנחנו מחפשים שטח גדול. אם זו דירה, אנו נזהרים ממספרים גדולים מדי.
                if p_type == "מגרש/קרקע":
                    sqm = val # במגרש לוקחים את המספר, אבל לא נחשב רווח לפי מ"ר בנוי
                    break
                else:
                    # לוגיקה לדירות/בתים
                    if val > 350 and p_type == "דירה": continue # דירה לא יכולה להיות 400 מ"ר
                    if (price / val) < 6000: continue # מחיר למ"ר נמוך מדי
                    sqm = val
                    break
            
            # אם לא נמצא מ"ר, שים 0
            if sqm == 0:
                sqm = 1
                ppm = 0
                conf = 10
            else:
                ppm = price // sqm
                conf = 60
                if rooms > 0: conf += 20 # בונוס ביטחון אם מצאנו חדרים
            
            is_ren = 1 if any(w in ad for w in ["תמא", "פינוי", "התחדשות"]) else 0
            
            context = ad[:150]
            clean_addr = extract_clean_address(context)
            proof_snippet = ad[:100].replace('\n', ' ')

            sql = "INSERT INTO listings (city, type, rooms, price, sqm, ppm, confidence, is_renewal, address, original_text, date) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
            val = (city,
