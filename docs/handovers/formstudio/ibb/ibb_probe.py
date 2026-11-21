# INBOX-BULK-BANK probe — runs inside `odoo-bin shell`. Counts only: never a name, never an
# account number. PROBE lines are what the scripts read.
#
# IBB_MODE=counts   (default) READ-ONLY, rolled back: the catalogue flags of the money / bank kinds,
#                   waiting bank-detail requests, decisions, mails, queued notices, bank accounts
#                   (count + a hash of id/number/holder, never the values), the joining checklist
#                   "Bank account" count, and what "Select all" offers each open seat.
# IBB_MODE=approve  ON A HIDDEN COPY ONLY (refuses unless the database name starts ibb_rh_):
#                   as IBB_UID (the approver's seat) — select all; the refusal without the check;
#                   one request approved alone (Approve in the drawer) and the rest with Approve
#                   selected in groups of 50 with the check confirmed, each group committed like
#                   one browser call; then one alone vs one together compared field by field.
import hashlib
import os
import time

MODE = os.environ.get('IBB_MODE', 'counts')
out = []


def p(line):
    out.append(line)
    print('PROBE', line, flush=True)


def bank_hash():
    Bank = env['res.partner.bank'].sudo().with_context(active_test=False)
    rows = Bank.search([], order='id')
    raw = '\n'.join('%s|%s|%s' % (b.id, ''.join(ch for ch in (b.acc_number or '') if ch.isalnum()),
                                  (b.acc_holder_name or '').strip().lower()) for b in rows)
    return len(rows), hashlib.md5(raw.encode()).hexdigest()[:10]


def checklist():
    E = env['hr.employee'].sudo().with_context(active_test=True)
    if 'profile_missing' not in E._fields:
        return 'n/a'
    emps = E.search([])
    miss = sum(1 for e in emps if 'Bank account' in (e.profile_missing or ''))
    wait = sum(1 for e in emps if 'Bank account' in (getattr(e, 'pb_profile_waiting', '') or ''))
    return 'active %s bank_missing %s waiting %s' % (len(emps), miss, wait)


def counts(tag):
    P = env['biz.approval.process'].sudo()
    flags = []
    for row in P.search([('money', '=', True)], order='key') | P.search([('key', 'in', ('bankchange', 'records_bank'))]):
        mode = row._bulk_mode() if hasattr(row, '_bulk_mode') else ('on' if row.bulk_ok else 'off')
        flags.append('%s=%s' % (row.key, mode))
    p('%s flags %s' % (tag, ' '.join(sorted(set(flags)))))
    R = env['biz.approval.request'].sudo()
    for key in ('records_bank', 'bankchange'):
        p('%s requests %s pending %s approved %s applied %s blocked %s' % (
            tag, key,
            R.search_count([('process_id.key', '=', key), ('state', '=', 'pending')]),
            R.search_count([('process_id.key', '=', key), ('state', '=', 'approved')]),
            R.search_count([('process_id.key', '=', key), ('state', '=', 'applied')]),
            R.search_count([('process_id.key', '=', key), ('state', '=', 'blocked')])))
    p('%s all requests %s decisions %s events %s' % (
        tag, R.search_count([]), env['biz.approval.decision'].sudo().search_count([]),
        env['biz.approval.event'].sudo().search_count([])))
    Req = env.get('pb.bank.change.request')
    if Req is not None:
        Req = Req.sudo().with_context(active_test=False)
        states = {}
        for row in Req.search([]):
            states[row.state] = states.get(row.state, 0) + 1
        p('%s bank change requests %s' % (tag, ' '.join('%s=%s' % kv for kv in sorted(states.items()))))
    p('%s mails %s outbox %s jobs active %s' % (
        tag, env['mail.mail'].sudo().search_count([]),
        env['biz.approval.outbox'].sudo().search_count([]),
        env['ir.cron'].sudo().search_count([])))
    n, h = bank_hash()
    p('%s bank accounts %s hash %s' % (tag, n, h))
    p('%s checklist %s' % (tag, checklist()))


def inbox_for(uid):
    user = env['res.users'].sudo().browse(uid)
    return env['pb.approval.inbox'].with_user(user).with_context(
        allowed_company_ids=user.company_ids.ids, pbf_ctx={'scope': 'me'})


