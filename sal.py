import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ૧. પેજ સેટઅપ
st.set_page_config(page_title="Salary System", layout="wide")

# ૨. પાસવર્ડ પ્રોટેક્શન
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Salary System Login</h2>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1,1,1])
    with col_m:
        pwd_input = st.text_input("Enter Password", type="password")
        if st.button("Login", use_container_width=True):
            if pwd_input == "123": 
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ ખોટો પાસવર્ડ!")
    st.stop()

# --- લોગિન પછીનો કોડ ---
st.markdown("<h1 style='text-align: center;'>💎 Salary & PL Management</h1>", unsafe_allow_html=True)
st.divider()

# ૩. ફાઈલ મેનેજમેન્ટ ફંક્શન
def get_user_file(name):
    if not name: return None
    safe_name = name.strip().replace(" ", "_")
    return f"{safe_name}_salary.csv"

# ૪. Sidebar - પ્રોફાઇલ
with st.sidebar:
    st.header("👤 Profile")
    st.write("**Employee Name :red[*]**")
    emp_sidebar_name = st.text_input("sidebar_name", value="", placeholder="Enter Name Here...", label_visibility="collapsed")
    
    st.divider()
    
    last_data = {
        "CTC": 0, "Std_Hrs": 0, "Present_Hrs": 0, "Late": 0, "Food": 0, "Gratuity": 0, "PT": 0, 
        "Last_Month": "", "Last_Year": 0
    }
    
    user_file = get_user_file(emp_sidebar_name)
    
    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file, on_bad_lines='skip')
            if not df_hist.empty:
                last_row = df_hist.iloc[-1]
                last_data["CTC"] = int(last_row.get("CTC", 0))
                last_data["Std_Hrs"] = int(last_row.get("Std Hrs", 0))
                last_data["Present_Hrs"] = int(last_row.get("Present Hrs", 0))
                last_data["Late"] = int(last_row.get("Late Mins", 0))
                last_data["Food"] = int(last_row.get("Food", 0))
                last_data["Gratuity"] = int(last_row.get("Gratuity", 0))
                last_data["PT"] = 200 if "Net Salary" in last_row else 0
                last_data["Last_Month"] = str(last_row.get("Month", ""))
                last_data["Last_Year"] = int(last_row.get("Year", 0))
        except:
            pass

