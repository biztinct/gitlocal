# DOCSTUDIO W1A probe (odoo-bin shell; read-only in effect: everything is rolled back).
# As the administrator: report builder answers (subjects, examples, one example run, Excel),
# then contract C1 across the two modules: save a built report, fill a tiny generated workbook
# from it through the Excel layout board's "Try it". Prints PROBE lines; never prints values.
import base64, io, os
from openpyxl import Workbook, load_workbook
out = []
def p(*a):
    print('PROBE', *a)
try:
    admin = env.ref('base.user_admin')
    cids = admin.company_ids.ids
    uenv = env(user=admin.id, context=dict(env.context, allowed_company_ids=cids))
    mods = {m.name: (m.state, m.latest_version) for m in env['ir.module.module'].search(
        [('name', 'in', ['pb_report_builder', 'pb_excel_layout', 'pb_explorer'])])}
    p('modules', ' '.join('%s=%s:%s' % (k, v[0], v[1]) for k, v in sorted(mods.items())))
    if 'pb.report.builder' in env and mods.get('pb_report_builder', ('',))[0] == 'installed':
        RB = uenv['pb.report.builder']
        p('rb can_open', bool(RB.can_open()))
        sch = RB.schema()
        subs = sch.get('subjects') if isinstance(sch, dict) else sch
        p('rb subjects', len(subs or []))
        ex = RB.examples()
        p('rb examples', len(ex))
        p('rb saved reports', env['pb.report.definition'].sudo().search_count([]))
        if ex:
            spec = ex[0]['spec']
            r = RB.run(spec, 0, 50)
            p('rb run example', ex[0]['key'], 'rows', len(r.get('rows') or []), 'total', r.get('total'))
            x = RB.export_xlsx(spec, ex[0]['name'])
            fn = (x or {}).get('filename') or ''
            p('rb excel', 'ok' if (x and (x.get('file_b64') or x.get('data') or x.get('content'))) else 'keys=%s' % sorted((x or {}).keys()), 'vendor-in-name', 'odoo' in fn.lower())
            card = RB.save_report('W1A probe', spec, False)
            rid = card['id'] if isinstance(card, dict) else card
            rep = uenv['pb.report.definition'].browse(rid)
            t = rep._pbxl_table()
            p('c1 table', 'cols', len(t['columns']), 'rows', len(t['rows']), 'truncated', t['truncated'])
            if 'pb.excel.layout.board' in env:
                wb = Workbook(); ws = wb.active; ws.title = 'Data'
                ws['A1'] = 'W1A probe layout'
                buf = io.BytesIO(); wb.save(buf)
                b64 = base64.b64encode(buf.getvalue()).decode()
                B = uenv['pb.excel.layout.board']
                ins = B.inspect(b64, 'probe.xlsx', 'pb.report.definition', rid)
                p('c1 inspect', 'ok' if ins.get('ok', True) and ins.get('sheets') else ins.get('msg'))
                tr = B.try_it(b64, 'Data', 'A3', True, 'pb.report.definition', rid, 'probe.xlsx')
                if tr.get('ok'):
                    wb2 = load_workbook(io.BytesIO(base64.b64decode(tr['file_b64'])))
                    ws2 = wb2['Data']
                    filled = sum(1 for row in ws2.iter_rows(min_row=4) if any(c.value is not None for c in row))
                    p('c1 try_it ok rows', tr['rows'], 'cols', tr['cols'], 'filled rows in file', filled,
                      'A1 kept', ws2['A1'].value == 'W1A probe layout',
                      'vendor-in-name', 'odoo' in tr['filename'].lower())
                else:
                    p('c1 try_it FAILED', tr.get('msg'))
                p('pbxl layouts', env['pb.excel.layout'].sudo().search_count([]))
    if 'pb.explorer.view' in env:
        p('explorer views', env['pb.explorer.view'].sudo().search_count([]),
          'schedules', env['pb.explorer.schedule'].sudo().search_count([]) if 'pb.explorer.schedule' in env else '-')
        sf = env['pb.explorer.schedule']._fields if 'pb.explorer.schedule' in env else {}
        p('schedule send-as field', 'layout_id' in sf)
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:300])
finally:
    env.cr.rollback()
    p('rolled back')
