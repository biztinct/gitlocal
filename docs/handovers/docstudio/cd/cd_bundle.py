# DOCSTUDIO close-out D: the compiled screen code of this database carries this release (odoo-bin
# shell, read-only, rolled back). Clone of w2/w2_bundle.py.
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
print('PROBE bundle files', len(b.javascripts),
      'Z4 preview flag', 'pbds_preview_auto' in js,
      'anchors pd-button', 'pd-button' in js, 'rb-rowis', 'rb-rowis' in js, 'dc-note', 'dc-note' in js,
      'ds-langs', 'ds-langs' in js, 'dh-lang', 'dh-lang' in js,
      'learn practice copies', 'reportpdf()' in js or 'reportpdf(' in js,
      'spotlight re-place 700 ms', 'setTimeout(place, 700)' in js or 'setTimeout(place,700)' in js)
env.cr.rollback()
