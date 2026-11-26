# PSCHEME P4 (odoo-bin shell, read-only, rolled back): what "Usual pay scheme by country" shows on this
# database, per company - counts only (countries, states, people relying, holes, other rules), plus the
# served code carries the section.
assert not env.cr.dbname.startswith('abm'), 'never this database'
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
print('PROBE', env.cr.dbname, 'section in served code', 'CountryLines' in js, '| country_set kind',
      'country_set' in dict(env['pb.schememap.proposal']._proposal_kind_labels))
for co in env['res.company'].sudo().search([], order='id'):
    if not env['hr.employee'].sudo().search_count([('company_id', '=', co.id)]):
        continue
    B = env['pb.scheme.board'].with_company(co).with_context(allowed_company_ids=[co.id])
    d = B.country_lines(co.id)
    rows = ['%s:%s/%s people/%s rely/%s holes' % (r['country'], r['state'], r['people'], r['rely'], r['holes'])
            for r in d['rows']]
    print('PROBE   company', co.id, '| set', d['set'], 'of', len(d['rows']), '| holes', d['holes'],
          '| other rules', len(d['others']), [(o['reaches'], o['removable']) for o in d['others']], '|', '; '.join(rows))
env.cr.rollback()
