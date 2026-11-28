"""Read-only post-deployment verification, executed by odoo shell in each database."""
import json
from odoo.addons.pb_workforce_workspace.models.workspace import CATALOGS
out={'database':env.cr.dbname,'preferences':env['pb.workforce.workspace'].preferences(),'catalogs':{}}
for key,(model,_,_) in CATALOGS.items():
 if model not in env:continue
 d=env['pb.workforce.workspace'].catalog(key)
 assert len(d['rows'])<=40
 assert d['total']>=len(d['rows'])
 out['catalogs'][key]={'total':d['total'],'fields':list(d['fields'])}
out['overview']=env['pb.workforce.workspace'].overview('2026-11-23')
assert len(out['overview']['steps'])==6
b=env['ir.qweb']._get_asset_bundle('web.assets_backend');b.css();b.js();assert not b.css_errors,b.css_errors
out['assets']=True
if env.cr.dbname!='sudima':assert not env['res.company'].search([('pb_workforce_workspace_enabled','=',True)])
print('WORKFORCE_VERIFIED='+json.dumps(out,default=str))
env.cr.rollback()
