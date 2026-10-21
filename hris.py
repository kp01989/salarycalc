import streamlit as st
import pandas as pd
import requests
import os
import io
from datetime import datetime
import time as tm

# ==========================================
# 1. Page Setup
# ==========================================
st.set_page_config(page_title="Salary Management System", layout="wide")
month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
month_dict = {m: i+1 for i, m in enumerate(month_order)}

# TARI ATTENDANCE TRACKER NI FIREBASE LINK
FIREBASE_URL = "https://attendence-ec921-default-rtdb.firebaseio.com"

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
    
    /* VERTICAL LINE CSS */
    div[data-testid="column"]:has(#left-column-marker) {
        border-right: 2px solid rgba(128, 128, 128, 0.4);
        padding-right: 25px;
    }
    div[data-testid="column"]:has(#left-column-marker) + div[data-testid="column"] {
        padding-left: 25px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. State Management
# ==========================================
if 'calc_result' not in st.session_state:
    st.session_state['calc_result'] = None
if 'form_key' not in st.session_state:
    st.session_state['form_key'] = 0
if 'flash_msg' not in st.session_state:
    st.session_state['flash_msg'] = None

st.markdown("<h1 style='text-align: center;'>💎 Salary & Leave Management</h1>", unsafe_allow_html=True)
st.divider()

if st.session_state['flash_msg']:
    st.success(st.session_state['flash_msg'])
    st.session_state['flash_msg'] = None

# ==========================================
# 4. Helper Functions & Configs
# ==========================================
def get_user_file(name):
    if not name: return None
    return f"{name.strip().replace(' ', '_')}_salary.csv"

def format_mins_to_hrs(val):
    try:
        if pd.isna(val): return "0:00"
        v = int(float(val))
        return f"{v//60}:{v%60:02d}"
    except:
        return str(val)

def clean_legacy_columns(df):
    if 'Std Hrs' in df.columns:
        if 'Working Hrs' in df.columns:
            df['Working Hrs'] = df['Working Hrs'].fillna(df['Std Hrs'])
            df['Working Hrs'] = df.apply(lambda r: r['Std Hrs'] if pd.isna(r.get('Working Hrs')) or r.get('Working Hrs') == 0 else r['Working Hrs'], axis=1)
            df = df.drop(columns=['Std Hrs'])
        else:
            df = df.rename(columns={'Std Hrs': 'Working Hrs'})
            
    rename_map = {'Late Mins': 'Late Hrs', 'Early Mins': 'Out Hrs', 'OT Mins': 'OT Hrs'}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    for col in ['Late Hrs', 'Out Hrs', 'OT Hrs']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: format_mins_to_hrs(x) if str(x).replace('.0','').isdigit() else str(x))
            
    if 'Final Present Hrs' in df.columns:
        df['Final Present Hrs'] = df['Final Present Hrs'].astype(str).str.replace('h ', ':').str.replace('m', '')
        
    if 'Opening PL' not in df.columns:
        df['Opening PL'] = 0.0
    if 'In Hand Salary' not in df.columns:
        df['In Hand Salary'] = 0.0
    if 'Total Pay Hrs' not in df.columns:
        df['Total Pay Hrs'] = ""
        
    df = df.loc[:, ~df.columns.duplicated()]
    return df

def parse_firebase_time(time_str):
    if pd.isna(time_str) or str(time_str).strip() == "":
        return 0, 0
    try:
        parts = str(time_str).split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h, m
    except:
        return 0, 0

def fetch_attendance_data(emp_name, month_name, year):
    sheet_name = f"{month_name}'{year}"
    url = f"{FIREBASE_URL}/{sheet_name}.json"
    
    total_reg_mins, total_ot_mins, total_late_mins, total_out_mins_att = 0, 0, 0, 0
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data:
                if isinstance(data, dict):
                    df = pd.DataFrame(list(data.values()))
                else:
                    df = pd.DataFrame([row for row in data if row is not None])
                
                if "Employee Name" in df.columns:
                    df = df[df["Employee Name"].str.lower() == emp_name.strip().lower()]
                    for _, row in df.iterrows():
                        h, m = parse_firebase_time(row.get("Total Hours", "00:00"))
                        total_reg_mins += (h * 60) + m
                        
                        h, m = parse_firebase_time(row.get("OT Hours", "00:00"))
                        total_ot_mins += (h * 60) + m
                        
                        h, m = parse_firebase_time(row.get("Late Hours", "00:00"))
                        total_late_mins += (h * 60) + m
                        
                        h, m = parse_firebase_time(row.get("Out Hours", "00:00"))
                        total_out_mins_att += (h * 60) + m
    except Exception as e:
        pass
        
    return {
        "reg_h": total_reg_mins // 60, "reg_m": total_reg_mins % 60,
        "ot_h": total_ot_mins // 60, "ot_m": total_ot_mins % 60,
        "late_h": total_late_mins // 60, "late_m": total_late_mins % 60,
        "out_h": total_out_mins_att // 60, "out_m": total_out_mins_att % 60
    }

