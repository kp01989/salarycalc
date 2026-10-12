import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import os
import io

# ==========================================
# 1. Page Setup & Config
# ==========================================
st.set_page_config(page_title="Salary & Attendance Management System", layout="wide", page_icon="📅")
month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
month_dict = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}

FILE_NAME = "Attendance_Tracker.xlsx"
STANDARD_IN = "08:00"
STANDARD_OUT = "18:00"

# ==========================================
# 2. Custom CSS
# ==========================================
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .summary-container {
        background-color: #1e2530;
        border: 2px solid #303d4f;
        border-radius: 12px;
        padding: 20px 20px 10px 20px;
        margin-bottom: 25px;
    }
    .stButton > button { 
        transition: all 0.2s ease-in-out !important; 
        cursor: pointer !important; 
    }
    .stButton > button:hover { 
        transform: scale(1.05) !important; 
        box-shadow: 0px 4px 15px rgba(255, 75, 75, 0.4) !important; 
    }
    div[data-baseweb="input"], div[data-testid="stDateInput"], div[data-testid="stTimeInput"] {
        max-width: 320px;
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
    st.markdown("<h2 style='text-align: center;'>🔐 Salary & Attendance System Login</h2>", unsafe_allow_html=True)
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

st.markdown("<h1 style='text-align: center;'>💎 Attendance & Salary Management</h1>", unsafe_allow_html=True)
st.divider()

# ==========================================
# 4. Helper Functions & Configs
# ==========================================
def get_user_file(name):
    if not name: return None
    return f"{name.strip().replace(' ', '_')}_salary.csv"

def get_sheet_name(selected_date):
    return selected_date.strftime("%b'%Y")

def get_all_sheet_names():
    if os.path.exists(FILE_NAME):
        xl = pd.ExcelFile(FILE_NAME)
        return xl.sheet_names
    return [get_sheet_name(date.today())]

def get_all_employees():
    if not os.path.exists(FILE_NAME):
        return []
    try:
        xl = pd.ExcelFile(FILE_NAME)
        emps = set()
        for sheet in xl.sheet_names:
            df = pd.read_excel(FILE_NAME, sheet_name=sheet, dtype=str)
            if "Employee Name" in df.columns:
                emps.update(df["Employee Name"].dropna().unique())
        valid_emps = [e for e in emps if e != "-"]
        return sorted(list(valid_emps))
    except Exception:
        return []

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

money_cols = ["CTC", "OT Salary", "Net Salary", "Food", "Gratuity", "PT", "TDS", "ESIC", "Advance", "Bonus", "Difference"]
table_format_config = {col: st.column_config.NumberColumn(format="₹ %,.2f") for col in money_cols}

def calculate_times(in_time, out_time, day_str):
    fmt = "%H:%M"
    if not isinstance(in_time, str):
        in_time = in_time.strftime(fmt)
    if not isinstance(out_time, str):
        out_time = out_time.strftime(fmt)
        
    t1 = datetime.strptime(in_time, fmt)
    t2 = datetime.strptime(out_time, fmt)
    std_in = datetime.strptime(STANDARD_IN, fmt)
    std_out = datetime.strptime(STANDARD_OUT, fmt)
    
    if t2 < t1:
        return "00:00", "", "", "00:00"
        
    total_worked_mins = (t2 - t1).seconds // 60
    
    if day_str == "Sun":
        reg_mins = 0
        ot_mins = total_worked_mins 
    else:
        actual_start = max(t1, std_in)
        actual_end = min(t2, std_out)
        
        if actual_end > actual_start:
            reg_mins = (actual_end - actual_start).seconds // 60
        else:
            reg_mins = 0
            
        ot_mins = total_worked_mins - reg_mins
        
        if ot_mins < 30:
            ot_mins = 0
            
    if day_str == "Sun":
        late_mins = 0
        out_early_mins = 0
    else:
        late_mins = max(0, (t1 - std_in).total_seconds() // 60) if t1 > std_in else 0
        out_early_mins = max(0, (std_out - t2).total_seconds() // 60) if t2 < std_out else 0
    
    def mins_to_str(m):
        h, m = divmod(int(m), 60)
        return f"{h:02d}:{m:02d}"
        
    total_hrs = mins_to_str(reg_mins)
    ot_hrs = mins_to_str(ot_mins)
    late_hrs = mins_to_str(late_mins) if late_mins > 0 else ""
    out_hrs = mins_to_str(out_early_mins) if out_early_mins > 0 else ""
    
    return total_hrs, late_hrs, out_hrs, ot_hrs

def load_attendance_data(sheet_name):
    columns = ["Employee Name", "Date", "Day", "In Time", "Out Time", "Late Hours", "Out Hours", "Total Hours", "OT Hours"]
    if os.path.exists(FILE_NAME):
        try:
            df = pd.read_excel(FILE_NAME, sheet_name=sheet_name, dtype=str)
            if "Employee Name" not in df.columns:
                df.insert(0, "Employee Name", "-")
            if "OT Hours" not in df.columns:
                df["OT Hours"] = "00:00"
            cols_to_drop = ["Late Minutes", "Out Minutes"]
            df = df.drop(columns=[col for col in cols_to_drop if col in df.columns], errors='ignore')
            
            for idx, row in df.iterrows():
                in_t = str(row.get("In Time", "08:00"))
                out_t = str(row.get("Out Time", "18:00"))
                day_s = str(row.get("Day", "Mon"))
                
                if pd.isna(row.get("In Time")) or in_t.lower() == 'nan':
                    continue
                    
                try:
                    tot, late, out_e, ot = calculate_times(in_t, out_t, day_s)
                    df.at[idx, "Total Hours"] = tot
                    df.at[idx, "Late Hours"] = late
                    df.at[idx, "Out Hours"] = out_e
                    df.at[idx, "OT Hours"] = ot
                except Exception:
                    pass
            return df
        except ValueError:
            return pd.DataFrame(columns=columns)
    else:
        return pd.DataFrame(columns=columns)

def save_attendance_data(df, sheet_name):
    if not os.path.exists(FILE_NAME):
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

# ==========================================
# 5. Sidebar Profile & Logic Setup
# ==========================================
with st.sidebar:
    st.header("👤 Profile")
    emp_sidebar_name = st.text_input("👤 Employee Name", placeholder="Enter Name...", label_visibility="collapsed")
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
        except Exception:
            pass

# ==========================================
# 6. Daily Attendance Tracker Section
# ==========================================
current_month_str = get_sheet_name(date.today())

if 'last_edited' not in st.session_state:
    st.session_state.last_edited = None

if 'filter_month' not in st.session_state:
    st.session_state.filter_month = current_month_str

if 'top_emp_input' not in st.session_state:
    st.session_state.top_emp_input = ""
    
if 'form_reset_counter' not in st.session_state:
    st.session_state.form_reset_counter = 0

def on_top_name_change():
    val = st.session_state.top_emp_input.strip()
    if val:
        st.session_state.filter_month = current_month_str

with st.expander("➕ Add New Attendance Entry / Search", expanded=True):
    col_input1, col_input2 = st.columns([1.5, 2.5])
    
    with col_input1:
        st.text_input("Employee Name", placeholder="Please enter name", key="top_emp_input", on_change=on_top_name_change)
    
    formatted_name = st.session_state.top_emp_input.strip().title()

    if formatted_name == "Admin":
        all_emps = get_all_employees()
        if all_emps:
            st.caption(f"📝 **Existing Employees:** {', '.join(all_emps)}")

    # Time inputs outside st.form so they correctly capture selected time values
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2])
    with c1:
        entry_date = st.date_input("Date", date.today(), format="DD/MM/YYYY")
        
    dynamic_key_in = f"in_{entry_date}_{st.session_state.form_reset_counter}"
    dynamic_key_out = f"out_{entry_date}_{st.session_state.form_reset_counter}"
    
    with c2:
        in_time = st.time_input("In Time", value=time(8, 0), key=dynamic_key_in)
    with c3:
        out_time = st.time_input("Out Time", value=time(18, 0), key=dynamic_key_out)
        
    with c4:
        st.write("")
        st.write("")
        submit = st.button("Save Attendance", type="primary", use_container_width=True)

    if submit:
        if not formatted_name:
            st.error("Please enter an Employee Name above!")
        elif formatted_name == "Admin":
            st.error("You cannot add an entry for 'Admin'. Please type a valid name!")
        elif out_time < in_time:
            st.error("Out Time cannot be before In Time!")
        else:
            target_sheet = get_sheet_name(entry_date)
            df_month = load_attendance_data(target_sheet)
            
            day_str = entry_date.strftime("%a")
            date_str = entry_date.strftime("%d/%m/%Y")
            
            is_duplicate = not df_month[(df_month["Employee Name"] == formatted_name) & (df_month["Date"] == date_str)].empty
            
            if is_duplicate:
                st.error(f"⚠️ An entry for {formatted_name} on {date_str} already exists!")
            else:
                total_hrs, late_hrs, out_hrs, ot_hrs = calculate_times(in_time, out_time, day_str)
                new_entry = pd.DataFrame({
                    "Employee Name": [formatted_name],
                    "Date": [date_str],
                    "Day": [day_str],
                    "In Time": [in_time.strftime("%H:%M")],
                    "Out Time": [out_time.strftime("%H:%M")],
                    "Late Hours": [late_hrs],
                    "Out Hours": [out_hrs],
                    "Total Hours": [total_hrs],
                    "OT Hours": [ot_hrs]
                })
                df_month = pd.concat([df_month, new_entry], ignore_index=True)
                save_attendance_data(df_month, target_sheet) 
                
                st.session_state.filter_month = target_sheet
                st.session_state.last_edited = f"{formatted_name}_{date_str}"
                st.session_state.form_reset_counter += 1
                
                st.success(f"Entry for {formatted_name} saved successfully!")
                st.rerun() 

st.divider()

# ==========================================
# 7. Salary & Leave Management Form Logic
# ==========================================
now = datetime.now()
current_month_name = now.strftime("%b") 
current_year = now.year

auto_present_hrs = float(last_data["Present_Hrs"])
auto_ot_mins = int(last_data["OT"])
auto_late_mins = int(last_data["Late"])
auto_early_mins = int(last_data["Early"])

if emp_sidebar_name:
    pass

kb = f"{st.session_state['form_key']}_{emp_sidebar_name.strip()}"

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Salary & Hours Details")
        emp_name = st.text_input("👤 Full Name", value=emp_sidebar_name, disabled=True)
        
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
            month = st.selectbox("📅 Month", m_list, index=def_m_idx, disabled=(not is_new_employee), key=f"month_{kb}")
        with y_col:
            year = st.number_input("🗓️ Year", min_value=2024, max_value=2030, value=def_year, disabled=(not is_new_employee), key=f"year_{kb}")
            
        c1_1, c1_2 = st.columns(2)
        with c1_1:
            ctc_salary = st.number_input("💰 CTC Salary (₹)", value=float(last_data["CTC"]), key=f"ctc_{kb}")
            
            def_p_hrs = int(auto_present_hrs)
            def_p_mins = int(round((auto_present_hrs - def_p_hrs) * 100))
            
            p_h_col, p_m_col = st.columns(2)
            with p_h_col:
                present_hrs_input = st.number_input("✅ Present Hrs", value=def_p_hrs, step=1, key=f"phrs_{kb}")
            with p_m_col:
                present_mins_input = st.number_input("⏱️ Mins", value=def_p_mins, min_value=0, max_value=59, step=1, key=f"pmins_{kb}")
            
            available_pl = 0.0
            if emp_sidebar_name and is_new_employee:
                available_pl = st.number_input("⚖️ Opening PL Balance", value=0.0, step=0.5, key=f"opl_{kb}")
            elif emp_sidebar_name and not is_new_employee:
                available_pl = last_pl_balance + 1.0
                st.text_input(f"⚖️ Available PL (From {last_saved_month} + 1)", value=str(available_pl), disabled=True)

            used_pl = st.number_input("🏖️ PL Used", value=0.0, step=0.5, key=f"plu_{kb}")

        with c1_2:
            work_hrs = st.number_input("🏢 Working Hrs", value=float(last_data["Working_Hrs"]), key=f"shrs_{kb}")
            
            # --- LATE ---
            def_late_hrs = auto_late_mins // 60
            def_late_mins = auto_late_mins % 60
            l_h_col, l_m_col = st.columns(2)
            with l_h_col: late_hrs_input = st.number_input("⏰ Late Hrs", value=def_late_hrs, step=1, key=f"lhrs_{kb}")
            with l_m_col: late_mins_input = st.number_input("⏱️ Late Mins", value=def_late_mins, min_value=0, max_value=59, step=1, key=f"lmins_{kb}")

            # --- EARLY GOING ---
            def_early_hrs = auto_early_mins // 60
            def_early_mins = auto_early_mins % 60
            e_h_col, e_m_col = st.columns(2)
            with e_h_col: early_hrs_input = st.number_input("🚶 Out Hrs", value=def_early_hrs, step=1, key=f"ehrs_{kb}")
            with e_m_col: early_mins_input = st.number_input("⏱️ Out Mins", value=def_early_mins, min_value=0, max_value=59, step=1, key=f"emins_{kb}")

            # --- OT (Overtime) ---
            def_ot_hrs = auto_ot_mins // 60
            def_ot_mins = auto_ot_mins % 60
            o_h_col, o_m_col = st.columns(2)
            with o_h_col: ot_hrs_input = st.number_input("⏳ OT Hrs", value=def_ot_hrs, step=1, key=f"othrs_{kb}")
            with o_m_col: ot_mins_input = st.number_input("⏱️ OT Mins", value=def_ot_mins, min_value=0, max_value=59, step=1, key=f"otmins_{kb}")

with col2:
    with st.container(border=True):
        st.subheader("📉 Deductions & Additions")
        c2_1, c2_2 = st.columns(2)
        with c2_1:
            food = st.number_input("🍽️ Food (₹)", value=float(last_data["Food"]), key=f"food_{kb}")
            pt_tax = st.number_input("🏛️ PT Tax (₹)", value=float(last_data["PT"]), key=f"pt_{kb}")
            tds = st.number_input("✂️ TDS (₹)", value=float(last_data["TDS"]), key=f"tds_{kb}")
            bonus = st.number_input("🎉 Bonus (₹)", value=float(last_data["Bonus"]), key=f"bn_{kb}")
        with c2_2:
            gratuity = st.number_input("🎁 Gratuity (₹)", value=float(last_data["Gratuity"]), key=f"gr_{kb}")
            advance = st.number_input("🏦 Loan/Advance (₹)", value=float(last_data["Advance"]), key=f"ad_{kb}")
            esic = st.number_input("🏥 ESIC (₹)", value=float(last_data["ESIC"]), key=f"esic_{kb}")
            difference = st.number_input("🧮 Difference (₹)", value=0.0, key=f"diff_{kb}")

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
# 8. Excel Slip Generation Helper
# ==========================================
def generate_excel_slip(slip_data, emp_name, month_str, year_val):
    sd = slip_data
    
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
    
    header_row = pd.DataFrame({"Label": [f"📅 {month_str}'{year_val}"], "Value": [f"👤 {emp_name}"]})
    slip_df = pd.concat([header_row, slip_df], ignore_index=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        slip_df.to_excel(writer, index=False, header=False, sheet_name='Salary_Slip')
        workbook = writer.book
        worksheet = writer.sheets['Salary_Slip']
        
        base_header = {'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'align': 'center', 'valign': 'vcenter', 'font_name': 'Segoe UI Emoji'}
        base_label = {'bold': True, 'bg_color': '#D9E1F2', 'align': 'center', 'valign': 'vcenter', 'font_name': 'Segoe UI Emoji'}
        base_val_text = {'align': 'center', 'valign': 'vcenter'}
        base_val_curr = {'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0.00'}
        base_val_yellow = {'bg_color': '#FFFF00', 'align': 'center', 'valign': 'vcenter'}
        base_val_green = {'bg_color': '#C6E0B4', 'align': 'center', 'valign': 'vcenter'}
        base_pay_label = {'bold': True, 'bg_color': '#C6E0B4', 'align': 'center', 'valign': 'vcenter', 'font_name': 'Segoe UI Emoji'}
        base_pay_val = {'bold': True, 'bg_color': '#C6E0B4', 'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0.00'}
        
        base_diff_pos = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#FF0000', 'num_format': '₹ #,##0.00'}
        base_diff_neg = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#228B22', 'num_format': '₹ #,##0.00'}
        base_diff_zero = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#000000', 'num_format': '₹ #,##0.00'}

        worksheet.set_column('A:A', 22)
        worksheet.set_column('B:B', 25)
        
        currency_labels = [
            "💰 CTC Salary", "🎉 Bonus", "🎁 Gratuity", "💵 Actual Salary", 
            "🏛️ PT", "🛡️ PF", "🏥 ESI", "✂️ TDS", "🏦 Loan", "🍽️ Food", 
            "💳 Bank Salary", "🧮 Diff"
        ]
        
        total_rows = len(slip_df)
        
        for row_num, (lbl, val) in enumerate(zip(slip_df['Label'], slip_df['Value'])):
            if row_num == 0:
                dict_col0 = base_header.copy()
            elif lbl == "💸 Pay Salary":
                dict_col0 = base_pay_label.copy()
            else:
                dict_col0 = base_label.copy()

            dict_col0['border'] = 1
            if row_num == 0: dict_col0['top'] = 2
            if row_num == total_rows - 1: dict_col0['bottom'] = 2
            dict_col0['left'] = 2

            worksheet.write(row_num, 0, lbl, workbook.add_format(dict_col0))

            if row_num == 0:
                dict_col1 = base_header.copy()
            elif lbl == "🏢 Working Hrs":
                dict_col1 = base_val_yellow.copy()
            elif lbl in ["✅ Present Hrs", "🏖️ PL Used"]:
                dict_col1 = base_val_green.copy()
            elif lbl == "💸 Pay Salary":
                dict_col1 = base_pay_val.copy()
            elif lbl == "🧮 Diff":
                diff_val = float(val) if val != "-" else 0
                if diff_val > 0: dict_col1 = base_diff_pos.copy()
                elif diff_val < 0: dict_col1 = base_diff_neg.copy()
                else: dict_col1 = base_diff_zero.copy()
            elif lbl in currency_labels and val != "-":
                dict_col1 = base_val_curr.copy()
            else:
                dict_col1 = base_val_text.copy()

            dict_col1['border'] = 1
            if row_num == 0: dict_col1['top'] = 2
            if row_num == total_rows - 1: dict_col1['bottom'] = 2
            dict_col1['right'] = 2

            worksheet.write(row_num, 1, val, workbook.add_format(dict_col1))
            
    return output.getvalue()

# ==========================================
# 9. Button Execution Logic
# ==========================================
st.write("")
_, btn_col, _ = st.columns([1, 1.5, 1])

with btn_col:
    save_clicked = st.button("Calculate & Save Salary Data", type="primary", use_container_width=True)

if save_clicked:
    if not emp_sidebar_name: 
        st.error("Please enter Employee Name in the sidebar!")
    else:
        base_sal = ctc_salary - gratuity - bonus
        hr_rate = base_sal / work_hrs if work_hrs > 0 else 0
        
        ot_salary = ((total_ot_mins // 60) * hr_rate) + ((total_ot_mins % 60) * (hr_rate/60.0))
        net_sal_exact = ((total_min // 60) * hr_rate) + ((total_min % 60) * (hr_rate/60.0)) - food - pt_tax - tds - esic - advance + difference
        net_sal = round(net_sal_exact)
        
        present_hrs_combined = present_hrs_input + (present_mins_input / 100.0)
        
        st.session_state['calc_result'] = {
            "name": emp_name, "month": month, "year": year, "net": net_sal, "ot_sal": round(ot_salary, 2), "pl": final_pl_balance,
            "slip_data": {
                "work_hrs_str": f"{int(work_hrs)}:00",
                "ctc": ctc_salary, "bonus": bonus, "gratuity": gratuity,
                "actual_salary": ctc_salary - gratuity - bonus,
                "present_hrs": f"{int(present_hrs_input)}:{int(present_mins_input):02d}",
                "pl_used": used_pl,
                "pl_balance": final_pl_balance,
                "ot_hrs": f"{total_ot_mins//60}:{total_ot_mins%60:02d}",
                "late_hrs": f"{total_late_mins//60}:{total_late_mins%60:02d}",
                "out_hrs": f"{total_early_mins//60}:{total_early_mins%60:02d}",
                "pay_hrs": f"{total_min//60}:{total_min%60:02d}",
                "pt": pt_tax, "tds": tds, "esic": esic, "advance": advance, "food": food, "difference": difference,
                "pay_salary_val": net_sal - difference,
                "bank_salary_val": net_sal
            }
        }
        
        new_rec = pd.DataFrame([{
            "Date": datetime.now().strftime("%d-%m-%Y"), "Name": emp_name, "Month": month, "Year": year,
            "CTC": ctc_salary, "Working Hrs": work_hrs, "Present Hrs": present_hrs_combined, 
            "Late Mins": total_late_mins, "Early Mins": total_early_mins, "OT Mins": total_ot_mins,
            "Final Present Hrs": calc_final_hrs, "PL Used": used_pl, "PL Balance": final_pl_balance,
            "OT Salary": round(ot_salary, 2), "Net Salary": net_sal, 
            "Food": food, "Gratuity": gratuity, "PT": pt_tax, "TDS": tds, "ESIC": esic, 
            "Advance": advance, "Bonus": bonus, "Difference": difference
        }])
        
        user_csv_file = get_user_file(emp_sidebar_name)
        if os.path.exists(user_csv_file):
            pd.concat([pd.read_csv(user_csv_file), new_rec], ignore_index=True).to_csv(user_csv_file, index=False)
        else: 
            new_rec.to_csv(user_csv_file, index=False)
            
        st.session_state['form_key'] += 1
        st.rerun()

# ==========================================
# SLIP DOWNLOAD BUTTON (AFTER SAVE)
# ==========================================
if st.session_state['calc_result']:
    res = st.session_state['calc_result']
    if res['name'] == emp_sidebar_name:
        st.success(f"✅ Data Saved! Name: {res['name']} | Net Salary: ₹ {res['net']:,.2f} | OT Salary: ₹ {res['ot_sal']:,.2f} | PL Balance: {res['pl']}")
        
        excel_data = generate_excel_slip(res['slip_data'], res['name'], res['month'], res['year'])
        
        _, btn_col, _ = st.columns([1, 1.5, 1])
        with btn_col:
            st.download_button(
                label="📄 Download Colorful Excel Slip",
                data=excel_data,
                file_name=f"{res['name']}_Salary_Slip_{res['month']}_{res['year']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.session_state['calc_result'] = None

# ==========================================
# 10. Attendance Sheet & Summary Section
# ==========================================
st.divider()

if not formatted_name:
    st.info("👆 Please enter a name in the sidebar or above to view or add attendance data.")
else:
    all_sheets_raw = get_all_sheet_names()
    if current_month_str not in all_sheets_raw:
        all_sheets_raw.insert(0, current_month_str)
    
    available_sheets = ["All Months"] + all_sheets_raw

    if selected_sheet := st.session_state.get('filter_month', current_month_str):
        pass
    selected_sheet = st.session_state.filter_month

    if selected_sheet == "All Months":
        df_list = []
        for sht in get_all_sheet_names():
            df_temp = load_attendance_data(sht)
            if not df_temp.empty:
                df_temp["_Original_Sheet"] = sht
                df_temp["_Original_Index"] = df_temp.index
                df_list.append(df_temp)
        if df_list:
            df_display = pd.concat(df_list, ignore_index=True)
        else:
            df_display = pd.DataFrame()
    else:
        df_display = load_attendance_data(selected_sheet)
        if not df_display.empty:
            df_display["_Original_Sheet"] = selected_sheet
            df_display["_Original_Index"] = df_display.index

    if not df_display.empty:
        df_display["RealDate"] = pd.to_datetime(df_display["Date"], format="%d/%m/%Y")
        df_display = df_display.sort_values(by=["Employee Name", "RealDate"]).drop(columns=["RealDate"])
        df_display = df_display.reset_index(drop=True)
        df_display = df_display.fillna("")

        if formatted_name != "Admin":
            df_display = df_display[df_display["Employee Name"] == formatted_name]

    if df_display.empty:
        st.warning(f"No attendance records found for '{formatted_name}' in {selected_sheet}.")
    else:
        # --- CALCULATE TOTALS FOR SUMMARY ---
        total_reg_mins = 0
        for val in df_display["Total Hours"]:
            if pd.notna(val) and ":" in str(val):
                h, m = map(int, str(val).split(":"))
                total_reg_mins += h * 60 + m
        reg_hours, reg_mins = divmod(total_reg_mins, 60)
        
        total_ot_mins_sum = 0
        for val in df_display["OT Hours"]:
            if pd.notna(val) and ":" in str(val):
                h, m = map(int, str(val).split(":"))
                total_ot_mins_sum += h * 60 + m
        ot_hours, ot_mins = divmod(total_ot_mins_sum, 60)

        total_late_mins_sum = 0
        for val in df_display["Late Hours"]:
            if pd.notna(val) and ":" in str(val):
                h, m = map(int, str(val).split(":"))
                total_late_mins_sum += h * 60 + m
        late_hours, late_mins = divmod(total_late_mins_sum, 60)

        total_out_mins_sum = 0
        for val in df_display["Out Hours"]:
            if pd.notna(val) and ":" in str(val):
                h, m = map(int, str(val).split(":"))
                total_out_mins_sum += h * 60 + m
        out_hours, out_mins = divmod(total_out_mins_sum, 60)

        # --- DISPLAY SUMMARY INSIDE PROPER CONTAINER ---
        st.subheader("📊 Attendance Summary")
        
        container = st.container(border=True)
        with container:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric(label="🕒 Total Regular Hours", value=f"{reg_hours:02d}:{reg_mins:02d}")
            with m2:
                st.metric(label="🔥 Total Overtime Hours", value=f"{ot_hours:02d}:{ot_mins:02d}")
            with m3:
                st.metric(label="⚠️ Total Late Hours", value=f"{late_hours:02d}:{late_mins:02d}")
            with m4:
                st.metric(label="🚪 Total Early Hours", value=f"{out_hours:02d}:{out_mins:02d}")

        st.divider()
        st.subheader("📋 Attendance Sheet")

        # --- COMPACT WIDTH MONTH FILTER & DOWNLOAD SECTION ---
        col_s1, col_s2, col_s3 = st.columns([1, 1, 2])
        with col_s1:
            st.selectbox("Select Month to View", available_sheets, key="filter_month")
            selected_sheet = st.session_state.filter_month

        with col_s2:
            st.write("")
            st.write("")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_export = df_display.drop(columns=["_Original_Sheet", "_Original_Index"], errors='ignore')
                export_sheet_name = selected_sheet if selected_sheet != "All Months" else "All_Months"
                df_export.to_excel(writer, index=False, sheet_name=export_sheet_name)
                
            excel_data = buffer.getvalue()
            file_name_export = f"Attendance_{export_sheet_name}_{formatted_name}.xlsx".replace(" ", "_")
            
            st.download_button(
                label="⬇️ Download Data (Excel)",
                data=excel_data,
                file_name=file_name_export,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True 
            )

        def highlight_rows(row):
            colors = [''] * len(row)
            if row['Day'] == 'Sun':
                colors = ['background-color: #ff7f7f; color: white'] * len(row)
            if st.session_state.last_edited == f"{row['Employee Name']}_{row['Date']}":
                colors = ['background-color: #ffffcc; color: black; font-weight: bold'] * len(row)
            return colors
        
        st.markdown("💡 **Tip:** Select the checkbox on the left side of the table to Edit or Delete.")

        event = st.dataframe(
            df_display.style.apply(highlight_rows, axis=1), 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",           
            selection_mode="multi-row",  
            column_config={
                "_Original_Sheet": None,
                "_Original_Index": None   
            }
        )
        
        selected_rows = event.selection.rows
        if len(selected_rows) > 0:
            st.markdown("---")
            
            if len(selected_rows) > 1:
                st.warning(f"⚠️ You have selected {len(selected_rows)} entries. Multiple entries can only be deleted, not edited.")
                if st.button("🗑️ Delete Selected Entries", type="primary"):
                    to_delete = {}
                    for row_idx in selected_rows:
                        sht = df_display.iloc[row_idx]["_Original_Sheet"]
                        idx = df_display.iloc[row_idx]["_Original_Index"]
                        if sht not in to_delete:
                            to_delete[sht] = []
                        to_delete[sht].append(idx)

                    for sht, indices in to_delete.items():
                        df_orig = load_attendance_data(sht)
                        df_orig = df_orig.drop(indices) 
                        save_attendance_data(df_orig, sht)
                    
                    st.session_state.last_edited = None
                    st.success("✅ Entries permanently deleted!")
                    st.rerun()
            else:
                selected_idx = df_display.iloc[selected_rows[0]]["_Original_Index"]
                selected_sheet_orig = df_display.iloc[selected_rows[0]]["_Original_Sheet"]
                row_data = df_display.iloc[selected_rows[0]]
                
                col_edit, col_delete = st.columns([3, 1])
                
                with col_edit:
                    st.subheader("✏️ Edit Selected Entry")
                    with st.form("edit_form"):
                        e_name = st.text_input("Employee Name", value=row_data["Employee Name"])
                        ce1, ce2, ce3 = st.columns(3)
                        with ce1:
                            d_obj = datetime.strptime(row_data["Date"], "%d/%m/%Y").date()
                            e_date = st.date_input("Date", value=d_obj, key="e_date", format="DD/MM/YYYY")
                        with ce2:
                            in_obj = datetime.strptime(row_data["In Time"], "%H:%M").time()
                            e_in = st.time_input("In Time", value=in_obj, key="e_in")
                        with ce3:
                            out_obj = datetime.strptime(row_data["Out Time"], "%H:%M").time()
                            e_out = st.time_input("Out Time", value=out_obj, key="e_out")
                            
                        if st.form_submit_button("Update Entry", type="secondary"):
                            formatted_e_name = e_name.strip().title()
                            date_str_e = e_date.strftime("%d/%m/%Y")
                            new_sheet = get_sheet_name(e_date)
                            
                            df_orig = load_attendance_data(selected_sheet_orig)
                            
                            if new_sheet == selected_sheet_orig:
                                temp_check = df_orig.drop(selected_idx)
                                is_dup = not temp_check[(temp_check["Employee Name"] == formatted_e_name) & (temp_check["Date"] == date_str_e)].empty
                            else:
                                df_new = load_attendance_data(new_sheet)
                                is_dup = not df_new[(df_new["Employee Name"] == formatted_e_name) & (df_new["Date"] == date_str_e)].empty

                            if is_dup:
                                st.error("⚠️ An entry for this employee on this date already exists!")
                            else:
                                day_str_e = e_date.strftime("%a")
                                t_hrs, l_hrs, o_hrs, ot_hrs = calculate_times(e_in, e_out, day_str_e)
                                
                                updated_row = pd.DataFrame({
                                    "Employee Name": [formatted_e_name],
                                    "Date": [date_str_e],
                                    "Day": [day_str_e],
                                    "In Time": [e_in.strftime("%H:%M")],
                                    "Out Time": [e_out.strftime("%H:%M")],
                                    "Late Hours": [l_hrs],
                                    "Out Hours": [o_hrs],
                                    "Total Hours": [t_hrs],
                                    "OT Hours": [ot_hrs]
                                })
                                
                                if new_sheet == selected_sheet_orig:
                                    updated_row.index = [selected_idx]
                                    df_orig.update(updated_row)
                                    save_attendance_data(df_orig, selected_sheet_orig)
                                else:
                                    df_orig = df_orig.drop(selected_idx)
                                    save_attendance_data(df_orig, selected_sheet_orig)
                                    df_new = pd.concat([df_new, updated_row], ignore_index=True)
                                    save_attendance_data(df_new, new_sheet)
                                
                                st.session_state.last_edited = f"{formatted_e_name}_{date_str_e}"
                                st.success("✅ Entry updated successfully!")
                                st.rerun()

                with col_delete:
                    st.subheader("🗑️ Delete")
                    st.write("Click below to permanently delete this entry:")
                    if st.button("Delete This Entry", type="primary"):
                        df_orig = load_attendance_data(selected_sheet_orig)
                        df_orig = df_orig.drop(selected_idx) 
                        save_attendance_data(df_orig, selected_sheet_orig)
                        
                        st.session_state.last_edited = None
                        st.success("✅ Entry permanently deleted!")
                        st.rerun()

# ==========================================
# 11. Search Records & History Section
# ==========================================
st.divider()
st.subheader("🔍 Search Salary Records")
with st.container(border=True):
    s1, s2, s3, s4 = st.columns([4, 1.5, 1.5, 1.5])
    search_n = s1.text_input("🔍 Search Name", placeholder="Name...", label_visibility="collapsed", key="sn")
    search_m = s2.selectbox("📅 Month", list(month_dict.keys()), key="sm", label_visibility="collapsed")
    search_y = s3.number_input("🗓️ Year", value=current_year, key="sy", label_visibility="collapsed")
    
    if s4.button("🔍 Search", use_container_width=True):
        s_file = get_user_file(search_n)
        if s_file and os.path.exists(s_file):
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

if emp_sidebar_name:
    st.divider()
    user_csv_file = get_user_file(emp_sidebar_name)
    if user_csv_file and os.path.exists(user_csv_file):
        st.subheader(f"📂 Salary History: {emp_sidebar_name}")
        h_df = pd.read_csv(user_csv_file).fillna(0)
        h_df = clean_legacy_columns(h_df)

        if 'Month' in h_df.columns:
            h_df['Sort_M'] = h_df['Month'].astype(str).str.strip().map(month_dict)
            if 'Year' in h_df.columns:
                h_df = h_df.sort_values(['Year', 'Sort_M']).drop(columns=['Sort_M']).reset_index(drop=True)
            else:
                h_df = h_df.sort_values('Sort_M').drop(columns=['Sort_M']).reset_index(drop=True)

        edited_df = st.data_editor(
            h_df, 
            use_container_width=True, 
            num_rows="dynamic",
            key=f"editor_{emp_sidebar_name.lower().replace(' ', '_')}",
            column_config=table_format_config
        )
        
        if not h_df.equals(edited_df):
            edited_df.to_csv(user_csv_file, index=False)
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
                    
                    p_hrs_val = float(row.get("Present Hrs", 0))
                    p_hrs = int(p_hrs_val)
                    p_mins = int(round((p_hrs_val - p_hrs) * 100))
                    
                    ot_m = int(row.get("OT Mins", 0))
                    late_m = int(row.get("Late Mins", 0))
                    early_m = int(row.get("Early Mins", 0))
                    
                    fh = str(row.get("Final Present Hrs", "0h 0m"))
                    try:
                        h, m = fh.replace('m','').split('h ')
                        pay_str = f"{int(h)}:{int(m):02d}"
                    except:
                        pay_str = "0:00"
                        
                    actual_salary_hist = row.get("CTC", 0) - row.get("Bonus", 0) - row.get("Gratuity", 0)
                    
                    net_sal_hist = float(row.get("Net Salary", 0))
                    diff_hist = float(row.get("Difference", 0))
                    
                    hist_slip_data = {
                        "work_hrs_str": f"{int(row.get('Working Hrs', 0))}:00",
                        "ctc": row.get("CTC", 0),
                        "bonus": row.get("Bonus", 0),
                        "gratuity": row.get("Gratuity", 0),
                        "actual_salary": actual_salary_hist,
                        "present_hrs": f"{p_hrs}:{p_mins:02d}",
                        "pl_used": row.get("PL Used", 0),
                        "pl_balance": row.get("PL Balance", 0),
                        "ot_hrs": f"{ot_m//60}:{ot_m%60:02d}",
                        "late_hrs": f"{late_m//60}:{late_m%60:02d}",
                        "out_hrs": f"{early_m//60}:{early_m%60:02d}",
                        "pay_hrs": pay_str,
                        "pt": row.get("PT", 0),
                        "tds": row.get("TDS", 0),
                        "esic": row.get("ESIC", 0),
                        "advance": row.get("Advance", 0),
                        "food": row.get("Food", 0),
                        "difference": diff_hist,
                        "pay_salary_val": round(net_sal_hist - diff_hist),
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
        st.info("No salary data saved for this employee yet. (Calculate & Save Salary Data to add new record)")
