import streamlit as st
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, time, timedelta, timezone
import io
import os
import json
import calendar
import hashlib
from openpyxl.styles import Alignment, PatternFill, Border, Side, Font
from openpyxl.utils import get_column_letter
import uuid
import time as time_module

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# ---------------------------------------------------------
st.set_page_config(page_title="Advanced Attendance & Salary System", layout="wide", page_icon="📅")
# ---------------------------------------------------------

# ==========================================
# 1. SETTINGS, CONSTANTS & FAST HTTP SESSION
# ==========================================
FIREBASE_URL = "https://attendence-ec921-default-rtdb.firebaseio.com"

STANDARD_IN = "08:00"
STANDARD_OUT = "18:00"

ATT_COLUMNS = ["Employee Name", "Date", "Day", "In Time", "Out Time", "Late Hours", "Out Hours", "Total Hours", "OT Hours", "Status"]
MONTH_ORDER = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
MONTH_DICT = {m: i + 1 for i, m in enumerate(MONTH_ORDER)}

@st.cache_resource
def get_http_session():
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

http = get_http_session()

def get_ist_now():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

def get_ist_today():
    return get_ist_now().date()

def get_sheet_name(selected_date):
    return selected_date.strftime("%b'%Y")

def get_emp_key(name):
    if not name:
        return "Unknown"
    return str(name).replace(".", "").replace("#", "").replace("$", "").replace("[", "").replace("]", "").strip()

def hash_pwd(pwd_str):
    return hashlib.sha256(str(pwd_str).encode("utf-8")).hexdigest()

def get_query_param(key):
    try:
        val = st.query_params.get(key)
        if isinstance(val, list):
            return val[0] if val else None
        return val
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def get_all_sheet_names():
    url = f"{FIREBASE_URL}.json?shallow=true"
    excluded = {"holidays_list", "employee_list", "employee_dict", "profiles", "salary_history", "active_sessions"}
    try:
        response = http.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, dict):
                return [k for k in data.keys() if k not in excluded]
    except Exception:
        pass

    fallback_sheets = []
    d = get_ist_today()
    for _ in range(12):
        fallback_sheets.append(d.strftime("%b'%Y"))
        if d.month == 1:
            d = d.replace(year=d.year - 1, month=12)
        else:
            d = d.replace(month=d.month - 1)
    return fallback_sheets

# ==========================================
# EMPLOYEE DICTIONARY LOGIC (SECURITY SYSTEM)
# ==========================================
def migrate_old_list_to_dict():
    old_list = []
    try:
        res = http.get(f"{FIREBASE_URL}/employee_list.json", timeout=10)
        if res.status_code == 200 and res.json():
            data = res.json()
            if isinstance(data, list):
                old_list = [str(r).strip().title() for r in data if r]
            elif isinstance(data, dict):
                old_list = [str(v).strip().title() for v in data.values() if v]
    except Exception:
        pass

    new_dict = {"Administrator": {"password": "1234", "details": "Master Admin"}}
    for emp in set(old_list):
        if emp != "Administrator":
            new_dict[emp] = {"password": "123", "details": ""}
    return new_dict

@st.cache_data(ttl=300, show_spinner=False)
def fetch_employee_dict():
    try:
        res = http.get(f"{FIREBASE_URL}/employee_dict.json", timeout=10)
        if res.status_code == 200 and res.json():
            data = res.json()
            if isinstance(data, dict):
                if "Administrator" not in data:
                    data["Administrator"] = {"password": "1234", "details": "Master Admin"}
                    save_employee_dict(data)
                return data
    except Exception:
        pass

    migrated_dict = migrate_old_list_to_dict()
    if migrated_dict:
        save_employee_dict(migrated_dict)
        return migrated_dict
    return {"Administrator": {"password": "1234", "details": "Master Admin"}}

def save_employee_dict(emp_dict):
    try:
        http.put(f"{FIREBASE_URL}/employee_dict.json", json=emp_dict, timeout=10)
        fetch_employee_dict.clear()
    except Exception:
        pass
    st.session_state.emp_dict = emp_dict
    st.session_state.emp_list = sorted([k for k in emp_dict.keys() if k != "Administrator"])

if 'emp_dict' not in st.session_state or not st.session_state.emp_dict:
    st.session_state.emp_dict = fetch_employee_dict()
    st.session_state.emp_list = sorted([k for k in st.session_state.emp_dict.keys() if k != "Administrator"])

# ==========================================
# PERSISTENT CLOUD SESSION (SURVIVES PAGE REFRESH)
# ==========================================
def create_cloud_session(user_name, role, pwd_plain):
    token = uuid.uuid4().hex
    expires_str = (get_ist_today() + timedelta(days=30)).isoformat()
    payload = {
        "user": user_name,
        "role": role,
        "pwd": hash_pwd(pwd_plain),
        "expires": expires_str
    }
    try:
        http.put(f"{FIREBASE_URL}/active_sessions/{token}.json", json=payload, timeout=10)
        st.query_params["sid"] = token
    except Exception:
        pass
    return token

def delete_cloud_session(token):
    if not token:
        return
    try:
        http.delete(f"{FIREBASE_URL}/active_sessions/{requests.utils.quote(str(token))}.json", timeout=10)
    except Exception:
        pass

def update_cloud_session_pwd(token, new_pwd_plain):
    if not token:
        return
    try:
        http.patch(
            f"{FIREBASE_URL}/active_sessions/{requests.utils.quote(str(token))}.json",
            json={"pwd": hash_pwd(new_pwd_plain)},
            timeout=10
        )
    except Exception:
        pass

def try_restore_cloud_session():
    sid = get_query_param("sid")
    if not sid:
        return None
    try:
        res = http.get(f"{FIREBASE_URL}/active_sessions/{requests.utils.quote(str(sid))}.json", timeout=10)
        if res.status_code == 200 and isinstance(res.json(), dict):
            sdata = res.json()
            s_user = sdata.get("user")
            s_role = sdata.get("role")
            s_pwd_hash = sdata.get("pwd")
            s_exp = sdata.get("expires", "")

            if s_user in st.session_state.emp_dict and s_exp >= get_ist_today().isoformat():
                actual_pwd = st.session_state.emp_dict[s_user].get("password", "123")
                if hash_pwd(actual_pwd) == s_pwd_hash:
                    return s_user, s_role, sid
        delete_cloud_session(sid)
        try:
            st.query_params.pop("sid", None)
        except Exception:
            pass
    except Exception:
        pass
    return None

# ==========================================
# HOLIDAYS LOGIC (CACHED)
# ==========================================
@st.cache_data(ttl=300, show_spinner=False)
def load_holidays_data():
    try:
        res = http.get(f"{FIREBASE_URL}/holidays_list.json", timeout=10)
        if res.status_code == 200 and res.json():
            return res.json()
    except Exception:
        pass
    return {}

@st.cache_data(ttl=300, show_spinner=False)
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
        except Exception:
            pass
    return flat_dict

def save_holidays_data(data):
    try:
        http.put(f"{FIREBASE_URL}/holidays_list.json", json=data, timeout=10)
        load_holidays_data.clear()
        get_flat_holiday_dates.clear()
        st.session_state.cached_holidays = data
    except Exception:
        pass

# ==========================================
# TIME CALCULATIONS
# ==========================================
def parse_time(time_val):
    time_str = str(time_val).strip()
    try:
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        try:
            return datetime.strptime(time_str, "%H:%M:%S")
        except ValueError:
            return datetime.strptime("00:00", "%H:%M")

def parse_hm_tuple(time_str):
    if pd.isna(time_str) or str(time_str).strip() == "":
        return 0, 0
    try:
        parts = str(time_str).strip().split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h, m
    except Exception:
        return 0, 0

def check_time_overlap(curr_in_str, curr_out_str, new_in_str, new_out_str):
    if not curr_in_str or curr_in_str == "00:00":
        return False

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
        if m <= 0:
            return "00:00"
        h, m = divmod(int(m), 60)
        return f"{h:02d}:{m:02d}"

    return mins_to_str(reg_mins), mins_to_str(late_mins), mins_to_str(out_early_mins), mins_to_str(ot_mins)

@st.cache_data(ttl=300, show_spinner=False)
def load_data(sheet_name):
    url = f"{FIREBASE_URL}/{requests.utils.quote(str(sheet_name))}.json"
    holidays_dict = get_flat_holiday_dates()

    try:
        response = http.get(url, timeout=10)
        data = response.json()
        if data:
            if isinstance(data, dict):
                df = pd.DataFrame(list(data.values()))
            else:
                df = pd.DataFrame([row for row in data if row is not None])

            for col in ATT_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
                    if col == "Status":
                        df[col] = "Regular"
                    if col in ["Late Hours", "Out Hours", "Total Hours", "OT Hours"]:
                        df[col] = "00:00"
                    if col == "In Time":
                        df[col] = "08:00"
                    if col == "Out Time":
                        df[col] = "18:00"

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

            return df[ATT_COLUMNS]
        else:
            return pd.DataFrame(columns=ATT_COLUMNS)
    except Exception:
        return pd.DataFrame(columns=ATT_COLUMNS)

def save_data(df, sheet_name):
    df_clean = df.fillna("").reset_index(drop=True)
    for col in ATT_COLUMNS:
        if col not in df_clean.columns:
            df_clean[col] = ""
    df_clean = df_clean[ATT_COLUMNS]
    url = f"{FIREBASE_URL}/{requests.utils.quote(str(sheet_name))}.json"
    data = df_clean.to_dict(orient='records')
    try:
        http.put(url, json=data, timeout=10)
        load_data.clear()
        get_all_sheet_names.clear()
        if 'cached_data' in st.session_state:
            st.session_state.cached_data[sheet_name] = df_clean.copy()
    except Exception:
        pass

# ==========================================
# SALARY & HRIS CLOUD HELPERS
# ==========================================
@st.cache_data(ttl=300, show_spinner=False)
def load_profiles():
    try:
        res = http.get(f"{FIREBASE_URL}/profiles.json", timeout=10)
        if res.status_code == 200 and isinstance(res.json(), dict):
            return res.json()
    except Exception:
        pass
    return {}

def find_profile_data(all_profiles, emp_name):
    if not emp_name or not isinstance(all_profiles, dict):
        return emp_name, {}
    if emp_name in all_profiles:
        return emp_name, all_profiles[emp_name]
    target_lower = emp_name.strip().lower()
    for k, v in all_profiles.items():
        if str(k).strip().lower() == target_lower:
            return k, v
    return emp_name, {}

def save_profiles(profiles):
    try:
        http.put(f"{FIREBASE_URL}/profiles.json", json=profiles, timeout=10)
        load_profiles.clear()
    except Exception as e:
        st.error(f"Failed to save profile to cloud: {e}")

@st.cache_data(ttl=300, show_spinner=False)
def load_salary_history_keys():
    try:
        res = http.get(f"{FIREBASE_URL}/salary_history.json?shallow=true", timeout=10)
        if res.status_code == 200 and isinstance(res.json(), dict):
            return list(res.json().keys())
    except Exception:
        pass
    return []

@st.cache_data(ttl=300, show_spinner=False)
def load_salary_history(emp_name):
    if not emp_name:
        return pd.DataFrame()
    emp_key = get_emp_key(emp_name)

    def _raw_to_df(raw):
        if isinstance(raw, dict):
            rows = [v for v in raw.values() if isinstance(v, dict)]
        elif isinstance(raw, list):
            rows = [v for v in raw if isinstance(v, dict)]
        else:
            rows = []
        return pd.DataFrame(rows)

    try:
        res = http.get(f"{FIREBASE_URL}/salary_history/{requests.utils.quote(emp_key)}.json", timeout=10)
        if res.status_code == 200 and res.json():
            return _raw_to_df(res.json())
        for k in load_salary_history_keys():
            if str(k).strip().lower() == emp_key.lower():
                res2 = http.get(f"{FIREBASE_URL}/salary_history/{requests.utils.quote(str(k))}.json", timeout=10)
                if res2.status_code == 200 and res2.json():
                    return _raw_to_df(res2.json())
    except Exception:
        pass
    return pd.DataFrame()

def save_salary_history(emp_name, df):
    emp_key = get_emp_key(emp_name)
    try:
        records = json.loads(df.to_json(orient='records'))
        http.put(f"{FIREBASE_URL}/salary_history/{requests.utils.quote(emp_key)}.json", json=records, timeout=10)
        load_salary_history.clear()
        load_salary_history_keys.clear()
    except Exception as e:
        st.error(f"Error saving salary history to cloud: {e}")

def delete_salary_history(emp_name):
    emp_key = get_emp_key(emp_name)
    try:
        http.delete(f"{FIREBASE_URL}/salary_history/{requests.utils.quote(emp_key)}.json", timeout=10)
        for k in load_salary_history_keys():
            if str(k).strip().lower() == emp_key.lower() and k != emp_key:
                http.delete(f"{FIREBASE_URL}/salary_history/{requests.utils.quote(str(k))}.json", timeout=10)
        load_salary_history.clear()
        load_salary_history_keys.clear()
    except Exception as e:
        st.error(f"Error deleting salary history: {e}")

def format_mins_to_hrs(val):
    try:
        if pd.isna(val):
            return "0:00"
        v = int(float(val))
        return f"{v // 60}:{v % 60:02d}"
    except Exception:
        return str(val)

def reorder_salary_columns(df):
    if df.empty:
        return df
    desired_cols = [
        "Date", "Name", "Month", "Year", "CTC", "Working Hrs", "Present Hrs",
        "Late Hrs", "Out Hrs", "OT Hrs", "Final Present Hrs", "Total Pay Hrs",
        "Opening PL", "PL Used", "PL Balance", "OT Salary", "Net Salary",
        "In Hand Salary", "Food", "Gratuity", "PT", "TDS", "ESIC",
        "Advance", "Bonus", "Difference"
    ]
    existing_cols = [col for col in desired_cols if col in df.columns]
    remaining_cols = [col for col in df.columns if col not in existing_cols]
    return df[existing_cols + remaining_cols]

