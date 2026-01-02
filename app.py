import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import random

# --- הגדרת עמוד ---
st.set_page_config(page_title="Real Estate Hunter V25", layout="wide")

# --- CSS מקצועי ---
st.markdown("""
<style>
    body { direction: rtl; text-align: right; font-family: 'Segoe UI', sans-serif; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; border-radius: 8px; padding: 10px; border: 1px solid #dee2e6; }
</style>
""", unsafe_allow_html=True)

# --- קונפיגורציה לסטארטאפ (כאן תכניס פרוקסי בעתיד) ---
PROXY_SERVER = None # דוגמה: "http://user:pass@gate.smartproxy.com:7000"

def get_driver():
    options = Options()
    options.add_argument("--headless") # רץ ברקע
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # התחזות לדפדפן רגיל לחלוטין
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    options.add_argument("--window-size=1920,1080")
    
    if PROXY_SERVER:
        options.add_argument(f'--proxy-server={PROXY_SERVER}')
        
    return webdriver.Chrome(options=options)

def extract_yad2_data(driver, url):
    data = []
    status = st.empty()
    bar = st.progress(0)
    
    status.info("🕵️ מתחבר לאתר ומנסה לעקוף הגנות...")
    driver.get(url)
    
    # השהייה רנדומלית וגלילה מדורגת (חיקוי אנושי)
    for i in range(1, 6):
        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {i/5});")
        time.sleep(random.uniform(1.5, 3.0))
        bar.progress(i * 10)

    status.info("extraction... שואב נתונים...")
    
    # זיהוי כל הכרטיסים בעמוד (Feed Items)
    # אנו משתמשים ב-Selectors גנריים כי יד2 משנים שמות של קלאסים
    # אבל המבנה של "feeditem" נשאר יחסית קבוע
    items = driver.find_elements(By.XPATH, "//div[contains(@class, 'feeditem') or contains(@class, 'feed_item')]")
    
    if not items:
        # ניסיון שני - אולי המבנה שונה
        items = driver.find_elements(By.CLASS_NAME, "feed-item-base")

    total = len(items)
    status.write(f"מצאתי {total} מודעות פוטנציאליות. מתחיל עיבוד...")
    
    for idx, item in enumerate(items):
        try:
            # אובייקט זמני
            listing = {
                "address": "לא צוין",
                "price": 0,
                "rooms": 0,
                "sqm": 0,
                "floor": 0,
                "link": "#"
            }
            
            # 1. חילוץ קישור (Link) - הכי חשוב!
            try:
                # מחפש תגית 'a' בתוך הכרטיס
                link_elem = item.find_element(By.TAG_NAME, "a")
                href = link_elem.get_attribute("href")
                if href and "yad2" in href:
                    listing["link"] = href
            except: pass

            # 2. חילוץ מחיר
            try:
                text_content = item.text
                import re
                price_match = re.search(r'(\d{1,3}(?:,\d{3})*)\s*₪', text_content)
                if price_match:
                    p = price_match.group(1).replace(',', '')
                    listing["price"] = int(p)
            except: pass
            
            # אם אין מחיר, מדלגים (לא מעניין)
            if listing["price"] < 100000: continue

            # 3. חילוץ כתובת (נמצאת לרוב בכותרת המשנית)
            try:
                # מנסה למצוא את האלמנט של הכתובת לפי מיקום יחסי או קלאס נפוץ
                subtitle = item.find_element(By.CLASS_NAME, "subtitle").text
                listing["address"] = subtitle
            except:
                # Fallback: מנסה לחלץ מהטקסט הכללי
                lines = item.text.split('\n')
                for line in lines:
                    if "רחוב" in line or "דרך" in line or "שכונה" in line:
                        listing["address"] = line
                        break

            # 4. חילוץ נתונים טכניים (חדרים, מ"ר, קומה)
            # יד2 שמים את זה בקוביות קטנות. ננסה לחלץ מהטקסט המלא בצורה חכמה
            full_text = item.text.replace('\n', ' ')
            
            # חדרים
            r_match = re.search(r'(\d+(?:\.\d+)?)\s*חד', full_text)
            if r_match: listing["rooms"] = float(r_match.group(1))
            
            # מ"ר
            s_matches = re.finditer(r'(\d{2,4})\s*(?:מ"ר|מר|מטר)', full_text)
            for m in s_matches:
                val = int(m.group(1))
                if val > 30 and (listing["price"] / val > 4000): # סינון רעשים
                    listing["sqm"] = val
                    break
            
            # קומה
            f_match = re.search(r'קומה\s*(\d+)', full_text)
            if f_match: listing["floor"] = int(f_match.group(1))

            data.append(listing)
            
        except Exception as e:
            continue # כרטיס דפוק, עוברים הלאה

        # עדכון פרוגרס בר
        bar.progress(min((idx + 1) / total, 1.0))

    status.success("סיימתי!")
    return data

# --- ממשק ---
st.title("🦅 Real Estate Hunter (Startup Mode)")
st.write("מערכת סריקה מתקדמת עם חילוץ לינקים ומיקומים.")

col1, col2 = st.columns([3, 1])
with col1:
    search_url = st.text_input("הדבק כתובת URL של חיפוש מיד2:", placeholder="https://www.yad2.co.il/realestate/forsale?city=7400")

with col2:
    st.write("") # Spacer
    st.write("")
    run_btn = st.button("🚀 הפעל צייד", type="primary")

if run_btn and search_url:
    driver = get_driver()
    try:
        results = extract_yad2_data(driver, search_url)
        
        if results:
            df = pd.DataFrame(results)
            
            # חישובים
            df['ppm'] = df.apply(lambda x: int(x['price'] / x['sqm']) if x['sqm'] > 0 else 0, axis=1)
            
            # סידור עמודות
            display_df = df[['address', 'rooms', 'floor', 'sqm', 'price', 'ppm', 'link']].copy()
            
            # הפיכת הלינק ללחיץ
            st.data_editor(
                display_df,
                column_config={
                    "address": st.column_config.TextColumn("כתובת", width="medium"),
                    "price": st.column_config.NumberColumn("מחיר", format="%d ₪"),
                    "ppm": st.column_config.NumberColumn("למ\"ר", format="%d ₪"),
                    "link": st.column_config.LinkColumn("לינק למודעה", display_text="פתח מודעה 🔗"),
                },
                use_container_width=True,
                hide_index=True
            )
            
            st.success(f"נמצאו {len(df)} נכסים איכותיים.")
        else:
            st.error("הבוט נחסם או לא מצא נכסים. נדרש שימוש ב-Residential Proxy כדי לעבוד ב-Scale.")
            
    except Exception as e:
        st.error(f"שגיאה קריטית: {e}")
    finally:
        driver.quit()
