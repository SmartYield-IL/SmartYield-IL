import streamlit as st

def apply_styles():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;700;800&display=swap');
        
        html, body, [class*="css"] { 
            font-family: 'Assistant', sans-serif; 
            direction: rtl; 
            text-align: right; 
        }
        
        .stApp { background-color: #fcfcfc; }

        /* כותרת עליונה משופרת */
        .header-container {
            background: #0f172a;
            padding: 2.5rem;
            border-radius: 0 0 20px 20px;
            color: white;
            text-align: center;
            margin-bottom: 1rem;
            border-bottom: 4px solid #b8860b;
        }

        /* עיצוב הלשוניות (Tabs) */
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
            justify-content: center;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            background-color: #f1f5f9;
            border-radius: 10px 10px 0 0;
            padding: 10px 30px;
            font-weight: 700;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1e3a8a !important;
            color: white !important;
        }

        /* אזור הניתוח המרכזי */
        .analysis-box {
            background: white;
            padding: 30px;
            border-radius: 20px;
            border: 2px solid #e2e8f0;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            margin-top: 20px;
        }
        </style>
        
        <div class="header-container">
            <h1 style='color: white; font-weight: 800; font-size: 2.8rem; margin:0;'>SmartYield <span style='color:#fbbf24'>PRO</span></h1>
            <p style='font-size: 1.1rem; opacity: 0.8;'>טרמינל לניתוח ארביטראז' נדל"ן ארצי</p>
        </div>
    """, unsafe_allow_html=True)
