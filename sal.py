import streamlit as st
import pandas as pd
import os
import io
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
# 3. Password Protection & State
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if 'calc_result' not in st.session_state:
    st.session_state['calc_result'] = None
if 'form_key' not in st.session_state:
    st.session_state['form_key'] = 0

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Salary System Login</h2>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1,1,1])
    with col_m:
        with st.form("login_form"):
            pwd_input = st.text_input("Enter Password", type="password")
            submit_btn = st.form_submit_button("Login", use_container_width=True)
            if submit_btn:
                if pwd_input == "1989": 
                    st.session_state.logged_in = True
                    st.rerun()
                else: 
                    st.error("❌ Incorrect Password!")
    st.stop()

st.markdown("<h1 style='text-align: center;'>💎 Salary & Leave Management</h1>", unsafe_allow_html=True)
st.divider()

# ==========================================
# 4. Helper Functions & Configs
# ==========================================
def get_user_file(name):
    if not name: return None
    return f"{name.strip().replace(' ', '_')}_salary.csv"

def clean_legacy_columns(df):
    if 'Std Hrs' in df.columns:
        if 'Working Hrs' in df.columns:
            df['Working Hrs'] = df['Working Hrs'].fillna(df['Std Hrs'])
            df['Working Hrs'] = df.apply(lambda r: r['Std Hrs'] if pd.isna(r.get('Working Hrs')) or r.get('Working Hrs') == 0 else r['Working Hrs'], axis=1)
            df = df.drop(columns=['Std Hrs'])
        else:
            df = df.rename(columns={'Std Hrs': 'Working Hrs'})
    df = df.loc[:, ~df.columns.duplicated()]
    return df

month_dict = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

money_cols = ["CTC", "OT Salary", "Net Salary", "Food", "Gratuity", "PT", "TDS", "ESIC", "Advance", "Bonus", "Difference"]
table_format_config = {col: st.column_config.NumberColumn(format="₹ %,.2f") for col in money_cols}

# ==========================================
# 5. Sidebar Profile & Logic Setup
# ==========================================
with st.sidebar:
    st.header("👤 Profile")
    emp_sidebar_name = st.text_input("Employee Name", placeholder="Enter Name...", label_visibility="collapsed")
    st.divider()

    last_data = {"CTC": 0.0, "Working_Hrs": 0.0, "Present_Hrs": 0.0, "Late": 0, "Early": 0, "OT": 0, "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, "Advance": 0.0, "Difference": 0.0, "TDS": 0.0, "ESIC": 0.0}
    
    user_file = get_user_file(emp_sidebar_name)
    is_new_employee = True
    last_pl_balance = 0.0
    last_saved_month = None
    df_hist_sorted = pd.DataFrame() 

    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file)
            df_hist = clean_legacy_columns(df_hist)
                
            if not df_hist.empty:
                is_new_employee = False
                
                df_hist['Month_Num'] = df_hist['Month'].astype(str).str.strip().map(month_dict)
                df_hist_sorted = df_hist.sort_values(by=['Year', 'Month_Num'])
                last_row_chronological = df_hist_sorted.iloc[-1]
                
                last_pl_balance = float(last_row_chronological.get("PL Balance", 0.0))
                last_saved_month = str(last_row_chronological.get("Month", "")).strip()

                key_mapping = {
                    "CTC": "CTC", "Working Hrs": "Working_Hrs", 
                    "Gratuity": "Gratuity", "PT": "PT", "TDS": "TDS", "ESIC": "ESIC"
                }
                for csv_k, data_k in key_mapping.items():
                    if csv_k in last_row_chronological: 
                        val = last_row_chronological[csv_k]
                        if pd.notna(val) and str(val).strip() != "":
                            try:
                                last_data[data_k] = float(val)
                            except:
                                pass
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
        def_year = current_year
        
        if emp_sidebar_name and not is_new_employee and last_saved_month in m_list:
            last_idx = m_list.index(last_saved_month)
            if last_idx < 11: 
                default_month = m_list[last_idx + 1]
                def_year = int(last_row_chronological.get("Year", current_year))
            else:
                default_month = 'Jan' 
                def_year = int(last_row_chronological.get("Year", current_year)) + 1

        def_m_idx = m_list.index(default_month) if default_month in m_list else 0

        with m_col:
            month = st.selectbox("Month", m_list, index=def_m_idx, disabled=(not is_new_employee), key=f"month_{kb}")
        with y_col:
            year = st.number_input("Year", min_value=2024, max_value=2030, value=def_year, disabled=(not is_new_employee), key=f"year_{kb}")
            
        c1_1, c1_2 = st.columns(2)
        with c1_1:
            ctc_salary = st.number_input("CTC Salary (₹)", value=float(last_data["CTC"]), key=f"ctc_{kb}")
            
            saved_p_hrs_val = float(last_data["Present_Hrs"])
            def_p_hrs = int(saved_p_hrs_val)
            def_p_mins = int(round((saved_p_hrs_val - def_p_hrs) * 100))
            
            p_h_col, p_m_col = st.columns(2)
            with p_h_col:
                present_hrs_input = st.number_input("Present Hrs", value=def_p_hrs, step=1, key=f"phrs_{kb}")
            with p_m_col:
                present_mins_input = st.number_input("Mins", value=def_p_mins, min_value=0, max_value=59, step=1, key=f"pmins_{kb}")
            
            available_pl = 0.0
            
            if emp_sidebar_name and is_new_employee:
                available_pl = st.number_input("Opening PL Balance (Starting)", value=0.0, step=0.5, key=f"opl_{kb}")
            elif emp_sidebar_name and not is_new_employee:
                available_pl = last_pl_balance + 1.0
                st.text_input(f"Available PL (From {last_saved_month} + 1)", value=str(available_pl), disabled=True)

            used_pl = st.number_input("PL Used", value=0.0, step=0.5, key=f"plu_{kb}")

        with c1_2:
            work_hrs = st.number_input("Working Hrs", value=float(last_data["Working_Hrs"]), key=f"shrs_{kb}")
            
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
            food = st.number_input("Food (₹)", value=float(last_data["Food"]), key=f"food_{kb}")
            pt_tax = st.number_input("PT Tax (₹)", value=float(last_data["PT"]), key=f"pt_{kb}")
            tds = st.number_input("TDS (₹)", value=float(last_data["TDS"]), key=f"tds_{kb}")
            bonus = st.number_input("Bonus (₹)", value=float(last_data["Bonus"]), key=f"bn_{kb}")
        with c2_2:
            gratuity = st.number_input("Gratuity (₹)", value=float(last_data["Gratuity"]), key=f"gr_{kb}")
            advance = st.number_input("Advance (₹)", value=float(last_data["Advance"]), key=f"ad_{kb}")
            esic = st.number_input("ESIC (₹)", value=float(last_data["ESIC"]), key=f"esic_{kb}")
            difference = st.number_input("Difference (₹)", value=0.0, key=f"diff_{kb}")

