"""Send the approved reset template once per validated roster user.
Run after provision.py with APPLY=1 and a private JSONL LEDGER_PATH. Existing
internal users stay held unless explicitly listed in KEEP_INTERNAL_EMAILS.
An unfinished 'sending' ledger row requires manual SMTP-log review, not retry.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

assert env.cr.dbname == 'rize'
report = json.loads(Path(os.environ['REPORT_JSON']).read_text())
assert report['applied']
ledger = Path(os.environ['LEDGER_PATH'])
keep = set(filter(None, os.getenv('KEEP_INTERNAL_EMAILS', '').lower().split(',')))
assert keep <= {r['email'] for r in report['records']}
prior = [json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
last = {r['email']: r for r in prior}
actor = env['res.users'].search([('login', '=', 'ash@biztinct.com')])
assert len(actor) == 1 and actor.has_group('base.group_system')
company = env['res.company'].browse(1)
template = company.pb_reset_password_template_id
assert template == env.ref('pb_settings.rize_reset_password_email')
assert company.email == 'support@payobook.com' and company.pb_outgoing_mail_server_id.active

def log(row):
    row['at_utc'] = datetime.now(timezone.utc).isoformat()
    with ledger.open('a') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    ledger.chmod(0o600)

for row in report['records']:
    email = row['email']
    user = env['res.users'].browse(row['user_id']).exists()
    emp = env['hr.employee'].browse(row['employee_id']).exists()
    assert user and emp and emp.user_id == user
    assert user.active and user.company_id == company and user.email.lower() == email and user.login.lower() == email
    if row['action'].startswith('held_') and email not in keep:
        print('HELD', email, flush=True)
        continue
    if email not in keep:
        assert user.share and user._pb_portal_only() and not user._is_internal()
    else:
        assert not user.share  # Explicitly approved retention of existing HR/payroll access.
    key = 'pb.operations.vn_initial_testing_20261120.reset_sent.%s' % user.id
    if env['ir.config_parameter'].sudo().get_param(key) or last.get(email, {}).get('status') == 'sent':
        print('ALREADY_SENT', email, flush=True)
        continue
    assert last.get(email, {}).get('status') != 'sending', ('Review uncertain SMTP outcome before retry', email)
    subject = template._render_field('subject', user.ids)[user.id]
    assert subject == 'Rize HRMS - Password reset'
    log({'email': email, 'user_id': user.id, 'status': 'sending'})
    try:
        user.with_user(actor).with_context(create_user=False).action_reset_password()
        env['ir.config_parameter'].sudo().set_param(key, datetime.now(timezone.utc).isoformat())
        env.cr.commit()
    except Exception as exc:
        env.cr.rollback()
        log({'email': email, 'user_id': user.id, 'status': 'review_required', 'error_type': type(exc).__name__})
        raise
    log({'email': email, 'user_id': user.id, 'status': 'sent', 'subject': subject, 'portal_only': user.share})
    print('SENT', email, flush=True)
