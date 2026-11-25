# NEWHIRE P6 (clone of ../p5b/nh_bundle.py): the compiled code of this database carries the release (odoo-bin shell, read-only,
# rolled back). Clone of ../../wfsetup/p10b/p10b_bundle.py.
#   studio       the studio's action is in the backend bundle (all five after P6)
#   takeover     the old door's tag is taken over (all five after P6)
#   old window   the old three-step window is still registered (everywhere)
#   step 2 line  P5b's "names only what is missing" sentence
#   learn        the new Add employee replica in Learn's engine
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
installed = env['ir.module.module'].sudo().search_count([('name', '=', 'pb_new_hire'), ('state', '=', 'installed')])
Cfg = env['payroll.ai.config'].sudo() if 'payroll.ai.config' in env else None
readers = {}
for c in env['res.company'].sudo().search([]):
    # an EMPTY recordset is falsy: test the model, not `Cfg` (P5b probe bug, ledger NH75)
    readers[c.id] = bool(Cfg is not None and Cfg.with_company(c).get_config_for_purpose('doc_ocr'))
print('PROBE bundle files', len(b.javascripts),
      'pb_new_hire installed', bool(installed),
      'studio', 'pb_new_hire_studio' in js,
      'takeover', 'NewHireDoor' in js,
      'old window', 'add("pb_onboard_wizard", OnboardWizard)' in js,
      'step 2 line', 'Team and country needed' in js,
      'learn replica', 'rep-newemp-team' in js,
      'reader per company', readers,
      'langs', ' '.join(env['res.lang'].sudo().search([('active', '=', True)]).mapped('code')))
env.cr.rollback()
