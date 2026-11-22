# Golden script (A1 rail R1): render the two shipped offer letters and the two
# shipped certificates (en / vi / id) exactly as the product does, print md5s.
# Run in `odoo-bin shell` BEFORE and AFTER installing the A1 bridges; the
# output must be identical. Everything is rolled back.
import hashlib
import json
import re
from datetime import timedelta

from odoo import fields
from odoo.tools import config

config['test_enable'] = True          # reports render as HTML (no PDF engine here)

out = {}


def md5(s):
    return hashlib.md5((s or '').encode()).hexdigest()


def norm_pdf(raw, *refs):
    text = raw.decode('utf-8', 'ignore') if isinstance(raw, bytes) else str(raw)
    text = re.sub(r'<link[^>]*/web/assets/[^>]*>', '', text)
    text = re.sub(r'<script[^>]*/web/assets/[^>]*></script>', '', text)
    text = re.sub(r'data-oe-id="\d+"', 'data-oe-id="N"', text)
    for ref in refs:
        if ref:
            text = text.replace(ref, 'REF')
    return text


cr = env.cr
cr.execute('SAVEPOINT golden')
try:
    company = env.company
    company.country_id = env.ref('base.vn')
    Emp = env['hr.employee']
    boss = Emp.create({'name': 'DEMO GOLD Boss', 'company_id': company.id})
    dept = env['hr.department'].create({'name': 'DEMO GOLD Dept', 'company_id': company.id})
    job = env['hr.job'].create({'name': 'DEMO GOLD Role', 'company_id': company.id,
                                'department_id': dept.id})
    app = env['hr.applicant'].create({'partner_name': 'DEMO GOLD Candidate',
                                      'email_from': 'demo.gold@example.com',
                                      'job_id': job.id, 'company_id': company.id})
    req = env['pb.hiring.requisition'].sudo().create({
        'title': 'DEMO GOLD Role', 'department_id': dept.id, 'company_id': company.id,
        'requested_by_id': boss.id, 'reporting_manager_id': boss.id, 'headcount': 1,
        'budget_cost': 100.0, 'requirements': 'x', 'job_id': job.id, 'state': 'open',
        'request_state': 'agreed', 'selected_applicant_id': app.id,
        'location': 'DEMO Ha Noi', 'opened_on': fields.Date.today() - timedelta(days=3)})
    app.sudo().write({'pb_requisition_id': req.id})
    bgv = env['pb.hiring.bgv'].open_for(req.id)
    bgv.item_ids.sudo().write({'result': 'ok'})
    offer = env['pb.hiring.offer'].draft_for(req.id)
    for name, kind, amount, period in (('Basic pay', 'earning', 25000000.0, 'monthly'),
                                       ('Allowance', 'earning', 2000000.0, 'monthly'),
                                       ('Sign-on bonus', 'bonus', 10000000.0, 'one_time')):
        offer.action_add_line({'name': name, 'kind': kind, 'amount': amount, 'period': period})
    offer.invalidate_recordset(['monthly_total', 'annual_total'])
    for xmlid in ('pb_hiring.letter_template_offer_generic', 'pb_hiring.letter_template_offer_vietnam'):
        tmpl = env.ref(xmlid)
        offer.sudo().write({'letter_template_id': tmpl.id})
        offer.action_prepare_letter()
        out[xmlid + ' html'] = md5(str(offer.rendered_html))
        out[xmlid + ' pdf'] = md5(norm_pdf(offer.attachment_id.raw, offer.name))
        out[xmlid + ' pdfname'] = offer.attachment_id.name
    # certificates
    Users = env['res.users'].with_context(no_reset_password=True)
    portal = Users.create({'name': 'DEMO GOLD Portal', 'login': 'demo_gold_portal',
                           'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
                           'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
    emp = Emp.create({'name': 'DEMO GOLD Person', 'company_id': company.id, 'user_id': portal.id,
                      'job_id': job.id, 'job_title': 'DEMO GOLD Planner', 'department_id': dept.id})
    env['hr.contract'].create({'name': 'DEMO GOLD contract', 'employee_id': emp.id,
                               'wage': 25000000.0, 'state': 'open', 'date_start': '2025-03-01'})
    Cert = env['pb.me.certificate']
    for lang in ('en_US', 'vi_VN', 'id_ID'):
        cert = Cert.with_user(portal).pb_portal_request(emp, 'employment', 'bank', lang=lang, note='DEMO bank')
        letter = cert.sudo().letter_id
        html = str(letter.rendered_html).replace(cert.name, 'REF')
        out['employment %s html' % lang] = md5(html)
        out['employment %s subject' % lang] = (letter.subject or '').replace(cert.name, 'REF')
        out['employment %s pdf' % lang] = md5(norm_pdf(letter.attachment_id.raw, cert.name))
        out['employment %s ctx' % lang] = md5(json.dumps(json.loads(letter.context_json or '{}'), sort_keys=True).replace(cert.name, 'REF'))
    # salary certificate issued directly (the approval click calls _pb_issue)
    for lang in ('en_US', 'vi_VN', 'id_ID'):
        cert = Cert.sudo().create({'employee_id': emp.id, 'company_id': company.id,
                                   'kind': 'salary', 'purpose': 'visa', 'lang': lang})
        letter = cert._pb_issue()
        html = str(letter.rendered_html).replace(cert.name, 'REF')
        out['salary %s html' % lang] = md5(html)
        out['salary %s subject' % lang] = (letter.subject or '').replace(cert.name, 'REF')
    # template rows
    cr.execute("SELECT t.id, md5(t.name::text), md5(coalesce(t.subject::text,'')), md5(t.body_html::text) "
               "FROM pb_letter_template t WHERE letter_type IN ('offer','employment_cert','salary_cert') ORDER BY id")
    out['template rows'] = md5(json.dumps(cr.fetchall()))
finally:
    cr.execute('ROLLBACK TO SAVEPOINT golden')
    cr.rollback()

for k in sorted(out):
    print('GOLDEN', k, out[k])
