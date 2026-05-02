import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. Page Setup
st.set_page_config(page_title="Salary Management System", layout="wide")

# --- Custom CSS for Zoom & Checkbox ---
st.markdown("""
<style>
    .stButton > button {
        transition: all 0.2s ease-in-out !important;
        cursor: pointer !important;
    }
    .stButton > button:hover {
        transform: scale(1.08) !important;
        box-shadow: 0px 4px 15px rgba(255, 75, 75, 0.4) !important;
    }
    [data-testid="stDataEditor"] [role="gridcell"] input[type="checkbox"] {
        opacity: 1 !important;
        visibility: visible !important;
    }
</style>
""", unsafe_allow_html=True)

# 2. Password Protection
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
            else:
                st.error("❌ Incorrect Password!")
    st.stop()

st.markdown("<h1 style='text-align: center;'>💎 Salary & Leave Management</h1>", unsafe_allow_html=True)
st.divider()

# 3. Helper Functions
def get_user_file(name):
    if not name: return None
    return f"{name.strip().replace(' ', '_')}_salary.csv"

month_dict = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

# 4. Sidebar Profile
with st.sidebar:
    st.header("👤 Profile")
    emp_sidebar_name = st.text_input("Employee Name", placeholder="Enter Name...", label_visibility="collapsed")
    st.divider()

    last_data = {"CTC": 0, "Std_Hrs": 0, "Present_Hrs": 0, "Late": 0, "Food": 0, "Gratuity": 0, "PT": 200, "PF": 0, "ESIC": 0, "Bonus": 0, "Advance": 0}
    
    user_file = get_user_file(emp_sidebar_name)
    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file)
            if not df_hist.empty:
                last_row = df_hist.iloc[-1]
                for key in last_data.keys():
                    csv_key = key.replace("_", " ") if key != "Std_Hrs" else "Std Hrs"
                    if csv_key in last_row: last_data[key] = last_row[csv_key]
        except: pass

# 5. Form Logic & PL Calculation
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        emp_name = st.text_input("Full Name", value=emp_sidebar_name, disabled=True)
        m_col, y_col = st.columns(2)
        with m_col: month = st.selectbox("Month", list(month_dict.keys()))
        with y_col: year = st.number_input("Year", min_value=2024, max_value=2030, value=2026)
        
        # PL Balance Logic
        past_used_pl = 0
        if user_file and os.path.exists(user_file):
            try:
                df_pl = pd.read_csv(user_file)
                df_pl['Month_Num'] = df_pl['Month'].str.strip().map(month_dict)
                # Only count PL used in the same year before the selected month
                df_past = df_pl[(df_pl['Year'] == year) & (df_pl['Month_Num'] < month_dict[month])]
                past_used_pl = pd.to_numeric(df_past['PL Used'], errors='coerce').sum()
            except: pass
        
        available_pl = max(0, month_dict[month] - int(past_used_pl))
        ctc_salary = st.number_input("Monthly CTC", value=int(last_data["CTC"]))
        work_hrs = st.number_input("Standard Work Hrs", value=int(last_data["Std_Hrs"]))

with col2:
    with st.container(border=True):
        st.subheader("🕒 Attendance")
        present_hrs = st.number_input("Present Hrs", value=int(last_data["Present_Hrs"]))
        late_mins = st.number_input("Late Minutes", value=int(last_data["Late"]))
        ot_mins = st.number_input("OT Minutes", value=0)
        used_pl = st.number_input("PL Used (Days)", min_value=0, max_value=available_pl, value=0)

        total_min = (present_hrs * 60) + (used_pl * 10 * 60) - max(0, late_mins - 120) + ot_mins
        calc_final_hrs = (total_min // 60) + ((total_min % 60) / 100)
        st.number_input("Final Present Hours", value=float(calc_final_hrs), format="%.2f", disabled=True)

with col3:
    with st.container(border=True):
        st.subheader("📉 Deductions")
        food = st.number_input("Food Exp", value=int(last_data["Food"]))
        gratuity = st.number_input("Gratuity", value=int(last_data["Gratuity"]))
        pt_tax = st.number_input("PT Tax", value=200)
        bonus = st.number_input("Bonus", value=int(last_data["Bonus"]))
        advance = st.number_input("Advance", value=int(last_data["Advance"]))

with st.sidebar:
    st.subheader("📊 PL Balance")
    st.title(f"{available_pl - used_pl} Days")

# 6. Save Data
if st.button("Calculate & Save Data", type="primary", use_container_width=True):
    if not emp_sidebar_name: st.error("Please enter name!")
    else:
        base_sal = ctc_salary - gratuity
        hr_rate = base_sal / work_hrs if work_hrs > 0 else 0
        net_sal = ((total_min // 60) * hr_rate) + ((total_min % 60) * (hr_rate/60)) - food - pt_tax - advance + bonus
        
        new_rec = pd.DataFrame([{
            "Date": datetime.now().strftime("%d-%m-%Y"), "Name": emp_name, "Month": month, "Year": year,
            "CTC": ctc_salary, "Std Hrs": work_hrs, "Present Hrs": present_hrs, "Late Mins": late_mins,
            "Final Present Hrs": calc_final_hrs, "PL Used": used_pl, "PL Balance": available_pl - used_pl,
            "Net Salary": round(net_sal, 2), "Food": food, "Gratuity": gratuity, "Advance": advance, "Bonus": bonus
        }])
        
        if os.path.exists(user_file):
            pd.concat([pd.read_csv(user_file), new_rec], ignore_index=True).to_csv(user_file, index=False)
        else: new_rec.to_csv(user_file, index=False)
        st.success("Saved!"); st.rerun()

# 7. Search Section (Fixed)
st.divider()
st.subheader("🔍 Search Records")
with st.container(border=True):
    s1, s2, s3, s4 = st.columns([4, 1.5, 1.5, 1.5])
    search_n = s1.text_input("Search Name", placeholder="Name...", label_visibility="collapsed")
    search_m = s2.selectbox("Month", list(month_dict.keys()), key="sm", label_visibility="collapsed")
    search_y = s3.number_input("Year", value=2026, key="sy", label_visibility="collapsed")
    if s4.button("🔍 Search", use_container_width=True):
        s_file = get_user_file(search_n)
        if os.path.exists(s_file):
            df_s = pd.read_csv(s_file)
            # મહિના અને નામ માંથી સ્પેસ કાઢી ને સર્ચ કરો
            res = df_s[(df_s['Month'].str.strip() == search_m) & (df_s['Year'] == search_y)]
            if not res.empty:
                res.index = range(1, len(res) + 1)
                st.dataframe(res, use_container_width=True)
            else: st.warning("No record found.")
        else: st.error("File not found.")

# 8. History
if emp_sidebar_name and os.path.exists(user_file):
    st.subheader(f"📂 History: {emp_sidebar_name}")
    h_df = pd.read_csv(user_file).fillna(0)
    h_df.index = range(1, len(h_df) + 1)
    edited = st.data_editor(h_df, use_container_width=True)
    if st.button("💾 Save Changes"):
        edited.to_csv(user_file, index=False)
        st.success("Updated!"); st.rerun()
