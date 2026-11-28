# DOCSTUDIO W2: the compiled screen code of this database carries the wave-2 modules (odoo-bin shell,
# read-only, rolled back). Clone of w1b/w1b_bundle.py.
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
urls = ' '.join(str(getattr(a, 'url', '') or getattr(a, 'name', '') or '') for a in b.javascripts)
print('PROBE bundle files', len(b.javascripts),
      'pdf button', 'registry.category("pb_report_pdf").add("button"' in js,
      'toolbars look it up', js.count('registry.category("pb_report_pdf")') >= 3,
      'contract document', 'pb_doc_contracts/static' in urls,
      'hiring bridge', 'pb_doc_studio_hiring/static' in urls,
      'certificate bridge', 'pb_doc_studio_me/static' in urls,
      'send bridge', 'pb_report_pdf_send/static' in urls)
env.cr.rollback()
