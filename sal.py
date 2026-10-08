import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==========================================
# 1. Page Setup
# ==========================================
st.set_page_config(page_title="Salary Management System", layout="wide")
month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# ==========================================
# 2. Custom CSS
# ==========================================
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .stButton > button { 
        transition: all 0.2s ease-in-out !important; 
        cursor: pointer !important; 
    }
    .stButton > button:hover { 
        transform: scale(1.05) !important; 
        box-shadow: 0px 4px 15px rgba(255, 75, 75, 0.4) !important; 
    }
    [data-testid="stDataEditor"] [role="gridcell"] input[type="checkbox"] { 
        opacity: 1 !important; 
        visibility: visible !important; 
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. Password Protection
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Salary System Login</h2>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1,1,1])
    with col_m:
        pwd_input = st.text_input("Enter Password", type="password")
        if st.button("Login", use_container_width=True):
            if pwd_input == "1989": 
                st.session_state.logged_in = True
                st.rerun()
            else: 
                st.error("❌ Incorrect Password!")
    st.stop()

st.markdown("<h1 style='text-align: center;'>💎 Salary & Leave Management</h1>", unsafe_allow_html=True)
st.divider()

# ==========================================
# 4. Helper Functions
# ==========================================
def get_user_file(name):
    if not name: return None
    return f"{name.strip().replace(' ', '_')}_salary.csv"

month_dict = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

if 'calc_result' not in st.session_state:
    st.session_state['calc_result'] = None
if 'form_key' not in st.session_state:
    st.session_state['form_key'] = 0

# ==========================================
# 5. Sidebar Profile & Logic Setup
# ==========================================
with st.sidebar:
    st.header("👤 Profile")
    emp_sidebar_name = st.text_input("Employee Name", placeholder="Enter Name...", label_visibility="collapsed")
    st.divider()

    last_data = {"CTC": 0.0, "Std_Hrs": 0.0, "Present_Hrs": 0.0, "Late": 0, "Early": 0, "OT": 0, "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, "Advance": 0.0, "Difference": 0.0}
    
    user_file = get_user_file(emp_sidebar_name)
    is_new_employee = True
    last_pl_balance = 0.0
    last_saved_month = None
    df_hist_sorted = pd.DataFrame() 

    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file)
            if not df_hist.empty:
                is_new_employee = False
                
                df_hist['Month_Num'] = df_hist['Month'].astype(str).str.strip().map(month_dict)
                df_hist_sorted = df_hist.sort_values(by=['Year', 'Month_Num'])
                last_row_chronological = df_hist_sorted.iloc[-1]
                
                last_pl_balance = float(last_row_chronological.get("PL Balance", 0.0))
                last_saved_month = str(last_row_chronological.get("Month", "")).strip()

                # --- Auto-fill Logic ---
                key_mapping = {
                    "CTC": "CTC", "Std Hrs": "Std_Hrs", 
                    "Gratuity": "Gratuity", "PT": "PT"
                }
                for csv_k, data_k in key_mapping.items():
                    if csv_k in last_row_chronological: 
                        last_data[data_k] = last_row_chronological[csv_k]
        except Exception as e:
            pass

# ==========================================
# 6. Form Logic & Input
# ==========================================
kb = f"{st.session_state['form_key']}_{emp_sidebar_name.strip()}"

col1, col2 = st.columns(2)

now = datetime.now()
current_month_name = now.strftime("%b") 
current_year = now.year

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        emp_name = st.text_input("Full Name", value=emp_sidebar_name, disabled=True)
        
        m_col, y_col = st.columns(2)
        
        m_list = list(month_dict.keys())
        default_month = current_month_name 
        
        if emp_sidebar_name and not is_new_employee and last_saved_
