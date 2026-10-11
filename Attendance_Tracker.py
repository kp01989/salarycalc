import streamlit as st
import pandas as pd
from datetime import datetime, date
import os

# Excel File Name
FILE_NAME = "Attendance_Tracker.xlsx"

# Default Office Timings
STANDARD_IN = "08:00"
STANDARD_OUT = "18:00"

# Sheet nu naam banavva mate (e.g., Oct'2026)
def get_sheet_name(selected_date):
    return selected_date.strftime("%b'%Y")

# Excel mathi badhi sheet na naam lavva mate
def get_all_sheet_names():
    if os.path.exists(FILE_NAME):
        xl = pd.ExcelFile(FILE_NAME)
        return xl.sheet_names
    return [get_sheet_name(date.today())]

# Data load karva mate
def load_data(sheet_name):
    columns = ["Employee Name", "Date", "Day", "In Time", "Out Time", "Late Hours", "Out Hours", "Total Hours", "OT Hours"]
    if os.path.exists(FILE_NAME):
        try:
            df = pd.read_excel(FILE_NAME, sheet_name=sheet_name)
            
            if "Employee Name" not in df.columns:
                df.insert(0, "Employee Name", "-")
            if "OT Hours" not in df.columns:
                df["OT Hours"] = "00:00"
                
            cols_to_drop = ["Late Minutes", "Out Minutes"]
            df = df.drop(columns=[col for col in cols_to_drop if col in df.columns], errors='ignore')
            
            return df
        except ValueError:
            return pd.DataFrame(columns=columns)
    else:
        return pd.DataFrame(columns=columns)

# Data save karva mate
def save_data(df, sheet_name):
    if not os.path.exists(FILE_NAME):
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

# Time ganatri karva mate 
def calculate_times(in_time, out_time, day_str):
    fmt = "%H:%M"
    t1 = datetime.strptime(in_time.strftime(fmt), fmt)
    t2 = datetime.strptime(out_time.strftime(fmt), fmt)
    std_in = datetime.strptime(STANDARD_IN, fmt)
    std_out = datetime.strptime(STANDARD_OUT, fmt)
    
    worked_mins_total = 0
    if t2 >= t1:
        delta = t2 - t1
        worked_mins_total = delta.seconds // 60
        hours, minutes = divmod(worked_mins_total, 60)
        worked_hrs = f"{hours:02d}:{minutes:02d}"
    else:
        worked_hrs = "00:00"
        
    late_hrs, out_hrs = "", ""
    ot_hrs = "00:00"
    total_hrs = "00:00"
    
    if day_str == "Sun":
        ot_hrs = worked_hrs
        total_hrs = "00:00"
    else:
        if worked_mins_total > 600:
            total_hrs = "10:00" 
            extra_mins = worked_mins_total - 600
            e_h, e_m = divmod(extra_mins, 60)
            ot_hrs = f"{e_h:02d}:{e_m:02d}" 
        else:
            total_hrs = worked_hrs
            ot_hrs = "00:00"
        
        if t1 > std_in:
            late_delta = t1 - std_in
            h, r = divmod(late_delta.seconds, 3600)
            m, _ = divmod(r, 60)
            late_hrs = f"{h:02d}:{m:02d}"

        if t2 < std_out:
            out_delta = std_out - t2
            h, r = divmod(out_delta.seconds, 3600)
            m, _ = divmod(r, 60)
            out_hrs = f"{h:02d}:{m:02d}"
            
    return total_hrs, late_hrs, out_hrs, ot_hrs

# --- Streamlit UI ---
st.set_page_config(page_title="Attendance Tracker", layout="wide")
st.title("📅 Daily Attendance Tracker")

st.subheader("Add New Entry")
with st.form("entry_form"):
    emp_name = st.text_input("Employee Name", placeholder="e.g. Ramesh Patel")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        entry_date = st.date_input("Date", date.today())
    with col2:
        in_time = st.time_input("In Time")
    with col3:
        out_time = st.time_input("Out Time")
        
    submit = st.form_submit_button("Add Entry")

