#!/usr/bin/env python3
"""What is waiting to be deployed, worked out from versions — no notes needed.

Compares, for every custom module (anything not in the server's own odoo git
clone):

  repo     the manifest version in this checkout
  files    the manifest version on the live server's disk
  <db>     ir_module_module.latest_version in each database

and prints only the modules where they disagree. A module is "pending" for a
database when that database's installed version is not the repo version.

    python3 tools/deploy_status.py            # every database
    python3 tools/deploy_status.py payobook   # just these databases

Workflow (owner ruling 2026-10-11): ship to `payobook` first, batch the rest
when told. The hand-kept list of what changed and why is
docs/deploy/PENDING.md; this script is the check that it is complete.

NOTE the server has ONE addons directory serving every database, so new
*code* reaches every database at the next restart. What stays pending per
database is the upgrade: views, data, translations, new fields.
"""
import ast
import json
import os
import subprocess
import sys

HOST = 'Payobook19v2'
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REMOTE = r'''
import ast, json, os, subprocess
ADDONS = '/odoo/odoo-server/addons'
std = set(subprocess.run(['git', '-C', '/odoo/odoo-server', 'ls-files', 'addons'],
                         capture_output=True, text=True).stdout.split())
std = {p.split('/')[1] for p in std if p.count('/') >= 2}
files = {}
for m in os.listdir(ADDONS):
    mf = os.path.join(ADDONS, m, '__manifest__.py')
    if m in std or not os.path.isfile(mf):
        continue
    try:
        files[m] = ast.literal_eval(open(mf).read()).get('version', '')
    except Exception:
        files[m] = '?'
dbs = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-Atc',
    "select datname from pg_database where not datistemplate and datname <> 'postgres' order by 1"],
    capture_output=True, text=True).stdout.split()
inst = {}
for db in dbs:
    out = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-d', db, '-Atc',
        "select name, latest_version from ir_module_module where state = 'installed'"],
        capture_output=True, text=True).stdout
    inst[db] = dict(l.split('|', 1) for l in out.splitlines() if '|' in l)
print(json.dumps({'std': sorted(std), 'files': files, 'dbs': dbs, 'inst': inst}))
'''


def norm(v):
    """Odoo prefixes the series: 1.7.0 and 19.0.1.7.0 are the same version."""
    v = (v or '').strip()
    parts = v.split('.')
    return '.'.join(parts[2:]) if len(parts) == 5 and parts[0] == '19' else v


def repo_versions(std):
    out = {}
    for m in os.listdir(REPO):
        mf = os.path.join(REPO, m, '__manifest__.py')
        if m in std or not os.path.isfile(mf):
            continue
        try:
            out[m] = ast.literal_eval(open(mf).read()).get('version', '')
        except Exception:
            out[m] = '?'
    return out


def last_commit(module):
    return subprocess.run(['git', '-C', REPO, 'log', '-1', '--format=%h %ad %s',
                           '--date=short', '--', module],
                          capture_output=True, text=True).stdout.strip()


def main():
    raw = subprocess.run(['ssh', HOST, 'sudo', 'python3', '-'], input=REMOTE,
                         capture_output=True, text=True, check=True).stdout
    live = json.loads(raw)
    dbs = [d for d in live['dbs'] if len(sys.argv) < 2 or d in sys.argv[1:]]
    repo = repo_versions(set(live['std']))
    rows = []
    for m, rv in sorted(repo.items()):
        installed = {db: live['inst'][db].get(m) for db in dbs}
        if not any(installed.values()):
            continue                      # not installed anywhere: not a deploy item
        fv = live['files'].get(m)
        files_stale = norm(fv) != norm(rv)
        behind = [db for db, v in installed.items() if v and norm(v) != norm(rv)]
        if files_stale or behind:
            rows.append((m, rv, fv, installed, files_stale, behind))
    if not rows:
        print('Nothing pending: every installed custom module matches the repo in %s.'
              % ', '.join(dbs))
        return
    print('%-28s %-16s %-16s %s' % ('module', 'repo', 'server files', '  '.join(dbs)))
    for m, rv, fv, installed, files_stale, behind in rows:
        cells = []
        for db in dbs:
            v = installed[db]
            cells.append(('-' if not v else ('ok' if db not in behind else norm(v))).ljust(len(db)))
        print('%-28s %-16s %-16s %s' % (m, norm(rv), (norm(fv) or 'missing')
                                        + (' *' if files_stale else ''), '  '.join(cells)))
        print('    last change: %s' % last_commit(m))
    print('\n* = code on the server is older than the repo (not uploaded yet).'
          '\nA version under a database = that database still needs the upgrade.')


if __name__ == '__main__':
    main()
