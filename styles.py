import streamlit as st

def apply_styles():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;700;800&display=swap');
        
        /* הגדרות גופן ויישור לימין */
        html, body, [class*="css"] { 
            font-family: 'Assistant', sans-serif; 
            direction: rtl; 
            text-align: right; 
        }
        
        .stApp { background-color: #ffffff; }

        /* כותרת עליונה יוקרתית (Navy & Gold) */
        .header-container {
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
            padding: 3.5rem;
            border-radius: 0 0 40px 40px;
            color: white;
            text-align: center;
            margin-bottom: 2.5rem;
            border-bottom: 6px solid #b8860b;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }

        /* כרטיסי המטריקות */
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 20px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            border-right: 6px solid #b8860b;
        }

        /* עיצוב כפתורי ה-Sidebar */
        .stButton>button {
            width: 100%;
            border-radius: 10px;
            background-color: #1e3a8a;
            color: white;
            font-weight: 700;
            border: none;
            transition: all 0.3s ease;
        }
        
        .stButton>button:hover {
            background-color: #b8860b;
            transform: translateY(-2px);
        }
        </style>
        
        <div class="header-container">
            <h1 style='color: white; font-weight: 800; font-size: 3.2rem; margin:0;'>SmartYield <span style='color:#fbbf24'>PRO</span></h1>
            <p style='font-size: 1.3rem; opacity: 0.9; margin-top:10px;'>מערכת קבלת החלטות בנדל"ן | המהדורה המקצועית 2026</p>
        </div>
    """, unsafe_allow_html=True)
