import streamlit as st 
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from datetime import datetime, time

# સાચો રસ્તો આ છે:
conn = st.connection("gsheets", type=GSheetsConnection)
# ફાઈલના નામ
LEAVE_FILE = "leave_data.csv"
RECORDS_FILE = "salary_records.xlsx"

def load_leave_data():
    if os.path.exists(LEAVE_FILE): return pd.read_csv(LEAVE_FILE)
    else: return pd.DataFrame(columns=["month", "pl_balance"])

def save_leave_data(balance):
    df = pd.DataFrame({"month": [datetime.now().strftime("%y-%m")], "pl_balance": [balance]})
    df.to_csv(LEAVE_FILE, index=False)

def save_to_excel(record_dict):
    if os.path.exists(RECORDS_FILE):
        existing_df = pd.read_excel(RECORDS_FILE)
        new_df = pd.concat([existing_df, pd.DataFrame([record_dict])], ignore_index=True)
    else: new_df = pd.DataFrame([record_dict])
    new_df.to_excel(RECORDS_FILE, index=False)

st.set_page_config(page_title="Salary Calculator", layout="wide")
st.markdown("<h1 style='text-align: center;'>💎 Salary Calculator</h1>", unsafe_allow_html=True)
st.markdown("---")

# સાઈડબાર
df_leave = load_leave_data()
current_balance = float(df_leave["pl_balance"].iloc[-1]) if not df_leave.empty else 0.0
with st.sidebar:
    st.header("👤 Profile")
    user_name = st.text_input("Name", value="Maulik Patel")
    st.metric("PL Balance", f"{int(current_balance)} Days")
    if st.button("Add 1 Monthly PL"):
        current_balance += 1.0
        save_leave_data(current_balance)
        st.rerun()

# મુખ્ય ત્રણ કોલમ
t1, t2, t3 = st.columns(3)

with t1:
    with st.container(border=True):
        st.subheader("💰 Salary Setup")
        entry_date = st.date_input("Date", datetime.now())
        month_year = st.selectbox("Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        # Label changed to CTC Salary
        ctc_salary = st.number_input("CTC Salary", value=40000)
        working_days = st.number_input("Total Days", value=30)
        present_days = st.number_input("Present Days", value=26)

with t2:
    with st.container(border=True):
        st.subheader("🕒 Time Tracking")
        c1, c2 = st.columns(2)
        with c1: in_time = st.time_input("In Time", value=time(9, 0))
        with c2: out_time = st.time_input("Out Time", value=time(18, 0))
        st.divider()
        late_min = st.number_input("Late (Mins)", value=0)
        early_min = st.number_input("Early (Mins)", value=0)
        out_hrs = st.number_input("Personal Out (Mins)", value=0)
        st.write("<br>", unsafe_allow_html=True)

with t3:
    with st.container(border=True):
        st.subheader("📉 Deductions")
        used_pl = st.number_input("Use PL", min_value=0, max_value=int(current_balance), value=0, step=1)
        loan = st.number_input("Loan Amount", value=0)
        st.divider()
        pf_amt = st.number_input("PF", value=0)
        esic_amt = st.number_input("ESIC", value=0)
        gratuity_amt = st.number_input("Gratuity", value=0)
        pt_amt = st.number_input("PT", value=200)

st.markdown("<br>", unsafe_allow_html=True)

# Calculate button size kept normal (not wide)
if st.button("Calculate & Save Record", type="primary"):
    per_day = ctc_salary / working_days
    total_paid = present_days + used_pl
    att_pay = per_day * total_paid
    
    deductible_min = max(0, (late_min + early_min + out_hrs) - 120)
    time_cut = deductible_min * ((per_day / 8) / 60)
    
    net_salary = att_pay - (pf_amt + esic_amt + gratuity_amt + pt_amt + loan + time_cut)
    
    record = {
        "Date": entry_date.strftime("%d-%m-%Y"),
        "Name": user_name, 
        "Month": month_year, 
        "CTC Salary": ctc_salary,
        "PF": pf_amt,
        "ESIC": esic_amt,
        "Gratuity": gratuity_amt,
        "Net Salary": round(net_salary, 2)
    }
    
    save_to_excel(record)
    save_leave_data(float(current_balance - used_pl))
    st.success(f"Record Saved Successfully!")
    st.metric("Final Net Salary", f"₹{net_salary:,.2f}")

if os.path.exists(RECORDS_FILE):
    st.divider()
    st.subheader("📂 History")
    st.dataframe(pd.read_excel(RECORDS_FILE), use_container_width=True)
