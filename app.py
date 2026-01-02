import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

# --- הגדרת עמוד ---
st.set_page_config(page_title="Auto-Scraper Pro", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    body { direction: rtl; text-align: right; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    div[data-testid="stMetric"] { background-color: #f0f2f6; border-radius: 10px; padding: 10px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- פונקציית הרובוט (הליבה) ---
def run_scraper(city_url, max_items=20):
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    status_text.info("🚀 מפעיל מנוע דפדפן (Headless Chrome)...")
    
    # הגדרות דפדפן (כדי להיראות כמו בן אדם ולא כמו בוט)
    options = Options()
    options.add_argument("--headless") # רץ ברקע בלי לפתוח חלון
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    data = []
    
    try:
        status_text.info(f"🌐 גולש לכתובת: {city_url}...")
        driver.get(city_url)
        
        # המתנה לטעינת האתר (חשוב מאוד ביד2!)
        time.sleep(5) 
        
        status_text.info("👀 סורק את העמוד ומחפש דירות...")
        
        # גלילה למטה כדי לטעון עוד נתונים (Infinite Scroll)
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        # ניסיון לאתר את קופסאות המודעות (Feed Items)
        # הערה: יד2 משנים את ה-Class ID כל הזמן. אנחנו ננסה לתפוס אלמנטים גנריים.
        # אסטרטגיה: חיפוש אלמנטים שמכילים מחיר
        
        # שיטה גנרית: תופסים את כל הטקסט ומפרקים אותו
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        # פירוק הטקסט הגולמי מהדפדפן (דומה למה שעשינו עם HTML, אבל הפעם הדפדפן הביא אותו לבד)
        raw_listings = body_text.split('\n')
        
        current_listing = {}
        counter = 0
        
        # לוגיקה פשוטה לזיהוי רצף נתונים מהמסך
        # זה לא מושלם כמו API, אבל זה עוקף חסימות כי זה קורא מהמסך
        for line in raw_listings:
            if "₪" in line and len(line) < 20: # זיהוי מחיר
                price_clean = ''.join(filter(str.isdigit, line))
                if price_clean and int(price_clean) > 500000:
                    current_listing['price'] = int(price_clean)
            
            elif "חדרים" in line: # זיהוי חדרים
                rooms_clean = line.replace("חדרים", "").replace("-", "").strip()
                try: current_listing['rooms'] = float(rooms_clean)
                except: pass
            
            elif 'מ"ר' in line or 'מ"ר' in line: # זיהוי מ"ר
                sqm_clean = ''.join(filter(str.isdigit, line))
                if sqm_clean: current_listing['sqm'] = int(sqm_clean)
            
            # אם אספנו מספיק מידע לרשומה, נשמור אותה
            if 'price' in current_listing and 'rooms' in current_listing:
                current_listing['city'] = "תוצאת סריקה" # אפשר לשפר זיהוי עיר
                data.append(current_listing)
                current_listing = {} # איפוס
                counter += 1
                progress_bar.progress(min(counter / max_items, 1.0))
        
        status_text.success(f"✅ הסריקה הסתיימה! נמצאו {len(data)} נכסים.")
        
    except Exception as e:
        status_text.error(f"שגיאה בסריקה: {str(e)}")
    finally:
        driver.quit() # סגירת הדפדפן
        
    return data

# --- ממשק משתמש ---
st.title("🤖 הבוט האוטונומי")
st.write("מערכת סריקה אקטיבית. הבוט ייכנס לאתר במקומך ויביא את הנתונים.")

# בחירת אזור לסריקה (הכתובות האלו הן דוגמאות לחיפושים ביד2)
URLS = {
    "נתניה - כל העיר": "https://www.yad2.co.il/realestate/forsale?city=7400",
    "תל אביב - 3-4 חדרים": "https://www.yad2.co.il/realestate/forsale?city=5000&rooms=3-4",
    "חיפה - עד 2 מיליון": "https://www.yad2.co.il/realestate/forsale?city=4000&price=-1-2000000"
}

target_search = st.selectbox("בחר אזור לסריקה:", list(URLS.keys()))

if st.button("🚀 הפעל את הרובוט", type="primary"):
    target_url = URLS[target_search]
    results = run_scraper(target_url)
    
    if results:
        df = pd.DataFrame(results)
        
        # חישובים בסיסיים
        if 'sqm' in df.columns and 'price' in df.columns:
            df['ppm'] = df.apply(lambda x: x['price'] / x['sqm'] if x.get('sqm') else 0, axis=1)
        
        # הצגת נתונים
        st.divider()
        col1, col2 = st.columns(2)
        col1.metric("נכסים שנסרקו", len(df))
        if 'price' in df.columns:
            col2.metric("מחיר ממוצע", f"{int(df['price'].mean()):,} ₪")
        
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("הבוט סיים לרוץ אך לא הצליח לחלץ נתונים. ייתכן שיד2 חסמו את הגישה או שינו את המבנה.")
        st.info("טיפ: אתרי נדל\"ן חוסמים שרתים בענן. הפתרון היחיד שעובד ב-100% הוא להריץ את זה מהמחשב האישי שלך.")
