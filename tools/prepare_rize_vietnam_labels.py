#!/usr/bin/env python3
"""Read the approved master headings; emit a non-personal label/mapping patch."""
import hashlib
import json
from pathlib import Path
import re

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'RIZE/VIETNAM/Rize_VN_Payroll_Report_Aug_2026_FINAL v3.xlsx'


def prepare():
    book = openpyxl.load_workbook(SOURCE, data_only=False)
    sheet = book['Salary']

    def text(value):
        return re.sub(r'\s+', ' ', str(value or '')).strip()

    def heading(letter):
        col = openpyxl.utils.column_index_from_string(letter)
        value = sheet.cell(7, col).value
        if value is None:
            for span in sheet.merged_cells.ranges:
                if span.min_col <= col <= span.max_col and span.min_row <= 7 <= span.max_row:
                    value = sheet.cell(span.min_row, span.min_col).value
                    break
        return text(value)

    labels = {openpyxl.utils.get_column_letter(i): heading(openpyxl.utils.get_column_letter(i))
              for i in range(1, 76)}
    # Keep every word supplied by Excel; add only the context supplied by its
    # merged parent when a leaf repeats or means only a currency.
    for currency, parent in [('K','K6'),('L','K6'),('BB','BB6'),('BC','BB6'),('BI','BI6'),('BJ','BI6')]:
        labels[currency] = text(sheet[parent].value) + ' — ' + heading(currency)
    labels['U'] += ' — ' + text(sheet['R6'].value)
    labels['AF'] += ' — ' + text(sheet['V6'].value)
    labels['AP'] += ' — ' + text(sheet['AN6'].value)
    labels['AU'] += ' — ' + text(sheet['AS6'].value)
    labels['AX'] += ' — Count'
    labels['AY'] += ' — VND'
    for col in ['BN','BO','BP','BQ']:
        labels[col] += ' — ' + text(sheet['BL6'].value)
    for col in ['BT','BU','BV','BW']:
        labels[col] += ' — ' + text(sheet['BS6'].value)
    direct = {
        'VNHCE':'B', 'VNHCF':'C', 'VNHCU':'D', 'VNPTYPE':'E', 'VNSIJOIN':'F',
        'VNPAYNAT':'G', 'VNHCX':'H', 'VNHCAB':'I', 'VNHCCB':'J',
        'VNGROSSUSD':'K','VNHCBK':'L','VNEFFINS':'M',
        'VNSTDDAYS':'O','VNPAIDDAYS':'P','VNBASIC':'Q','VNUNIFORM':'R',
        'VNFREETEL':'S','VNSEVER':'T','VNFREOTH':'U','VNLEAVEPAY':'V',
        'VNEXTRANS':'W','VNTRANSPAY':'X','VNPHONEPAY':'Y','VNPRIVATE':'Z',
        'VNTECH':'AA','VNY2S2':'AB','VNPRODUCT':'AC','VNACTBONUS':'AD',
        'VNREFERRAL':'AE','VNOTHTAX':'AF','VNPREADD':'AG','VNPREDED':'AH',
        'VNBENEFIT':'AI','VNOVERTIME':'AJ','VNHOLPAY':'AK','VNTOTALINC':'AL',
        'VNTAXABLE':'AM','VNSIEMP':'AN','VNHIEMP':'AO','VNUIEMP':'AP',
        'VNUNIONEE':'AQ','VNTUFLAG':'AR','VNSIER':'AS','VNHIERR':'AT',
        'VNUIERR':'AU','VNTUER':'AV','VNPERSDED':'AW','VNREGISTER':'AX',
        'VNDEPDED':'AY','VNASSESS':'AZ','VNPITDUE':'BA','VNNETINC':'BB',
        'VNUSDNET':'BC','VNEMPCTC':'BD','VNADVANCE':'BE','VNDEDUCT':'BF',
        'VNNETADD':'BG','VNPITREF':'BH','VNNETPAY':'BI','VNUSDPAY':'BJ',
        'VNTRIP':'BL','VNPREMIUM':'BM','VNREVTX':'BN','VNREVAI':'BO',
        'VNREVPIT':'BP','VNGAP':'BQ','VNHCAH':'BR','VNSUPPORT':'BS',
        'VNSUPTX':'BT','VNSUPAI':'BU','VNSUPPIT':'BV','VNSUPGAP':'BW',
    }
    rules = [{'code':code,'name':labels[col],'column':col,'key':'Salary|'+col}
             for code,col in direct.items()]
    # M is a calculated result in the scheme; an optional fixed-base input is
    # different and keeps an explicit qualifier. The registered count remains
    # separate from the imported dependent-detail count.
    rules += [{'code':'VNINSBASE','name':labels['M']+' — Fixed base','column':'M','key':'Salary|M'},
              {'code':'VNPITRES','name':labels['BA']+' — Workbook','column':'BA','key':''}]
    columns = [dict(key='Salary|'+col,sheet='Salary',header=heading(col),label=label,
                    letter=col,physical_letter=col,preferred=True,sample='',
                    data_start_row=9,data_end_row=78)
               for col,label in labels.items() if label]
    types = {r['code']:r['type'] for r in json.loads(
        (ROOT/'docs/configuration/rize-vietnam-payroll-master-v3.json').read_text())['rules']}
    outputs = {col for code,col in direct.items() if types[code]=='formula'} - {'M'}
    for column in columns:
        if column['letter'] in outputs:
            column['calculated'] = True
    result = dict(code='RIZE_VIETNAM_MASTER_V3',filename=SOURCE.name,
                  sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  rules=rules,columns=columns)
    path=ROOT/'docs/configuration/rize-vietnam-master-labels.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'rules':len(rules),'columns':len(columns),'path':str(path)}))


if __name__=='__main__':
    prepare()
