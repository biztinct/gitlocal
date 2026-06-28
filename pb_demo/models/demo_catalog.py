# -*- coding: utf-8 -*-
"""Demo catalog — FORMULA-ENGINE native, 12 industry configs, parameter-driven.

The demo payroll is computed by the existing Formula Engine (hr.formula.config +
hr.formula.rule), NOT salary structures. This catalog defines **12 configs** —
6 divisions × {End-Month, Mid-Month} — each a genuinely different industry payroll
(shared spine + industry-unique components).

DESIGN PRINCIPLES (mirrors the real VPTQ End Cycle config):
* **No hard-coded numbers in formulas.** Every rate / cap / multiplier / standard
  value is a **parameter constant column** (DAYSTD, EESI, CAPLO, MULTWD, …) that
  formulas reference — e.g. `SIEMP = -ROUND(MIN(BASIC,CAPLO)*EESI)`, not `*0.08`.
  (VPTQ does the same with CE/CF/CG/CH.) Fixed allowance amounts stay as constant
  columns (a constant column IS a parameter, not an inline literal).
* **Components reference other components**, so GROSS/NET/TXBASE are sums/links.
* Each component carries EN+VI labels → a translatable hr.salary.rule is linked
  (`salary_rule_id`) for multilingual payslips + studio labels.

CONVERTER CONTRACT (do not "tidy" the codes): rule codes must be (a) free of
underscores and (b) not a substring of any other code in the same config, or the
Excel→Python converter mangles them. Country/currency/division segregation: each
config carries country_code (→ currency) + cycle_type + pb_division.
"""

GROUP_COMPANY_NAME = 'Payobook Vietnam JSC'
COUNTRY_CODE = 'VN'           # -> currency VND auto-derived by the engine

# Vietnam statutory constants (2024 practice) — used as PARAMETER VALUES, never inline.
SI_CAP = 46800000     # 20x base salary cap (SI/HI)
UI_CAP = 99200000     # 20x regional min cap (UI)

# --- Categories (code, EN, VI, parent, category_type, seq) -----------------------
CATEGORIES = [
    ('PARAM', 'Parameters', 'Tham số', False, 'basic', 0),
    ('GROSS', 'Gross Salary', 'Tổng thu nhập', False, 'basic', 1),
    ('BASIC', 'Basic Salary', 'Lương cơ bản', False, 'basic', 2),
    ('ALW', 'Allowances', 'Phụ cấp', False, 'allowance', 3),
    ('OT', 'Overtime', 'Làm thêm giờ', False, 'allowance', 4),
    ('BON', 'Bonuses', 'Thưởng', False, 'allowance', 5),
    ('DED', 'Deductions', 'Các khoản khấu trừ', False, 'deduction', 6),
    ('INS', 'Insurance', 'Bảo hiểm', 'DED', 'social_security', 7),
    ('TAX', 'Personal Income Tax', 'Thuế thu nhập cá nhân', 'DED', 'tax', 8),
    ('LOANDED', 'Loan & Advances', 'Vay & tạm ứng', 'DED', 'deduction', 9),
    ('NET', 'Net Salary', 'Thực lãnh', False, 'net', 10),
    ('COMP', 'Employer Cost', 'Chi phí doanh nghiệp', False, 'employer_cost', 11),
    ('INSCO', 'Employer Insurance', 'Bảo hiểm doanh nghiệp', 'COMP', 'employer_cost', 12),
]

# PIT progressive (monthly, quick-deduction) — statutory bracket structure, kept as
# one inline formula over TXBASE (the real VPTQ config inlines the brackets too).
_PIT = ("=-MAX(0,IF(TXBASE<=0,0,IF(TXBASE<=5000000,TXBASE*0.05,"
        "IF(TXBASE<=10000000,TXBASE*0.1-250000,IF(TXBASE<=18000000,TXBASE*0.15-750000,"
        "IF(TXBASE<=32000000,TXBASE*0.2-1650000,IF(TXBASE<=52000000,TXBASE*0.25-3250000,"
        "IF(TXBASE<=80000000,TXBASE*0.3-5850000,TXBASE*0.35-9850000))))))))")

