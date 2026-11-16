# WDGAP W3-C BG1 — "Bank details already on record — copy to the bank file".
#
# Run inside `odoo-bin shell -d <db>` (stdin). The first line of the file that
# is fed in sets MODE = 'dry' | 'run' (prepended by the caller).
#
# What it does (owner ruling BG1, 2026-11-17): for the people whose bank
# account is on record but whose bank-file fields are empty, it creates ONE
# WAITING bank change each, through the product's own import-hold path
# (pb_bank_ocr `_pb_hold_from_import`, BK2), all keyed to ONE batch so the
# approver sees one row with one "Approve all in this file" on Compliance ›
# Bank. NOTHING on any employee or bank account changes here: the two bank
# stores are written only when a second person approves.
#
#   dry: builds the lists, creates the batch, checks, then ROLLS BACK.
#   run: same, COMMITS only when every check passes.
# Idempotent: a person with a waiting change from this batch is skipped, so a
# second run creates nothing.
import hashlib
import json
from collections import defaultdict, Counter

from odoo.addons.pb_bank_ocr.models.pb_bank_import_hold import (
    FILE_FIELDS, OPEN_STATES, Hold)
from odoo.addons.pb_bank_ocr.models.vn_bank_dictionary import (
    account_ok, name_similarity)
from odoo.addons.pb_hr_payroll_formula.models.bank_account_util import (
    sanitize_acc_number, sanitize_bank_text)

assert MODE in ('dry', 'run'), MODE  # noqa: F821 — set by the caller
# NAME_RULE (set by the caller, default 'match_only'): which people whose
# account holder name differs from their own name are included —
#   'match_only' : only a holder name that matches (the bank check's green band)
#   'not_red'    : matches or is close (green + amber)
#   'any'        : everybody (the approver judges each name)
try:
    NAME_RULE  # noqa: F821
except NameError:
    NAME_RULE = 'match_only'
assert NAME_RULE in ('match_only', 'not_red', 'any'), NAME_RULE
DB = env.cr.dbname  # noqa: F821
KEY = 'bank-gap-copy,%s,2026-11-17' % DB
LABEL = 'Bank details already on record — copy to the bank file (%d people)'
OUT = '/tmp/bg1w3c/%s-%s' % (DB, MODE)

ROOT = env.ref('base.user_root')  # noqa: F821
Emp = env['hr.employee'].sudo().with_context(active_test=False)  # noqa: F821
Req = env['pb.bank.change.request'].sudo()  # noqa: F821
Reg = env['pb.bank.registry'].sudo()  # noqa: F821
Bank = env['res.bank'].sudo()  # noqa: F821
cr = env.cr  # noqa: F821


def digits(text):
    return ''.join(ch for ch in str(text or '') if ch.isdigit())


def mask(text):
    d = digits(text)
    return ('****' + d[-4:]) if len(d) > 4 else ('****' if d else '')


def stores_fingerprint():
    """Both bank stores of every employee + every bank account row."""
    h = hashlib.sha256()
    for e in Emp.search([], order='id'):
        h.update(repr((e.id, [e[f] or '' for f in FILE_FIELDS],
                       e.bank_account_ids.ids)).encode())
    PB = env['res.partner.bank'].sudo().with_context(active_test=False)  # noqa: F821
    for a in PB.search([], order='id'):
        h.update(repr((a.id, a.acc_number, a.bank_id.id, a.acc_holder_name,
                       a.partner_id.id, a.sequence, a.active)).encode())
    return h.hexdigest()


def counts():
    q = {}
    for table in ('pb_bank_change_request', 'biz_approval_request',
                  'biz_approval_outbox', 'mail_mail', 'mail_message',
                  'mail_activity', 'mail_notification', 'pb_employee_bank_history',
                  'res_bank', 'res_partner_bank', 'hr_employee'):
        cr.execute('SELECT count(*) FROM %s' % table)
        q[table] = cr.fetchone()[0]
    return q


fp_before = stores_fingerprint()
counts_before = counts()

check = Emp.pb_bank_store_check()
rows = [r for r in check['rows'] if r['status'] == 'accounts_only']

# Who holds which account number, in either store, anywhere in the database.
owners = defaultdict(set)
for e in Emp.search([]):
    d = digits(e.vietnam_bank_account_number)
    if d:
        owners[d].add(e.id)
    for a in e.bank_account_ids:
        d = digits(a.acc_number)
        if d:
            owners[d].add(e.id)

