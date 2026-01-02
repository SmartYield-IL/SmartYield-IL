import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# --- הגדרת עמוד ---
st.set_page_config(page_title="Real Estate Search Engine", layout="wide")
st.markdown("""<style>body { direction: rtl; text-align: right; font-family: 'Segoe UI'; }</style>""", unsafe_allow_html=True)

# --- מילון קודי ערים של יד2 (המוח שמאחורי הקלעים) ---
YAD2_CITY_CODES = {
    "תל אביב יפו": 5000,
    "נתניה": 7400,
    "חיפה": 4000,
    "ירושלים": 3000,
    "ראשון לציון": 8300,
    "באר שבע": 9000,
    "פתח תקווה": 7900,
    "אשדוד": 70,
    "חולון": 6600,
    "רמת גן": 8600,
    "גבעתיים": 6300,
    "הרצליה": 6400,
    "רעננה": 8700,
    "כפר סבא": 6900,
    "בת ים": 6200,
    "חדרה": 6500,
    "רחובות": 8400,
    "אשקלון": 7100,
    "מודיעין": 1200
}

# --- 1. בניית הלינק ליד2 באופן עצמאי ---
def build_search_url(city_name, min_rooms, max_rooms, min_price, max_price):
    city_code = YAD2_CITY_CODES.get(city_name)
    if not city_code: return None
    
    # בניית ה-URL המדויק שיד2 מצפים לקבל
    url = f"https://www.yad2.co.il/realestate/forsale?city={city_code}"
    
    # הוספת חדרים
    if min_rooms > 0 or max_rooms < 10:
        url += f"&rooms={min_rooms}-{max_rooms}"
    
    # הוספת מחיר
    if max_price > 0:
        url += f"&price={min_price}-{max_price}"
        
    return url

# --- 2. שליחה ל-ZenRows (עוקף חסימות) ---
def fetch_data(target_url, api_key):
    proxy_url = "https://api.zenrows.com/v1/"
    params = {
        "apikey": api_key,
        "url": target_url,
        "js_render": "true",
        "premium_proxy": "true",
        "country": "il"
    }
    
    try:
        with st.spinner(f'🤖 הרובוט סורק את {target_url}...'):
            response = requests.get(proxy_url, params=params, timeout=60)
            if response.status_code == 200: return response.text
            else: st.error(f"תקלה בחיבור: {response.status_code}"); return None
    except Exception as e:
        st.error(f"שגיאה: {str(e)}")
        return None

# --- 3. ניתוח התוצאות ---
def parse_results(html):
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.find_all('div', class_=re.compile(r'(feeditem|feed_item|feed-item)', re.IGNORECASE))
    
    results = []
    for item in items:
        try:
            txt = item.get_text(" ", strip=True)
            
            # מחיר
            price = 0
            p_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*₪', txt)
            if p_match: price = int(p_match.group(1).replace(',', ''))
            if price < 100000: continue

            # לינק
            link = "#"
            a_tag = item.find('a', href=True)
            if a_tag: 
                href = a_tag['href']
                link = f"https://www.yad2.co.il{href}" if href.startswith("/") else href

            # כתובת
            address = "לא צוין"
            sub = item.find(class_="subtitle")
            if sub: address = sub.get_text(strip=True)
            elif "שכונה" in txt: address = "שכונה מזוהה בטקסט"

            # חדרים, קומה, מ"ר
            rooms, floor, sqm = 0, 0, 0
            
            r_m = re.search(r'(\d+(?:\.\d+)?)\s*חד', txt)
            if r_m: rooms = float(r_m.group(1))
            
            f_m = re.search(r'קומה\s*(\d+)', txt)
            if f_m: floor = int(f_m.group(1))
            
            s_matches = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', txt)
            for m in s_matches:
                val = int(m.group(1))
                if 30 < val < 500 and price/val > 3000:
                    sqm = val; break
            
            ppm = int(price / sqm) if sqm > 0 else 0
            
            results.append({
                "address": address, "city": "תוצאה", "rooms": rooms, "floor": floor,
                "sqm": sqm, "price": price, "ppm": ppm, "link": link
            })
        except: continue
    return results

# --- הממשק החדש (הסטארטאפ) ---
st.title("🔎 Real Estate Search Engine")
st.caption("חפש דירות ביד2 ישירות מכאן - ללא צורך לצאת מהאתר.")

# סרגל הגדרות בצד (שמים את המפתח פעם אחת ושוכחים)
with st.sidebar:
    st.header("🔑 מפתח גישה")
    api_key = st.text_input("ZenRows API Key", type="password")
    st.info("הירשם ב-zenrows.com לקבלת מפתח חינם")

# מנוע החיפוש הראשי
st.container()
c1, c2, c3 = st.columns([1, 1, 1])

with c1:
    city = st.selectbox("עיר", list(YAD2_CITY_CODES.keys()))
with c2:
    rooms_range = st.slider("טווח חדרים", 1.0, 7.0, (3.0, 5.0), step=0.5)
with c3:
    max_p = st.number_input("מחיר מקסימלי", 500000, 10000000, 3000000, step=100000)

if st.button("🔎 חפש לי דירות", type="primary", use_container_width=True):
    if not api_key:
        st.error("חסר מפתח API בצד ימין!")
    else:
        # 1. יצירת הלינק האוטומטית
        generated_url = build_search_url(city, rooms_range[0], rooms_range[1], 0, max_p)
        # st.write(f"Debug URL: {generated_url}") # לבדיקה
        
        # 2. שליחת הרובוט
        html = fetch_data(generated_url, api_key)
        
        # 3. הצגת תוצאות
        if html:
            data = parse_results(html)
            if data:
                df = pd.DataFrame(data)
                
                st.success(f"נמצאו {len(df)} דירות ב{city}!")
                
                # טבלה אינטראקטיבית עם תמונות ולינקים
                st.data_editor(
                    df[['address', 'rooms', 'floor', 'sqm', 'price', 'ppm', 'link']],
                    column_config={
                        "address": st.column_config.TextColumn("כתובת", width="medium"),
                        "price": st.column_config.NumberColumn("מחיר", format="%d ₪"),
                        "ppm": st.column_config.NumberColumn("למ\"ר", format="%d ₪"),
                        "link": st.column_config.LinkColumn("צפייה", display_text="פתח מודעה 🔗"),
                        "rooms": st.column_config.NumberColumn("חד'", format="%.1f"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("החיפוש עבד, אך לא נמצאו תוצאות שתואמות את הסינון.")
