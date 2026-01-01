import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles

st.set_page_config(page_title="SmartYield Pro", layout="wide")
styles.apply_styles()

# CSS לרוחב מלא
st.markdown("""
<style>
    .block-container { max_width: 100% !important; padding: 1rem; }
    div[data-testid="stDataFrame"] { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v17_stable.db')
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

def extract_clean_address(text_segment):
    blacklist = ["נגיש", "בקליק", "תפריט", "צור קשר", "whatsapp", "פייסבוק", "נדל\"ן", "טלפון", "משרד", "תיווך"]
    street_match = re.search(r"(?:רחוב|רח'|שד'|שדרות|דרך|סמטת|שכונת)\s+([\u0590-\u05FF\"']+(?:\s+[\u0590-\u05FF\"']+)*\s*\d*)", text_segment)
    if street_match:
        address = street_match.group(0).strip()
        if not any(bad in address for bad in blacklist): return address
    clean_lines = [line.strip() for line in text_segment.split('\n') if 4 < len(line.strip()) < 40 and not any(bad in line for bad in blacklist)]
    return clean_lines[0] if clean_lines else "אזור כללי"

# --- מנוע זיהוי ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v17_stable.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", 
              "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד"]
    
    text = text.replace(',', '')
    raw_ads = text.split('₪')
    count = 0
    
    for ad in raw_ads:
        price_match = re.search(r'(\d{6,8})', ad)
        if not price_match: continue