# ==========================================
# TIME CALCULATION LOGIC
# ==========================================
final_pl_balance = available_pl - used_pl
pl_hours_to_add = used_pl * 10 

total_late_mins = (late_hrs_input * 60) + late_mins_input
total_early_mins = (early_hrs_input * 60) + early_mins_input
total_late_early_mins = total_late_mins + total_early_mins

total_ot_mins = (ot_hrs_input * 60) + ot_mins_input
working_mins = int(work_hrs * 60)
base_present_mins = int((present_hrs_input + pl_hours_to_add) * 60) + present_mins_input

if base_present_mins == 0:
    total_min = total_ot_mins
else:
    adjusted_mins = base_present_mins - total_late_early_mins + 120
    if adjusted_mins > working_mins:
        adjusted_mins = working_mins
    total_min = adjusted_mins + total_ot_mins

if total_min < 0: total_min = 0
calc_final_hrs = f"{total_min // 60}h {total_min % 60}m"

# ==========================================
# 7. Save Data & Excel Generation Helper
# ==========================================
def generate_excel_slip(slip_data, emp_name, month_str, year_val):
    sd = slip_data
    
    # EMOJIS ADDED TO LABELS
    slip_df = pd.DataFrame({
        "Label": [
            "💰 CTC Salary", "🎁 Gratuity", "🎉 Bonus", "💵 Actual Salary", 
            "🏢 Working Hrs", "✅ Present Hrs", "🏖️ PL Used", 
            "⏳ OT Hrs", "⏰ Late Hrs", "🚶 Out Hrs", "⏱️ Pay Hrs", 
            "🏛️ PT", "🛡️ PF", "🏥 ESI", "✂️ TDS", "🏦 Loan", "🍽️ Food", 
            "⚖️ PL Balance", "💸 Pay Salary", "💳 Bank Salary", "🧮 Diff"
        ],
        "Value": [
            sd['ctc'], sd['gratuity'], sd['bonus'], sd['actual_salary'], 
            sd['work_hrs_str'], sd['present_hrs'], sd['pl_used'], 
            sd['ot_hrs'], sd['late_hrs'], sd['out_hrs'], sd['pay_hrs'], 
            sd['pt'], "-", sd['esic'] if sd['esic'] else "-", sd['tds'] if sd['tds'] else "-", 
            sd['advance'], sd['food'], sd['pl_balance'], 
            sd['pay_salary_val'], sd['bank_salary_val'], sd['difference']
        ]
    })
    
    # EMOJIS ADDED TO HEADER
    header_row = pd.DataFrame({"Label": [f"📅 {month_str}'{year_val}"], "Value": [f"👤 {emp_name}"]})
    slip_df = pd.concat([header_row, slip_df], ignore_index=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        slip_df.to_excel(writer, index=False, header=False, sheet_name='Salary_Slip')
        workbook = writer.book
        worksheet = writer.sheets['Salary_Slip']
        
        base_header = {'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'align': 'center', 'valign': 'vcenter'}
        base_label = {'bold': True, 'bg_color': '#D9E1F2', 'align': 'center', 'valign': 'vcenter'}
        base_val_text = {'align': 'center', 'valign': 'vcenter'}
        base_val_curr = {'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0.00'}
        base_val_yellow = {'bg_color': '#FFFF00', 'align': 'center', 'valign': 'vcenter'}
        base_val_green = {'bg_color': '#C6E0B4', 'align': 'center', 'valign': 'v
