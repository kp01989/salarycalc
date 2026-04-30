import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os
from datetime import datetime

# ૧. પેજ કન્ફિગરેશન
st.set_page_config(page_title="Salary & PL System", layout="wide")
st.markdown("<h1 style='text-align: center;'>💎 Salary & PL Management System</h1>", unsafe_allow_html=True)
st.markdown("---")

# ૨. ગૂગલ શીટ કનેક્શન સેટઅપ
conn = st.connection("gsheets", type=GSheetsConnection)

# ૩. PL Balance મેળવવાનું ફંક્શન (Default 0)
def get_pl_balance():
    try:
        # તમારી શીટમાં 'PL_Sheet' નામની ટેબ હોવી જોઈએ
        df_pl = conn.read(worksheet="PL_Sheet", ttl=0)
        if not df_pl.empty:
            return int(df_pl.iloc[-1]["balance"])
        return 0
    except Exception:
        return 0

current_pl = get_pl_balance()

# ૪. Sidebar - પ્રોફાઇલ અને PL મેનેજમેન્ટ
with st.sidebar:
    st.header("👤 Profile")
    st.write("**Employee Name:**")
    # Placeholder સાથે નામનું ઇનપુટ
    display_name = st.text_input("Name Display", value="", placeholder="Enter Name Here...", label_visibility="collapsed")
    
    st.divider()
    st.subheader("📊 PL Balance")
    st.title(f"{current_pl} Days")
    
    if st.button("Add 1 Monthly PL", use_container_width=True):
        new_balance = current_pl + 1
        pl_record = pd.DataFrame([{"date": datetime.now().strftime("%d-%m-%Y"), "balance": new_balance}])
        conn.update(worksheet="PL_Sheet", data=pl_record)
        st.success("✅ 1 PL ઉમેરાઈ ગઈ!")
        st.rerun()

# ૫. મેઈન ફોર્મ - સેલરી વિગતો
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        # Compulsory Name Field
        emp_name = st.text_input("Full Name", value="", placeholder="Enter Employee Name")
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

st.markdown("<br>", unsafe_allow_html=True)

# ૬. ગણતરી અને સેવ કરવાનું લોજિક
if st.button("Calculate & Save to Google Sheet", type="primary", use_container_width=True):
    # ફરજિયાત નામ ચેક કરો
    if not emp_name or emp_name.strip() == "":
        st.error("❗ મહેરબાની કરીને કર્મચારીનું નામ લખો! (Name is Compulsory)")
    else:
        try:
            # પગારની ગણતરી
            hr_rate = (ctc_salary - gratuity) / work_hrs
            min_rate = hr_rate / 60
            
            # ૧૨૦ મિનિટ માફી બાદ લેટ કપાત
            actual_late = max(0, late_mins - 120)
            deduction = actual_late * min_rate
            ot_pay = ot_mins * min_rate
            
            net_salary = ctc_salary - deduction - food - gratuity - pt_tax + ot_pay
            
            # નવો રેકોર્ડ તૈયાર કરવો
            new_data = pd.DataFrame([{
                "Entry Date": datetime.now().strftime("%d-%m-%Y %H:%M"),
                "Name": emp_name,
                "Month": month,
                "CTC": ctc_salary,
                "Net Salary": round(net_salary, 2),
                "PL Balance": current_pl - used_pl
            }])
            
            # ગૂગલ શીટ અપડેટ (પહેલી ટેબમાં)
            existing_df = conn.read(ttl=0)
            updated_df = pd.concat([existing_df, new_data], ignore_index=True)
            conn.update(data=updated_df)
            
            # જો PL વપરાઈ હોય તો PL_Sheet પણ અપડેટ કરો
            if used_pl > 0:
                new_pl_bal = current_pl - used_pl
                pl_upd = pd.DataFrame([{"date": datetime.now().strftime("%d-%m-%Y"), "balance": new_pl_bal}])
                conn.update(worksheet="PL_Sheet", data=pl_upd)
            
            st.success(f"✅ સેવ થઈ ગયું! Net Salary: ₹{round(net_salary, 2)}")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ એરર આવી: {e}")

# ૭. હિસ્ટ્રી બતાવવી
st.divider()
st.subheader("📂 Recent History")
try:
    df_history = conn.read(ttl=0)
    st.dataframe(df_history.tail(5), use_container_width=True)
except:
    st.info("હજુ સુધી કોઈ ડેટા નથી.")
