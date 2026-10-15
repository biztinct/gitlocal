#!/usr/bin/env python3
"""TIERS T4 — switch plain employees from full accounts to employee logins.

Runs over JSON-RPC against a RUNNING server (never `odoo-bin shell`, see
memory `payobook-deploy`), as an administrator. Dry-run by default.

    PB_URL=https://payobook.com PB_DB=payobook PB_LOGIN=... PB_PASSWORD=... \
        python3 tools/tiers_switchover.py                 # list candidates
    ... python3 tools/tiers_switchover.py --apply         # convert them
    ... python3 tools/tiers_switchover.py --rollback FILE # undo from a list
    ... python3 tools/tiers_switchover.py --backfill      # user_id <- pb_portal_user_id

A candidate is an active internal user who
  * has an active employee record (`hr.employee.user_id`),
  * is not an administrator / the system user / the recovery login,
  * holds no direct group outside base.group_user's implied closure except the
    harmless ones (`HARMLESS`), i.e. nobody gave them a permission by hand,
  * and whom the Access screen itself would allow to switch
    (`pb.access.passport(uid)['header']['switch']`: no role, no direct
    report, no open approval seat).

`--apply` writes a rollback list first (`tiers_rollback_<db>_<stamp>.json`:
uid, login, the direct group ids before the switch), then calls
`pb.access.set_account_type(uid, 'employee', reason)` one person at a time.
`--rollback FILE` calls `set_account_type(uid, 'staff')` and restores the
exact direct groups from the list.
`--backfill` sets `hr.employee.user_id` from `pb_portal_user_id` where the
employee has no login yet and the portal account is an active share user
(T-R10), writing its own rollback list (employee ids).

Credentials come from the environment only; nothing is stored.
"""
import argparse
import datetime as dt
import json
import os
import sys
import xmlrpc.client

HARMLESS = ('base.group_multi_company',
            'pb_driver_checkin.group_pb_driver',
            'pb_driver_checkin.group_pb_field_staff')
SKIP_LOGINS = {'manager.demo@payobook.com'}      # demo team lead stays staff


class Rpc:
    def __init__(self, url, db, login, password):
        self.db, self.password = db, password
        common = xmlrpc.client.ServerProxy('%s/xmlrpc/2/common' % url)
        self.uid = common.authenticate(db, login, password, {})
        if not self.uid:
            sys.exit('sign-in failed for %s on %s' % (login, db))
        self.models = xmlrpc.client.ServerProxy('%s/xmlrpc/2/object' % url)

    def call(self, model, method, *args, **kw):
        return self.models.execute_kw(self.db, self.uid, self.password,
                                      model, method, list(args), kw)

    def ref(self, xmlid):
        module, name = xmlid.split('.')
        rows = self.call('ir.model.data', 'search_read',
                         [['module', '=', module], ['name', '=', name]],
                         fields=['res_id'], limit=1)
        return rows[0]['res_id'] if rows else None


def closure_of_group_user(rpc):
    gid = rpc.ref('base.group_user')
    row = rpc.call('res.groups', 'read', [gid], fields=['all_implied_ids'])[0]
    return set(row['all_implied_ids']) | {gid}


def candidates(rpc, verbose=True):
    allowed_extra = closure_of_group_user(rpc)
    for xmlid in HARMLESS:
        g = rpc.ref(xmlid)
        if g:
            allowed_extra.add(g)
    out, skipped = [], []
    people = rpc.call('pb.access', 'people')
    for p in people:
        if p.get('kind') != 'staff' or not p.get('has_employee'):
            continue
        if p['login'] in SKIP_LOGINS:
            skipped.append((p['login'], 'skip list'))
            continue
        user = rpc.call('res.users', 'read', [p['id']],
                        fields=['group_ids', 'login', 'name', 'share'])[0]
        extra = set(user['group_ids']) - allowed_extra
        if extra:
            skipped.append((p['login'], 'hand-given permission(s) %s'
                            % sorted(extra)))
            continue
        passport = rpc.call('pb.access', 'passport', p['id'])
        switch = passport['header'].get('switch') or {}
        if switch.get('to') != 'employee' or not switch.get('allowed'):
            skipped.append((p['login'], switch.get('why') or 'not allowed'))
            continue
        out.append({'uid': p['id'], 'login': p['login'], 'name': p['name'],
                    'group_ids': user['group_ids']})
    if verbose:
        print('%d candidate(s), %d skipped' % (len(out), len(skipped)))
        for c in out:
            print('  CONVERT %-40s %s' % (c['login'], c['name']))
        for login, why in skipped:
            print('  skip    %-40s %s' % (login, why))
    return out