def pages():
    """Open the changed screens over the web stack (counts and status codes only):
    the inbox's own calls as the administrator and as one open bank seat, the route
    editor's switch, /my and My Leave for three employees, and the backend page with
    its style bundle (proves the new styles compiled: the check dialog's class is in it)."""
    import hashlib as _h
    import re
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from odoo import http
    from odoo.service import security
    host = os.environ.get('PROBE_HOST') or 'localhost'
    db = env.cr.dbname
    env.cr.commit()

    def session_for(user):
        s = http.root.session_store.new()
        s.update(http.get_default_session(), db=db, _trace_disable=True)
        s.uid = user.id
        s.login = user.login
        s.context = {'lang': user.lang or 'en_US'}
        s.session_token = security.compute_session_token(s, env(user=user.id))
        http.root.session_store.save(s)
        return s

    def fetch(user, paths):
        s = session_for(user)
        c = Client(http.root, Response)
        c.set_cookie('session_id', s.sid, domain=host)
        res = []
        try:
            for path in paths:
                r = c.get(path, headers={'Host': host})
                res.append((path, r.status_code, r.get_data()))
        finally:
            http.root.session_store.delete(s)
        return res

    admin = env.ref('base.user_admin')
    if not admin.has_group('base.group_system'):
        admin = env['res.users'].search([('share', '=', False), ('id', '!=', 1)]).filtered(
            lambda u: u.has_group('base.group_system'))[:1]
    # the backend page, and its style bundle
    got = fetch(admin, ['/odoo'])
    path, code, body = got[0]
    css = re.findall(rb'/web/assets/[^"\']*web\.assets_web[^"\']*\.css', body)
    line = '/odoo %s' % code
    if css:
        (cp, cc, cb), = fetch(admin, [css[0].decode()])
        line += ' styles %s %s bytes, check dialog styles %s, vendor word %s' % (
            cc, len(cb), b'pbam-check-tick' in cb, b'Odoo' in cb.replace(b'odoo', b''))
    p('pages admin %s' % line)
    # the inbox and the route editor's switch, as the administrator
    try:
        inbox = inbox_for(admin.id)
        head = inbox.get_inbox_head()
        page = inbox.get_inbox_page(filters={'my_turn': ['yes']})
        p('pages inbox admin head ok %s, my approvals %s cards %s, tickable %s, extra check %s' % (
            bool(head), page['total'], len(page['cards']),
            sum(1 for c in page['cards'] if c.get('can_bulk')),
            sum(1 for c in page['cards'] if c.get('bulk_confirm'))))
        Matrix = env['pb.approval.matrix'].with_user(admin).with_context(
            allowed_company_ids=admin.company_ids.ids)
        wf = env['biz.approval.workflow'].sudo().search(
            [('process_id.key', '=', 'records_bank'), ('company_id', 'in', admin.company_ids.ids)], limit=1)
        if wf:
            data = Matrix.get_workflow(wf.id)
            b = data.get('bulk') or {}
            p('pages route editor bank: switch %s allowed %s can_edit %s' % (
                b.get('mode'), b.get('allowed'), b.get('can_edit')))
    except Exception as e:  # noqa
        p('pages inbox ERROR %s %s' % (type(e).__name__, str(e)[:120]))
    # three employees: /my and My Leave
    Emp = env['hr.employee'].sudo()
    dom = [('user_id', '!=', False), ('active', '=', True), ('user_id.active', '=', True)]
    emps = Emp.search(dom, limit=3, order='id desc')
    paths = ['/my']
    if 'pb.ess.workforce' in env:
        paths.append('/my/work/leave')
    for i, emp in enumerate(emps):
        res = fetch(emp.user_id, paths)
        p('pages emp%s %s' % (i + 1, ' | '.join('%s %s %s' % (pp, cc, _h.md5(
            re.sub(rb'[0-9a-f]{40}o[0-9]+|/web/assets/[^"\' ]+|data-server-now-ms="[0-9]+"', b'', bb)
        ).hexdigest()[:10]) for pp, cc, bb in res)))
    env.cr.rollback()


if MODE == 'pages':
    pages()

elif MODE == 'counts':
    counts('before')
    seats = env['biz.approval.request.seat'].sudo().search([
        ('status', '=', 'open'), ('step_id.status', '=', 'active'),
        ('step_id.request_id.process_id.key', '=', 'records_bank'),
        ('step_id.request_id.state', '=', 'pending')])
    for uid in sorted(set(seats.mapped('acting_user_id').ids)):
        if not hasattr(env['pb.approval.inbox'], 'select_all_ids'):
            p('select-all not in this code; open seats uid %s' % uid)
            continue
        try:
            t0 = time.time()
            sel = inbox_for(uid).select_all_ids(filters={}, search=None)
            p('select-all uid %s offers %s (extra check %s, capped %s) in %.1f s' % (
                uid, sel['count'], sel['confirm'], sel['capped'], time.time() - t0))
            if hasattr(env['pb.approval.inbox'], 'bulk_summary'):
                t0 = time.time()
                s = inbox_for(uid).bulk_summary(sel['ids'])
                p('summary uid %s count %s confirm %s bank %s other_name %s pay %s in %.1f s' % (
                    uid, s['count'], s['confirm'], s['bank'], s['other_name'], s['pay'], time.time() - t0))
        except Exception as e:  # noqa
            p('select-all uid %s ERROR %s %s' % (uid, type(e).__name__, str(e)[:120]))
    env.cr.rollback()

