# WFSETUP P10b: the compiled code of this database carries the release (odoo-bin shell, read-only,
# rolled back). Clone of ../p9/p9_bundle.py.
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
print('PROBE bundle files', len(b.javascripts),
      'clock panel', 'pb_clock_readiness' in js,
      'extra hours', 'extra_hours_off' in js,
      'clock card', 'bp_clock_bind' in js,
      'clock date field', 'pb_clock_from' in env['hr.formula.config']._fields,
      'provider', 'pb.clock.payroll' in env,
      'schemes with a clock date', env['hr.formula.config'].sudo().search_count([('pb_clock_from', '!=', False)]))
env.cr.rollback()
