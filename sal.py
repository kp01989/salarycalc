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
# અહીં હેડિંગ પાછું ઉમેર્યું છે
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
        "CTC": 0, "Std_Hrs": 0, "Present_Hrs": 0, "Late": 0, "Food": 0, "Gratuity": 0, "PT": 0, "PL_Bal": 0
    }
    
    user_file = get_user_file(emp_sidebar_name)
    
    # એરર ફિક્સ: on_bad_lines='skip'
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
                last_data["PL_Bal"] = int(last_row.get("PL Balance", 0))
        except:
            pass

    st.subheader("📊 Current PL Balance")
    st.title(f"{last_data['PL_Bal']} Days")

# ૫. મેઈન ફોર્મ
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        emp_name = st.text_input("Full Name :red[*]", value=emp_sidebar_name, disabled=True)
        month = st.selectbox("Select Month", ["Jan'26", "Feb'26", "Mar'26", "Apr'26", "May'26", "Jun'26"])
        ctc_salary = st.number_input("Monthly CTC", min_value=0, value=last_data["CTC"])
        work_hrs = st.number_input("Standard Work Hrs", min_value=0, value=last_data["Std_Hrs"])

with col2:
    with st.container(border=True):
        st.subheader("🕒 Attendance & OT")
        present_hrs = st.number_input("Present Hrs", min_value=0, value=last_data["Present_Hrs"])
        late_mins = st.number_input("Late Minutes", min_value=0, value=last_data["Late"])
        ot_mins = st.number_input("OT Minutes", min_value=0, value=0)
        used_pl = st.number_input("PL Used (Days)", min_value=0, value=0)

with col3:
    with st.container(border=True):
        st.subheader("📉 Deductions")
        food = st.number_input("Food Exp", min_value=0, value=last_data["Food"])
        gratuity = st.number_input("Gratuity", min_value=0, value=last_data["Gratuity"])
        pt_tax = st.number_input("PT Tax", min_value=0, value=last_data["PT"])

# ૬. ગણતરી અને સેવિંગ
if st.button("Calculate & Save Data", type="primary", use_container_width=True):
    if not emp_sidebar_name:
        st.error("❗ મહારબાની કરીને સાઈડબારમાં નામ લખો!")
    elif work_hrs == 0:
        st.error("❗ Standard Work Hrs 0 ન હોઈ શકે!")
    else:
        try:
            hr_rate = (ctc_salary - gratuity) / work_hrs if work_hrs > 0 else 0
            min_rate = hr_rate / 60
            actual_late = max(0, late_mins - 120)
            deduction = actual_late * min_rate
            ot_pay = ot_mins * min_rate
            net_salary = ctc_salary - deduction - food - gratuity - pt_tax + ot_pay
            
            new_pl_balance = last_data["PL_Bal"] - used_pl
            
            new_record = pd.DataFrame([{
                "Date": datetime.now().strftime("%d-%m-%Y"),
                "Name": emp_name,
                "Month": month,
                "CTC": ctc_salary,
                "Std Hrs": work_hrs,
                "Present Hrs": present_hrs,
                "Late Mins": late_mins,
                "OT Mins": ot_mins,
                "Food": food,
                "Gratuity": gratuity,
                "Net Salary": round(net_salary, 2),
                "PL Used": used_pl,
                "PL Balance": new_pl_balance
            }])
            
            if os.path.exists(user_file):
                new_record.to_csv(user_file, mode='a', header=False, index=False)
            else:
                new_record.to_csv(user_file, index=False)
            
            st.success(f"✅ ડેટા સેવ થયો!")
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
            history_df = pd.read_csv(user_file, on_bad_lines='skip')
            st.dataframe(history_df.tail(10), use_container_width=True)
            
            with open(user_file, "rb") as f:
                st.download_button(label="📥 Download CSV", data=f, file_name=user_file, mime="text/csv")
        except:
            st.error(f"ફાઈલ વાંચવામાં સમસ્યા છે.")
    else:
        st.info(f"{emp_sidebar_name} માટે કોઈ જૂનો રેકોર્ડ નથી.")
