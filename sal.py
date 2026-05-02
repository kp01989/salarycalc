import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. Page Setup
st.set_page_config(page_title="Salary Management System", layout="wide")

# 2. Password Protection
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
                st.error("❌ Incorrect Password!")
    st.stop()

# --- Post-Login UI ---
st.markdown("<h1 style='text-align: center;'>💎 Salary & Leave Management</h1>", unsafe_allow_html=True)
st.divider()

# 3. File Management Functions
def get_user_file(name):
    if not name: return None
    safe_name = name.strip().replace(" ", "_")
    return f"{safe_name}_salary.csv"

# 4. Sidebar - Profile Section
with st.sidebar:
    st.header("👤 Profile")
    st.write("**Employee Name :red[*]**")
    emp_sidebar_name = st.text_input("sidebar_name", value="", placeholder="Enter Name Here...", label_visibility="collapsed")
    st.divider()

    last_data = {
        "CTC": 0, "Std_Hrs": 0, "Present_Hrs": 0, "Late": 0, "Food": 0, "Gratuity": 0, "PT": 0, 
        "PF": 0, "ESIC": 0, "Bonus": 0, "Advance": 0,
        "Last_Month": "", "Last_Year": 2026
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
                last_data["PT"] = 200
                last_data["PF"] = int(last_row.get("PF", 0))
                last_data["ESIC"] = int(last_row.get("ESIC", 0))
                last_data["Bonus"] = int(last_row.get("Bonus", 0))
                last_data["Advance"] = int(last_row.get("Advance", 0))
                last_data["Last_Month"] = str(last_row.get("Month", ""))
                last_data["Last_Year"] = int(last_row.get("Year", 2026))
        except:
            pass

# 5. Main Input Form
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        emp_name = st.text_input("Full Name :red[*]", value=emp_sidebar_name, disabled=True)
        
        m_col, y_col = st.columns(2)
        with m_col:
            month = st.selectbox("Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        with y_col:
            year = st.number_input("Year", min_value=2024, max_value=2030, value=2026)

        month_dict = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
        selected_month_num = month_dict[month]
        past_used_pl = 0

        if emp_sidebar_name and os.path.exists(user_file):
            try:
                df_hist = pd.read_csv(user_file, on_bad_lines='skip')
                if not df_hist.empty and "PL Used" in df_hist.columns:
                    df_hist['Month_Num'] = df_hist['Month'].map(month_dict)
                    df_past = df_hist[(df_hist['Year'] == year) & (df_hist['Month_Num'] <= selected_month_num)]
                    past_used_pl = pd.to_numeric(df_past['PL Used'], errors='coerce').fillna(0).sum()
            except:
                pass

        available_pl = max(0, int(selected_month_num - past_used_pl))

        ctc_salary = st.number_input("Monthly CTC", min_value=0, value=last_data["CTC"])
        work_hrs = st.number_input("Standard Work Hrs", min_value=0, value=last_data["Std_Hrs"])

with col2:
    with st.container(border=True):
        st.subheader("🕒 Attendance & OT")
        present_hrs = st.number_input("Present Hrs", min_value=0, value=last_data["Present_Hrs"])
        late_mins = st.number_input("Late Minutes", min_value=0, value=last_data["Late"])
        ot_mins = st.number_input("OT Minutes", min_value=0, value=0)
        
        used_pl = st.number_input("Paid Leave Used (Days)", min_value=0, max_value=available_pl if available_pl > 0 else 0, value=0)

        pl_bonus_mins = used_pl * 10 * 60
        deductible_late_mins = max(0, late_mins - 120) 
        
        total_minutes = (present_hrs * 60) + pl_bonus_mins - deductible_late_mins + ot_mins
        total_minutes = max(0, total_minutes)

        final_h = total_minutes // 60
        final_m = total_minutes % 60
        calculated_final_hrs = final_h + (final_m / 100)

        final_present_hrs = st.number_input("Final Present Hours", value=float(calculated_final_hrs), format="%.2f", disabled=True)

with col3:
    with st.container(border=True):
        st.subheader("📉 Deductions & Bonus")
        food = st.number_input("Food Exp", min_value=0, value=last_data["Food"])
        gratuity = st.number_input("Gratuity", min_value=0, value=last_data["Gratuity"])
        pt_tax = st.number_input("PT Tax", min_value=0, value=last_data["PT"])
        pf = st.number_input("Provident Fund (PF)", min_value=0, value=last_data["PF"])
        esic = st.number_input("ESIC", min_value=0, value=last_data["ESIC"])
        bonus = st.number_input("Performance Bonus", min_value=0, value=last_data["Bonus"])
        advance = st.number_input("Salary Advance", min_value=0, value=last_data["Advance"])

# Final PL Balance Display in Sidebar
with st.sidebar:
    st.subheader("📊 Current PL Balance")
    st.title(f"{available_pl - used_pl} Days")

# 6. Calculation and Data Storage
if st.button("Calculate & Save Data", type="primary", use_container_width=True):
    if not emp_sidebar_name:
        st.error("❗ Please enter employee name in the sidebar!")
    elif work_hrs == 0:
        st.error("❗ Standard Work Hours cannot be zero!")
    else:
        try:
            base_salary = ctc_salary - gratuity
            hr_rate = base_salary / work_hrs if work_hrs > 0 else 0
            min_rate = hr_rate / 60

            salary_for_hours = final_h * hr_rate
            salary_for_minutes = final_m * min_rate
            net_salary_before_deductions = salary_for_hours + salary_for_minutes

            net_salary = net_salary_before_deductions - food - pt_tax - pf - esic - advance + bonus
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
                "Final Present Hrs": calculated_final_hrs,
                "Food": food,
                "Gratuity": gratuity,
                "PT Tax": pt_tax,
                "PF": pf,
                "ESIC": esic,
                "Advance": advance,
                "Bonus": bonus,
                "Net Salary": round(net_salary, 2),
                "PL Used": used_pl,
                "PL Balance": final_pl_save
            }])

            if os.path.exists(user_file):
                old_df = pd.read_csv(user_file, on_bad_lines='skip')
                updated_df = pd.concat([old_df, new_record], ignore_index=True)
                updated_df.to_csv(user_file, index=False)
            else:
                new_record.to_csv(user_file, index=False)

            st.success(f"✅ Data saved successfully! Remaining PL: {final_pl_save}")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error occurred: {e}")

