# DOCSTUDIO W1B: the compiled screen code and the PDF style sheet of this database carry the new
# module (odoo-bin shell, read-only, rolled back). Clone of the wave 1a bundle check.
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
r = env['ir.qweb']._get_asset_bundle('web.report_assets_common', css=True, js=False)
css = ''.join((a.content or '') for a in r.stylesheets)
print('PROBE bundle files', len(b.javascripts),
      'action', 'registry.category("actions").add("pb_doc_studio"' in js,
      'settings card', 'registry.category("pb_settings_category").add(' in js and 'pb_doc_studio' in js,
      'palette row', 'registry.category("pb_hub_palette").add("doc_studio"' in js,
      'report fonts', 'pbds-face' in css or any('report_fonts' in str(getattr(a, 'url', '') or '') for a in r.stylesheets))
env.cr.rollback()