elif MODE == 'approve':
    assert env.cr.dbname.startswith('ibb_rh_'), 'approve mode runs on a hidden copy only'
    uid = int(os.environ['IBB_UID'])
    counts('before')
    env.cr.commit()
    inbox = inbox_for(uid)
    t0 = time.time()
    sel = inbox.select_all_ids(filters={}, search=None)
    ids, revs = sel['ids'], sel['revisions']
    p('select-all offers %s (extra check %s) in %.1f s' % (len(ids), sel['confirm'], time.time() - t0))
    # 1. without the check: refused, nothing changes
    answer = inbox.decide_many(ids[:3], {k: revs[str(k)] for k in ids[:3]})
    p('without the check: done %s refused %s' % (answer['done'], answer['failed']))
    env.cr.rollback()
    # 2. one alone, as the drawer's Approve does
    Request = env['biz.approval.request'].sudo()
    single = Request.browse(ids[0])
    step = single.step_ids.filtered(lambda s: s.status == 'active')[:1]
    inbox.decide(single.id, step.key, 'approve')
    env.cr.commit()
    rest = ids[1:]
    done = failed = 0
    times = []
    errors = {}
    for start in range(0, len(rest), 50):
        chunk = rest[start:start + 50]
        t1 = time.time()
        answer = inbox.decide_many(chunk, {str(k): revs[str(k)] for k in chunk},
                                   confirmed=True, batch_size=len(ids))
        env.cr.commit()
        times.append(round(time.time() - t1, 1))
        done += answer['done']
        failed += answer['failed']
        for row in answer['results']:
            if not row['ok']:
                # the first six words only: a reason may go on to name people
                key = ' '.join((row['error'] or '').split()[:6])
                errors[key] = errors.get(key, 0) + 1
    p('together: %s groups, done %s failed %s, seconds per group %s' % (len(times), done, failed, times))
    for key, n in sorted(errors.items()):
        p('  not approved x%s: %s' % (n, key))
    # 3. one alone vs one together, field by field
    env.invalidate_all()

    def shape(request):
        rec = request._record()
        emp = rec.employee_id.sudo() if 'employee_id' in rec._fields else None
        d = {'request': request.state,
             'record': getattr(rec, 'state', ''),
             'steps': [s.status for s in request.step_ids.sorted('sequence')],
             'seats': sorted(s.status for s in request.step_ids.seat_ids)}
        if emp is not None and rec._name == 'pb.bank.change.request':
            dig = lambda t: ''.join(ch for ch in str(t or '') if ch.isalnum()).upper()
            acc = emp.bank_account_ids[:1] if 'bank_account_ids' in emp._fields else None
            d['file number = proposal'] = dig(emp.vietnam_bank_account_number) == dig(rec.x_account_number)
            d['file holder = proposal'] = (emp.vietnam_bank_account_name or '').strip().lower() == (rec.x_account_name or '').strip().lower()
            d['file bank = proposal'] = (emp.vietnam_bank_name or '').strip().lower() == (rec.x_bank_name or '').strip().lower()
            d['approved account number = proposal'] = bool(acc) and dig(acc.acc_number) == dig(rec.x_account_number)
            d['approved account holder = proposal'] = bool(acc) and (acc.acc_holder_name or '').strip().lower() == (rec.x_account_name or '').strip().lower()
        return d

    one = shape(single)
    other = shape(Request.browse(rest[0])) if rest else {}
    p('alone    %s' % sorted(one.items()))
    p('together %s' % sorted(other.items()))
    p('alone vs together identical: %s' % (one == other))
    dec_one = env['biz.approval.decision'].sudo().search([('request_id', '=', single.id)])
    dec_two = env['biz.approval.decision'].sudo().search([('request_id', '=', rest[0])]) if rest else dec_one
    same = all(dec_one[f] == dec_two[f] for f in ('action', 'step_key', 'user_id', 'acting_for_uid',
                                                   'exception_grant_id', 'conflict_kind', 'company_id'))
    p('decision fields identical (but the note): %s; note on the together one: %s' % (
        same, (dec_two.reason or '')[:90]))
    # every approved one: does the bank now read the proposal?
    ok = bad = 0
    for rid in ids:
        s = shape(Request.browse(rid))
        flags = [v for k, v in s.items() if k.endswith('proposal')]
        if flags and all(flags):
            ok += 1
        else:
            bad += 1
    p('every request: bank now = proposal %s, not %s' % (ok, bad))
    counts('after')