def apply(rpc, reason):
    rows = candidates(rpc)
    if not rows:
        return
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    path = 'tiers_rollback_%s_%s.json' % (rpc.db, stamp)
    with open(path, 'w') as fh:
        json.dump(rows, fh, indent=1)
    print('rollback list written: %s' % path)
    done = 0
    for c in rows:
        try:
            res = rpc.call('pb.access', 'set_account_type', c['uid'],
                           'employee', reason)
            done += 1
            print('  ok      %-40s %s' % (c['login'], res.get('message', '')))
        except Exception as err:           # noqa: BLE001 — one person at a time
            print('  FAILED  %-40s %s' % (c['login'], err))
    print('%d of %d converted' % (done, len(rows)))


def rollback(rpc, path):
    rows = json.load(open(path))
    for c in rows:
        try:
            rpc.call('pb.access', 'set_account_type', c['uid'], 'staff',
                     'rollback of %s' % os.path.basename(path))
            rpc.call('res.users', 'write', [c['uid']],
                     {'group_ids': [(6, 0, c['group_ids'])]})
            print('  restored %-40s' % c['login'])
        except Exception as err:           # noqa: BLE001
            print('  FAILED   %-40s %s' % (c['login'], err))


def backfill(rpc, do_apply):
    fields = rpc.call('hr.employee', 'fields_get', attributes=['type'])
    if 'pb_portal_user_id' not in fields:
        print('no pb_portal_user_id field on this database; nothing to do')
        return
    emps = rpc.call('hr.employee', 'search_read',
                    [['user_id', '=', False], ['pb_portal_user_id', '!=', False],
                     ['active', '=', True]],
                    fields=['name', 'pb_portal_user_id', 'company_id'])
    todo = []
    for e in emps:
        uid = e['pb_portal_user_id'][0]
        u = rpc.call('res.users', 'read', [uid],
                     fields=['share', 'active', 'login'])[0]
        if u['share'] and u['active']:
            todo.append((e['id'], e['name'], uid, u['login']))
        else:
            print('  skip    %-40s account is %s' % (
                e['name'], 'archived' if not u['active'] else 'a full account'))
    print('%d employee(s) to link' % len(todo))
    for eid, name, uid, login in todo:
        print('  LINK    %-40s -> %s' % (name, login))
    if not do_apply or not todo:
        return
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    path = 'tiers_backfill_%s_%s.json' % (rpc.db, stamp)
    json.dump([t[0] for t in todo], open(path, 'w'))
    print('rollback list written: %s (set user_id back to False)' % path)
    for eid, name, uid, login in todo:
        try:
            rpc.call('hr.employee', 'write', [eid], {'user_id': uid})
            print('  ok      %-40s' % name)
        except Exception as err:           # noqa: BLE001
            print('  FAILED  %-40s %s' % (name, err))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--rollback', metavar='FILE')
    ap.add_argument('--backfill', action='store_true')
    ap.add_argument('--reason', default='TIERS switch-over')
    args = ap.parse_args()
    env = {k: os.environ.get('PB_' + k) for k in ('URL', 'DB', 'LOGIN', 'PASSWORD')}
    missing = [k for k, v in env.items() if not v]
    if missing:
        sys.exit('set PB_%s in the environment' % ', PB_'.join(missing))
    rpc = Rpc(env['URL'], env['DB'], env['LOGIN'], env['PASSWORD'])
    if args.rollback:
        rollback(rpc, args.rollback)
    elif args.backfill:
        backfill(rpc, args.apply)
    elif args.apply:
        apply(rpc, args.reason)
    else:
        candidates(rpc)


if __name__ == '__main__':
    main()
