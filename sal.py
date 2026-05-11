import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==========================================
# 1. Page Setup
# ==========================================
st.set_page_config(page_title="Salary Management System", layout="wide")
month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

month_order['Month'] = pd.Categorical(df['Month'], categories=month_order, ordered=True)
month_order = month_order.sort_values('Month')
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
            if pwd_input == "123": 
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
# 5. Sidebar Profile
# ==========================================
with st.sidebar:
    st.header("👤 Profile")
    emp_sidebar_name = st.text_input("Employee Name", placeholder="Enter Name...", label_visibility="collapsed")
    st.divider()

    last_data = {"CTC": 0.0, "Std_Hrs": 0.0, "Present_Hrs": 0.0, "Late": 0, "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, "Advance": 0.0, "PL_Balance": 0.0}
    
    user_file = get_user_file(emp_sidebar_name)
    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file)
            if not df_hist.empty:
                last_row = df_hist.iloc[-1]
                key_mapping = {
                    "CTC": "CTC", "Std Hrs": "Std_Hrs", "Present Hrs": "Present_Hrs", 
                    "Late Mins": "Late", "Food": "Food", "Gratuity": "Gratuity", 
                    "Advance": "Advance", "Bonus": "Bonus", "PL Balance": "PL_Balance"
                }
                for csv_k, data_k in key_mapping.items():
                    if csv_k in last_row: last_data[data_k] = last_row[csv_k]
        except Exception as e:
            pass

# ==========================================
# 6. Form Logic & Input
# ==========================================
fk = st.session_state['form_key']
col1, col2 = st.columns(2)

now = datetime.now()
current_month_name = now.strftime("%b") 
current_year = now.year

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        emp_name = st.text_input("Full Name", value=emp_sidebar_name, disabled=True)
        
        m_col, y_col = st.columns(2)
        with m_col:
            m_list = list(month_dict.keys())
            def_m_idx = m_list.index(current_month_name) if current_month_name in m_list else 0
            month = st.selectbox("Month", m_list, index=def_m_idx, key=f"month_{fk}")
        with y_col:
            year = st.number_input("Year", min_value=2024, max_value=2030, value=current_year, key=f"year_{fk}")
            
        c1_1, c1_2 = st.columns(2)
        with c1_1:
            ctc_salary = st.number_input("CTC Salary", value=float(last_data["CTC"]), key=f"ctc_{fk}")
            present_hrs = st.number_input("Present Hrs", value=float(last_data["Present_Hrs"]), key=f"phrs_{fk}")
            used_pl = st.number_input("PL Used", value=0.0, step=0.5, key=f"plu_{fk}")
        with c1_2:
            work_hrs = st.number_input("Std Hrs", value=float(last_data["Std_Hrs"]), key=f"shrs_{fk}")
            late_mins = st.number_input("Late Mins", value=int(last_data["Late"]), key=f"late_{fk}")

with col2:
    with st.container(border=True):
        st.subheader("📉 Deductions & Additions")
        c2_1, c2_2 = st.columns(2)
        with c2_1:
            food = st.number_input("Food", value=float(last_data["Food"]), key=f"food_{fk}")
            pt_tax = st.number_input("PT Tax", value=200.0, key=f"pt_{fk}")
            bonus = st.number_input("Bonus", value=float(last_data["Bonus"]), key=f"bn_{fk}")
        with c2_2:
            gratuity = st.number_input("Gratuity", value=float(last_data["Gratuity"]), key=f"gr_{fk}")
            advance = st.number_input("Advance", value=float(last_data["Advance"]), key=f"ad_{fk}")

# --- PL & Time Calculation Logic ---
available_pl = float(last_data["PL_Balance"]) + 1.0
if month == "Jan": 
    available_pl = 1.0 
final_pl_balance = available_pl - used_pl

total_min = int((present_hrs * 60) - late_mins)
if total_min < 0: total_min = 0
calc_final_hrs = f"{total_min // 60}h {total_min % 60}m"

