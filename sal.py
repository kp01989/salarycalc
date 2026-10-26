import streamlit as st
import pandas as pd
import requests
import os
import io
from datetime import datetime
import time as tm
import streamlit.components.v1 as components 
from fpdf import FPDF
import urllib.request

# ==========================================
# 1. Page Setup
# ==========================================
st.set_page_config(page_title="Salary Management System", layout="wide")
month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
month_dict = {m: i+1 for i, m in enumerate(month_order)}

FIREBASE_URL = "https://attendence-ec921-default-rtdb.firebaseio.com"

# ==========================================
# CUSTOM JAVASCRIPT: "ENTER" NE "TAB" TARIKE KAM KARAVVA
# ==========================================
components.html(
    """
    <script>
    const doc = window.parent.document;
    if (!doc.getElementById('custom-enter-tab')) {
        let script = doc.createElement('script');
        script.id = 'custom-enter-tab';
        script.innerHTML = `
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    let active = document.activeElement;
                    if (active && active.tagName === 'INPUT') {
                        e.preventDefault(); 
                        
                        let focusable = Array.from(document.querySelectorAll('input:not([disabled]), button:not([disabled])'));
                        let index = focusable.indexOf(active);
                        
                        if (index > -1 && index < focusable.length - 1) {
                            focusable[index + 1].focus();
                        }
                    }
                }
            });
        `;
        doc.head.appendChild(script);
    }
    </script>
    """,
    height=0, width=0
)

# ==========================================
# 2. Custom CSS
# ==========================================
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .stButton > button { 
        transition: all 0.2s ease-in-out !important; 
        cursor: pointer !important; 
    }
    .stButton > button:hover { 
        transform: scale(1.05) !important; 
        box-shadow: 0px 4px 15px rgba(255, 75, 75, 0.4) !important; 
    }
    [data-testid="stDataEditor"] [role="gridcell"] input[type="checkbox"] { 
        opacity: 1 !important; 
        visibility: visible !important; 
    }
    
    div[data-testid="column"]:has(#left-column-marker) {
        border-right: 2px solid rgba(128, 128, 128, 0.4);
        padding-right: 25px;
    }
    div[data-testid="column"]:has(#left-column-marker) + div[data-testid="column"] {
        padding-left: 25px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. State Management
# ==========================================
if 'calc_result' not in st.session_state:
    st.session_state['calc_result'] = None
if 'form_key' not in st.session_state:
    st.session_state['form_key'] = 0
if 'flash_msg' not in st.session_state:
    st.session_state['flash_msg'] = None

st.markdown("<h1 style='text-align: center;'>💎 Salary & Leave Management</h1>", unsafe_allow_html=True)
st.divider()

if st.session_state['flash_msg']:
    st.success(st.session_state['flash_msg'])
    st.session_state['flash_msg'] = None

# ==========================================
# 4. Helper Functions
# ==========================================
def get_user_file(name):
    if not name: return None
    return f"{name.strip().replace(' ', '_')}_salary.csv"

def format_mins_to_hrs(val):
    try:
        if pd.isna(val): return "0:00"
        v = int(float(val))
        return f"{v//60}:{v%60:02d}"
    except:
        return str(val)

def clean_legacy_columns(df):
    if 'Std Hrs' in df.columns:
        if 'Working Hrs' in df.columns:
            df['Working Hrs'] = df['Working Hrs'].fillna(df['Std Hrs'])
            df['Working Hrs'] = df.apply(lambda r: r['Std Hrs'] if pd.isna(r.get('Working Hrs')) or r.get('Working Hrs') == 0 else r['Working Hrs'], axis=1)
            df = df.drop(columns=['Std Hrs'])
        else:
            df = df.rename(columns={'Std Hrs': 'Working Hrs'})
            
    rename_map = {'Late Mins': 'Late Hrs', 'Early Mins': 'Out Hrs', 'OT Mins': 'OT Hrs'}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    for col in ['Late Hrs', 'Out Hrs', 'OT Hrs']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: format_mins_to_hrs(x) if str(x).replace('.0','').isdigit() else str(x))
            
    if 'Final Present Hrs' in df.columns:
        df['Final Present Hrs'] = df['Final Present Hrs'].astype(str).str.replace('h ', ':').str.replace('m', '')
        
    if 'Opening PL' not in df.columns:
        df['Opening PL'] = 0.0
    if 'In Hand Salary' not in df.columns:
        df['In Hand Salary'] = 0.0
    if 'Total Pay Hrs' not in df.columns:
        df['Total Pay Hrs'] = ""
        
    df = df.loc[:, ~df.columns.duplicated()]
    return df

