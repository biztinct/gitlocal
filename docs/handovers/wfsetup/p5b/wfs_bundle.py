# WFSETUP P5b: the compiled screen code of this database carries the release (odoo-bin shell,
# read-only, rolled back). Clone of docstudio/w2/w2_bundle.py.
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
urls = ' '.join(str(getattr(a, 'url', '') or getattr(a, 'name', '') or '') for a in b.javascripts)
print('PROBE bundle files', len(b.javascripts),
      'setup studio', 'pb_workforce_setup/static' in urls,
      'studio tag', 'pb_workforce_setup_studio' in js,
      'workspace trim', 'TRIMMED_GROUPS' in js,
      'workspace groupLabel', 'groupLabel' in js)
env.cr.rollback()