if submit:
    if not emp_name.strip():
        st.error("Please enter an Employee Name!")
    else:
        target_sheet = get_sheet_name(entry_date)
        df_month = load_data(target_sheet)
        
        day_str = entry_date.strftime("%a")
        date_str = entry_date.strftime("%d/%m/%Y")
        
        total_hrs, late_hrs, out_hrs, ot_hrs = calculate_times(in_time, out_time, day_str)
        
        new_entry = pd.DataFrame({
            "Employee Name": [emp_name.strip()],
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
        save_data(df_month, target_sheet) 
        st.success(f"Entry for {emp_name} saved in sheet: {target_sheet}")
        st.rerun() 

st.divider()

st.subheader("Attendance Sheet")

col_s1, col_s2 = st.columns(2)
with col_s1:
    available_sheets = get_all_sheet_names()
    selected_sheet = st.selectbox("Select Month to View", available_sheets)

df_display = load_data(selected_sheet)

if not df_display.empty:
    emp_list = df_display["Employee Name"].dropna().unique().tolist()
    with col_s2:
        selected_emp = st.selectbox("Filter by Employee", ["All"] + emp_list)
        
    if selected_emp != "All":
        df_display = df_display[df_display["Employee Name"] == selected_emp]

    # Original Index સાચવી રાખવા જેથી ફિલ્ટર કર્યા પછી પણ સાચી એન્ટ્રી જ ડીલીટ થાય 
    df_display["Original_Index"] = df_display.index
    df_display = df_display.fillna("")

    def highlight_sunday(row):
        if row['Day'] == 'Sun':
            return ['background-color: #ff7f7f; color: white'] * len(row)
        return [''] * len(row)

    styled_df = df_display.style.apply(highlight_sunday, axis=1)
    
    # યુઝરને માહિતી આપવા માટે મેસેજ
    st.markdown("💡 **માહિતી:** જે Entry ડીલીટ કરવી હોય તેને ડાબી બાજુના ચેકબોક્સ(Checkbox) થી સિલેક્ટ કરો. સિલેક્ટ કરતા જ ઉપર ડાઉનલોડ બટનની બાજુમાં 🗑️ (Delete) નું આઇકોન દેખાશે.")

    # st.dataframe ની જગ્યાએ st.data_editor વાપર્યું છે
    edited_df = st.data_editor(
        styled_df, 
        use_container_width=True, 
        hide_index=True,
        num_rows="dynamic", # આનાથી ચેકબોક્સ અને ડિલીટ ટૂલ એક્ટિવેટ થશે
        column_config={
            "Original_Index": None # ઓરિજિનલ ઇન્ડેક્સ યુઝરથી છુપાવવા માટે
        },
        key=f"editor_{selected_sheet}_{selected_emp}"
    )
    
    # ડિલીટ લોજીક (જો ડેટાબેઝ કરતા edited_df માં લાઇનો ઓછી હોય, તો એનો અર્થ યુઝરે ડિલીટ કર્યું છે)
    if len(edited_df) < len(df_display):
        remaining_indices = edited_df["Original_Index"].dropna().tolist()
        deleted_indices = set(df_display["Original_Index"]) - set(remaining_indices)
        
        if deleted_indices:
            df_original = load_data(selected_sheet)
            df_original = df_original.drop(list(deleted_indices)) # એક્સેલ માંથી કાયમ માટે કાઢી નાખવા
            save_data(df_original, selected_sheet)
            st.success("✅ Entry Delete થઈ ગઈ છે!")
            st.rerun()
    
    # Total Ganatri
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
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.info(f"### 🕒 Regular Hours: **{reg_hours:02d}:{reg_mins:02d}**")
    with col_b:
        st.success(f"### 🔥 Total OT Hours: **{ot_hours:02d}:{ot_mins:02d}**")
            
else:
    st.info(f"No data available in sheet {selected_sheet}. Please add an entry above.")
