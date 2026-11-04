import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
import io
from openpyxl.styles import Alignment, PatternFill, Border, Side, Font
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------
st.set_page_config(page_title="Advanced Attendance Tracker", layout="wide", page_icon="📅")
# ---------------------------------------------------------

# ==========================================
# 1. SETTINGS & CONSTANTS
# ==========================================
FIREBASE_URL = "https://attendence-ec921-default-rtdb.firebaseio.com"
ADMIN_PASSWORD = "1234"  

STANDARD_IN = "08:00"
STANDARD_OUT = "18:00"

def get_sheet_name(selected_date):
    return selected_date.strftime("%b'%Y")

@st.cache_data
def get_all_sheet_names():
    url = f"{FIREBASE_URL}.json?shallow=true"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, dict):
                return [k for k in data.keys() if k not in ["holidays_list", "employee_list"]]
    except Exception:
        pass
    
    fallback_sheets = []
    d = date.today()
    for _ in range(12):
        fallback_sheets.append(d.strftime("%b'%Y"))
        if d.month == 1:
            d = d.replace(year=d.year - 1, month=12)
        else:
            d = d.replace(month=d.month - 1)
    return fallback_sheets

@st.cache_data
def get_all_employees():
    emps = set()
    try:
        res = requests.get(f"{FIREBASE_URL}/employee_list.json", timeout=10)
        if res.status_code == 200 and res.json():
            data = res.json()
            if isinstance(data, list):
                for r in data:
                    if r: emps.add(str(r).strip().title())
            elif isinstance(data, dict):
                for k, v in data.items():
                    if v: emps.add(str(v).strip().title())
    except Exception:
        pass
        
    valid_emps = sorted(list([e for e in emps if e != "-"]))
    return valid_emps

def load_registered_employees():
    try:
        res = requests.get(f"{FIREBASE_URL}/employee_list.json", timeout=10)
        if res.status_code == 200 and res.json():
            data = res.json()
            if isinstance(data, dict):
                return list(data.values())
            elif isinstance(data, list):
                return [x for x in data if x is not None]
    except Exception:
        pass
    return []

def save_registered_employees(emp_list):
    try:
        requests.put(f"{FIREBASE_URL}/employee_list.json", json=emp_list, timeout=10)
        get_all_employees.clear()
    except Exception:
        pass

@st.cache_data
def load_holidays_data():
    try:
        res = requests.get(f"{FIREBASE_URL}/holidays_list.json", timeout=10)
        if res.status_code == 200 and res.json():
            return res.json()
    except Exception:
        pass
    return {}

def save_holidays_data(data):
    try:
        requests.put(f"{FIREBASE_URL}/holidays_list.json", json=data, timeout=10)
        load_holidays_data.clear() 
        if 'cached_holidays' in st.session_state:
            del st.session_state.cached_holidays
    except Exception:
        pass

def get_flat_holiday_dates():
    hol_data = load_holidays_data()
    flat_dict = {}
    for hid, hinfo in hol_data.items():
        try:
            f_date = datetime.strptime(hinfo['from'], "%d/%m/%Y").date()
            t_date = datetime.strptime(hinfo['to'], "%d/%m/%Y").date()
            delta = (t_date - f_date).days
            for i in range(delta + 1):
                d = f_date + timedelta(days=i)
                flat_dict[d.strftime("%d/%m/%Y")] = hinfo['reason']
        except:
            pass
    return flat_dict

def parse_time(time_val):
    time_str = str(time_val).strip()
    try:
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        try:
            return datetime.strptime(time_str, "%H:%M:%S")
        except ValueError:
            return datetime.strptime("00:00", "%H:%M")

def check_time_overlap(curr_in_str, curr_out_str, new_in_str, new_out_str):
    if not curr_in_str or curr_in_str == "00:00": return False
    
    existing_ins = [parse_time(t) for t in str(curr_in_str).split(',') if t.strip()]
    existing_outs = [parse_time(t) for t in str(curr_out_str).split(',') if t.strip()]
    
    new_in = parse_time(new_in_str)
    new_out = parse_time(new_out_str)
    
    for ein, eout in zip(existing_ins, existing_outs):
        if max(new_in, ein) < min(new_out, eout):
            return True
        if new_in == ein or new_out == eout:
            return True
            
    return False

