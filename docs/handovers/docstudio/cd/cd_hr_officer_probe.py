# DOCSTUDIO close-out D: an HR-officer-level person on LIVE payobook, synthetic and ROLLED BACK (no login
# left). Same groups the Access screen's "Time off officer" role gives (it implies HR officer), no payroll
# role. Mirrors pb_report_builder test 22 + build, save, download, and a protected pay field.
import base64, json
from odoo.exceptions import AccessError, UserError
def p(*a): print('PROBE', *a)
try:
    comp = env['res.company'].browse(5)
    gids = [env.ref('base.group_user').id, env.ref('hr_holidays.group_hr_holidays_user').id]
    u = env['res.users'].with_context(no_reset_password=True).create({
        'name': 'DEMO CD HR probe', 'login': 'demo.cd.hr.probe@example.invalid',
        'company_id': comp.id, 'company_ids': [(6, 0, [comp.id])], 'group_ids': [(6, 0, gids)]})
    e = env(user=u.id, context=dict(env.context, allowed_company_ids=[comp.id]))
    p('groups: HR officer', u.has_group('hr.group_hr_user'), 'payroll officer', u.has_group('pb_hr_payroll_base.group_payroll_base_officer'),
      'analytics', u.has_group('pb_hr_payroll_base.group_payroll_analytics_user'))
    item = env.ref('pb_insights_hub.item_insights')
    p('side menu Insights', env['pb.sidebar.item'].visibility_for(u)['items'].get(item.id))
    RB = e['pb.report.builder']
    p('Build a report opens', RB.can_open())
    refused = []
    for model, method, args in [('pb.insights', 'get_insights', ()), ('pb.explorer', 'get_schema', ()),
                                ('pb.explorer', 'query', ({},)), ('pb.workforce.insights', '_require', ())]:
        if model not in env:
            continue
        try:
            getattr(e[model], method)(*args); refused.append('%s.%s=OPEN' % (model, method))
        except (AccessError, UserError):
            refused.append('%s.%s=refused' % (model, method))
    p('payroll tabs on the server', ' '.join(refused))
    ex = RB.examples()
    pick = next((x for x in ex if x['spec'].get('subject') == 'people'), ex[0])
    res = RB.run(pick['spec'])
    card = RB.save_report('DEMO CD HR probe report', pick['spec'], False)
    xl = RB.export_xlsx(pick['spec'], 'DEMO CD HR probe report')
    xb = base64.b64decode(xl['file_b64']) if isinstance(xl, dict) and xl.get('file_b64') else b''
    p('build: examples', len(ex), 'rows', res.get('total', len(res.get('rows', []))), '| saved id', bool(card.get('id')),
      '| Excel file', xb[:2] == b'PK', 'name has vendor word', 'odoo' in str((xl or {}).get('filename', '')).lower())
    # a protected pay field
    sch = RB.schema()
    p('subjects locked for this person', '; '.join('%s: %s' % (s_['label'], s_['why']) for s_ in (sch.get('subjects') or []) if s_.get('locked'))[:400])
    found = []
    for subj in (sch.get('subjects') or []):
        for f in [f for sec in (subj.get('sections') or []) for f in sec.get('fields', [])]:
            k = str(f.get('key', ''))
            if 'wage' in k.lower():
                found.append((subj.get('key'), k, f.get('locked') or f.get('refused') or f.get('note') or ''))
    p('pay fields offered to this person', len(found), json.dumps(found[:3])[:300])
    if found:
        subj, key, _n = found[0]
        try:
            r = RB.run({'subject': subj, 'columns': [key]})
            p('pay field run', 'rows', len(r.get('rows', [])), 'message', str(r.get('note') or r.get('msg') or r.get('warning') or '')[:160])
        except (AccessError, UserError) as ex2:
            p('pay field refused:', str(ex2)[:200])
    else:
        # no pay field is offered at all: try one by name on the contracts subject
        try:
            r = RB.run({'subject': 'contracts', 'columns': ['wage']})
            p('pay field by name ran', 'rows', len(r.get('rows', [])), 'message', str(r.get('note') or r.get('msg') or '')[:160])
        except (AccessError, UserError) as ex2:
            p('pay field by name refused:', str(ex2)[:200])
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:200])
finally:
    env.cr.rollback()
    p('rolled back')
