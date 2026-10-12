import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import os
import io

# Excel File Name
FILE_NAME = "Attendance_Tracker.xlsx"

STANDARD_IN = "08:00"
STANDARD_OUT = "18:00"

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

def load_data(sheet_name):
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
            return df
        except ValueError:
            return pd.DataFrame(columns=columns)
    else:
        return pd.DataFrame(columns=columns)

def save_data(df, sheet_name):
    if not os.path.exists(FILE_NAME):
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

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
        
    late_hrs, out_hrs, ot_hrs, total_hrs = "", "", "00:00", "00:00"
    
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

        if t2 < std_out and t2 >= t1:
            out_delta = std_out - t2
            h, r = divmod(out_delta.seconds, 3600)
            m, _ = divmod(r, 60)
            out_hrs = f"{h:02d}:{m:02d}"
            
    return total_hrs, late_hrs, out_hrs, ot_hrs

if 'last_edited' not in st.session_state:
    st.session_state.last_edited = None

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
            formatted_name = emp_name.strip().title()
            target_sheet = get_sheet_name(entry_date)
            df_month = load_data(target_sheet)
            
            day_str = entry_date.strftime("%a")
            date_str = entry_date.strftime("%d/%m/%Y")
            
            is_duplicate = not df_month[(df_month["Employee Name"] == formatted_name) & (df_month["Date"] == date_str)].empty
            
            if is_duplicate:
                st.error(f"⚠️ {formatted_name} ni tarikh {date_str} ni entry aagad thi j add kareli che!")
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
                save_data(df_month, target_sheet) 
                
                st.session_state.last_edited = f"{formatted_name}_{date_str}"
                st.success(f"Entry for {formatted_name} saved successfully!")
                st.rerun() 

st.divider()
st.subheader("📋 Search & Attendance Sheet")

# --- FILTER SECTION ---
col_s1, col_s2, col_s3 = st.columns([2, 2, 1])

with col_s1:
    available_sheets = ["Baddha Mahina (All Months)"] + get_all_sheet_names()
    selected_sheet = st.selectbox("Select Month to View", available_sheets)

with col_s2:
    all_emps = get_all_employees()
    # Default option "Select Employee" add karyu jethi pelathi data load na thay
    selected_emp = st.selectbox("Filter by Employee", ["Select Employee", "All"] + all_emps)

# Jo "Select Employee" rakhyu hoy to table hide rehse
if selected_emp == "Select Employee":
    st.info("👆 Upar 'Filter by Employee' mathi naam select karo athva type karo data jova mate.")
else:
    # ડેટા લોડ કરવાનું લોજીક
    if selected_sheet == "Baddha Mahina (All Months)":
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

        # એમ્પ્લોયી નામ પરથી ફિલ્ટર 
        if selected_emp != "All":
            df_display = df_display[df_display["Employee Name"] == selected_emp]

        if df_display.empty:
            st.warning(f"No records found for '{selected_emp}' in {selected_sheet}.")
        else:
            with col_s3:
                st.write("") 
                st.write("") 
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_export = df_display.drop(columns=["_Original_Sheet", "_Original_Index"], errors='ignore')
                    export_sheet_name = selected_sheet if selected_sheet != "Baddha Mahina (All Months)" else "All_Months"
                    df_export.to_excel(writer, index=False, sheet_name=export_sheet_name)
                    
                excel_data = buffer.getvalue()
                file_name_export = f"Attendance_{export_sheet_name}_{selected_emp}.xlsx".replace(" ", "_")
                st.download_button(
                    label="⬇️ Download Data (Excel)",
                    data=excel_data,
                    file_name=file_name_export,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            def highlight_rows(row):
                colors = [''] * len(row)
                if row['Day'] == 'Sun':
                    colors = ['background-color: #ff7f7f; color: white'] * len(row)
                if st.session_state.last_edited == f"{row['Employee Name']}_{row['Date']}":
                    colors = ['background-color: #ffffcc; color: black; font-weight: bold'] * len(row)
                return colors
            
            st.markdown("💡 **Tip:** Table ni dabi baaju checkbox select kari ne Edit ke Delete karo.")

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
                    st.warning(f"⚠️ Tame {len(selected_rows)} entries select kari che. Eksathe multiple entries khali delete thai shake.")
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
                                e_date = st.date_input("Date", value=d_obj, key="e_date")
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
                                
                                df_orig = load_data(selected_sheet_orig)
                                
                                if new_sheet == selected_sheet_orig:
                                    temp_check = df_orig.drop(selected_idx)
                                    is_dup = not temp_check[(temp_check["Employee Name"] == formatted_e_name) & (temp_check["Date"] == date_str_e)].empty
                                else:
                                    df_new = load_data(new_sheet)
                                    is_dup = not df_new[(df_new["Employee Name"] == formatted_e_name) & (df_new["Date"] == date_str_e)].empty

                                if is_dup:
                                    st.error("⚠️ Aa tarikh par aa employee ni entry pehla thi j che!")
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
                                        save_data(df_orig, selected_sheet_orig)
                                    else:
                                        df_orig = df_orig.drop(selected_idx)
                                        save_data(df_orig, selected_sheet_orig)
                                        df_new = pd.concat([df_new, updated_row], ignore_index=True)
                                        save_data(df_new, new_sheet)
                                    
                                    st.session_state.last_edited = f"{formatted_e_name}_{date_str_e}"
                                    st.success("✅ Entry updated successfully!")
                                    st.rerun()

                    with col_delete:
                        st.subheader("🗑️ Delete")
                        st.write("Aa entry ne hamesha mate kadhva mate niche click karo:")
                        if st.button("Delete This Entry", type="primary"):
                            df_orig = load_data(selected_sheet_orig)
                            df_orig = df_orig.drop(selected_idx) 
                            save_data(df_orig, selected_sheet_orig)
                            
                            st.session_state.last_edited = None
                            st.success("✅ Entry permanently deleted!")
                            st.rerun()

            st.markdown("---")
            
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
        st.info(f"No data available in {selected_sheet}. Please add an entry above.")