# --- PARAMETER constants (shared by every End-Month config) ----------------------
# (code, EN, VI, value) -> built as constant columns, appears_on_payslip=False.
PARAMS_SHARED = [
    ('DAYSTD', 'Standard Working Days', 'Ngày công chuẩn', 26),
    ('HRSTD', 'Standard Hours / Day', 'Giờ công mỗi ngày', 8),
    ('EESI', 'Social Insurance Rate (EE)', 'Tỷ lệ BHXH (NLĐ)', 0.08),
    ('EEHI', 'Health Insurance Rate (EE)', 'Tỷ lệ BHYT (NLĐ)', 0.015),
    ('EEUI', 'Unemployment Rate (EE)', 'Tỷ lệ BHTN (NLĐ)', 0.01),
    ('ERSI', 'Social Insurance Rate (ER)', 'Tỷ lệ BHXH (DN)', 0.175),
    ('ERHI', 'Health Insurance Rate (ER)', 'Tỷ lệ BHYT (DN)', 0.03),
    ('ERUI', 'Unemployment Rate (ER)', 'Tỷ lệ BHTN (DN)', 0.01),
    ('ERUNION', 'Trade Union Rate', 'Tỷ lệ kinh phí công đoàn', 0.02),
    ('CAPLO', 'Insurance Cap (SI/HI)', 'Trần BHXH/BHYT', SI_CAP),
    ('CAPHI', 'Insurance Cap (UI)', 'Trần BHTN', UI_CAP),
    ('MULTWD', 'OT Multiplier — Weekday', 'Hệ số tăng ca ngày thường', 1.5),
    ('MULTWE', 'OT Multiplier — Weekend', 'Hệ số tăng ca cuối tuần', 2),
    ('MULTHO', 'OT Multiplier — Holiday', 'Hệ số tăng ca ngày lễ', 3),
    ('PCTRESP', 'Responsibility Allowance %', 'Tỷ lệ phụ cấp trách nhiệm', 0.1),
    ('DEDUCTSELF', 'Personal Tax Relief', 'Giảm trừ bản thân', 11000000),
    ('DEDUCTDEP', 'Dependent Tax Relief', 'Giảm trừ người phụ thuộc', 4400000),
]

# --- SHARED building blocks (7-tuples: code, EN, VI, category, kind, spec, appears)
#   kind: 'input' | 'const' | 'formula' | 'helper' (formula hidden on payslip)
SHARED_INPUTS = [
    ('BASIC', 'Basic Salary', 'Lương cơ bản', 'BASIC', 'input', None, True),
    ('DEPS', 'Dependents', 'Số người phụ thuộc', 'TAX', 'input', None, False),
    ('OTWD', 'OT Weekday (hrs)', 'Giờ làm thêm ngày thường', 'OT', 'input', None, False),
    ('OTWE', 'OT Weekend (hrs)', 'Giờ làm thêm cuối tuần', 'OT', 'input', None, False),
    ('OTHO', 'OT Holiday (hrs)', 'Giờ làm thêm ngày lễ', 'OT', 'input', None, False),
    ('INLOAN', 'Loan Installment (in)', 'Khoản trả nợ vay (nhập)', 'LOANDED', 'input', None, False),
    ('INTET', '13th-Month Bonus (in)', 'Thưởng tháng 13 (nhập)', 'BON', 'input', None, False),
]

# allowances + overtime amounts — formulas reference PARAMETERS, not literals
SHARED_EARN = [
    ('MEAL', 'Meal Allowance', 'Phụ cấp ăn trưa', 'ALW', 'const', 730000, True),
    ('TRANSPORT', 'Transport Allowance', 'Phụ cấp đi lại', 'ALW', 'const', 500000, True),
    ('PHONE', 'Phone Allowance', 'Phụ cấp điện thoại', 'ALW', 'const', 300000, True),
    ('ATTEND', 'Attendance Allowance', 'Phụ cấp chuyên cần', 'ALW', 'const', 400000, True),
    ('RESPALW', 'Responsibility Allowance', 'Phụ cấp trách nhiệm', 'ALW', 'formula', '=ROUND(BASIC*PCTRESP)', True),
    ('OTPAYWD', 'Overtime (Weekday)', 'Lương làm thêm ngày thường', 'OT', 'formula', '=ROUND(BASIC/DAYSTD/HRSTD*MULTWD*OTWD)', True),
    ('OTPAYWE', 'Overtime (Weekend)', 'Lương làm thêm cuối tuần', 'OT', 'formula', '=ROUND(BASIC/DAYSTD/HRSTD*MULTWE*OTWE)', True),
    ('OTPAYHO', 'Overtime (Holiday)', 'Lương làm thêm ngày lễ', 'OT', 'formula', '=ROUND(BASIC/DAYSTD/HRSTD*MULTHO*OTHO)', True),
    ('BONTET', '13th-Month / Tet Bonus', 'Thưởng tháng 13 / Tết', 'BON', 'formula', '=INTET', True),
]

