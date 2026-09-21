import streamlit as st
import pandas as pd
from datetime import date
import plotly.express as px

# પેજ સેટઅપ / Page Setup
st.set_page_config(page_title="માસિક બજેટ અને ખર્ચ ટ્રેકર | Monthly Budget & Expense Tracker", layout="wide")

# મુખ્ય શીર્ષક / Main Title
st.title("📊 માસિક બજેટ પ્લાનર અને ખર્ચ ટ્રેકર (Monthly Budget Planner & Expense Tracker)")

# ૧. માસિક આવક / 1. Monthly Income
st.subheader("૧. તમારી માસિક આવક દાખલ કરો / 1. Enter Your Monthly Income")
# પગાર દાખલ કરવા માટે ઇનપુટ / Input for Salary
income = st.number_input("માસિક પગાર / Monthly Salary (₹)", min_value=0, value=38800, step=1000)

st.divider()

# ૨. બજેટ સ્લાઈડર્સ / 2. Budget Sliders
st.subheader("૨. અંદાજિત માસિક બજેટ ફાળવણી / 2. Estimated Monthly Budget Allocation")

col1, col2 = st.columns(2)

with col1:
    # ઘરખર્ચની કેટેગરી / Housing & Essentials Category
    st.markdown("### 🏠 ઘરખર્ચ અને જીવનજરૂરિયાત / Housing & Essentials")
    groceries = st.slider("કરિયાણું અને દૂધ / Groceries & Milk", 0, 15000, 8000, step=500)
    utilities = st.slider("લાઈટ બિલ અને મેન્ટેનન્સ / Utilities & Maintenance", 0, 10000, 3000, step=100)
    medical = st.slider("મેડિકલ અને દવાઓ / Medical & Medicines", 0, 10000, 3000, step=100)

with col2:
    # ટ્રાન્સપોર્ટ અને જીવનશૈલી કેટેગરી / Transport & Lifestyle Category
    st.markdown("### 🛵 ટ્રાન્સપોર્ટ અને જીવનશૈલી / Transport & Lifestyle")
    petrol = st.slider("પેટ્રોલ - મુસાફરી / Petrol - Travel", 0, 10000, 3000, step=100)
    dining = st.slider("બહાર જમવાનું - શોપિંગ / Dining - Shopping", 0, 10000, 3500, step=100)
    misc = st.slider("અન્ય પરચૂરણ ખર્ચ / Other Misc Expenses", 0, 10000, 2500, step=100)

# કુલ ખર્ચ અને બચતની ગણતરી / Total Expense & Savings Calculation
total_budget = groceries + utilities + medical + petrol + dining + misc
savings = income - total_budget

# બજેટ સમરી / Budget Summary
st.markdown("### બજેટ સમરી / Budget Summary")
c1, c2, c3 = st.columns(3)
c1.metric("કુલ આવક / Total Income", f"₹{income}")
c2.metric("કુલ બજેટ ખર્ચ / Total Budget Expense", f"₹{total_budget}")
c3.metric("અંદાજિત બચત / Estimated Savings (Surplus)", f"₹{savings}")

st.divider()

# ૩. રોજિંદા ખર્ચની નોંધ / 3. Daily Expense Tracking
st.subheader("૩. રોજિંદા ખર્ચની નોંધ ઉમેરો / 3. Add Daily Expenses")

# ડેટા સ્ટોર કરવા માટે સેશન સ્ટેટ નો ઉપયોગ / Using Session State to store data
if 'expenses_df' not in st.session_state:
    st.session_state['expenses_df'] = pd.DataFrame(columns=['તારીખ/Date', 'કેટેગરી/Category', 'વિગત/Description', 'રકમ/Amount (₹)'])

# ખર્ચ ઉમેરવા માટેનું ફોર્મ / Form to add expenses
with st.form("expense_form"):
    d1, d2, d3, d4 = st.columns(4)
    exp_date = d1.date_input("તારીખ / Date", date.today())
    
    # ડ્રોપડાઉન મેનુ માટે કેટેગરી / Categories for Dropdown menu
    exp_cat = d2.selectbox("કેટેગરી / Category", [
        "કરિયાણું અને દૂધ / Groceries", 
        "લાઈટ બિલ અને મેન્ટેનન્સ / Utilities", 
        "મેડિકલ અને દવાઓ / Medical", 
        "પેટ્રોલ - મુસાફરી / Transport", 
        "બહાર જમવાનું - શોપિંગ / Dining & Shopping", 
        "અન્ય પરચૂરણ ખર્ચ / Misc"
    ])
    exp_desc = d3.text_input("ખર્ચની વિગત / Description (Optional)")
    exp_amt = d4.number_input("રકમ / Amount (₹)", min_value=0, value=0, step=10)
    
    # સેવ બટન / Save Button
    submitted = st.form_submit_button("ખર્ચ સેવ કરો / Save Expense")

    # જ્યારે ફોર્મ સબમિટ થાય ત્યારે / When form is submitted
    if submitted and exp_amt > 0:
        new_row = pd.DataFrame([{
            'તારીખ/Date': exp_date, 
            'કેટેગરી/Category': exp_cat, 
            'વિગત/Description': exp_desc, 
            'રકમ/Amount (₹)': exp_amt
        }])
        st.session_state['expenses_df'] = pd.concat([st.session_state['expenses_df'], new_row], ignore_index=True)
        st.success("✅ તમારો ખર્ચ સફળતાપૂર્વક ઉમેરાઈ ગયો છે! / Expense added successfully!")

# ડેટા ટેબલ અને ચાર્ટ દર્શાવો / Display Data Table and Chart
if not st.session_state['expenses_df'].empty:
    st.markdown("### આ મહિનાનો નોંધાયેલો ખર્ચ / Logged Expenses for this Month")
    
    # ટેબલ બતાવો / Show Table
    st.dataframe(st.session_state['expenses_df'], use_container_width=True)
    
    # ખર્ચનો પાઇ ચાર્ટ / Expense Pie Chart
    st.markdown("### કેટેગરી મુજબ ખર્ચનો ચાર્ટ / Expense Chart by Category")
    expense_summary = st.session_state['expenses_df'].groupby('કેટેગરી/Category')['રકમ/Amount (₹)'].sum().reset_index()
    fig = px.pie(expense_summary, values='રકમ/Amount (₹)', names='કેટેગરી/Category', hole=0.4)
    st.plotly_chart(fig, use_container_width=True)
