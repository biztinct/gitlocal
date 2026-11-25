# WFSETUP P9: the compiled screen code of this database carries the release (odoo-bin shell,
# read-only, rolled back). Clone of ../p6/p6_bundle.py.
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
c = env['ir.qweb']._get_asset_bundle('web.assets_web', css=True, js=False)
css = ''.join(a.content for a in c.stylesheets) if hasattr(c, 'stylesheets') else ''
sel = dict(env['pb.clock.connector']._fields['state'].selection)
print('PROBE bundle files', len(b.javascripts),
      'P9 enable', 'clock_enable' in js,
      'P9 css', 'pbck-off-note' in css,
      'state disabled', sel.get('disabled'),
      'action_disable', hasattr(env['pb.clock.connector'], 'action_disable'))
env.cr.rollback()