# Pre-net statutory (after GROSS): employee insurance, tax, loan, then FULLPAY =
# the full-month net. FULLPAY is the shared base that the Mid/End split works on.
SHARED_PRENET = [
    ('SIEMP', 'Social Insurance (EE)', 'BHXH - NLĐ', 'INS', 'formula', '=-ROUND(MIN(BASIC,CAPLO)*EESI)', True),
    ('HIEMP', 'Health Insurance (EE)', 'BHYT - NLĐ', 'INS', 'formula', '=-ROUND(MIN(BASIC,CAPLO)*EEHI)', True),
    ('UIEMP', 'Unemployment Insurance (EE)', 'BHTN - NLĐ', 'INS', 'formula', '=-ROUND(MIN(BASIC,CAPHI)*EEUI)', True),
    ('TXBASE', 'Taxable Income', 'Thu nhập tính thuế', 'TAX', 'helper',
     '=GROSS+SIEMP+HIEMP+UIEMP-DEDUCTSELF-DEDUCTDEP*DEPS', False),
    ('PIT', 'Personal Income Tax', 'Thuế thu nhập cá nhân', 'TAX', 'formula', _PIT, True),
    ('LOANREP', 'Loan Repayment', 'Trả nợ vay', 'LOANDED', 'formula', '=-INLOAN', True),
    ('FULLPAY', 'Net Salary (full month)', 'Thực lãnh (cả tháng)', 'NET', 'helper',
     '=GROSS+SIEMP+HIEMP+UIEMP+PIT+LOANREP', False),
]

# Employer contributions (after the net split) — same in both cycles.
SHARED_EMPLOYER = [
    ('SICOMP', 'Social Insurance (ER)', 'BHXH - DN', 'INSCO', 'formula', '=ROUND(MIN(BASIC,CAPLO)*ERSI)', True),
    ('HICOMP', 'Health Insurance (ER)', 'BHYT - DN', 'INSCO', 'formula', '=ROUND(MIN(BASIC,CAPLO)*ERHI)', True),
    ('UICOMP', 'Unemployment Insurance (ER)', 'BHTN - DN', 'INSCO', 'formula', '=ROUND(MIN(BASIC,CAPHI)*ERUI)', True),
    ('UNIONF', 'Trade Union Fund', 'Kinh phí công đoàn', 'COMP', 'formula', '=ROUND(MIN(BASIC,CAPLO)*ERUNION)', True),
]

# Mid-cycle advance parameters (VPTQ rule): advance = FULLPAY × (HI rate if income
# >= threshold else LO rate). The transferred field is ADVPAY ("net received K1").
ADVANCE_PARAMS = [
    ('ADVTHRESH', 'Advance Threshold', 'Ngưỡng tạm ứng', 11000000),
    ('ADVRATEHI', 'Advance Rate (≥ threshold)', 'Tỷ lệ tạm ứng (≥ ngưỡng)', 0.8),
    ('ADVRATELO', 'Advance Rate (< threshold)', 'Tỷ lệ tạm ứng (< ngưỡng)', 1.0),
]

