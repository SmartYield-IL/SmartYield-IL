import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

# --- הגדרת עמוד ---
st.set_page_config(page_title="Debug Mode", layout="wide")
st.markdown("""<style>body { direction: rtl; text-align: right; font-family: 'Segoe UI'; }</style>""", unsafe_allow_html=True)

# --- בדיקת מפתח (דיבאג) ---
def get_api_key():
    if "ZENROWS_KEY" in st.secrets:
        key = st.secrets["ZENROWS_KEY"]
        # בדיקה שהמפתח לא ריק
        if len(key) > 10:
            return key
    return None

def fetch_data_debug(target_url):
    api_key = get_api_key()
    
    # בדיקה 1: האם המפתח קיים?
    if not api_key:
        st.error("❌ שגיאה 1: המערכת לא מצליחה לקרוא את המפתח מה-Secrets. וודא שעשית Save ו-Reboot.")
        return None
    
    st.info(f"✅ מפתח זוהה (מתחיל ב: {api_key[:4]}...)")
    st.info(f"📡 מנסה להתחבר לכתובת: {target_url}")

    proxy_url = "https://api.zenrows.com/v1/"
    params = {
        "apikey": api_key,
        "url": target_url,
        "js_render": "true",
        "premium_proxy": "true",
        "country": "il"
    }
    
    try:
        response = requests.get(proxy_url, params=params, timeout=60)
        
        # בדיקה 2: מה השרת ענה?
        st.write(f"🔄 קוד תשובה מהשרת: {response.status_code}")
        
        if response.status_code == 200:
            st.success("✅ החיבור הצליח! התקבל HTML.")
            # בדיקה 3: האם קיבלנו דף ריק?
            if len(response.text) < 500:
                st.warning("⚠️ התקבל דף קצר מדי (חשד לחסימה).")
                st.code(response.text) # הצגת התוכן הגולמי
            return response.text
        else:
            st.error(f"❌ שגיאה מהשרת: {response.text}")
            return None
            
    except Exception as e:
        st.error(f"❌ שגיאה בחיבור Python: {str(e)}")
        return None

def parse_results(html):
    soup = BeautifulSoup(html, 'html.parser')
    # בדיקה 4: האם יש בכלל פריטים בדף?
    items = soup.find_all('div', class_=re.compile(r'(feeditem|feed_item|feed-item)', re.IGNORECASE))
    st.write(f"🧐 המנתח מצא {len(items)} אלמנטים של מודעות ב-HTML.")
    
    results = []
    for item in items:
        try:
            txt = item.get_text(" ", strip=True)
            price = 0
            p_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*₪', txt)
            if p_match: price = int(p_match.group(1).replace(',', ''))
            
            # בדיקה 5: האם המחיר הגיוני?
            if price < 100000: continue

            link = "#"
            a_tag = item.find('a', href=True)
            if a_tag:
                href = a_tag['href']
                link = f"https://www.yad2.co.il{href}" if href.startswith("/") else href

            address = "לא צוין"
            sub = item.find(class_="subtitle")
            if sub: address = sub.get_text(strip=True)

            sqm = 0
            s_m = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', txt)
            for m in s_m:
                val = int(m.group(1))
                if 30 < val < 500: sqm = val; break
            
            ppm = int(price / sqm) if sqm > 0 else 0
            results.append({"address": address, "price": price, "sqm": sqm, "ppm": ppm, "link": link})
        except: continue
    return results

# --- ממשק ---
st.title("🛠️ Debug Mode")

if st.button("בצע בדיקה על נתניה (הארד-קוד)"):
    # שימוש בלינק קבוע לנתניה כדי לנטרל בעיות בבניית הלינק
    test_url = "https://www.yad2.co.il/realestate/forsale?city=7400&rooms=3-4"
    
    html = fetch_data_debug(test_url)
    
    if html:
        data = parse_results(html)
        if data:
            st.dataframe(pd.DataFrame(data))
        else:
            st.warning("ה-HTML התקבל אבל לא הצלחנו לחלץ ממנו דירות.")
