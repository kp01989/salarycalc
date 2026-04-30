import streamlit as st
from streamlit_gsheets import GSheetsConnection
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

# ૩. ફાઈલ મેનેજમેન્ટ ફંક્શન્સ
PL_FILE = "pl_data.csv"

def get_user_file(name):
    # નામમાંથી સ્પેસ કાઢીને ફાઈલનું નામ બનાવવું (દા.ત. Krutinkumar_Patel_salary.csv)
    safe_name = name.strip().replace(" ", "_")
    return f"{safe_name}_salary.csv"

def load_csv(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame()

# ૪. Sidebar - પ્રોફાઇલ
with st.sidebar:
    st.header("👤 Profile")
    st.write("**Employee Name :red[*]**")
    emp_sidebar_name = st.text_input("sidebar_name", value="", placeholder="Enter Name Here...", label_visibility="collapsed")
    
    st.divider()
    # PL લોડ કરવું
    pl_df = load_csv(PL_FILE)
    current_pl = int(pl_df.iloc[-1]['balance']) if not pl_df.empty else 0
    
    st.subheader("📊 PL Balance")
    st.title(f"{current_pl} Days")
    
    if st.button("Add 1 Monthly PL", use_container_width=True):
        new_bal = current_pl + 1
        new_pl_data = pd.DataFrame([{"date": datetime.now().strftime("%d-%m-%Y"), "balance": new_bal}])
        if os.path.exists(PL_FILE):
            new_pl_data.to_csv(PL_FILE, mode='a', header=False, index=False)
        else:
            new_pl_data.to_csv(PL_FILE, index=False)
        st.success("✅ 1 PL Added!")
        st.rerun()

# ૫. મેઈન ફોર્મ
col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        emp_name = st.text_input("Full Name :red[*]", value=emp_sidebar_name, disabled=True)
        month = st.selectbox("Select Month", ["Jan'26", "Feb'26", "Mar'26", "Apr'26", "May'26", "Jun'26"])
        ctc_salary = st.number_input("Monthly CTC", min_value=0, value=40000)
        work_hrs = st.number_input("Standard Work Hrs", min_value=1, value=248)

with col2:
    with st.container(border=True):
        st.subheader("🕒 Attendance & OT")
        present_hrs = st.number_input("Present Hrs", min_value=0, value=248)
        late_mins = st.number_input("Late Minutes", min_value=0, value=0)
        ot_mins = st.number_input("OT Minutes", min_value=0, value=0)
        used_pl = st.number_input("PL Used (Days)", min_value=0, value=0)

with col3:
    with st.container(border=True):
        st.subheader("📉 Deductions")
        food = st.number_input("Food Exp", min_value=0, value=0)
        gratuity = st.number_input("Gratuity", min_value=0, value=1200)
        pt_tax = st.number_input("PT Tax", min_value=0, value=200)

# ૬. ગણતરી અને નામ મુજબ અલગ ફાઈલમાં સેવ
if st.button("Calculate & Save Data", type="primary", use_container_width=True):
    if not emp_sidebar_name:
        st.error("❗ મહારબાની કરીને સાઈડબારમાં નામ લખો!")
    else:
        try:
            # ગણતરી લોજિક
            hr_rate = (ctc_salary - gratuity) / work_hrs
            min_rate = hr_rate / 60
            actual_late = max(0, late_mins - 120)
            deduction = actual_late * min_rate
            ot_pay = ot_mins * min_rate
            net_salary = ctc_salary - deduction - food - gratuity - pt_tax + ot_pay
            
            # ફાઈલ પાથ નક્કી કરવો
            user_file = get_user_file(emp_sidebar_name)
            
            # નવો રેકોર્ડ
            new_record = pd.DataFrame([{
                "Date": datetime.now().strftime("%d-%m-%Y"),
                "Name": emp_name,
                "Month": month,
                "Net Salary": round(net_salary, 2),
                "PL Used": used_pl
            }])
            
            # ફાઈલમાં ઉમેરો (Append)
            if os.path.exists(user_file):
                new_record.to_csv(user_file, mode='a', header=False, index=False)
            else:
                new_record.to_csv(user_file, index=False)
            
            # PL વપરાઈ હોય તો PL ફાઈલ અપડેટ
            if used_pl > 0:
                new_pl_row = pd.DataFrame([{"date": datetime.now().strftime("%d-%m-%Y"), "balance": current_pl - used_pl}])
                new_pl_row.to_csv(PL_FILE, mode='a', header=False, index=False)
            
            st.success(f"✅ ડેટા '{user_file}' માં સેવ થઈ ગયો!")
            st.balloons()
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ એરર: {e}")

# ૭. હિસ્ટ્રી બતાવવી (માત્ર અત્યારના યુઝરની ફાઈલમાંથી)
st.divider()
if emp_sidebar_name:
    user_file = get_user_file(emp_sidebar_name)
    st.subheader(f"📂 Recent History for {emp_sidebar_name}")
    
    if os.path.exists(user_file):
        history_df = pd.read_csv(user_file)
        st.dataframe(history_df.tail(10), use_container_width=True)
    else:
        st.info(f"{emp_sidebar_name} માટે હજુ સુધી કોઈ ફાઈલ બની નથી.")
            if os.path.exists(user_file):
        with open(user_file, "rb") as file:
            st.download_button(
                label=f"📥 Download {emp_sidebar_name}'s Salary File",
                data=file,
                file_name=user_file,
                mime="text/csv",
            )
