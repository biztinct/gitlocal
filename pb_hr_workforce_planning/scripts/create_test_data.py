#!/usr/bin/env python3
"""
WFP Test Data Generator
Creates realistic test data for the Workforce Planning dashboard:
1. Auto-tags formula rules with WFP categories
2. Sets contract wages
3. Creates 2 planning scenarios with increase rules
4. Runs the simulation engine
"""

# === STEP 1: Auto-tag formula component WFP categories ===
config = env['hr.formula.config'].browse(5)
rules = env['hr.formula.rule'].search([('config_id', '=', 5)])

# Classification mapping based on Vietnamese payroll component analysis
TAG_MAP = {
    # Base salary components
    'MCLNGH': 'base_salary',   # Mức lương HĐLĐ

    # Allowances (Phụ cấp / Hỗ trợ)
    'PHCPPCCCAT': 'allowance',
    'PHCPCNGTC': 'allowance',
    'HTRCM': 'allowance',
    'HTRNH': 'allowance',
    'PCCHDANH': 'allowance',
    'PCKIMNHIM': 'allowance',
    'PCBITPHI': 'allowance',
    'PCTHMN': 'allowance',
    'BIDNGPHSK': 'allowance',

    # Earnings (wage-type items => base_salary or allowance)
    'LNGNGYTH': 'base_salary',

    # Deductions (Các khoản trừ)
    'BHXH': 'deduction',
    'BHYT': 'deduction',
    'BHTN': 'deduction',
    'TNGBHXH': 'deduction',
    'TRUYTHUBHXH': 'deduction',
    'PHCNGO': 'deduction',
    'THUTNCN': 'deduction',
    'THUTINTM': 'deduction',

    # Employer costs (BHXH employer portion)
    'THAMGIABHXH': 'employer_cost',
    'CONSTANTBHXH': 'employer_cost',
    'CONSTANTBHYT': 'employer_cost',
    'CONSTANTBHTN': 'employer_cost',

    # Gross / Net
    'TNGTHUNH': 'gross',
    'THCNHNK1': 'net',
    'THCNHNK2': 'net',

    # Bonus
    'THNGN': 'bonus',
    'TMNGTHN': 'bonus',
    'CHITRPHPNM': 'bonus',

    # Info only
    'TT': 'info',
    'MSNV': 'info',
    'HVTN': 'info',
    'NV': 'info',
    'NPT': 'info',
    'GIMTRNPT': 'info',
    'GIMTRCN': 'info',
    'TNTT': 'info',
    'NGCHLNG': 'info',
}

tagged_count = 0
for rule in rules:
    code = rule.code
    # Try exact match first
    matched_cat = None
    for prefix, cat in TAG_MAP.items():
        if code == prefix or code.startswith(prefix):
            matched_cat = cat
            break

    # Heuristic: component_type hints
    if not matched_cat:
        ct = rule.component_type or ''
        if 'trừ' in ct.lower() or 'khấu trừ' in ct.lower():
            matched_cat = 'deduction'
        elif 'hưởng' in ct.lower():
            matched_cat = 'allowance'
        elif 'Constant' in ct:
            matched_cat = 'employer_cost'
        elif 'Ngày công' in ct:
            matched_cat = 'info'

    if not matched_cat:
        # Default: info for unmatched
        matched_cat = 'info'

    rule.wfp_category = matched_cat
    tagged_count += 1

print('TAGGED: %d rules' % tagged_count)
env.cr.commit()

# === STEP 2: Set contract wages for Vietnamese employees ===
# Realistic VN salaries (monthly VND)
WAGES = {
    'Tô Thanh Liêm': 15000000,       # 15M - Accounting
    'Nguyễn Thành An': 12000000,      # 12M - HR
    'Nguyễn Hữu Thọ': 18000000,      # 18M - Finance
    'Trương Thị Thu Hiền': 14000000,  # 14M - Accounting
    'Võ Thị Tú Trinh': 11000000,     # 11M - Admin
    'Nguyễn Ngọc Thủy Tiên': 13000000, # 13M - HR
    'Nguyễn Hồng Nhung': 16000000,   # 16M - Digital Transformation
}

