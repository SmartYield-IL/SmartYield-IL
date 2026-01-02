import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

# --- הגדרת עמוד ---
st.set_page_config(page_title="SmartYield Search", layout="wide")
st.markdown("""
<style>
    body { direction: rtl; text-align: right; font-family: 'Segoe UI', sans-serif; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 3em; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- מילון ערים ---
YAD2_CITY_CODES = {
    "תל אביב יפו": 5000, "נתניה": 7400, "חיפה": 4000, "ירושלים": 3000,
    "ראשון לציון": 8300, "באר שבע": 9000, "פתח תקווה": 7900, "אשדוד": 70,
    "חולון": 6600, "רמת גן": 8600, "גבעתיים": 6300, "הרצליה": 6400,
    "רעננה": 8700, "כפר סבא": 6900, "בת ים": 6200, "חדרה": 6500,
    "רחובות": 8400, "אשקלון": 7100, "מודיעין": 1200
}

# --- שליפת המפתח ---
def get_api_key():
    if "ZENROWS_KEY" in st.secrets:
        return st.secrets["ZENROWS_KEY"]
    return None

# --- לוגיקה ---
def build_search_url(city_name, min_rooms, max_rooms, max_price):
    city_code = YAD2_CITY_CODES.get(city_name)
    url = f"https://www.yad2.co.il/realestate/forsale?city={city_code}"
    if min_rooms > 0 or max_rooms < 10: url += f"&rooms={min_rooms}-{max_rooms}"
    if max_price > 0: url += f"&price=0-{max_price}"
    return url

def fetch_data(target_url):
    api_key = get_api_key()
    if not api_key:
        st.error("שגיאת מערכת: מפתח API חסר ב-Secrets.")
        return None

    proxy_url = "https://api.zenrows.com/v1/"
    
    # --- התיקון הגדול כאן ---
    params = {
        "apikey": api_key,
        "url": target_url,
        "js_render": "true",
        "premium_proxy": "true",
        "proxy_country": "il"  # תיקון: במקום country כתבנו proxy_country
    }
    
    try:
        with st.spinner('יוצר קשר מאובטח עם יד2...'):
            response = requests.get(proxy_url, params=params, timeout=60)
            if response.status_code == 200: return response.text
            else:
                st.error(f"שגיאה מהפרוקסי: {response.status_code} - {response.text}")
                return None
    except: return None

def parse_results(html):
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.find_all('div', class_=re.compile(r'(feeditem|feed_item|feed-item)', re.IGNORECASE))
    results = []
    
    for item in items:
        try:
            txt = item.get_text(" ", strip=True)
            price = 0
            p_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*₪', txt)
            if p_match: price = int(p_match.group(1).replace(',', ''))
            if price < 100000: continue

            link = "#"
            a_tag = item.find('a', href=True)
            if a_tag:
                href = a_tag['href']
                link = f"https://www.yad2.co.il{href}" if href.startswith("/") else href

            address = "לא צוין"
            sub = item.find(class_="subtitle")
            if sub: address = sub.get_text(strip=True)
            elif "שכונה" in txt: address = "שכונה מזוהה"

            rooms, floor, sqm = 0, 0, 0
            r_m = re.search(r'(\d+(?:\.\d+)?)\s*חד', txt)
            if r_m: rooms = float(r_m.group(1))
            f_m = re.search(r'קומה\s*(\d+)', txt)
            if f_m: floor = int(f_m.group(1))
            s_m = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', txt)
            for m in s_m:
                val = int(m.group(1))
                if 30 < val < 500 and price/val > 3000:
                    sqm = val; break
            
            ppm = int(price / sqm) if sqm > 0 else 0
            
            # רווח פוטנציאלי
            profit_potential = 0
            if ppm > 0:
                profit_potential = ((30000 - ppm) / 30000) * 100
            
            results.append({"address": address, "rooms": rooms, "floor": floor, "sqm": sqm, "price": price, "ppm": ppm, "profit": profit_potential, "link": link})
        except: continue
    return results

# --- ממשק משתמש ---
st.title("🏡 SmartYield Pro")
st.caption("מנוע חיפוש נדל\"ן אוטונומי")

col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1: city = st.selectbox("עיר", list(YAD2_CITY_CODES.keys()))
with col2: rooms = st.selectbox("חדרים", ["3", "4", "5", "3-4", "4-5"])
with col3: max_price = st.number_input("עד מחיר (מיליונים)", 1.0, 10.0, 2.5, step=0.1)
with col4: 
    st.write("") 
    st.write("") 
    search = st.button("🔍 חפש", type="primary")

if search:
    r_min, r_max = 3, 4
    if rooms == "3": r_min, r_max = 3, 3
    elif rooms == "4": r_min, r_max = 4, 4
    elif rooms == "5": r_min, r_max = 5, 5
    elif rooms == "3-4": r_min, r_max = 3, 4
    elif rooms == "4-5": r_min, r_max = 4, 5
    
    url = build_search_url(city, r_min, r_max, int(max_price * 1000000))
    html = fetch_data(url)
    
    if html:
        data = parse_results(html)
        if data:
            st.success(f"נמצאו {len(data)} נכסים ב{city}")
            df = pd.DataFrame(data)
            
            st.data_editor(
                df[['address', 'price', 'rooms', 'sqm', 'ppm', 'link']],
                column_config={
                    "address": st.column_config.TextColumn("אזור/שכונה", width="medium"),
                    "price": st.column_config.NumberColumn("מחיר", format="%d ₪"),
                    "ppm": st.column_config.NumberColumn("למ\"ר", format="%d ₪"),
                    "link": st.column_config.LinkColumn("צפייה", display_text="פתח מודעה"),
                    "rooms": "חד'", "sqm": "מ\"ר"
                },
                use_container_width=True, hide_index=True
            )
        else: st.warning("החיפוש עבד, אך לא נמצאו תוצאות בטווח המחירים הזה.")