def parse_firebase_time(time_str):
    if pd.isna(time_str) or str(time_str).strip() == "":
        return 0, 0
    try:
        parts = str(time_str).split(':')
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h, m
    except:
        return 0, 0

def fetch_attendance_data(emp_name, month_name, year):
    sheet_name = f"{month_name}'{year}"
    url = f"{FIREBASE_URL}/{sheet_name}.json"
    
    total_reg_mins, total_ot_mins, total_late_mins, total_out_mins_att = 0, 0, 0, 0
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data:
                if isinstance(data, dict):
                    df = pd.DataFrame(list(data.values()))
                else:
                    df = pd.DataFrame([row for row in data if row is not None])
                
                if "Employee Name" in df.columns:
                    df = df[df["Employee Name"].str.lower() == emp_name.strip().lower()]
                    for _, row in df.iterrows():
                        h, m = parse_firebase_time(row.get("Total Hours", "00:00"))
                        total_reg_mins += (h * 60) + m
                        
                        h, m = parse_firebase_time(row.get("OT Hours", "00:00"))
                        total_ot_mins += (h * 60) + m
                        
                        h, m = parse_firebase_time(row.get("Late Hours", "00:00"))
                        total_late_mins += (h * 60) + m
                        
                        h, m = parse_firebase_time(row.get("Out Hours", "00:00"))
                        total_out_mins_att += (h * 60) + m
    except Exception:
        pass
        
    return {
        "reg_h": total_reg_mins // 60, "reg_m": total_reg_mins % 60,
        "ot_h": total_ot_mins // 60, "ot_m": total_ot_mins % 60,
        "late_h": total_late_mins // 60, "late_m": total_late_mins % 60,
        "out_h": total_out_mins_att // 60, "out_m": total_out_mins_att % 60
    }

def recalculate_future_pl(df, start_index):
    for i in range(start_index + 1, len(df)):
        prev_balance = int(float(df.at[df.index[i-1], 'PL Balance']))
        used_pl_current = int(float(df.at[df.index[i], 'PL Used']))
        
        new_opening = prev_balance + 1
        new_balance = new_opening - used_pl_current
        
        df.at[df.index[i], 'Opening PL'] = new_opening
        df.at[df.index[i], 'PL Balance'] = new_balance
    return df

