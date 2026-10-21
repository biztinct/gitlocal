# -*- coding: utf-8 -*-
"""LEARNING L2 — demo required training on payobook (handover §6). Idempotent.

Run with the service stopped, on payobook ONLY:

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < l2_demo_seed.py

What it does (every new record named "DEMO …" and put on the demo register):
  1. Safety groups on demo employees of the demo company (5): group 3 / 4 for
     up to 20 people in Manufacturing and Construction, group 2 for two Safety
     Officers, group 1 for two managers (people others report to).
  2. "DEMO Field safety basics" — hold at all times, valid 12 months, course
     27, Manufacturing and everything under it. Assign-by-itself OFF.
  3. "DEMO Forklift licence" — a licence whose name contains "Forklift", for the
     plant; files one DEMO forklift licence with about 20 days left on the first
     plant worker (→ an expiring cell).
  4. "DEMO Induction" — within 30 days of joining, course 27, for the
     departments of the two L1 demo joiners (20208, 20209) → not due yet.
  5. Switches the Vietnam pack on for the demo company and links its group-4
     rule to course 27 (still assign-by-hand), so the matrix shows all five
     cell states.
  6. Runs the morning job ONCE INSIDE A SAVEPOINT THAT IS ROLLED BACK and
     prints its counts (no rule is auto-assign, so it should put 0 required
     courses on anybody).
Nothing here contains a password or a real person's data.
"""
import base64
from datetime import timedelta

from odoo import fields

PDF = base64.b64decode(
    b'JVBERi0xLjQKMSAwIG9iajw8L1R5cGUvQ2F0YWxvZy9QYWdlcyAyIDAgUj4+ZW5kb2JqCjIg'
    b'MCBvYmo8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PmVuZG9iagozIDAgb2Jq'
    b'PDwvVHlwZS9QYWdlL1BhcmVudCAyIDAgUi9NZWRpYUJveFswIDAgMjAwIDIwMF0+PmVuZG9i'
    b'agp0cmFpbGVyPDwvUm9vdCAxIDAgUj4+CiUlRU9GCg==')

COMPANY_ID = 5
COURSE_ID = 27
JOINERS = (20208, 20209)
LABEL = 'DEMO Learning L2 required training'


def say(msg, *args):
    print('L2 SEED | ' + (msg % args if args else msg))


env = env  # noqa: F821 — provided by `odoo-bin shell`
today = fields.Date.today()
seed = env.get('pb.demo.seed')
company = env['res.company'].browse(COMPANY_ID).exists() or env.company
Emp = env['hr.employee'].sudo()
Req = env['pb.training.requirement'].sudo().with_context(active_test=False)
course = env['slide.channel'].sudo().browse(COURSE_ID).exists()
say('company %s "%s"; course %s', company.id, company.name,
    course and '%s "%s"' % (course.id, course.name) or 'NOT FOUND')

# ---------------------------------------------------------------- 1. groups
Dept = env['hr.department'].sudo()
plant = Dept.search([('company_id', '=', company.id),
                     ('name', 'in', ('Manufacturing', 'Construction'))])
# Company 5 is the demo company: its people are the demo world (their names
# carry no "DEMO" prefix), so the plant departments are the filter.
workers = Emp.search([('company_id', '=', company.id),
                      ('department_id', 'child_of', plant.ids)],
                     order='id', limit=20) if plant else Emp.browse()
for i, emp in enumerate(workers):
    if not emp.pb_safety_group:
        emp.pb_safety_group = '3' if i % 3 == 0 else '4'
officers = Emp.search([('company_id', '=', company.id),
                       ('job_id.name', '=', 'Safety Officer')], limit=2)
officers.filtered(lambda e: not e.pb_safety_group).write(
    {'pb_safety_group': '2'})
bosses = Emp.search([('company_id', '=', company.id),
                     ('child_ids', '!=', False)], limit=2)
bosses.filtered(lambda e: not e.pb_safety_group).write(
    {'pb_safety_group': '1'})
say('safety groups: %s workers (3/4), %s officers (2), %s managers (1)',
    len(workers), len(officers), len(bosses))


# ---------------------------------------------------------------- 2-4. rules
def rule(code, vals):
    found = Req.search([('company_id', '=', company.id), ('code', '=', code)],
                       limit=1)
    if found:
        say('rule %s already there (%s)', code, found.id)
        return found, False
    base = {'code': code, 'company_id': company.id, 'auto_assign': False}
    base.update(vals)
    made = Req.create(base)
    say('rule %s made (%s): %s', code, made.id, made.name)
    return made, True


