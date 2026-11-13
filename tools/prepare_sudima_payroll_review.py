"""Prepare private September fixtures and a UI-reproducible formula definition.

Reads the audited cell JSON, never changes the customer workbooks. No personal
data is embedded in this script or in the public formula definition.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

p = argparse.ArgumentParser()
p.add_argument('audit_dir', type=Path)
p.add_argument('output_dir', type=Path)
args = p.parse_args()
args.output_dir.mkdir(parents=True, exist_ok=True)
books = {s['name']: {c[0]: c for c in s['cells']}
         for s in json.loads((args.audit_dir/'payroll_cells.json').read_text())}
attendance = {s['name']: {c[0]: c for c in s['cells']}
              for s in json.loads((args.audit_dir/'attendance_cells.json').read_text())}['Attendance Sep-26(N)']

def cell(sheet, col, row):
    return sheet.get(f'{col}{row}', [None, None, None, None])

def value(sheet, col, row):
    return cell(sheet, col, row)[2]

def number(sheet, col, row):
    v = value(sheet, col, row)
    if v in (None, '', '0'):
        return 0
    assert isinstance(v, (int, float)), (col, row, v)
    return v

def key(v):
    return str(int(str(v).strip()))

def roster(sheet, col, start, end):
    result = {}
    for row in range(start, end+1):
        v = value(sheet, col, row)
        if v is not None and re.fullmatch(r'\d+', str(v).strip()):
            k = key(v)
            assert k not in result, (k, row)
            result[k] = row
    return result

actual = books['Actual pay_Sep (transfer+cash)']
audit = books['Salary_Sep (Print-Audit)']
ar = roster(actual, 'I', 9, 899)
br = roster(audit, 'I', 9, 873)
tr = roster(attendance, 'C', 5, 654)
assert len(ar) == 649 and len(br) == len(tr) == 650
assert set(br) == set(tr) and set(br)-set(ar) == {'1168'}

def definition(view):
    rules = []
    def add(code, name, kind='money', formula=None, role='info', lane='adjustments', destination='', application=''):
        rules.append(dict(code=code, name=name, kind=kind, formula=formula,
                          role=role, lane=lane, destination=destination,
                          application=application, required=formula is None))
    add('VNID', 'Employee ID', 'identifier', lane='records', destination='f:hr.employee:barcode', application='employee.barcode')
    add('VNNAME', 'Employee name', 'text', lane='records', destination='f:hr.employee:name', application='employee.name')
    for code, label, kind in [('VNBASIS','Pay basis (1 monthly, 2 daily)','integer'), ('VNBASE','Basic rate','money'),
                              ('VNRESP','Responsibility rate','money'), ('VNPOS','Position rate','money')]:
        add(code, label, kind, lane='records', destination='c:amount')
    add('VNDIVISOR','Monthly salary divisor','quantity', lane='records', destination='c:amount')
    add('VNHOURSDAY','Hours per salary day','quantity', lane='records', destination='c:amount')
    add('VNPAIDDAYS','Paid day equivalents','quantity', lane='time', application='period.paid_day_equivalents')
    add('VNLEAVEQTY','Leave / meal quantity in source','quantity',lane='time')
    add('VNLEAVERATE','Leave / meal unit rate','money',lane='records',destination='c:amount')
    add('VNOTHOURS','Normal overtime base hours','quantity',lane='time')
    add('VNPREMHOURS','Overtime premium equivalent hours','quantity',lane='time')
    add('VNSUNDAYHOURS','Sunday base hours','quantity',lane='time')
    if view == 'actual':
        add('VNSUNPREMHOURS','Sunday premium hours','quantity',lane='time')
    for code, label in [('VNATT','Attendance allowance'),('VNATTPLUS','Additional attendance allowance'),
                        ('VNHOUSE','Housing allowance'),('VNOTHER','Other allowance'),('VNWORK','Work / loading allowance'),
                        ('VNMILEAGE','Mileage allowance'),('VNSAT','Saturday allowance from source'),
                        ('VNSHIFT','Shift allowance from source'),('VNPROD','Production / milestone allowance'),
                        ('VNADJUST','Earnings adjustment'),('VNEFF','Efficiency incentive'),('VNSENIOR','Seniority allowance'),
                        ('VNCHILD','Childcare allowance')]:
        add(code,label,role='earning')
    for code,label in [('VNRECOVERY','Salary recovery'),('VNUNION','Union deduction'),('VNPERSONAL','Personal deduction'),
                       ('VNOTHERDED','Other deduction'),('VNINS','Employee insurance'),('VNADVANCE','Salary advance'),
                       ('VNBANKFEE','Bank fee')]:
        add(code,label,role='deduction')
    add('VNRELIEF','Source personal and dependent tax relief')
    add('VNTAXZERO','Explicit source taxable-income zero (1 yes)','integer')
    add('VNTAXCARRY','Taxable earnings carried from another source row')
    if view == 'actual':
        add('VNAUDITTAXABLE','Print-Audit taxable income used by Actual tax')
    add('VNRECOVERYUSED','Deduct recovery (1 yes, 0 omitted in source)','integer')
    add('VNNETADJUST','Explicit source adjustment before rounding',role='earning')
    add('VNROUNDADJUST','Explicit source adjustment after rounding',role='earning')
    add('VNDAYRATE','Salary per paid day',formula='IF({VNBASIS}=1,({VNBASE}+{VNRESP}+{VNPOS})/{VNDIVISOR},{VNBASE}+{VNRESP}+{VNPOS})')
    add('VNBASEHOUR','Basic hourly rate',formula='IF({VNBASIS}=1,{VNBASE}/{VNDIVISOR},{VNBASE})/{VNHOURSDAY}')
    add('VNREGULAR','Regular salary',formula='{VNDAYRATE}*{VNPAIDDAYS}',role='earning')
    add('VNLEAVEPAY','Leave / meal pay',formula='{VNLEAVEQTY}*{VNLEAVERATE}',role='earning')
    add('VNOTPAY','Normal overtime base pay',formula='{VNBASEHOUR}*{VNOTHOURS}',role='earning')
    add('VNPREMPAY','Overtime premium pay',formula='{VNBASEHOUR}*{VNPREMHOURS}',role='earning')
    add('VNSUNPAY','Sunday base pay',formula='{VNDAYRATE}/{VNHOURSDAY}*{VNSUNDAYHOURS}',role='earning')
    if view == 'actual':
        add('VNSUNPREM','Sunday premium pay',formula='{VNBASEHOUR}*{VNSUNPREMHOURS}',role='earning')
    earnings = [r['code'] for r in rules if r['role']=='earning' and r['code'] not in ('VNNETADJUST','VNROUNDADJUST')]
    add('VNGROSS','Gross earnings',formula='+'.join('{'+c+'}' for c in earnings))
    add('VNATAX','Assessable income in source',formula='{VNGROSS}-{VNPERSONAL}-{VNOTHERDED}-{VNINS}-{VNPREMPAY}-{VNSUNPAY}-{VNSAT}+{VNTAXCARRY}')
    add('VNTAXABLE','Taxable income in this view',formula='IF({VNTAXZERO}=1,0,MAX(0,{VNATAX}-{VNRELIEF}))')
    taxbase = 'VNAUDITTAXABLE' if view == 'actual' else 'VNTAXABLE'
    t='{'+taxbase+'}'
    add('VNTAX','Income tax (Print-Audit basis)' if view=='actual' else 'Income tax',
        formula=f'ROUND(IF({t}<=10000000,{t}*0.05,IF({t}<=30000000,{t}*0.1-500000,IF({t}<=60000000,{t}*0.2-3500000,IF({t}<=100000000,{t}*0.3-9500000,{t}*0.35-14500000)))),-3)',role='deduction')
    add('VNRECOVERYADJUST','Source omission of recovery deduction',formula='{VNRECOVERY}*(1-{VNRECOVERYUSED})',role='earning')
    add('VNNETRAW','Net pay before rounding',formula='{VNGROSS}-{VNRECOVERY}*{VNRECOVERYUSED}-{VNUNION}-{VNPERSONAL}-{VNOTHERDED}-{VNINS}-{VNTAX}-{VNADVANCE}-{VNBANKFEE}+{VNNETADJUST}')
    add('VNNET','Net pay',formula='ROUND({VNNETRAW},-3)+{VNROUNDADJUST}',role='net')
    add('VNROUNDING','Rounding adjustment',formula='{VNNET}-{VNNETRAW}-{VNROUNDADJUST}',role='earning')
    return dict(code='SUDIMA_SEP_2026_'+view.upper(),name='Sudima September 2026 — '+('Actual pay review' if view=='actual' else 'Print-Audit review'),view=view,rules=rules)

mapping_common={'VNBASE':'M','VNRESP':'N','VNPOS':'O','VNPAIDDAYS':'V','VNLEAVEQTY':'X','VNOTHOURS':'Z','VNPREMHOURS':'AB',
                'VNSUNDAYHOURS':'AF','VNATT':'P','VNATTPLUS':'Q','VNHOUSE':'R','VNOTHER':'S','VNWORK':'T','VNMILEAGE':'U','VNSAT':'AE'}
mapping_actual={'VNSUNPREMHOURS':'AH','VNSHIFT':'AJ','VNPROD':'AK','VNADJUST':'AL','VNEFF':'AM','VNSENIOR':'AN','VNCHILD':'AO',
                'VNRECOVERY':'AQ','VNUNION':'AR','VNPERSONAL':'AS','VNOTHERDED':'AT','VNINS':'AU','VNRELIEF':'AW','VNADVANCE':'AZ','VNBANKFEE':'BA'}
mapping_audit={'VNSHIFT':'AH','VNPROD':'AI','VNADJUST':'AJ','VNEFF':'AK','VNSENIOR':'AL','VNCHILD':'AM',
               'VNRECOVERY':'AO','VNUNION':'AP','VNPERSONAL':'AQ','VNOTHERDED':'AR','VNINS':'AS','VNRELIEF':'AU','VNADVANCE':'AX','VNBANKFEE':'AY'}
expected_common={'VNREGULAR':'W','VNLEAVEPAY':'Y','VNOTPAY':'AA','VNPREMPAY':'AC','VNSUNPAY':'AG'}
private={'views':{},'employees':[], 'source_sha256':{
    name:json.loads((args.audit_dir/(name+'_summary.json')).read_text())['sha256']
    for name in ('payroll','attendance')}}
definitions=[]
for view,sheet,rows in [('actual',actual,ar),('audit',audit,br)]:
    spec=definition(view)
    # Owner direction: Actual extras are analysis only, never installed.
    if view == 'audit':
        definitions.append(spec)
    kinds={r['code']:r['kind'] for r in spec['rules']}
    mapping=dict(mapping_common,**(mapping_actual if view=='actual' else mapping_audit))
    expected_map=dict(expected_common,**({'VNSUNPREM':'AI','VNGROSS':'AP','VNATAX':'AV','VNTAXABLE':'AX','VNTAX':'AY','VNNETRAW':'BB','VNNET':'BC'} if view=='actual' else {'VNGROSS':'AN','VNATAX':'AT','VNTAXABLE':'AV','VNTAX':'AW','VNNETRAW':'AZ','VNNET':'BA'}))
    fixtures=[]
    for code,row in rows.items():
        basis=1 if '/26' in cell(sheet,'W',row)[1] else 2
        inputs={c:number(sheet,col,row)*(1000 if kinds[c]=='money' else 1) for c,col in mapping.items()}
        taxable_col='AX' if view=='actual' else 'AV'
        recovery_col='AQ' if view=='actual' else 'AO'
        net_col='BB' if view=='actual' else 'AZ'
        rounded_col='BC' if view=='actual' else 'BA'
        net_formula=cell(sheet,net_col,row)[1]
        round_formula=cell(sheet,rounded_col,row)[1]
        adjust=lambda formula: 1000*int(re.search(r'([+-]1)$',formula).group(1)) if re.search(r'([+-]1)$',formula) else 0
        carry=0
        if view=='audit':
            extra=re.search(r'\+AT(\d+)$',cell(sheet,'AT',row)[1])
            if extra: carry=number(sheet,'AT',int(extra.group(1)))*1000
        inputs.update(VNID=str(value(sheet,'I',row)).strip(),VNNAME=str(value(sheet,'L',row)).strip(),VNBASIS=basis,
                      VNDIVISOR=26,VNHOURSDAY=8,VNLEAVERATE=190000 if view=='actual' else 50000,
                      VNTAXZERO=int(cell(sheet,taxable_col,row)[3]!='f'),VNTAXCARRY=carry,
                      VNRECOVERYUSED=int(f'-{recovery_col}{row}' in net_formula),
                      VNNETADJUST=adjust(net_formula),VNROUNDADJUST=adjust(round_formula))
        if view=='actual': inputs['VNAUDITTAXABLE']=number(audit,'AV',br[code])*1000
        assert set(inputs)=={r['code'] for r in spec['rules'] if r['formula'] is None}
        expected={c:number(sheet,col,row)*1000 for c,col in expected_map.items()}
        expected['VNROUNDING']=expected['VNNET']-expected['VNNETRAW']-inputs['VNROUNDADJUST']
        # Every recovery omitted in the source net formula is explicitly zero.
        assert inputs['VNRECOVERYUSED'] or inputs['VNRECOVERY']==0
        expected['VNRECOVERYADJUST']=0
        fixtures.append(dict(key=code,source_row=row,inputs=inputs,expected=expected))
    private['views'][view]=fixtures
for code,row in br.items():
    sr=ar.get(code); sheet=actual if sr else audit; r=sr or row
    identifier=str(value(sheet,'I',r)).strip()
    private['employees'].append(dict(key=code,code=identifier,name=str(value(sheet,'L',r)).strip(),
        department=str(value(attendance,'E',tr[code]) or '').strip(),
        join_date=value(sheet,'J',r),government_id=str(value(sheet,'D',r) or '').strip(),
        bank_account=str(value(sheet,'F',r) or '').strip(),bank_name=str(value(sheet,'G',r) or '').strip(),
        bank_holder=str(value(sheet,'E',r) or '').strip(),
        attendance_code=str(value(attendance,'C',tr[code])).strip(),
        actual_present=code in ar))

# The guided pay preview recognises PIT as its income-tax component.
# This is a template code choice; the tax formula and all values are unchanged.
for spec in definitions:
    for rule in spec['rules']:
        if rule['code']=='VNTAX': rule['code']='PIT'
        if rule['formula']: rule['formula']=rule['formula'].replace('{VNTAX}','{PIT}')
for fixtures in private['views'].values():
    for fixture in fixtures:
        fixture['expected']['PIT']=fixture['expected'].pop('VNTAX')
(args.output_dir/'definition.json').write_text(json.dumps(definitions,ensure_ascii=False,indent=2))
(args.output_dir/'private-fixtures.json').write_text(json.dumps(private,ensure_ascii=False,indent=2))
print(json.dumps({'rules':{d['view']:len(d['rules']) for d in definitions},'fixtures':{k:len(v) for k,v in private['views'].items()},'employees':len(private['employees'])}))
