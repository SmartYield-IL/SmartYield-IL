import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import styles

# הפעלת העיצוב
styles.apply_styles()

# --- 1. מסד נתונים ---
def init_db():
    conn = sqlite3.connect('smartyield_v7_final.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS listings 
                      (id INTEGER PRIMARY KEY, city TEXT, type TEXT, price INTEGER, sqm INTEGER, 
                       ppm INTEGER, confidence INTEGER, is_renewal INTEGER, date TEXT)''')
    
    benchmarks = [
        ("תל אביב", 68000), ("ירושלים", 45000), ("נתניה", 33000), 
        ("חיפה", 25000), ("באר שבע", 19000), ("רמת גן", 50000),
        ("גבעתיים", 54000), ("הרצליה", 55000), ("ראשון לציון", 35000),
        ("פתח תקווה", 31000), ("חולון", 36000), ("אשדוד", 29000)
    ]
    cursor.execute('CREATE TABLE IF NOT EXISTS benchmarks (city TEXT PRIMARY KEY, avg_ppm INTEGER)')
    cursor.executemany('INSERT OR REPLACE INTO benchmarks VALUES (?, ?)', benchmarks)
    conn.commit()
    conn.close()

# --- 2. מנוע סריקה ---
def smart_parse(text):
    conn = sqlite3.connect('smartyield_v7_final.db')
    cursor = conn.cursor()
    cities = ["תל אביב", "ירושלים", "נתניה", "חיפה", "באר שבע", "רמת גן", "גבעתיים", 
              "הרצליה", "ראשון לציון", "פתח תקווה", "חולון", "אשדוד"]
    
    # הגדרת סוגי נכס בצורה בטוחה
    text = text.replace(',', '')
    raw_ads = text.split('₪')
    count = 0
    
    for ad in raw_ads:
        price_match = re.search(r'(\d{6,8})', ad)
        if not price_match: continue
        price = int(price_match.group(1))
        
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
            
            # חישוב מדד ביטחון
            conf = 50 + (25 if sqm_match else 0) + (25 if len(ad) > 130 else 0)
            is_ren = 1 if any(w in ad for w in ["תמא", "פינוי", "התחדשות"]) else 0
            
            cursor.execute("""INSERT INTO listings (city, type, price, sqm, ppm, confidence, is_
