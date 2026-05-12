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
# 5. Sidebar Profile & Logic Setup
# ==========================================
with st.sidebar:
    st.header("👤 Profile")
    emp_sidebar_name = st.text_input("Employee Name", placeholder="Enter Name...", label_visibility="collapsed")
    st.divider()

    last_data = {"CTC": 0.0, "Std_Hrs": 0.0, "Present_Hrs": 0.0, "Late": 0, "Early": 0, "OT": 0, "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, "Advance": 0.0}
    
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
                # Only fetch fixed details from the old data; variable fields will default to 0 automatically
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
        
        if emp_sidebar_name and not is_new_employee and last_saved_month in m_list:
            last_idx = m_list.index(last_saved_month)
            if last_idx < 11: 
                default_month = m_list[last_idx + 1]
            else:
                default_month = 'Jan' 

        def_m_idx = m_list.index(default_month) if default_month in m_list else 0

        with m_col:
            month = st.selectbox("Month", m_list, index=def_m_idx, key=f"month_{kb}")
        with y_col:
            def_year = current_year
            if not is_new_employee and last_saved_month == 'Dec':
                def_year = int(last_row_chronological.get("Year", current_year)) + 1
                
            year = st.number_input("Year", min_value=2024, max_value=2030, value=def_year, key=f"year_{kb}")
            
        c1_1, c1_2 = st.columns(2)
        with c1_1:
            ctc_salary = st.number_input("CTC Salary", value=float(last_data["CTC"]), key=f"ctc_{kb}")
            
            saved_p_hrs_val = float(last_data["Present_Hrs"])
            def_p_hrs = int(saved_p_hrs_val)
            def_p_mins = int(round((saved_p_hrs_val - def_p_hrs) * 100))
            
            p_h_col, p_m_col = st.columns(2)
            with p_h_col:
                present_hrs_input = st.number_input("Present Hrs", value=def_p_hrs, step=1, key=f"phrs_{kb}")
            with p_m_col:
                present_mins_input = st.number_input("Mins", value=def_p_mins, min_value=0, max_value=59, step=1, key=f"pmins_{kb}")
            
            available_pl = 0.0
            
            if month == "Jan":
                available_pl = 1.0
                st.text_input("Available PL (Jan Reset = 1)", value="1.0", disabled=True)
                
            elif emp_sidebar_name and is_new_employee:
                available_pl = st.number_input("Opening PL Balance", value=0.0, step=0.5, key=f"opl_{kb}")
                
            elif emp_sidebar_name and not is_new_employee:
                prev_month_str = month_order[month_order.index(month) - 1]
                
                if not df_hist_sorted.empty:
                    prev_rec = df_hist_sorted[(df_hist_sorted['Year'] == year) & (df_hist_sorted['Month'].str.strip() == prev_month_str)]
                    if not prev_rec.empty:
                        prev_pl_bal = float(prev_rec.iloc[-1].get("PL Balance", 0.0))
                        available_pl = prev_pl_bal + 1.0
                    else:
                        available_pl = last_pl_balance + 1.0
                else:
                    available_pl = last_pl_balance + 1.0
                    
                st.text_input(f"Available PL (From {prev_month_str} + 1)", value=str(available_pl), disabled=True)

            used_pl = st.number_input("PL Used", value=0.0, step=0.5, key=f"plu_{kb}")

        with c1_2:
            work_hrs = st.number_input("Std Hrs", value=float(last_data["Std_Hrs"]), key=f"shrs_{kb}")
            
            # --- LATE ---
            saved_late_val = int(last_data["Late"])
            def_late_hrs = saved_late_val // 60
            def_late_mins = saved_late_val % 60
            
            l_h_col, l_m_col = st.columns(2)
            with l_h_col: late_hrs_input = st.number_input("Late Hrs", value=def_late_hrs, step=1, key=f"lhrs_{kb}")
            with l_m_col: late_mins_input = st.number_input("Late Mins", value=def_late_mins, min_value=0, max_value=59, step=1, key=f"lmins_{kb}")

            # --- EARLY GOING ---
            saved_early_val = int(last_data["Early"])
            def_early_hrs = saved_early_val // 60
            def_early_mins = saved_early_val % 60
            
            e_h_col, e_m_col = st.columns(2)
            with e_h_col: early_hrs_input = st.number_input("Early Hrs", value=def_early_hrs, step=1, key=f"ehrs_{kb}")
            with e_m_col: early_mins_input = st.number_input("Early Mins", value=def_early_mins, min_value=0, max_value=59, step=1, key=f"emins_{kb}")

            # --- OT (Overtime) ---
            saved_ot_val = int(last_data["OT"])
            def_ot_hrs = saved_ot_val // 60
            def_ot_mins = saved_ot_val % 60
            
            o_h_col, o_m_col = st.columns(2)
            with o_h_col: ot_hrs_input = st.number_input("OT Hrs", value=def_ot_hrs, step=1, key=f"othrs_{kb}")
            with o_m_col: ot_mins_input = st.number_input("OT Mins", value=def_ot_mins, min_value=0, max_value=59, step=1, key=f"otmins_{kb}")

with col2:
    with st.container(border=True):
        st.subheader("📉 Deductions & Additions")
        c2_1, c2_2 = st.columns(2)
        with c2_1:
            food = st.number_input("Food", value=float(last_data["Food"]), key=f"food_{kb}")
            pt_tax = st.number_input("PT Tax", value=float(last_data["PT"]), key=f"pt_{kb}")
            bonus = st.number_input("Bonus", value=float(last_data["Bonus"]), key=f"bn_{kb}")
        with c2_2:
            gratuity = st.number_input("Gratuity", value=float(last_data["Gratuity"]), key=f"gr_{kb}")
            advance = st.number_input("Advance", value=float(last_data["Advance"]), key=f"ad_{kb}")

# --- Time Calculation Logic ---
final_pl_balance = available_pl - used_pl

pl_hours_to_add = used_pl * 10 

total_late_mins = (late_hrs_input * 60) + late_mins_input
total_early_mins = (early_hrs_input * 60) + early_mins_input
total_ot_mins = (ot_hrs_input * 60) + ot_mins_input

# Calculation: (Present Hrs + PL Hrs + OT) - (Late Mins + Early Mins)
total_min = int(((present_hrs_input + pl_hours_to_add) * 60) + present_mins_input + total_ot_mins - total_late_mins - total_early_mins)
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
        
        present_hrs_combined = present_hrs_input + (present_mins_input / 100.0)
        
        new_rec = pd.DataFrame([{
            "Date": datetime.now().strftime("%d-%m-%Y"), "Name": emp_name, "Month": month, "Year": year,
            "CTC": ctc_salary, "Std Hrs": work_hrs, "Present Hrs": present_hrs_combined, 
            "Late Mins": total_late_mins, "Early Mins": total_early_mins, "OT Mins": total_ot_mins,
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
    
    # Only show the success message if it belongs to the currently selected employee in the sidebar
    if res['name'] == emp_sidebar_name:
        st.success(f"✅ Data Saved! Name: {res['name']} | Net Salary: ₹{res['net']:,.2f} | PL Balance: {res['pl']}")
    else:
        # Clear the old message when a new name is typed
        st.session_state['calc_result'] = None

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
# 9. History 
# ==========================================
if emp_sidebar_name:
    user_file = get_user_file(emp_sidebar_name)
    if os.path.exists(user_file):
        st.subheader(f"📂 History: {emp_sidebar_name}")
        # Fill missing Early/OT columns with 0 for older files
        h_df = pd.read_csv(user_file).fillna(0)

        if 'Month' in h_df.columns:
            h_df['Month'] = pd.Categorical(h_df['Month'], categories=month_order, ordered=True)
            if 'Year' in h_df.columns:
                h_df = h_df.sort_values(['Year', 'Month']).reset_index(drop=True)
            else:
                h_df = h_df.sort_values('Month').reset_index(drop=True)

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
        st.info("No salary data saved for this employee yet. (Calculate & Save Data to add new employee)")
