import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==========================================
# 1. PAGE SETUP & CSS
# ==========================================
st.set_page_config(page_title="Salary Management System", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    .stButton > button { transition: all 0.2s ease-in-out !important; cursor: pointer !important; }
    .stButton > button:hover { transform: scale(1.05) !important; box-shadow: 0px 4px 15px rgba(255, 75, 75, 0.4) !important; }
    [data-testid="stDataEditor"] [role="gridcell"] input[type="checkbox"] { opacity: 1 !important; visibility: visible !important; }
    label { font-size: 0.9rem !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. PASSWORD PROTECTION
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Salary System Login</h2>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1,1,1])
    with col_m:
        pwd_input = st.text_input("Enter Password", type="password")
        if st.button("Login", use_container_width=True):
            if pwd_input == "123": 
                st.session_state.logged_in = True
                st.rerun()
            else: st.error("❌ Incorrect Password!")
    st.stop()

st.markdown("<h1 style='text-align: center;'>💎 Salary & Leave Management</h1>", unsafe_allow_html=True)
st.divider()

# ==========================================
# 3. HELPER FUNCTIONS & STATE
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
# 4. SIDEBAR - PROFILE & DATA AUTO-LOAD
# ==========================================
with st.sidebar:
    st.header("👤 Employee Profile")
    emp_sidebar_name = st.text_input("Enter Name", placeholder="Type Name here...", label_visibility="collapsed")
    st.divider()
    
    # Defaults for Auto-fill
    last_data = {
        "CTC": 0.0, "Std_Hrs": 0.0, "Present_Hrs": 0.0, "Late": 0, 
        "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, 
        "Advance": 0.0, "PL_Balance": 0.0
    }
    
    user_file = get_user_file(emp_sidebar_name)
    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file)
            if not df_hist.empty:
                last_row = df_hist.iloc[-1]
                # Mapping CSV columns to our internal keys
                mapping = {
                    "CTC": "CTC", "Std Hrs": "Std_Hrs", "Present Hrs": "Present_Hrs", 
                    "Late Mins": "Late", "Food": "Food", "Gratuity": "Gratuity", 
                    "Advance": "Advance", "Bonus": "Bonus", "PL Balance": "PL_Balance"
                }
                for csv_col, dict_key in mapping.items():
                    if csv_col in last_row: last_data[dict_key] = last_row[csv_col]
        except Exception as e:
            pass

# ==========================================
# 5. MAIN FORM SECTION
# ==========================================
fk = st.session_state['form_key']
col1, col2 = st.columns(2)

now = datetime.now()
current_month_name = now.strftime("%b") 
current_year = now.year

with col1:
    with st.container(border=True):
        st.subheader("📊 Attendance & Basic Details")
        emp_name_display = st.text_input("Full Name", value=emp_sidebar_name, disabled=True)
        
        m_col, y_col = st.columns(2)
        with m_col:
            m_list = list(month_dict.keys())
            def_m_idx = m_list.index(current_month_name) if current_month_name in m_list else 0
            month = st.selectbox("Month", m_list, index=def_m_idx, key=f"month_{fk}")
        with y_col:
            year = st.number_input("Year", min_value=2024, max_value=2030, value=current_year, key=f"year_{fk}")
        
        c1a, c1b = st.columns(2)
        with c1a:
            ctc = st.number_input("CTC Salary", value=float(last_data["CTC"]), key=f"ctc_{fk}")
            present_hrs = st.number_input("Present Hrs", value=float(last_data["Present_Hrs"]), key=f"p_hrs_{fk}")
            used_pl = st.number_input("PL Used (Days)", value=0.0, step=0.5, key=f"pl_u_{fk}")
        with c1b:
            std_hrs = st.number_input("Std Work Hrs", value=float(last_data["Std_Hrs"]), key=f"s_hrs_{fk}")
            late_m = st.number_input("Late Minutes", value=int(last_data["Late"]), key=f"late_{fk}")

with col2:
    with st.container(border=True):
        st.subheader("📉 Deductions & Bonus")
        c2a, c2b = st.columns(2)
        with c2a:
            food = st.number_input("Food Deduction", value=float(last_data["Food"]), key=f"food_{fk}")
            pt_tax = st.number_input("Professional Tax", value=float(last_data["PT"]), key=f"pt_{fk}")
            bonus = st.number_input("Bonus / Extra", value=float(last_data["Bonus"]), key=f"bonus_{fk}")
        with c2b:
            gratuity = st.number_input("Gratuity", value=float(last_data["Gratuity"]), key=f"grat_{fk}")
            advance = st.number_input("Advance Deduction", value=float(last_data["Advance"]), key=f"adv_{fk}")

# --- PL Balance & Salary Logic ---
# Nava mahine 1 PL malse + Gaya mahina nu balance - Used
available_pl = float(last_data["PL_Balance"]) + 1.0
if month == "Jan": available_pl = 1.0 # Jan ma reset 1 thi
current_pl_balance = available_pl - used_pl

# Work Time Calculation
total_working_min = int((present_hrs * 60) - late_m)
if total_working_min < 0: total_working_min = 0
final_time_str = f"{total_working_min // 60}h {total_working_min % 60}m"

# ==========================================
# 6. CALCULATE & SAVE
# ==========================================
st.write("")
if st.button("🚀 Calculate & Save Monthly Data", type="primary", use_container_width=True):
    if not emp_sidebar_name:
        st.error("❌ Sidebar ma Employee Name nakhvu jaruri che!")
    else:
        # Core Calculation
        base_for_rate = ctc - gratuity
        hourly_rate = base_for_rate / std_hrs if std_hrs > 0 else 0
        
        # Net Salary Formula
        calc_net = ((total_working_min / 60) * hourly_rate) - food - pt_tax - advance + bonus
        
        # Save Result to Session
        st.session_state['calc_result'] = {
            "name": emp_sidebar_name, "month": month, "net": calc_net, "pl": current_pl_balance
        }
        
        # Prepare DataFrame Row
        new_row = pd.DataFrame([{
            "Date": datetime.now().strftime("%d-%m-%Y"),
            "Name": emp_sidebar_name,
            "Month": month,
            "Year": year,
            "CTC": ctc,
            "Std Hrs": std_hrs,
            "Present Hrs": present_hrs,
            "Late Mins": late_m,
            "Final Present Hrs": final_time_str,
            "PL Used": used_pl,
            "PL Balance": current_pl_balance,
            "Net Salary": round(calc_net, 2),
            "Food": food,
            "Gratuity": gratuity,
            "PT": pt_tax,
            "Advance": advance,
            "Bonus": bonus
        }])
        
        # Save to CSV
        if os.path.exists(user_file):
            existing_df = pd.read_csv(user_file)
            pd.concat([existing_df, new_row], ignore_index=True).to_csv(user_file, index=False)
        else:
            new_row.to_csv(user_file, index=False)
            
        st.session_state['form_key'] += 1
        st.rerun()

# Display Last Result
if st.session_state['calc_result']:
    res = st.session_state['calc_result']
    st.success(f"✅ Record Saved! {res['name']} |
