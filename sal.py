import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os
from datetime import datetime

# ૧. પેજ સેટઅપ
st.set_page_config(page_title="Salary System", layout="wide")

# ૨. પાસવર્ડ પ્રોટેક્શન (Login)
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

conn = st.connection("gsheets", type=GSheetsConnection)

# ૩. PL Balance લોજિક
PL_FILE = "pl_data.csv"
def load_pl_balance():
    if os.path.exists(PL_FILE):
        try:
            df = pd.read_csv(PL_FILE)
            return int(df.iloc[-1]['balance'])
        except: return 0
    return 0

def save_pl_balance(new_balance):
    df = pd.DataFrame([{"date": datetime.now().strftime("%d-%m-%Y"), "balance": new_balance}])
    df.to_csv(PL_FILE, index=False)

current_pl = load_pl_balance()

# ૪. Sidebar - પ્રોફાઇલ (અહીં એક જ વાર નામ લખવાનું રહેશે)
with st.sidebar:
    st.header("👤 Profile")
    st.write("**Employee Name :red[*]**")
    # સાઈડબારમાં નામ ઇનપુટ
    emp_sidebar_name = st.text_input("sidebar_name", value="", placeholder="Enter Name Here...", label_visibility="collapsed")
    
    st.divider()
    st.subheader("📊 PL Balance")
    st.title(f"{current_pl} Days")
    
    if st.button("Add 1 Monthly PL", use_container_width=True):
        new_bal = current_pl + 1
        save_pl_balance(new_bal)
        st.success("✅ 1 PL Added!")
        st.rerun()

# ૫. મેઈન ફોર્મ - સેલરી વિગતો
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        # સ્માર્ટ ફેરફાર: સાઈડબારના નામને જ અહીં ડિસ્પ્લે કરવું
        # 'disabled=True' રાખવાથી યુઝરને અહીં ફરી ટાઈપ કરવાની જરૂર નહીં રહે
        emp_name = st.text_input("Full Name :red[*]", value=emp_sidebar_name, placeholder="Sidebar માં નામ લખો...", disabled=True)
        
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

# ૬. ગણતરી બટન
if st.button("Calculate & Save Data", type="primary", use_container_width=True):
    if not emp_sidebar_name or emp_sidebar_name.strip() == "":
        st.error("❗ મહારબાની કરીને સાઈડબારમાં નામ લખો!")
    else:
        try:
            hr_rate = (ctc_salary - gratuity) / work_hrs
            min_rate = hr_rate / 60
            actual_late = max(0, late_mins - 120)
            deduction = actual_late * min_rate
            ot_pay = ot_mins * min_rate
            net_salary = ctc_salary - deduction - food - gratuity - pt_tax + ot_pay
            
            st.success(f"✅ ગણતરી સફળ! {emp_sidebar_name} ની Net Salary: ₹{round(net_salary, 2)}")
            
            # PL વપરાઈ હોય તો CSV અપડેટ
            if used_pl > 0:
                save_pl_balance(current_pl - used_pl)
            st.balloons()
        except Exception as e:
            st.error(f"❌ એરર: {e}")

# ૭. સિક્યોર હિસ્ટ્રી
st.divider()
if emp_sidebar_name:
    st.subheader(f"📂 Recent History for {emp_sidebar_name}")
    try:
        df_history = conn.read(ttl=0)
        user_only_df = df_history[df_history['Name'] == emp_sidebar_name]
        if not user_only_df.empty:
            st.dataframe(user_only_df.tail(10), use_container_width=True)
        else:
            st.info(f"{emp_sidebar_name} માટે કોઈ રેકોર્ડ નથી.")
    except:
        st.info("ડેટા લોડ થઈ શક્યો નથી.")
