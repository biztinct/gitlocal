"""Set each rize employee's MANAGER from the pay data file's "Reporting Manager".

Owner ruling 2026-11-05: fill the clean matches now; the rest goes to Rize as a
list. Run ON rize ONLY, through the shell (the service may stay up). The script
is kept beside its undo tables in ARCHIVE (odoo-only folder, so it is piped in
with `sudo cat`; settings go AFTER `sudo -u odoo` because sudo drops a variable
set in front of it):

    S=/odoo/archives/rize-managers-20261105/seed_rize_managers_from_payfile.py
    ODOO="python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d rize --no-http"

    # 1. dry run (default) - prints the proposal, writes nothing
    sudo cat $S | sudo -u odoo $ODOO

    # 2. real run - undo table first, then the managers, then commit
    sudo cat $S | sudo -u odoo PB_MGR_APPLY=1 $ODOO

    # 3. undo - puts back manager, coach and both approvers from the undo table
    #    (add PB_MGR_DRY=1 to rehearse it and roll back)
    sudo cat $S | sudo -u odoo PB_MGR_UNDO=/odoo/archives/rize-managers-20261105/undo-<stamp>.csv $ODOO

Source: the latest real pay data batch per scheme (BATCHES below). Each imported
row keeps the file's columns in `hr.payroll.import.line.raw_data_json`; the
manager is "Consolidated|Reporting Manager" (Vietnam, India) or
"Consolidated|Master Reporting Manager" (Indonesia, Singapore). "Hiring Manager"
is NOT the manager and is never read.

Matching: the manager's name against every ACTIVE rize employee, accent-
insensitive ("Ho Huu Du" = "Hồ Hữu Dư"), in three tiers - the full name; the
same words in another order ("Nithya R" = "R Nithya"); a short name whose
every word is inside ONE person's name ("Monica" = "Monica Puranlal
Bhojwani"; a short name outside Vietnam must not contradict the file's own
manager email). A name that also fits someone who has LEFT is not clean
("Shreya": one active, one archived). Two or more people at a tier: the
"Reporting manager Mail ID" column settles it against the work email - never
for Vietnam, where one address sits beside five different names. Anything that
is not ONE clean match is refused and listed (ambiguous, no match, blank, the
person reporting to themselves, a person who has left, two files disagreeing,
a loop).

Writes: `parent_id` ONLY, through `pb.orgchart._set_managers` (ORGCHART_LEDGER
rule 12 / G16): coach, time-off approver and expense approver keep their value
in the same write. The script re-reads them afterwards and refuses to commit if
any moved. A person who already has a DIFFERENT manager is kept as they are and
listed. Loops are judged with `pb.orgchart._loop_in` on the whole change list.
Runs as the admin user (uid 2) so the history on each record names the admin.

Idempotent: a second run finds everyone already set and writes nothing. Each
real run writes its own undo table (never overwrites an earlier one) under
ARCHIVE, plus a JSON of the whole proposal for the client list.
"""
import csv
import json
import os
import re
import unicodedata
from datetime import datetime, timezone

assert env.cr.dbname == 'rize', 'Rize-only data task.'  # noqa: F821

ARCHIVE = '/odoo/archives/rize-managers-20261105'
BATCHES = {2072: 'VN', 2284: 'ID', 2260: 'IN', 2285: 'SG'}
EXPECT = {'rows': 214, 'clean': 204, 'tolerance': 5}
MGR_KEYS = ('Consolidated|Reporting Manager', 'Consolidated|Master Reporting Manager')
FOLLOWERS = ('coach_id', 'leave_manager_id', 'expense_manager_id')


def norm(s):
    s = (s or '').replace('đ', 'd').replace('Đ', 'D')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def mail_value(raw):
    for k, v in raw.items():
        if k.startswith('Consolidated|') and 'reporting manager mail' in k.lower():
            return (str(v or '')).strip().lower()
    return ''


def emp_code(e):
    for f in ('employee_code', 'pb_employee_code', 'registration_number', 'barcode'):
        if f in e._fields and e[f]:
            return str(e[f])
    return ''


def active_with_manager(Emp):
    return Emp.search_count([('parent_id', '!=', False)])


def snapshot(Emp, ids):
    out = {}
    for e in Emp.with_context(active_test=False).browse(list(ids)):
        out[e.id] = {'parent_id': e.parent_id.id or False}
        for f in FOLLOWERS:
            if f in e._fields:
                out[e.id][f] = e[f].id or False
    return out