# --- DIVISION-SPECIFIC components (industry-unique) -------------------------------
# Each: optional 'params' (code,EN,VI,value), 'inputs' & 'earn' (7-tuples).
DIVISIONS_COMP = {
    'retail': {
        'inputs': [
            ('INCOMM', 'Commission (in)', 'Hoa hồng (nhập)', 'BON', 'input', None, False),
            ('INKPI', 'KPI Bonus (in)', 'Thưởng KPI (nhập)', 'BON', 'input', None, False),
        ],
        'earn': [
            ('RTSTORE', 'Store Incentive', 'Thưởng cửa hàng', 'ALW', 'const', 800000, True),
            ('RTWKND', 'Weekend Allowance', 'Phụ cấp cuối tuần', 'ALW', 'const', 600000, True),
            ('BONCOMM', 'Sales Commission', 'Hoa hồng bán hàng', 'BON', 'formula', '=INCOMM', True),
            ('BONKPI', 'KPI Bonus', 'Thưởng KPI', 'BON', 'formula', '=INKPI', True),
        ],
    },
    'manufacturing': {
        'inputs': [
            ('INPROD', 'Production Bonus (in)', 'Thưởng sản lượng (nhập)', 'BON', 'input', None, False),
        ],
        'earn': [
            ('MFSHIFT', 'Shift Allowance', 'Phụ cấp ca', 'ALW', 'const', 900000, True),
            ('MFMACH', 'Machine Risk Allowance', 'Phụ cấp rủi ro máy móc', 'ALW', 'const', 750000, True),
            ('BONPROD', 'Production Bonus', 'Thưởng sản lượng', 'BON', 'formula', '=INPROD', True),
        ],
    },
    'logistics': {
        'params': [
            ('TRIPRATE', 'Per-Trip Rate', 'Đơn giá mỗi chuyến', 50000),
        ],
        'inputs': [
            ('INTRIP', 'Trips Completed (in)', 'Số chuyến (nhập)', 'BON', 'input', None, False),
        ],
        'earn': [
            ('LGFUEL', 'Fuel Allowance', 'Phụ cấp nhiên liệu', 'ALW', 'const', 1200000, True),
            ('LGNIGHT', 'Night Driving Allowance', 'Phụ cấp lái xe đêm', 'ALW', 'const', 800000, True),
            ('LGTRIP', 'Trip Allowance', 'Phụ cấp theo chuyến', 'BON', 'formula', '=INTRIP*TRIPRATE', True),
        ],
    },
    'corporate': {
        'params': [
            ('PCTMGMT', 'Management Allowance %', 'Tỷ lệ phụ cấp quản lý', 0.15),
        ],
        'inputs': [
            ('INPERF', 'Performance Bonus (in)', 'Thưởng hiệu suất (nhập)', 'BON', 'input', None, False),
        ],
        'earn': [
            ('COMGMT', 'Management Allowance', 'Phụ cấp quản lý', 'ALW', 'formula', '=ROUND(BASIC*PCTMGMT)', True),
            ('COHOUSE', 'Housing Allowance', 'Phụ cấp nhà ở', 'ALW', 'const', 3000000, True),
            ('BONPERF', 'Performance Bonus', 'Thưởng hiệu suất', 'BON', 'formula', '=INPERF', True),
        ],
    },
    'it': {
        'params': [
            ('PCTSKILL', 'Technical Skill %', 'Tỷ lệ phụ cấp kỹ năng', 0.12),
        ],
        'inputs': [
            ('INPERF', 'Performance Bonus (in)', 'Thưởng hiệu suất (nhập)', 'BON', 'input', None, False),
        ],
        'earn': [
            ('ITSKILL', 'Technical Skill Allowance', 'Phụ cấp kỹ năng', 'ALW', 'formula', '=ROUND(BASIC*PCTSKILL)', True),
            ('ITCALL', 'On-Call Allowance', 'Phụ cấp trực hệ thống', 'ALW', 'const', 1500000, True),
            ('ITREMOTE', 'Remote Work Allowance', 'Phụ cấp làm việc từ xa', 'ALW', 'const', 1000000, True),
            ('BONPERF', 'Performance Bonus', 'Thưởng hiệu suất', 'BON', 'formula', '=INPERF', True),
        ],
    },
    'construction': {
        'earn': [
            ('CNSITE', 'Site Allowance', 'Phụ cấp công trường', 'ALW', 'const', 1100000, True),
            ('CNHIGH', 'Height Allowance', 'Phụ cấp làm việc trên cao', 'ALW', 'const', 900000, True),
            ('CNHEAT', 'Heat Allowance', 'Phụ cấp nắng nóng', 'ALW', 'const', 600000, True),
        ],
    },
}

_DIV_ORDER = ['retail', 'manufacturing', 'logistics', 'corporate', 'it', 'construction']

# The transferred field (mid computes it, end receives it as input).
TRANSFER_CODE = 'ADVPAY'


