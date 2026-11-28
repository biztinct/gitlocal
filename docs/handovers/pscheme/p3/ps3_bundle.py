# PSCHEME P3 (odoo-bin shell, read-only, rolled back): the compiled code of this database carries the
# release, and the person-scheme engine is there with NO rows yet. Clone of ../../newhire/p8/nh8_bundle.py.
#   person block    the side panel's Pay scheme block (P1)
#   fill drawer     Mapping's "Give everyone their own pay scheme" (P2a)
#   country prompt  the Country of work prompt after a save (P2a)
#   learn replica   the Add employee practice copy draws the Pay scheme from the Country of work (P3 B)
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
env.cr.execute("select count(*) from pb_person_scheme")
rows = env.cr.fetchone()[0]
env.cr.execute("select count(*) from pb_person_scheme_fill")
fills = env.cr.fetchone()[0]
cron = env.ref('pb_scheme_map.cron_person_scheme_boundaries', raise_if_not_found=False)
src = dict(env['pb.person.scheme']._fields['source']._description_selection(env))
print('PROBE bundle files', len(b.javascripts),
      'person block', 'PersonSchemeBlock' in js,
      'fill drawer', 'PersonFillDrawer' in js,
      'country prompt', 'Change the pay scheme too?' in js,
      'learn replica', 'Filled in from the Country of work' in js,
      '| person scheme rows', rows, 'fills', fills,
      '| new job', bool(cron), cron and cron.active, cron and cron.interval_number, cron and cron.interval_type,
      '| sheet source', src.get('sheet'),
      '| langs', ' '.join(env['res.lang'].sudo().search([('active', '=', True)]).mapped('code')))
env.cr.rollback()
