"""Remove known Rize review copies from the demo DB; dry-run unless approved.

Run in the payobook Odoo shell. Rize client data belongs only in the rize DB.
The original client configurations and records in rize are never touched.
"""
import base64
import json
import os
from pathlib import Path

assert env.cr.dbname == 'payobook'
apply = os.getenv('RIZE_CLEANUP_APPLY') == '1'
expected = {602: 'RIZE_ID_202608_REVIEW', 613: 'RIZE_SINGAPORE_AUGUST_2026_I'}
Config = env['hr.formula.config'].sudo()
configs = Config.browse(list(expected)).exists()
assert all(expected[c.id] == c.code and c.state == 'draft' for c in configs)
assert not Config.search([('code', 'ilike', 'RIZE')]) - configs, 'Unexpected Rize configuration needs review'
for cfg in configs:
    assert not cfg._delete_blockers(), (cfg.id, cfg._delete_blockers())
models = ['hr.employee', 'hr.contract', 'hr.payslip', 'hr.payslip.run']
before = {m: env[m].sudo().with_context(active_test=False).search_count([]) for m in models}
attachments = env['ir.attachment'].sudo().search([
    ('res_model', '=', 'hr.formula.config'), ('res_id', 'in', configs.ids)])
# An older masked client payslip was also copied into a demo recruitment test.
masked = env['ir.attachment'].sudo().browse(217105).exists()
if masked:
    assert masked.name == 'Rize SGP-Payslip-Masked.pdf' and masked.res_model == 'hr.applicant'
attachments |= masked
backup = Path(os.environ['RIZE_CLEANUP_BACKUP'])
backup.mkdir(mode=0o700, parents=True, exist_ok=True)
receipt = {'database': env.cr.dbname, 'applied': apply,
           'removed_configuration_ids': configs.ids, 'removed_attachment_ids': attachments.ids,
           'before': before, 'configurations': configs.read(['name', 'code', 'state', 'company_id'])}
(backup / 'review-copy-removal.json').write_text(json.dumps(receipt, default=str, indent=2))
(backup / 'review-copy-removal.json').chmod(0o600)
for a in attachments:
    if a.datas:
        p = backup / ('attachment-%s.bin' % a.id)
        p.write_bytes(base64.b64decode(a.datas)); p.chmod(0o600)
attachments.unlink()
configs.unlink()
assert not Config.search([('code', 'ilike', 'RIZE')])
assert before == {m: env[m].sudo().with_context(active_test=False).search_count([]) for m in models}
print('RIZE_COPY_CLEANUP', json.dumps({k: v for k, v in receipt.items() if k != 'configurations'}))
if apply:
    env.cr.commit()
else:
    env.cr.rollback()
