import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, time

# પેજ સેટઅપ
st.set_page_config(page_title="Salary Calculator", layout="wide")
st.markdown("<h1 style='text-align: center;'>💎 Salary Calculator</h1>", unsafe_allow_html=True)
st.markdown("---")

# ગૂગલ શીટ કનેક્શન
conn = st.connection("gsheets", type=GSheetsConnection)

# --- UI Layout ---
t1, t2, t3 = st.columns(3)

with t1:
    with st.container(border=True):
        st.subheader("💰 Salary Setup")
        month_year = st.selectbox("Month", ["Jan'26", "Feb'26", "Mar'26", "Apr'26", "May'26", "Jun'26"])
        user_name = st.text_input("Name", value="Krutinkumar Patel")
        ctc_salary = st.number_input("CTC Salary", value=40000)
        working_hrs = st.number_input("Working Hrs (Month)", value=248)

with t2:
    with st.container(border=True):
        st.subheader("🕒 Attendance & OT")
        present_hrs = st.number_input("Present Hrs", value=248)
        late_min = st.number_input("Late Minutes", value=0)
        out_min = st.number_input("Out Minutes", value=0)
        early_min = st.number_input("Early Going Minutes", value=0)
        ot_min = st.number_input("OT Minutes", value=0)
        st.write("<br>", unsafe_allow_html=True)

with t3:
    with st.container(border=True):
        st.subheader("📉 Deductions & Food")
        food_exp = st.number_input("Food Exp", value=0)
        pf_amt = st.number_input("PF", value=0)
        esic_amt = st.number_input("ESIC", value=0)
        gratuity_amt = st.number_input("Gratuity", value=1200)
        pt_amt = st.number_input("PT", value=200)
        used_pl = st.number_input("Used PL", value=0, step=1)

st.markdown("<br>", unsafe_allow_html=True)

# ગણતરી અને સેવ લોજિક
if st.button("Calculate & Save to Google Sheets", type="primary"):
    auto_date = datetime.now().strftime("%d-%m-%Y %H:%M")
    
    # કલાક દીઠ રેટ (CTC માંથી ગ્રેચ્યુઈટી બાદ કરીને)
    per_hour_rate = (ctc_salary - gratuity_amt) / working_hrs
    
    # OT અને કપાતની ગણતરી
    ot_pay = ot_min * (per_hour_rate / 60)
    total_late_mins = late_min + out_min + early_min
    
    # ૨ કલાક (120 મિનિટ) ની માફી પછીની કપાત
    deductible_min = max(0, total_late_mins - 120)
    time_cut = deductible_min * (per_hour_rate / 60)
    
    # ફાઈનલ નેટ સેલરી ફોર્મ્યુલા
    net_salary = ctc_salary - time_cut - food_exp - pf_amt - esic_amt - gratuity_amt - pt_amt + ot_pay
    
    # નવો ડેટા રેકોર્ડ
    new_data = pd.DataFrame([{
        "Entry Date": auto_date,
        "Month": month_year,
        "Name": user_name,
        "CTC Salary": ctc_salary,
        "Late Minutes": late_min,
        "Out Minutes": out_min,
        "Early Going": early_min,
        "OT Minutes": ot_min,
        "Food": food_exp,
        "PF": pf_amt,
        "ESIC": esic_amt,
        "Gratuity": gratuity_amt,
        "PT": pt_amt,
        "Used PL": used_pl,
        "Net Salary": round(net_salary, 2)
    }])
    
    try:
        # કોઈ પણ શીટનું નામ આપ્યા વગર સીધું રીડ/અપડેટ (પહેલી ટેબ લેશે)
        existing_df = conn.read(ttl=0)
        updated_df = pd.concat([existing_df, new_data], ignore_index=True)
        conn.update(data=updated_df)
        
        st.success(f"✅ સેવ થઈ ગયું! Net Salary: ₹{round(net_salary, 2)}")
        st.balloons()
    except Exception as e:
        st.error(f"ભૂલ આવી: {e}")
        st.info("નોંધ: ખાતરી કરો કે Google Sheet ની પહેલી લાઈનમાં હેડિંગ્સ લખેલા છે.")

# હિસ્ટ્રી બતાવવી
try:
    df_history = conn.read(ttl=0)
    if not df_history.empty:
        st.divider()
        st.subheader("📂 History (Google Sheets)")
        st.dataframe(df_history, use_container_width=True)
except:
    pass
