import streamlit as st
import pandas as pd
from datetime import datetime, date
import os

# File name for saving data
FILE_NAME = "attendance.csv"

# 1. Function to load existing data
def load_data():
    if os.path.exists(FILE_NAME):
        return pd.read_csv(FILE_NAME)
    else:
        return pd.DataFrame(columns=["Date", "Day", "In Time", "Out Time", "Total Hours"])

# 2. Function to save new data
def save_data(df):
    df.to_csv(FILE_NAME, index=False)

# 3. Calculate Total Hours from In Time and Out Time
def calculate_hours(in_time, out_time):
    fmt = "%H:%M"
    t1 = datetime.strptime(in_time.strftime(fmt), fmt)
    t2 = datetime.strptime(out_time.strftime(fmt), fmt)
    
    # If Out Time is greater than or equal to In Time
    if t2 >= t1:
        delta = t2 - t1
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}"
    else:
        return "00:00"

# 4. Streamlit UI
st.set_page_config(page_title="Attendance Tracker", layout="centered")
st.title("📅 Daily Attendance Tracker")

# Load data
df = load_data()

# --- ENTRY FORM ---
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

# On form submission
if submit:
    day_str = entry_date.strftime("%a") # e.g., 'Mon', 'Tue'
    date_str = entry_date.strftime("%d/%m/%Y")
    total_hrs = calculate_hours(in_time, out_time)
    
    # Add new data to dataframe
    new_entry = pd.DataFrame({
        "Date": [date_str],
        "Day": [day_str],
        "In Time": [in_time.strftime("%H:%M")],
        "Out Time": [out_time.strftime("%H:%M")],
        "Total Hours": [total_hrs]
    })
    
    df = pd.concat([df, new_entry], ignore_index=True)
    save_data(df) # Save to file
    st.success(f"Entry for {date_str} added successfully!")

st.divider()

# --- TABLE AND TOTAL DISPLAY ---
st.subheader("Attendance Sheet")

if not df.empty:
    # Logic to highlight Sunday in red
    def highlight_sunday(row):
        if row['Day'] == 'Sun':
            return ['background-color: red; color: white'] * len(row)
        return [''] * len(row)

    styled_df = df.style.apply(highlight_sunday, axis=1)
    
    # Display Table
    st.dataframe(styled_df, use_container_width=True)
    
    # Calculate Grand Total
    total_mins = 0
    for val in df["Total Hours"]:
        if pd.notna(val) and ":" in str(val):
            h, m = map(int, str(val).split(":"))
            total_mins += h * 60 + m
            
    grand_hours, grand_mins = divmod(total_mins, 60)
    grand_total_str = f"{grand_hours:02d}:{grand_mins:02d}"
    
    # Display Grand Total
    st.markdown(f"### 🕒 Grand Total Hours: **{grand_total_str}**")
else:
    st.info("No data available yet. Please add an entry from the form above.")