# ==========================================
# EXCEL & PDF GENERATORS
# ==========================================
def generate_excel_slip(slip_data, emp_name, month_str, year_val):
    sd = slip_data
    slip_df = pd.DataFrame({
        "Label": [
            "CTC Salary", "Gratuity", "Bonus", "Actual Salary", 
            "Working Hrs", "Pay Hrs", "PL Used", 
            "OT Hrs", "Late Hrs", "Out Hrs", "Total Pay Hrs", 
            "PT", "PF", "ESI", "TDS", "Loan", "Food", 
            "PL Balance", "Pay Salary", "OT Salary", "In Hand Salary", "Bank Salary", "Diff"
        ],
        "Value": [
            sd['ctc'], sd['gratuity'], sd['bonus'], sd['actual_salary'], 
            sd['work_hrs_str'], sd['present_hrs'], sd['pl_used'], 
            sd['ot_hrs'], sd['late_hrs'], sd['out_hrs'], sd['pay_hrs'], 
            sd['pt'], "-", sd['esic'] if sd['esic'] else "-", sd['tds'] if sd['tds'] else "-", 
            sd['advance'], sd['food'], sd['pl_balance'], 
            sd['pay_salary_val'], sd['ot_sal'], sd['in_hand_salary'], sd['bank_salary_val'], sd['difference']
        ]
    })
    
    header_row = pd.DataFrame({"Label": [f"{month_str}'{year_val}"], "Value": [f"{emp_name}"]})
    slip_df = pd.concat([header_row, slip_df], ignore_index=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        slip_df.to_excel(writer, index=False, header=False, sheet_name='Salary_Slip')
        workbook = writer.book
        worksheet = writer.sheets['Salary_Slip']
        
        base_header_left = {'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'align': 'left', 'valign': 'vcenter', 'indent': 1}
        base_header_center = {'bold': True, 'bg_color': '#1F4E78', 'font_color': 'white', 'align': 'center', 'valign': 'vcenter'}
        base_label_left = {'bold': True, 'bg_color': '#D9E1F2', 'align': 'left', 'valign': 'vcenter', 'indent': 1}
        base_val_text = {'align': 'center', 'valign': 'vcenter'}
        
        base_val_curr = {'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0'}
        base_val_curr_tds = {'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0.00'} 
        
        base_val_yellow = {'bg_color': '#FFFF00', 'align': 'center', 'valign': 'vcenter'}
        base_val_green = {'bg_color': '#C6E0B4', 'align': 'center', 'valign': 'vcenter'}
        
        base_pay_label_left = {'bold': True, 'bg_color': '#C6E0B4', 'align': 'left', 'valign': 'vcenter', 'indent': 1}
        base_pay_val_center = {'bold': True, 'bg_color': '#C6E0B4', 'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0'}
        
        base_ot_label_left = {'bold': True, 'bg_color': '#F4B084', 'align': 'left', 'valign': 'vcenter', 'indent': 1}
        base_ot_val_center = {'bold': True, 'bg_color': '#F4B084', 'align': 'center', 'valign': 'vcenter', 'num_format': '₹ #,##0'}
        
        base_diff_pos_red = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#FF0000', 'num_format': '₹ #,##0'}
        base_diff_neg_green = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#228B22', 'num_format': '₹ #,##0'}
        base_diff_zero = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_color': '#000000', 'num_format': '₹ #,##0'}

        worksheet.set_column('A:A', 22)
        worksheet.set_column('B:B', 25)
        
        for i in range(len(slip_df)):
            worksheet.set_row(i, 18)
        
        currency_labels = ["CTC Salary", "Bonus", "Gratuity", "Actual Salary", "PT", "PF", "ESI", "Loan", "Food", "Bank Salary", "Diff"]
        total_rows = len(slip_df)
        
        for row_num, (lbl, val) in enumerate(zip(slip_df['Label'], slip_df['Value'])):
            if row_num == 0: dict_col0 = base_header_left.copy()
            elif lbl in ["Pay Salary", "In Hand Salary"]: dict_col0 = base_pay_label_left.copy()
            elif lbl == "OT Salary": dict_col0 = base_ot_label_left.copy()
            else: dict_col0 = base_label_left.copy()

            dict_col0['border'] = 1
            if row_num == 0: dict_col0['top'] = 2
            if row_num == total_rows - 1: dict_col0['bottom'] = 2
            dict_col0['left'] = 2
            worksheet.write(row_num, 0, lbl, workbook.add_format(dict_col0))

            if row_num == 0: dict_col1 = base_header_center.copy()
            elif lbl == "Working Hrs": dict_col1 = base_val_yellow.copy()
            elif lbl in ["Pay Hrs", "PL Used", "Total Pay Hrs"]: dict_col1 = base_val_green.copy()
            elif lbl in ["Pay Salary", "In Hand Salary"]: dict_col1 = base_pay_val_center.copy()
            elif lbl == "OT Salary": dict_col1 = base_ot_val_center.copy()
            elif lbl == "Diff":
                diff_val = float(val) if val != "-" else 0
                if diff_val > 0: dict_col1 = base_diff_pos_red.copy()
                elif diff_val < 0: dict_col1 = base_diff_neg_green.copy()
                else: dict_col1 = base_diff_zero.copy()
            elif lbl == "TDS" and val != "-": dict_col1 = base_val_curr_tds.copy() 
            elif lbl in currency_labels and val != "-": dict_col1 = base_val_curr.copy()
            else: dict_col1 = base_val_text.copy()

            dict_col1['border'] = 1
            if row_num == 0: dict_col1['top'] = 2
            if row_num == total_rows - 1: dict_col1['bottom'] = 2
            dict_col1['right'] = 2
            worksheet.write(row_num, 1, val, workbook.add_format(dict_col1))
            
    return output.getvalue()


# === NEW PRO PDF GENERATOR ===
def generate_pdf_slip(slip_data, emp_name, month_str, year_val):
    sd = slip_data
    
    # Dummy data for new fields (Future form fields can replace these)
    emp_code = "KPP0023"
    department = "Bhaghubhai Office - Polish Assorting"
    designation = "Data Analyst"
    doj = "22/12/2025"
    dob = "29/07/1989"
    pan_no = "CFOPP1244J"
    
    days_absent = "0"
    paid_holiday = "2"
    week_off = "4"
    month_days = "30"
    
    da = 0.00
    hra = 6600.00
    ca = 2000.00
    ea = 0.00
    ma = 0.00
    target_salary = 4029.00
    gross_salary = sd['actual_salary'] + da + hra + ca + ea + ma + target_salary # Dummy logic
    
    pf_fund = 0.00
    esi_cont = 0.00
    lw_fund = 0.00
    total_deduct = sd['pt'] + sd['tds'] + sd['advance'] + sd['food'] + pf_fund + esi_cont + lw_fund
    
    sr_no = f"{year_val}{month_str}-12345"
    pf_no = "-"
    uan_no = "-"
    esi_no = "-"
    bank_name = "State Bank of India"
    bank_ac = "32826390970"
    adv_bonus = 0.00

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    
    # Margins & Base Setup
    pdf.set_margins(10, 10, 10)
    
    # 1. HEADER LOGO & COMPANY NAME
    logo_url = "https://www.laxmidiamond.com/images/logo.png" 
    logo_path = "temp_logo.png"
    
    try:
        if not os.path.exists(logo_path):
            urllib.request.urlretrieve(logo_url, logo_path)
        pdf.image(logo_path, x=10, y=10, w=30)
    except:
        # Placeholder jo logo na male
        pdf.set_xy(10, 10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(30, 15, "LAXMI", border=1, align='C')
        
    pdf.set_xy(45, 10)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(120, 7, "LAXMI DIAMOND PVT. LTD.(SURAT)", ln=1, align='C')
    
    pdf.set_font("Arial", '', 9)
    pdf.set_x(45)
    pdf.cell(120, 5, "Nr. Gajera Circle, Katargam Fulpada Road, Katargam, Surat.", ln=1, align='C')
    pdf.set_font("Arial", 'B', 9)
    pdf.set_x(45)
    pdf.cell(120, 5, "(Minimum Wages Act. Rule 25-2)", ln=1, align='C')
    
    pdf.set_xy(170, 10)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(30, 15, "SIGHTHOLDER", border=0, align='C') # Dummy right logo
    pdf.ln(5)
    
    # Draw outer box for Header
    pdf.rect(10, 9, 190, 18)
    
    # 2. EMPLOYEE DETAILS SECTION
    y_start = 27
    pdf.set_xy(10, y_start)
    
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(190, 6, f"Employee's Name : {emp_name.upper()} ({emp_code})", border=1, ln=1)
    
    pdf.cell(95, 6, f"Department : {department}", border='L', align='L')
    pdf.cell(95, 6, f"Designation : {designation}", border='R', align='L', ln=1)
    
    # Draw bottom border for department line
    x, y = pdf.get_x(), pdf.get_y()
    pdf.line(10, y, 200, y)
    
    pdf.cell(60, 6, f"Date of Joining : {doj}", border='L')
    pdf.cell(60, 6, f"Date of Birth : {dob}", border=0)
    pdf.cell(70, 6, f"PAN : {pan_no}", border='R', ln=1)
    
    # Draw bottom border for joining date line
    x, y = pdf.get_x(), pdf.get_y()
    pdf.line(10, y, 200, y)
    
    # 3. MAIN TABLE (4 Columns)
    # Widths: C1=40, C2=55, C3=55, C4=40
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(40, 6, "Section : Pricing", border='LRT')
    pdf.cell(55, 6, "Earning", border='LRT')
    pdf.cell(55, 6, "Deduction", border='LRT')
    pdf.cell(40, 6, "", border='LRT', ln=1)
    
    # Cell heights
    row_h = 7
    pdf.set_font("Arial", '', 8)
    
    def draw_row(c1_lbl, c1_val, c2_lbl, c2_val, c3_lbl, c3_val, c4_lbl, c4_val, is_bold=False):
        if is_bold:
            pdf.set_font("Arial", 'B', 9)
        else:
            pdf.set_font("Arial", '', 8)
            
        # Col 1
        pdf.cell(25, row_h, c1_lbl, border=1)
        pdf.cell(15, row_h, c1_val, border=1, align='R')
        # Col 2
        pdf.cell(35, row_h, c2_lbl, border=1)
        pdf.cell(20, row_h, c2_val, border=1, align='R')
        # Col 3
        pdf.cell(35, row_h, c3_lbl, border=1)
        pdf.cell(20, row_h, c3_val, border=1, align='R')
        # Col 4
        if c4_lbl != "MERGE_DISCLAIMER":
            pdf.cell(20, row_h, c4_lbl, border=1)
            pdf.cell(20, row_h, c4_val, border=1, align='R')
        pdf.ln()

    # R1
    draw_row("Working Days", str(int(sd['work_hrs_str'].split(':')[0])//8 if ':' in sd['work_hrs_str'] else 24), 
             "Basic Salary", f"{sd['ctc']:,.2f}", 
             "Provident Fund", f"{pf_fund:,.2f}", 
             "Sr No", sr_no)
    # R2
    draw_row("Days Present", str(int(sd['present_hrs'].split(':')[0])//8 if ':' in sd['present_hrs'] else 24), 
             "D.A.", f"{da:,.2f}", 
             "E.S.I Contribution", f"{esi_cont:,.2f}", 
             "Month", f"{month_str}-{year_val}")
    # R3
    draw_row("Paid Holiday", paid_holiday, 
             "HRA", f"{hra:,.2f}", 
             "Professional Tax", f"{sd['pt']:,.2f}", 
             "P.F. No.", pf_no)
    # R4
    draw_row("Week Off", week_off, 
             "C.A.", f"{ca:,.2f}", 
             "T.D.S", f"{sd['tds']:,.2f}", 
             "UAN", uAN_no if 'uAN_no' in locals() else "-")
    # R5
    draw_row("Days Absent", days_absent, 
             "E.A.", f"{ea:,.2f}", 
             "L.W.Fund", f"{lw_fund:,.2f}", 
             "E.S.I. No.", esi_no)
    # R6
    draw_row("PL", str(sd['pl_used']), 
             "M.A.", f"{ma:,.2f}", 
             "Other/Adv./Loan", f"{sd['advance']:,.2f}", 
             "Bank Name", "SBI") # Short bank name to fit
    # R7
    draw_row("Month Days", month_days, 
             "Target Salary", f"{target_salary:,.2f}", 
             "Food Charge", f"{sd['food']:,.2f}", 
             "Bank A/c. No.", bank_ac)
    
    # R8 (Bold Totals Row)
    draw_row("Actual Salary", f"{sd['actual_salary']:,.2f}", 
             "Gross Salary", f"{gross_salary:,.2f}", 
             "Total Deduction", f"{total_deduct:,.2f}", 
             "Net Salary", f"{sd['in_hand_salary']:,.2f}", is_bold=True)
             
    # R9 (Footer row for bonus and disclaimer)
    pdf.set_font("Arial", '', 8)
    pdf.cell(40, row_h, "", border=1) # Empty C1
    pdf.cell(55, row_h, "", border=1) # Empty C2
    pdf.cell(55, row_h, "", border=1) # Empty C3
    
    # C4 Split
    pdf.cell(20, row_h, "Adv agst Bonus", border=1)
    pdf.cell(20, row_h, f"{adv_bonus:,.2f}", border=1, align='R')
    pdf.ln()

    # Disclaimer Box at Bottom Right
    curr_y = pdf.get_y()
    pdf.set_xy(160, curr_y)
    pdf.set_font("Arial", 'I', 7)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(40, 4, "This is computer generated slip hence signature is not required.", border=1, align='C')
    pdf.set_text_color(0, 0, 0)
    
    # Outer Table Border correction if needed
    
    # 4. FOOTER DETAILS
    pdf.set_y(curr_y + 10)
    pdf.set_font("Arial", 'B', 7)
    pdf.cell(190, 5, "Company's Details : P.F Code : GJ/SRT/30549      E.S.I.C Code : 39000207770000910    PAN : AABCL1815G    TAN : SRTL00591D", border=0, align='L')
    pdf.ln(4)
    pdf.set_font("Arial", '', 6)
    pdf.cell(190, 4, "DA - Dearness Allowance, HRA - House Rent Allowance, CA - Conveyance Allowance, EA - Education Allowance, WA - Washing Allowance, TDS - Tax Deducted At Source", border=0, align='L')
    
    return pdf.output(dest='S').encode('latin1')

# ==========================================
# 5. Sidebar Profile & Logic Setup
# ==========================================
with st.sidebar:
    st.header("👤 Profile")
    emp_sidebar_name = st.text_input("Employee Name", placeholder="Enter Name...", label_visibility="collapsed").title()
    
    user_file = get_user_file(emp_sidebar_name)
    
    if emp_sidebar_name and user_file and os.path.exists(user_file):
        st.write("")
        if st.button("🗑️ Delete All Data", type="secondary", use_container_width=True, help="Permanently delete all data for this employee"):
            try:
                os.remove(user_file)
                st.session_state['calc_result'] = None 
                st.session_state['flash_msg'] = f"✅ All data for {emp_sidebar_name} has been deleted!"
                st.rerun()
            except Exception as e:
                st.error("Error deleting file.")
                
    st.divider()

    last_data = {"CTC": 0.0, "Working_Hrs": 0.0, "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, "Advance": 0.0, "Difference": 0.0, "TDS": 0.0, "ESIC": 0.0}
    
    is_new_employee = True
    last_pl_balance = 0
    last_saved_month = None
    df_hist_sorted = pd.DataFrame() 

    if user_file and os.path.exists(user_file):
        try:
            df_hist = pd.read_csv(user_file)
            df_hist = clean_legacy_columns(df_hist)
                
            if not df_hist.empty:
                is_new_employee = False
                
                df_hist['Month_Num'] = df_hist['Month'].astype(str).str.strip().map(month_dict)
                df_hist_sorted = df_hist.sort_values(by=['Year', 'Month_Num']).reset_index(drop=True)
                last_row_chronological = df_hist_sorted.iloc[-1]
                
                last_pl_balance = int(float(last_row_chronological.get("PL Balance", 0)))
                last_saved_month = str(last_row_chronological.get("Month", "")).strip()

                key_mapping = {
                    "CTC": "CTC", "Working Hrs": "Working_Hrs", 
                    "Gratuity": "Gratuity", "PT": "PT", "TDS": "TDS", "ESIC": "ESIC",
                    "Food": "Food", "Advance": "Advance", "Difference": "Difference"
                }
                for csv_k, data_k in key_mapping.items():
                    if csv_k in last_row_chronological: 
                        val = last_row_chronological[csv_k]
                        if pd.notna(val) and str(val).strip() != "":
                            try:
                                last_data[data_k] = float(val)
                            except:
                                pass
        except Exception:
            pass

# ==========================================
# 6. MONTH/YEAR
# ==========================================
kb = f"{st.session_state['form_key']}_{emp_sidebar_name.strip()}"

now = datetime.now()
current_month_name = now.strftime("%b") 
current_year = now.year

m_list = list(month_dict.keys())
default_month = current_month_name 
def_year = current_year

if not is_new_employee and not df_hist_sorted.empty:
    last_row = df_hist_sorted.iloc[-1]
    last_saved_month = str(last_row.get("Month", "")).strip()
    if last_saved_month in m_list:
        last_idx = m_list.index(last_saved_month)
        if last_idx < 11: 
            default_month = m_list[last_idx + 1]
            def_year = int(last_row.get("Year", current_year))
        else:
            default_month = 'Jan' 
            def_year = int(last_row.get("Year", current_year)) + 1

def_m_idx = m_list.index(default_month) if default_month in m_list else 0

with st.container(border=True):
    col_m, col_y, col_emp = st.columns([1, 1, 2])
    with col_m:
        selected_month = st.selectbox("📅 Month", m_list, index=def_m_idx, disabled=(not is_new_employee), key=f"month_{kb}")
    with col_y:
        selected_year = st.number_input("🗓️ Year", min_value=2024, max_value=2030, value=def_year, disabled=(not is_new_employee), key=f"year_{kb}")
    with col_emp:
        emp_name = st.text_input("Full Name", value=emp_sidebar_name, disabled=True)

# Fetching Data Logic
form_data = {"CTC": 0.0, "Working_Hrs": 0.0, "Food": 0.0, "Gratuity": 0.0, "PT": 200.0, "Bonus": 0.0, "Advance": 0.0, "Difference": 0.0, "TDS": 0.0, "ESIC": 0.0, "PL_Used": 0}
opening_pl = 0
is_editing_past = False

if not is_new_employee and not df_hist_sorted.empty:
    existing_row = df_hist_sorted[(df_hist_sorted['Month'].astype(str).str.strip() == selected_month) & (df_hist_sorted['Year'] == selected_year)]
    
    if not existing_row.empty:
        is_editing_past = True
        row = existing_row.iloc[0]
        form_data["CTC"] = float(row.get("CTC", 0.0))
        form_data["Working_Hrs"] = float(row.get("Working Hrs", 0.0))
        form_data["Food"] = float(row.get("Food", 0.0))
        form_data["Gratuity"] = float(row.get("Gratuity", 0.0))
        form_data["PT"] = float(row.get("PT", 200.0))
        form_data["Bonus"] = float(row.get("Bonus", 0.0))
        form_data["Advance"] = float(row.get("Advance", 0.0))
        form_data["Difference"] = float(row.get("Difference", 0.0))
        form_data["TDS"] = float(row.get("TDS", 0.0))
        form_data["ESIC"] = float(row.get("ESIC", 0.0))
        form_data["PL_Used"] = int(float(row.get("PL Used", 0)))
        opening_pl = int(float(row.get("Opening PL", 0)))
    else:
        last_row = df_hist_sorted.iloc[-1]
        form_data["CTC"] = float(last_row.get("CTC", 0.0))
        form_data["Working_Hrs"] = float(last_row.get("Working Hrs", 0.0))
        form_data["PT"] = float(last_row.get("PT", 200.0))
        form_data["TDS"] = float(last_row.get("TDS", 0.0))
        form_data["ESIC"] = float(last_row.get("ESIC", 0.0))
        opening_pl = int(float(last_row.get("PL Balance", 0))) + 1

att_data = fetch_attendance_data(emp_name, selected_month, selected_year) if emp_name else {"reg_h": 0, "reg_m": 0, "ot_h": 0, "ot_m": 0, "late_h": 0, "late_m": 0, "out_h": 0, "out_m": 0}

# ==========================================
# 7. MAIN FORM 
# ==========================================
with st.form(key=f"salary_form_{kb}"):
    col1, col_line, col2 = st.columns([1, 0.05, 1])
    
    with col1:
        st.markdown('<div id="left-column-marker"></div>', unsafe_allow_html=True)
        st.subheader("💰 Basic Details")
        c1_1, c1_2 = st.columns(2)
        with c1_1:
            ctc_salary = st.number_input("CTC Salary (₹)", value=float(form_data["CTC"]), format="%.0f")
            
            p_h_col, p_m_col = st.
