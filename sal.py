import streamlit as st
import pandas as pd
import os
from datetime import datetime, time

# ફાઈલના નામ
LEAVE_FILE = "leave_data.csv"
RECORDS_FILE = "salary_records.xlsx"

def load_leave_data():
    if os.path.exists(LEAVE_FILE):
        return pd.read_csv(LEAVE_FILE)
    else:
        return pd.DataFrame(columns=["month", "pl_balance"])

def save_leave_data(balance):
    df = pd.DataFrame({"month": [datetime.now().strftime("%Y-%m")], "pl_balance": [balance]})
    df.to_csv(LEAVE_FILE, index=False)

def save_to_excel(record_dict):
    if os.path.exists(RECORDS_FILE):
        existing_df = pd.read_excel(RECORDS_FILE)
        new_df = pd.concat([existing_df, pd.DataFrame([record_dict])], ignore_index=True)
    else:
        new_df = pd.DataFrame([record_dict])
    new_df.to_excel(RECORDS_FILE, index=False)

# પેજ સેટઅપ
st.set_page_config(page_title="Salary Calculator", layout="wide")

# મુખ્ય હેડિંગ
st.markdown("<h1 style='text-align: center;'>💎 Salary Calculator</h1>", unsafe_allow_html=True)
st.markdown("---")

# --- PL લોજિક (સાઈડબાર) ---
df_leave = load_leave_data()
current_balance = float(df_leave["pl_balance"].iloc[-1]) if not df_leave.empty else 0.0

with st.sidebar:
    st.header("👤 Profile & Leave")
    user_name = st.text_input("Name", value="Maulik Patel")
    st.metric("Current PL Balance", f"{current_balance} Days")
    if st.button("Add 1 Monthly PL"):
        current_balance += 1.0
        save_leave_data(current_balance)
        st.success("1 PL Credited!")
        st.rerun()

# --- મુખ્ય ડિઝાઇન ---
# ત્રણ મુખ્ય ભાગોને કન્ટેનરમાં મૂકીએ
t1, t2, t3 = st.columns(3)

with t1:
    with st.container(border=True):
        st.subheader("💰 Salary Setup")
        month_year = st.selectbox("Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        basic_salary = st.number_input("Basic Salary", value=40000, step=500)
        working_days = st.number_input("Total Month Days", value=30)
        present_days = st.number_input("Present Days", value=26)

with t2:
    with st.container(border=True):
        st.subheader("🕒 Time Tracking")
        # In/Out ટાઈમ લાઈનમાં
        c1, c2 = st.columns(2)
        with c1: in_time = st.time_input("In Time", value=time(9, 0))
        with c2: out_time = st.time_input("Out Time", value=time(18, 0))
        
        st.divider()
        late_min = st.number_input("Late Mins", value=0)
        early_min = st.number_input("Early Going Mins", value=0)
        out_hrs = st.number_input("Personal Out (Mins)", value=0)
        
        total_lost = late_min + early_min + out_hrs
        deductible_min = max(0, total_lost - 120)

with t3:
    with st.container(border=True):
        st.subheader("📉 Deductions")
        used_pl = st.number_input("Use PL Balance", min_value=0.0, max_value=float(current_balance), value=0.0)
        loan = st.number_input("Loan / Advance", value=0)
        
        st.divider()
        st.caption("Enter Manual Amounts:")
        pf_amt = st.number_input("PF", value=0)
        esic_amt = st.number_input("ESIC", value=0)
        gratuity_amt = st.number_input("Gratuity", value=0)
        pt_amt = st.number_input("PT", value=200)

st.markdown("<br>", unsafe_allow_html=True)

# કેલ્ક્યુલેશન બટન સેન્ટરમાં
col_btn, col_res = st.columns([1, 2])

with col_btn:
    calculate = st.button("Calculate & Save to Excel", use_container_width=True, type="primary")

if calculate:
    # લોજિક
    per_day = basic_salary / working_days
    total_paid_days = present_days + used_pl
    attendance_pay = per_day * total_paid_days
    
    time_penalty = deductible_min * ((per_day / 8) / 60)
    total_deduction = pf_amt + esic_amt + gratuity_amt + pt_amt + loan + time_penalty
    net_salary = attendance_pay - total_deduction
    
    record = {
        "Date": datetime.now().strftime("%d-%m-%Y"),
        "Name": user_name,
        "Month": month_year,
        "Basic": basic_salary,
        "Paid Days": total_paid_days,
        "PF": pf_amt, "ESIC": esic_amt, "Gratuity": gratuity_amt, "PT": pt_amt,
        "Time Cut": round(time_penalty, 2),
        "Loan": loan,
        "Net Salary": round(net_salary, 2)
    }
    
    save_to_excel(record)
    save_leave_data(current_balance - used_pl)
    
    with col_res:
        st.success(f"Record Saved for {month_year}!")
        st.metric(label="Final Net Salary", value=f"₹{net_salary:,.2f}")
        st.balloons()

# હિસ્ટ્રી સેક્શન
if os.path.exists(RECORDS_FILE):
    st.divider()
    st.subheader("📂 Saved Records")
    st.dataframe(pd.read_excel(RECORDS_FILE), use_container_width=True)