def _param_rows(params):
    """(code,EN,VI,value) -> constant 7-tuples in the PARAM category."""
    return [(c, en, vi, 'PARAM', 'const', val, False) for (c, en, vi, val) in params]


def build_components(division, cycle):
    """Ordered component list (7-tuples) for one config = division × cycle.

    Mid and End share the FULL spine (inputs, params, allowances, OT, GROSS,
    insurance, PIT, FULLPAY, employer). They differ only at the net split:
      * Mid  computes ADVPAY = ROUND(FULLPAY × advance-rate) and pays NET = ADVPAY.
      * End  receives ADVPAY as an INPUT and pays NET = FULLPAY − ADVPAY.
    ADVPAY is the one field mapped Mid→End (hr.payroll.cycle.component.mapping).
    """
    dc = DIVISIONS_COMP[division]
    comps = []
    # inputs (+ division inputs); End additionally receives ADVPAY as an input
    comps += SHARED_INPUTS + dc.get('inputs', [])
    if cycle == 'end':
        comps.append(('ADVPAY', 'Mid-Month Advance (received)', 'Tạm ứng đã nhận (K1)',
                      'LOANDED', 'input', None, True))
    # parameters (shared + division; Mid adds the advance-rate params)
    params = PARAMS_SHARED + dc.get('params', [])
    if cycle == 'mid':
        params = params + ADVANCE_PARAMS
    comps += _param_rows(params)
    # earnings + GROSS (identical in both cycles)
    earn = SHARED_EARN + dc.get('earn', [])
    comps += earn
    gross = '=' + '+'.join(['BASIC'] + [e[0] for e in earn])
    comps.append(('GROSS', 'Gross Salary', 'Tổng thu nhập', 'GROSS', 'formula', gross, True))
    # pre-net statutory (… FULLPAY)
    comps += SHARED_PRENET
    # net split (cycle-specific)
    if cycle == 'mid':
        comps.append(('ADVPAY', 'Mid-Month Advance (Net K1)', 'Tạm ứng giữa tháng (Thực nhận K1)',
                      'NET', 'formula', '=ROUND(FULLPAY*IF(GROSS>=ADVTHRESH,ADVRATEHI,ADVRATELO))', True))
        comps.append(('NET', 'Net Salary', 'Thực lãnh', 'NET', 'formula', '=ADVPAY', True))
    else:
        comps.append(('NET', 'Net Salary (end-month)', 'Thực lãnh (cuối tháng)',
                      'NET', 'formula', '=FULLPAY-ADVPAY', True))
    # employer contributions
    comps += SHARED_EMPLOYER
    return comps


# CONFIGS (the 12 (code, name_en, name_vi, division, cycle) tuples) are populated
# at the bottom of this module, once DIVISIONS is defined.
CONFIGS = []


def all_components():
    """Unique components across all 12 configs — for translatable label rules."""
    seen = {}
    for code, name_en, name_vi, div, cycle in CONFIGS:
        for comp in build_components(div, cycle):
            seen.setdefault(comp[0], comp)
    return list(seen.values())


