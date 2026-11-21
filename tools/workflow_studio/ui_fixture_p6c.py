"""WF2 P6c browser fixture — LOCAL DISPOSABLE DATABASES ONLY (wf2p6c*).

    P6C_FIXTURE_FILE=/outside/the/repo/p6c.json \
    odoo-bin shell -d wf2p6c_ui --no-http < tools/workflow_studio/ui_fixture_p6c.py

Three employee-home (portal) logins — English, Vietnamese, Indonesian — each
with one time-off request (half day, morning) that their manager SENT BACK
through the approval route with a reason in their language, plus one more
sent-back request for the English employee that staff "ask again" from the
Time off cockpit. Three staff logins (one per language) with the time-off
officer role look at the cockpit. Nothing is sent: outgoing mail is queued
only (local database). Passwords are random and written only to a 0600 file
outside the repo (path printed).
"""
import json
import os
import secrets
from datetime import date, timedelta
from pathlib import Path

assert env.cr.dbname.startswith('wf2p6c'), 'Local disposable databases only.'
out = Path(os.environ['P6C_FIXTURE_FILE'])
from odoo.modules.module import get_module_path
_repo = Path(get_module_path('pb_timeoff')).resolve().parent
assert _repo not in out.resolve().parents, 'The fixture file must live outside the repo.'
company = env.company
password = secrets.token_urlsafe(18)
Users = env['res.users'].with_context(no_reset_password=True)


def login(name, key, groups, lang):
    found = Users.search([('login', '=', key)], limit=1)
    vals = {'name': name, 'login': key, 'password': password,
            'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
            'lang': lang, 'tz': 'Asia/Ho_Chi_Minh',
            'group_ids': [(6, 0, [env.ref(g).id for g in groups])]}
    if found:
        found.write(vals)
        return found
    return Users.create(vals)


# employee-home pages follow the login's language only for a language the
# website offers (ledger G82): offer the two the proof is in
langs = env['res.lang'].search([('code', 'in', ('vi_VN', 'id_ID'))])
env['website'].sudo().search([]).write(
    {'language_ids': [(4, lang.id) for lang in langs]})

Employee = env['hr.employee']
boss_user = login('Minh Tran', 'p6c.boss', ['base.group_user'], 'en_US')
boss = Employee.search([('user_id', '=', boss_user.id)], limit=1) or Employee.create(
    {'name': 'Minh Tran', 'user_id': boss_user.id, 'company_id': company.id})
staff = {lang: login('Linh Pham (%s)' % tag, 'p6c.hr.%s' % tag,
                     ['base.group_user', 'hr_holidays.group_hr_holidays_manager',
                      'hr.group_hr_manager'], lang)
         for lang, tag in (('en_US', 'en'), ('vi_VN', 'vi'), ('id_ID', 'id'))}

# the company runs time off through the approval engine (manager first)
env['hr.leave']._approval_seed_default(company)

Type = env['hr.leave.type'].sudo()
kind = Type.search([('name', '=', 'P6c Annual leave')], limit=1) or Type.create({
    'name': 'P6c Annual leave', 'requires_allocation': True,
    'leave_validation_type': 'manager', 'request_unit': 'half_day',
    'allocation_validation_type': 'hr', 'company_id': company.id})
kind.with_context(lang='en_US').name = 'Annual leave'
kind.with_context(lang='vi_VN').name = 'Nghỉ phép năm'
kind.with_context(lang='id_ID').name = 'Cuti tahunan'

PEOPLE = [
    ('en_US', 'Amy Nguyen', 'p6c.amy',
     'Please take the afternoon instead — the client visit is in the morning.'),
    ('vi_VN', 'Lan Hoàng', 'p6c.lan',
     'Vui lòng chọn buổi chiều — buổi sáng có cuộc họp với khách hàng.'),
    ('id_ID', 'Sari Wijaya', 'p6c.sari',
     'Mohon ambil siang hari saja — pagi ada kunjungan klien.'),
]
anchor = date.today() + timedelta(days=21)
monday = anchor - timedelta(days=anchor.weekday())
result = {'database': env.cr.dbname, 'password': password,
          'staff': {k: u.login for k, u in staff.items()}, 'people': {}}
engine = env['biz.approval.engine']


def send_back(leave, reason):
    leave = leave.sudo()
    request = leave.approval_request_id
    assert request, 'the request went to the route'
    step = request.step_ids.filtered(lambda s: s.status == 'active')
    engine.with_user(boss_user).decide(request.id, step.key, 'return',
                                       reason=reason)
    env.invalidate_all()
    assert leave.state == 'refuse' and leave.pb_sent_back
    return leave


for n, (lang, name, key, reason) in enumerate(PEOPLE):
    person = login(name, key, ['base.group_portal'], lang)
    emp = Employee.search([('user_id', '=', person.id)], limit=1) or Employee.create({
        'name': name, 'user_id': person.id, 'company_id': company.id,
        'work_email': '%s@example.invalid' % key, 'parent_id': boss.id,
        'leave_manager_id': boss_user.id})
    alloc = env['hr.leave.allocation'].sudo().create({
        'name': 'P6c grant', 'employee_id': emp.id, 'holiday_status_id': kind.id,
        'number_of_days': 12, 'allocation_type': 'regular',
        'date_from': date.today() - timedelta(days=30)})
    alloc.action_approve()
    day = monday + timedelta(days=n)
    res = env['pb.ess.workforce'].with_user(person).with_context(lang=lang).apply_leave(
        kind.id, day.isoformat(), day.isoformat(), 'Family visit',
        period_from='am')
    leave = send_back(env['hr.leave'].browse(res['id']), reason)
    row = {'login': key, 'lang': lang, 'employee_id': emp.id,
           'leave_id': leave.id, 'day': day.isoformat()}
    if lang == 'en_US':
        # one more, for staff to "ask again" from the cockpit
        day2 = monday + timedelta(days=7)
        res = env['pb.ess.workforce'].with_user(person).apply_leave(
            kind.id, day2.isoformat(), (day2 + timedelta(days=1)).isoformat(),
            'Wedding')
        staff_leave = send_back(env['hr.leave'].browse(res['id']),
                                'Two days is fine, but say whose wedding it is.')
        row['staff_leave_id'] = staff_leave.id
    result['people'][lang] = row
env.cr.commit()
out.write_text(json.dumps(result, ensure_ascii=False))
os.chmod(out, 0o600)
print('P6C_FIXTURE', out)
