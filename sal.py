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

# ૩. ફાઈલ મેનેજમેન્ટ ફંક્શન્સ
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
    
    # PL બેલેન્સ લોજિક - ફાઈલમાંથી છેલ્લું બેલેન્સ ખેંચવું
    user_pl_balance = 0
    user_file = get_user_file(emp_sidebar_name)
    
    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file)
            if not df_hist.empty and "PL Balance" in df_hist.columns:
                user_pl_balance = int(df_hist.iloc[-1]['PL Balance'])
        except:
            user_pl_balance = 0

    st.subheader("📊 Current PL Balance")
    st.title(f"{user_pl_balance} Days")
    st.info("નોંધ: PL વપરાશ મુજબ બેલેન્સ ઓટોમેટિક અપડેટ થશે.")

# ૫. મેઈન ફોર્મ - ડાયનેમિક વેલ્યુઝ (જો નામ બદલાય તો બધું 0)
# 'key' પેરામીટર વાપરવાથી જ્યારે નામ બદલાશે ત્યારે ફોર્મ રીસેટ થઈ જશે
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        emp_name = st.text_input("Full Name :red[*]", value=emp_sidebar_name, disabled=True)
        month = st.selectbox("Select Month", ["Jan'26", "Feb'26", "Mar'26", "Apr'26", "May'26", "Jun'26"])
        
        # જો નામ ખાલી હોય તો ડિફોલ્ટ 0, નહીંતર છેલ્લી વેલ્યુ (Optional)
        ctc_salary = st.number_input("Monthly CTC", min_value=0, value=0 if not emp_sidebar_name else 30000)
        work_hrs = st.number_input("Standard Work Hrs", min_value=0, value=0 if not emp_sidebar_name else 260)

with col2:
    with st.container(border=True):
        st.subheader("🕒 Attendance & OT")
        present_hrs = st.number_input("Present Hrs", min_value=0, value=0 if not emp_sidebar_name else 220)
        late_mins = st.number_input("Late Minutes", min_value=0, value=0 if not emp_sidebar_name else 30)
        ot_mins = st.number_input("OT Minutes", min_value=0, value=0)
        used_pl = st.number_input("PL Used (Days)", min_value=0, value=0)

with col3:
    with st.container(border=True):
        st.subheader("📉 Deductions")
        food = st.number_input("Food Exp", min_value=0, value=0 if not emp_sidebar_name else 275)
        gratuity = st.number_input("Gratuity", min_value=0, value=0 if not emp_sidebar_name else 1200)
        pt_tax = st.number_input("PT Tax", min_value=0, value=0 if not emp_sidebar_name else 200)

# ૬. ગણતરી અને સેવિંગ
if st.button("Calculate & Save Data", type="primary", use_container_width=True):
    if not emp_sidebar_name:
        st.error("❗ મહારબાની કરીને સાઈડબારમાં નામ લખો!")
    elif work_hrs == 0:
        st.error("❗ Standard Work Hrs 0 ન હોઈ શકે!")
    else:
        try:
            # ગણતરી
            hr_rate = (ctc_salary - gratuity) / work_hrs if work_hrs > 0 else 0
            min_rate = hr_rate / 60
            actual_late = max(0, late_mins - 120)
            deduction = actual_late * min_rate
            ot_pay = ot_mins * min_rate
            net_salary = ctc_salary - deduction - food - gratuity - pt_tax + ot_pay
            
            # નવું PL બેલેન્સ
            new_pl_balance = user_pl_balance - used_pl
            
            # રેકોર્ડ તૈયાર કરવો
            new_record = pd.DataFrame([{
                "Date": datetime.now().strftime("%d-%m-%Y"),
                "Name": emp_name,
                "Month": month,
                "CTC": ctc_salary,
                "Present Hrs": present_hrs,
                "Late Mins": late_mins,
                "Food": food,
                "Net Salary": round(net_salary, 2),
                "PL Used": used_pl,
                "PL Balance": new_pl_balance
            }])
            
            # ફાઈલમાં સેવ
            if os.path.exists(user_file):
                new_record.to_csv(user_file, mode='a', header=False, index=False)
            else:
                new_record.to_csv(user_file, index=False)
            
            st.success(f"✅ ડેટા સેવ થયો! નવી Net Salary: ₹{round(net_salary, 2)} | નવું PL બેલેન્સ: {new_pl_balance}")
            st.balloons()
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ એરર: {e}")

# ૭. હિસ્ટ્રી અને ડાઉનલોડ
st.divider()
if emp_sidebar_name:
    st.subheader(f"📂 Recent History for {emp_sidebar_name}")
    if os.path.exists(user_file):
        history_df = pd.read_csv(user_file)
        st.dataframe(history_df.tail(10), use_container_width=True)
        
        with open(user_file, "rb") as f:
            st.download_button(
                label=f"📥 Download {emp_sidebar_name}'s Report",
                data=f,
                file_name=user_file,
                mime="text/csv"
            )
    else:
        st.info(f"{emp_sidebar_name} માટે કોઈ જૂનો રેકોર્ડ નથી.")