def undo(env, path):
    Emp = env['hr.employee']
    Org = env['pb.orgchart']
    rows = list(csv.DictReader(open(path, encoding='utf-8')))
    ids = [int(r['employee_id']) for r in rows]
    now = snapshot(Emp, ids)
    changes, followers, changed_since = {}, {}, []
    for r in rows:
        e = int(r['employee_id'])
        new = int(r['new_parent_id']) if r['new_parent_id'] else False
        if now.get(e, {}).get('parent_id') != new:
            changed_since.append((e, r['employee_name']))
            continue
        changes[e] = int(r['old_parent_id']) if r['old_parent_id'] else False
        followers[e] = {f: (int(r['old_' + f]) if r['old_' + f] else False) for f in FOLLOWERS}
    print('UNDO rows %d, to put back %d, changed by someone since (left alone) %d'
          % (len(rows), len(changes), len(changed_since)))
    for e, n in changed_since:
        print('  left alone (manager changed since):', e, n)
    bad = Org._loop_in(changes)
    if bad:
        raise SystemExit('UNDO STOP: putting back would make a loop at employee %s' % bad)
    before = active_with_manager(Emp)
    Org._set_managers(changes)
    for e, vals in followers.items():
        rec = Emp.with_context(active_test=False).browse(e)
        w = {f: v for f, v in vals.items() if f in rec._fields and (rec[f].id or False) != v}
        if w:
            rec.write(w)
    Emp.flush_model()
    after = active_with_manager(Emp)
    back = snapshot(Emp, changes.keys())
    wrong = [e for e in changes if back[e]['parent_id'] != changes[e]
             or any(back[e].get(f) != followers[e][f] for f in FOLLOWERS if f in back[e])]
    if wrong or os.environ.get('PB_MGR_DRY') == '1':
        env.cr.rollback()
        print('UNDO REHEARSAL (rolled back). would put back %d; not matching the table afterwards: %s; '
              'people with a manager: %d -> %d' % (len(changes), wrong, before, after))
        return
    env.cr.commit()
    print('UNDO DONE. people with a manager: %d -> %d' % (before, after))


