import streamlit as st
import pandas as pd
from datetime import datetime, date, time
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
        if worked_mins_total > 600: # 10 hours = 600 mins
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

        if t2 < std_out and t2 >= t1: # Only calculate early out if they worked
            out_delta = std_out - t2
            h, r = divmod(out_delta.seconds, 3600)
            m, _ = divmod(r, 60)
            out_hrs = f"{h:02d}:{m:02d}"
            
    return total_hrs, late_hrs, out_hrs, ot_hrs

# --- Streamlit UI ---
st.set_page_config(page_title="Attendance Tracker", layout="wide", page_icon="📅")
st.title("📅 Daily Attendance Tracker")

with st.expander("➕ Add New Entry", expanded=True):
    with st.form("entry_form"):
        emp_name = st.text_input("Employee Name", placeholder="e.g. Ramesh Patel")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            entry_date = st.date_input("Date", date.today())
        with col2:
            in_time = st.time_input("In Time", value=time(8, 0))
        with col3:
            out_time = st.time_input("Out Time", value=time(18, 0))
            
        submit = st.form_submit_button("Save Entry", type="primary")

    if submit:
        if not emp_name.strip():
            st.error("Please enter an Employee Name!")
        elif out_time < in_time:
            st.error("Out Time cannot be before In Time!")
        else:
            # Format name properly (Title Case)
            formatted_name = emp_name.strip().title()
            
            target_sheet = get_sheet_name(entry_date)
            df_month = load_data(target_sheet)
            
            day_str = entry_date.strftime("%a")
            date_str = entry_date.strftime("%d/%m/%Y")
            
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
            save_data(df_month, target_sheet) 
            st.success(f"Entry for {formatted_name} saved successfully!")
            st.rerun() 

st.divider()

st.subheader("📋 Attendance Sheet")

col_s1, col_s2 = st.columns(2)
with col_s1:
    available_sheets = get_all_sheet_names()
    selected_sheet = st.selectbox("Select Month to View", available_sheets)

df_display = load_data(selected_sheet)

if not df_display.empty:
    # Sort data by Employee Name and Date for professional look
    df_display["RealDate"] = pd.to_datetime(df_display["Date"], format="%d/%m/%Y")
    df_display = df_display.sort_values(by=["Employee Name", "RealDate"]).drop(columns=["RealDate"])
    
    # Refresh index after sorting
    df_display = df_display.reset_index(drop=True)
    df_display["Original_Index"] = df_display.index
    df_display = df_display.fillna("")

    emp_list = df_display["Employee Name"].dropna().unique().tolist()
    with col_s2:
        selected_emp = st.selectbox("Filter by Employee", ["All"] + emp_list)
        
    if selected_emp != "All":
        df_display = df_display[df_display["Employee Name"] == selected_emp]

    def highlight_sunday(row):
        if row['Day'] == 'Sun':
            return ['background-color: #ff7f7f; color: white'] * len(row)
        return [''] * len(row)

    styled_df = df_display.style.apply(highlight_sunday, axis=1)
    
    st.markdown("💡 **Tip:** Select checkbox on the left to Edit or Delete entries.")

    event = st.dataframe(
        styled_df, 
        use_container_width=True, 
        hide_index=True,
        on_select="rerun",           
        selection_mode="multi-row",  
        column_config={
            "Original_Index": None   
        }
    )
    
    # --- EDIT & DELETE LOGIC ---
    selected_rows = event.selection.rows
    if selected_rows:
        col_btn1, col_btn2 = st.columns([1, 4])
        
        with col_btn2:
            if st.button("🗑️ Delete Selected", type="primary"):
                indices_to_drop = df_display.iloc[selected_rows]["Original_Index"].tolist()
                df_original = load_data(selected_sheet)
                df_original = df_original.drop(indices_to_drop) 
                save_data(df_original, selected_sheet)
                st.success("✅ Entry deleted successfully!")
                st.rerun()
                
        # Show Edit Option ONLY if exactly 1 row is selected
        if len(selected_rows) == 1:
            st.markdown("---")
            st.subheader("✏️ Edit Selected Entry")
            selected_idx = df_display.iloc[selected_rows[0]]["Original_Index"]
            row_data = df_display.iloc[selected_rows[0]]
            
            with st.form("edit_form"):
                e_name = st.text_input("Employee Name", value=row_data["Employee Name"])
                
                col_e1, col_e2, col_e3 = st.columns(3)
                with col_e1:
                    d_obj = datetime.strptime(row_data["Date"], "%d/%m/%Y").date()
                    e_date = st.date_input("Date", value=d_obj, key="e_date")
                with col_e2:
                    in_obj = datetime.strptime(row_data["In Time"], "%H:%M").time()
                    e_in = st.time_input("In Time", value=in_obj, key="e_in")
                with col_e3:
                    out_obj = datetime.strptime(row_data["Out Time"], "%H:%M").time()
                    e_out = st.time_input("Out Time", value=out_obj, key="e_out")
                    
                if st.form_submit_button("Update Entry", type="secondary"):
                    formatted_e_name = e_name.strip().title()
                    day_str_e = e_date.strftime("%a")
                    date_str_e = e_date.strftime("%d/%m/%Y")
                    t_hrs, l_hrs, o_hrs, ot_hrs = calculate_times(e_in, e_out, day_str_e)
                    
                    df_original = load_data(selected_sheet)
                    df_original.at[selected_idx, "Employee Name"] = formatted_e_name
                    df_original.at[selected_idx, "Date"] = date_str_e
                    df_original.at[selected_idx, "Day"] = day_str_e
                    df_original.at[selected_idx, "In Time"] = e_in.strftime("%H:%M")
                    df_original.at[selected_idx, "Out Time"] = e_out.strftime("%H:%M")
                    df_original.at[selected_idx, "Late Hours"] = l_hrs
                    df_original.at[selected_idx, "Out Hours"] = o_hrs
                    df_original.at[selected_idx, "Total Hours"] = t_hrs
                    df_original.at[selected_idx, "OT Hours"] = ot_hrs
                    
                    save_data(df_original, selected_sheet)
                    st.success("✅ Entry updated successfully!")
                    st.rerun()
        else:
            st.info("📌 Note: Edit option is only available when exactly ONE row is selected.")

    st.markdown("---")
    
    # --- SUMMARY DASHBOARD ---
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
    
    st.subheader("📊 Summary")
    met1, met2 = st.columns(2)
    with met1:
        st.metric(label="🕒 Total Regular Hours", value=f"{reg_hours:02d}:{reg_mins:02d}")
    with met2:
        st.metric(label="🔥 Total Overtime (OT) Hours", value=f"{ot_hours:02d}:{ot_mins:02d}")
            
else:
    st.info(f"No data available in sheet {selected_sheet}. Please add an entry above.")
