# -*- coding: utf-8 -*-
"""WDGAP IDB1-F part B — demo bank accounts on record (payobook ONLY).

Owner question 3 of the IDB1 deploy report: the demo people have bank-file
numbers (the four Vietnamese bank-file fields) but no bank account on record
(`hr.employee.bank_account_ids`, the store the "Payment list (any bank)"
reads), so every demo payment list says "No bank account on record" for
everyone. This seed ADDS one bank account on record for each active demo
person of the demo Vietnam company who is paid by bank (has a bank-file
number) and has no bank account on record yet:

  * bank   = the bank named in their bank-file fields (Vietcombank, BIDV,
             Agribank, ... — real Vietnamese bank names; the bank is found by
             name, created only when the database has none);
  * number = OBVIOUSLY FAKE: "9999" + the employee's id on 8 digits
             (e.g. 9999 0002 3440) — never a real account, never the person's
             bank-file number;
  * holder = the employee's name.

So the "Check" column has something to show, SIX people of one demo pay run
(the showcase run: "Payroll Manufacturing July 2026", else the latest
approved run of the company) are left deliberately imperfect — picked as the
six lowest employee ids of that run, so a second run picks the same six:

  1, 2  no bank account at all (left out by this seed)
  3     holder name close to, but not the same as, the employee's name
  4     account in another person's name (another demo person's name)
  5, 6  the same account number (6 is given 5's number)

ADD-ONLY AND IDEMPOTENT. A person who already has a bank account on record
(any, archived ones included) is never touched; the bank-file fields are
never written; nothing existing is changed or deleted. A second run makes
nothing. Every record made goes on the demo register ("DEMO HR programme
data", label below) so Settings > Demo data accounts for it.

Rails, inside the script's own transaction (rolled back on any breach):
payslips, pay runs, logins, every mail row, to-dos, active jobs, bank change
requests, approval requests, the bank-file fields (checksum) and every
existing bank account row (checksum) unchanged; employees unchanged; bank
accounts move by exactly what was made. No approval, to-do or email is made.

Run, service UP, on payobook ONLY (refuses any other database except a
local test copy named wdgap_idb1f*):

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < idb1f_demo_bank_seed.py

IDB1F_DRY=1 = everything, print, then roll back. Prints counts only — never
an account number. Nothing here contains a password or a real person's data.
"""
import os

from odoo.addons.pb_bank_ocr.models.vn_bank_dictionary import name_similarity

LABEL = 'DEMO bank accounts on record (WDGAP IDB1-F)'
SHOWCASE_RUN = 'Payroll Manufacturing July 2026'
SCHEME_CODE = 'DEMO_RETAIL_END'      # finds the demo Vietnam company (DM1)
NAME_MATCH, NAME_CLOSE = 85.0, 60.0  # the payment list's own bands
DRY = bool(os.environ.get('IDB1F_DRY'))
CTX = {'tracking_disable': True, 'mail_create_nolog': True,
       'mail_create_nosubscribe': True, 'mail_notrack': True}


def say(msg, *args):
    print('IDB1F SEED | ' + (msg % args if args else msg), flush=True)


def fake_number(emp_id):
    return '9999%08d' % emp_id


env = env  # noqa: F821 — provided by `odoo-bin shell`
db = env.cr.dbname
if db != 'payobook' and not db.startswith('wdgap_idb1f'):
    raise SystemExit('IDB1F SEED | refused: database %r is not payobook' % db)
env.cr.rollback()
env.cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
env = env(context=dict(env.context, **CTX))


def q(sql):
    env.cr.execute(sql)
    return env.cr.fetchone()[0]


