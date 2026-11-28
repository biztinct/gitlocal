# NEWHIRE P8 (odoo-bin shell, read-only, rolled back): the compiled code of this database carries the
# release. Clone of ../p6/nh6_bundle.py.
#   country first   step 2's country-first code (pickCountry, places)
#   bank boxes      step 5's bank row follows the account's country (bankFormatOf)
#   verification    the Bank Verification screen's "Bank account in" (pbbk-format)
#   my payobook     the frontend script that shapes the codes
#   learn           the replica draws Country of work above Team
b = env['ir.qweb']._get_asset_bundle('web.assets_web', css=False, js=True)
js = ''.join(a.content for a in b.javascripts)
f = env['ir.qweb']._get_asset_bundle('web.assets_frontend', css=False, js=True)
fjs = ''.join(a.content for a in f.javascripts)
print('PROBE bundle files', len(b.javascripts),
      'country first', 'pickCountry' in js and '"places"' in js,
      'bank boxes', 'bankFormatOf' in js,
      'verification', 'canEditFormat' in js,
      'my payobook', 'data-pbmd-code' in fjs,
      'learn replica', 'the money of the country of work' in js,
      'old window', 'add("pb_onboard_wizard", OnboardWizard)' in js,
      'langs', ' '.join(env['res.lang'].sudo().search([('active', '=', True)]).mapped('code')))
env.cr.rollback()