# ==========================================
# 7. Save Data
# ==========================================
st.write("")
if st.button("Calculate & Save Data", type="primary", use_container_width=True):
    if not emp_sidebar_name: 
        st.error("Please enter Employee Name in the sidebar!")
    else:
        base_sal = ctc_salary - gratuity
        hr_rate = base_sal / work_hrs if work_hrs > 0 else 0
        net_sal = ((total_min // 60) * hr_rate) + ((total_min % 60) * (hr_rate/60)) - food - pt_tax - advance + bonus
        
        st.session_state['calc_result'] = {
            "name": emp_name, "month": month, "net": net_sal, "pl": final_pl_balance
        }
        
        new_rec = pd.DataFrame([{
            "Date": datetime.now().strftime("%d-%m-%Y"), "Name": emp_name, "Month": month, "Year": year,
            "CTC": ctc_salary, "Std Hrs": work_hrs, "Present Hrs": present_hrs, "Late Mins": late_mins,
            "Final Present Hrs": calc_final_hrs, "PL Used": used_pl, "PL Balance": final_pl_balance,
            "Net Salary": round(net_sal, 2), "Food": food, "Gratuity": gratuity, "PT": pt_tax, "Advance": advance, "Bonus": bonus
        }])
        
        if os.path.exists(user_file):
            pd.concat([pd.read_csv(user_file), new_rec], ignore_index=True).to_csv(user_file, index=False)
        else: 
            new_rec.to_csv(user_file, index=False)
            
        st.session_state['form_key'] += 1
        st.rerun()

if st.session_state['calc_result']:
    res = st.session_state['calc_result']
    st.success(f"✅ Data Saved! Name: {res['name']} | Net Salary: ₹{res['net']:,.2f} | PL Balance: {res['pl']}")

# ==========================================
# 8. Search Section
# ==========================================
st.divider()
st.subheader("🔍 Search Records")
with st.container(border=True):
    s1, s2, s3, s4 = st.columns([4, 1.5, 1.5, 1.5])
    search_n = s1.text_input("Search Name", placeholder="Name...", label_visibility="collapsed", key="sn")
    search_m = s2.selectbox("Month", list(month_dict.keys()), key="sm", label_visibility="collapsed")
    search_y = s3.number_input("Year", value=current_year, key="sy", label_visibility="collapsed")
    
    if s4.button("🔍 Search", use_container_width=True):
        s_file = get_user_file(search_n)
        if os.path.exists(s_file):
            df_s = pd.read_csv(s_file)
            res = df_s[(df_s['Month'].str.strip() == search_m) & (df_s['Year'] == search_y)]
            if not res.empty:
                res.index = range(1, len(res) + 1)
                st.dataframe(res, use_container_width=True)
            else: 
                st.warning("No record found for this month/year.")
        else: 
            st.error("File not found.")

# ==========================================
# 9. History - નામ પ્રમાણે અને ડિલીટ ઓપ્શન સાથે
# ==========================================
if emp_sidebar_name:
    user_file = get_user_file(emp_sidebar_name)
    if os.path.exists(user_file):
        st.subheader(f"📂 History: {emp_sidebar_name}")
        h_df = pd.read_csv(user_file).fillna(0)

        # num_rows="dynamic" થી રો ડિલીટ કરી શકાશે
        edited_df = st.data_editor(
            h_df, 
            use_container_width=True, 
            num_rows="dynamic",
            key=f"editor_{emp_sidebar_name.lower().replace(' ', '_')}" 
        )
        
        if st.button("💾 Save Changes (Update/Delete)"):
            edited_df.to_csv(user_file, index=False)
            st.success("Record updated successfully!")
            st.rerun()
    else:
        st.info("આ કર્મચારી માટે હજુ કોઈ સેલરી ડેટા સેવ થયો નથી.")
