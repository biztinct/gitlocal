# COPY ONLY: run the approvals "tell people" job once, as the live server's job
# would within a minute of the batch, and count what it produces.
import json
from collections import Counter
DB = env.cr.dbname  # noqa: F821
assert DB.startswith('bg1w3c_'), DB
cr = env.cr  # noqa: F821


def n(t):
    cr.execute('select count(*) from %s' % t)
    return cr.fetchone()[0]


tables = ('mail_mail', 'mail_activity', 'mail_notification', 'mail_message')
before = {t: n(t) for t in tables}
cr.execute("select max(id) from mail_activity")
act0 = cr.fetchone()[0] or 0
env['biz.approval.outbox']._cron_deliver(limit=100000)  # noqa: F821
env.invalidate_all()  # noqa: F821
after = {t: n(t) for t in tables}
acts = env['mail.activity'].sudo().search([('id', '>', act0)])  # noqa: F821
per_user = Counter(a.user_id.login for a in acts)  # not mapped(): it de-duplicates
cr.execute("select state, count(*) from mail_mail group by state")
mm = cr.fetchall()
cr.execute("select state, count(*) from biz_approval_outbox group by state")
ob = cr.fetchall()
out = {'delta': {t: after[t] - before[t] for t in tables},
       'new_todos_per_user': dict(per_user), 'mail_mail_states': mm,
       'outbox_states': ob}
print(json.dumps(out, indent=1, default=str))
json.dump(out, open('/tmp/bg1w3c/%s-deliver.json' % DB, 'w'), indent=1, default=str)
cr.commit()
