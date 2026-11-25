# WFSETUP P10c: the compiled code of this database carries the release (odoo-bin shell, read-only,
# rolled back). Clone of ../p10b/p10b_bundle.py.
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
Config = env['hr.formula.config'].sudo()
dated = Config.search([('pb_clock_from', '!=', False)])
print('PROBE bundle files', len(b.javascripts),
      'clock chip template', 'SrcClockChip' in js,
      'template notes', hasattr(Config, '_pb_clock_template_notes'),
      'source chip', hasattr(env['pb.formula.studio'], '_source_clock_chip'),
      'schemes with a clock date', len(dated),
      'chips', sum(len(c._pb_clock_rules()) for c in dated))
env.cr.rollback()
