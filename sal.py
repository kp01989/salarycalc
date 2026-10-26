# === PDF GENERATOR (LANDSCAPE MODE) ===
def generate_pdf_slip(slip_data, emp_name, month_str, year_val):
    sd = slip_data
    
    # Dummy data for new fields
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
    gross_salary = sd['actual_salary'] + da + hra + ca + ea + ma + target_salary 
    
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

    # Orientation changed to 'L' (Landscape)
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    # Margins & Base Setup (A4 Landscape Width = 297mm. Usable = 277mm)
    pdf.set_margins(10, 10, 10)
    
    # 1. HEADER LOGO & COMPANY NAME
    logo_url = "https://www.laxmidiamond.com/images/logo.png" 
    logo_path = "temp_logo.png"
    
    try:
        if not os.path.exists(logo_path):
            urllib.request.urlretrieve(logo_url, logo_path)
        pdf.image(logo_path, x=10, y=10, w=35)
    except:
        pdf.set_xy(10, 10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(35, 15, "LAXMI", border=1, align='C')
        
    pdf.set_xy(45, 10)
    pdf.set_font("Arial", 'B', 18) 
    pdf.cell(192, 7, "LAXMI DIAMOND PVT. LTD.(SURAT)", ln=1, align='C')
    
    pdf.set_font("Arial", '', 10)
    pdf.set_x(45)
    pdf.cell(192, 5, "Nr. Gajera Circle, Katargam Fulpada Road, Katargam, Surat.", ln=1, align='C')
    pdf.set_font("Arial", 'B', 10)
    pdf.set_x(45)
    pdf.cell(192, 5, "(Minimum Wages Act. Rule 25-2)", ln=1, align='C')
    
    # SIGHTHOLDER FIX for Landscape (Shifted Right)
    pdf.set_xy(237, 10)
    pdf.set_font("Arial", '', 10)
    pdf.cell(40, 5, "(S)", border=0, align='C', ln=1)
    pdf.set_x(237)
    pdf.set_font("Arial", '', 9)
    pdf.cell(40, 4, "SIGHTHOLDER", border=0, align='C', ln=1)
    pdf.set_x(237)
    pdf.set_font("Arial", '', 4.5) 
    pdf.cell(40, 3, "OF THE DE BEERS GROUP OF COMPANIES", border=0, align='C', ln=1)
    
    pdf.ln(2)
    
    # Draw outer box for Header (width 277)
    pdf.rect(10, 9, 277, 18)
    
    # 2. EMPLOYEE DETAILS SECTION
    y_start = 27
    pdf.set_xy(10, y_start)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(277, 7, f"Employee's Name : {emp_name.upper()} ({emp_code})", border=1, ln=1)
    
    pdf.cell(138.5, 7, f"Department : {department}", border='L', align='L')
    pdf.cell(138.5, 7, f"Designation : {designation}", border='R', align='L', ln=1)
    
    x, y = pdf.get_x(), pdf.get_y()
    pdf.line(10, y, 287, y)
    
    pdf.cell(92, 7, f"Date of Joining : {doj}", border='L')
    pdf.cell(92, 7, f"Date of Birth : {dob}", border=0)
    pdf.cell(93, 7, f"PAN : {pan_no}", border='R', ln=1)
    
    x, y = pdf.get_x(), pdf.get_y()
    pdf.line(10, y, 287, y)
    
    # 3. MAIN TABLE 
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(50, 7, "Section : Pricing", border='LRT')
    pdf.cell(85, 7, "Earning", border='LRT')
    pdf.cell(85, 7, "Deduction", border='LRT')
    pdf.cell(57, 7, "", border='LRT', ln=1)
    
    row_h = 7.5 # Taller rows for landscape
    
    def draw_row(c1_lbl, c1_val, c2_lbl, c2_val, c3_lbl, c3_val, c4_lbl, c4_val, is_bold=False):
        if is_bold:
            pdf.set_font("Arial", 'B', 10)
        else:
            pdf.set_font("Arial", '', 9)
            
        # Col 1 (Total 50)
        pdf.cell(32, row_h, c1_lbl, border=1)
        pdf.cell(18, row_h, c1_val, border=1, align='R')
        # Col 2 (Total 85)
        pdf.cell(55, row_h, c2_lbl, border=1)
        pdf.cell(30, row_h, c2_val, border=1, align='R')
        # Col 3 (Total 85)
        pdf.cell(55, row_h, c3_lbl, border=1)
        pdf.cell(30, row_h, c3_val, border=1, align='R')
        
        # Col 4 (Total 57)
        if c4_lbl != "MERGE_DISCLAIMER":
            pdf.cell(27, row_h, c4_lbl, border=1)
            if c4_lbl == "Sr No":
                pdf.set_font("Arial", '', 8.5) 
                pdf.cell(30, row_h, c4_val, border=1, align='C')
                if not is_bold: pdf.set_font("Arial", '', 9) 
            else:
                pdf.cell(30, row_h, c4_val, border=1, align='R')
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
             "UAN", uan_no)
    # R5
    draw_row("Days Absent", days_absent, 
             "E.A.", f"{ea:,.2f}", 
             "L.W.Fund", f"{lw_fund:,.2f}", 
             "E.S.I. No.", esi_no)
    # R6
    draw_row("PL", str(sd['pl_used']), 
             "M.A.", f"{ma:,.2f}", 
             "Other/Adv./Loan", f"{sd['advance']:,.2f}", 
             "Bank Name", "SBI") 
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
    pdf.set_font("Arial", '', 9)
    pdf.cell(50, row_h, "", border=1) 
    pdf.cell(85, row_h, "", border=1) 
    pdf.cell(85, row_h, "", border=1) 
    
    # C4 Split
    pdf.cell(27, row_h, "Adv agst Bonus", border=1)
    pdf.cell(30, row_h, f"{adv_bonus:,.2f}", border=1, align='R')
    pdf.ln()

    # Disclaimer Box at Bottom Right (Shifted to X=230 for Landscape)
    curr_y = pdf.get_y()
    pdf.set_xy(230, curr_y)
    pdf.set_font("Arial", 'I', 7.5)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(57, 4.5, "This is computer generated slip hence signature is not required.", border=1, align='C')
    pdf.set_text_color(0, 0, 0)
    
    # 4. FOOTER DETAILS
    pdf.set_y(curr_y + 12)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(277, 5, "Company's Details : P.F Code : GJ/SRT/30549      E.S.I.C Code : 39000207770000910    PAN : AABCL1815G    TAN : SRTL00591D", border=0, align='L')
    pdf.ln(4.5)
    pdf.set_font("Arial", '', 7)
    pdf.cell(277, 4, "DA - Dearness Allowance, HRA - House Rent Allowance, CA - Conveyance Allowance, EA - Education Allowance, WA - Washing Allowance, TDS - Tax Deducted At Source", border=0, align='L')
    
    return pdf.output(dest='S').encode('latin1')
