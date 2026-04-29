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

# સાઈડબાર - પ્રોફાઈલ અને PL બેલેન્સ
# (PL બેલેન્સનું લોજિક તમે તમારી રીતે મેન્ટેન કરી શકો છો)
with st.sidebar:
    st.header("👤 Profile")
    user_name = st.text_input("Name", value="Maulik Patel")
    st.info("નોંધ: એન્ટ્રી સેવ કરવાથી ગૂગલ શીટમાં ડેટા અપડેટ થશે.")

# મુખ્ય ત્રણ કોલમ - તમારા ફોટા મુજબ ડિઝાઇન
t1, t2, t3 = st.columns(3)

with t1:
    with st.container(border=True):
        st.subheader("💰 Salary Setup")
        month_year = st.selectbox("Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
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
        used_pl = st.number_input("Use PL", min_value=0, value=0, step=1)
        loan = st.number_input("Loan Amount", value=0)
        st.divider()
        pf_amt = st.number_input("PF", value=0)
        esic_amt = st.number_input("ESIC", value=0)
        gratuity_amt = st.number_input("Gratuity", value=0)
        pt_amt = st.number_input("PT", value=200)

st.markdown("<br>", unsafe_allow_html=True)

# ગણતરી લોજિક (Calculation Check)
if st.button("Calculate & Save Record", type="primary"):
    auto_date = datetime.now().strftime("%d-%m-%Y %H:%M")
    
    # ૧. પર ડે સેલરી
    per_day = ctc_salary / working_days
    
    # ૨. હાજર દિવસો + PL
    total_paid_days = present_days + used_pl
    
    # ૩. એટેન્ડન્સ મુજબ સેલરી (પગાર)
    attendance_pay = per_day * total_paid_days
    
    # ૪. મોડા આવવાનું કપાત (2 કલાક એટલે કે 120 મિનિટ ફ્રી)
    total_late_mins = late_min + early_min + out_hrs
    deductible_min = max(0, total_late_mins - 120)
    time_cut_amt = deductible_min * ((per_day / 8) / 60)
    
    # ૫. ફાઈનલ નેટ સેલરી (તમારા ફોર્મેટ મુજબ બધી કપાત બાદ કરીએ)
    # Net Salary = (Pay per attendance) - PF - ESIC - Gratuity - PT - Loan - Time Cut
    net_salary = attendance_pay - (pf_amt + esic_amt + gratuity_amt + pt_amt + loan + time_cut_amt)
    
    # Excel/Google Sheet માટેનું ફોર્મેટ (તમારા ફોટા મુજબની કોલમ)
    new_record = pd.DataFrame([{
        "Entry Date": auto_date,
        "Name": user_name,
        "Month": month_year,
        "CTC Salary": ctc_salary,
        "Total Days": working_days,
        "Present": present_days,
        "Used PL": used_pl,
        "PF": pf_amt,
        "ESIC": esic_amt,
        "Gratuity": gratuity_amt,
        "PT": pt_amt,
        "Loan": loan,
        "Time Cut": round(time_cut_amt, 2),
        "Net Salary": round(net_salary, 2)
    }])
    
    try:
        # ગૂગલ શીટ અપડેટ કરવી
        existing_data = conn.read(ttl=0)
        updated_df = pd.concat([existing_data, new_record], ignore_index=True)
        conn.update(data=updated_df)
        
        st.success(f"✅ રેકોર્ડ સેવ થયો! Net Salary: ₹{net_salary:,.2f}")
        st.balloons()
    except:
        st.error("Google Sheets સાથે કનેક્ટ કરવામાં ભૂલ આવી. કૃપા કરીને Secrets ચેક કરો.")

# હિસ્ટ્રી સેક્શન
try:
    df_history = conn.read(ttl=0)
    if not df_history.empty:
        st.divider()
        st.subheader("📂 Salary Records History")
        st.dataframe(df_history, use_container_width=True)
except:
    pass
