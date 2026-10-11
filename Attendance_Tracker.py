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
    columns = ["Date", "Day", "In Time", "Out Time", "Late Hours", "Late Minutes", "Out Hours", "Out Minutes", "Total Hours"]
    if os.path.exists(FILE_NAME):
        try:
            return pd.read_excel(FILE_NAME, sheet_name=sheet_name)
        except ValueError:
            # Jo sheet haji na bani hoy to khali dataframe aapo
            return pd.DataFrame(columns=columns)
    else:
        return pd.DataFrame(columns=columns)

# Data save karva mate (Ek j file ma navi sheet)
def save_data(df, sheet_name):
    if not os.path.exists(FILE_NAME):
        # Pehli var file banavva mate
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        # Juni file ma navi sheet add karva athva update karva mate
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

# Time ganatri karva mate
def calculate_times(in_time, out_time):
    fmt = "%H:%M"
    t1 = datetime.strptime(in_time.strftime(fmt), fmt)
    t2 = datetime.strptime(out_time.strftime(fmt), fmt)
    std_in = datetime.strptime(STANDARD_IN, fmt)
    std_out = datetime.strptime(STANDARD_OUT, fmt)
    
    if t2 >= t1:
        delta = t2 - t1
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        total_hrs = f"{hours:02d}:{minutes:02d}"
    else:
        total_hrs = "00:00"
        
    late_h, late_m = "", ""
    if t1 > std_in:
        late_delta = t1 - std_in
        h, r = divmod(late_delta.seconds, 3600)
        m, _ = divmod(r, 60)
        late_h = str(h) if h > 0 else ""
        late_m = str(m) if m > 0 or h > 0 else ""

    out_h, out_m = "", ""
    if t2 < std_out:
        out_delta = std_out - t2
        h, r = divmod(out_delta.seconds, 3600)
        m, _ = divmod(r, 60)
        out_h = str(h) if h > 0 else ""
        out_m = str(m) if m > 0 or h > 0 else ""
        
    return total_hrs, late_h, late_m, out_h, out_m

# --- Streamlit UI ---
st.set_page_config(page_title="Attendance Tracker", layout="wide")
st.title("📅 Daily Attendance Tracker")

st.subheader("Add New Entry")
with st.form("entry_form"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        entry_date = st.date_input("Date", date.today())
    with col2:
        in_time = st.time_input("In Time")
    with col3:
        out_time = st.time_input("Out Time")
        
    submit = st.form_submit_button("Add Entry")

if submit:
    # Je tarikh pasand kari teni sheet nu naam (e.g. Oct'2026)
    target_sheet = get_sheet_name(entry_date)
    
    df_month = load_data(target_sheet)
    
    day_str = entry_date.strftime("%a")
    date_str = entry_date.strftime("%d/%m/%Y")
    
    total_hrs, late_h, late_m, out_h, out_m = calculate_times(in_time, out_time)
    
    new_entry = pd.DataFrame({
        "Date": [date_str],
        "Day": [day_str],
        "In Time": [in_time.strftime("%H:%M")],
        "Out Time": [out_time.strftime("%H:%M")],
        "Late Hours": [late_h],
        "Late Minutes": [late_m],
        "Out Hours": [out_h],
        "Out Minutes": [out_m],
        "Total Hours": [total_hrs]
    })
    
    df_month = pd.concat([df_month, new_entry], ignore_index=True)
    save_data(df_month, target_sheet) 
    st.success(f"Entry saved in sheet: {target_sheet}")

st.divider()

st.subheader("Attendance Sheet")

# Dropdown mathi sheet select karva mate
available_sheets = get_all_sheet_names()
selected_sheet = st.selectbox("Select Month to View", available_sheets)

# Select kareli sheet no data batao
df_display = load_data(selected_sheet)

if not df_display.empty:
    def highlight_sunday(row):
        if row['Day'] == 'Sun':
            return ['background-color: red; color: white'] * len(row)
        return [''] * len(row)

    styled_df = df_display.style.apply(highlight_sunday, axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Grand Total
    total_mins = 0
    for val in df_display["Total Hours"]:
        if pd.notna(val) and ":" in str(val):
            h, m = map(int, str(val).split(":"))
            total_mins += h * 60 + m
            
    grand_hours, grand_mins = divmod(total_mins, 60)
    grand_total_str = f"{grand_hours:02d}:{grand_mins:02d}"
    
    st.markdown(f"### 🕒 Grand Total Hours for {selected_sheet}: **{grand_total_str}**")
else:
    st.info(f"No data available in sheet {selected_sheet}. Please add an entry above.")
