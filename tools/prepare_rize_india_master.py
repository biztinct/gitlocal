#!/usr/bin/env python3
"""Prepare a metadata-only India definition and private reconciliation inputs.

Reads the client XLS/XLSX without changing either source. BIFF extraction is a
separate read-only step; --private-dir holds its source-data.json and all people
or pay values. No employee fixtures are written into the repository.
"""
import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CODE = 'RIZE_INDIA_CLIENT_MASTER_2026'


def letter(index):
    result = ''
    while index:
        index, n = divmod(index - 1, 26)
        result = chr(65 + n) + result
    return result


def rounded(value):
    return float(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def prepare(private_dir):
    source = json.loads((private_dir / 'source-data.json').read_text())
    salary = source['payroll']['Payroll_August 2026']
    master = source['master']['India']
    rules = []

    def add(code, name, kind='money', group='Employee records', destination='',
            formula='', value=None, tab='', role='info', detail=False,
            required=False, source_column='', source_sheet='', note=''):
        spec = dict(code=code, name=name, kind=kind, group=group,
                    destination=destination, formula=formula, value=value,
                    tab=tab, role=role, detail=detail, required=required,
                    type='formula' if formula else 'constant' if value is not None else 'input',
                    source_column=source_column, source_sheet=source_sheet,
                    note=note)
        spec['source_key'] = 'Consolidated|' + name if spec['type'] == 'input' else ''
        rules.append(spec)
        return spec

    def calc(code, name, expr, group='Calculation', role='info', detail=False, kind='money', note=''):
        return add(code, name, kind, group, formula=expr, role=role,
                   detail=detail, note=note or 'Calculated from the August client payroll. Never an Excel or employee-record mapping input.')

    add('INCODE', 'Employee Code', 'identifier', destination='f:hr.employee:barcode', required=True,
        note='Canonical employee-master ID; historical payroll code is retained separately. Identity conflicts must be approved before import.')
    add('INMASTERID', 'Employee ID', 'identifier', destination='f:hr.employee:employee_id', required=True,
        note='Global ID from the India employee master. Initially the same canonical ID as Employee Code; both native identity fields are kept consistent.')
    add('INNAME', 'Employees name', 'text', destination='f:hr.employee:name', required=True)
    add('INJOIN', 'Date of Joining', 'date', destination='f:hr.employee:date_of_joining')
    add('INJOB', 'Designation', 'text', destination='f:hr.employee:job_id')
    add('INDEPT', 'Department', 'text', destination='f:hr.employee:department_id')
    add('INLOC', 'Location', 'text', destination='f:hr.contract:location')
    add('INDOR', 'DOR', 'date', destination='f:hr.contract:date_end',
        note='Last employment date reported by payroll. A source/master status conflict requires review; historical pay must remain possible.')
    add('INWDAYS', 'No. of Working Days', 'quantity', 'Time', tab='Time', required=True,
        note='Salary I11 calendar-day divisor. Enter the applicable month divisor, including the full-month denominator for a leaver.')
    add('INPDAYS', 'No. of days paid', 'quantity', 'Time', tab='Time', required=True,
        note='Salary I: actual payable days. The client leaver has 14/31 days.')
    add('INADAYS', 'Arrears Days', 'quantity', 'Time', tab='Time',
        note='Source reference quantity. The client workbook does not turn it into pay. Approved arrears payment is a separate monthly amount.')
    add('INANNFIX', 'Annual Fixed CTC', group='Contract pay', destination='c:amount', required=True,
        note='Annual fixed CTC includes employer PF. Kept as one relational contract amount. August payroll is authoritative for pay amounts.')
    add('INANNVAR', 'Variable Component', group='Contract pay', destination='c:amount',
        note='Annual target variable component, information only. It is not automatically paid every month.')
    calc('INANNCTC', 'Annual CTC', '{INANNFIX}+{INANNVAR}', 'Contract calculation')
    calc('INMONTHCTC', 'Monthly Fixed CTC', '{INANNFIX}/12', 'Contract calculation')
    calc('INBASICANN', 'Basic (Annual contract)', 'ROUND({INANNFIX}*{INBASICRATE},0)', 'Contract calculation')
    calc('INHRAANN', 'House rent allowance (Annual contract)', 'ROUND({INBASICANN}*{INHRARATE},0)', 'Contract calculation')
    calc('INCONVANN', 'Conveyance allowance (Annual contract)',
         'ROUND({INANNFIX}-({INBASICANN}+{INHRAANN}),0)-IF({INPFMODE}="Full basic",{INPFANN},{INPFCAP}*12)', 'Contract calculation')
    calc('INPFANN', 'Employers contribution to PF (Annual contract)',
         'IF({INPFMODE}="Full basic",ROUND({INBASICANN}*{INPFRATE},0),'
         'IF({INANNFIX}-{INHRAANN}-{INPFCAP}*12<{INPFBASE}*12,'
         'ROUND(({INANNFIX}-{INHRAANN}-{INPFCAP}*12)*{INPFRATE},0),{INPFCAP}*12))',
         'Contract calculation', note='Salary R: capped source branch, or full annual Basic for the source exception. August parameters are explicit constants and require review before live use for later periods.')
    calc('INCTCTOTAL', 'Total (Annual contract)', 'SUM({INBASICANN},{INHRAANN},{INCONVANN},{INPFANN})', 'Contract calculation')
    calc('INBASIC', 'Basic (Earnings)', 'ROUND({INBASICANN}/12/{INWDAYS}*{INPDAYS},0)+{INBASICADJ}', 'Earnings', 'earning', True)
    calc('INHRA', 'House rent allowance (Earnings)', 'ROUND({INHRAANN}/12/{INWDAYS}*{INPDAYS},0)+{INHRAADJ}', 'Earnings', 'earning', True)
    monthly = [
        ('INCONV', 'Conveyance allowance', 'V'),
        ('INBOOKS', 'Books & Periodicals', 'W'),
        ('INPHONE', 'Telephone & Internet', 'X'),
        ('INPROFDEV', 'Professional Development Course', 'Y'),
        ('INLTA', 'Leave Travel Allowance', 'Z'),
        ('INCAR', 'Car Maintenance & Fuel', 'AA'),
        ('INDRIVER', 'Driver Allowance', 'AB'),
        ('INUNIFORM', 'Uniform Allowance', 'AC'),
        ('INHELPER', 'Helper Allowance', 'AD'),
        ('INMEDICAL', 'Medical Reimbursement', 'AE'),
        ('INRESEARCH', 'Research Allowance', 'AF'),
    ]
    for code, name, col in monthly:
        add(code, name, group='Earnings', tab='Monthly adjustments', role='earning', detail=True,
            required=code=='INCONV',
            source_column=col, source_sheet='Payroll_August 2026',
            note='Approved current-month payment from the client payroll. Not a recurring contract amount.')
    add('INLEAVEDAYS', 'Leave balance for encashment', 'quantity', 'Time', tab='Time',
        note='Leave Encashment D. Only the days being paid out, not the total saved leave balance.')
    calc('INLEAVE', 'Leave Encashment',
         'ROUND(ROUND({INBASICANN}/12,0)/{INWDAYS}*{INLEAVEDAYS},0)', 'Earnings', 'earning', True,
         note='Leave Encashment F: rounded full-month Basic divided by the full-month divisor, multiplied by approved encashment days. Not prorated again by paid days.')
    add('INARREARS', 'Approved arrears payment', group='Earnings', tab='Monthly adjustments', role='earning', detail=True,
        note='Explicit approved arrears amount. August is zero. Arrears Days alone does not establish the amount or historical rate.')
    add('INVARPAY', 'Variable pay paid this month', group='Earnings', tab='Monthly adjustments', role='earning', detail=True,
        note='Explicit approved payout; annual target Variable Component is never added automatically.')
    earnings = ['INBASIC', 'INHRA'] + [x[0] for x in monthly] + ['INLEAVE', 'INARREARS', 'INVARPAY']
    calc('INGROSS', 'Total (Earnings)', 'SUM(' + ','.join('{'+c+'}' for c in earnings) + ')', 'Totals', 'earning')
    for code, name, col, required in [
        ('INPT', 'Profession Tax', 'AI', True),
        ('INPFEE', "Employee's contribution to PF", 'AJ', True),
        ('PIT', 'Tax Deducted at Source (TDS)', 'AK', True),
        ('INOTHERDED', 'Other Deduction', 'AL', False),
    ]:
        add(code, name, group='Deductions', tab='Monthly adjustments', role='deduction', detail=True,
            required=required, source_column=col, source_sheet='Payroll_August 2026',
            note='Approved monthly amount from the client payroll. No calculation for this deduction is supplied. Enter a reviewed zero explicitly when no deduction applies; do not carry August forward.')
    calc('INDEDTOTAL', 'Total deduction', 'SUM({INPT},{INPFEE},{PIT},{INOTHERDED})', 'Totals', 'deduction')
    calc('INNET', 'NET PAY', '{INGROSS}-{INDEDTOTAL}', 'Totals', 'net')
    calc('INPFER', 'Employers contribution to PF (Monthly)', 'ROUND({INPFANN}/12,0)', 'Employer contributions', 'employer_cost')
    for code, name in [('INBASICADJ', 'Basic rounding adjustment'), ('INHRAADJ', 'House rent allowance rounding adjustment')]:
        add(code, name, group='Rounding adjustments', tab='Monthly adjustments',
            note='Explicit signed adjustment found in the client row formula (+1 or -1 rupee). Included inside the corresponding earning once. Zero in a normal month unless the payroll owner approves an adjustment.')
    add('INPFMODE', 'PF contribution basis', 'text', 'Contract pay', destination='c:text', required=True,
        note='Capped or Full basic. Full basic represents the one exception in Salary R; this is a saved setting, never an employee-name condition in code.')
    add('INOLDCODE', 'Payroll Employee Code (source)', 'identifier', destination='c:text',
        note='Audit/reference alias from the August workbook. Never used as an alternative identity match when it belongs to another master employee.')
    add('INHOLD', 'Payment status (source)', 'text', destination='c:text',
        note='Preserves the payroll Hold marker. A Draft calculation does not release or authorize a bank payment.')

    # Keep source labels identifiable. Duplicate semantic fields above use one
    # authoritative input; computed/source-only foreign-country fields stay out.
    aliases = {'D': 'INMASTERID', 'F': 'INNAME', 'U': 'INJOB', 'X': 'INJOIN',
               'AC': 'INDOR', 'AH': 'INDEPT', 'BK': 'INANNFIX'}
    excluded = {'A', 'G', 'H', 'L', 'Q', 'AM', 'AS', 'AT', 'AU', 'AV', 'AW',
                'BN', 'BO', 'BP', 'BQ', 'BU', 'BV', 'BW', 'BX', 'BY'}
    native = {
        'B':'f:hr.employee:payroll_country', 'J':'f:hr.employee:country_id',
        'K':'f:hr.employee:birthday', 'M':'f:hr.employee:place_of_birth',
        'P':'f:hr.employee:marital', 'R':'f:hr.employee:private_email',
        'S':'f:hr.employee:private_phone', 'T':'f:hr.employee:work_phone',
        'Z':'f:hr.contract:trial_date_end', 'AL':'f:hr.contract:date_start', 'AN':'f:hr.employee:identification_id',
        'AO':'f:hr.employee:permit_no', 'AP':'f:hr.employee:passport_id',
        'AR':'f:hr.contract:tax_identification_number',
        'BD':'f:hr.employee:private_street', 'BF':'f:hr.employee:emergency_phone',
        'BG':'f:hr.employee:emergency_contact', 'BL':'f:hr.contract:wage',
        'CI':'f:hr.employee:work_email', 'CQ':'b:bank_name',
        'CR':'b:acc_number', 'CS':'b:acc_holder_name',
        'CU':'f:hr.employee:study_school', 'CV':'f:hr.employee:study_field',
    }
    date_cols = set('K Y Z AB AC AL BZ CB CC CM CO'.split())
    number_cols = set('BL BR BS CX CY CZ DA'.split())
    for i, raw_name in enumerate(master['rows'][0]):
        col = letter(i+1)
        if not raw_name or col in aliases or col in excluded:
            continue
        name = re.sub(r'\s+', ' ', str(raw_name)).strip()
        name = re.sub(r'\((?:HR Only Visibility|Employee and HR Only Visibility|Employee, HR and Administrative stakeholder visibility)\)', '', name).strip()
        if len(name) > 66:
            name = name.split('(')[0].strip().rstrip('/')
        dest = native.get(col)
        kind = 'date' if col in date_cols else 'rate' if col == 'BM' else 'money' if col in number_cols and col not in {'CX','CY','CZ','DA'} else 'quantity' if col in {'CX','CY','CZ','DA'} else 'identifier' if col in {'C','E','AN','AP','AR','CR','CT'} else 'text'
        if not dest:
            dest = 'c:amount' if kind in {'money','quantity','rate'} else 'c:text'
        if dest == 'c:text':
            kind = 'identifier' if kind == 'identifier' else 'text'
        spec = add('INHC'+col, name, kind, destination=dest,
                   source_column=col, source_sheet='India',
                   note='Employee master input, stored on the native employee/contract/bank destination where suitable; otherwise one relational contract text/amount line. Information only, excluded from payroll totals.')
        if col == 'CT':
            spec['note'] += ' India IFSC is preserved as contract text; it is not mislabeled or saved as an international SWIFT/BIC.'
        if col == 'BL':
            spec['note'] += ' Initial monthly fixed CTC baseline is Annual Fixed CTC / 12; payroll calculations continue to use the saved annual CTC, avoiding another proration.'
    for code, name, val, kind in [
        ('INBASICRATE','Basic allocation rate',.5,'rate'),
        ('INHRARATE','House rent allowance rate on Basic',.65,'rate'),
        ('INPFRATE','Employer PF rate (August source)',.12,'rate'),
        ('INPFCAP','Monthly employer PF cap (August source)',1800,'money'),
        ('INPFBASE','Monthly PF wage ceiling (August source)',15000,'money'),
    ]:
        add(code, name, kind, 'Source parameters', value=val,
            note='Explicit parameter from the August 2026 client workbook. Historical comparison value, not a declaration of the current statutory rule. Review applicable later-period PF rules before live payroll.')
    calc('INREADY', 'Payroll input validation',
         'IF(OR({INMONTHCTC}<=0,{INANNCTC}<{INANNFIX},ABS({INCTCTOTAL}-{INANNFIX})>1,{INWDAYS}<=0,{INPDAYS}<0,{INPDAYS}>{INWDAYS},{INLEAVEDAYS}<0),"Review salary or days",'
         'IF(AND({INPFMODE}<>"Capped",{INPFMODE}<>"Full basic"),"Review PF contribution basis",'
         'IF(AND({INADAYS}<>0,{INARREARS}=0),"Review arrears payment","Ready")))', kind='text')

    by = {r['code']:r for r in rules}
    assert len(by) == len(rules)
    assert len({r['name'] for r in rules}) == len(rules)
    inputs=[]
    for n, row in enumerate(salary['rows'],1):
        if n < 13 or not row[1]:
            continue
        values={'INANNFIX':row[10], 'INANNVAR':row[11], 'INWDAYS':31,
                'INPDAYS':row[8], 'INADAYS':row[9], 'INLEAVEDAYS':0,
                'INARREARS':0, 'INVARPAY':0,
                'INPFMODE':'Full basic' if salary['formulas']['R'+str(n)].startswith('+ROUND(O') else 'Capped'}
        for r in rules:
            col=r['source_column']
            if r['source_sheet']=='Payroll_August 2026' and r['type']=='input':
                idx=0
                for ch in col:idx=idx*26+ord(ch)-64
                values[r['code']]=row[idx-1] or 0
        for code,col in [('INBASICADJ','T'),('INHRAADJ','U')]:
            formula=salary['formulas'][col+str(n)]
            tail=re.search(r'([+-]\d+\.\d+)$',formula)
            values[code]=float(tail[1]) if tail else 0
        for lr in source['payroll']['Leave Encashment']['rows']:
            if lr[0]==row[1]:
                assert str(lr[1]).strip()==str(row[2]).strip(), 'Leave employee ID belongs to a different person'
                values['INLEAVEDAYS']=lr[3]
        expected={code:row[idx] or 0 for code,idx in [
            ('INANNCTC',12),('INMONTHCTC',13),('INBASICANN',14),('INHRAANN',15),
            ('INCONVANN',16),('INPFANN',17),('INCTCTOTAL',18),
            ('INBASIC',19),('INHRA',20),('INLEAVE',32),('INGROSS',33),
            ('INDEDTOTAL',38),('INNET',39)]}
        expected['INPFER']=row[17]/12
        # Independent checks from inputs, never baselines copied from the engine.
        check=dict(INBASICANN=rounded(values['INANNFIX']*.5))
        check['INHRAANN']=rounded(check['INBASICANN']*.65)
        check['INBASIC']=rounded(check['INBASICANN']/12/31*values['INPDAYS'])+values['INBASICADJ']
        check['INHRA']=rounded(check['INHRAANN']/12/31*values['INPDAYS'])+values['INHRAADJ']
        check['INLEAVE']=rounded(rounded(check['INBASICANN']/12)/31*values['INLEAVEDAYS'])
        check['INGROSS']=sum(check.get(c,values.get(c,0)) for c in earnings)
        check['INDEDTOTAL']=sum(values[c] for c in ['INPT','INPFEE','PIT','INOTHERDED'])
        check['INNET']=check['INGROSS']-check['INDEDTOTAL']
        assert all(abs(v-expected[c])<.00001 for c,v in check.items()),(row[1],check,expected)
        inputs.append(dict(row=n,payroll_code=row[1],payroll_name=row[2],values=values,expected=expected,
                           original=row,rounding={c:values[c] for c in ['INBASICADJ','INHRAADJ']}))
    assert len(inputs)==27
    definition=dict(code=CODE,name='Rize India Payroll Client Master 2026',country='IN',
                    company='Rize Farms',period='2026-08',source_hashes=source['sources'],rules=rules,
                    time_order=[r['code'] for r in rules if r['tab']=='Time'],
                    adjustments_order=[r['code'] for r in rules if r['tab']=='Monthly adjustments'],
                    master_aliases=aliases,master_excluded_columns=sorted(excluded),
                    source_notes=['Salary TDS, professional tax and employee PF are approved monthly inputs: no source calculation is supplied.',
                                  'Annual target variable pay is information only; the payout is a separate monthly input.',
                                  'Basic/HRA row-level rounding corrections are visible signed monthly adjustments.',
                                  'Historical PF constants reproduce August and must be reviewed for later-period statutory changes.'])
    (ROOT/'docs/configuration/rize-india-client-master-2026.json').write_text(json.dumps(definition,ensure_ascii=False,indent=2)+'\n')
    (private_dir/'payroll-fixtures.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2))
    print(json.dumps(dict(rules=len(rules),inputs=sum(r['type']=='input' for r in rules),formulas=sum(r['type']=='formula' for r in rules),
                          time=len(definition['time_order']),adjustments=len(definition['adjustments_order']),
                          source_employees=len(inputs),independent_checks=len(inputs)*len(check),
                          totals={c:sum(r['expected'][c] for r in inputs) for c in ['INGROSS','INDEDTOTAL','INNET','INPFER']}),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--private-dir',type=Path,required=True)
    prepare(parser.parse_args().private_dir)