made = Req.browse()
manufacturing = Dept.search([('company_id', '=', company.id),
                             ('name', '=', 'Manufacturing')], limit=1)
if course:
    r, new = rule('demo_field_safety', {
        'name': 'DEMO Field safety basics', 'kind': 'always',
        'target': 'course', 'channel_id': course.id, 'validity_months': 12,
        'department_ids': [(6, 0, manufacturing.ids)],
    })
    made |= r if new else Req.browse()
lic = env.ref('pb_training.cat_licence', raise_if_not_found=False)
joiners = Emp.browse(JOINERS).exists()
# The plant AND the L1 demo joiners' departments: L1's forklift licence
# (document 162, about 20 days left) belongs to a joiner, which is what
# gives the matrix its "expiring" cell.
forklift_depts = plant | joiners.mapped('department_id')
r, new = rule('demo_forklift', {
    'name': 'DEMO Forklift licence', 'kind': 'always', 'target': 'licence',
    'name_pattern': 'Forklift', 'document_category_id': lic.id if lic else False,
    'department_ids': [(6, 0, forklift_depts.ids)],
})
if not new and r.department_ids != forklift_depts:
    r.department_ids = [(6, 0, forklift_depts.ids)]
    say('rule demo_forklift now also covers the joiners\' departments')
made |= r if new else Req.browse()
# An "expiring" cell: one DEMO forklift licence with about 20 days left for
# the first plant worker (L1's licence holder has no department, so no
# department rule reaches her). Filed through the register's own door.
docs = env['pb.employee.document'].sudo()
if workers and not docs.search_count([('employee_id', '=', workers[0].id),
                                      ('name', '=', 'DEMO Forklift operator licence')]):
    doc = env['pb.training.certificate'].sudo()._create_upload(workers[0], {
        'name': 'DEMO Forklift operator licence', 'kind': 'LIC',
        'issuer': 'DEMO Training Authority', 'reference': 'DEMO-L2-1',
        'issue_date': fields.Date.to_string(today - timedelta(days=345)),
        'expiry_date': fields.Date.to_string(today + timedelta(days=20)),
    }, ('DEMO Forklift operator licence.pdf', PDF), 'statutory')
    doc._pb_training_verify()
    if seed is not None:
        seed.register(doc.attachment_id, LABEL, last=True)
        seed.register(doc, LABEL)
    say('filed DEMO Forklift operator licence on %s (document %s): %s',
        workers[0].name, doc.id, doc.valid_words)
if course and joiners:
    r, new = rule('demo_induction', {
        'name': 'DEMO Induction', 'kind': 'day_one', 'target': 'course',
        'channel_id': course.id, 'due_days': 30,
        'department_ids': [(6, 0, joiners.mapped('department_id').ids)],
    })
    made |= r if new else Req.browse()

# ---------------------------------------------------------------- 5. VN pack
before = Req.search([('company_id', '=', company.id),
                     ('pack_key', '=', 'vn_osh')])
res = Req._switch_pack('vn', company, True)
copies = Req.search([('company_id', '=', company.id),
                     ('pack_key', '=', 'vn_osh')])
say('Vietnam pack on: %s', res)
g4 = copies.filtered(lambda c: c.code == 'vn_osh_g4')
if g4 and course and not g4.channel_id:
    g4.channel_id = course.id
    say('vn_osh_g4 now linked to course %s (assign by hand)', course.id)
made |= copies - before

if made and seed is not None:
    seed.register(made, LABEL)
    say('registered %s rule(s) on the demo register', len(made))
env.cr.commit()

# ---------------------------------------------------------------- summary
data = env['pb.training'].with_company(company).with_context(
    allowed_company_ids=[company.id])._matrix_data({}, paged=False)
say('matrix: %s', data['headline'])
say('cells: %s', {k: data['summary'].get(k) for k in (
    'valid', 'expiring', 'missing', 'in_progress', 'not_due')})

# ---------------------------------------------------------------- 6. test mode
Auto = env['pb.training.automation'].sudo()
try:
    with env.cr.savepoint():
        say('morning job, test mode: %s', Auto._cron_daily())
        raise RuntimeError('roll back the test run')
except RuntimeError:
    say('test run rolled back: no email queued, no assignment kept')
