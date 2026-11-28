"""Synthetic pay schemes used by the Pay Builder checks and browser walks."""
import re

from odoo import Command
from odoo.addons.pb_hr_payroll_formula.models.scheme_proposal import SCHEME_APPLY_KEY, SCHEME_APPLY_TOKEN


def make_scheme(env, company, shape):
    env = env(context=dict(env.context, tracking_disable=True, **{SCHEME_APPLY_KEY: SCHEME_APPLY_TOKEN}))
    country = 'IN' if shape in ('COMP', 'COMP_DAYS') else 'VN'
    scheme = env['hr.formula.config'].create({
        'name': 'DEMO Pay Builder ' + shape, 'code': 'DEMOPB' + shape,
        'company_id': company.id, 'country_code': country,
    })
    category = env['hr.salary.rule.category'].search([('code', '=', 'OTH')], limit=1)
    if not category:
        category = env['hr.salary.rule.category'].create({'name': 'DEMO Other', 'code': 'OTH'})
    data = []
    formulas = {}

    def line(code, label, role='info', *, usual=0, person=False, kind='money',
             formula=None, constant=None, source=False, detail=False, labels=None, application_key=None):
        vals = {
            'code': code, 'config_id': scheme.id, 'sequence': len(data) + 1,
            'name': 'DEMO ' + label, 'column_type': 'input', 'category_id': category.id,
            'appears_on_payslip': role != 'info', 'value_kind': kind, 'net_role': role,
            'net_role_detail': detail, 'default_value': usual, 'is_contract_component': person,
        }
        if application_key:
            vals['application_source_key'] = application_key
        if labels:
            vals['value_labels'] = labels
        if formula is not None:
            vals['column_type'] = 'formula'
            formulas[code] = formula
        if constant is not None:
            vals.update(column_type='constant', constant_value=constant)
        if source:
            vals['source_ids'] = [Command.create({'kind': 'excel', 'key': label})]
        data.append(vals)

    if shape in ('SIMPLE', 'WAGE'):
        line('BASIC', 'Basic wage', 'earning')
        if shape == 'WAGE':
            line('LUNCH', 'Lunch allowance', 'earning', usual=730000, person=True)
            line('PHONE', 'Phone allowance', 'earning', person=True)
            line('DEP', 'People they support', person=True, kind='integer')
            line('INS', 'Pays social insurance', usual=1, person=True, kind='boolean', labels='0=No;1=Yes')
            line('OT', 'Overtime', 'earning', source=True)
            line('CAP', 'Insurance wage ceiling', constant=46800000)
            for code, label, rate, er_rate in [('SI','Social insurance',.08,.175), ('HI','Health insurance',.015,.03), ('UI','Unemployment insurance',.01,.01)]:
                for suffix, pct, role in [('',rate,'deduction'), ('ER',er_rate,'employer_cost')]:
                    rate_code = code + suffix + 'RATE'
                    line(rate_code, label + ' rate' + (' for the company' if suffix else ''), constant=pct, kind='rate')
                    line(code + suffix, label + (' paid by the company' if suffix else ''), role,
                         formula='IF({INS}=1,ROUND(MIN({BASIC},{CAP})*{' + rate_code + '},0),0)')
            env['hr.formula.rate.table'].create({
                'name': 'DEMO Progressive tax', 'code': 'DEMOTAX', 'config_id': scheme.id,
                'line_ids': [Command.create({'lower': lower, 'rate': rate}) for lower, rate in
                             [(0,.05),(5000000,.1),(10000000,.15),(18000000,.2),(32000000,.25),(52000000,.3),(80000000,.35)]],
            })
            line('TAXABLE', 'Taxable pay', formula='MAX(0,{BASIC}+{LUNCH}+{PHONE}+{OT}-MIN({LUNCH},730000)-{SI}-{HI}-{UI}-11000000-{DEP}*4400000)')
            line('PIT', 'Personal income tax', 'deduction', formula='BRACKET(DEMOTAX,{TAXABLE})')
            net = '{BASIC}+{LUNCH}+{PHONE}+{OT}-{SI}-{HI}-{UI}-{PIT}'
        else:
            net = '{BASIC}'
        line('TAKEHOME', 'Take-home', 'net', formula=net)
    elif shape in ('COMP', 'COMP_DAYS'):
        line('INANNFIX', 'Annual fixed pay', person=True)
        line('INANNVAR', 'Variable pay for the year', person=True)
        line('BASICRATE', 'Basic share', constant=.5, kind='rate')
        line('HRARATE', 'House rent share', constant=.65, kind='rate')
        line('PFRATE', 'Provident fund rate', constant=.12, kind='rate')
        line('PFCAP', 'Provident fund ceiling', constant=25000)
        line('BASIC', 'Basic', 'earning', formula='ROUND({INANNFIX}*{BASICRATE}/12,0)', detail=True)
        line('HRA', 'House rent allowance', 'earning', formula='ROUND({BASIC}*{HRARATE},0)', detail=True)
        line('PFER', 'Provident fund paid by the company', 'employer_cost', formula='ROUND(MIN({BASIC},{PFCAP})*{PFRATE},0)')
        line('CONV', 'Conveyance allowance', 'earning', formula='MAX(0,ROUND({INANNFIX}/12,0)-{BASIC}-{HRA}-{PFER})', detail=True)
        line('MED', 'Medical reimbursement', 'earning', usual=1250, person=True, detail=True)
        line('PHONE', 'Telephone and internet', 'earning', person=True, detail=True)
        line('ARR', 'Approved arrears', 'earning', source=True, detail=True)
        line('INGROSS', 'Gross pay', 'earning', formula='{BASIC}+{HRA}+{CONV}+{MED}+{PHONE}+{ARR}')
        line('PFEE', 'Provident fund employee share', 'deduction', formula='{PFER}')
        line('INPT', 'Profession tax', 'deduction', usual=200, source=True)
        line('PIT', 'Income tax', 'deduction', source=True)
        line('INNET', 'Take-home', 'net', formula='{INGROSS}-{PFEE}-{INPT}-{PIT}')
        if shape == 'COMP_DAYS':
            line('FULLPERIOD', 'Standard working days', kind='quantity', source=True,
                 application_key='period.standard_days')
            line('PAIDPERIOD', 'Paid days', kind='quantity', source=True,
                 application_key='period.paid_day_equivalents')
            formulas['BASIC'] = 'ROUND({INANNFIX}*{BASICRATE}/12/{FULLPERIOD}*{PAIDPERIOD},0)'
    elif shape == 'NONE':
        line('FILEPAY','Pay from the file','earning',usual=50000,source=True)
        line('FILENET','Take-home','net',formula='{FILEPAY}')
    elif shape == 'NONET':
        line('BASIC','Basic wage','earning')
    elif shape == 'BROKEN':
        line('BASIC','Basic wage','earning')
        line('DIVISOR','Number of shares',person=True,kind='integer')
        line('SHARE','Shared deduction','deduction',formula='{BASIC}/{DIVISOR}')
        line('PAYNET','Take-home','net',formula='{BASIC}-{SHARE}')
    elif shape == 'BIG':
        line('BASIC','Basic wage','earning')
        for n in range(398):
            line('DEMOLINE' + str(n), 'Earning ' + str(n + 1), 'earning', formula='ROUND({BASIC}*0.001,0)')
        line('BIGNET','Take-home','net',formula='SUM({BASIC}:{DEMOLINE397})')

    rules = env['hr.formula.rule'].create(data)
    by_code = {r.code: r for r in rules}
    for vals in data:
        rule = by_code[vals['code']]
        updates = {k: vals[k] for k in ('net_role', 'net_role_detail', 'value_kind', 'appears_on_payslip') if rule[k] != vals[k]}
        if rule.code in formulas:
            updates['excel_formula'] = '=' + re.sub(r'\{(\w+)\}', lambda m: by_code[m[1]].column_letter + '5', formulas[rule.code])
        if updates:
            rule.write(updates)
    scheme.write({'state': 'active'})
    return scheme