contracts = env['hr.contract'].search([('state', '=', 'open')])
for ct in contracts:
    name = ct.employee_id.name
    if name in WAGES:
        ct.wage = WAGES[name]
        print('SET WAGE: %s -> %s' % (name, WAGES[name]))
env.cr.commit()

# === STEP 3: Create test scenarios ===
Scenario = env['wfp.planning.scenario']

# Scenario 1: Conservative 5% across the board
s1 = Scenario.create({
    'name': 'FY2027 Budget — Conservative 5%',
    'formula_config_id': 5,
    'fiscal_year': 2027,
    'effective_date': '2027-01-01',
    'budget_amount': 1500000000,  # 1.5B VND budget
    'state': 'draft',
})
print('CREATED SCENARIO 1: id=%s' % s1.id)

# Create increase rule for scenario 1 - flat 5% on base
env['wfp.increase.rule'].create({
    'scenario_id': s1.id,
    'name': 'Standard 5% Base Salary Increase',
    'increase_type': 'percentage',
    'increase_pct': 5.0,
    'component_target': 'base',
    'apply_to': 'all',
    'exclude_probation': True,
    'sequence': 10,
})
print('CREATED RULE for S1: 5% base')

# Scenario 2: Aggressive differential
s2 = Scenario.create({
    'name': 'FY2027 Budget — Aggressive Differential',
    'formula_config_id': 5,
    'fiscal_year': 2027,
    'effective_date': '2027-01-01',
    'budget_amount': 1800000000,  # 1.8B VND budget
    'state': 'draft',
})
print('CREATED SCENARIO 2: id=%s' % s2.id)

# Multiple rules for scenario 2
env['wfp.increase.rule'].create({
    'scenario_id': s2.id,
    'name': 'HR & Admin 3% Increase',
    'increase_type': 'percentage',
    'increase_pct': 3.0,
    'component_target': 'base',
    'apply_to': 'department',
    'exclude_probation': True,
    'sequence': 10,
    'department_ids': [(6, 0, env['hr.department'].search([('name', 'in', ['Ban nhân sự', 'Ban hành chính', 'Administration'])]).ids)],
})
print('CREATED RULE for S2: HR/Admin 3%')

env['wfp.increase.rule'].create({
    'scenario_id': s2.id,
    'name': 'Finance & Accounting 7% Increase',
    'increase_type': 'percentage',
    'increase_pct': 7.0,
    'component_target': 'base',
    'apply_to': 'department',
    'exclude_probation': True,
    'sequence': 20,
    'department_ids': [(6, 0, env['hr.department'].search([('name', 'in', ['Ban kế toán', 'Ban tài chính'])]).ids)],
})
print('CREATED RULE for S2: Finance 7%')

env['wfp.increase.rule'].create({
    'scenario_id': s2.id,
    'name': 'Digital Transformation 10% Increase',
    'increase_type': 'percentage',
    'increase_pct': 10.0,
    'component_target': 'base',
    'apply_to': 'department',
    'exclude_probation': True,
    'sequence': 30,
    'department_ids': [(6, 0, env['hr.department'].search([('name', '=', 'Ban Chuyển đổi số')]).ids)],
})
print('CREATED RULE for S2: Digital 10%')
env.cr.commit()

# === STEP 4: Calculate forecasts ===
print('CALCULATING S1...')
try:
    s1.action_calculate()
    print('S1 CALCULATED: headcount=%s, forecast=%s' % (s1.headcount, s1.total_forecast_cost))
except Exception as e:
    print('S1 ERROR: %s' % str(e)[:200])

print('CALCULATING S2...')
try:
    s2.action_calculate()
    print('S2 CALCULATED: headcount=%s, forecast=%s' % (s2.headcount, s2.total_forecast_cost))
except Exception as e:
    print('S2 ERROR: %s' % str(e)[:200])

env.cr.commit()
print('DONE - ALL TEST DATA CREATED')