def counts():
    return {
        'employees': q('SELECT count(*) FROM hr_employee'),
        'payslips': q('SELECT count(*) FROM hr_payslip'),
        'payslip_runs': q('SELECT count(*) FROM hr_payslip_run'),
        'users': q('SELECT count(*) FROM res_users'),
        'mail_all': q('SELECT count(*) FROM mail_mail'),
        'mail_outgoing': q("SELECT count(*) FROM mail_mail WHERE state = 'outgoing'"),
        'activities': q('SELECT count(*) FROM mail_activity'),
        'crons_active': q("SELECT count(*)||':'||coalesce(string_agg(id::text, ',' ORDER BY id),'') "
                          "FROM ir_cron WHERE active"),
        'bank_changes': q('SELECT count(*) FROM pb_bank_change_request'),
        'approval_requests': q('SELECT count(*) FROM biz_approval_request'),
        'bank_file_fields': q("SELECT md5(coalesce(string_agg(row(id, vietnam_bank_name, "
                              "vietnam_bank_branch, vietnam_bank_account_number, "
                              "vietnam_bank_account_name)::text, ',' ORDER BY id), '')) "
                              "FROM hr_employee"),
        'bank_accounts': q('SELECT count(*) FROM res_partner_bank'),
        'bank_accounts_existing': None,
        'banks': q('SELECT count(*) FROM res_bank'),
        'messages': q('SELECT count(*) FROM mail_message'),
    }


def existing_accounts_sum(max_id):
    return q("SELECT md5(coalesce(string_agg(row(id, partner_id, acc_number, bank_id, "
             "acc_holder_name, active, allow_out_payment)::text, ',' ORDER BY id), '')) "
             "FROM res_partner_bank WHERE id <= %d" % max_id)


before = counts()
max_acc = q('SELECT coalesce(max(id), 0) FROM res_partner_bank')
before['bank_accounts_existing'] = existing_accounts_sum(max_acc)
say('before %s', {k: v for k, v in before.items() if k not in ('bank_file_fields', 'bank_accounts_existing')})

Config = env['hr.formula.config'].sudo()
scheme = Config.search([('code', '=', SCHEME_CODE)], limit=1)
if not scheme:
    raise SystemExit('IDB1F SEED | no %s scheme here — nothing done' % SCHEME_CODE)
company = scheme.company_id
Emp = env['hr.employee'].sudo().with_company(company).with_context(active_test=False)
Run = env['hr.payslip.run'].sudo()
Bank = env['res.bank'].sudo()
Account = env['res.partner.bank'].sudo()

people = Emp.search([('company_id', '=', company.id), ('active', '=', True),
                     ('is_demo', '=', True),
                     ('vietnam_bank_account_number', 'not in', (False, ''))], order='id')
say('company %s (%s): %s active demo people paid by bank', company.id, company.name, len(people))

run = Run.search([('name', '=', SHOWCASE_RUN), ('state', '=', 'done')], limit=1)
if not run:
    run = Run.search([('state', '=', 'done')], order='id desc', limit=1)
run_people = run.slip_ids.filtered(lambda s: s.state == 'done').mapped('employee_id') & people
six = run_people.sorted('id')[:6]
if len(six) < 6:
    raise SystemExit('IDB1F SEED | showcase run %s has fewer than 6 demo people — nothing done' % run.id)
no_account, close_one, other_one, shared_a, shared_b = six[:2], six[2], six[3], six[4], six[5]
say('showcase run %s "%s": %s demo people; imperfect: no account %s, close name %s, '
    'another person %s, shared %s+%s', run.id, run.name, len(run_people), no_account.ids,
    close_one.id, other_one.id, shared_a.id, shared_b.id)


def close_variant(name):
    """A holder name the payment list calls "close to, but not the same"."""
    words = (name or '').split()
    candidates = []
    if len(words) >= 3:
        candidates.append(' '.join(words[:1] + words[2:]))       # middle name left out
    if len(words) >= 2:
        candidates.append(' '.join(words[:-1]))                  # last name left out
        candidates.append(' '.join(words[:-1] + [words[-1][:1]]))
    candidates.append((name or '')[:-2])
    for cand in candidates:
        if NAME_CLOSE <= name_similarity(cand, name) < NAME_MATCH:
            return cand
    return None


close_holder = close_variant(close_one.name)
other_holder = None
for cand in people.sorted('id', reverse=True)[:200]:
    if cand not in run_people and name_similarity(cand.name, other_one.name) < NAME_CLOSE:
        other_holder = cand.name
        break