# 7. Optimized One-Line Search Section
st.divider()
st.subheader("🔍 Quick Search")
with st.container(border=True):
    # Name gets more space (ratio 4), others get less (ratio 1)
    sc1, sc2, sc3, sc4 = st.columns([4, 1.5, 1.5, 1.5])
    with sc1:
        search_name = st.text_input("Name", placeholder="e.g. Krutinkumar Patel", label_visibility="collapsed")
    with sc2:
        search_month = st.selectbox("Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], key="s_m", label_visibility="collapsed")
    with sc3:
        search_year = st.number_input("Year", min_value=2024, max_value=2030, value=2026, key="s_y", label_visibility="collapsed")
    with sc4:
        search_btn = st.button("🔍 Search", use_container_width=True)

if search_btn:
    if not search_name:
        st.warning("⚠️ Please enter a name to search.")
    else:
        s_file = get_user_file(search_name)
        if os.path.exists(s_file):
            df_s = pd.read_csv(s_file)
            res = df_s[(df_s['Month'] == search_month) & (df_s['Year'] == search_year)]
            if not res.empty:
                res.index = range(1, len(res) + 1)
                st.dataframe(res, use_container_width=True)
            else:
                st.warning("No record found.")
        else:
            st.error("File not found.")

# 8. Data History Log
st.divider()
if emp_sidebar_name:
    st.subheader(f"📂 History Log: {emp_sidebar_name}")
    if os.path.exists(user_file):
        try:
            history_df = pd.read_csv(user_file, on_bad_lines='skip').fillna(0)
            history_df.index = range(1, len(history_df) + 1)
            edited_df = st.data_editor(history_df, num_rows="dynamic", use_container_width=True, key="h_editor")
            
            c_b1, c_b2 = st.columns(2)
            with c_b1:
                with open(user_file, "rb") as f:
                    st.download_button(label="📥 Download CSV", data=f, file_name=user_file, mime="text/csv", use_container_width=True)
            with c_b2:
                if st.button("💾 Save Changes", type="primary", use_container_width=True):
                    edited_df.to_csv(user_file, index=False)
                    st.success("Changes saved!")
                    st.rerun()
        except:
            st.error("Failed to load history.")