def recalculate_future_pl(df, start_index):
    for i in range(start_index + 1, len(df)):
        prev_balance = int(float(df.at[df.index[i-1], 'PL Balance']))
        used_pl_current = int(float(df.at[df.index[i], 'PL Used']))
        
        new_opening = prev_balance + 1
        new_balance = new_opening - used_pl_current
        
        df.at[df.index[i], 'Opening PL'] = new_opening
        df.at[df.index[i], 'PL Balance'] = new_balance
    return df

def generate_excel_slip(slip_data, emp_name, month_str, year_val):
    sd = slip_data
    slip_df = pd.DataFrame({
        "Label": [
            "CTC Salary", "Gratuity", "Bonus", "Actual Salary", 
            "Working Hrs", "Pay Hrs", "PL Used", 
            "OT Hrs", "Late Hrs", "Out Hrs", "Total Pay Hrs", 
            "PT", "PF", "ESI", "TDS", "Loan", "Food", 
            "PL Balance", "Pay Salary", "OT Salary", "In Hand Salary", "Bank Salary", "Diff"
        ],
        "Value": [
            sd['ctc'], sd['gratuity'], sd['bonus'], sd['actual_salary'], 
            sd['work_hrs_str'], sd['present_hrs'], sd['pl_used'], 
            sd['ot_hrs'], sd['late_hrs'], sd['out_hrs'], sd['pay_hrs'], 
            sd['pt'], "-", sd['esic'] if sd['esic'] else "-", sd['tds'] if sd['tds'] else "-", 
            sd['advance'], sd['food'], sd['pl_balance'], 
            sd['pay_salary_val'], sd['ot_sal'], sd['in_hand_salary'], sd['bank_salary_val'], sd['difference']
        ]
    })
    
    header_row = pd.DataFrame({"Label": [f"{month_str}'{year_val}"], "Value": [f"{emp_name}"]})
    slip_df = pd.concat([header_row, slip_df], ignore_index=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        slip_df.to_excel(writer, index=False, header=False, sheet_name='Salary_Slip')
        workbook = writer.book
        worksheet = writer.sheets['Salary_Slip']
        
        base_header_left = {'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'align': 'left', 'valign': 'vcenter', 'indent': 1}
        base_header_center = {'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'align': 'center', 'valign': 'vcenter'}
        base_label_left = {'bold': True, 'bg_color': '#D9E1F2', 'align': 'left', 'valign': 'vcenter', 'indent': 1}
        base_val_text = {'align': 'center', 'valign': 'vcenter'}
        
        base_val_curr = {'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0'}
        base_val_curr_tds = {'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0.00'} 
        
        base_val_yellow = {'bg_color': '#FFFF00', 'align': 'center', 'valign': 'vcenter'}
        base_val_green = {'bg_color': '#C6E0B4', 'align': 'center', 'valign': 'vcenter'}
        
        base_pay_label_left = {'bold': True, 'bg_color': '#C6E0B4', 'align': 'left', 'valign': 'vcenter', 'indent': 1}
        base_pay_val_center = {'bold': True, 'bg_color': '#C6E0B4', 'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0'}
        
        base_ot_label_left = {'bold': True, 'bg_color': '#F4B084', 'align': 'left', 'valign': 'vcenter', 'indent': 1}
        base_ot_val_center = {'bold': True, 'bg_color': '#F4B084', 'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0'}
        
        base_diff_pos_red = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#FF0000', 'num_format': '₹ #,##0'}
        base_diff_neg_green = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#228B22', 'num_format': '₹ #,##0'}
        base_diff_zero = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#000000', 'num_format': '₹ #,##0'}

        worksheet.set_column('A:A', 22)
        worksheet.set_column('B:B', 25)
        
        for i in range(len(slip_df)):
            worksheet.set_row(i, 18)
        
        currency_labels = ["CTC Salary", "Bonus", "Gratuity", "Actual Salary", "PT", "PF", "ESI", "Loan", "Food", "Bank Salary", "Diff"]
        total_rows = len(slip_df)
        
        for row_num, (lbl, val) in enumerate(zip(slip_df['Label'], slip_df['Value'])):
            if row_num == 0: dict_col0 = base_header_left.copy()
            elif lbl in ["Pay Salary", "In Hand Salary"]: dict_col0 = base_pay_label_left.copy()
            elif lbl == "OT Salary": dict_col0 = base_ot_label_left.copy()
            else: dict_col0 = base_label_left.copy()

            dict_col0['border'] = 1
            if row_num == 0: dict_col0['top'] = 2
            if row_num == total_rows - 1: dict_col0['bottom'] = 2
            dict_col0['left'] = 2
            worksheet.write(row_num, 0, lbl, workbook.add_format(dict_col0))

            if row_num == 0: dict_col1 = base_header_center.copy()
            elif lbl == "Working Hrs": dict_col1 = base_val_yellow.copy()
            elif lbl in ["Pay Hrs", "PL Used", "Total Pay Hrs"]: dict_col1 = base_val_green.copy()
            elif lbl in ["Pay Salary", "In Hand Salary"]: dict_col1 = base_pay_val_center.copy()
            elif lbl == "OT Salary": dict_col1 = base_ot_val_center.copy()
            elif lbl == "Diff":
                diff_val = float(val) if val != "-" else 0
                if diff_val > 0: dict_col1 = base_diff_pos_red.copy()
                elif diff_val < 0: dict_col1 = base_diff_neg_green.copy()
                else: dict_col1 = base_diff_zero.copy()
            elif lbl == "TDS" and val != "-": dict_col1 = base_val_curr_tds.copy() 
            elif lbl in currency_labels and val != "-": dict_col1 = base_val_curr.copy()
            else: dict_col1 = base_val_text.copy()

            dict_col1['border'] = 1
            if row_num == 0: dict_col1['top'] = 2
            if row_num == total_rows - 1: dict_col1['bottom'] = 2
            dict_col1['right'] = 2
            worksheet.write(row_num, 1, val, workbook.add_format(dict_col1))
            
    return output.getvalue()

money_cols = ["CTC", "OT Salary", "Net Salary", "In Hand Salary", "Food", "Gratuity", "PT", "ESIC", "Advance", "Bonus", "Difference"]
table_format_config = {col: st.column_config.NumberColumn(format="₹ %,.0f") for col in money_cols}
table_format_config["TDS"] = st.column_config.NumberColumn(format="₹ %,.2f") 

pl_cols = ["Opening PL", "PL Used", "PL Balance"]
for col in pl_cols:
    table_format_config[col] = st.column_config.NumberColumn(format="%d")

# ==========================================
# 5. Sidebar Profile & Logic Setup
# ==========================================
with st.sidebar:
    st.header("👤 Profile")
    emp_sidebar_name = st.text_input("Employee Name", placeholder="Enter Name...", label_visibility="collapsed").title()
    
    user_file = get_user_file(emp_sidebar_name)
    
    if emp_sidebar_name and user_file and os.path.exists(user_file):
        st.write("")
        if st.button("🗑️ Delete All Data", type="secondary", use_container_width=True, help="Permanently delete all data for this employee"):
            try:
                os.remove(user_file)
                st.session_state['calc_result'] = None 
                st.session_state['flash_msg'] = f"✅ All data for {emp_sidebar_name} has been deleted!"
                st.rerun()
            except Exception as e:
                st.error("Error deleting file.")
                
    st.divider()

    last_data = {"CTC": 0.0, "Working_Hrs": 0.0, "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, "Advance": 0.0, "Difference": 0.0, "TDS": 0.0, "ESIC": 0.0}
    
    is_new_employee = True
    last_pl_balance = 0
    last_saved_month = None
    df_hist_sorted = pd.DataFrame() 

    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file)
            df_hist = clean_legacy_columns(df_hist)
                
            if not df_hist.empty:
                is_new_employee = False
                
                df_hist['Month_Num'] = df_hist['Month'].astype(str).str.strip().map(month_dict)
                df_hist_sorted = df_hist.sort_values(by=['Year', 'Month_Num']).reset_index(drop=True)
                last_row_chronological = df_hist_sorted.iloc[-1]
                
                last_pl_balance = int(float(last_row_chronological.get("PL Balance", 0)))
                last_saved_month = str(last_row_chronological.get("Month", "")).strip()

                key_mapping = {
                    "CTC": "CTC", "Working Hrs": "Working_Hrs", 
                    "Gratuity": "Gratuity", "PT": "PT", "TDS": "TDS", "ESIC": "ESIC",
                    "Food": "Food", "Advance": "Advance", "Difference": "Difference"
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
# 6. MONTH/YEAR (OUTSIDE FORM FOR AUTO-FILL)
# ==========================================
kb = f"{st.session_state['form_key']}_{emp_sidebar_name.strip()}"

now = datetime.now()
current_month_name = now.strftime("%b") 
current_year = now.year

m_list = list(month_dict.keys())
default_month = current_month_name 
def_year = current_year

if not is_new_employee and not df_hist_sorted.empty:
    last_row = df_hist_sorted.iloc[-1]
    last_saved_month = str(last_row.get("Month", "")).strip()
    if last_saved_month in m_list:
        last_idx = m_list.index(last_saved_month)
        if last_idx < 11: 
            default_month = m_list[last_idx + 1]
            def_year = int(last_row.get("Year", current_year))
        else:
            default_month = 'Jan' 
            def_year = int(last_row.get("Year", current_year)) + 1

def_m_idx = m_list.index(default_month) if default_month in m_list else 0

with st.container(border=True):
    col_m, col_y, col_emp = st.columns([1, 1, 2])
    with col_m:
        selected_month = st.selectbox("📅 Month", m_list, index=def_m_idx, disabled=(not is_new_employee), key=f"month_{kb}")
    with col_y:
        selected_year = st.number_input("🗓️ Year", min_value=2024, max_value=2030, value=def_year, disabled=(not is_new_employee), key=f"year_{kb}")
    with col_emp:
        emp_name = st.text_input("Full Name", value=emp_sidebar_name, disabled=True)

# Fetching Data Logic
form_data = {"CTC": 0.0, "Working_Hrs": 0.0, "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, "Advance": 0.0, "Difference": 0.0, "TDS": 0.0, "ESIC": 0.0, "PL_Used": 0}
opening_pl = 0
is_editing_past = False

if not is_new_employee and not df_hist_sorted.empty:
    existing_row = df_hist_sorted[(df_hist_sorted['Month'].astype(str).str.strip() == selected_month) & (df_hist_sorted['Year'] == selected_year)]
    
    if not existing_row.empty:
        is_editing_past = True
        row = existing_row.iloc[0]
        form_data["CTC"] = float(row.get("CTC", 0.0))
        form_data["Working_Hrs"] = float(row.get("Working Hrs", 0.0))
        form_data["Food"] = float(row.get("Food", 0.0))
        form_data["Gratuity"] = float(row.get("Gratuity", 0.0))
        form_data["PT"] = float(row.get("PT", 200.0))
        form_data["Bonus"] = float(row.get("Bonus", 0.0))
        form_data["Advance"] = float(row.get("Advance", 0.0))
        form_data["Difference"] = float(row.get("Difference", 0.0))
        form_data["TDS"] = float(row.get("TDS", 0.0))
        form_data["ESIC"] = float(row.get("ESIC", 0.0))
        form_data["PL_Used"] = int(float(row.get("PL Used", 0)))
        opening_pl = int(float(row.get("Opening PL", 0)))
    else:
        last_row = df_hist_sorted.iloc[-1]
        form_data["CTC"] = float(last_row.get("CTC", 0.0))
        form_data["Working_Hrs"] = float(last_row.get("Working Hrs", 0.0))
        form_data["PT"] = float(last_row.get("PT", 200.0))
        form_data["TDS"] = float(last_row.get("TDS", 0.0))
        form_data["ESIC"] = float(last_row.get("ESIC", 0.0))
        opening_pl = int(float(last_row.get("PL Balance", 0))) + 1

att_data = fetch_attendance_data(emp_name, selected_month, selected_year) if emp_name else {"reg_h": 0, "reg_m": 0, "ot_h": 0, "ot_m": 0, "late_h": 0, "late_m": 0, "out_h": 0, "out_m": 0}

# ==========================================
# 7. MAIN FORM
# ==========================================
with st.form(key=f"salary_form_{kb}"):
    col1, col_line, col2 = st.columns([1, 0.05, 1])
    
    with col1:
        st.markdown('<div id="left-column-marker"></div>', unsafe_allow_html=True)
        st.subheader("💰 Basic Details")
        c1_1, c1_2 = st.columns(2)
        with c1_1:
            ctc_salary = st.number_input("CTC Salary (₹)", value=float(form_data["CTC"]), format="%.0f")
            
            p_h_col, p_m_col = st.columns(2)
            with p_h_col:
                present_hrs_input = st.number_input("Pay Hrs", value=att_data["reg_h"], step=1)
            with p_m_col:
                present_mins_input = st.number_input("Mins", value=att_data["reg_m"], min_value=0, max_value=59, step=1)
            
            if is_new_employee:
                opening_pl = st.number_input("Opening PL Balance", value=0, step=1)
            else:
                st.text_input("Opening PL Balance (Auto)", value=str(int(opening_pl)), disabled=True)

            used_pl = st.number_input("PL Used", value=int(form_data["PL_Used"]), step=1)

        with c1_2:
            work_hrs = st.number_input("Working Hrs", value=float(form_data["Working_Hrs"]), format="%.0f")
            
            l_h_col, l_m_col = st.columns(2)
            with l_h_col: late_hrs_input = st.number_input("Late Hrs", value=att_data["late_h"], step=1)
            with l_m_col: late_mins_input = st.number_input("Late Mins", value=att_data["late_m"], min_value=0, max_value=59, step=1)
            
            e_h_col, e_m_col = st.columns(2)
            with e_h_col: out_hrs_input = st.number_input("Out Hrs", value=att_data["out_h"], step=1)
            with e_m_col: out_mins_input = st.number_input("Out Mins", value=att_data["out_m"], min_value=0, max_value=59, step=1)
            
            o_h_col, o_m_col = st.columns(2)
            with o_h_col: ot_hrs_input = st.number_input("OT Hrs", value=att_data["ot_h"], step=1)
            with o_m_col: ot_mins_input = st.number_input("OT Mins", value=att_data["ot_m"], min_value=0, max_value=59, step=1)

    with col_line:
        st.markdown("""
            <style>
                .vline {
                    width: 2px;
                    background-color: rgba(255, 255, 255, 0.2);
                    height: 420px;
                    margin: 40px auto 0 auto;
                    border-radius: 2px;
                }
                @media (max-width: 768px) {
                    .vline { display: none; }
                }
            </style>
            <div class="vline"></div>
        """, unsafe_allow_html=True)

    with col2:
        st.subheader("📉 Deductions & Additions")
        c2_1, c2_2 = st.columns(2)
        with c2_1:
            food = st.number_input("Food (₹)", value=float(form_data["Food"]), format="%.0f")
            pt_tax = st.number_input("PT Tax (₹)", value=float(form_data["PT"]), format="%.0f")
            tds = st.number_input("TDS (₹)", value=float(form_data["TDS"]), format="%.2f")
            bonus = st.number_input("Bonus (₹)", value=float(form_data["Bonus"]), format="%.0f")
        with c2_2:
            gratuity = st.number_input("Gratuity (₹)", value=float(form_data["Gratuity"]), format="%.0f")
            advance = st.number_input("Loan/Advance (₹)", value=float(form_data["Advance"]), format="%.0f")
            esic = st.number_input("ESIC (₹)", value=float(form_data["ESIC"]), format="%.0f")
            difference = st.number_input("Difference (₹)", value=float(form_data["Difference"]), format="%.0f")
            
    st.write("")
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        save_clicked = st.form_submit_button("Calculate & Save Data", type="primary", use_container_width=True)

# ==========================================
# TIME CALCULATION LOGIC
# ==========================================
final_pl_balance = int(opening_pl) - int(used_pl)
pl_hours_to_add = int(used_pl) * 10 

total_late_mins = (late_hrs_input * 60) + late_mins_input
total_out_mins = (out_hrs_input * 60) + out_mins_input
total_ot_mins = (ot_hrs_input * 60) + ot_mins_input

total_pay_mins = (present_hrs_input * 60) + present_mins_input
total_min = total_pay_mins + int(pl_hours_to_add * 60)

if total_min < 0: total_min = 0

calc_final_hrs = f"{total_min // 60}:{total_min % 60:02d}"
late_hrs_str = f"{total_late_mins // 60}:{total_late_mins % 60:02d}"
early_hrs_str = f"{total_out_mins // 60}:{total_out_mins % 60:02d}"
ot_hrs_str = f"{total_ot_mins // 60}:{total_ot_mins % 60:02d}"

total_late_out_mins = total_late_mins + total_out_mins
deductible_mins = max(0, total_late_out_mins - 120) 

total_pay_hrs_mins = (total_min + total_ot_mins) - deductible_mins
if total_pay_hrs_mins < 0:
    total_pay_hrs_mins = 0
    
total_pay_hrs_str = f"{total_pay_hrs_mins // 60}:{total_pay_hrs_mins % 60:02d}"

# ==========================================
# 8. Execution Logic
# ==========================================
if save_clicked:
    if not emp_sidebar_name: 
        st.error("Please enter Employee Name in the sidebar!")
    else:
        base_sal = ctc_salary - gratuity - bonus
        hr_rate = base_sal / work_hrs if work_hrs > 0 else 0
        
        total_earned_exact = (total_pay_hrs_mins / 60.0) * hr_rate
        in_hand_salary = round(total_earned_exact - food - pt_tax - tds - esic - advance)
        
        ot_salary = round((total_ot_mins / 60.0) * hr_rate) 
        pay_salary_val = in_hand_salary - ot_salary
        bank_salary_val = in_hand_salary + difference
        
        st.session_state['calc_result'] = {
            "name": emp_name, "month": selected_month, "year": selected_year, "in_hand": in_hand_salary, "ot_sal": ot_salary, "pl": final_pl_balance,
            "slip_data": {
                "work_hrs_str": f"{int(work_hrs)}:00",
                "ctc": ctc_salary, "bonus": bonus, "gratuity": gratuity,
                "actual_salary": ctc_salary - gratuity - bonus,
                "present_hrs": f"{int(present_hrs_input)}:{int(present_mins_input):02d}",
                "pl_used": used_pl,
                "pl_balance": final_pl_balance,
                "ot_hrs": ot_hrs_str,
                "late_hrs": late_hrs_str,
                "out_hrs": early_hrs_str,
                "pay_hrs": total_pay_hrs_str,
                "pt": pt_tax, "tds": tds, "esic": esic, "advance": advance, "food": food, "difference": difference,
                "pay_salary_val": pay_salary_val,
                "ot_sal": ot_salary,
                "in_hand_salary": in_hand_salary,
                "bank_salary_val": bank_salary_val
            }
        }
        
        new_rec_dict = {
            "Date": datetime.now().strftime("%d-%m-%Y"), "Name": emp_name, "Month": selected_month, "Year": selected_year,
            "CTC": ctc_salary, "Working Hrs": work_hrs, "Present Hrs": f"{int(present_hrs_input)}:{int(present_mins_input):02d}", 
            "Late Hrs": late_hrs_str, "Out Hrs": early_hrs_str, "OT Hrs": ot_hrs_str,
            "Final Present Hrs": calc_final_hrs, "Total Pay Hrs": total_pay_hrs_str,
            "Opening PL": opening_pl, "PL Used": used_pl, "PL Balance": final_pl_balance,
            "OT Salary": ot_salary, "Net Salary": bank_salary_val, "In Hand Salary": in_hand_salary, 
            "Food": food, "Gratuity": gratuity, "PT": pt_tax, "TDS": tds, "ESIC": esic, 
            "Advance": advance, "Bonus": bonus, "Difference": difference
        }
        new_rec = pd.DataFrame([new_rec_dict])
        
        if os.path.exists(user_file):
            df_existing = pd.read_csv(user_file)
            if 'Opening PL' not in df_existing.columns:
                df_existing['Opening PL'] = 0
            if 'In Hand Salary' not in df_existing.columns:
                df_existing['In Hand Salary'] = 0.0
            if 'Total Pay Hrs' not in df_existing.columns:
                df_existing['Total Pay Hrs'] = ""
                
            df_existing = df_existing[~((df_existing['Month'].astype(str).str.strip() == selected_month) & (df_existing['Year'] == selected_year))]
            df_combined = pd.concat([df_existing, new_rec], ignore_index=True)
            df_combined['Month_Num'] = df_combined['Month'].astype(str).str.strip().map(month_dict)
            df_combined = df_combined.sort_values(by=['Year', 'Month_Num']).reset_index(drop=True)
            
            updated_idx = df_combined.index[(df_combined['Month'] == selected_month) & (df_combined['Year'] == selected_year)].tolist()[0]
            if updated_idx < len(df_combined) - 1:
                df_combined = recalculate_future_pl(df_combined, updated_idx)
            
            df_combined = df_combined.drop(columns=['Month_Num'])
            df_combined.to_csv(user_file, index=False)
        else: 
            new_rec.to_csv(user_file, index=False)
            
        st.session_state['form_key'] += 1
        st.session_state['flash_msg'] = f"✅ Data Saved! Name: {emp_name} | In Hand Salary: ₹ {int(in_hand_salary):,} | Bank Salary: ₹ {int(bank_salary_val):,} | OT Salary: ₹ {int(ot_salary):,} | PL Balance: {final_pl_balance}"
        st.rerun()

# ==========================================
# 9. SLIP DOWNLOAD BUTTON (OUTSIDE FORM)
# ==========================================
if st.session_state.get('calc_result'):
    res = st.session_state['calc_result']
    if res['name'] == emp_sidebar_name:
        excel_data = generate_excel_slip(res['slip_data'], res['name'], res['month'], res['year'])
        
        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            st.download_button(
                label="📄 Download Excel Slip",
                data=excel_data,
                file_name=f"{res['name']}_Salary_Slip_{res['month']}_{res['year']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

# ==========================================
# 10. Search Section
# ==========================================
st.divider()
st.subheader("🔍 Search Records")
with st.container(border=True):
    s1, s2, s3, s4 = st.columns([4, 1.5, 1.5, 1.5])
    search_n = s1.text_input("Search Name", placeholder="Name...", label_visibility="collapsed", key="sn").title()
    search_m = s2.selectbox("Month", list(month_dict.keys()), key="sm", label_visibility="collapsed")
    search_y = s3.number_input("Year", value=current_year, key="sy", label_visibility="collapsed")
    
    if s4.button("🔍 Search", use_container_width=True):
        s_file = get_user_file(search_n)
        if os.path.exists(s_file):
            df_s = pd.read_csv(s_file)
            df_s = clean_legacy_columns(df_s)
                
            res = df_s[(df_s['Month'].str.strip() == search_m) & (df_s['Year'] == search_y)]
            if not res.empty:
                res.index = range(1, len(res) + 1)
                st.dataframe(res, use_container_width=True, column_config=table_format_config)
            else: 
                st.warning("No record found for this month/year.")
        else: 
            st.error("File not found.")

# ==========================================
# 11. History & Download Old Slips
# ==========================================
if emp_sidebar_name:
    st.divider()
    user_file = get_user_file(emp_sidebar_name)
    if os.path.exists(user_file):
        st.subheader(f"📂 History: {emp_sidebar_name}")
        h_df = pd.read_csv(user_file).fillna(0)
        h_df = clean_legacy_columns(h_df)

        if 'Month' in h_df.columns:
            h_df['Sort_M'] = h_df['Month'].astype(str).str.strip().map(month_dict)
            if 'Year' in h_df.columns:
                h_df = h_df.sort_values(['Year', 'Sort_M']).drop(columns=['Sort_M']).reset_index(drop=True)
            else:
                h_df = h_df.sort_values('Sort_M').drop(columns=['Sort_M']).reset_index(drop=True)

        cols = list(h_df.columns)
        if 'Opening PL' in cols and 'PL Used' in cols and 'PL Balance' in cols:
            if 'Total Pay Hrs' in cols and 'Final Present Hrs' in cols:
                if cols.index('Total Pay Hrs') != cols.index('Final Present Hrs') + 1:
                    cols.insert(cols.index('Final Present Hrs') + 1, cols.pop(cols.index('Total Pay Hrs')))
            cols.insert(cols.index('PL Used'), cols.pop(cols.index('Opening PL')))
            h_df = h_df[cols]

        def highlight_salary_columns(col):
            if col.name == 'Net Salary':
                return ['background-color: #4a1c1c; color: #ff9999; font-weight: bold'] * len(col)
            elif col.name == 'In Hand Salary':
                return ['background-color: #1c4a22; color: #99ff99; font-weight: bold'] * len(col)
            return [''] * len(col)

        styled_h_df = h_df.style.apply(highlight_salary_columns, axis=0)

        edited_df = st.data_editor(
            styled_h_df, 
            use_container_width=True, 
            num_rows="dynamic",
            key=f"editor_{emp_sidebar_name.lower().replace(' ', '_')}",
            column_config=table_format_config
        )
        
        if not h_df.equals(edited_df):
            edited_df.to_csv(user_file, index=False)
            st.toast("✅ Record auto-updated successfully!") 
            st.rerun()

        st.write("")
        with st.container(border=True):
            st.markdown("#### 📥 Download Slip from History")
            h1, h2 = st.columns([2, 1])
            with h1:
                options = []
                for idx, r in h_df.iterrows():
                    options.append(f"{str(r.get('Month', '')).strip()} - {int(r.get('Year', current_year))}")
                
                unique_options = list(dict.fromkeys(options))
                selected_opt = st.selectbox("Select Month & Year:", unique_options, key="hist_dl_sel")
            
            with h2:
                st.write("") 
                st.write("")
                if selected_opt:
                    sel_m, sel_y = selected_opt.split(" - ")
                    row = h_df[(h_df['Month'].astype(str).str.strip() == sel_m) & (h_df['Year'] == int(sel_y))].iloc[-1]
                    
                    ot_val = str(row.get("OT Hrs", "0:00")).strip()
                    late_val = str(row.get("Late Hrs", "0:00")).strip()
                    early_val = str(row.get("Out Hrs", "0:00")).strip()
                    pay_str = str(row.get("Total Pay Hrs", row.get("Final Present Hrs", "0:00"))).strip() 
                    present_str = str(row.get("Present Hrs", "0:00")).strip()
                        
                    actual_salary_hist = row.get("CTC", 0) - row.get("Bonus", 0) - row.get("Gratuity", 0)
                    
                    net_sal_hist = float(row.get("Net Salary", 0)) 
                    in_hand_hist = float(row.get("In Hand Salary", 0))
                    diff_hist = float(row.get("Difference", 0))
                    
                    if in_hand_hist == 0:
                        pay_salary_hist = round(net_sal_hist - diff_hist - float(row.get("OT Salary", 0)))
                        in_hand_hist = pay_salary_hist + float(row.get("OT Salary", 0))
                    else:
                        pay_salary_hist = in_hand_hist - float(row.get("OT Salary", 0))
                    
                    hist_slip_data = {
                        "work_hrs_str": f"{int(row.get('Working Hrs', 0))}:00",
                        "ctc": row.get("CTC", 0),
                        "bonus": row.get("Bonus", 0),
                        "gratuity": row.get("Gratuity", 0),
                        "actual_salary": actual_salary_hist,
                        "present_hrs": present_str,
                        "pl_used": row.get("PL Used", 0),
                        "pl_balance": row.get("PL Balance", 0),
                        "ot_hrs": ot_val,
                        "late_hrs": late_val,
                        "out_hrs": early_val,
                        "pay_hrs": pay_str,
                        "pt": row.get("PT", 0),
                        "tds": row.get("TDS", 0),
                        "esic": row.get("ESIC", 0),
                        "advance": row.get("Advance", 0),
                        "food": row.get("Food", 0),
                        "difference": diff_hist,
                        "pay_salary_val": pay_salary_hist,
                        "ot_sal": float(row.get("OT Salary", 0)),
                        "in_hand_salary": in_hand_hist,
                        "bank_salary_val": round(net_sal_hist)
                    }
                    
                    excel_data_hist = generate_excel_slip(hist_slip_data, row.get("Name", ""), sel_m, sel_y)
                    
                    st.download_button(
                        label=f"📄 Download Slip ({sel_m} {sel_y})",
                        data=excel_data_hist,
                        file_name=f"{row.get('Name', '')}_Salary_Slip_{sel_m}_{sel_y}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="hist_dl_btn"
                    )
            
    else:
        st.info("No salary data saved for this employee yet. (Calculate & Save Data to add new employee)")
