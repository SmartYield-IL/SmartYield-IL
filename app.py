import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime

# --- הגדרת עמוד בסיסית וחזקה ---
st.set_page_config(page_title="SmartYield Pro", layout="wide")

# CSS בסיסי ליישור לימין ורוחב מלא - בלי להסתיר אלמנטים
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;700;800&display=swap');
    html, body, [class*="css"] { 
        font-family: 'Assistant', sans-serif; 
        direction: rtl; 
        text-align: right; 
    }
    /* הרחבת אזור העבודה למקסימום */
    .block-container { 
        padding-top: 1rem; 
        padding-bottom: 5rem; 
        max-width: 100% !important;
    }
    /* עיצוב כותרת */
    h1 { color: #1e3a8a; }
</style>
""", unsafe_allow_html=True)

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v18_final.db')
    cursor = conn.cursor()
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

# --- מנוע ניקוי כתובת ---
def extract_clean_address(text_segment):
    blacklist = ["נגיש", "בקליק", "תפריט", "צור קשר", "whatsapp", "פייסבוק", "נדל\"ן", "טלפון", "משרד", "תיווך"]
    street_match = re.search(r"(?:רחוב|רח'|שד'|שדרות|דרך|סמטת|שכונת)\s+([\u0590-\u05FF\"']+(?:\s+[\u0590-\u05FF\"']+)*\s*\d*)", text_segment)
    if street_match:
        address = street_match.group(0).strip()
        if not any(bad in address for bad in blacklist): return address
    clean_lines = [line.strip() for line in text_segment.split('\n') if 4 < len(line.strip()) < 40 and not any(bad in line for bad in blacklist)]
    return clean_lines[0] if clean_lines else "אזור כללי"

# --- מנוע ניתוח (הלוגיקה שעבדה) ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v18_final.db')
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
        if "מגרש" in ad or "קרקע" in ad: p_type = "מגרש/קרקע"
        elif "פנטהאוז" in ad or "גג" in ad: p_type = "פנטהאוז"
        elif "דירת גן" in ad or "גן" in ad: p_type = "דירת גן"
        elif "וילה" in ad or "פרטי" in ad or "קוטג" in ad: p_type = "וילה/בית פרטי"
        elif "דו משפחתי" in ad: p_type = "דו משפחתי"
        
        rooms_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:חדרים|חד\b|חד\')', ad)
        rooms = float(rooms_match.group(1)) if rooms_match else 0
        
        if city and (600000 < price < 50000000):
            clean_text = re.sub(r'(?:מרחק|כ-|הליכה)\s*\d+\s*(?:מטר|מ"ר|מ\'|מ)', '', ad)
            sqm_matches = re.finditer(r'(\d{2,
