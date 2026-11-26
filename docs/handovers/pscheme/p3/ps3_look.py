# PSCHEME P3 C.5 (odoo-bin shell on payobook, read-only, rolled back): what the QA login's screens are served,
# through the screens' own calls AS THAT USER (no password typed anywhere): the Mapping board's banner figures
# (get_board -> persons), one person's Pay scheme block (person_scheme, the side panel and the Change pay scheme
# dialog read the same answer), en and vi. Counts and words only, no names.
assert env.cr.dbname == 'payobook', 'payobook only'
qa = env['res.users'].sudo().search([('login', '=', 'qa.test@payobook.com')], limit=1)
assert qa, 'no QA login'
for cid in sorted(set(qa.company_ids.ids)):
    B = env['pb.scheme.board'].with_user(qa).with_company(cid).with_context(allowed_company_ids=[cid])
    try:
        b = B.get_board(cid)
    except Exception as e:      # noqa: BLE001
        print('PROBE company', cid, 'board refused:', type(e).__name__, str(e)[:120]); continue
    p = b.get('persons') or {}
    print('PROBE company', cid, 'board allowed', b.get('allowed'), '| banner: people', p.get('people'), 'own', p.get('own'),
          'still follow their team', p.get('without'), 'other-country', p.get('mismatch'), 'latest fill', p.get('latest_fill'),
          'can propose', p.get('can_propose'))
    emp = env['hr.employee'].sudo().search([('company_id', '=', cid), ('active', '=', True),
                                            ('contract_id.state', '=', 'open')], limit=1)
    if not emp:
        continue
    for lang in ('en_US', 'vi_VN'):
        ps = B.with_context(lang=lang).person_scheme(emp.id)
        m = ps.get('main') or {}
        print('PROBE   person (%s) %s: found %s, scheme kind %s, own %s, from words %r, choices %s, can propose %s, lane %s, none words %r, mismatch %s' % (
            lang, emp.id, ps.get('found'), m.get('kind_words'), m.get('own'), m.get('from_words') or m.get('since_words'),
            len(ps.get('choices') or []), ps.get('can_propose'), ps.get('lane'), (ps.get('none_words') or '')[:60],
            bool(ps.get('country_mismatch'))))
env.cr.rollback()