if not close_holder or not other_holder:
    raise SystemExit('IDB1F SEED | could not make the two holder-name examples — nothing done')

bank_cache = {}
made_banks = Bank.browse()


def bank_for(name):
    global made_banks
    key = (name or '').strip().lower()
    if key not in bank_cache:
        found = Bank.with_context(active_test=False).search([('name', '=ilike', name.strip())], limit=1)
        if not found:
            found = Bank.create({'name': name.strip(),
                                 'country': company.country_id.id or env.ref('base.vn').id})
            made_banks |= found
        bank_cache[key] = found
    return bank_cache[key]


AnyAccount = Account.with_context(active_test=False)
made = Account.browse()
skipped = {'has_account': 0, 'no_contact': 0, 'left_without_account': 0}
by_bank = {}
for emp in people:
    if emp in no_account:
        skipped['left_without_account'] += 1
        continue
    partner = emp.work_contact_id
    # already an account on record (or any account on their contact, archived
    # ones included): leave it exactly as it is
    if emp.bank_account_ids or (partner and AnyAccount.search_count(
            [('partner_id', '=', partner.id)])):
        skipped['has_account'] += 1
        continue
    if not partner:
        skipped['no_contact'] += 1
        continue
    number = fake_number(shared_a.id if emp == shared_b else emp.id)
    holder = emp.name
    if emp == close_one:
        holder = close_holder
    elif emp == other_one:
        holder = other_holder
    bank = bank_for(emp.vietnam_bank_name or 'Vietcombank')
    account = Account.create({
        'acc_number': number, 'partner_id': partner.id, 'bank_id': bank.id,
        'acc_holder_name': holder, 'company_id': company.id,
    })
    emp.write({'bank_account_ids': [(4, account.id)]})
    made |= account
    by_bank[bank.name] = by_bank.get(bank.name, 0) + 1

Seed = env.get('pb.demo.seed')
registered = 0
if Seed is not None:
    if made_banks:
        registered += Seed.register(made_banks, LABEL)
    if made:
        registered += Seed.register(made, LABEL)

env.flush_all()
after = counts()
after['bank_accounts_existing'] = existing_accounts_sum(max_acc)
say('after  %s', {k: v for k, v in after.items() if k not in ('bank_file_fields', 'bank_accounts_existing')})
say('made %s bank accounts on record, %s new banks; skipped %s; register +%s',
    len(made), len(made_banks), skipped, registered)
say('by bank %s', dict(sorted(by_bank.items(), key=lambda kv: -kv[1])))

# THE RAILS
problems = []
for key in ('employees', 'payslips', 'payslip_runs', 'users', 'mail_all', 'mail_outgoing',
            'activities', 'crons_active', 'bank_changes', 'approval_requests',
            'bank_file_fields', 'bank_accounts_existing'):
    if after[key] != before[key]:
        problems.append('%s changed' % key)
if after['bank_accounts'] - before['bank_accounts'] != len(made):
    problems.append('bank accounts moved by more than the seed made')
if after['banks'] - before['banks'] != len(made_banks):
    problems.append('banks moved by more than the seed made')

# What the showcase run's payment list now says (counts only; no account number).
summary = env['pb.payment.list'].sudo()._pb_build_rows(run)
reasons = {}
for row in summary['rows']:
    for check in row['checks']:
        key = check.split(' as ')[0] if check.startswith('Same account') else check
        reasons[key] = reasons.get(key, 0) + 1
say('showcase payment list: %s people, totals %s, %s need a check: %s',
    summary['count'], [(t['currency'], round(t['amount'], 2), t['count']) for t in summary['totals']],
    summary['check_count'], reasons)
say('messages +%s (the standard "Bank Account created" note on each contact)',
    after['messages'] - before['messages'])

if problems:
    env.cr.rollback()
    say('ABORTED, rolled back: %s', '; '.join(problems))
elif DRY:
    env.cr.rollback()
    say('DRY RUN — rolled back')
else:
    env.cr.commit()
    say('COMMITTED')