# --- Divisions (employee generation metadata; division = pb_division + KHOI value) -
DIVISIONS = {
    'retail': {'name_en': 'Retail', 'name_vi': 'Bán lẻ', 'headcount': 900,
               'cost_centres': ['Stores - North', 'Stores - South', 'Stores - Central', 'E-commerce', 'Visual Merchandising'],
               'jobs': ['Sales Associate', 'Cashier', 'Store Supervisor', 'Store Manager', 'Area Manager', 'Merchandiser', 'Inventory Clerk'],
               'grades': [('G1 Associate', 6500000, 9500000), ('G2 Senior Associate', 9000000, 13000000),
                          ('G3 Supervisor', 13000000, 19000000), ('G4 Manager', 19000000, 32000000), ('G5 Area Manager', 32000000, 55000000)]},
    'manufacturing': {'name_en': 'Manufacturing', 'name_vi': 'Sản xuất', 'headcount': 1000,
               'cost_centres': ['Assembly Line A', 'Assembly Line B', 'Quality Control', 'Maintenance', 'Warehouse'],
               'jobs': ['Production Operator', 'Machine Operator', 'Line Leader', 'Quality Inspector', 'Shift Supervisor', 'Production Manager', 'Maintenance Technician'],
               'grades': [('P1 Operator', 6000000, 8500000), ('P2 Skilled Operator', 8000000, 12000000),
                          ('P3 Line Leader', 12000000, 18000000), ('P4 Supervisor', 18000000, 28000000), ('P5 Manager', 28000000, 48000000)]},
    'logistics': {'name_en': 'Logistics', 'name_vi': 'Vận tải & Logistics', 'headcount': 700,
               'cost_centres': ['Fleet - HCMC', 'Fleet - Hanoi', 'Warehouse Ops', 'Last Mile', 'Dispatch'],
               'jobs': ['Driver', 'Delivery Rider', 'Warehouse Operative', 'Dispatcher', 'Fleet Supervisor', 'Logistics Coordinator', 'Operations Manager'],
               'grades': [('L1 Operative', 6500000, 9000000), ('L2 Driver', 8500000, 13000000),
                          ('L3 Coordinator', 12000000, 18000000), ('L4 Supervisor', 18000000, 27000000), ('L5 Manager', 27000000, 45000000)]},
    'corporate': {'name_en': 'Corporate Office', 'name_vi': 'Khối văn phòng', 'headcount': 500,
               'cost_centres': ['Finance', 'Human Resources', 'Legal', 'Marketing', 'Executive'],
               'jobs': ['Accountant', 'HR Officer', 'Legal Counsel', 'Marketing Specialist', 'Finance Manager', 'HR Manager', 'Director'],
               'grades': [('C1 Officer', 10000000, 16000000), ('C2 Senior Officer', 15000000, 24000000),
                          ('C3 Lead', 24000000, 38000000), ('C4 Manager', 38000000, 65000000), ('C5 Director', 65000000, 120000000)]},
    'it': {'name_en': 'Information Technology', 'name_vi': 'Công nghệ thông tin', 'headcount': 600,
               'cost_centres': ['Engineering', 'Infrastructure', 'Data & Analytics', 'Product', 'IT Support'],
               'jobs': ['Software Engineer', 'QA Engineer', 'DevOps Engineer', 'Data Analyst', 'Tech Lead', 'Engineering Manager', 'IT Support Specialist'],
               'grades': [('T1 Junior', 12000000, 20000000), ('T2 Engineer', 18000000, 32000000),
                          ('T3 Senior', 30000000, 50000000), ('T4 Lead', 48000000, 75000000), ('T5 Manager', 70000000, 130000000)]},
    'construction': {'name_en': 'Construction', 'name_vi': 'Xây dựng', 'headcount': 800,
               'cost_centres': ['Site - Project Alpha', 'Site - Project Beta', 'Civil Works', 'MEP', 'Site Safety'],
               'jobs': ['Construction Worker', 'Steel Fixer', 'Site Engineer', 'Foreman', 'Safety Officer', 'Site Supervisor', 'Project Manager'],
               'grades': [('S1 Worker', 6000000, 9000000), ('S2 Skilled Worker', 8500000, 13000000),
                          ('S3 Engineer', 13000000, 22000000), ('S4 Supervisor', 22000000, 36000000), ('S5 Project Manager', 36000000, 65000000)]},
}

# Now that DIVISIONS exists, populate the 12 CONFIGS (6 divisions × end/mid).
CONFIGS = []
for _d in _DIV_ORDER:
    _en = DIVISIONS[_d]['name_en']
    _vi = DIVISIONS[_d]['name_vi']
    CONFIGS.append(('DEMO_%s_END' % _d.upper(), 'Payobook %s — End-Month Payroll' % _en,
                    'Payobook %s — Lương cuối tháng' % _vi, _d, 'end'))
    CONFIGS.append(('DEMO_%s_MID' % _d.upper(), 'Payobook %s — Mid-Month Advance' % _en,
                    'Payobook %s — Tạm ứng giữa tháng' % _vi, _d, 'mid'))

# Female ratio per division (industry realism).
FEMALE_RATIO = {'retail': 0.62, 'manufacturing': 0.45, 'logistics': 0.20,
                'corporate': 0.55, 'it': 0.30, 'construction': 0.10}
HIGH_OT_DIVISIONS = {'manufacturing', 'construction', 'logistics'}

# Input codes the generator feeds per employee, per division (END cycle).
DIVISION_INPUTS = {d: [c[0] for c in DIVISIONS_COMP[d].get('inputs', [])] for d in _DIV_ORDER}
