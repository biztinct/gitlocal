# NEWHIRE P6 read-only look (odoo-bin shell; LIVE or a rehearsal copy). Creates nothing: every call is the
# studio's own server call, the payslip example is savepoint + rollback by design, and the whole shell
# transaction is rolled back at the end. Row counts of the tables a hire would touch are printed before
# and after inside the same transaction (and nh_counts.sh runs outside, before and after, too).
#   teams      one team per pay-scheme country: the scheme and currency the studio decides
#   example    the first-payslip example for that team (Studio step 3)
#   papers     step 5's list for that country
#   hiring     the "From Hiring" tile (count of signed offers waiting)
#   words      step 6 in vi_VN and id_ID: checklist name, step titles, equipment names
#   checklist  one existing joining checklist read as a vi and an id reader (pb.journeys.get_case)
import time
DBS = ('payobook', 'payobook_template', 'p0clone', 'rize', 'sudima')
assert env.cr.dbname in DBS or env.cr.dbname.startswith('nh6_rh_'), env.cr.dbname
TABLES = ('hr_employee', 'hr_contract', 'hr_version', 'pb_newhire_proposal', 'pb_journey_case', 'pb_journey_task',
          'hr_payslip', 'hr_payslip_line', 'mail_mail', 'mail_message', 'res_users', 'pb_asset_request',
          'pb_new_hire_ask', 'ir_attachment')


def counts():
    out = {}
    for t in TABLES:
        env.cr.execute("select to_regclass(%s)", ('public.' + t,))
        if env.cr.fetchone()[0]:
            env.cr.execute('select count(*), coalesce(max(id),0) from "%s"' % t)
            out[t] = env.cr.fetchone()
    return out


before = counts()
out = []
installed = env['ir.module.module'].sudo().search_count([('name', '=', 'pb_new_hire'), ('state', '=', 'installed')])
out.append('pb_new_hire installed %s' % bool(installed))
if installed:
    M = env['pb.scheme.map'].sudo()
    Cfg = env['hr.formula.config'].sudo()
    start = '2026-12-01'
    wages = {'VN': 12000000, 'ID': 6000000, 'IN': 50000, 'SG': 5000, 'MY': 4000}
    seen = set()
    companies = env['res.company'].sudo().search([])
    for c in companies:
        if not env['hr.employee'].sudo().search_count([('company_id', '=', c.id)]):
            continue
        S = env['pb.new.hire'].with_company(c).with_context(allowed_company_ids=[c.id], lang='en_US')
        for d in env['hr.department'].sudo().search([('company_id', '=', c.id)], order='id'):
            try:
                r = M.resolve_for_team(d.id, c.id)
            except Exception as e:                       # noqa: BLE001
                continue
            cfg = Cfg.browse(r.get('config_id') or 0).exists() if r else Cfg
            code = (getattr(cfg, 'country_code', '') or '').upper() if cfg else ''
            if not cfg or not code or code in seen or code not in wages:
                continue
            seen.add(code)
            dec = S.decides(d.id, code, start)
            sch = dec.get('scheme') or {}
            cur = dec.get('currency') or {}
            out.append('TEAM %s | company %s | team %s | country %s | scheme %s | currency %s | mismatch %s' % (
                code, c.id, d.id, code, sch.get('name') if isinstance(sch, dict) else sch,
                cur.get('name') or cur.get('symbol') if isinstance(cur, dict) else cur, bool(dec.get('mismatch'))))
            draft = {'name': 'Example Person', 'date_start': start, 'department_id': d.id, 'payroll_country': code,
                     'wage': wages[code], 'contract_kind': 'permanent', 'trial_on': True}
            t0 = time.time()
            ex = S.payslip_example(draft)
            out.append('  EXAMPLE ok %s | %s | scheme %s | money %s | gross %s | net %s | lines %s | %s ms | reason %s' % (
                ex.get('ok'), ex.get('month_label'), ex.get('scheme'), (ex.get('currency') or {}).get('symbol'),
                ex.get('gross'), ex.get('net'), len(ex.get('lines') or []),
                int((time.time() - t0) * 1000), ex.get('reason') or ''))
            dt = S.details_options(draft)
            items = dt.get('items') or []
            out.append('  PAPERS %s: %s' % (dt.get('country_name'), '; '.join(
                (i.get('label') or i.get('name') or i.get('key') or '?') for i in items)[:400]))
            for lang in ('vi_VN', 'id_ID'):
                w = env['pb.new.hire'].with_company(c).with_context(allowed_company_ids=[c.id], lang=lang) \
                    .welcome_options(dict(draft, equipment=None))
                out.append('  WORDS %s: checklist "%s" (%s steps) | steps: %s | equipment: %s' % (
                    lang, (w.get('case') or {}).get('template_name'), (w.get('case') or {}).get('steps'),
                    ' / '.join(t.get('title') or '' for t in (w.get('timeline') or []))[:600],
                    ', '.join(e.get('name') or '' for e in (w.get('equipment') or []))))
        ld = env['pb.new.hire'].with_company(c).with_context(allowed_company_ids=[c.id]).load()
        out.append('HIRING tile company %s: %s' % (c.id, ld.get('hiring')))
J = env['pb.journeys'].sudo()
case = env['pb.journey.case'].sudo().search([('case_type', '=', 'onboarding'), ('task_ids', '!=', False)], order='id desc', limit=1)
if case:
    for lang in ('vi_VN', 'id_ID', 'en_US'):
        rows = J.with_context(lang=lang).get_case(case.id)['tasks']
        out.append('CHECKLIST case %s %s: %s' % (case.id, lang, ' / '.join(r['name'] for r in rows)[:500]))
else:
    out.append('CHECKLIST none on this database')
for lang in ('vi_VN', 'id_ID'):
    cats = env['pb.asset.category'].sudo().with_context(lang=lang).search([])
    out.append('EQUIPMENT %s: %s' % (lang, ', '.join(cats.mapped('name'))))
after = counts()
diff = {t: (before[t], after.get(t)) for t in before if before[t] != after.get(t)}
out.append('COUNTS inside the transaction: %s' % ('identical' if not diff else diff))
print('PROBE ' + '\nPROBE '.join(out))
env.cr.rollback()