def calculate_times(in_time_str, out_time_str, day_str, status="Regular", is_public_holiday=False):
    if status in ["PL", "LWP", "Absent"]:
        return "00:00", "00:00", "00:00", "00:00"

    in_times = [parse_time(t) for t in str(in_time_str).split(',') if t.strip()]
    out_times = [parse_time(t) for t in str(out_time_str).split(',') if t.strip()]
    
    if not in_times or not out_times:
        return "00:00", "00:00", "00:00", "00:00"

    min_len = min(len(in_times), len(out_times))
    in_times = in_times[:min_len]
    out_times = out_times[:min_len]

    std_in = datetime.strptime(STANDARD_IN, "%H:%M")
    std_out = datetime.strptime(STANDARD_OUT, "%H:%M")
    
    total_worked_mins = 0
    reg_mins = 0

    for t1, t2 in zip(in_times, out_times):
        if t2 > t1:
            pair_worked_mins = (t2 - t1).seconds // 60
            total_worked_mins += pair_worked_mins

            if not (day_str == "Sun" or status == "Holiday" or is_public_holiday):
                actual_start = max(t1, std_in)
                actual_end = min(t2, std_out)
                if actual_end > actual_start:
                    reg_mins += (actual_end - actual_start).seconds // 60

    if day_str == "Sun" or status == "Holiday" or is_public_holiday:
        ot_mins = total_worked_mins
        reg_mins = 0
        late_mins = 0
        out_early_mins = 0
    else:
        ot_mins = total_worked_mins - reg_mins
        if ot_mins < 30:
            ot_mins = 0
            
        first_in = min(in_times) if in_times else std_in
        last_out = max(out_times) if out_times else std_out

        late_mins = max(0, (first_in - std_in).total_seconds() // 60) if first_in > std_in else 0
        out_early_mins = max(0, (std_out - last_out).total_seconds() // 60) if last_out < std_out else 0

    def mins_to_str(m):
        if m <= 0: return "00:00"
        h, m = divmod(int(m), 60)
        return f"{h:02d}:{m:02d}"
        
    return mins_to_str(reg_mins), mins_to_str(late_mins), mins_to_str(out_early_mins), mins_to_str(ot_mins)

@st.cache_data
def load_data(sheet_name):
    columns = ["Employee Name", "Date", "Day", "In Time", "Out Time", "Late Hours", "Out Hours", "Total Hours", "OT Hours", "Status"]
    url = f"{FIREBASE_URL}/{sheet_name}.json"
    holidays_dict = get_flat_holiday_dates()
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data:
            if isinstance(data, dict):
                df = pd.DataFrame(list(data.values()))
            else:
                df = pd.DataFrame([row for row in data if row is not None])
            
            for col in columns:
                if col not in df.columns:
                    df[col] = ""
                    if col == "Status": df[col] = "Regular"
                    if col in ["Late Hours", "Out Hours", "Total Hours", "OT Hours"]: df[col] = "00:00"
                    if col in ["In Time"]: df[col] = "08:00"
                    if col in ["Out Time"]: df[col] = "18:00"
                    
            for idx, row in df.iterrows():
                in_t = str(row.get("In Time", "08:00"))
                out_t = str(row.get("Out Time", "18:00"))
                day_s = str(row.get("Day", "Mon"))
                status = str(row.get("Status", "Regular"))
                date_s = str(row.get("Date", ""))
                
                is_pub_hol = date_s in holidays_dict
                
                if pd.isna(row.get("In Time")) or in_t.lower() == 'nan':
                    continue
                    
                try:
                    tot, late, out_e, ot = calculate_times(in_t, out_t, day_s, status, is_pub_hol)
                    df.at[idx, "Total Hours"] = tot
                    df.at[idx, "Late Hours"] = late
                    df.at[idx, "Out Hours"] = out_e
                    df.at[idx, "OT Hours"] = ot
                except Exception:
                    pass
            
            return df[columns]
        else:
            return pd.DataFrame(columns=columns)
    except Exception:
        return pd.DataFrame(columns=columns)

def save_data(df, sheet_name):
    df_clean = df.fillna("")
    url = f"{FIREBASE_URL}/{sheet_name}.json"
    data = df_clean.to_dict(orient='records')
    try:
        requests.put(url, json=data, timeout=10)
        load_data.clear(sheet_name) 
        if 'cached_data' in st.session_state and sheet_name in st.session_state.cached_data:
            del st.session_state.cached_data[sheet_name]
    except Exception:
        pass

def time_to_float(time_str):
    if not time_str or pd.isna(time_str) or str(time_str).strip() == "": return 0.0
    try:
        parts = str(time_str).split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h + (m / 60.0)
    except:
        return 0.0

current_month_str = get_sheet_name(date.today())

# Variables Initialization
if 'last_edited' not in st.session_state: st.session_state.last_edited = None
if 'filter_month_dash' not in st.session_state: st.session_state.filter_month_dash = current_month_str 
if 'top_emp_selectbox' not in st.session_state: st.session_state.top_emp_selectbox = "-- Select Employee --"
if 'form_reset_counter' not in st.session_state: st.session_state.form_reset_counter = 0
if 'flash_msg' not in st.session_state: st.session_state.flash_msg = ""
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'cached_data' not in st.session_state: st.session_state.cached_data = {}
if 'cached_holidays' not in st.session_state: st.session_state.cached_holidays = None

# Tab 4 Actions
if 'edit_row' not in st.session_state: st.session_state.edit_row = None
if 'del_row' not in st.session_state: st.session_state.del_row = None

# Tab 5 Actions
if 'edit_emp' not in st.session_state: st.session_state.edit_emp = None
if 'del_emp' not in st.session_state: st.session_state.del_emp = None

def on_top_name_change():
    val = st.session_state.top_emp_selectbox
    if val and val != "-- Select Employee --":
        st.session_state.filter_month_dash = current_month_str 
    else:
        st.session_state.filter_month_dash = current_month_str

st.markdown("""
    <style>
        @keyframes instantHide {
            to {
                opacity: 0;
                max-height: 0;
                padding: 0;
                margin: 0;
                border: none;
                overflow: hidden;
            }
        }
        
        .auto-hide-success {
            background-color: rgba(29, 169, 85, 0.2);
            border: 1px solid rgba(29, 169, 85, 0.5);
            color: rgb(184, 241, 198);
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 1rem;
            animation: instantHide 0s 5s forwards; 
        }
        
        .auto-hide-error {
            background-color: rgba(255, 43, 43, 0.2);
            border: 1px solid rgba(255, 43, 43, 0.5);
            color: rgb(255, 189, 189);
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 1rem;
            animation: instantHide 0s 5s forwards;
        }
        
        div[data-baseweb="input"], div[data-testid="stDateInput"], div[data-testid="stTimeInput"] { max-width: 320px; }
        .stDownloadButton button { margin-top: 27px; }
        [data-testid="stMetric"] { background-color: #1e2530; padding: 15px; border-radius: 12px; border: 1px solid #303d4f; }
        div[data-testid="InputInstructions"] { display: none !important; }
        
        div[data-testid="stTabs"] button[role="tab"] p {
            font-size: 28px !important;
            font-weight: 900 !important;
        }
        .stTabs button[data-baseweb="tab"] div[data-testid="stMarkdownContainer"] p {
            font-size: 28px !important;
            font-weight: 900 !important;
        }
        div[data-testid="stTabs"] button[role="tab"] {
            padding-top: 15px !important;
            padding-bottom: 15px !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📅 Advanced Attendance Tracker")

if st.session_state.flash_msg:
    st.markdown(f'<div class="auto-hide-success">{st.session_state.flash_msg}</div>', unsafe_allow_html=True)
    st.session_state.flash_msg = "" 

raw_emp_name = st.session_state.top_emp_selectbox
if raw_emp_name == "-- Select Employee --":
    formatted_name = ""
else:
    formatted_name = raw_emp_name.strip().title()

if formatted_name != "Administrator":
    st.session_state.admin_auth = False

is_admin_unlocked = (formatted_name == "Administrator" and st.session_state.admin_auth)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Add Attendance", "👥 Daily Roster", "🌴 Holiday Calendar", "📊 Dashboard & History", "👤 Manage Employees"])

with tab1:
    entry_mode = st.radio("Choose Entry Method:", ["✏️ Manual Entry", "📂 Bulk Upload (Excel/CSV)"], horizontal=True)
    st.divider()

    if entry_mode == "✏️ Manual Entry":
        col_input1, col_input2 = st.columns([1.5, 2.5])
        
        all_emps_list = get_all_employees()
        dropdown_options = ["-- Select Employee --", "Administrator"] + all_emps_list
        
        with col_input1:
            st.selectbox("Select Employee", options=dropdown_options, key="top_emp_selectbox", on_change=on_top_name_change)

        if formatted_name == "Administrator":
            with col_input2:
                if not st.session_state.admin_auth:
                    ap1, ap2 = st.columns([1.5, 1])
                    with ap1:
                        admin_pwd = st.text_input("🔑 Enter Admin Password", type="password", key="pwd_input")
                    with ap2:
                        st.write("")
                        st.write("")
                        if st.button("Unlock Admin", type="primary"):
                            if admin_pwd == ADMIN_PASSWORD:
                                st.session_state.admin_auth = True
                                st.rerun()
                            else:
                                st.markdown('<div class="auto-hide-error" style="margin-top: 28px;">❌ Incorrect Password!</div>', unsafe_allow_html=True)
                else:
                    ap1, ap2 = st.columns([1.5, 1])
                    with ap1:
                        st.markdown('<div class="auto-hide-success" style="margin-top: 28px;">✅ Admin Access Granted</div>', unsafe_allow_html=True)
                    with ap2:
                        st.write("")
                        st.write("")
                        if st.button("Lock 🔒"):
                            st.session_state.admin_auth = False
                            st.rerun()

        default_date = date.today()
        default_in = time(8, 0)
        default_out = time(18, 0)
        
        if formatted_name and formatted_name != "Administrator":
            if st.session_state.filter_month_dash not in st.session_state.cached_data:
                st.session_state.cached_data[st.session_state.filter_month_dash] = load_data(st.session_state.filter_month_dash)
            df_month_check = st.session_state.cached_data[st.session_state.filter_month_dash]

            if not df_month_check.empty:
                 df_emp = df_month_check[df_month_check["Employee Name"].astype(str).str.strip().str.lower() == formatted_name.lower()]
                 if not df_emp.empty:
                      df_emp = df_emp.copy()
                      df_emp["RealDate"] = pd.to_datetime(df_emp["Date"], format="%d/%m/%Y")
                      latest_date_row = df_emp.loc[df_emp['RealDate'].idxmax()]
                      latest_date = latest_date_row['RealDate'].date()
                      
                      today_entry = df_emp[df_emp['RealDate'].dt.date == date.today()]
                      if not today_entry.empty:
                          default_date = date.today()
                          now = datetime.now()
                          default_in = now.time()
                          default_out = time(18, 0) 
                      else:
                          default_date = latest_date + timedelta(days=1)

        with st.form("entry_form"):
            c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.2, 1.2, 1.5])
            with c1:
                entry_date = st.date_input("Date", value=default_date, format="DD/MM/YYYY")
            with c2:
                entry_status = st.selectbox("Status", ["Regular", "Holiday", "PL", "LWP", "Absent"])
            with c3:
                in_time = st.time_input("In Time", value=default_in, key=f"in_{st.session_state.form_reset_counter}")
            with c4:
                out_time = st.time_input("Out Time", value=default_out, key=f"out_{st.session_state.form_reset_counter}")
                
            with c5:
                st.write("")
                st.write("")
                submit = st.form_submit_button("Save Entry", type="primary", use_container_width=True)

        if submit:
            if not formatted_name:
                st.error("Please select an Employee Name from the dropdown above!")
            elif formatted_name == "Administrator":
                st.error("You cannot add an entry for 'Administrator'. Please select a valid employee!")
            elif out_time < in_time and entry_status not in ["PL", "LWP", "Absent"]:
                st.error("Out Time cannot be before In Time for a single shift!")
            else:
                target_sheet = get_sheet_name(entry_date)
                df_month = load_data(target_sheet).copy() 
                day_str = entry_date.strftime("%a")
                date_str = entry_date.strftime("%d/%m/%Y")
                
                existing_match = df_month[(df_month["Employee Name"].astype(str).str.strip().str.lower() == formatted_name.lower()) & (df_month["Date"] == date_str)]
                holidays_dict = get_flat_holiday_dates()
                is_pub_hol = date_str in holidays_dict
                
                if entry_status in ["PL", "LWP", "Absent"]:
                    in_t_str, out_t_str = "00:00", "00:00"
                else:
                    in_t_str, out_t_str = in_time.strftime("%H:%M"), out_time.strftime("%H:%M")
                
                is_overlapping = False
                
                if not existing_match.empty:
                    idx = existing_match.index[0]
                    if entry_status not in ["PL", "LWP", "Absent"]:
                        curr_in = str(df_month.at[idx, "In Time"])
                        curr_out = str(df_month.at[idx, "Out Time"])
                        
                        if check_time_overlap(curr_in, curr_out, in_t_str, out_t_str):
                            st.error(f"⚠️ Overlap Error: Tame nakhelo time ({in_t_str} thi {out_t_str}) phelathi j add karel time sathe overlap thay che!")
                            is_overlapping = True
                        else:
                            if curr_in and curr_in != "00:00":
                                in_t_str = curr_in + ", " + in_t_str
                            if curr_out and curr_out != "00:00":
                                out_t_str = curr_out + ", " + out_t_str
                
                if not is_overlapping:
                    if not existing_match.empty:
                        tot, late, out_e, ot = calculate_times(in_t_str, out_t_str, day_str, entry_status, is_pub_hol)
                        
                        df_month.at[idx, "In Time"] = in_t_str
                        df_month.at[idx, "Out Time"] = out_t_str
                        df_month.at[idx, "Total Hours"] = tot
                        df_month.at[idx, "Late Hours"] = late
                        df_month.at[idx, "Out Hours"] = out_e
                        df_month.at[idx, "OT Hours"] = ot
                        df_month.at[idx, "Status"] = entry_status
                        
                        save_data(df_month, target_sheet)
                        st.session_state.flash_msg = f"✅ Additional punch added for {formatted_name} on {date_str}!"
                    else:
                        tot, late, out_e, ot = calculate_times(in_t_str, out_t_str, day_str, entry_status, is_pub_hol)
                        new_entry = pd.DataFrame({
                            "Employee Name": [formatted_name],
                            "Date": [date_str],
                            "Day": [day_str],
                            "In Time": [in_t_str],
                            "Out Time": [out_t_str],
                            "Late Hours": [late], 
                            "Out Hours": [out_e],
                            "Total Hours": [tot],
                            "OT Hours": [ot],
                            "Status": [entry_status]
                        })
                        df_month = pd.concat([df_month, new_entry], ignore_index=True)
                        save_data(df_month, target_sheet) 
                        st.session_state.flash_msg = f"✅ Record for {formatted_name} on {date_str} saved successfully!"
                    
                    st.session_state.filter_month_dash = target_sheet
                    st.session_state.last_edited = f"{formatted_name}_{date_str}"
                    st.session_state.form_reset_counter += 1
                    st.rerun()

    elif entry_mode == "📂 Bulk Upload (Excel/CSV)":
        st.subheader("📂 Upload Monthly Excel/CSV")
        st.markdown("""
        **Instructions:**
        1. File must have columns: `Employee Name`, `Date` (DD/MM/YYYY), `In Time` (HH:MM), `Out Time` (HH:MM), `Status` (Optional).
        2. Overlap Protection is Active: Duplicates or overlapping times will be automatically skipped!
        """)
        
        template_df = pd.DataFrame({
            "Employee Name": ["Manoj Kumar", "Ramesh Patel", "Suresh Desai"],
            "Date": ["01/11/2026", "02/11/2026", "03/11/2026"],
            "In Time": ["08:00", "09:15", ""],
            "Out Time": ["18:00", "18:00", ""],
            "Status": ["Regular", "Holiday", "PL"]
        })
        csv_template = template_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Download CSV Template",
            data=csv_template,
            file_name="Attendance_Template.csv",
            mime="text/csv",
        )
        st.write("")

        uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_upload = pd.read_csv(uploaded_file)
                else:
                    df_upload = pd.read_excel(uploaded_file)
                    
                required_cols = ["Employee Name", "Date", "In Time", "Out Time"]
                if not all(c in df_upload.columns for c in required_cols):
                    st.error(f"Missing required columns! Required: {required_cols}")
                else:
                    st.write("Preview of Uploaded Data:")
                    st.dataframe(df_upload.head(3), use_container_width=True)
                    
                    if st.button("🚀 Process & Upload Bulk Data", type="primary"):
                        success_count = 0
                        grouped = df_upload.groupby('Date')
                        holidays_dict = get_flat_holiday_dates()
                        
                        master_emps = get_all_employees()
                        
                        for date_val, group in grouped:
                            try:
                                d_obj = pd.to_datetime(date_val, format='%d/%m/%Y', errors='coerce').date()
                                if pd.isna(d_obj): continue
                                
                                sheet_n = get_sheet_name(d_obj)
                                day_s = d_obj.strftime("%a")
                                date_s = d_obj.strftime("%d/%m/%Y")
                                is_pub_hol = date_s in holidays_dict
                                
                                df_db = load_data(sheet_n).copy()
                                new_rows = []
                                
                                for _, r in group.iterrows():
                                    ename = str(r['Employee Name']).strip().title()
                                    
                                    if ename not in master_emps:
                                        continue
                                        
                                    stat = str(r.get('Status', 'Regular')) if pd.notna(r.get('Status')) else 'Regular'
                                    if stat not in ["Regular", "Holiday", "PL", "LWP", "Absent"]: stat = "Regular"
                                        
                                    in_val = str(r['In Time']).strip() if pd.notna(r['In Time']) else "08:00"
                                    out_val = str(r['Out Time']).strip() if pd.notna(r['Out Time']) else "18:00"
                                    
                                    existing_match = df_db[(df_db["Employee Name"].str.lower() == ename.lower()) & (df_db["Date"] == date_s)]
                                    
                                    if not existing_match.empty:
                                        idx = existing_match.index[0]
                                        if stat not in ["PL", "LWP", "Absent"]:
                                            curr_in = str(df_db.at[idx, "In Time"])
                                            curr_out = str(df_db.at[idx, "Out Time"])
                                            
                                            if check_time_overlap(curr_in, curr_out, in_val, out_val):
                                                continue 
                                                
                                            if in_val != "00:00" and curr_in != "00:00":
                                                in_val = curr_in + ", " + in_val
                                            if out_val != "00:00" and curr_out != "00:00":
                                                out_val = curr_out + ", " + out_val
                                        
                                        tot, late, out_e, ot = calculate_times(in_val, out_val, day_s, stat, is_pub_hol)
                                        df_db.at[idx, "In Time"] = in_val
                                        df_db.at[idx, "Out Time"] = out_val
                                        df_db.at[idx, "Total Hours"] = tot
                                        df_db.at[idx, "Late Hours"] = late
                                        df_db.at[idx, "Out Hours"] = out_e
                                        df_db.at[idx, "OT Hours"] = ot
                                        df_db.at[idx, "Status"] = stat
                                        success_count += 1
                                        continue
                                        
                                    tot, late, out_e, ot = calculate_times(in_val, out_val, day_s, stat, is_pub_hol)
                                    new_rows.append({
                                        "Employee Name": ename, "Date": date_s, "Day": day_s,
                                        "In Time": in_val, "Out Time": out_val, "Late Hours": late, "Out Hours": out_e,
                                        "Total Hours": tot, "OT Hours": ot, "Status": stat
                                    })
                                    success_count += 1
                                    
                                if new_rows:
                                    df_db = pd.concat([df_db, pd.DataFrame(new_rows)], ignore_index=True)
                                save_data(df_db, sheet_n)
                                    
                            except Exception:
                                pass
                                
                        st.session_state.flash_msg = f"✅ Successfully processed {success_count} valid records!"
                        st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

with tab2:
    st.subheader("👥 Daily Roster (Mark all employees for a day)")
    roster_date = st.date_input("Select Date for Roster", value=date.today(), format="DD/MM/YYYY", key="roster_date")
    
    all_emp_list = get_all_employees()
    if not all_emp_list:
        st.info("No employees found in the database. Please add them in 'Manage Employees' first.")
    else:
        r_sheet = get_sheet_name(roster_date)
        if r_sheet not in st.session_state.cached_data:
            st.session_state.cached_data[r_sheet] = load_data(r_sheet)
        df_r_month = st.session_state.cached_data[r_sheet].copy()
        r_date_str = roster_date.strftime("%d/%m/%Y")
        r_day_str = roster_date.strftime("%a")
        
        existing_emps_on_date = df_r_month[df_r_month["Date"] == r_date_str]["Employee Name"].tolist() if not df_r_month.empty else []
        pending_emps = [e for e in all_emp_list if e not in existing_emps_on_date]
        
        if not pending_emps:
            st.markdown(f'<div class="auto-hide-success">✅ All employees are already marked for {r_date_str}.</div>', unsafe_allow_html=True)
        else:
            roster_df = pd.DataFrame({
                "Employee Name": pending_emps,
                "Status": ["Regular"] * len(pending_emps),
                "In Time": ["08:00"] * len(pending_emps),
                "Out Time": ["18:00"] * len(pending_emps)
            })
            
            edited_roster = st.data_editor(
                roster_df,
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=["Regular", "Holiday", "PL", "LWP", "Absent"], required=True)
                },
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic"
            )
            
            if st.button("💾 Save Full Roster", type="primary"):
                new_records = []
                holidays_dict = get_flat_holiday_dates()
                is_pub_hol = r_date_str in holidays_dict
                
                for _, row in edited_roster.iterrows():
                    emp_n = row["Employee Name"]
                    stat = row["Status"]
                    
                    if stat in ["PL", "LWP", "Absent"]:
                        in_t, out_t = "00:00", "00:00"
                    else:
                        try:
                            in_t = row["In Time"].strftime("%H:%M") if isinstance(row["In Time"], time) else str(row["In Time"])
                            out_t = row["Out Time"].strftime("%H:%M") if isinstance(row["Out Time"], time) else str(row["Out Time"])
                        except:
                            in_t, out_t = "08:00", "18:00"
                    
                    tot, late, out_e, out_e, ot = calculate_times(in_t, out_t, r_day_str, stat, is_pub_hol)
                    new_records.append({
                        "Employee Name": emp_n, "Date": r_date_str, "Day": r_day_str,
                        "In Time": in_t, "Out Time": out_t, "Late Hours": late, "Out Hours": out_e,
                        "Total Hours": tot, "OT Hours": ot, "Status": stat
                    })
                
                if new_records:
                    df_new_roster = pd.DataFrame(new_records)
                    df_r_month = pd.concat([df_r_month, df_new_roster], ignore_index=True)
                    save_data(df_r_month, r_sheet)
                    st.session_state.flash_msg = f"✅ Daily Roster for {r_date_str} saved successfully!"
                    st.rerun()

with tab3:
    st.subheader("🌴 Holiday Calendar")
    if st.session_state.cached_holidays is None:
        st.session_state.cached_holidays = load_holidays_data()
    hol_data = st.session_state.cached_holidays
    
    if is_admin_unlocked:
        st.info("🔓 You have Administrator access to manage holidays.")
        
        with st.form("add_holiday_form"):
            hc1, hc2, hc3, hc4 = st.columns([1.5, 1.5, 2, 1])
            with hc1: 
                f_date = st.date_input("From Date", format="DD/MM/YYYY")
            with hc2: 
                t_date = st.date_input("To Date", value=f_date, format="DD/MM/YYYY")
            with hc3: 
                hol_reason = st.text_input("Occasion / Reason", placeholder="e.g. Diwali Holidays")
            with hc4:
                st.write("")
                st.write("")
                add_hol = st.form_submit_button("➕ Add Holiday", type="primary", use_container_width=True)
        
        if add_hol:
            if t_date < f_date:
                st.error("⚠️ 'To Date' cannot be before 'From Date'!")
            elif not hol_reason.strip():
                st.error("⚠️ Please enter a Reason!")
            else:
                days_count = (t_date - f_date).days + 1
                unique_id = str(uuid.uuid4())[:8] 
                
                hol_data[unique_id] = {
                    "from": f_date.strftime("%d/%m/%Y"),
                    "to": t_date.strftime("%d/%m/%Y"),
                    "reason": hol_reason.strip(),
                    "days": days_count
                }
                save_holidays_data(hol_data)
                st.session_state.flash_msg = f"✅ Holiday Range Added! ({days_count} Days)"
                st.rerun()
            
        if hol_data:
            st.write("### 📅 Existing Holidays")
            for hid, hinfo in list(hol_data.items()):
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
                    c1.write(f"🗓️ **{hinfo['from']}** to **{hinfo['to']}**")
                    c2.write(f"✨ {hinfo['reason']} ({hinfo['days']} Days)")
                    
                    if c3.button("✏️ Edit", key=f"edit_{hid}"):
                        st.session_state[f"edit_mode_{hid}"] = not st.session_state.get(f"edit_mode_{hid}", False)
                        st.rerun()
                        
                    if c4.button("🗑️ Delete", key=f"del_{hid}"):
                        del hol_data[hid]
                        save_holidays_data(hol_data)
                        st.session_state.flash_msg = "✅ Holiday entry deleted successfully!"
                        st.rerun()
                    
                    if st.session_state.get(f"edit_mode_{hid}", False):
                        with st.form(f"edit_form_{hid}"):
                            ec1, ec2, ec3, ec4 = st.columns([1.5, 1.5, 2, 1])
                            curr_f = datetime.strptime(hinfo['from'], "%d/%m/%Y").date()
                            curr_t = datetime.strptime(hinfo['to'], "%d/%m/%Y").date()
                            with ec1: ef_date = st.date_input("From Date", value=curr_f, format="DD/MM/YYYY", key=f"ef_{hid}")
                            with ec2: et_date = st.date_input("To Date", value=curr_t, format="DD/MM/YYYY", key=f"et_{hid}")
                            with ec3: ereason = st.text_input("Reason", value=hinfo['reason'], key=f"er_{hid}")
                            with ec4:
                                st.write("")
                                st.write("")
                                update_btn = st.form_submit_button("💾 Save", type="primary")

                        if update_btn:
                            if et_date < ef_date:
                                st.error("⚠️ 'To Date' cannot be before 'From Date'!")
                            else:
                                hol_data[hid]['from'] = ef_date.strftime("%d/%m/%Y")
                                hol_data[hid]['to'] = et_date.strftime("%d/%m/%Y")
                                hol_data[hid]['reason'] = ereason.strip()
                                hol_data[hid]['days'] = (et_date - ef_date).days + 1
                                save_holidays_data(hol_data)
                                st.session_state[f"edit_mode_{hid}"] = False
                                st.session_state.flash_msg = "✅ Holiday updated!"
                                st.rerun()
    else:
        st.caption("🔒 **Note:** Only Administrator can add, edit or delete holidays. (Enter password in 'Add Attendance' tab to unlock)")
        
        if hol_data:
            st.write("### 📅 Upcoming / Declared Holidays")
            hol_list = []
            for hid, hinfo in hol_data.items():
                hol_list.append({
                    "Reason": hinfo['reason'],
                    "From Date": hinfo['from'],
                    "To Date": hinfo['to'],
                    "Total Days": hinfo['days']
                })
            df_hol = pd.DataFrame(hol_list)
            df_hol['SortDate'] = pd.to_datetime(df_hol['From Date'], format='%d/%m/%Y', errors='coerce')
            df_hol = df_hol.sort_values('SortDate').drop(columns=['SortDate']).reset_index(drop=True)
            df_hol.index = range(1, len(df_hol) + 1)
            st.dataframe(df_hol, use_container_width=True)
        else:
            st.write("No holidays declared yet.")

with tab4:
    if not formatted_name:
        st.info("👆 Please select an Employee Name in the 'Add Attendance' tab to view their Dashboard & History.")
    elif formatted_name == "Administrator" and not is_admin_unlocked:
        st.caption("🔒 **Note:** Please enter the Admin password in the 'Add Attendance' tab to unlock the Dashboard.")
    else:
        all_sheets_raw = get_all_sheet_names()
        if current_month_str not in all_sheets_raw:
            all_sheets_raw.insert(0, current_month_str)
        
        available_sheets = ["All Months"] + all_sheets_raw

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            selected_sheet = st.selectbox("Select Month to View", available_sheets, key="filter_month_dash")
        
        if is_admin_unlocked:
            with col_f2:
                emp_list = ["All Employees"] + get_all_employees()
                selected_emp = st.selectbox("Select Master View", emp_list, key="admin_emp_select")
        else:
            selected_emp = formatted_name

        if selected_sheet == "All Months":
            df_list = []
            for sht in get_all_sheet_names():
                if sht not in st.session_state.cached_data:
                    st.session_state.cached_data[sht] = load_data(sht)
                df_temp = st.session_state.cached_data[sht]
                if not df_temp.empty:
                    df_temp = df_temp.copy()
                    df_temp["_Original_Sheet"] = sht
                    df_temp["_Original_Index"] = df_temp.index
                    df_list.append(df_temp)
            if df_list:
                df_display = pd.concat(df_list, ignore_index=True)
            else:
                df_display = pd.DataFrame()
        else:
            if selected_sheet not in st.session_state.cached_data:
                st.session_state.cached_data[selected_sheet] = load_data(selected_sheet)
            df_temp = st.session_state.cached_data[selected_sheet]
            if not df_temp.empty:
                df_display = df_temp.copy()
                df_display["_Original_Sheet"] = selected_sheet
                df_display["_Original_Index"] = df_display.index
            else:
                df_display = pd.DataFrame()

        if not df_display.empty:
            df_display["RealDate"] = pd.to_datetime(df_display["Date"], format="%d/%m/%Y")
            df_display = df_display.sort_values(by=["Employee Name", "RealDate"]).drop(columns=["RealDate"])
            df_display = df_display.reset_index(drop=True)
            df_display = df_display.fillna("") 

            if selected_emp != "All Employees":
                df_display = df_display[df_display["Employee Name"].astype(str).str.strip().str.lower() == selected_emp.lower()]

            final_display_columns = ["Employee Name", "Date", "Day", "In Time", "Out Time", "Late Hours", "Out Hours", "Total Hours", "OT Hours", "Status", "_Original_Sheet", "_Original_Index"]
            for c in final_display_columns:
                 if c not in df_display.columns:
                     df_display[c] = ""
            df_display = df_display[final_display_columns]
            
            st.write("")
            
            # --- SMART FILTERS UI ---
            st.markdown("### 🔍 Smart Filters (Select Multiple)")
            
            filt_c1, filt_c2 = st.columns([1, 1])
            
            with filt_c1:
                if is_admin_unlocked and selected_emp == "All Employees":
                    emp_opts = sorted(df_display["Employee Name"].unique().tolist())
                    f_emps = st.multiselect("👤 Filter by Employee(s)", emp_opts, placeholder="Select 1 or more...")
                else:
                    f_emps = []
                    
            with filt_c2:
                stat_opts = sorted(df_display["Status"].unique().tolist())
                f_stats = st.multiselect("📌 Filter by Status", stat_opts, placeholder="Select 1 or more...")
                
            # Apply Filters
            if f_emps:
                df_display = df_display[df_display["Employee Name"].isin(f_emps)]
            if f_stats:
                df_display = df_display[df_display["Status"].isin(f_stats)]
                
            st.divider()

        if df_display.empty:
            st.warning(f"No records found with the current filters.")
        else:
            total_reg_mins = 0
            for val in df_display["Total Hours"]:
                if pd.notna(val) and ":" in str(val):
                    h, m = map(int, str(val).split(":"))
                    total_reg_mins += h * 60 + m
            reg_hours, reg_mins = divmod(total_reg_mins, 60)
            
            total_ot_mins = 0
            for val in df_display["OT Hours"]:
                if pd.notna(val) and ":" in str(val):
                    h, m = map(int, str(val).split(":"))
                    total_ot_mins += h * 60 + m
            ot_hours, ot_mins = divmod(total_ot_mins, 60)

            total_late_mins = 0
            for val in df_display["Late Hours"]:
                if pd.notna(val) and ":" in str(val):
                    h, m = map(int, str(val).split(":"))
                    total_late_mins += h * 60 + m
            late_hours, late_mins = divmod(total_late_mins, 60)

            total_out_mins = 0
            for val in df_display["Out Hours"]:
                if pd.notna(val) and ":" in str(val):
                    h, m = map(int, str(val).split(":"))
                    total_out_mins += h * 60 + m
            out_hours, out_mins = divmod(total_out_mins, 60)
            
            pl_count = len(df_display[df_display["Status"] == "PL"])
            absent_count = len(df_display[df_display["Status"].isin(["LWP", "Absent"])])

            st.markdown('<div class="summary-container">', unsafe_allow_html=True)
            if f_emps or selected_emp != "All Employees" or f_stats:
                st.subheader(f"📊 Summary Data")
            else:
                st.subheader("📊 Master Attendance Data (All Employees)")
                
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1: st.metric(label="🕒 Total Working Hrs", value=f"{reg_hours:02d}:{reg_mins:02d}")
            with m2: st.metric(label="🔥 Total OT Hrs", value=f"{ot_hours:02d}:{ot_mins:02d}")
            with m3: st.metric(label="⚠️ Total Late/Out Hrs", value=f"{late_hours+out_hours:02d}:{(late_mins+out_mins):02d}")
            with m4: st.metric(label="🌴 Paid Leaves (PL)", value=pl_count)
            with m5: st.metric(label="❌ Absent (LWP)", value=absent_count)
            st.markdown('</div>', unsafe_allow_html=True)

            st.write("")
            st.divider()
            
            # --- EDIT/DELETE FORMS ---
            if st.session_state.edit_row:
                st.subheader("✏️ Edit Selected Entry")
                row_data = st.session_state.edit_row["data"]
                selected_idx = st.session_state.edit_row["index"]
                selected_sheet_orig = st.session_state.edit_row["sheet"]
                
                with st.form("edit_form_hist"):
                    e_name = st.text_input("Employee Name", value=row_data["Employee Name"], disabled=True)
                    
                    ce1, ce2, ce3, ce4, ce5, ce6 = st.columns([1.2, 1.2, 1.2, 1.2, 1, 1])
                    with ce1:
                        d_obj = datetime.strptime(row_data["Date"], "%d/%m/%Y").date()
                        e_date = st.date_input("Date", value=d_obj, key="e_date", format="DD/MM/YYYY")
                    with ce2:
                        def_status = ["Regular", "Holiday", "PL", "LWP", "Absent"]
                        e_stat = st.selectbox("Status", def_status, index=def_status.index(row_data.get("Status", "Regular")))
                    with ce3:
                        e_in = st.text_input("In Time", value=row_data["In Time"], key="e_in")
                    with ce4:
                        e_out = st.text_input("Out Time", value=row_data["Out Time"], key="e_out")
                        
                    with ce5:
                        st.write("")
                        st.write("")
                        btn_update = st.form_submit_button("Update", type="primary", use_container_width=True)
                    with ce6:
                        st.write("")
                        st.write("")
                        btn_cancel = st.form_submit_button("Cancel", use_container_width=True)
                        
                    if btn_update:
                        formatted_e_name = e_name.strip().title()
                        date_str_e = e_date.strftime("%d/%m/%Y")
                        new_sheet = get_sheet_name(e_date)
                        
                        if selected_sheet_orig not in st.session_state.cached_data:
                            st.session_state.cached_data[selected_sheet_orig] = load_data(selected_sheet_orig)
                        df_orig = st.session_state.cached_data[selected_sheet_orig].copy()
                        
                        if new_sheet == selected_sheet_orig:
                            temp_check = df_orig.drop(selected_idx, errors='ignore')
                            is_dup = not temp_check[(temp_check["Employee Name"].astype(str).str.strip().str.lower() == formatted_e_name.lower()) & (temp_check["Date"] == date_str_e)].empty
                        else:
                            if new_sheet not in st.session_state.cached_data:
                                st.session_state.cached_data[new_sheet] = load_data(new_sheet)
                            df_new = st.session_state.cached_data[new_sheet].copy()
                            is_dup = not df_new[(df_new["Employee Name"].astype(str).str.strip().str.lower() == formatted_e_name.lower()) & (df_new["Date"] == date_str_e)].empty

                        if is_dup:
                            st.error("⚠️ An entry for this employee on this date already exists!")
                        else:
                            day_str_e = e_date.strftime("%a")
                            holidays_dict = get_flat_holiday_dates()
                            is_pub_hol = date_str_e in holidays_dict
                            t_hrs, l_hrs, o_hrs, ot_hrs = calculate_times(e_in, e_out, day_str_e, e_stat, is_pub_hol)
                            
                            if e_stat in ["PL", "LWP", "Absent"]:
                                in_t_str, out_t_str = "00:00", "00:00"
                            else:
                                in_t_str, out_t_str = e_in, e_out

                            updated_row = pd.DataFrame({
                                "Employee Name": [formatted_e_name],
                                "Date": [date_str_e],
                                "Day": [day_str_e],
                                "In Time": [in_t_str],
                                "Out Time": [out_t_str],
                                "Late Hours": [l_hrs],
                                "Out Hours": [o_hrs],
                                "Total Hours": [t_hrs],
                                "OT Hours": [ot_hrs],
                                "Status": [e_stat]
                            })
                            
                            if new_sheet == selected_sheet_orig:
                                updated_row.index = [selected_idx]
                                df_orig.update(updated_row)
                                save_data(df_orig, selected_sheet_orig)
                            else:
                                df_orig = df_orig.drop(selected_idx, errors='ignore')
                                save_data(df_orig, selected_sheet_orig)
                                df_new = pd.concat([df_new, updated_row], ignore_index=True)
                                save_data(df_new, new_sheet)
                            
                            st.session_state.edit_row = None
                            st.session_state.flash_msg = f"✅ Record updated successfully!"
                            st.rerun()
                    if btn_cancel:
                        st.session_state.edit_row = None
                        st.rerun()
                st.markdown("---")

            if st.session_state.del_row:
                st.warning(f"Are you sure you want to delete the record for {st.session_state.del_row['data']['Employee Name']} on {st.session_state.del_row['data']['Date']}?")
                col_y, col_n = st.columns([1,1])
                with col_y:
                    if st.button("Yes, Delete", type="primary"):
                        sht = st.session_state.del_row["sheet"]
                        idx = st.session_state.del_row["index"]
                        if sht not in st.session_state.cached_data:
                            st.session_state.cached_data[sht] = load_data(sht)
                        df_orig = st.session_state.cached_data[sht].copy()
                        df_orig = df_orig.drop(idx, errors='ignore')
                        save_data(df_orig, sht)
                        
                        st.session_state.del_row = None
                        st.session_state.flash_msg = "✅ Entry permanently deleted!"
                        st.rerun()
                with col_n:
                    if st.button("No, Cancel"):
                        st.session_state.del_row = None
                        st.rerun()
                st.markdown("---")
            # --------------------------------------------------------

            head_col1, head_col2 = st.columns([3,1])
            with head_col1:
                st.subheader("📋 Attendance Records")
            with head_col2:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    export_sheet_name = selected_sheet if selected_sheet != "All Months" else "All_Months"
                    
                    if selected_emp != "All Employees":
                        df_export = df_display.drop(columns=["_Original_Sheet", "_Original_Index", "Employee Name"], errors='ignore')
                        df_export.to_excel(writer, index=False, startrow=2, sheet_name=export_sheet_name)
                        worksheet = writer.sheets[export_sheet_name]
                        
                        center_align = Alignment(horizontal='center', vertical='center')
                        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                        
                        red_fill = PatternFill(start_color='FF4C4C', end_color='FF4C4C', fill_type='solid') 
                        gray_fill = PatternFill(start_color='D9D9D9', end_color='D9D9D9', fill_type='solid') 
                        yellow_fill_name = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
                        total_fill = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid') 
                        holiday_fill = PatternFill(start_color='B3D9FF', end_color='B3D9FF', fill_type='solid') 
                        
                        white_bold_font = Font(color="FFFFFF", bold=True)
                        black_bold_font = Font(color="000000", bold=True)
                        header_font = Font(bold=True)
                        total_font = Font(bold=True, size=12)
                        
                        worksheet.merge_cells('A1:B1')
                        worksheet.merge_cells('C1:D1')
                        
                        a1 = worksheet['A1']
                        a1.value = "Employee Name :"
                        a1.fill = gray_fill
                        a1.font = header_font
                        a1.alignment = center_align
                        
                        c1 = worksheet['C1']
                        c1.value = selected_emp
                        c1.fill = yellow_fill_name
                        c1.font = header_font
                        c1.alignment = center_align
                        
                        for r in worksheet['A1:D1']:
                            for c in r:
                                c.border = thin_border
                                
                        for col_idx in range(1, 10): 
                            cell = worksheet.cell(row=3, column=col_idx)
                            cell.fill = gray_fill
                            cell.font = header_font
                            cell.alignment = center_align
                            cell.border = thin_border
                        
                        day_col_idx = 2 
                        status_col_idx = 9
                        max_data_row = 3 + len(df_export)
                        
                        holidays_dict_xls = get_flat_holiday_dates()
                        
                        for row_idx in range(4, max_data_row + 1):
                            date_val_xls = worksheet.cell(row=row_idx, column=1).value
                            day_val = worksheet.cell(row=row_idx, column=day_col_idx).value
                            status_val = worksheet.cell(row=row_idx, column=status_col_idx).value
                            
                            is_sunday = (day_val == "Sun")
                            is_holiday = (status_val == "Holiday") or (str(date_val_xls) in holidays_dict_xls)
                            
                            for col_idx in range(1, 10):
                                cell = worksheet.cell(row=row_idx, column=col_idx)
                                cell.alignment = center_align
                                cell.border = thin_border
                                if is_sunday:
                                    cell.fill = red_fill
                                    cell.font = white_bold_font
                                elif is_holiday:
                                    cell.fill = holiday_fill
                                    cell.font = black_bold_font
                                    
                        total_row_idx = max_data_row + 2
                        worksheet.merge_cells(start_row=total_row_idx, start_column=3, end_row=total_row_idx, end_column=4)
                        
                        worksheet.cell(row=total_row_idx, column=3, value="TOTAL")
                        worksheet.cell(row=total_row_idx, column=5, value=f"{late_hours:02d}:{late_mins:02d}")
                        worksheet.cell(row=total_row_idx, column=6, value=f"{out_hours:02d}:{out_mins:02d}")
                        worksheet.cell(row=total_row_idx, column=7, value=f"{reg_hours:02d}:{reg_mins:02d}")
                        worksheet.cell(row=total_row_idx, column=8, value=f"{ot_hours:02d}:{ot_mins:02d}")
                        
                        for col_idx in range(1, 10):
                            cell = worksheet.cell(row=total_row_idx, column=col_idx)
                            cell.border = thin_border
                            cell.fill = total_fill
                            cell.font = total_font
                            cell.alignment = center_align

                        empty_row_idx = max_data_row + 1
                        for row_idx in range(1, worksheet.max_row + 1):
                            if row_idx == 2 or row_idx == empty_row_idx:
                                worksheet.row_dimensions[row_idx].height = 6 
                            else:
                                worksheet.row_dimensions[row_idx].height = 18
                        
                        for col_idx in range(1, worksheet.max_column + 1):
                            max_length = 0
                            col_letter = get_column_letter(col_idx)
                            for row_idx in range(3, worksheet.max_row + 1): 
                                cell_val = worksheet.cell(row=row_idx, column=col_idx).value
                                try:
                                    if cell_val and len(str(cell_val)) > max_length:
                                        max_length = len(str(cell_val))
                                except:
                                    pass
                            worksheet.column_dimensions[col_letter].width = max_length + 3
                    else:
                        df_export = df_display.drop(columns=["_Original_Sheet", "_Original_Index"], errors='ignore')
                        df_export.to_excel(writer, index=False, sheet_name=export_sheet_name)
                        worksheet = writer.sheets[export_sheet_name]
                        
                        header_fill = PatternFill(start_color='D9D9D9', end_color='D9D9D9', fill_type='solid')
                        header_font = Font(bold=True)
                        for cell in worksheet[1]:
                            cell.fill = header_fill
                            cell.font = header_font
                            
                        for column_cells in worksheet.columns:
                            length = max(len(str(cell.value)) for cell in column_cells)
                            worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = length + 2

                excel_data = buffer.getvalue()
                file_name_export = f"Attendance_{selected_sheet}.xlsx".replace(" ", "_")
                
                st.download_button(
                    label="⬇️ Download Excel",
                    data=excel_data,
                    file_name=file_name_export,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            st.markdown("💡 **Tip:** Use the Edit/Delete buttons on the right side of each entry to make changes.")
            
            # --- FIX: NARROW COMPACT UI & BUTTONS CLOSER ---
            for index, row in df_display.iterrows():
                status_color = "#1e2530" 
                hol_dict_hl = get_flat_holiday_dates()
                
                if row['Day'] == 'Sun':
                    status_color = "#4a1c1c"
                elif row['Status'] == 'Holiday' or row['Date'] in hol_dict_hl:
                    status_color = "#1c3756"
                elif row['Status'] in ['PL', 'LWP', 'Absent']:
                    status_color = "#563d1c"
                elif st.session_state.last_edited == f"{row['Employee Name']}_{row['Date']}":
                    status_color = "#3b3b18"
                
                # Made info smaller, buttons closer, and added blank space on the right
                c_info, c_edit, c_del, c_blank = st.columns([5, 0.7, 0.7, 3.6])
                
                with c_info:
                    st.markdown(f"""
                    <div style="background-color: {status_color}; padding: 6px 12px; border-radius: 6px; border: 1px solid #303d4f; height: 100%; display: flex; align-items: center;">
                        <div style="width: 100%;">
                            <span style="color: #8b9bb4; font-size: 0.85em; margin-right: 10px;">{row['Date']} ({row['Day']})</span>
                            <strong style="font-size: 1em; margin-right: 10px;">{row['Employee Name']}</strong>
                            <span style="font-size: 0.9em; color: #d1d5db;">{row['Status']} | In: {row['In Time']} - Out: {row['Out Time']} | Total: <span style="color:white; font-weight:bold;">{row['Total Hours']}</span> (OT: {row['OT Hours']})</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with c_edit:
                    if st.button("✏️ Edit", key=f"e_{row['_Original_Index']}_{row['_Original_Sheet']}", use_container_width=True):
                        st.session_state.edit_row = {"index": row['_Original_Index'], "sheet": row['_Original_Sheet'], "data": row}
                        st.session_state.del_row = None
                        st.rerun()
                
                with c_del:
                    if st.button("🗑️ Del", key=f"d_{row['_Original_Index']}_{row['_Original_Sheet']}", use_container_width=True):
                        st.session_state.del_row = {"index": row['_Original_Index'], "sheet": row['_Original_Sheet'], "data": row}
                        st.session_state.edit_row = None
                        st.rerun()

with tab5:
    st.subheader("👤 Manage Employees")
    if is_admin_unlocked:
        with st.form("add_new_emp_form"):
            col_e1, col_e2 = st.columns([3, 1])
            with col_e1:
                new_emp_name = st.text_input("Enter New Employee Name", placeholder="e.g. Rahul Patel")
            with col_e2:
                st.write("")
                st.write("")
                add_emp_btn = st.form_submit_button("➕ Add Employee", type="primary", use_container_width=True)
        
        if add_emp_btn:
            clean_name = new_emp_name.strip().title()
            if not clean_name:
                st.error("⚠️ Please enter a valid name!")
            elif clean_name == "Administrator":
                st.error("⚠️ You cannot add 'Administrator' as an employee.")
            else:
                all_existing = get_all_employees()
                if clean_name in all_existing:
                    st.warning(f"⚠️ Employee '{clean_name}' already exists in the system!")
                else:
                    reg_emps = load_registered_employees()
                    if clean_name not in reg_emps:
                        reg_emps.append(clean_name)
                        save_registered_employees(reg_emps)
                    st.session_state.flash_msg = f"✅ Employee '{clean_name}' successfully added!"
                    st.rerun()
        
        st.divider()
        st.write("### 📋 All Registered Employees")
        
        current_emps = get_all_employees()
        if current_emps:
            
            if st.session_state.get('edit_emp'):
                st.subheader(f"✏️ Update Employee Name: {st.session_state.edit_emp}")
                with st.form("edit_emp_form"):
                    cs1, cs2, cs3 = st.columns([3, 1, 1])
                    with cs1:
                        new_n = st.text_input("New Name", value=st.session_state.edit_emp)
                    with cs2:
                        st.write("")
                        st.write("")
                        btn_upd = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
                    with cs3:
                        st.write("")
                        st.write("")
                        btn_canc = st.form_submit_button("❌ Cancel", use_container_width=True)
                    
                    if btn_upd:
                        clean_new = new_n.strip().title()
                        if clean_new and clean_new != st.session_state.edit_emp:
                            reg_emps = load_registered_employees()
                            if st.session_state.edit_emp in reg_emps:
                                reg_emps.remove(st.session_state.edit_emp)
                            if clean_new not in reg_emps:
                                reg_emps.append(clean_new)
                            save_registered_employees(reg_emps)
                            st.session_state.flash_msg = f"✅ Updated '{st.session_state.edit_emp}' to '{clean_new}'!"
                        st.session_state.edit_emp = None
                        st.rerun()
                    if btn_canc:
                        st.session_state.edit_emp = None
                        st.rerun()
                st.markdown("---")
                            
            if st.session_state.get('del_emp'):
                st.warning(f"⚠️ Are you sure you want to remove '{st.session_state.del_emp}' from the system?")
                dy, dn = st.columns(2)
                with dy:
                    if st.button("✅ Yes, Delete", type="primary"):
                        reg_emps = load_registered_employees()
                        if st.session_state.del_emp in reg_emps:
                            reg_emps.remove(st.session_state.del_emp)
                            save_registered_employees(reg_emps)
                        st.session_state.flash_msg = f"🗑️ '{st.session_state.del_emp}' deleted successfully!"
                        st.session_state.del_emp = None
                        st.rerun()
                with dn:
                    if st.button("❌ No, Cancel"):
                        st.session_state.del_emp = None
                        st.rerun()
                st.markdown("---")
            
            # Use columns for headers to match exactly
            hc1, hc2, hc3, hc_blank = st.columns([0.6, 3, 1.4, 4])
            with hc1: st.markdown("**Sr No.**")
            with hc2: st.markdown("**Employee Name**")
            with hc3: st.markdown("**Actions**")
            st.divider()
            
            for idx, emp in enumerate(current_emps):
                c1, c2, c3, c4, c_blank = st.columns([0.6, 3, 0.7, 0.7, 4])
                with c1:
                    st.write(f"**{idx + 1}**")
                with c2:
                    st.write(emp)
                with c3:
                    if st.button("✏️ Edit", key=f"emp_edit_{emp}"):
                        st.session_state.edit_emp = emp
                        st.session_state.del_emp = None
                        st.rerun()
                with c4:
                    if st.button("🗑️ Delete", key=f"emp_del_{emp}"):
                        st.session_state.del_emp = emp
                        st.session_state.edit_emp = None
                        st.rerun()

        else:
            st.info("No employees found. Please add a new employee above.")
            
    else:
        st.caption("🔒 **Note:** Only Administrator can manage employees. (Enter password in 'Add Attendance' tab to unlock)")
