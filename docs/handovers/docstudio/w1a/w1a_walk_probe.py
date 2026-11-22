# DOCSTUDIO W1A: the browser walk's functional steps run as the payobook QA login (uid 6672) and as one
# existing HR-officer-level login, inside odoo-bin shell, everything ROLLED BACK (precedent S5M-4:
# no password typed). Prints PROBE lines: counts and yes/no only, never names or values.
import base64, io
from odoo.exceptions import AccessError, UserError
from openpyxl import Workbook, load_workbook
def p(*a): print('PROBE', *a)
try:
    qa = env['res.users'].browse(6672)
    cids = qa.company_ids.ids
    q = env(user=qa.id, context=dict(env.context, allowed_company_ids=[qa.company_id.id] + [c for c in cids if c != qa.company_id.id]))
    RB = q['pb.report.builder']
    p('qa can_open', RB.can_open())
    ex = RB.examples()
    pick = next((e for e in ex if e['spec'].get('subject') == 'people'), ex[0])
    spec = dict(pick['spec'])
    sch = RB.schema()
    subj = next(s for s in sch['subjects'] if s['key'] == spec['subject'])
    keys = [f['key'] for sec in subj.get('sections', []) for f in sec.get('fields', [])] or \
           [f['key'] for f in subj.get('fields', [])]
    extra = next((k for k in keys if k not in spec['columns']), None)
    spec['columns'] = spec['columns'] + ([extra] if extra else [])
    p('qa example', pick['key'], 'added a field', bool(extra), 'columns', len(spec['columns']))
    gkey = next((k for k in ('department', 'company', 'job') if k in keys), None)
    if gkey:
        spec['group_by'] = [gkey]
    r = RB.run(spec, 0, 50)
    p('qa run grouped', bool(gkey), 'ok', r.get('ok', True), 'groups', len(r.get('groups') or []), 'total', r.get('total'))
    card = RB.save_report('W1A walk', spec, False)
    rid = card['id']
    p('qa saved report', bool(rid), 'my reports', len(RB.my_reports()))
    x = RB.export_xlsx(spec, 'W1A walk')
    wb = load_workbook(io.BytesIO(base64.b64decode(x['file_b64'])))
    p('qa excel download ok', x['ok'], 'rows', x['rows'], 'sheets', len(wb.sheetnames), 'vendor-in-name', 'odoo' in x['filename'].lower())
    # Explorer: save a view, use my Excel layout, try it, save, download, Send as
    V = q['pb.explorer.view']
    view = V.pbx_save('W1A walk view', {'measure': 'net', 'dimension': 'department_id'}, False)
    vid = view['id']
    B = q['pb.excel.layout.board']
    wbt = Workbook(); ws = wbt.active; ws.title = 'Data'; ws['A1'] = 'Board pack'
    buf = io.BytesIO(); wbt.save(buf); b64 = base64.b64encode(buf.getvalue()).decode()
    ins = B.inspect(b64, 'pack.xlsx', 'pb.explorer.view', vid)
    p('qa explorer layout inspect sheets', len(ins.get('sheets') or []), 'table cols', (ins.get('table') or {}).get('cols'))
    tr = B.try_it(b64, 'Data', 'B6', True, 'pb.explorer.view', vid, 'pack.xlsx')
    p('qa try it ok', tr.get('ok'), 'rows', tr.get('rows'), 'cols', tr.get('cols'), 'vendor-in-name', 'odoo' in (tr.get('filename') or '').lower(), tr.get('msg') or '')
    lay = B.save({'name': 'W1A walk layout', 'file_b64': b64, 'file_name': 'pack.xlsx', 'sheet': 'Data',
                  'start': 'B6', 'headers': True, 'shared': False,
                  'source_model': 'pb.explorer.view', 'source_id': vid})
    dl = B.download(lay['id'])
    p('qa download in my layout', 'fallback' if dl.get('fallback') else 'ok', 'has file', bool(dl.get('file_b64')))
    dr = q['pb.explorer'].schedule_drawer(vid)
    p('qa send-as choices in the drawer', len(dr.get('layouts') or []))
    # report builder's toolbar source: a saved built report fills a layout too (C1)
    tr2 = B.try_it(b64, 'Data', 'A3', True, 'pb.report.definition', rid, 'pack.xlsx')
    p('qa try it from the built report', tr2.get('ok'), 'rows', tr2.get('rows'))
    # HR-officer-level login (existing, internal, HR officer, no payroll/analytics group)
    pay_groups = ['pb_hr_payroll_base.group_payroll_base_user', 'pb_hr_payroll_base.group_payroll_base_officer',
                  'pb_hr_payroll_base.group_payroll_base_manager', 'pb_hr_payroll_base.group_payroll_analytics_user',
                  'pb_hr_payroll_base.group_payroll_analytics_manager', 'base.group_system']
    cand = env['res.users'].search([('share', '=', False), ('active', '=', True), ('id', '>', 2)], order='id')
    hr = next((u for u in cand if u.has_group('hr.group_hr_user')
               and not any(env.ref(g, raise_if_not_found=False) and u.has_group(g) for g in pay_groups)), None)
    if not hr:
        p('hr officer: none found')
    else:
        h = env(user=hr.id, context=dict(env.context, allowed_company_ids=hr.company_ids.ids))
        item = env.ref('pb_insights_hub.item_insights')
        gf = 'all_group_ids' if 'all_group_ids' in hr._fields else 'groups_id'  # implied groups count
        p('hr officer uid', hr.id, 'demo name', (hr.name or '').upper().startswith('DEMO'),
          'Insights entry groups match', bool(item.groups_id & hr[gf]), 'report builder opens', h['pb.report.builder'].can_open())
        for label, fn in [('explorer schema', lambda: h['pb.explorer'].get_schema()),
                          ('explorer query', lambda: h['pb.explorer'].query({'measure': 'net'})),
                          ('pulse', lambda: h['pb.insights'].get_insights() if 'pb.insights' in h else None)]:
            try:
                with env.cr.savepoint():
                    fn()
                p('hr officer', label, 'ALLOWED')
            except (AccessError, UserError) as e:
                p('hr officer', label, 'refused')
            except Exception as e:
                p('hr officer', label, 'error', type(e).__name__)
        ex_h = h['pb.report.builder'].examples()
        p('hr officer examples offered', len(ex_h))
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:300])
finally:
    env.cr.rollback()
    p('rolled back')