def clean_legacy_salary_columns(df):
    if df.empty:
        return df
    df = df.copy()
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
            df[col] = df[col].apply(lambda x: format_mins_to_hrs(x) if str(x).replace('.0', '').isdigit() else str(x))

    if 'Final Present Hrs' in df.columns:
        df['Final Present Hrs'] = df['Final Present Hrs'].astype(str).str.replace('h ', ':').str.replace('m', '')

    if 'Opening PL' not in df.columns:
        df['Opening PL'] = 0.0
    if 'In Hand Salary' not in df.columns:
        df['In Hand Salary'] = 0.0
    if 'Total Pay Hrs' not in df.columns:
        df['Total Pay Hrs'] = ""
    if 'LWP' not in df.columns:
        df['LWP'] = 0.0

    df = df.loc[:, ~df.columns.duplicated()]
    return reorder_salary_columns(df)

def recalculate_future_pl(df, start_index):
    for i in range(start_index + 1, len(df)):
        prev_balance = int(float(df.at[df.index[i - 1], 'PL Balance']))
        used_pl_current = int(float(df.at[df.index[i], 'PL Used']))
        new_opening = prev_balance + 1
        new_balance = new_opening - used_pl_current
        df.at[df.index[i], 'Opening PL'] = new_opening
        df.at[df.index[i], 'PL Balance'] = new_balance
    return df

def fetch_attendance_totals_for_salary(emp_name, month_name, year):
    sheet_name = f"{month_name}'{year}"
    if sheet_name not in st.session_state.cached_data:
        st.session_state.cached_data[sheet_name] = load_data(sheet_name)
    df_att = st.session_state.cached_data[sheet_name]

    total_reg_mins, total_ot_mins, total_late_mins, total_out_mins_att, pl_days = 0, 0, 0, 0, 0

    if not df_att.empty and emp_name:
        df_emp = df_att[df_att["Employee Name"].astype(str).str.strip().str.lower() == emp_name.strip().lower()]
        for _, row in df_emp.iterrows():
            h, m = parse_hm_tuple(row.get("Total Hours", "00:00"))
            total_reg_mins += (h * 60) + m

            h, m = parse_hm_tuple(row.get("OT Hours", "00:00"))
            total_ot_mins += (h * 60) + m

            h, m = parse_hm_tuple(row.get("Late Hours", "00:00"))
            total_late_mins += (h * 60) + m

            h, m = parse_hm_tuple(row.get("Out Hours", "00:00"))
            total_out_mins_att += (h * 60) + m

            if str(row.get("Status", "")).strip() == "PL":
                pl_days += 1

    return {
        "reg_h": total_reg_mins // 60, "reg_m": total_reg_mins % 60,
        "ot_h": total_ot_mins // 60, "ot_m": total_ot_mins % 60,
        "late_h": total_late_mins // 60, "late_m": total_late_mins % 60,
        "out_h": total_out_mins_att // 60, "out_m": total_out_mins_att % 60,
        "pl_days": pl_days
    }

@st.cache_data(show_spinner=False)
def get_company_logo_path():
    logo_url = "https://www.laxmidiamond.com/images/logo.png"
    logo_path = "temp_logo.png"
    if not os.path.exists(logo_path):
        try:
            res = http.get(logo_url, timeout=4)
            if res.status_code == 200:
                with open(logo_path, "wb") as f:
                    f.write(res.content)
        except Exception:
            return None
    return logo_path if os.path.exists(logo_path) else None