already = Req.search([('pb_import_key', '=', KEY)])
included, excluded, skipped_waiting = [], [], []
for r in rows:
    e = Emp.browse(r['employee_id'])
    accs = e.bank_account_ids
    a = accs[:1]
    base = {'employee_id': e.id, 'name': e.name or '', 'company': e.company_id.name or '',
            'accounts': len(accs), 'number': mask(a.acc_number) if a else '',
            'bank': (a.bank_id.name or '') if a else '',
            'holder': (a.acc_holder_name or '') if a else ''}
    reason = None
    if not e.active:
        reason = 'archived (no longer working here)'
    elif len(accs) != 1:
        reason = 'more than one bank account on record'
    elif any(e[f] for f in FILE_FIELDS):
        reason = 'bank-file details partly filled already'
    elif 'active' in a._fields and not a.active:
        reason = 'the bank account on record is archived'
    elif a.partner_id != e.work_contact_id:
        reason = 'the bank account is filed under a different contact'
    else:
        number, damaged = sanitize_acc_number(a.acc_number)
        bank_name = sanitize_bank_text(a.bank_id.name) or ''
        holder = a.acc_holder_name or ''
        if damaged or not number or not account_ok(a.acc_number):
            reason = 'account number is not 6 to 19 digits'
        elif not a.bank_id or not bank_name:
            reason = 'no bank name on the bank account'
        elif len(owners[digits(a.acc_number)]) > 1:
            reason = 'the same account number is on record for another person'
        elif Bank.search([('name', '=ilike', bank_name)], limit=1) != a.bank_id:
            reason = 'two banks on record have this name'
        elif not holder.strip():
            reason = 'no account holder name'
        elif holder != holder.strip():
            reason = 'account holder name has extra spaces'
        elif NAME_RULE != 'any' and name_similarity(holder, e.name) < (
                85 if NAME_RULE == 'match_only' else 60):
            # the same score and bands the bank check shows the approver
            # (`action_validate`: >=85 matches, >=60 close, else mismatch)
            reason = ('the account is in another name'
                      if name_similarity(holder, e.name) < 60
                      else 'the account name is close to, not the same as, the person')
        else:
            mine = already.filtered(lambda q: q.employee_id == e
                                    and q.state in OPEN_STATES)
            other_open = Req.search_count([('employee_id', '=', e.id),
                                           ('state', 'in', OPEN_STATES),
                                           ('id', 'not in', already.ids)])
            if mine:
                skipped_waiting.append(dict(base, request=mine[:1].name))
                continue
            if other_open:
                reason = 'another bank change for this person is already waiting'
    if reason:
        excluded.append(dict(base, reason=reason))
        continue
    base['bank_file_knows_bank'] = bool(Reg.match(a.bank_id.name or ''))
    base['holder_matches_name'] = None
    base['number_has_non_digits'] = a.acc_number.strip() != digits(a.acc_number)
    included.append((e, a, base))

n_new = len(included)
label = LABEL % (n_new + len(skipped_waiting))
hold = Hold(KEY, label, ROOT)
made_before = set(Req.search([('pb_import_key', '=', KEY)]).ids)
results = Counter()
for e, a, base in included:
    vals = {
        'x_account_number': a.acc_number,
        'x_bank_name': a.bank_id.name,
        'x_account_name': a.acc_holder_name,
        'x_bank_branch': '',
    }
    with cr.savepoint():
        res = Req.with_user(ROOT)._pb_hold_from_import(e, vals, hold)
    results[res] += 1
made = Req.search([('pb_import_key', '=', KEY), ('id', 'not in', list(made_before))])
for (e, a, base) in included:
    req = made.filtered(lambda q: q.employee_id == e)[:1]
    base['request'] = req.name or ''
    base['state'] = req.state or ''
    base['name_match'] = req.name_match_band or ''
env.invalidate_all()  # noqa: F821

state_counts = Counter(made.mapped('state'))
fp_after = stores_fingerprint()
counts_after = counts()
seats = Counter()
for q in made:
    request = q._chain_open_request()
    step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
    for s in step.seat_ids.filtered(lambda s: s.status == 'open'):
        seats[s.acting_user_id.login] += 1
proposers = Counter(made.mapped('proposed_by_id.name'))
ok = (fp_before == fp_after
      and state_counts.get('draft', 0) == 0
      and len(made) == n_new
      and all(r['state'] == 'hr_review' for _e, _a, r in included))

summary = {
    'db': DB, 'mode': MODE, 'name_rule': NAME_RULE, 'key': KEY, 'label': label,
    'store_check_counts': check['counts'],
    'accounts_only_rows': len(rows),
    'included_new': n_new, 'already_waiting_from_this_batch': len(skipped_waiting),
    'excluded': len(excluded),
    'excluded_by_reason': dict(Counter(x['reason'] for x in excluded)),
    'created': len(made), 'created_states': dict(state_counts),
    'hold_results': dict(results),
    'proposed_by': dict(proposers),
    'open_seats_per_approver': dict(seats),
    'bank_file_knows_bank': dict(Counter(r['bank_file_knows_bank'] for _e, _a, r in included)),
    'name_match_bands': dict(Counter(r['name_match'] for _e, _a, r in included)),
    'numbers_with_non_digits': sum(1 for _e, _a, r in included if r['number_has_non_digits']),
    'stores_unchanged': fp_before == fp_after,
    'counts_before': counts_before, 'counts_after': counts_after,
    'delta': {k: counts_after[k] - counts_before[k] for k in counts_before},
    'ok': ok,
}
with open(OUT + '-summary.json', 'w') as fh:
    json.dump(summary, fh, indent=1, ensure_ascii=False, default=str)
with open(OUT + '-lists.json', 'w') as fh:
    json.dump({'included': [r for _e, _a, r in included],
               'excluded': excluded, 'already_waiting': skipped_waiting},
              fh, indent=1, ensure_ascii=False, default=str)
print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))

if MODE == 'run' and ok:
    cr.commit()
    print('COMMITTED')
else:
    cr.rollback()
    print('ROLLED BACK (mode=%s, ok=%s)' % (MODE, ok))
