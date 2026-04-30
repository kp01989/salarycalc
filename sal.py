import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import os
from datetime import datetime

# પેજ સેટઅપ
st.set_page_config(page_title="Salary Calculator", layout="wide")
st.markdown("<h1 style='text-align: center;'>💎 Salary Management System</h1>", unsafe_allow_html=True)
st.markdown("---")

# ગૂગલ શીટ કનેક્શન (Secrets માંથી લિંક ઉપાડશે)
conn = st.connection("gsheets", type=GSheetsConnection)

# --- UI Layout: Columns ---
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("💰 Basic Details")
        # Placeholder અને Compulsory ફિલ્ડ્સ
        user_name = st.text_input("Full Name", placeholder="Enter Employee Name")
        month_year = st.selectbox("Select Month", ["Jan'26", "Feb'26", "Mar'26", "Apr'26", "May'26", "Jun'26"])
        ctc_salary = st.number_input("CTC Salary (Monthly)", min_value=0, value=40000)
        working_hrs = st.number_input("Working Hrs (As per Policy)", min_value=1, value=248)

with col2:
    with st.container(border=True):
        st.subheader("🕒 Attendance & OT")
        present_hrs = st.number_input("Present Hrs", min_value=0, value=248)
        late_min = st.number_input("Late Minutes", min_value=0, value=0)
        out_min = st.number_input("Out Minutes", min_value=0, value=0)
        early_going = st.number_input("Early Going Minutes", min_value=0, value=0)
        ot_minutes = st.number_input("Overtime (Minutes)", min_value=0, value=0)

with col3:
    with st.container(border=True):
        st.subheader("📉 Deductions & Benefits")
        food_exp = st.number_input("Food Expenses", min_value=0, value=0)
        pf_amt = st.number_input("PF Deduction", min_value=0, value=0)
        esic_amt = st.number_input("ESIC", min_value=0, value=0)
        gratuity = st.number_input("Gratuity Contribution", min_value=0, value=1200)
        pt_tax = st.number_input("Professional Tax (PT)", min_value=0, value=200)

st.markdown("<br>", unsafe_allow_html=True)

# --- Calculation & Save Logic ---
if st.button("Calculate & Save to Google Sheet", type="primary", use_container_width=True):
    
    # Compulsory Field Check: જો નામ ખાલી હોય તો
    if not user_name or user_name.strip() == "":
        st.error("❗ Employee Name લખવું ફરજિયાત છે! (Name is Compulsory)")
    else:
        try:
            # ૧. પગારની ગણતરી (Salary Calculations)
            per_hour_rate = (ctc_salary - gratuity) / working_hrs
            per_min_rate = per_hour_rate / 60
            
            # OT અને કપાત (Late Mins માં ૧૨૦ મિનિટની માફી બાદ કર્યા પછી)
            ot_pay = ot_minutes * per_min_rate
            total_late_mins = late_min + out_min + early_going
            deductible_late_mins = max(0, total_late_mins - 120)
            late_deduction = deductible_late_mins * per_min_rate
            
            # Final Net Salary
            net_salary = (ctc_salary - late_deduction - food_exp - pf_amt - esic_amt - gratuity - pt_tax + ot_pay)
            
            # ૨. નવો ડેટા રેકોર્ડ તૈયાર કરવો (Automatic new_record)
            new_record = pd.DataFrame([{
                "Entry Date": datetime.now().strftime("%d-%m-%Y %H:%M"),
                "Month": month_year,
                "Name": user_name,
                "CTC": ctc_salary,
                "Total Late Mins": total_late_mins,
                "OT Mins": ot_minutes,
                "Food": food_exp,
                "PF": pf_amt,
                "PT": pt_tax,
                "Gratuity": gratuity,
                "Net Salary": round(net_salary, 2)
            }])
            
            # ૩. ગૂગલ શીટમાં સેવ કરવું
            # જૂનો ડેટા વાંચો
            existing_df = conn.read(ttl=0)
            
            # નવો અને જૂનો ડેટા ભેગો કરો
            updated_df = pd.concat([existing_df, new_record], ignore_index=True)
            
            # શીટ અપડેટ કરો
            conn.update(data=updated_df)
            
            st.success(f"🎉 {user_name} નો ડેટા સફળતાપૂર્વક સેવ થયો! Net Salary: ₹{round(net_salary, 2)}")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ ભૂલ આવી: {e}")
            st.info("નોંધ: ખાતરી કરો કે 'Secrets' માં ગૂગલ શીટની લિંક સાચી છે અને શીટમાં 'Editor' પરમિશન છે.")

# --- History Table ---
st.divider()
st.subheader("📂 Recent Entries")
try:
    history_df = conn.read(ttl=0)
    if not history_df.empty:
        st.dataframe(history_df.tail(10), use_container_width=True) # છેલ્લા ૧૦ રેકોર્ડ બતાવશે
except:
    st.write("હજુ સુધી કોઈ ડેટા ઉપલબ્ધ નથી.")
