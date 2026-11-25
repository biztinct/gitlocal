# WFSETUP P6: the compiled screen code of this database carries the release (odoo-bin shell,
# read-only, rolled back). Clone of ../p5b/wfs_bundle.py.
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
print('PROBE bundle files', len(b.javascripts),
      'studio tag', 'pb_workforce_setup_studio' in js,
      'P6 switch', 'clock_switch_on' in js,
      'P6 finish', 'clocks_sending' in js)
env.cr.rollback()
