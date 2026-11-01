import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
import io
import time as tm
from openpyxl.styles import Alignment, PatternFill, Border, Side, Font
from openpyxl.utils import get_column_letter
import streamlit.components.v1 as components 
import uuid

# ==========================================
# 1. FIREBASE CLOUD DATABASE URL
# ==========================================
FIREBASE_URL = "https://attendence-ec921-default-rtdb.firebaseio.com"

STANDARD_IN = "08:00"
STANDARD_OUT = "18:00"

def get_sheet_name(selected_date):
    return selected_date.strftime("%b'%Y")

def get_all_sheet_names():
    url = f"{FIREBASE_URL}.json?shallow=true"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data:
                return list(data.keys())
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

def get_all_employees():
    url = f"{FIREBASE_URL}.json"
    try:
        response = requests.get(url)
        data = response.json()
        emps = set()
        if data:
            for sheet, records in data.items():
                if isinstance(records, list):
                    for r in records:
                        if r is not None and "Employee Name" in r:
                            emps.add(r["Employee Name"])
                elif isinstance(records, dict):
                    for key, r in records.items():
                        if r is not None and "Employee Name" in r:
                            emps.add(r["Employee Name"])
        valid_emps = [e for e in emps if e != "-"]
        return sorted(list(valid_emps))
    except Exception:
        return []

def load_holidays_data():
    try:
        res = requests.get(f"{FIREBASE_URL}/holidays_list.json")
        if res.status_code == 200 and res.json():
            return res.json()
    except Exception:
        pass
    return {}

def save_holidays_data(data):
    try:
        requests.put(f"{FIREBASE_URL}/holidays_list.json", json=data)
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