# ૫. મેઈન ફોર્મ
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        emp_name = st.text_input("Full Name :red[*]", value=emp_sidebar_name, disabled=True)
        
        # --- Month અને Year અલગ બોક્સ ---
        m_col, y_col = st.columns(2)
        with m_col:
            month = st.selectbox("Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        with y_col:
            year = st.number_input("Year", min_value=2024, max_value=2030, value=2026)
        
        # --- કેલેન્ડર મુજબ PL ની ગણતરી (Calendar PL Logic) ---
        month_dict = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
        selected_month_num = month_dict[month]
        
        past_used_pl = 0
        if emp_sidebar_name and os.path.exists(user_file):
            try:
                df_hist = pd.read_csv(user_file, on_bad_lines='skip')
                if not df_hist.empty and "PL Used" in df_hist.columns and "Month" in df_hist.columns and "Year" in df_hist.columns:
                    # Create numeric month for comparison
                    df_hist['Month_Num'] = df_hist['Month'].map(month_dict)
                    # Filter history to find PLs used in the SAME year, but strictly BEFORE the selected month
                    df_past = df_hist[(df_hist['Year'] == year) & (df_hist['Month_Num'] < selected_month_num)]
                    past_used_pl = pd.to_numeric(df_past['PL Used'], errors='coerce').fillna(0).sum()
            except Exception as e:
                pass
        
        # Total Available PL before current month usage
        available_pl = selected_month_num - past_used_pl
        available_pl = max(0, int(available_pl)) 

        ctc_salary = st.number_input("Monthly CTC", min_value=0, value=last_data["CTC"])
        work_hrs = st.number_input("Standard Work Hrs", min_value=0, value=last_data["Std_Hrs"])

with col2:
    with st.container(border=True):
        st.subheader("🕒 Attendance & OT")
        present_hrs = st.number_input("Present Hrs", min_value=0, value=last_data["Present_Hrs"])
        late_mins = st.number_input("Late Minutes", min_value=0, value=last_data["Late"])
        ot_mins = st.number_input("OT Minutes", min_value=0, value=0)
        
        # --- Final Present Hours Formula (HH.MM Format) ---
        deductible_late_mins = max(0, late_mins - 120) 
        total_minutes = (present_hrs * 60) - deductible_late_mins + ot_mins
        total_minutes = max(0, total_minutes)
        
        final_h = total_minutes // 60
        final_m = total_minutes % 60
        calculated_final_hrs = final_h + (final_m / 100)
        
        final_present_hrs = st.number_input("Final Present Hours", value=float(calculated_final_hrs), format="%.2f", disabled=True)
        
        used_pl = st.number_input("PL Used (Days)", min_value=0, max_value=available_pl, value=0)

with col3:
    with st.container(border=True):
        st.subheader("📉 Deductions")
        food = st.number_input("Food Exp", min_value=0, value=last_data["Food"])
        gratuity = st.number_input("Gratuity", min_value=0, value=last_data["Gratuity"])
        pt_tax = st.number_input("PT Tax", min_value=0, value=last_data["PT"])

# સાઈડબારમાં ફાઈનલ PL
with st.sidebar:
    st.subheader("📊 Current PL Balance")
    st.title(f"{available_pl - used_pl} Days")

# ૬. ગણતરી અને સેવિંગ
if st.button("Calculate & Save Data", type="primary", use_container_width=True):
    if not emp_sidebar_name:
        st.error("❗ મહારબાની કરીને સાઈડબારમાં નામ લખો!")
    elif work_hrs == 0:
        st.error("❗ Standard Work Hrs 0 ન હોઈ શકે!")
    else:
        try:
            # 1. Final Present Hours and Minutes Calculation
            deductible_late_mins = max(0, late_mins - 120) 
            total_minutes = (present_hrs * 60) - deductible_late_mins + ot_mins
            total_minutes = max(0, total_minutes)
            
            final_h = total_minutes // 60
            final_m = total_minutes % 60
            
            # 2. Salary Calculation Logic 
            base_salary = ctc_salary - gratuity
            
            hr_rate = base_salary / work_hrs if work_hrs > 0 else 0
            min_rate = hr_rate / 60
            
            salary_for_hours = final_h * hr_rate
            salary_for_minutes = final_m * min_rate
            
            net_salary_before_deductions = salary_for_hours + salary_for_minutes
            
            net_salary = net_salary_before_deductions - food - pt_tax
            
            final_pl_save = available_pl - used_pl
            
            new_record = pd.DataFrame([{
                "Date": datetime.now().strftime("%d-%m-%Y"),
                "Name": emp_name,
                "Month": month,
                "Year": year,
                "CTC": ctc_salary,
                "Std Hrs": work_hrs,
                "Present Hrs": present_hrs,
                "Late Mins": late_mins,
                "OT Mins": ot_mins,
                "Final Present Hrs": final_present_hrs,
                "Food": food,
                "Gratuity": gratuity,
                "Net Salary": round(net_salary, 2),
                "PL Used": used_pl,
                "PL Balance": final_pl_save
            }])
            
            # --- AUTO FIX LOGIC FOR OLD FILES ---
            if os.path.exists(user_file):
                try:
                    # Read the old file
                    old_df = pd.read_csv(user_file, on_bad_lines='skip')
                    # Concatenate old data with the new record
                    updated_df = pd.concat([old_df, new_record], ignore_index=True)
                    # Overwrite the file cleanly
                    updated_df.to_csv(user_file, index=False)
                except:
                    # Fallback just in case
                    new_record.to_csv(user_file, mode='a', header=False, index=False)
            else:
                new_record.to_csv(user_file, index=False)
            
            st.success(f"✅ ડેટા સેવ થયો! નવું PL બેલેન્સ: {final_pl_save}")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"❌ એરર: {e}")

# ૭. હિસ્ટ્રી
st.divider()
if emp_sidebar_name:
    st.subheader(f"📂 Recent History for {emp_sidebar_name}")
    if os.path.exists(user_file):
        try:
            history_df = pd.read_csv(user_file, on_bad_lines='skip').fillna(0)
            st.dataframe(history_df.tail(10), use_container_width=True)
            with open(user_file, "rb") as f:
                st.download_button(label="📥 Download CSV", data=f, file_name=user_file, mime="text/csv")
        except:
            st.error(f"ફાઈલ વાંચવામાં સમસ્યા છે.")
