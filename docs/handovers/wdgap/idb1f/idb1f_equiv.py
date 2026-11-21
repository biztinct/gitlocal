# WDGAP IDB1-F probe inside `odoo-bin shell`: for EVERY active internal login that may open
# Pay & deliver, press "Prepare" on the bank file and on the payment list of a finished pay run
# (inside savepoints) and compare: is either refused for ACCESS? They must agree.
# Everything is rolled back; e-mail sending stubbed; files kept in the database (never the
# file folder, IDB1M-4). Prints EQ lines, counts only (QA Test named on payobook).
import os
import re
from unittest.mock import patch

import odoo.modules.module as odoo_module
from odoo.exceptions import AccessError, UserError

env.cr.rollback()  # noqa: F821
SENT = []
s1 = patch.object(type(env['ir.mail_server']), 'send_email',  # noqa: F821
                  lambda self, *a, **k: SENT.append(1) or 'stubbed')
s2 = patch.object(type(env['ir.attachment']), '_storage', lambda self: 'db')  # noqa: F821
s1.start(); s2.start()
odoo_module.current_test = 'idb1f-equiv'


def p(*a):
    print('EQ ' + ' '.join(str(x) for x in a), flush=True)


def attempt(call):
    try:
        with env.cr.savepoint():  # noqa: F821
            call()
        return 'ok'
    except AccessError:
        return 'access'
    except UserError as e:
        return 'other:' + re.sub(r'\d{5,}', '<n>', re.sub(r'\s+', ' ', str(e)))[:70]
    finally:
        env.invalidate_all()  # noqa: F821


try:
    S = env(user=1, su=True)  # noqa: F821
    users = S['res.users'].search([('active', '=', True), ('share', '=', False)])
    Mixin = S['pb.money.approval.mixin']
    gated = users.filtered(lambda u: Mixin._pay_groups_held(u))
    want = int(os.environ.get('EQ_RUN') or 0)
    stats = {'internal': len(users), 'may_open_pay_and_deliver': len(gated), 'checked': 0,
             'agree': 0, 'DISAGREE': 0, 'both_ok': 0, 'both_refused_access': 0, 'other': 0}
    for u in gated:
        cids = [u.company_id.id] + [c for c in u.company_ids.ids if c != u.company_id.id]
        run = S['hr.payslip.run'].browse(want).exists() if want else S['hr.payslip.run']
        if not run:
            run = S['hr.payslip.run'].search([('state', '=', 'done'), ('slip_ids.company_id', 'in', cids)],
                                             order='id desc', limit=1)
        if not run:
            continue
        Pd = env['pb.pay.delivery'].with_user(u).with_context(dict(env.context, allowed_company_ids=cids))  # noqa: F821
        bank = attempt(lambda: Pd.prepare_bank_file(run.id, 'vietcombank'))
        listed = attempt(lambda: Pd.prepare_payment_list(run.id))
        stats['checked'] += 1
        same = (bank == 'access') == (listed == 'access')
        stats['agree' if same else 'DISAGREE'] += 1
        if bank == listed == 'ok':
            stats['both_ok'] += 1
        elif bank == listed == 'access':
            stats['both_refused_access'] += 1
        else:
            stats['other'] += 1
        who = 'QA Test' if (env.cr.dbname == 'payobook' and u.id == 6672) else 'a login'  # noqa: F821
        if not same or who == 'QA Test' or (bank != 'ok' or listed != 'ok'):
            p('%s | run %s | bank file: %s | payment list: %s' % (who, run.id, bank, listed))
    p(env.cr.dbname, stats, '| e-mails tried (stopped):', len(SENT))  # noqa: F821
finally:
    odoo_module.current_test = None
    s2.stop(); s1.stop()
    env.cr.rollback()  # noqa: F821
    print('EQ rolled back', flush=True)