def main(env):
    admin = env.ref('base.user_admin')
    company = env['res.company'].search([])
    env = env(user=admin.id, context=dict(env.context, allowed_company_ids=company.ids))
    if os.environ.get('PB_MGR_UNDO'):
        return undo(env, os.environ['PB_MGR_UNDO'])
    apply = os.environ.get('PB_MGR_APPLY') == '1'
    Emp = env['hr.employee']
    EmpAll = Emp.with_context(active_test=False)
    Org = env['pb.orgchart']
    Batch = env['hr.payroll.import.batch']
    Line = env['hr.payroll.import.line']

    # ---------------------------------------------------------- the files
    for bid, cc in BATCHES.items():
        b = Batch.browse(bid).exists()
        assert b, 'batch %s is gone' % bid
        print('SOURCE batch %d [%s] %s (%s)' % (bid, cc, b.display_name, b.state))

    active = Emp.search([])
    everyone = [(e, norm(e.name), set(norm(e.name).split())) for e in EmpAll.search([])]

    def find(text):
        """(active candidates, people who have left, method) at the first tier
        that finds anyone, active or not: full name -> same words in another
        order -> every word of the file's short name inside the person's name
        ("Monica" -> "Monica Puranlal Bhojwani"). Only a single ACTIVE
        candidate with nobody who has left at the same tier is ever written."""
        n = norm(text)
        ws = set(n.split())
        tiers = [('full name', lambda nm, w: nm == n),
                 ('same name, words in another order', lambda nm, w: w == ws)]
        if ws and max(len(x) for x in ws) >= 3:
            tiers.append(('short name', lambda nm, w: ws <= w))
        for how, ok in tiers:
            hit = [e for e, nm, w in everyone if ok(nm, w)]
            if hit:
                return ([e for e in hit if e.active], [e for e in hit if not e.active], how)
        return [], [], ''

    def mails(e):
        return {m.strip().lower() for m in (e.work_email, e.private_email) if m}

    def cand(c, **extra):
        d = {'id': c.id, 'name': c.name, 'code': emp_code(c), 'email': c.work_email or c.private_email or '',
             'job': c.job_title or '', 'left': not c.active}
        d.update(extra)
        return d

    rows, problems, blanks = [], [], []
    for bid, cc in BATCHES.items():
        for ln in Line.search([('batch_id', '=', bid)], order='id'):
            raw = json.loads(ln.raw_data_json or '{}')
            mname = next((str(raw[k]).strip() for k in MGR_KEYS if raw.get(k) not in (None, '')), '')
            mail = mail_value(raw)
            subj = ln.employee_id.with_context(active_test=False)
            row = {'batch': bid, 'scheme': cc, 'line': ln.id,
                   'emp_id': subj.id or False, 'emp_name': subj.name or ln.employee_name or '',
                   'emp_code': (emp_code(subj) if subj else '') or (ln.employee_code or ''),
                   'emp_active': bool(subj.active) if subj else False,
                   'manager_text': mname, 'manager_mail': mail,
                   'mgr_id': False, 'mgr_name': '', 'method': '', 'problem': '', 'candidates': [],
                   'email_agrees': ''}
            rows.append(row)
            if not mname:
                row['problem'] = 'blank'
                blanks.append(row)
                continue
            cands, gone, how = find(mname)
            row['candidates'] = [cand(c) for c in cands + gone]
            if not subj:
                row['problem'] = 'row not linked to an employee'
            elif not subj.active:
                row['problem'] = 'employee has left (archived) - skipped'
            elif len(cands) == 1 and not gone:
                row['mgr_id'], row['method'] = cands[0].id, how
                cm = mails(cands[0])
                row['email_agrees'] = ('no email in file' if not mail else
                                       'no email on the record' if not cm else
                                       'yes' if mail in cm else 'no')
                # a short/reordered name outside Vietnam must not contradict the
                # file's own manager email (Vietnam's email column is unreliable)
                if how != 'full name' and cc != 'VN' and row['email_agrees'] == 'no':
                    row['mgr_id'] = False
                    row['problem'] = 'short name matches %s but the email says %s' % (cands[0].name, mail)
            elif cands:
                if cc != 'VN' and mail and not gone:
                    hit = [c for c in cands if mail in mails(c)]
                    if len(hit) == 1:
                        row['mgr_id'], row['method'] = hit[0].id, how + ', tie settled by email'
                if not row['mgr_id']:
                    row['problem'] = 'ambiguous: %d people fit this name%s' % (
                        len(cands) + len(gone), ' (%d of them has left)' % len(gone) if gone else '')
            else:
                row['problem'] = 'manager has left (archived)' if gone else 'no one with this name'
                if mail and not gone:
                    by_mail = Emp.search(['|', ('work_email', '=ilike', mail), ('private_email', '=ilike', mail)])
                    row['candidates'] = [cand(c, via='email') for c in by_mail]
            if row['mgr_id']:
                row['mgr_name'] = Emp.browse(row['mgr_id']).name
                if row['mgr_id'] == row['emp_id']:
                    row['problem'], row['mgr_id'] = 'would report to themselves', False
            if row['problem'] and row not in problems:
                problems.append(row)

    # one employee, two files, two different managers -> refuse both
    per_emp = {}
    for r in rows:
        if r['mgr_id']:
            per_emp.setdefault(r['emp_id'], set()).add(r['mgr_id'])
    for r in rows:
        if r['mgr_id'] and len(per_emp[r['emp_id']]) > 1:
            r['problem'], r['mgr_id'] = 'files disagree on the manager', False
            problems.append(r)

    clean = [r for r in rows if r['mgr_id']]
    proposal = {}
    for r in clean:
        proposal[r['emp_id']] = r['mgr_id']

    # current values; people who already have a different manager are kept
    cur = snapshot(Emp, proposal.keys())
    already, kept_other, changes = [], [], {}
    for e, m in proposal.items():
        p = cur[e]['parent_id']
        if p == m:
            already.append(e)
        elif p:
            kept_other.append((e, p, m))
        else:
            changes[e] = m

    # loops: drop the offender until none is left
    loops = []
    while True:
        bad = Org._loop_in(changes)
        if not bad:
            break
        loops.append((bad, changes.pop(bad)))

    # people in no file
    in_files = {r['emp_id'] for r in rows if r['emp_id']}
    unlisted = [e for e in active if e.id not in in_files]

    # ------------------------------------------------------------- print
    print('\nPROPOSAL (employee -> manager | scheme batch | method | status)')
    for r in sorted(clean, key=lambda r: (r['scheme'], r['emp_name'])):
        e = r['emp_id']
        st = ('already set' if e in already else
              'KEPT: has another manager' if any(k[0] == e for k in kept_other) else
              'LOOP: refused' if any(l[0] == e for l in loops) else 'to write')
        print('  [%s] %s (%s) -> %s (%s) | %d | %s | email agrees: %s | %s'
              % (r['scheme'], r['emp_name'], e, r['mgr_name'], r['mgr_id'], r['batch'], r['method'],
                 r['email_agrees'], st))
    print('\nPROBLEM ROWS (not written)')
    for r in problems:
        if r['problem'] == 'blank':
            continue
        cs = '; '.join('%s <%s> #%s%s' % (c['name'], c['email'], c['id'],
                       ' (by email)' if c.get('via') else '') for c in r['candidates']) or '-'
        print('  [%s] %s (%s): "%s" mail=%s -> %s | candidates: %s'
              % (r['scheme'], r['emp_name'], r['emp_id'], r['manager_text'], r['manager_mail'] or '-',
                 r['problem'], cs))
    print('\nBLANK manager cell:', ', '.join('[%s] %s' % (r['scheme'], r['emp_name']) for r in blanks) or '-')
    for e, p, m in kept_other:
        print('KEPT (already has a different manager): %s has %s, file says %s'
              % (Emp.browse(e).name, EmpAll.browse(p).name, Emp.browse(m).name))
    for e, m in loops:
        print('LOOP refused: %s -> %s' % (Emp.browse(e).name, Emp.browse(m).name))

    before = active_with_manager(Emp)
    nprob = len([r for r in problems if r['problem'] != 'blank'])
    print('\nSUMMARY rows=%d with_manager=%d clean=%d problems=%d blank=%d '
          'already_set=%d kept_other=%d loops=%d to_write=%d in_no_file=%d'
          % (len(rows), len(rows) - len(blanks), len(clean), nprob, len(blanks),
             len(already), len(kept_other), len(loops), len(changes), len(unlisted)))
    print('people with a manager now: %d of %d active; coach %d; time-off approver %d; expense approver %d'
          % (before, len(active), Emp.search_count([('coach_id', '!=', False)]),
             Emp.search_count([('leave_manager_id', '!=', False)]),
             Emp.search_count([('expense_manager_id', '!=', False)])))

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report = {
        'stamp': stamp, 'apply': apply, 'before_with_manager': before,
        'rows': rows, 'to_write': {str(k): v for k, v in changes.items()},
        'already': already, 'kept_other': kept_other, 'loops': loops,
        'unlisted': [{'id': e.id, 'name': e.name, 'code': emp_code(e), 'job': e.job_title or '',
                      'department': e.department_id.name or '', 'email': e.work_email or '',
                      'country': (e.payroll_country if 'payroll_country' in e._fields else '') or '',
                      'manager': e.parent_id.name or ''}
                     for e in unlisted],
        'emp_info': {str(e.id): {'name': e.name, 'code': emp_code(e), 'job': e.job_title or '',
                                 'department': e.department_id.name or ''}
                     for e in EmpAll.browse(sorted({r['emp_id'] for r in rows if r['emp_id']}
                                                   | {r['mgr_id'] for r in clean}))},
    }

    tol = EXPECT['tolerance']
    if abs(len(rows) - EXPECT['rows']) > tol or abs(len(clean) - EXPECT['clean']) > tol:
        env.cr.rollback()
        raise SystemExit('STOP: counts differ from the read-only check (rows %d, clean %d)'
                         % (len(rows), len(clean)))

    os.makedirs(ARCHIVE, exist_ok=True)
    kind = 'apply' if apply else 'dry'
    with open(os.path.join(ARCHIVE, 'proposal-%s-%s.json' % (kind, stamp)), 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1, default=str)

    if not apply:
        env.cr.rollback()
        print('\nDRY RUN - nothing written. Proposal JSON in %s' % ARCHIVE)
        return
    if not changes:
        env.cr.rollback()
        print('\nNothing to write (everyone already set).')
        return

    # ------------------------------------------------- undo table FIRST
    old = snapshot(Emp, changes.keys())
    undo_path = os.path.join(ARCHIVE, 'undo-%s.csv' % stamp)
    with open(undo_path, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['employee_id', 'employee_name', 'old_parent_id'] +
                   ['old_' + f for f in FOLLOWERS] + ['new_parent_id'])
        for e, m in sorted(changes.items()):
            o = old[e]
            w.writerow([e, Emp.browse(e).name, o['parent_id'] or ''] +
                       [o.get(f) or '' for f in FOLLOWERS] + [m])
        fh.flush()
        os.fsync(fh.fileno())
    print('\nUNDO TABLE %s (%d rows)' % (undo_path, len(changes)))
    print('UNDO COMMAND:\n  sudo cat %s/seed_rize_managers_from_payfile.py | sudo -u odoo '
          'PB_MGR_UNDO=%s python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf '
          '-d rize --no-http' % (ARCHIVE, undo_path))

    # ------------------------------------------------------------ write
    Org._set_managers(changes)
    Emp.flush_model()
    after = snapshot(Emp, changes.keys())
    moved = [e for e in changes if any(after[e].get(f) != old[e].get(f) for f in FOLLOWERS)]
    wrong = [e for e in changes if after[e]['parent_id'] != changes[e]]
    if moved or wrong:
        env.cr.rollback()
        raise SystemExit('STOP: rolled back - followers moved %s, manager not set %s' % (moved, wrong))
    env.cr.commit()
    print('WRITTEN %d managers. people with a manager: %d -> %d; coach %d; time-off approver %d; '
          'expense approver %d'
          % (len(changes), before, active_with_manager(Emp),
             Emp.search_count([('coach_id', '!=', False)]),
             Emp.search_count([('leave_manager_id', '!=', False)]),
             Emp.search_count([('expense_manager_id', '!=', False)])))


main(env)  # noqa: F821 - `env` comes from odoo-bin shell