def calculate_times(in_time, out_time, day_str, status="Regular", is_public_holiday=False):
    if status in ["PL", "LWP", "Absent"]:
        return "00:00", "00:00", "00:00", "00:00"

    t1 = parse_time(in_time)
    t2 = parse_time(out_time)
    std_in = datetime.strptime(STANDARD_IN, "%H:%M")
    std_out = datetime.strptime(STANDARD_OUT, "%H:%M")
    
    if t2 < t1:
        return "00:00", "00:00", "00:00", "00:00"
        
    total_worked_mins = (t2 - t1).seconds // 60
    
    if day_str == "Sun" or status == "Holiday" or is_public_holiday:
        reg_mins = 0
        ot_mins = total_worked_mins 
        late_mins = 0
        out_early_mins = 0
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
            
        late_mins = max(0, (t1 - std_in).total_seconds() // 60) if t1 > std_in else 0
        out_early_mins = max(0, (std_out - t2).total_seconds() // 60) if t2 < std_out else 0
    
    def mins_to_str(m):
        if m <= 0: return "00:00"
        h, m = divmod(int(m), 60)
        return f"{h:02d}:{m:02d}"
        
    total_hrs = mins_to_str(reg_mins)
    ot_hrs = mins_to_str(ot_mins)
    late_hrs = mins_to_str(late_mins) 
    out_hrs = mins_to_str(out_early_mins) 
    
    return total_hrs, late_hrs, out_hrs, ot_hrs

def load_data(sheet_name):
    columns = ["Employee Name", "Date", "Day", "Status", "In Time", "Out Time", "Late Hours", "Out Hours", "Total Hours", "OT Hours"]
    url = f"{FIREBASE_URL}/{sheet_name}.json"
    holidays_dict = get_flat_holiday_dates()
    
    try:
        response = requests.get(url)
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
    url = f"{FIREBASE_URL}/{sheet_name}.json"
    data = df.to_dict(orient='records')
    try:
        requests.put(url, json=data)
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

if 'last_edited' not in st.session_state: st.session_state.last_edited = None
if 'filter_month' not in st.session_state: st.session_state.filter_month = current_month_str
if 'top_emp_input' not in st.session_state: st.session_state.top_emp_input = ""
if 'form_reset_counter' not in st.session_state: st.session_state.form_reset_counter = 0
if 'flash_msg' not in st.session_state: st.session_state.flash_msg = ""

def on_top_name_change():
    val = st.session_state.top_emp_input.strip()
    if val:
        st.session_state.filter_month = "All Months"
    else:
        st.session_state.filter_month = current_month_str

st.set_page_config(page_title="Advanced Attendance Tracker", layout="wide", page_icon="📅")

components.html(
    """
    <script>
    const doc = window.parent.document;
    if (!doc.getElementById('custom-enter-tab')) {
        let script = doc.createElement('script');
        script.id = 'custom-enter-tab';
        script.innerHTML = `
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    let active = document.activeElement;
                    if (active && active.tagName === 'INPUT') {
                        e.preventDefault(); 
                        let focusable = Array.from(document.querySelectorAll('input:not([disabled]), button:not([disabled])'));
                        let index = focusable.indexOf(active);
                        if (index > -1 && index < focusable.length - 1) {
                            focusable[index + 1].focus();
                        }
                    }
                }
            });
        `;
        doc.head.appendChild(script);
    }
    </script>
    """,
    height=0, width=0
)

st.markdown("""
    <style>
        div[data-baseweb="input"], div[data-testid="stDateInput"], div[data-testid="stTimeInput"] { max-width: 320px; }
        .stDownloadButton button { margin-top: 27px; }
        [data-testid="stMetric"] { background-color: #1e2530; padding: 15px; border-radius: 12px; border: 1px solid #303d4f; }
        div[data-testid="InputInstructions"] { display: none !important; }
        
        /* 🔥 BRAHMASTRA CSS FOR TABS 🔥 */
        button[data-baseweb="tab"] {
            padding: 10px 20px !important;
        }
        button[data-baseweb="tab"] * {
            font-size: 28px !important;
            font-weight: 800 !important;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📅 Advanced Attendance Tracker")

msg_placeholder = st.empty()
has_msg = False
if st.session_state.flash_msg:
    msg_placeholder.success(st.session_state.flash_msg)
    has_msg = True
    st.session_state.flash_msg = "" 

formatted_name = st.session_state.top_emp_input.strip().title()

tab1, tab2, tab3, tab4 = st.tabs(["📝 Add Attendance", "👥 Daily Roster", "🌴 Holiday Calendar", "📊 Dashboard & History"])

with tab1:
    entry_mode = st.radio("Choose Entry Method:", ["✏️ Manual Entry", "📂 Bulk Upload (Excel/CSV)"], horizontal=True)
    st.divider()

    if entry_mode == "✏️ Manual Entry":
        col_input1, col_input2 = st.columns([1.5, 2.5])
        with col_input1:
            st.text_input("Employee Name", placeholder="Please enter name", key="top_emp_input", on_change=on_top_name_change)
        
        formatted_name = st.session_state.top_emp_input.strip().title()

        if formatted_name == "Administrator":
            all_emps = get_all_employees()
            if all_emps: st.caption(f"📝 **Existing Employees:** {', '.join(all_emps)}")

        default_date = date.today()
        if formatted_name and formatted_name != "Administrator":
            df_month_check = load_data(st.session_state.filter_month)
            if not df_month_check.empty:
                 df_emp = df_month_check[df_month_check["Employee Name"].astype(str).str.strip().str.lower() == formatted_name.lower()]
                 if not df_emp.empty:
                      df_emp = df_emp.copy()
                      df_emp["RealDate"] = pd.to_datetime(df_emp["Date"], format="%d/%m/%Y")
                      latest_date_row = df_emp.loc[df_emp['RealDate'].idxmax()]
                      latest_date = latest_date_row['RealDate'].date()
                      default_date = latest_date + timedelta(days=1)

        with st.form("entry_form"):
            c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.2, 1.2, 1.5])
            with c1:
                entry_date = st.date_input("Date", value=default_date, format="DD/MM/YYYY")
            with c2:
                entry_status = st.selectbox("Status", ["Regular", "Holiday", "PL", "LWP", "Absent"])
            with c3:
                in_time = st.time_input("In Time", value=time(8, 0), key=f"in_{st.session_state.form_reset_counter}")
            with c4:
                out_time = st.time_input("Out Time", value=time(18, 0), key=f"out_{st.session_state.form_reset_counter}")
                
            with c5:
                st.write("")
                st.write("")
                submit = st.form_submit_button("Save Entry", type="primary", use_container_width=True)

        if submit:
            if not formatted_name:
                st.error("Please enter an Employee Name above!")
            elif formatted_name == "Administrator":
                st.error("You cannot add an entry for 'Administrator'. Please type a valid name!")
            elif out_time < in_time and entry_status not in ["PL", "LWP", "Absent"]:
                st.error("Out Time cannot be before In Time!")
            else:
                target_sheet = get_sheet_name(entry_date)
                df_month = load_data(target_sheet)
                day_str = entry_date.strftime("%a")
                date_str = entry_date.strftime("%d/%m/%Y")
                
                is_duplicate = not df_month[(df_month["Employee Name"].astype(str).str.strip().str.lower() == formatted_name.lower()) & (df_month["Date"] == date_str)].empty
                
                if is_duplicate:
                    st.error(f"⚠️ An entry for {formatted_name} on {date_str} already exists!")
                else:
                    holidays_dict = get_flat_holiday_dates()
                    is_pub_hol = date_str in holidays_dict
                    total_hrs, late_hrs, out_hrs, ot_hrs = calculate_times(in_time.strftime("%H:%M"), out_time.strftime("%H:%M"), day_str, entry_status, is_pub_hol)
                    
                    if entry_status in ["PL", "LWP", "Absent"]:
                        in_t_str, out_t_str = "00:00", "00:00"
                    else:
                        in_t_str, out_t_str = in_time.strftime("%H:%M"), out_time.strftime("%H:%M")

                    new_entry = pd.DataFrame({
                        "Employee Name": [formatted_name],
                        "Date": [date_str],
                        "Day": [day_str],
                        "Status": [entry_status],
                        "In Time": [in_t_str],
                        "Out Time": [out_t_str],
                        "Late Hours": [late_hrs],
                        "Out Hours": [out_hrs],
                        "Total Hours": [total_hrs],
                        "OT Hours": [ot_hrs]
                    })
                    df_month = pd.concat([df_month, new_entry], ignore_index=True)
                    save_data(df_month, target_sheet) 
                    
                    st.session_state.filter_month = target_sheet
                    st.session_state.last_edited = f"{formatted_name}_{date_str}"
                    st.session_state.form_reset_counter += 1
                    
                    st.session_state.flash_msg = f"✅ Record for {formatted_name} on {date_str} saved successfully!"
                    st.rerun()

    elif entry_mode == "📂 Bulk Upload (Excel/CSV)":
        st.subheader("📂 Upload Monthly Excel/CSV")
        st.markdown("""
        **Instructions:**
        1. File must have columns: `Employee Name`, `Date` (DD/MM/YYYY), `In Time` (HH:MM), `Out Time` (HH:MM), `Status` (Optional).
        2. Missing times will default to 08:00 and 18:00. Missing Status defaults to Regular.
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
                        
                        for date_val, group in grouped:
                            try:
                                d_obj = pd.to_datetime(date_val, format='%d/%m/%Y', errors='coerce').date()
                                if pd.isna(d_obj): continue
                                
                                sheet_n = get_sheet_name(d_obj)
                                day_s = d_obj.strftime("%a")
                                date_s = d_obj.strftime("%d/%m/%Y")
                                is_pub_hol = date_s in holidays_dict
                                
                                df_db = load_data(sheet_n)
                                new_rows = []
                                
                                for _, r in group.iterrows():
                                    ename = str(r['Employee Name']).strip().title()
                                    stat = str(r.get('Status', 'Regular')) if pd.notna(r.get('Status')) else 'Regular'
                                    if stat not in ["Regular", "Holiday", "PL", "LWP", "Absent"]: stat = "Regular"
                                        
                                    in_val = str(r['In Time']).strip() if pd.notna(r['In Time']) else "08:00"
                                    out_val = str(r['Out Time']).strip() if pd.notna(r['Out Time']) else "18:00"
                                    
                                    if not df_db[(df_db["Employee Name"].str.lower() == ename.lower()) & (df_db["Date"] == date_s)].empty:
                                        continue
                                        
                                    tot, late, out_e, ot = calculate_times(in_val, out_val, day_s, stat, is_pub_hol)
                                    new_rows.append({
                                        "Employee Name": ename, "Date": date_s, "Day": day_s, "Status": stat,
                                        "In Time": in_val, "Out Time": out_val, "Late Hours": late, "Out Hours": out_e,
                                        "Total Hours": tot, "OT Hours": ot
                                    })
                                    success_count += 1
                                    
                                if new_rows:
                                    df_db = pd.concat([df_db, pd.DataFrame(new_rows)], ignore_index=True)
                                    save_data(df_db, sheet_n)
                                    
                            except Exception:
                                pass
                                
                        st.session_state.flash_msg = f"✅ Successfully uploaded {success_count} records!"
                        st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

with tab2:
    st.subheader("👥 Daily Roster (Mark all employees for a day)")
    roster_date = st.date_input("Select Date for Roster", value=date.today(), format="DD/MM/YYYY", key="roster_date")
    
    all_emp_list = get_all_employees()
    if not all_emp_list:
        st.info("No employees found in the database. Please add at least one entry in 'Manual Entry' first.")
    else:
        r_sheet = get_sheet_name(roster_date)
        df_r_month = load_data(r_sheet)
        r_date_str = roster_date.strftime("%d/%m/%Y")
        r_day_str = roster_date.strftime("%a")
        
        existing_emps_on_date = df_r_month[df_r_month["Date"] == r_date_str]["Employee Name"].tolist() if not df_r_month.empty else []
        pending_emps = [e for e in all_emp_list if e not in existing_emps_on_date]
        
        if not pending_emps:
            st.success(f"✅ All employees are already marked for {r_date_str}.")
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
                    "Status": st.column_config.SelectboxColumn("Status", options=["Regular", "Holiday", "PL", "LWP", "Absent"], required=True),
                    "In Time": st.column_config.TimeColumn("In Time", format="HH:mm", step=60),
                    "Out Time": st.column_config.TimeColumn("Out Time", format="HH:mm", step=60)
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
                    
                    tot, late, out_e, ot = calculate_times(in_t, out_t, r_day_str, stat, is_pub_hol)
                    new_records.append({
                        "Employee Name": emp_n, "Date": r_date_str, "Day": r_day_str, "Status": stat,
                        "In Time": in_t, "Out Time": out_t, "Late Hours": late, "Out Hours": out_e,
                        "Total Hours": tot, "OT Hours": ot
                    })
                
                if new_records:
                    df_new_roster = pd.DataFrame(new_records)
                    df_r_month = pd.concat([df_r_month, df_new_roster], ignore_index=True)
                    save_data(df_r_month, r_sheet)
                    st.session_state.flash_msg = f"✅ Daily Roster for {r_date_str} saved successfully!"
                    st.rerun()

with tab3:
    st.subheader("🌴 Holiday Calendar")
    hol_data = load_holidays_data()
    
    if formatted_name == "Administrator":
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
        st.info("🔒 Only Administrator can add, edit or delete holidays.")
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
    if not formatted_name or formatted_name == "Administrator":
        st.info("👆 Please select an Employee Name in the 'Add Attendance' tab to view their Dashboard & History.")
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
                df_temp = load_data(sht)
                if not df_temp.empty:
                    df_temp["_Original_Sheet"] = sht
                    df_temp["_Original_Index"] = df_temp.index
                    df_list.append(df_temp)
            if df_list:
                df_display = pd.concat(df_list, ignore_index=True)
            else:
                df_display = pd.DataFrame()
        else:
            df_display = load_data(selected_sheet)
            if not df_display.empty:
                df_display["_Original_Sheet"] = selected_sheet
                df_display["_Original_Index"] = df_display.index

        if not df_display.empty:
            df_display["RealDate"] = pd.to_datetime(df_display["Date"], format="%d/%m/%Y")
            df_display = df_display.sort_values(by=["Employee Name", "RealDate"]).drop(columns=["RealDate"])
            df_display = df_display.reset_index(drop=True)
            df_display = df_display.fillna("") 

            df_display = df_display[df_display["Employee Name"].astype(str).str.strip().str.lower() == formatted_name.lower()]

            final_display_columns = ["Employee Name", "Date", "Day", "Status", "In Time", "Out Time", "Late Hours", "Out Hours", "Total Hours", "OT Hours", "_Original_Sheet", "_Original_Index"]
            for c in final_display_columns:
                 if c not in df_display.columns:
                     df_display[c] = ""
            df_display = df_display[final_display_columns]

        if df_display.empty:
            st.warning(f"No records found for '{formatted_name}' in {selected_sheet}.")
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
            st.subheader(f"📊 Summary for {formatted_name}")
            m1, m2, m3, m4, m5 = st.columns(5)
            with m1: st.metric(label="🕒 Total Working Hrs", value=f"{reg_hours:02d}:{reg_mins:02d}")
            with m2: st.metric(label="🔥 Total OT Hrs", value=f"{ot_hours:02d}:{ot_mins:02d}")
            with m3: st.metric(label="⚠️ Total Late/Out Hrs", value=f"{late_hours+out_hours:02d}:{(late_mins+out_mins):02d}")
            with m4: st.metric(label="🌴 Paid Leaves (PL)", value=pl_count)
            with m5: st.metric(label="❌ Absent (LWP)", value=absent_count)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.write("")
            st.subheader("📈 Daily Working Hours")
            chart_data = df_display[['Date', 'Total Hours', 'OT Hours']].copy()
            chart_data['Working Hrs'] = chart_data['Total Hours'].apply(time_to_float)
            chart_data['Overtime Hrs'] = chart_data['OT Hours'].apply(time_to_float)
            chart_data.set_index('Date', inplace=True)
            
            st.bar_chart(chart_data[['Working Hrs', 'Overtime Hrs']], use_container_width=True)

            st.divider()
            st.subheader("📋 Attendance Sheet")

            col_s1, col_s2, col_s3 = st.columns([1, 1, 2])
            with col_s1:
                st.selectbox("Select Month to View", available_sheets, key="filter_month")
                selected_sheet = st.session_state.filter_month

            with col_s2:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_export = df_display.drop(columns=["_Original_Sheet", "_Original_Index", "Employee Name"], errors='ignore')
                    export_sheet_name = selected_sheet if selected_sheet != "All Months" else "All_Months"
                    
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
                    c1.value = formatted_name
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
                    status_col_idx = 3
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
                    worksheet.merge_cells(start_row=total_row_idx, start_column=3, end_row=total_row_idx, end_column=5)
                    
                    worksheet.cell(row=total_row_idx, column=3, value="TOTAL")
                    worksheet.cell(row=total_row_idx, column=6, value=f"{late_hours:02d}:{late_mins:02d}")
                    worksheet.cell(row=total_row_idx, column=7, value=f"{out_hours:02d}:{out_mins:02d}")
                    worksheet.cell(row=total_row_idx, column=8, value=f"{reg_hours:02d}:{reg_mins:02d}")
                    worksheet.cell(row=total_row_idx, column=9, value=f"{ot_hours:02d}:{ot_mins:02d}")
                    
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
                hol_dict_hl = get_flat_holiday_dates()
                
                if row['Day'] == 'Sun':
                    colors = ['background-color: #ff4c4c; color: white; font-weight: bold'] * len(row)
                elif row['Status'] == 'Holiday' or row['Date'] in hol_dict_hl:
                    colors = ['background-color: #b3d9ff; color: black; font-weight: bold'] * len(row)
                elif row['Status'] in ['PL', 'LWP', 'Absent']:
                    colors = ['background-color: #ffcc99; color: black; font-weight: bold'] * len(row)
                elif st.session_state.last_edited == f"{row['Employee Name']}_{row['Date']}":
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
                            df_orig = load_data(sht)
                            df_orig = df_orig.drop(indices) 
                            save_data(df_orig, sht)
                        
                        st.session_state.last_edited = None
                        st.session_state.flash_msg = "✅ Selected entries permanently deleted!"
                        st.rerun()
                else:
                    selected_idx = df_display.iloc[selected_rows[0]]["_Original_Index"]
                    selected_sheet_orig = df_display.iloc[selected_rows[0]]["_Original_Sheet"]
                    row_data = df_display.iloc[selected_rows[0]]
                    
                    col_edit, col_delete = st.columns([3, 1])
                    
                    with col_edit:
                        st.subheader("✏️ Edit Selected Entry")
                        with st.form("edit_form_hist"):
                            e_name = st.text_input("Employee Name", value=row_data["Employee Name"], disabled=True)
                            ce1, ce2, ce3, ce4 = st.columns(4)
                            with ce1:
                                d_obj = datetime.strptime(row_data["Date"], "%d/%m/%Y").date()
                                e_date = st.date_input("Date", value=d_obj, key="e_date", format="DD/MM/YYYY")
                            with ce2:
                                def_status = ["Regular", "Holiday", "PL", "LWP", "Absent"]
                                e_stat = st.selectbox("Status", def_status, index=def_status.index(row_data.get("Status", "Regular")))
                            with ce3:
                                in_obj = datetime.strptime(row_data["In Time"], "%H:%M").time()
                                e_in = st.time_input("In Time", value=in_obj, key="e_in")
                            with ce4:
                                out_obj = datetime.strptime(row_data["Out Time"], "%H:%M").time()
                                e_out = st.time_input("Out Time", value=out_obj, key="e_out")
                                
                            if st.form_submit_button("Update Entry", type="secondary"):
                                formatted_e_name = e_name.strip().title()
                                date_str_e = e_date.strftime("%d/%m/%Y")
                                new_sheet = get_sheet_name(e_date)
                                
                                df_orig = load_data(selected_sheet_orig)
                                
                                if new_sheet == selected_sheet_orig:
                                    temp_check = df_orig.drop(selected_idx)
                                    is_dup = not temp_check[(temp_check["Employee Name"].astype(str).str.strip().str.lower() == formatted_e_name.lower()) & (temp_check["Date"] == date_str_e)].empty
                                else:
                                    df_new = load_data(new_sheet)
                                    is_dup = not df_new[(df_new["Employee Name"].astype(str).str.strip().str.lower() == formatted_e_name.lower()) & (df_new["Date"] == date_str_e)].empty

                                if is_dup:
                                    st.error("⚠️ An entry for this employee on this date already exists!")
                                else:
                                    day_str_e = e_date.strftime("%a")
                                    holidays_dict = get_flat_holiday_dates()
                                    is_pub_hol = date_str_e in holidays_dict
                                    t_hrs, l_hrs, o_hrs, ot_hrs = calculate_times(e_in.strftime("%H:%M"), e_out.strftime("%H:%M"), day_str_e, e_stat, is_pub_hol)
                                    
                                    if e_stat in ["PL", "LWP", "Absent"]:
                                        in_t_str, out_t_str = "00:00", "00:00"
                                    else:
                                        in_t_str, out_t_str = e_in.strftime("%H:%M"), e_out.strftime("%H:%M")

                                    updated_row = pd.DataFrame({
                                        "Employee Name": [formatted_e_name],
                                        "Date": [date_str_e],
                                        "Day": [day_str_e],
                                        "Status": [e_stat],
                                        "In Time": [in_t_str],
                                        "Out Time": [out_t_str],
                                        "Late Hours": [l_hrs],
                                        "Out Hours": [o_hrs],
                                        "Total Hours": [t_hrs],
                                        "OT Hours": [ot_hrs]
                                    })
                                    
                                    if new_sheet == selected_sheet_orig:
                                        updated_row.index = [selected_idx]
                                        df_orig.update(updated_row)
                                        save_data(df_orig, selected_sheet_orig)
                                    else:
                                        df_orig = df_orig.drop(selected_idx)
                                        save_data(df_orig, selected_sheet_orig)
                                        df_new = pd.concat([df_new, updated_row], ignore_index=True)
                                        save_data(df_new, new_sheet)
                                    
                                    st.session_state.last_edited = f"{formatted_e_name}_{date_str_e}"
                                    st.session_state.flash_msg = f"✅ Record for {formatted_e_name} on {date_str_e} updated successfully!"
                                    st.rerun()

                    with col_delete:
                        st.subheader("🗑️ Delete")
                        st.write("Click below to permanently delete this entry:")
                        if st.button("Delete This Entry", type="primary"):
                            df_orig = load_data(selected_sheet_orig)
                            df_orig = df_orig.drop(selected_idx) 
                            save_data(df_orig, selected_sheet_orig)
                            
                            st.session_state.last_edited = None
                            st.session_state.flash_msg = f"✅ Record for {row_data['Employee Name']} on {row_data['Date']} permanently deleted!"
                            st.rerun()

if has_msg:
    tm.sleep(3)
    msg_placeholder.empty()