@st.cache_data(show_spinner=False)
def generate_excel_slip(slip_data, emp_name, month_str, year_val):
    if not HAS_XLSXWRITER:
        return None
    sd = slip_data
    slip_df = pd.DataFrame({
        "Label": [
            "CTC Salary", "Gratuity", "Bonus", "Actual Salary",
            "Working Hrs", "Pay Hrs", "PL Used",
            "OT Hrs", "Late Hrs", "Out Hrs", "Total Pay Hrs",
            "PT", "PF", "ESI", "TDS", "Loan", "Food", "LWP",
            "PL Balance", "Pay Salary", "OT Salary", "In Hand Salary", "Bank Salary", "Diff"
        ],
        "Value": [
            sd['ctc'], sd['gratuity'], sd['bonus'], sd['actual_salary'],
            sd['work_hrs_str'], sd['present_hrs'], sd['pl_used'],
            sd['ot_hrs'], sd['late_hrs'], sd['out_hrs'], sd['pay_hrs'],
            sd['pt'], "-", sd['esic'] if sd['esic'] else "-", sd['tds'] if sd['tds'] else "-",
            sd['advance'], sd['food'], sd.get('lwp_val', 0.0), sd['pl_balance'],
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

        currency_labels = ["CTC Salary", "Bonus", "Gratuity", "Actual Salary", "PT", "PF", "ESI", "Loan", "Food", "LWP", "Bank Salary", "Diff"]
        total_rows = len(slip_df)

        for row_num, (lbl, val) in enumerate(zip(slip_df['Label'], slip_df['Value'])):
            if row_num == 0:
                dict_col0 = base_header_left.copy()
            elif lbl in ["Pay Salary", "In Hand Salary"]:
                dict_col0 = base_pay_label_left.copy()
            elif lbl == "OT Salary":
                dict_col0 = base_ot_label_left.copy()
            else:
                dict_col0 = base_label_left.copy()

            dict_col0['border'] = 1
            if row_num == 0:
                dict_col0['top'] = 2
            if row_num == total_rows - 1:
                dict_col0['bottom'] = 2
            dict_col0['left'] = 2
            worksheet.write(row_num, 0, lbl, workbook.add_format(dict_col0))

            if row_num == 0:
                dict_col1 = base_header_center.copy()
            elif lbl == "Working Hrs":
                dict_col1 = base_val_yellow.copy()
            elif lbl in ["Pay Hrs", "PL Used", "Total Pay Hrs"]:
                dict_col1 = base_val_green.copy()
            elif lbl in ["Pay Salary", "In Hand Salary"]:
                dict_col1 = base_pay_val_center.copy()
            elif lbl == "OT Salary":
                dict_col1 = base_ot_val_center.copy()
            elif lbl == "Diff":
                diff_val = float(val) if val != "-" else 0
                if diff_val > 0:
                    dict_col1 = base_diff_pos_red.copy()
                elif diff_val < 0:
                    dict_col1 = base_diff_neg_green.copy()
                else:
                    dict_col1 = base_diff_zero.copy()
            elif lbl == "TDS" and val != "-":
                dict_col1 = base_val_curr_tds.copy()
            elif lbl in currency_labels and val != "-":
                dict_col1 = base_val_curr.copy()
            else:
                dict_col1 = base_val_text.copy()

            dict_col1['border'] = 1
            if row_num == 0:
                dict_col1['top'] = 2
            if row_num == total_rows - 1:
                dict_col1['bottom'] = 2
            dict_col1['right'] = 2
            worksheet.write(row_num, 1, val, workbook.add_format(dict_col1))

    return output.getvalue()

@st.cache_data(show_spinner=False)
def generate_pdf_slip(slip_data, emp_name, month_str, year_val, profile=None):
    if not HAS_FPDF:
        return None
    sd = slip_data
    if profile is None:
        profile = {}

    emp_code = profile.get("emp_code", "-")
    department = profile.get("department", "-")
    designation = profile.get("designation", "-")
    doj = profile.get("doj", "-")
    dob = profile.get("dob", "-")
    pan_no = profile.get("pan_no", "-")
    pf_no = profile.get("pf_no", "-")
    uan_no = profile.get("uan", "-")
    esi_no = profile.get("esi_no", "-")
    bank_name = profile.get("bank_name", "-")
    bank_ac = profile.get("bank_ac", "-")

    month_num = MONTH_DICT.get(month_str, 1)
    month_days_val = calendar.monthrange(int(year_val), month_num)[1]
    sundays = sum(1 for week in calendar.monthcalendar(int(year_val), month_num) if week[6] != 0)

    paid_holiday_val = 0
    working_days_val = month_days_val - sundays - paid_holiday_val

    try:
        h = int(sd['present_hrs'].split(':')[0])
        m = int(sd['present_hrs'].split(':')[1])
        total_present_hrs = h + (m / 60.0)
        days_present_val = total_present_hrs / 10.0
        days_present_str = f"{days_present_val:g}"
    except Exception:
        days_present_val = 0.0
        days_present_str = "0"

    days_absent_val = max(0, working_days_val - int(days_present_val))

    basic_salary = sd['ctc'] * 0.60
    da, hra, ca, ea, ma = 0.00, 0.00, 0.00, 0.00, 0.00
    gross_salary = sd['actual_salary'] + sd['ot_sal']

    pf_fund = 0.00
    esi_cont = 0.00
    lwp_fund = sd.get('lwp_val', 0.0)

    total_deduct = sd['pt'] + sd['tds'] + sd['advance'] + sd['food'] + pf_fund + esi_cont + lwp_fund
    net_salary = gross_salary - total_deduct

    sr_no = f"{year_val}{month_str}-12345"
    adv_bonus = 0.00

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_margins(10, 10, 10)

    logo_path = get_company_logo_path()
    if logo_path:
        try:
            pdf.image(logo_path, x=10, y=10, w=35)
        except Exception:
            pdf.set_xy(10, 10)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(35, 15, "LAXMI", border=1, align='C')
    else:
        pdf.set_xy(10, 10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(35, 15, "LAXMI", border=1, align='C')

    pdf.set_xy(45, 10)
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(192, 7, "LAXMI DIAMOND PVT. LTD.(SURAT)", ln=1, align='C')

    pdf.set_font("Arial", '', 10)
    pdf.set_x(45)
    pdf.cell(192, 5, "Nr. Gajera Circle, Katargam Fulpada Road, Katargam, Surat.", ln=1, align='C')
    pdf.set_font("Arial", 'B', 10)
    pdf.set_x(45)
    pdf.cell(192, 5, "(Minimum Wages Act. Rule 25-2)", ln=1, align='C')

    pdf.set_xy(237, 10)
    pdf.set_font("Arial", '', 10)
    pdf.cell(40, 5, "(S)", border=0, align='C', ln=1)
    pdf.set_x(237)
    pdf.set_font("Arial", '', 9)
    pdf.cell(40, 4, "SIGHTHOLDER", border=0, align='C', ln=1)
    pdf.set_x(237)
    pdf.set_font("Arial", '', 4.5)
    pdf.cell(40, 3, "OF THE DE BEERS GROUP OF COMPANIES", border=0, align='C', ln=1)

    pdf.ln(2)
    pdf.rect(10, 9, 277, 18)

    pdf.set_xy(10, 27)
    pdf.set_font("Arial", 'B', 10)

    emp_display = f"Employee's Name : {emp_name.upper()}"
    if emp_code != "-":
        emp_display += f" ({emp_code})"

    pdf.cell(277, 7, emp_display, border=1, ln=1)
    pdf.cell(138.5, 7, f"Department : {department}", border='L', align='L')
    pdf.cell(138.5, 7, f"Designation : {designation}", border='R', align='L', ln=1)

    y = pdf.get_y()
    pdf.line(10, y, 287, y)

    pdf.cell(92, 7, f"Date of Joining : {doj}", border='L')
    pdf.cell(92, 7, f"Date of Birth : {dob}", border=0)
    pdf.cell(93, 7, f"PAN : {pan_no}", border='R', ln=1)

    y = pdf.get_y()
    pdf.line(10, y, 287, y)

    pdf.set_font("Arial", 'B', 9)
    pdf.cell(50, 7, "Section : Pricing", border='LRT')
    pdf.cell(85, 7, "Earning", border='LRT')
    pdf.cell(85, 7, "Deduction", border='LRT')
    pdf.cell(57, 7, "", border='LRT', ln=1)

    row_h = 7.5

    def draw_row(c1_lbl, c1_val, c2_lbl, c2_val, c3_lbl, c3_val, c4_lbl, c4_val, is_bold=False, c3_subtext=None):
        curr_y = pdf.get_y()
        pdf.set_font("Arial", 'B' if is_bold else '', 10 if is_bold else 9)

        pdf.cell(32, row_h, c1_lbl, border=1)
        pdf.cell(18, row_h, c1_val, border=1, align='R')

        pdf.cell(55, row_h, c2_lbl, border=1)
        pdf.cell(30, row_h, c2_val, border=1, align='R')

        c3_x = pdf.get_x()
        pdf.cell(55, row_h, "", border=1)
        pdf.set_xy(c3_x, curr_y + 1)
        pdf.cell(55, 3.5, c3_lbl, border=0, align='L')
        if c3_subtext:
            pdf.set_xy(c3_x, curr_y + 4.5)
            pdf.set_font("Arial", '', 4.5)
            pdf.cell(55, 3, c3_subtext, border=0, align='L')
            if not is_bold:
                pdf.set_font("Arial", '', 9)
        pdf.set_xy(c3_x + 55, curr_y)
        pdf.cell(30, row_h, c3_val, border=1, align='R')

        if c4_lbl != "MERGE_DISCLAIMER":
            pdf.cell(27, row_h, c4_lbl, border=1)
            c4_val_x = pdf.get_x()

            if c4_lbl == "Sr No":
                pdf.set_font("Arial", '', 8.5)
                pdf.cell(30, row_h, c4_val, border=1, align='C')
                if not is_bold:
                    pdf.set_font("Arial", '', 9)
            elif c4_lbl == "Bank Name":
                name_str = str(c4_val).strip()
                pdf.cell(30, row_h, "", border=1)
                if len(name_str) > 13:
                    pdf.set_font("Arial", '', 5.5)
                    pdf.set_xy(c4_val_x, curr_y + 1.5)
                    pdf.multi_cell(30, 2.5, name_str, border=0, align='C')
                else:
                    pdf.set_font("Arial", '', 8)
                    pdf.set_xy(c4_val_x, curr_y)
                    pdf.cell(30, row_h, name_str, border=0, align='R')
                if not is_bold:
                    pdf.set_font("Arial", '', 9)
            elif c4_lbl == "Bank A/c. No.":
                pdf.set_font("Arial", '', 8)
                pdf.set_xy(c4_val_x, curr_y)
                pdf.cell(30, row_h, c4_val, border=1, align='R')
                if not is_bold:
                    pdf.set_font("Arial", '', 9)
            else:
                pdf.set_xy(c4_val_x, curr_y)
                pdf.cell(30, row_h, c4_val, border=1, align='R')

        pdf.set_xy(10, curr_y + row_h)

    draw_row("Working Days", str(working_days_val), "Basic Salary", f"{basic_salary:,.2f}", "Provident Fund", f"{pf_fund:,.2f}", "Sr No", sr_no)
    draw_row("Present Days", days_present_str, "D.A.", f"{da:,.2f}", "E.S.I Contribution", f"{esi_cont:,.2f}", "Month", f"{month_str}-{year_val}")
    draw_row("Paid Holiday", str(paid_holiday_val), "HRA", f"{hra:,.2f}", "Professional Tax", f"{sd['pt']:,.2f}", "P.F. No.", pf_no)
    draw_row("Week Off", str(sundays), "C.A.", f"{ca:,.2f}", "T.D.S", f"{sd['tds']:,.2f}", "UAN", uan_no)
    draw_row("Days Absent", str(days_absent_val), "E.A.", f"{ea:,.2f}", "LWP", f"{lwp_fund:,.2f}", "E.S.I. No.", esi_no, c3_subtext="(Leave Without Pay)")
    draw_row("PL", str(sd['pl_used']), "M.A.", f"{ma:,.2f}", "Other/Adv./Loan", f"{sd['advance']:,.2f}", "Bank Name", bank_name)
    draw_row("Month Days", str(month_days_val), "OT Salary", f"{sd['ot_sal']:,.2f}", "Food Charge", f"{sd['food']:,.2f}", "Bank A/c. No.", bank_ac)
    draw_row("Actual Salary", f"{sd['actual_salary']:,.2f}", "Gross Salary", f"{gross_salary:,.2f}", "Total Deduction", f"{total_deduct:,.2f}", "Net Salary", f"{net_salary:,.2f}", is_bold=True)

    pdf.set_font("Arial", '', 9)
    pdf.cell(50, row_h, "", border=1)
    pdf.cell(85, row_h, "", border=1)
    pdf.cell(85, row_h, "", border=1)
    pdf.cell(27, row_h, "Adv agst Bonus", border=1)
    pdf.cell(30, row_h, f"{adv_bonus:,.2f}", border=1, align='R')
    pdf.ln()

    curr_y = pdf.get_y()
    pdf.set_xy(230, curr_y)
    pdf.set_font("Arial", 'I', 7.5)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(57, 4.5, "This is computer generated slip hence signature is not required.", border=1, align='C')
    pdf.set_text_color(0, 0, 0)

    pdf.set_y(curr_y + 12)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(277, 5, "Company's Details : P.F Code : GJ/SRT/30549      E.S.I.C Code : 39000207770000910    PAN : AABCL1815G    TAN : SRTL00591D", border=0, align='L')
    pdf.ln(4.5)
    pdf.set_font("Arial", '', 7)
    pdf.cell(277, 4, "DA - Dearness Allowance, HRA - House Rent Allowance, CA - Conveyance Allowance, EA - Education Allowance, WA - Washing Allowance, TDS - Tax Deducted At Source", border=0, align='L')

    pdf_out = pdf.output(dest='S')
    return bytes(pdf_out) if isinstance(pdf_out, (bytes, bytearray)) else pdf_out.encode('latin1')

# ==========================================
# SESSION STATE & AUTHENTICATION LOGIC
# ==========================================
current_month_str = get_sheet_name(get_ist_today())

if 'current_user' not in st.session_state:
    st.session_state.current_user = "-- Select Employee --"
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'session_token' not in st.session_state:
    st.session_state.session_token = None

# Auto-restore session after browser refresh using ?sid= token
if not st.session_state.is_logged_in:
    restored = try_restore_cloud_session()
    if restored:
        st.session_state.current_user, st.session_state.user_role, st.session_state.session_token = restored
        st.session_state.is_logged_in = True

def logout():
    tok = st.session_state.get("session_token") or get_query_param("sid")
    delete_cloud_session(tok)
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.session_state.current_user = "-- Select Employee --"
    st.session_state.is_logged_in = False
    st.session_state.user_role = None
    st.session_state.session_token = None
    st.session_state.pop("active_nav_tab", None)
    st.session_state.pop("synced_emp_sig", None)
    st.session_state.pop("synced_date_sig", None)
    st.session_state['sal_calc_result'] = None

is_admin_unlocked = (st.session_state.is_logged_in and st.session_state.user_role == "Admin")
is_employee_unlocked = (st.session_state.is_logged_in and st.session_state.user_role == "Employee")

if 'last_edited' not in st.session_state:
    st.session_state.last_edited = None
if 'form_reset_counter' not in st.session_state:
    st.session_state.form_reset_counter = 0
if 'sal_form_key' not in st.session_state:
    st.session_state.sal_form_key = 0
if 'sal_calc_result' not in st.session_state:
    st.session_state.sal_calc_result = None
if 'flash_msg' not in st.session_state:
    st.session_state.flash_msg = ""
if 'cached_data' not in st.session_state:
    st.session_state.cached_data = {}
if 'cached_holidays' not in st.session_state:
    st.session_state.cached_holidays = None
if 'edit_row' not in st.session_state:
    st.session_state.edit_row = None
if 'del_row' not in st.session_state:
    st.session_state.del_row = None
if 'edit_emp' not in st.session_state:
    st.session_state.edit_emp = None
if 'del_emp' not in st.session_state:
    st.session_state.del_emp = None
if 'filter_month_dash' not in st.session_state:
    st.session_state.filter_month_dash = current_month_str

# ==========================================
# UI STYLING (DESKTOP UNCHANGED + MOBILE-FIRST + SMOOTH SCROLL)
# ==========================================
st.markdown("""<style>
/* --- SINGLE SMOOTH SCROLL CONTAINER FIX (NO STUCK SCROLL / NO PULL-TO-REFRESH HIJACK) --- */
html, body {
    overscroll-behavior-y: none !important;
    overflow: hidden !important;
    height: 100% !important;
}
.stApp, [data-testid="stAppViewContainer"] {
    overflow: hidden !important;
    overscroll-behavior-y: none !important;
    height: 100% !important;
}
[data-testid="stMain"], section.main {
    height: 100vh !important;
    height: 100dvh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    -webkit-overflow-scrolling: touch !important;
    overscroll-behavior-y: contain !important;
}
.block-container {
    overflow: visible !important;
    height: auto !important;
}
[data-testid="stDataFrame"] canvas,
[data-testid="stDataFrame"] div,
[data-testid="stTable"] {
    touch-action: pan-x pan-y !important;
    overscroll-behavior: contain !important;
}
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
    color: var(--text-color);
    font-weight: 600;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 1rem;
    animation: instantHide 0s 5s forwards;
}
.auto-hide-error {
    background-color: rgba(255, 43, 43, 0.2);
    border: 1px solid rgba(255, 43, 43, 0.5);
    color: var(--text-color);
    font-weight: 600;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 1rem;
    animation: instantHide 0s 5s forwards;
}
div[data-testid="InputInstructions"] {
    display: none !important;
}
div[data-testid="stFormSubmitButton"] button {
    position: relative !important;
    top: -5px !important;
    height: 40px !important;
    min-height: 40px !important;
}
/* --- CLEAN UNDERLINE NAVIGATION TABS (GREEN ACTIVE) --- */
[class*="st-key-nav_idle_"] button,
[class*="st-key-nav_active_"] button {
    background-color: transparent !important;
    border: none !important;
    border-radius: 0px !important;
    padding: 6px 4px 10px 4px !important;
    box-shadow: none !important;
    min-height: 0px !important;
    height: auto !important;
    transition: all 0.2s ease !important;
}
[class*="st-key-nav_idle_"] button {
    border-bottom: 3px solid transparent !important;
    opacity: 0.72 !important;
    color: var(--text-color) !important;
}
[class*="st-key-nav_idle_"] button:hover {
    opacity: 1 !important;
    border-bottom: 3px solid rgba(46, 204, 113, 0.5) !important;
    color: var(--text-color) !important;
}
[class*="st-key-nav_idle_"] button:focus {
    box-shadow: none !important;
}
[class*="st-key-nav_active_"] button,
[class*="st-key-nav_active_"] button:hover,
[class*="st-key-nav_active_"] button:focus {
    border-bottom: 3px solid #2ecc71 !important;
    opacity: 1 !important;
    color: var(--text-color) !important;
    box-shadow: none !important;
}
[class*="st-key-nav_active_"] button p {
    color: var(--text-color) !important;
    font-weight: 700 !important;
}
[class*="st-key-nav_idle_"] button p,
[class*="st-key-nav_active_"] button p {
    font-size: 0.95rem !important;
    white-space: nowrap !important;
    margin: 0 !important;
}

/* ==========================================
   MOBILE-ONLY RESPONSIVE DESIGN (<= 768px)
   (PC / Desktop > 768px is 100% untouched)
   ========================================== */
@media (max-width: 768px) {
    .block-container {
        padding-top: 2.3rem !important;
        padding-left: 0.7rem !important;
        padding-right: 0.7rem !important;
        padding-bottom: 2.5rem !important;
    }
    h1 {
        font-size: 1.4rem !important;
        line-height: 1.25 !important;
        margin-bottom: 0.25rem !important;
    }
    h2 {
        font-size: 1.2rem !important;
    }
    h3 {
        font-size: 1.05rem !important;
    }
    hr {
        margin: 0.6rem 0 !important;
    }
    [data-testid="stColumn"]:has(.sal-vline),
    [data-testid="column"]:has(.sal-vline),
    [data-testid="stColumn"]:not(:has(input, button, select, textarea, table, canvas, [role="combobox"], [data-testid="stWidgetLabel"], [data-testid="stMarkdownContainer"], [data-testid="stMetric"], [data-testid="stDataFrame"], [data-testid="stAlert"], [data-testid="stFileUploader"], [data-testid="stExpander"])),
    [data-testid="column"]:not(:has(input, button, select, textarea, table, canvas, [role="combobox"], [data-testid="stWidgetLabel"], [data-testid="stMarkdownContainer"], [data-testid="stMetric"], [data-testid="stDataFrame"], [data-testid="stAlert"], [data-testid="stFileUploader"], [data-testid="stExpander"])) {
        display: none !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.st-key-hdr_sync_btn) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 8px !important;
        margin-bottom: 6px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.st-key-hdr_sync_btn) > [data-testid="stColumn"]:first-child,
    div[data-testid="stHorizontalBlock"]:has(.st-key-hdr_sync_btn) > [data-testid="column"]:first-child {
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.st-key-hdr_sync_btn) > [data-testid="stColumn"]:not(:first-child),
    div[data-testid="stHorizontalBlock"]:has(.st-key-hdr_sync_btn) > [data-testid="column"]:not(:first-child) {
        flex: 1 1 46% !important;
        min-width: 45% !important;
    }
    .st-key-hdr_sync_btn button,
    .st-key-hdr_logout_btn button {
        min-height: 36px !important;
        height: 36px !important;
        padding: 4px 10px !important;
        font-size: 0.85rem !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-nav_active_"]) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        gap: 16px !important;
        padding: 2px 2px 0px 2px !important;
        margin-bottom: 4px !important;
        scrollbar-width: none !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-nav_active_"])::-webkit-scrollbar {
        display: none !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-nav_active_"]) > [data-testid="stColumn"],
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-nav_active_"]) > [data-testid="column"] {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: max-content !important;
    }
    [class*="st-key-nav_idle_"] button p,
    [class*="st-key-nav_active_"] button p {
        font-size: 0.88rem !important;
    }
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 8px !important;
    }
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"],
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] {
        width: 100% !important;
        min-width: 0 !important;
    }
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"]:nth-child(5),
    div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"]:nth-child(5) {
        grid-column: 1 / -1 !important;
    }
    [data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        padding: 10px 12px !important;
    }
    [data-testid="stMetricLabel"] p {
        font-size: 0.78rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-e_"]) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 8px !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-e_"]) > [data-testid="stColumn"]:first-child,
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-e_"]) > [data-testid="column"]:first-child {
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-e_"]) > [data-testid="stColumn"]:not(:first-child),
    div[data-testid="stHorizontalBlock"]:has([class*="st-key-e_"]) > [data-testid="column"]:not(:first-child) {
        flex: 1 1 45% !important;
        min-width: 45% !important;
    }
    [data-testid="stForm"] [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
    }
    [data-testid="stForm"] [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
    [data-testid="stForm"] [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 48% !important;
        min-width: 0 !important;
    }
    button[data-testid="stNumberInputStepDown"],
    button[data-testid="stNumberInputStepUp"] {
        width: 28px !important;
        padding: 0 !important;
    }
    div[data-testid="stFormSubmitButton"] button,
    [class*="st-key-save_btn_"] button,
    div[data-testid="stDownloadButton"] button {
        width: 100% !important;
        top: 0px !important;
        min-height: 44px !important;
        height: 44px !important;
        margin-top: 6px !important;
    }
    div:has(.login-card-marker) .stButton > button {
        width: 100% !important;
        min-height: 44px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding: 0.65rem !important;
    }
    div[role="radiogroup"] {
        flex-wrap: wrap !important;
        gap: 8px !important;
    }
}
</style>""", unsafe_allow_html=True)

# ==========================================
# MASTER LOGIN SYSTEM
# ==========================================
if not st.session_state.is_logged_in:
    st.markdown("""<style>
div[data-testid="stVerticalBlockBorderWrapper"]:has(.login-card-marker):not(:has(div[data-testid="stVerticalBlockBorderWrapper"] .login-card-marker)),
div[data-testid="stVerticalBlock"]:has(.login-card-marker):not(:has(div[data-testid="stVerticalBlock"] .login-card-marker)):not([data-testid="stVerticalBlockBorderWrapper"] div) {
    border-radius: 20px !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    padding: 35px 30px !important;
    background-color: rgba(255, 255, 255, 0.03) !important;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.45) !important;
}
</style>""", unsafe_allow_html=True)

    st.write("")
    st.write("")
    _, col_login, _ = st.columns([2.5, 5, 2.5])
    with col_login:
        with st.container(border=True):
            st.markdown("<h2 class='login-card-marker' style='text-align: center; margin-top: 0;'>📅 Advanced Attendance & Salary</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; font-size: 1.1rem; opacity: 0.85; margin-bottom: 20px;'>🔒 Please Login to Continue</p>", unsafe_allow_html=True)

            dropdown_options = ["-- Select Employee --", "Administrator"] + st.session_state.emp_list
            login_user = st.selectbox("Select Your Profile", options=dropdown_options, key="login_select")

            if login_user != "-- Select Employee --":
                pwd = st.text_input("🔑 Enter Password", type="password", key="login_pwd")
                if st.button("Unlock", type="primary"):
                    correct_pwd = st.session_state.emp_dict.get(login_user, {}).get("password", "123")
                    if pwd == correct_pwd:
                        role_val = "Admin" if login_user == "Administrator" else "Employee"
                        st.session_state.is_logged_in = True
                        st.session_state.user_role = role_val
                        st.session_state.current_user = login_user
                        st.session_state.session_token = create_cloud_session(login_user, role_val, correct_pwd)
                        st.rerun()
                    else:
                        st.error("❌ Incorrect Password!")
    st.stop()

st.title("📅 Advanced Attendance & Salary Tracker")

if st.session_state.flash_msg:
    st.markdown(f'<div class="auto-hide-success">{st.session_state.flash_msg}</div>', unsafe_allow_html=True)
    st.session_state.flash_msg = ""

# ==========================================
# NAVIGATION MENU (UNDERLINE TABS)
# ==========================================
header_col1, header_col2, header_col3 = st.columns([8, 1, 1], vertical_alignment="center")
with header_col1:
    st.markdown(f"👤 Logged in as: **{st.session_state.current_user}** ({st.session_state.user_role})")
with header_col2:
    if st.button("🔄 Sync", use_container_width=True, key="hdr_sync_btn"):
        st.cache_data.clear()
        st.session_state.cached_data.clear()
        st.session_state.cached_holidays = None
        st.session_state.emp_dict = fetch_employee_dict()
        st.session_state.emp_list = sorted([k for k in st.session_state.emp_dict.keys() if k != "Administrator"])
        st.session_state.flash_msg = "✅ Cloud data synced!"
        st.rerun()
with header_col3:
    if st.button("🚪 Logout", use_container_width=True, key="hdr_logout_btn"):
        logout()
        st.rerun()

if is_admin_unlocked:
    nav_options = ["📝 Add Attendance", "👥 Daily Roster", "🌴 Holiday Calendar", "📊 Dashboard & History", "💰 Salary & Payroll", "⚙️ Manage Employees", "🔑 Change Password"]
else:
    nav_options = ["📝 Add Attendance", "🌴 Holiday Calendar", "📊 Dashboard & History", "💰 Salary & Payroll", "🔑 Change Password"]

if 'active_nav_tab' not in st.session_state or st.session_state.active_nav_tab not in nav_options:
    t_idx = get_query_param("tab")
    if t_idx is not None and str(t_idx).isdigit() and 0 <= int(t_idx) < len(nav_options):
        st.session_state.active_nav_tab = nav_options[int(t_idx)]
    else:
        st.session_state.active_nav_tab = nav_options[0]

nav_weights = [len(opt) + 2 for opt in nav_options]
if len(nav_options) <= 5:
    nav_weights.append(45)
else:
    nav_weights.append(8)

nav_cols = st.columns(nav_weights, gap="small")
for idx, opt in enumerate(nav_options):
    is_active = (st.session_state.active_nav_tab == opt)
    btn_key = f"nav_active_{idx}" if is_active else f"nav_idle_{idx}"
    with nav_cols[idx]:
        if st.button(opt, key=btn_key, use_container_width=True):
            st.session_state.active_nav_tab = opt
            try:
                st.query_params["tab"] = str(idx)
            except Exception:
                pass
            st.rerun()

st.markdown("<hr style='margin: -16px 0 18px 0; border: none; border-top: 1px solid rgba(255, 255, 255, 0.15);'>", unsafe_allow_html=True)
selected_tab = st.session_state.active_nav_tab

# ==========================================
# TAB 1: ADD ATTENDANCE
# ==========================================
if selected_tab == "📝 Add Attendance":
    entry_mode = st.radio("Choose Entry Method:", ["✏️ Manual Entry", "📂 Bulk Upload (Excel/CSV)"], horizontal=True) if is_admin_unlocked else "✏️ Manual Entry"
    if is_admin_unlocked:
        st.divider()

    if entry_mode == "✏️ Manual Entry":
        if is_admin_unlocked:
            col_sel, _ = st.columns([3, 7])
            with col_sel:
                target_emp = st.selectbox("Select Employee to Add Attendance", options=st.session_state.emp_list)
        else:
            target_emp = st.session_state.current_user
            st.markdown(f"### Adding Attendance for: **{target_emp}**")

        now_ist = get_ist_now()
        today_ist = now_ist.date()
        today_sheet = get_sheet_name(today_ist)
        if today_sheet not in st.session_state.cached_data:
            st.session_state.cached_data[today_sheet] = load_data(today_sheet)
        df_month_check = st.session_state.cached_data[today_sheet]
        holidays_dict_curr = get_flat_holiday_dates()

        def _is_emp_shift_done(sub_df, d_obj):
            d_rows = sub_df[sub_df["RealDate"].dt.date == d_obj]
            for _, r in d_rows.iterrows():
                st_val = str(r.get("Status", "Regular"))
                if st_val in ["PL", "LWP", "Absent"]:
                    return True
                outs = [parse_time(t) for t in str(r.get("Out Time", "")).split(',') if t.strip()]
                if outs and max(outs).time() >= time(18, 0):
                    return True
            return False

        emp_sig = (target_emp, st.session_state.form_reset_counter)
        if st.session_state.get("synced_emp_sig") != emp_sig or "manual_entry_date" not in st.session_state:
            default_date = today_ist

            if target_emp and not df_month_check.empty:
                df_emp = df_month_check[df_month_check["Employee Name"].astype(str).str.strip().str.lower() == target_emp.lower()].copy()
                if not df_emp.empty:
                    df_emp["RealDate"] = pd.to_datetime(df_emp["Date"], format="%d/%m/%Y", errors="coerce")
                    df_emp = df_emp.dropna(subset=["RealDate"])

                if not df_emp.empty:
                    latest_date = df_emp["RealDate"].dt.date.max()
                    if latest_date >= today_ist:
                        if _is_emp_shift_done(df_emp, latest_date):
                            default_date = latest_date + timedelta(days=1)
                            while default_date.strftime("%d/%m/%Y") in holidays_dict_curr or default_date.weekday() == 6:
                                default_date += timedelta(days=1)
                        else:
                            default_date = latest_date
                    else:
                        default_date = today_ist

            st.session_state["manual_entry_date"] = default_date
            st.session_state["synced_emp_sig"] = emp_sig

        with st.container(border=True):
            c1, c2, c3, c4, c5, c_blank = st.columns([1.5, 1.5, 1, 1, 1.5, 2.5], vertical_alignment="bottom")
            with c1:
                entry_date = st.date_input("Date", format="DD/MM/YYYY", key="manual_entry_date")

            date_sig = (target_emp, entry_date, st.session_state.form_reset_counter)
            if st.session_state.get("synced_date_sig") != date_sig or "manual_in_time" not in st.session_state or "manual_out_time" not in st.session_state:
                calc_in = time(8, 0)
                calc_out = time(18, 0)

                if target_emp and entry_date:
                    sel_sheet = get_sheet_name(entry_date)
                    if sel_sheet not in st.session_state.cached_data:
                        st.session_state.cached_data[sel_sheet] = load_data(sel_sheet)
                    df_sel_month = st.session_state.cached_data[sel_sheet]

                    if not df_sel_month.empty:
                        sel_date_str = entry_date.strftime("%d/%m/%Y")
                        df_date_emp = df_sel_month[
                            (df_sel_month["Employee Name"].astype(str).str.strip().str.lower() == target_emp.lower()) &
                            (df_sel_month["Date"] == sel_date_str)
                        ]
                        if not df_date_emp.empty:
                            out_list_for_date = []
                            for _, dr in df_date_emp.iterrows():
                                date_stat = str(dr.get("Status", "Regular"))
                                if date_stat not in ["PL", "LWP", "Absent"]:
                                    date_out_str = str(dr.get("Out Time", ""))
                                    out_list_for_date.extend([parse_time(t) for t in date_out_str.split(',') if t.strip()])

                            if out_list_for_date:
                                last_out_for_date = max(out_list_for_date).time()
                                if last_out_for_date > time(0, 0):
                                    calc_in = last_out_for_date
                                    calc_out = time(18, 0) if calc_in < time(18, 0) else calc_in

                st.session_state["manual_in_time"] = calc_in
                st.session_state["manual_out_time"] = calc_out
                st.session_state["manual_status"] = "Regular"
                st.session_state["synced_date_sig"] = date_sig

            with c2:
                entry_status = st.selectbox("Status", ["Regular", "Holiday", "PL", "LWP", "Absent"], key="manual_status")
            with c3:
                in_time = st.time_input("In Time", key="manual_in_time")
            with c4:
                out_time = st.time_input("Out Time", key="manual_out_time")
            with c5:
                submit = st.button("Save Entry", type="primary", key=f"save_btn_{st.session_state.form_reset_counter}")

        if submit:
            if not target_emp:
                st.error("Please select an Employee Name!")
            elif out_time < in_time and entry_status not in ["PL", "LWP", "Absent"]:
                st.error("Out Time cannot be before In Time for a single shift!")
            else:
                target_sheet = get_sheet_name(entry_date)
                if target_sheet not in st.session_state.cached_data:
                    st.session_state.cached_data[target_sheet] = load_data(target_sheet)
                df_month = st.session_state.cached_data[target_sheet].copy()
                day_str = entry_date.strftime("%a")
                date_str = entry_date.strftime("%d/%m/%Y")

                existing_match = df_month[(df_month["Employee Name"].astype(str).str.strip().str.lower() == target_emp.lower()) & (df_month["Date"] == date_str)]
                is_pub_hol = date_str in holidays_dict_curr

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
                            st.error(f"⚠️ Overlap Error: The entered time ({in_t_str} to {out_t_str}) overlaps with an already existing entry!")
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
                        st.session_state.flash_msg = f"✅ Additional punch added for {target_emp} on {date_str}!"
                    else:
                        tot, late, out_e, ot = calculate_times(in_t_str, out_t_str, day_str, entry_status, is_pub_hol)
                        new_entry = pd.DataFrame({
                            "Employee Name": [target_emp],
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
                        st.session_state.flash_msg = f"✅ Record for {target_emp} on {date_str} saved successfully!"

                    st.session_state.filter_month_dash = target_sheet
                    st.session_state.last_edited = f"{target_emp}_{date_str}"
                    st.session_state.form_reset_counter += 1
                    st.rerun()

        # --- USER-WISE PENDING ATTENDANCE TABLE ---
        emps_for_pending = st.session_state.emp_list if is_admin_unlocked else ([target_emp] if target_emp else [])
        pending_rows = []

        for emp_check in emps_for_pending:
            emp_dates_set = set()
            df_e_sub = pd.DataFrame()
            if not df_month_check.empty:
                df_e_sub = df_month_check[
                    df_month_check["Employee Name"].astype(str).str.strip().str.lower() == emp_check.strip().lower()
                ].copy()
                if not df_e_sub.empty:
                    df_e_sub["RealDate"] = pd.to_datetime(df_e_sub["Date"], format="%d/%m/%Y", errors="coerce")
                    df_e_sub = df_e_sub.dropna(subset=["RealDate"])
                    emp_dates_set = set(df_e_sub["RealDate"].dt.date.tolist())

            if emp_dates_set:
                scan_d = min(emp_dates_set)
                while scan_d <= today_ist:
                    is_sun = (scan_d.weekday() == 6)
                    is_hol = (scan_d.strftime("%d/%m/%Y") in holidays_dict_curr)
                    if not is_sun and not is_hol:
                        if scan_d not in emp_dates_set:
                            pending_rows.append({
                                "Employee Name": emp_check,
                                "Pending Date": scan_d.strftime("%d/%m/%Y"),
                                "Day": scan_d.strftime("%a"),
                                "Status": "Pending (Today)" if scan_d == today_ist else "Missing"
                            })
                        elif scan_d == today_ist and not _is_emp_shift_done(df_e_sub, scan_d):
                            pending_rows.append({
                                "Employee Name": emp_check,
                                "Pending Date": scan_d.strftime("%d/%m/%Y"),
                                "Day": scan_d.strftime("%a"),
                                "Status": "Incomplete Shift"
                            })
                    scan_d += timedelta(days=1)
            else:
                is_sun = (today_ist.weekday() == 6)
                is_hol = (today_ist.strftime("%d/%m/%Y") in holidays_dict_curr)
                if not is_sun and not is_hol:
                    pending_rows.append({
                        "Employee Name": emp_check,
                        "Pending Date": today_ist.strftime("%d/%m/%Y"),
                        "Day": today_ist.strftime("%a"),
                        "Status": "Pending (Today)"
                    })

        st.write("")
        st.subheader(f"⏳ Pending Attendance ({today_sheet})")
        pend_col, _ = st.columns([6, 4])
        with pend_col:
            if pending_rows:
                df_pending = pd.DataFrame(pending_rows)
                st.dataframe(df_pending, use_container_width=True, hide_index=True)
            else:
                st.success("✅ All working days up to today are marked!")

    elif entry_mode == "📂 Bulk Upload (Excel/CSV)" and is_admin_unlocked:
        st.subheader("📂 Upload Monthly Excel/CSV")

        col_up1, col_up_blank = st.columns([6, 4])
        with col_up1:
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
                            master_emps = st.session_state.emp_list

                            for date_val, group in grouped:
                                try:
                                    d_obj = pd.to_datetime(date_val, format='%d/%m/%Y', errors='coerce').date()
                                    if pd.isna(d_obj):
                                        continue

                                    sheet_n = get_sheet_name(d_obj)
                                    day_s = d_obj.strftime("%a")
                                    date_s = d_obj.strftime("%d/%m/%Y")
                                    is_pub_hol = date_s in holidays_dict

                                    if sheet_n not in st.session_state.cached_data:
                                        st.session_state.cached_data[sheet_n] = load_data(sheet_n)
                                    df_db = st.session_state.cached_data[sheet_n].copy()
                                    new_rows = []

                                    for _, r in group.iterrows():
                                        ename = str(r['Employee Name']).strip().title()
                                        if ename not in master_emps:
                                            continue

                                        stat = str(r.get('Status', 'Regular')) if pd.notna(r.get('Status')) else 'Regular'
                                        if stat not in ["Regular", "Holiday", "PL", "LWP", "Absent"]:
                                            stat = "Regular"

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

                            st.session_state.form_reset_counter += 1
                            st.session_state.flash_msg = f"✅ Successfully processed {success_count} valid records!"
                            st.rerun()
                except Exception as e:
                    st.error(f"Error reading file: {e}")

# ==========================================
# TAB 2: DAILY ROSTER (ADMIN ONLY)
# ==========================================
elif selected_tab == "👥 Daily Roster" and is_admin_unlocked:
    st.subheader("👥 Daily Roster (Mark all employees for a day)")

    rc1, rc_blank = st.columns([3, 7])
    with rc1:
        roster_date = st.date_input("Select Date for Roster", value=get_ist_today(), format="DD/MM/YYYY", key="roster_date")

    all_emp_list = st.session_state.emp_list
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

            rost_col, rost_blank = st.columns([6, 4])
            with rost_col:
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
                            except Exception:
                                in_t, out_t = "08:00", "18:00"

                        tot, late, out_e_hrs, ot = calculate_times(in_t, out_t, r_day_str, stat, is_pub_hol)
                        new_records.append({
                            "Employee Name": emp_n, "Date": r_date_str, "Day": r_day_str,
                            "In Time": in_t, "Out Time": out_t, "Late Hours": late, "Out Hours": out_e_hrs,
                            "Total Hours": tot, "OT Hours": ot, "Status": stat
                        })

                    if new_records:
                        df_new_roster = pd.DataFrame(new_records)
                        df_r_month = pd.concat([df_r_month, df_new_roster], ignore_index=True)
                        save_data(df_r_month, r_sheet)
                        st.session_state.form_reset_counter += 1
                        st.session_state.flash_msg = f"✅ Daily Roster for {r_date_str} saved successfully!"
                        st.rerun()

# ==========================================
# TAB 3: HOLIDAY CALENDAR
# ==========================================
elif selected_tab == "🌴 Holiday Calendar":
    st.subheader("🌴 Holiday Calendar")
    if st.session_state.cached_holidays is None:
        st.session_state.cached_holidays = load_holidays_data()
    hol_data = st.session_state.cached_holidays

    if is_admin_unlocked:
        st.info("🔓 You have Administrator access to manage holidays.")

        with st.form("add_holiday_form"):
            hc1, hc2, hc3, hc4, hc_blank = st.columns([1.5, 1.5, 2.5, 1.5, 2], vertical_alignment="bottom")
            with hc1:
                f_date = st.date_input("From Date", value=get_ist_today(), format="DD/MM/YYYY")
            with hc2:
                t_date = st.date_input("To Date", value=f_date, format="DD/MM/YYYY")
            with hc3:
                hol_reason = st.text_input("Occasion / Reason", placeholder="e.g. Diwali Holidays")
            with hc4:
                add_hol = st.form_submit_button("➕ Add Holiday", type="primary")

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
            hol_col, hol_blank = st.columns([6, 4])
            with hol_col:
                for hid, hinfo in list(hol_data.items()):
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([3, 3, 1, 1], vertical_alignment="center")
                        c1.write(f"🗓️ **{hinfo['from']}** to **{hinfo['to']}**")
                        c2.write(f"✨ {hinfo['reason']} ({hinfo['days']} Days)")

                        if c3.button("✏️ Edit", key=f"edit_{hid}", use_container_width=True):
                            st.session_state[f"edit_mode_{hid}"] = not st.session_state.get(f"edit_mode_{hid}", False)
                            st.rerun()

                        if c4.button("🗑️ Delete", key=f"del_{hid}", use_container_width=True):
                            del hol_data[hid]
                            save_holidays_data(hol_data)
                            st.session_state.flash_msg = "✅ Holiday entry deleted successfully!"
                            st.rerun()

                        if st.session_state.get(f"edit_mode_{hid}", False):
                            with st.form(f"edit_form_{hid}"):
                                ec1, ec2, ec3, ec4 = st.columns([1.5, 1.5, 2, 1], vertical_alignment="bottom")
                                curr_f = datetime.strptime(hinfo['from'], "%d/%m/%Y").date()
                                curr_t = datetime.strptime(hinfo['to'], "%d/%m/%Y").date()
                                with ec1:
                                    ef_date = st.date_input("From Date", value=curr_f, format="DD/MM/YYYY", key=f"ef_{hid}")
                                with ec2:
                                    et_date = st.date_input("To Date", value=curr_t, format="DD/MM/YYYY", key=f"et_{hid}")
                                with ec3:
                                    ereason = st.text_input("Reason", value=hinfo['reason'], key=f"er_{hid}")
                                with ec4:
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
        st.write("### 📅 Upcoming / Declared Holidays")
        if hol_data:
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

            hol_col, _ = st.columns([6, 4])
            with hol_col:
                st.dataframe(df_hol, use_container_width=True)
        else:
            st.write("No holidays declared yet.")

# ==========================================
# TAB 4: DASHBOARD & HISTORY (PARALLEL FETCH)
# ==========================================
elif selected_tab == "📊 Dashboard & History":
    formatted_name = st.session_state.current_user
    current_month_str = get_sheet_name(get_ist_today())
    all_sheets_raw = get_all_sheet_names()
    if current_month_str not in all_sheets_raw:
        all_sheets_raw.insert(0, current_month_str)

    available_sheets = ["All Months"] + all_sheets_raw

    col_f1, col_f2, col_f_blank = st.columns([2, 3.5, 4.5])
    with col_f1:
        selected_sheet = st.selectbox("Select Month to View", available_sheets, key="filter_month_dash")

    if is_admin_unlocked:
        with col_f2:
            selected_emps = st.multiselect(
                "👤 Select Employee(s)",
                options=st.session_state.emp_list,
                placeholder="All Employees (Select 1 or more...)",
                key="admin_emp_multiselect"
            )
        selected_emp = selected_emps[0] if len(selected_emps) == 1 else "All Employees"
    else:
        selected_emps = [formatted_name]
        selected_emp = formatted_name

    if selected_sheet == "All Months":
        sheets_all = get_all_sheet_names()
        missing_sheets = [s for s in sheets_all if s not in st.session_state.cached_data]
        if missing_sheets:
            holidays_for_par = get_flat_holiday_dates()

            def _fetch_raw_sheet(sht_name):
                try:
                    u = f"{FIREBASE_URL}/{requests.utils.quote(str(sht_name))}.json"
                    r = http.get(u, timeout=10)
                    return sht_name, r.json() if r.status_code == 200 else None
                except Exception:
                    return sht_name, None

            with ThreadPoolExecutor(max_workers=min(8, len(missing_sheets))) as executor:
                fetched_results = list(executor.map(_fetch_raw_sheet, missing_sheets))

            for sht_name, raw_d in fetched_results:
                if raw_d:
                    if isinstance(raw_d, dict):
                        df_p = pd.DataFrame(list(raw_d.values()))
                    else:
                        df_p = pd.DataFrame([row for row in raw_d if row is not None])
                    for col in ATT_COLUMNS:
                        if col not in df_p.columns:
                            if col == "Status":
                                df_p[col] = "Regular"
                            elif col in ["Late Hours", "Out Hours", "Total Hours", "OT Hours"]:
                                df_p[col] = "00:00"
                            elif col == "In Time":
                                df_p[col] = "08:00"
                            elif col == "Out Time":
                                df_p[col] = "18:00"
                            else:
                                df_p[col] = ""
                    for idx_p, row_p in df_p.iterrows():
                        in_t = str(row_p.get("In Time", "08:00"))
                        if pd.isna(row_p.get("In Time")) or in_t.lower() == 'nan':
                            continue
                        try:
                            tot, late, out_e, ot = calculate_times(
                                in_t,
                                str(row_p.get("Out Time", "18:00")),
                                str(row_p.get("Day", "Mon")),
                                str(row_p.get("Status", "Regular")),
                                str(row_p.get("Date", "")) in holidays_for_par
                            )
                            df_p.at[idx_p, "Total Hours"] = tot
                            df_p.at[idx_p, "Late Hours"] = late
                            df_p.at[idx_p, "Out Hours"] = out_e
                            df_p.at[idx_p, "OT Hours"] = ot
                        except Exception:
                            pass
                    st.session_state.cached_data[sht_name] = df_p[ATT_COLUMNS]
                else:
                    st.session_state.cached_data[sht_name] = pd.DataFrame(columns=ATT_COLUMNS)

        df_list = []
        for sht in sheets_all:
            df_temp = st.session_state.cached_data.get(sht, pd.DataFrame())
            if not df_temp.empty:
                df_temp = df_temp.copy()
                df_temp["_Original_Sheet"] = sht
                df_temp["_Original_Index"] = df_temp.index
                df_list.append(df_temp)
        df_display = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
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

        if selected_emps:
            lower_emps = [e.strip().lower() for e in selected_emps]
            df_display = df_display[df_display["Employee Name"].astype(str).str.strip().str.lower().isin(lower_emps)]

        final_display_columns = ATT_COLUMNS + ["_Original_Sheet", "_Original_Index"]
        for c in final_display_columns:
            if c not in df_display.columns:
                df_display[c] = ""
        df_display = df_display[final_display_columns]

        st.divider()

    if df_display.empty:
        st.warning("No records found with the current filters.")
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

        tot_lo_hours, tot_lo_mins = divmod(total_late_mins + total_out_mins, 60)

        pl_count = len(df_display[df_display["Status"] == "PL"])
        absent_count = len(df_display[df_display["Status"].isin(["LWP", "Absent"])])

        st.markdown('<div class="summary-container">', unsafe_allow_html=True)
        if len(selected_emps) == 1:
            st.subheader(f"📊 Summary Data ({selected_emps[0]})")
        elif len(selected_emps) > 1:
            st.subheader(f"📊 Summary Data ({len(selected_emps)} Employees Selected)")
        else:
            st.subheader("📊 Master Attendance Data (All Employees)")

        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric(label="🕒 Total Working Hrs", value=f"{reg_hours:02d}:{reg_mins:02d}")
        with m2:
            st.metric(label="🔥 Total OT Hrs", value=f"{ot_hours:02d}:{ot_mins:02d}")
        with m3:
            st.metric(label="⚠️ Total Late/Out Hrs", value=f"{tot_lo_hours:02d}:{tot_lo_mins:02d}")
        with m4:
            st.metric(label="🌴 Paid Leaves (PL)", value=pl_count)
        with m5:
            st.metric(label="❌ Absent (LWP)", value=absent_count)
        st.markdown('</div>', unsafe_allow_html=True)

        st.write("")
        st.divider()

        hol_dict_hl = get_flat_holiday_dates()

        head_col1, head_col2 = st.columns([8, 2], vertical_alignment="center")
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

                    for row_idx in range(4, max_data_row + 1):
                        date_val_xls = worksheet.cell(row=row_idx, column=1).value
                        day_val = worksheet.cell(row=row_idx, column=day_col_idx).value
                        status_val = worksheet.cell(row=row_idx, column=status_col_idx).value

                        is_sunday = (day_val == "Sun")
                        is_holiday = (status_val == "Holiday") or (str(date_val_xls) in hol_dict_hl)

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
                            except Exception:
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
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.markdown("💡 **Tip:** Click Edit or Delete to manage individual records.")

        for index, row in df_display.iterrows():
            status_color = "#5cd65c"

            if row['Day'] == 'Sun':
                status_color = "#ff4c4c"
            elif row['Status'] == 'Holiday' or row['Date'] in hol_dict_hl:
                status_color = "#4da6ff"
            elif row['Status'] in ['PL', 'LWP', 'Absent']:
                status_color = "#ffb366"
            elif st.session_state.last_edited == f"{row['Employee Name']}_{row['Date']}":
                status_color = "#ffff66"

            can_edit = is_admin_unlocked or (is_employee_unlocked and row['Employee Name'].strip().lower() == st.session_state.current_user.strip().lower())

            col_rec, col_blank = st.columns([8, 2])
            with col_rec:
                with st.container(border=True):
                    if can_edit:
                        c_info, c_edit, c_del = st.columns([6, 1, 1], vertical_alignment="center")
                    else:
                        c_info, c_blank_space = st.columns([7, 1], vertical_alignment="center")

                    with c_info:
                        st.markdown(f"""
                        <div style="border-left: 5px solid {status_color}; padding: 4px 15px; border-radius: 2px;">
                            <span style="color: var(--text-color); opacity: 0.7; font-size: 0.9em; margin-right: 15px;">{row['Date']} ({row['Day']})</span>
                            <strong style="font-size: 1.05em; margin-right: 15px; color: var(--text-color);">{row['Employee Name']}</strong>
                            <span style="font-size: 0.95em; color: var(--text-color); opacity: 0.8;">{row['Status']} | In: {row['In Time']} - Out: {row['Out Time']} | Total: <span style="font-weight:bold;">{row['Total Hours']}</span> <span style="font-size: 0.9em;">(OT: {row['OT Hours']} | Late: {row['Late Hours']} | Out: {row['Out Hours']})</span></span>
                        </div>
                        """, unsafe_allow_html=True)

                    if can_edit:
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

                        if st.session_state.edit_row and st.session_state.edit_row["index"] == row['_Original_Index'] and st.session_state.edit_row["sheet"] == row['_Original_Sheet']:
                            st.markdown("---")
                            row_data = st.session_state.edit_row["data"]
                            selected_idx = st.session_state.edit_row["index"]
                            selected_sheet_orig = st.session_state.edit_row["sheet"]

                            with st.form(f"edit_form_hist_{selected_idx}_{selected_sheet_orig}"):
                                ce1, ce2, ce3, ce4, ce5, ce6 = st.columns([1.5, 1.5, 1, 1, 0.8, 0.8], vertical_alignment="bottom")
                                with ce1:
                                    d_obj = datetime.strptime(row_data["Date"], "%d/%m/%Y").date()
                                    e_date = st.date_input("Date", value=d_obj, format="DD/MM/YYYY")
                                with ce2:
                                    def_status = ["Regular", "Holiday", "PL", "LWP", "Absent"]
                                    curr_stat = row_data.get("Status", "Regular")
                                    e_stat = st.selectbox("Status", def_status, index=def_status.index(curr_stat) if curr_stat in def_status else 0)
                                with ce3:
                                    e_in = st.text_input("In Time", value=row_data["In Time"])
                                with ce4:
                                    e_out = st.text_input("Out Time", value=row_data["Out Time"])
                                with ce5:
                                    btn_update = st.form_submit_button("Save", type="primary", use_container_width=True)
                                with ce6:
                                    btn_cancel = st.form_submit_button("Cancel", use_container_width=True)

                                if btn_update:
                                    formatted_e_name = row_data["Employee Name"].strip().title()
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
                                        is_pub_hol = date_str_e in hol_dict_hl
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
                                        st.session_state.form_reset_counter += 1
                                        st.session_state.flash_msg = "✅ Record updated successfully!"
                                        st.rerun()
                                if btn_cancel:
                                    st.session_state.edit_row = None
                                    st.rerun()

                        elif st.session_state.del_row and st.session_state.del_row["index"] == row['_Original_Index'] and st.session_state.del_row["sheet"] == row['_Original_Sheet']:
                            st.markdown("---")
                            st.warning(f"Are you sure you want to delete this record for {row['Employee Name']}?")
                            col_y, col_n = st.columns([1, 10])
                            with col_y:
                                if st.button("Yes", type="primary", key=f"conf_d_{row['_Original_Index']}_{row['_Original_Sheet']}"):
                                    sht = st.session_state.del_row["sheet"]
                                    idx = st.session_state.del_row["index"]
                                    if sht not in st.session_state.cached_data:
                                        st.session_state.cached_data[sht] = load_data(sht)
                                    df_orig = st.session_state.cached_data[sht].copy()
                                    df_orig = df_orig.drop(idx, errors='ignore')
                                    save_data(df_orig, sht)

                                    st.session_state.del_row = None
                                    st.session_state.form_reset_counter += 1
                                    st.session_state.flash_msg = "✅ Entry permanently deleted!"
                                    st.rerun()
                            with col_n:
                                if st.button("Cancel", key=f"canc_d_{row['_Original_Index']}_{row['_Original_Sheet']}"):
                                    st.session_state.del_row = None
                                    st.rerun()

# ==========================================
# TAB 5: SALARY & PAYROLL (INTEGRATED HRIS)
# ==========================================
elif selected_tab == "💰 Salary & Payroll":
    all_profiles = load_profiles()

    money_cols = ["CTC", "OT Salary", "Net Salary", "In Hand Salary", "Food", "Gratuity", "PT", "ESIC", "Advance", "Bonus", "Difference"]
    sal_table_config = {col: st.column_config.NumberColumn(format="₹ %,.0f") for col in money_cols}
    sal_table_config["TDS"] = st.column_config.NumberColumn(format="₹ %,.2f")
    for pl_c in ["Opening PL", "PL Used", "PL Balance"]:
        sal_table_config[pl_c] = st.column_config.NumberColumn(format="%d")

    sal_mode = "🧾 Salary Calculator & History"
    if is_admin_unlocked:
        sal_mode = st.radio(
            "Salary Section",
            ["🧾 Salary Calculator & History", "👥 All Employee Profiles (Master)"],
            horizontal=True,
            label_visibility="collapsed",
            key="sal_sub_mode"
        )
        st.divider()

    # --- SUB-MODE A: ADMIN MASTER PROFILES ---
    if sal_mode == "👥 All Employee Profiles (Master)" and is_admin_unlocked:
        st.subheader("👥 All Employee Master Profiles (Cloud Data)")
        if all_profiles:
            df_profs = pd.DataFrame.from_dict(all_profiles, orient='index').reset_index()
            df_profs = df_profs.rename(columns={
                'index': 'Employee Name', 'emp_code': 'Emp Code', 'base_salary': 'Fixed CTC',
                'department': 'Department', 'designation': 'Designation', 'doj': 'DOJ',
                'dob': 'DOB', 'pan_no': 'PAN No', 'pf_no': 'PF No', 'uan': 'UAN',
                'esi_no': 'ESI No', 'bank_name': 'Bank Name', 'bank_ac': 'Bank A/c No'
            })
            st.dataframe(df_profs, use_container_width=True)
            csv_profs = df_profs.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Profile Data (CSV)",
                data=csv_profs,
                file_name="employee_master_data.csv",
                mime="text/csv",
            )
        else:
            st.info("⚠️ No employee profiles found in Cloud Database.")

        st.divider()
        st.subheader("📝 Add / Edit Employee Profile")
        merged_names = st.session_state.emp_list
        with st.container(border=True):
            c_pe, _ = st.columns([3, 7])
            with c_pe:
                target_prof_emp = st.selectbox("Select Employee to Edit Profile:", options=["-- Select Employee --"] + merged_names, key="sal_admin_prof_sel")

            if target_prof_emp != "-- Select Employee --":
                t_key, t_data = find_profile_data(all_profiles, target_prof_emp)
                with st.form("sal_admin_profile_form"):
                    col_s1, col_s2, col_s3 = st.columns(3)
                    with col_s1:
                        p_code = st.text_input("Emp Code", value=t_data.get("emp_code", ""))
                        p_dept = st.text_input("Department", value=t_data.get("department", ""))
                        p_pan = st.text_input("PAN No", value=t_data.get("pan_no", ""))
                        p_bank = st.text_input("Bank Name", value=t_data.get("bank_name", ""))
                    with col_s2:
                        p_salary = st.number_input("Fixed CTC (₹)", value=float(t_data.get("base_salary", 0.0)), step=500.0)
                        p_desig = st.text_input("Designation", value=t_data.get("designation", ""))
                        p_uan = st.text_input("UAN", value=t_data.get("uan", ""))
                        p_ac = st.text_input("Bank A/c No", value=t_data.get("bank_ac", ""))
                    with col_s3:
                        p_doj = st.text_input("Date of Joining", value=t_data.get("doj", ""))
                        p_dob = st.text_input("Date of Birth", value=t_data.get("dob", ""))
                        p_pf = st.text_input("PF No", value=t_data.get("pf_no", ""))
                        p_esi = st.text_input("ESI No", value=t_data.get("esi_no", ""))

                    if st.form_submit_button("💾 Save Profile to Cloud", type="primary"):
                        updated_profiles = dict(all_profiles)
                        if t_key != target_prof_emp and t_key in updated_profiles:
                            del updated_profiles[t_key]
                        updated_profiles[target_prof_emp] = {
                            "emp_code": p_code, "base_salary": p_salary, "department": p_dept, "designation": p_desig,
                            "doj": p_doj, "dob": p_dob, "pan_no": p_pan, "pf_no": p_pf,
                            "uan": p_uan, "esi_no": p_esi, "bank_name": p_bank, "bank_ac": p_ac
                        }
                        save_profiles(updated_profiles)
                        st.session_state.flash_msg = f"✅ Cloud Profile for {target_prof_emp} saved successfully!"
                        st.rerun()

    # --- SUB-MODE B: SALARY CALCULATOR, SLIPS & HISTORY ---
    else:
        if is_admin_unlocked:
            sal_emp_opts = st.session_state.emp_list
            c_se1, c_se2 = st.columns([3, 7], vertical_alignment="bottom")
            with c_se1:
                sal_emp_name = st.selectbox("👤 Select Employee for Salary", options=sal_emp_opts, key="sal_emp_select") if sal_emp_opts else ""
        else:
            sal_emp_name = st.session_state.current_user

        if not sal_emp_name:
            st.info("No employees found. Please add employees in 'Manage Employees' first.")
        else:
            matched_prof_key, emp_profile_data = find_profile_data(all_profiles, sal_emp_name)
            df_sal_raw = load_salary_history(sal_emp_name)
            has_sal_history = not df_sal_raw.empty

            with st.expander(f"📝 Profile Details — {sal_emp_name}", expanded=False):
                with st.form(f"sal_emp_profile_form_{sal_emp_name}"):
                    p1, p2, p3, p4 = st.columns(4)
                    with p1:
                        p_code = st.text_input("Emp Code", value=emp_profile_data.get("emp_code", ""))
                        p_doj = st.text_input("Date of Joining", value=emp_profile_data.get("doj", ""))
                        p_pf = st.text_input("PF No", value=emp_profile_data.get("pf_no", ""))
                    with p2:
                        p_salary = st.number_input("Fixed CTC (₹)", value=float(emp_profile_data.get("base_salary", 0.0)), step=500.0)
                        p_dob = st.text_input("Date of Birth", value=emp_profile_data.get("dob", ""))
                        p_esi = st.text_input("ESI No", value=emp_profile_data.get("esi_no", ""))
                    with p3:
                        p_dept = st.text_input("Department", value=emp_profile_data.get("department", ""))
                        p_pan = st.text_input("PAN No", value=emp_profile_data.get("pan_no", ""))
                        p_bank = st.text_input("Bank Name", value=emp_profile_data.get("bank_name", ""))
                    with p4:
                        p_desig = st.text_input("Designation", value=emp_profile_data.get("designation", ""))
                        p_uan = st.text_input("UAN", value=emp_profile_data.get("uan", ""))
                        p_ac = st.text_input("Bank A/c No", value=emp_profile_data.get("bank_ac", ""))

                    if st.form_submit_button("💾 Save Profile Details", type="primary"):
                        updated_profiles = dict(all_profiles)
                        if matched_prof_key != sal_emp_name and matched_prof_key in updated_profiles:
                            del updated_profiles[matched_prof_key]
                        updated_profiles[sal_emp_name] = {
                            "emp_code": p_code, "base_salary": p_salary, "department": p_dept, "designation": p_desig,
                            "doj": p_doj, "dob": p_dob, "pan_no": p_pan, "pf_no": p_pf,
                            "uan": p_uan, "esi_no": p_esi, "bank_name": p_bank, "bank_ac": p_ac
                        }
                        save_profiles(updated_profiles)
                        st.session_state.flash_msg = f"✅ Profile updated for {sal_emp_name}!"
                        st.rerun()

            is_new_sal_emp = True
            df_sal_sorted = pd.DataFrame()
            if has_sal_history:
                df_clean = clean_legacy_salary_columns(df_sal_raw)
                if not df_clean.empty:
                    is_new_sal_emp = False
                    df_clean['Month_Num'] = df_clean['Month'].astype(str).str.strip().map(MONTH_DICT)
                    df_sal_sorted = df_clean.sort_values(by=['Year', 'Month_Num']).reset_index(drop=True)

            now_ist_sal = get_ist_now()
            current_m_name = now_ist_sal.strftime("%b")
            current_yr = now_ist_sal.year

            default_m = current_m_name
            default_yr = current_yr

            if not is_new_sal_emp and not df_sal_sorted.empty:
                last_r = df_sal_sorted.iloc[-1]
                last_m = str(last_r.get("Month", "")).strip()
                if last_m in MONTH_ORDER:
                    l_idx = MONTH_ORDER.index(last_m)
                    if l_idx < 11:
                        default_m = MONTH_ORDER[l_idx + 1]
                        default_yr = int(last_r.get("Year", current_yr))
                    else:
                        default_m = 'Jan'
                        default_yr = int(last_r.get("Year", current_yr)) + 1

            def_m_idx = MONTH_ORDER.index(default_m) if default_m in MONTH_ORDER else 0
            kb = f"{st.session_state.sal_form_key}_{sal_emp_name.strip()}"

            with st.container(border=True):
                col_m, col_y, col_unlock, col_emp = st.columns([1.2, 1.2, 1.3, 2.3], vertical_alignment="bottom")
                with col_unlock:
                    unlock_my = st.checkbox("🔓 Edit Any Month", value=False, key=f"sal_unlock_{kb}") if not is_new_sal_emp else True
                with col_m:
                    selected_month = st.selectbox("📅 Month", MONTH_ORDER, index=def_m_idx, disabled=(not is_new_sal_emp and not unlock_my), key=f"sal_m_{kb}")
                with col_y:
                    selected_year = st.number_input("🗓️ Year", min_value=2024, max_value=2030, value=default_yr, disabled=(not is_new_sal_emp and not unlock_my), key=f"sal_y_{kb}")
                with col_emp:
                    st.text_input("Employee Name", value=sal_emp_name, disabled=True)

            prof_ctc = float(emp_profile_data.get("base_salary", 0.0))
            form_data = {
                "CTC": prof_ctc, "Working_Hrs": 0.0, "Food": 0.0, "Gratuity": 0.0,
                "PT": 200.0, "Bonus": 0.0, "Advance": 0.0, "Difference": 0.0,
                "TDS": 0.0, "ESIC": 0.0, "PL_Used": 0
            }
            opening_pl = 0
            is_editing_past = False

            if not is_new_sal_emp and not df_sal_sorted.empty:
                existing_row = df_sal_sorted[
                    (df_sal_sorted['Month'].astype(str).str.strip() == selected_month) &
                    (df_sal_sorted['Year'] == selected_year)
                ]
                if not existing_row.empty:
                    is_editing_past = True
                    r_ex = existing_row.iloc[0]
                    form_data["CTC"] = float(r_ex.get("CTC", 0.0))
                    form_data["Working_Hrs"] = float(r_ex.get("Working Hrs", 0.0))
                    form_data["Food"] = float(r_ex.get("Food", 0.0))
                    form_data["Gratuity"] = float(r_ex.get("Gratuity", 0.0))
                    form_data["PT"] = float(r_ex.get("PT", 200.0))
                    form_data["Bonus"] = float(r_ex.get("Bonus", 0.0))
                    form_data["Advance"] = float(r_ex.get("Advance", 0.0))
                    form_data["Difference"] = float(r_ex.get("Difference", 0.0))
                    form_data["TDS"] = float(r_ex.get("TDS", 0.0))
                    form_data["ESIC"] = float(r_ex.get("ESIC", 0.0))
                    form_data["PL_Used"] = int(float(r_ex.get("PL Used", 0)))
                    opening_pl = int(float(r_ex.get("Opening PL", 0)))
                else:
                    last_r = df_sal_sorted.iloc[-1]
                    form_data["CTC"] = prof_ctc if prof_ctc > 0 else float(last_r.get("CTC", 0.0))
                    form_data["Working_Hrs"] = float(last_r.get("Working Hrs", 0.0))
                    form_data["PT"] = float(last_r.get("PT", 200.0))
                    form_data["TDS"] = float(last_r.get("TDS", 0.0))
                    form_data["ESIC"] = float(last_r.get("ESIC", 0.0))
                    opening_pl = int(float(last_r.get("PL Balance", 0))) + 1

            att_data = fetch_attendance_totals_for_salary(sal_emp_name, selected_month, selected_year)
            default_pl_used = form_data["PL_Used"] if is_editing_past else att_data["pl_days"]

            with st.form(key=f"salary_calc_form_{kb}_{selected_month}_{selected_year}"):
                col1, col_line, col2 = st.columns([1, 0.04, 1])

                with col1:
                    st.subheader("💰 Basic Details (Auto-Synced from Attendance)")
                    c1_1, c1_2 = st.columns(2)
                    with c1_1:
                        ctc_salary = st.number_input("CTC Salary (₹)", value=float(form_data["CTC"]), format="%.0f")

                        p_h_col, p_m_col = st.columns(2)
                        with p_h_col:
                            present_hrs_input = st.number_input("Present Hrs", value=int(att_data["reg_h"]), step=1)
                        with p_m_col:
                            present_mins_input = st.number_input("Present Mins", value=int(att_data["reg_m"]), min_value=0, max_value=59, step=1)

                        if is_new_sal_emp:
                            opening_pl = st.number_input("Opening PL Balance", value=0, step=1)
                        else:
                            st.text_input("Opening PL Balance (Auto)", value=str(int(opening_pl)), disabled=True)

                        used_pl = st.number_input("PL Used", value=int(default_pl_used), step=1)

                    with c1_2:
                        work_hrs = st.number_input("Working Hrs", value=float(form_data["Working_Hrs"]), format="%.0f")

                        l_h_col, l_m_col = st.columns(2)
                        with l_h_col:
                            late_hrs_input = st.number_input("Late Hrs", value=int(att_data["late_h"]), step=1)
                        with l_m_col:
                            late_mins_input = st.number_input("Late Mins", value=int(att_data["late_m"]), min_value=0, max_value=59, step=1)

                        e_h_col, e_m_col = st.columns(2)
                        with e_h_col:
                            out_hrs_input = st.number_input("Out Hrs", value=int(att_data["out_h"]), step=1)
                        with e_m_col:
                            out_mins_input = st.number_input("Out Mins", value=int(att_data["out_m"]), min_value=0, max_value=59, step=1)

                        o_h_col, o_m_col = st.columns(2)
                        with o_h_col:
                            ot_hrs_input = st.number_input("OT Hrs", value=int(att_data["ot_h"]), step=1)
                        with o_m_col:
                            ot_mins_input = st.number_input("OT Mins", value=int(att_data["ot_m"]), min_value=0, max_value=59, step=1)

                with col_line:
                    st.markdown("""<style>
.sal-vline {
    width: 2px;
    background-color: rgba(255, 255, 255, 0.2);
    height: 390px;
    margin: 30px auto 0 auto;
    border-radius: 2px;
}
@media (max-width: 768px) { .sal-vline { display: none; } }
</style>
<div class="sal-vline"></div>""", unsafe_allow_html=True)

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

                st.markdown('<style>[data-testid="stForm"]:has(.sal-btn-center) [data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]),[data-testid="stForm"]:has(.sal-btn-center) .element-container:has([data-testid="stFormSubmitButton"]),[data-testid="stForm"]:has(.sal-btn-center) div:has(> [data-testid="stFormSubmitButton"]),[data-testid="stForm"]:has(.sal-btn-center) [data-testid="stFormSubmitButton"]{width:100%!important;max-width:100%!important;display:flex!important;justify-content:center!important;}</style><span class="sal-btn-center"></span>', unsafe_allow_html=True)
                sal_save_clicked = st.form_submit_button("💾 Calculate & Save Salary to Cloud", type="primary", use_container_width=False)

            if sal_save_clicked:
                final_pl_balance = int(opening_pl) - int(used_pl)
                pl_hours_to_add = int(used_pl) * 10

                total_late_mins = (late_hrs_input * 60) + late_mins_input
                total_out_mins = (out_hrs_input * 60) + out_mins_input
                total_ot_mins = (ot_hrs_input * 60) + ot_mins_input
                total_pay_mins = (present_hrs_input * 60) + present_mins_input
                total_min = max(0, total_pay_mins + int(pl_hours_to_add * 60))

                calc_final_hrs = f"{total_min // 60}:{total_min % 60:02d}"
                late_hrs_str = f"{total_late_mins // 60}:{total_late_mins % 60:02d}"
                early_hrs_str = f"{total_out_mins // 60}:{total_out_mins % 60:02d}"
                ot_hrs_str = f"{total_ot_mins // 60}:{total_ot_mins % 60:02d}"

                total_late_out_mins = total_late_mins + total_out_mins
                deductible_mins = max(0, total_late_out_mins - 120)

                total_pay_hrs_mins = max(0, (total_min + total_ot_mins) - deductible_mins)
                total_pay_hrs_str = f"{total_pay_hrs_mins // 60}:{total_pay_hrs_mins % 60:02d}"

                actual_salary_val = ctc_salary - gratuity - bonus
                hr_rate = actual_salary_val / work_hrs if work_hrs > 0 else 0
                min_rate = hr_rate / 60.0 if work_hrs > 0 else 0

                lwp_val = round(((deductible_mins // 60) * hr_rate) + ((deductible_mins % 60) * min_rate))
                ot_salary = round((total_ot_mins / 60.0) * hr_rate)

                gross_salary_calc = actual_salary_val + ot_salary
                total_deductions_calc = lwp_val + pt_tax + tds + esic + advance + food

                in_hand_salary = round(gross_salary_calc - total_deductions_calc)
                pay_salary_val = in_hand_salary - ot_salary
                bank_salary_val = in_hand_salary + difference

                st.session_state.sal_calc_result = {
                    "name": sal_emp_name, "month": selected_month, "year": selected_year,
                    "in_hand": in_hand_salary, "ot_sal": ot_salary, "pl": final_pl_balance,
                    "slip_data": {
                        "work_hrs_str": f"{int(work_hrs)}:00",
                        "ctc": ctc_salary, "bonus": bonus, "gratuity": gratuity,
                        "actual_salary": actual_salary_val,
                        "present_hrs": f"{int(present_hrs_input)}:{int(present_mins_input):02d}",
                        "pl_used": used_pl, "pl_balance": final_pl_balance,
                        "ot_hrs": ot_hrs_str, "late_hrs": late_hrs_str, "out_hrs": early_hrs_str,
                        "pay_hrs": total_pay_hrs_str,
                        "pt": pt_tax, "tds": tds, "esic": esic, "advance": advance, "food": food,
                        "lwp_val": lwp_val, "difference": difference,
                        "pay_salary_val": pay_salary_val, "ot_sal": ot_salary,
                        "in_hand_salary": in_hand_salary, "bank_salary_val": bank_salary_val
                    }
                }

                new_rec_dict = {
                    "Date": get_ist_now().strftime("%d-%m-%Y"), "Name": sal_emp_name, "Month": selected_month, "Year": selected_year,
                    "CTC": ctc_salary, "Working Hrs": work_hrs, "Present Hrs": f"{int(present_hrs_input)}:{int(present_mins_input):02d}",
                    "Late Hrs": late_hrs_str, "Out Hrs": early_hrs_str, "OT Hrs": ot_hrs_str,
                    "Final Present Hrs": calc_final_hrs, "Total Pay Hrs": total_pay_hrs_str,
                    "Opening PL": opening_pl, "PL Used": used_pl, "PL Balance": final_pl_balance,
                    "OT Salary": ot_salary, "Net Salary": bank_salary_val, "In Hand Salary": in_hand_salary,
                    "Food": food, "Gratuity": gratuity, "PT": pt_tax, "TDS": tds, "ESIC": esic,
                    "Advance": advance, "Bonus": bonus, "Difference": difference, "LWP": lwp_val
                }
                new_rec = reorder_salary_columns(pd.DataFrame([new_rec_dict]))

                df_existing = load_salary_history(sal_emp_name)
                if not df_existing.empty:
                    df_existing = clean_legacy_salary_columns(df_existing)
                    df_existing = df_existing[~((df_existing['Month'].astype(str).str.strip() == selected_month) & (df_existing['Year'] == selected_year))]
                    df_combined = pd.concat([df_existing, new_rec], ignore_index=True)
                    df_combined['Month_Num'] = df_combined['Month'].astype(str).str.strip().map(MONTH_DICT)
                    df_combined = df_combined.sort_values(by=['Year', 'Month_Num']).reset_index(drop=True)

                    updated_idx = df_combined.index[(df_combined['Month'] == selected_month) & (df_combined['Year'] == selected_year)].tolist()[0]
                    if updated_idx < len(df_combined) - 1:
                        df_combined = recalculate_future_pl(df_combined, updated_idx)

                    df_combined = reorder_salary_columns(df_combined.drop(columns=['Month_Num']))
                    save_salary_history(sal_emp_name, df_combined)
                else:
                    save_salary_history(sal_emp_name, new_rec)

                st.session_state.sal_form_key += 1
                st.session_state.flash_msg = f"✅ Salary Saved! {sal_emp_name} ({selected_month}'{selected_year}) | PL Bal: {final_pl_balance} | OT: ₹ {int(ot_salary):,} | LWP: ₹ {int(lwp_val):,} | In Hand: ₹ {int(in_hand_salary):,}"
                st.rerun()

            if st.session_state.get('sal_calc_result') and st.session_state.sal_calc_result['name'] == sal_emp_name:
                res_s = st.session_state.sal_calc_result
                _, dl_c1, dl_c2, _ = st.columns([1, 1, 1, 1])
                with dl_c1:
                    if HAS_XLSXWRITER:
                        excel_slip = generate_excel_slip(res_s['slip_data'], res_s['name'], res_s['month'], res_s['year'])
                        st.download_button(
                            label="📄 Download Excel Slip",
                            data=excel_slip,
                            file_name=f"{res_s['name']}_Salary_Slip_{res_s['month']}_{res_s['year']}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    else:
                        st.warning("⚠️ Add `xlsxwriter` to requirements.txt for Excel Slip.")
                with dl_c2:
                    if HAS_FPDF:
                        _, prof_pdf = find_profile_data(all_profiles, res_s['name'])
                        pdf_slip = generate_pdf_slip(res_s['slip_data'], res_s['name'], res_s['month'], res_s['year'], prof_pdf)
                        st.download_button(
                            label="📕 Download PDF Slip",
                            data=pdf_slip,
                            file_name=f"{res_s['name']}_Salary_Slip_{res_s['month']}_{res_s['year']}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    else:
                        st.warning("⚠️ Add `fpdf` to requirements.txt for PDF Slip.")

            if has_sal_history:
                st.divider()
                st.subheader(f"📂 Salary History: {sal_emp_name}")
                h_df = clean_legacy_salary_columns(df_sal_raw)
                if 'Month' in h_df.columns:
                    h_df['Sort_M'] = h_df['Month'].astype(str).str.strip().map(MONTH_DICT)
                    if 'Year' in h_df.columns:
                        h_df = h_df.sort_values(['Year', 'Sort_M']).drop(columns=['Sort_M']).reset_index(drop=True)
                    else:
                        h_df = h_df.sort_values('Sort_M').drop(columns=['Sort_M']).reset_index(drop=True)
                h_df = reorder_salary_columns(h_df)

                def highlight_sal_cols(col):
                    if col.name == 'Net Salary':
                        return ['background-color: #4a1c1c; color: #ff9999; font-weight: bold'] * len(col)
                    elif col.name == 'In Hand Salary':
                        return ['background-color: #1c4a22; color: #99ff99; font-weight: bold'] * len(col)
                    return [''] * len(col)

                edited_sal_df = st.data_editor(
                    h_df.style.apply(highlight_sal_cols, axis=0),
                    use_container_width=True,
                    num_rows="dynamic",
                    key=f"sal_editor_{sal_emp_name.lower().replace(' ', '_')}",
                    column_config=sal_table_config
                )

                if not h_df.equals(edited_sal_df):
                    save_salary_history(sal_emp_name, edited_sal_df)
                    st.toast("✅ Salary Cloud Record updated!")
                    st.rerun()

                st.write("")
                with st.container(border=True):
                    st.markdown("#### 📥 Download Slip from History")
                    hs1, hs2, hs3, hs_blank = st.columns([2, 0.8, 0.8, 4.4], vertical_alignment="bottom")
                    with hs1:
                        hist_opts = list(dict.fromkeys([
                            f"{str(r.get('Month', '')).strip()} - {int(r.get('Year', current_yr))}"
                            for _, r in h_df.iterrows()
                        ]))
                        sel_hist_opt = st.selectbox("Select Month & Year:", hist_opts, key=f"sal_hist_sel_{sal_emp_name}")

                    if sel_hist_opt:
                        sm, sy = sel_hist_opt.split(" - ")
                        h_row = h_df[(h_df['Month'].astype(str).str.strip() == sm) & (h_df['Year'] == int(sy))].iloc[-1]

                        actual_sal_h = float(h_row.get("CTC", 0)) - float(h_row.get("Bonus", 0)) - float(h_row.get("Gratuity", 0))
                        net_sal_h = float(h_row.get("Net Salary", 0))
                        in_hand_h = float(h_row.get("In Hand Salary", 0))
                        diff_h = float(h_row.get("Difference", 0))
                        ot_sal_h = float(h_row.get("OT Salary", 0))

                        if in_hand_h == 0:
                            pay_sal_h = round(net_sal_h - diff_h - ot_sal_h)
                            in_hand_h = pay_sal_h + ot_sal_h
                        else:
                            pay_sal_h = in_hand_h - ot_sal_h

                        hist_slip_data = {
                            "work_hrs_str": f"{int(float(h_row.get('Working Hrs', 0)))}:00",
                            "ctc": float(h_row.get("CTC", 0)),
                            "bonus": float(h_row.get("Bonus", 0)),
                            "gratuity": float(h_row.get("Gratuity", 0)),
                            "actual_salary": actual_sal_h,
                            "present_hrs": str(h_row.get("Present Hrs", "0:00")).strip(),
                            "pl_used": int(float(h_row.get("PL Used", 0))),
                            "pl_balance": int(float(h_row.get("PL Balance", 0))),
                            "ot_hrs": str(h_row.get("OT Hrs", "0:00")).strip(),
                            "late_hrs": str(h_row.get("Late Hrs", "0:00")).strip(),
                            "out_hrs": str(h_row.get("Out Hrs", "0:00")).strip(),
                            "pay_hrs": str(h_row.get("Total Pay Hrs", h_row.get("Final Present Hrs", "0:00"))).strip(),
                            "pt": float(h_row.get("PT", 0)),
                            "tds": float(h_row.get("TDS", 0)),
                            "esic": float(h_row.get("ESIC", 0)),
                            "advance": float(h_row.get("Advance", 0)),
                            "food": float(h_row.get("Food", 0)),
                            "lwp_val": float(h_row.get("LWP", 0.0)),
                            "difference": diff_h,
                            "pay_salary_val": pay_sal_h,
                            "ot_sal": ot_sal_h,
                            "in_hand_salary": in_hand_h,
                            "bank_salary_val": round(net_sal_h)
                        }

                        with hs2:
                            if HAS_XLSXWRITER:
                                xls_h = generate_excel_slip(hist_slip_data, str(h_row.get("Name", sal_emp_name)), sm, sy)
                                st.download_button(
                                    label="📄 Excel Slip",
                                    data=xls_h,
                                    file_name=f"{sal_emp_name}_Salary_Slip_{sm}_{sy}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True,
                                    key=f"sal_dl_xls_{sal_emp_name}"
                                )
                            else:
                                st.caption("⚠️ Add `xlsxwriter`")
                        with hs3:
                            if HAS_FPDF:
                                pdf_h = generate_pdf_slip(hist_slip_data, str(h_row.get("Name", sal_emp_name)), sm, sy, emp_profile_data)
                                st.download_button(
                                    label="📕 PDF Slip",
                                    data=pdf_h,
                                    file_name=f"{sal_emp_name}_Salary_Slip_{sm}_{sy}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"sal_dl_pdf_{sal_emp_name}"
                                )
                            else:
                                st.caption("⚠️ Add `fpdf`")

# ==========================================
# TAB 6: MANAGE EMPLOYEES (ADMIN ONLY)
# ==========================================
elif selected_tab == "⚙️ Manage Employees" and is_admin_unlocked:
    st.subheader("⚙️ Master Employee Control (Passwords & Details)")
    st.info("💡 Edit employee names, passwords, or details directly in the table below and click 'Save Master Data' at the bottom.")

    with st.form("add_new_emp_form"):
        col_e1, col_e2, col_e3, col_e_blank = st.columns([2.5, 1.5, 1.5, 2.5], vertical_alignment="bottom")
        with col_e1:
            new_emp_name = st.text_input("Enter New Employee Name", placeholder="e.g. Rahul Patel")
        with col_e2:
            new_emp_pwd = st.text_input("Initial Password", value="123")
        with col_e3:
            add_emp_btn = st.form_submit_button("➕ Add Employee", type="primary")

    if add_emp_btn:
        clean_name = new_emp_name.strip().title()
        if not clean_name:
            st.error("⚠️ Please enter a valid name!")
        elif clean_name == "Administrator":
            st.error("⚠️ You cannot add 'Administrator' as an employee.")
        else:
            curr_dict = st.session_state.emp_dict.copy()
            if clean_name not in curr_dict:
                curr_dict[clean_name] = {"password": new_emp_pwd.strip() or "123", "details": ""}
                save_employee_dict(curr_dict)
                st.session_state.flash_msg = f"✅ Employee '{clean_name}' successfully added!"
                st.rerun()
            else:
                st.error("⚠️ Employee already exists!")

    st.divider()

    emp_records = []
    for name, data in st.session_state.emp_dict.items():
        if name != "Administrator":
            emp_records.append({
                "Employee Name": name,
                "Password": data.get("password", "123"),
                "Details/Phone": data.get("details", "")
            })

    if emp_records:
        emp_df = pd.DataFrame(emp_records)
    else:
        emp_df = pd.DataFrame(columns=["Employee Name", "Password", "Details/Phone"])

    edited_emp_df = st.data_editor(
        emp_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Employee Name": st.column_config.TextColumn("Employee Name", required=True),
            "Password": st.column_config.TextColumn("Password (Required)", required=True),
            "Details/Phone": st.column_config.TextColumn("Details/Phone")
        }
    )

    if st.button("💾 Save Master Data", type="primary"):
        new_emp_dict = {"Administrator": st.session_state.emp_dict.get("Administrator", {"password": "1234", "details": "Master Admin"})}
        for _, r in edited_emp_df.iterrows():
            raw_name = r.get("Employee Name", "")
            if pd.isna(raw_name):
                continue
            ename = str(raw_name).strip().title()
            if ename and ename != "Administrator":
                raw_pwd = r.get("Password", "123")
                raw_det = r.get("Details/Phone", "")
                new_emp_dict[ename] = {
                    "password": "123" if pd.isna(raw_pwd) or not str(raw_pwd).strip() else str(raw_pwd).strip(),
                    "details": "" if pd.isna(raw_det) else str(raw_det).strip()
                }
        save_employee_dict(new_emp_dict)
        st.session_state.flash_msg = "✅ All passwords and details saved successfully!"
        st.rerun()

    st.divider()

    # Emergency Data Fixer (Cached on render, live fetch only on submit)
    st.subheader("🛠️ Emergency Data Fixer (Sync Attendance, Profile & Salary History)")
    st.error("⚠️ If you renamed an employee (e.g., 'KP' to 'Krutin Patel'), select the old and new names below to transfer all Attendance, Profile, and Salary History in one click.")

    cached_profs_fix = load_profiles()
    cached_hist_keys = load_salary_history_keys()

    old_name_candidates = sorted(list(set(
        [str(k).strip() for k in cached_hist_keys if k] +
        [str(k).strip() for k in cached_profs_fix.keys() if k] +
        [str(k).strip() for k in st.session_state.emp_list if k]
    )))

    if cached_hist_keys:
        st.caption(f"📌 Saved names currently in Firebase Salary History: **{', '.join(sorted(cached_hist_keys))}**")

    with st.form("fix_data_form"):
        f_col1, f_col2, f_col3 = st.columns([2, 2, 2], vertical_alignment="bottom")
        with f_col1:
            old_sel_fix = st.selectbox("Old Name (Select from Dropdown)", options=["-- Type Manually --"] + old_name_candidates)
            old_manual_fix = st.text_input("Or Type Old Name Manually", placeholder="e.g. KP")
        with f_col2:
            new_sel_fix = st.selectbox("New Name (Employee List)", options=["-- Type Manually --"] + st.session_state.emp_list)
            new_manual_fix = st.text_input("Or Type New Name Manually", placeholder="e.g. Krutin Patel")
        with f_col3:
            fix_submit = st.form_submit_button("🚀 Fix All Data & Transfer History", type="primary", use_container_width=True)

    if fix_submit:
        old_clean = old_manual_fix.strip() if old_manual_fix.strip() else ("" if old_sel_fix == "-- Type Manually --" else old_sel_fix.strip())
        clean_new = new_manual_fix.strip().title() if new_manual_fix.strip() else ("" if new_sel_fix == "-- Type Manually --" else new_sel_fix.strip())

        if not old_clean or not clean_new:
            st.error("⚠️ Both Old Name and New Name are required!")
        elif old_clean == clean_new:
            st.warning("⚠️ Old Name and New Name cannot be the same.")
        else:
            def _raw_to_df_fix(raw):
                if isinstance(raw, dict):
                    return pd.DataFrame([v for v in raw.values() if isinstance(v, dict)])
                elif isinstance(raw, list):
                    return pd.DataFrame([v for v in raw if isinstance(v, dict)])
                return pd.DataFrame()

            # Fetch fresh copies on submit to avoid stale writes
            fresh_profs_fix = {}
            try:
                r_pf = http.get(f"{FIREBASE_URL}/profiles.json", timeout=10)
                if r_pf.status_code == 200 and isinstance(r_pf.json(), dict):
                    fresh_profs_fix = r_pf.json()
            except Exception:
                fresh_profs_fix = dict(cached_profs_fix)

            fresh_hist_keys = []
            try:
                r_hk = http.get(f"{FIREBASE_URL}/salary_history.json?shallow=true", timeout=10)
                if r_hk.status_code == 200 and isinstance(r_hk.json(), dict):
                    fresh_hist_keys = list(r_hk.json().keys())
            except Exception:
                fresh_hist_keys = list(cached_hist_keys)

            success_count = 0
            prof_transferred = False
            sal_records_moved = 0
            sheets_to_check = get_all_sheet_names()

            # Step 1: Fix historical Attendance sheets
            for sheet in sheets_to_check:
                url_sheet = f"{FIREBASE_URL}/{requests.utils.quote(str(sheet))}.json"
                try:
                    res_sheet = http.get(url_sheet, timeout=10)
                    if res_sheet.status_code == 200 and res_sheet.json():
                        sheet_data = res_sheet.json()
                        updated = False

                        if isinstance(sheet_data, dict):
                            for k, v in sheet_data.items():
                                if v and str(v.get("Employee Name", "")).strip().lower() == old_clean.lower():
                                    sheet_data[k]["Employee Name"] = clean_new
                                    updated = True
                            if updated:
                                http.put(url_sheet, json=sheet_data, timeout=10)
                                success_count += 1

                        elif isinstance(sheet_data, list):
                            for i in range(len(sheet_data)):
                                if sheet_data[i] and str(sheet_data[i].get("Employee Name", "")).strip().lower() == old_clean.lower():
                                    sheet_data[i]["Employee Name"] = clean_new
                                    updated = True
                            if updated:
                                http.put(url_sheet, json=sheet_data, timeout=10)
                                success_count += 1
                except Exception:
                    pass

            # Step 2: Migrate password & employee_dict
            curr_dict = st.session_state.emp_dict.copy()
            matched_old_keys = [k for k in curr_dict.keys() if k.strip().lower() == old_clean.lower() and k != "Administrator"]
            for old_key in matched_old_keys:
                old_details = curr_dict[old_key]
                if clean_new not in curr_dict:
                    curr_dict[clean_new] = old_details
                if old_key != clean_new:
                    del curr_dict[old_key]
            if matched_old_keys:
                save_employee_dict(curr_dict)

            # Step 3: Migrate HRIS Profile (/profiles.json) with smart merge
            matched_prof_keys = [k for k in list(fresh_profs_fix.keys()) if str(k).strip().lower() == old_clean.lower()]
            if matched_prof_keys:
                updated_profs = dict(fresh_profs_fix)
                for pk in matched_prof_keys:
                    old_p = updated_profs.get(pk, {})
                    if clean_new in updated_profs and isinstance(updated_profs[clean_new], dict):
                        merged_p = dict(old_p)
                        for fld, val in updated_profs[clean_new].items():
                            if val not in ("", None, 0, 0.0, "-"):
                                merged_p[fld] = val
                        updated_profs[clean_new] = merged_p
                    else:
                        updated_profs[clean_new] = old_p
                    if pk != clean_new:
                        del updated_profs[pk]
                    prof_transferred = True
                save_profiles(updated_profs)

            # Step 4: Migrate HRIS Salary History (/salary_history)
            old_h_key_lower = get_emp_key(old_clean).lower()
            new_h_key = get_emp_key(clean_new)
            matched_hist_keys = [hk for hk in fresh_hist_keys if str(hk).strip().lower() == old_h_key_lower]

            for hk in matched_hist_keys:
                try:
                    res_old_h = http.get(f"{FIREBASE_URL}/salary_history/{requests.utils.quote(str(hk))}.json", timeout=10)
                    if res_old_h.status_code == 200 and res_old_h.json():
                        df_old_h = _raw_to_df_fix(res_old_h.json())
                        if not df_old_h.empty:
                            df_old_h["Name"] = clean_new
                            df_merged = df_old_h
                            if hk != new_h_key:
                                res_new_h = http.get(f"{FIREBASE_URL}/salary_history/{requests.utils.quote(new_h_key)}.json", timeout=10)
                                if res_new_h.status_code == 200 and res_new_h.json():
                                    df_ex_new = _raw_to_df_fix(res_new_h.json())
                                    if not df_ex_new.empty:
                                        df_merged = pd.concat([df_old_h, df_ex_new], ignore_index=True)

                            df_merged = clean_legacy_salary_columns(df_merged)
                            if "Month" in df_merged.columns and "Year" in df_merged.columns:
                                df_merged["Month"] = df_merged["Month"].astype(str).str.strip()
                                df_merged["Year"] = pd.to_numeric(df_merged["Year"], errors="coerce").fillna(get_ist_now().year).astype(int)
                                df_merged = df_merged.drop_duplicates(subset=["Month", "Year"], keep="last")
                                df_merged["_m_sort"] = df_merged["Month"].map(MONTH_DICT).fillna(0)
                                df_merged = df_merged.sort_values(["Year", "_m_sort"]).drop(columns=["_m_sort"]).reset_index(drop=True)

                            save_salary_history(clean_new, df_merged)
                            sal_records_moved = len(df_merged)
                            if hk != new_h_key:
                                http.delete(f"{FIREBASE_URL}/salary_history/{requests.utils.quote(str(hk))}.json", timeout=10)
                except Exception as e:
                    st.error(f"Salary History error for '{hk}': {e}")

            st.session_state.cached_data.clear()
            st.cache_data.clear()
            st.session_state.form_reset_counter += 1
            st.session_state.sal_form_key += 1
            st.session_state.flash_msg = f"✅ Done! '{old_clean}' → '{clean_new}' | Attendance: {success_count} months | Profile: {'Synced' if prof_transferred else 'Not Found'} | Salary History: {sal_records_moved} records transferred!"
            st.rerun()

# ==========================================
# TAB 7: CHANGE PASSWORD (FOR EVERYONE)
# ==========================================
elif selected_tab == "🔑 Change Password":
    st.subheader(f"🔑 Update Password for: **{st.session_state.current_user}**")
    st.markdown("Update your password below. Please do not share your new password with anyone.")

    with st.form("change_pwd_form"):
        cp1, cp2, cp3 = st.columns([1.5, 1.5, 3], vertical_alignment="bottom")
        with cp1:
            old_pwd = st.text_input("Current Password", type="password")
        with cp2:
            new_pwd = st.text_input("New Password", type="password")
        with cp3:
            btn_update_pwd = st.form_submit_button("Update Password", type="primary")

        if btn_update_pwd:
            curr_dict = st.session_state.emp_dict.copy()
            actual_pwd = curr_dict.get(st.session_state.current_user, {}).get("password", "123")

            if old_pwd != actual_pwd:
                st.error("❌ Incorrect Current Password!")
            elif len(new_pwd.strip()) < 3:
                st.error("❌ New password must be at least 3 characters long!")
            elif old_pwd == new_pwd.strip():
                st.warning("⚠️ New password cannot be the same as the current password.")
            else:
                new_pwd_clean = new_pwd.strip()
                curr_dict[st.session_state.current_user]["password"] = new_pwd_clean
                save_employee_dict(curr_dict)
                update_cloud_session_pwd(st.session_state.get("session_token"), new_pwd_clean)
                st.success("✅ Your new password has been successfully updated!")
