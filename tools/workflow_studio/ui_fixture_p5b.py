"""WF2 P5b browser fixture — LOCAL DISPOSABLE DATABASES ONLY (am_wf2p5b*).

    P5B_LANG=vi_VN odoo-bin shell -d am_wf2p5b_ui --no-http < tools/workflow_studio/ui_fixture_p5b.py

First run: builds P5c's fixture (designer, checker, employee-home login, the
receipts workflow with three lines, six lines, a home claim) plus one step for
someone with no login (the link email and the link page), and offers
Vietnamese and Indonesian on the local website. Every run: sets the three
logins and the no-login contact to P5B_LANG, so the same fixture is shot in
each language. Passwords are random, written only to a 0600 file outside the
repo; nothing is committed.
"""
import json
import os
import uuid
from pathlib import Path

from odoo.addons.pb_lifecycle.models import workflow_definition as D

assert env.cr.dbname.startswith('am_wf2p5b'), 'Local disposable databases only.'
lang = os.environ.get('P5B_LANG') or 'en_US'
out = Path(os.environ.get('P5B_FIXTURE_FILE') or '/tmp/wf2p5b-ui-%s.json' % env.cr.dbname)
fx = json.loads(out.read_text()) if out.exists() else None
if not fx:
    source = open(os.path.join(os.path.dirname(os.path.abspath('tools/workflow_studio/ui_fixture_p5c.py')),
                               'ui_fixture_p5c.py'), encoding='utf-8').read()
    source = source.replace("assert env.cr.dbname.startswith('am_wf2p5c')", "assert env.cr.dbname.startswith('am_wf2p5b')")
    os.environ['P5C_FIXTURE_FILE'] = str(out)
    exec(compile(source, 'ui_fixture_p5c.py', 'exec'), {'env': env, '__name__': '__fixture__'})
    fx = json.loads(out.read_text())
    company = env.company
    designer = env['res.users'].search([('login', '=', fx['designer'])])
    service = env['pb.workflow.studio'].with_user(designer).with_company(company)
    # someone with no login: an employee with only a work email
    outsider = env['hr.employee'].create({'name': 'P5b Outsider', 'company_id': company.id,
                                          'work_email': 'p5b.outsider@example.invalid'})
    env['res.partner'].create({'name': 'P5b Outsider', 'email': 'p5b.outsider@example.invalid'})
    product = env['product.product'].search([('name', '=', 'P5c Taxi')], limit=1)
    claim = env['pb.expense.claim'].create({'employee_id': outsider.id, 'company_id': company.id})
    env['hr.expense'].create({'name': 'Bus', 'employee_id': outsider.id, 'product_id': product.id,
                              'total_amount_currency': 12.0, 'company_id': company.id, 'pb_claim_id': claim.id})
    row = service.create_workflow('P5b confirm by link', 'pb.expense.claim', 'Expenses')
    w = env['pb.workflow'].browse(row['id'])
    d = D.fresh(w.name)
    d['nodes'] += [{'id': 'own', 'type': 'confirm', 'title': 'Confirm the bus ticket is yours', 'stage': 0,
                    'owner': {'kind': 'subject'}, 'due': 2, 'text': 'I paid this myself.'}]
    d['order'] += ['own']
    service.save_draft(w.id, w.revision, d)
    service.publish(w.id, w.revision)
    service.activate(w.id, True, acknowledge_existing=True)
    run = env['pb.workflow.run'].browse(service.start(w.id, claim.id, str(uuid.uuid4()))['run_id'])
    fx.update(link_run_id=run.id, link_claim_id=claim.id)
    site = env['website'].search([], limit=1)
    site.language_ids |= env['res.lang'].search([('code', 'in', ['vi_VN', 'id_ID'])])
    out.write_text(json.dumps(fx))
    os.chmod(out, 0o600)

Users = env['res.users']
for login in (fx['designer'], fx['checker'], fx['home']):
    Users.search([('login', '=', login)]).lang = lang
env['res.partner'].search([('email', '=', 'p5b.outsider@example.invalid')]).lang = lang
# a fresh link in this language (the old one stops working), and its email
run = env['pb.workflow.run'].browse(fx['link_run_id'])
step = run.step_ids.filtered(lambda s: s.key == 'own')
studio = env['pb.workflow.studio'].sudo()
studio._send_link(run, step, step.link_email or 'p5b.outsider@example.invalid', step.link_name or 'P5b Outsider')
mail = env['mail.mail'].sudo().search([('email_to', '=', 'p5b.outsider@example.invalid')], order='id desc', limit=1)
fx.update(lang=lang, link_token=step.access_token, link_mail_subject=mail.subject, link_mail_html=mail.body_html,
          link_mail_id=mail.id)
out.write_text(json.dumps(fx))
os.chmod(out, 0o600)
env.cr.commit()
print('P5B_UI_FIXTURE=' + str(out))
