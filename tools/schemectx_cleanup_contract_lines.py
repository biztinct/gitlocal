# -*- coding: utf-8 -*-
"""SCHEMECTX P2 — take the stray contract components off the contracts.

WHY THIS EXISTS. Until this phase `hr.contract.create` gave every new contract
one line per row of `hr.contract.advantage.template`, a flat catalogue shared by
the whole database with no country and no scheme on it. On a tenant running more
than one payroll scheme that means Indian components sitting on Vietnamese
people's contracts and the other way round. The fan-out is gone from the code;
the lines it already made are still in the database, and this takes them out.

WHAT IT WILL AND WILL NOT DELETE (owner ruling 10b, and it is not negotiable).

  DELETED   a line whose code belongs to no scheme that pays this person, AND
            whose amount is 0 or empty, AND whose text value is empty.
  KEPT      every line that holds a non-zero amount or any text, whoever it
            belongs to. A value somebody typed, or a pay run wrote, is never
            deleted by a tidy-up. It stays on the contract and the drawer shows
            it under "Other values on this contract".
  KEPT      every line of a scheme that DOES pay this person, filled or not.
  SKIPPED   people no scheme covers — there is no answer for them, so nothing
            is touched.
  SKIPPED   archived contracts, and contracts that are not draft or running.

EVERY RUN WRITES ITS OWN UNDO. Before a single row is deleted the exact set is
written to a CSV with enough in it to put every line back, and `--restore` does
exactly that. The CSV is written by the dry run too, so the file that says what
would happen is the same file that undoes it.

USAGE (the service must be stopped — an Odoo shell wants the database to
itself; ledger: shell vs a running registry hangs)::

    sudo service odoo-server stop

    # 1. look
    sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell \\
        -c /etc/odoo-server.conf -d rztest --http-port=8199 \\
        --logfile=/tmp/cleanup.log < tools/schemectx_cleanup_contract_lines.py

    # 2. do it
    PB_CLEANUP_APPLY=1 sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell \\
        -c /etc/odoo-server.conf -d rztest --http-port=8199 \\
        --logfile=/tmp/cleanup.log < tools/schemectx_cleanup_contract_lines.py

    # 3. put it back, if it ever has to go back
    PB_CLEANUP_RESTORE=/root/schemectx_cleanup_rztest_20260919.csv \\
        sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell ... < ...

Environment switches (there are no command-line flags inside an Odoo shell):

  ``PB_CLEANUP_APPLY=1``     delete; without it nothing is written.
  ``PB_CLEANUP_RESTORE=<f>`` recreate every line listed in that CSV.
  ``PB_CLEANUP_CSV=<path>``  where to write the undo file. Default
                             ``/root/schemectx_cleanup_<db>_<YYYYMMDD>.csv``.
  ``PB_CLEANUP_LIMIT=<n>``   look at only the first n contracts (a rehearsal).

IT IS SAFE TO RUN TWICE. The second run finds nothing to do and says so.
"""

import csv
import logging
import os
from datetime import date

_logger = logging.getLogger('schemectx_cleanup')

APPLY = os.environ.get('PB_CLEANUP_APPLY') == '1'
RESTORE = os.environ.get('PB_CLEANUP_RESTORE') or ''
LIMIT = int(os.environ.get('PB_CLEANUP_LIMIT') or 0)

#: A contract that is finished, cancelled or archived is history. History is
#: not tidied up.
LIVE_STATES = ('draft', 'open')

CSV_COLUMNS = ('line_id', 'contract_id', 'contract_name', 'employee_id',
               'employee_name', 'template_id', 'code', 'amount', 'text_value',
               'value_type')


def csv_path(env):
    return os.environ.get('PB_CLEANUP_CSV') or (
        '/root/schemectx_cleanup_%s_%s.csv'
        % (env.cr.dbname, date.today().strftime('%Y%m%d')))


# =====================================================================
#  Reading: what would go
# =====================================================================
def survey(env, limit=0):
    """`(doomed, counts)` — the lines this run would delete, and the tally.

    One pass over the live contracts. The scope question is asked through
    `hr.formula.config.component_scope_for_employee`, the same method the
    contract drawer and the pay package card read, so this script can never
    have a different opinion about whose component something is.
    """
    Contract = env['hr.contract'].sudo()
    Config = env.get('hr.formula.config')
    counts = {'contracts_seen': 0, 'contracts_touched': 0, 'lines_doomed': 0,
              'lines_kept_value': 0, 'lines_kept_in_scheme': 0,
              'people_unassigned': 0, 'people_no_scheme_map': 0,
              'contracts_not_live': 0}

    if Config is None or not hasattr(Config, 'component_scope_for_employee'):
        print('  The payroll scheme engine is not installed on this database, '
              'so there is nothing to work out. Nothing was touched.')
        return [], counts

    domain = [('state', 'in', LIVE_STATES)]
    contracts = Contract.search(domain, order='id',
                                limit=limit or None)
    doomed = []
    for contract in contracts:
        counts['contracts_seen'] += 1
        employee = contract.employee_id
        if not employee:
            counts['people_unassigned'] += 1
            continue
        answer = Config.sudo().component_scope_for_employee(employee)
        if not answer or not answer.get('known'):
            counts['people_no_scheme_map'] += 1
            continue
        if not answer.get('schemes'):
            # Nobody's map reaches this person. There is no "outside the
            # scheme" without a scheme, so nothing here is safe to delete.
            counts['people_unassigned'] += 1
            continue
        codes = {c for c in (answer.get('codes') or set()) if c}
        hit = 0
        for line in contract.advantages_ids:
            code = (line.advantage_template_code
                    or (line.advantage_template_id.code
                        if line.advantage_template_id else '') or '')
            if code and code in codes:
                counts['lines_kept_in_scheme'] += 1
                continue
            value_type = getattr(line, 'value_type', 'amount') or 'amount'
            text = (getattr(line, 'text_value', '') or '').strip()
            amount = line.amount or 0.0
            # THE ONE TEST THAT MATTERS. Anything at all in the box and the
            # line stays, whichever scheme it came from.
            if text or abs(amount) > 1e-9:
                counts['lines_kept_value'] += 1
                continue
            doomed.append({
                'line_id': line.id,
                'contract_id': contract.id,
                'contract_name': contract.name or '',
                'employee_id': employee.id,
                'employee_name': employee.name or '',
                'template_id': line.advantage_template_id.id or 0,
                'code': code,
                'amount': amount,
                'text_value': text,
                'value_type': value_type,
            })
            hit += 1
        if hit:
            counts['contracts_touched'] += 1
    counts['lines_doomed'] = len(doomed)
    return doomed, counts


def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, '') for key in CSV_COLUMNS})
    return path


# =====================================================================
#  Writing: the delete, and the undo
# =====================================================================
def apply(env, doomed):
    """Delete in one statement per thousand, and say how many really went."""
    Advantage = env['hr.contract.advantage'].sudo()
    ids = [row['line_id'] for row in doomed]
    gone = 0
    for start in range(0, len(ids), 1000):
        chunk = Advantage.browse(ids[start:start + 1000]).exists()
        gone += len(chunk)
        chunk.unlink()
    env.cr.commit()
    return gone


def restore(env, path):
    """Put back exactly what a CSV says was taken, and nothing else.

    Idempotent: a line that is already there (same contract, same catalogue
    row) is left alone rather than duplicated.
    """
    Advantage = env['hr.contract.advantage'].sudo()
    with open(path, newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    made = skipped = missing = 0
    for row in rows:
        contract_id = int(row.get('contract_id') or 0)
        template_id = int(row.get('template_id') or 0)
        if not contract_id or not template_id:
            missing += 1
            continue
        if not env['hr.contract'].sudo().browse(contract_id).exists():
            missing += 1
            continue
        if Advantage.search_count([('contract_id', '=', contract_id),
                                   ('advantage_template_id', '=', template_id)]):
            skipped += 1
            continue
        vals = {'contract_id': contract_id,
                'advantage_template_id': template_id,
                'amount': float(row.get('amount') or 0.0)}
        if 'text_value' in Advantage._fields and (row.get('text_value') or ''):
            vals['text_value'] = row['text_value']
        Advantage.create(vals)
        made += 1
    env.cr.commit()
    print('  put back %s, already there %s, could not place %s'
          % (made, skipped, missing))
    return made


def report(counts, doomed, path):
    print('  contracts looked at ................ %s' % counts['contracts_seen'])
    print('  contracts with something to take .... %s' % counts['contracts_touched'])
    print('  lines that would go ................. %s' % counts['lines_doomed'])
    print('  lines kept — they hold a value ...... %s' % counts['lines_kept_value'])
    print('  lines kept — the scheme uses them ... %s' % counts['lines_kept_in_scheme'])
    print('  people skipped — no scheme pays them  %s' % counts['people_unassigned'])
    print('  people skipped — no scheme map ...... %s' % counts['people_no_scheme_map'])
    print('  undo file ........................... %s' % path)
    by_code = {}
    for row in doomed:
        by_code[row['code']] = by_code.get(row['code'], 0) + 1
    if by_code:
        print('  by component:')
        for code, number in sorted(by_code.items(), key=lambda kv: -kv[1])[:40]:
            print('      %-22s %s' % (code or '(no code)', number))


# =====================================================================
if 'env' in dir():                                 # inside an Odoo shell
    print('SCHEMECTX contract-component clean-up on %s%s'
          % (env.cr.dbname, '' if APPLY else '   (DRY RUN — nothing is written)'))
    if RESTORE:
        print('RESTORING from %s' % RESTORE)
        restore(env, RESTORE)
    else:
        doomed, counts = survey(env, LIMIT)
        path = write_csv(csv_path(env), doomed)
        report(counts, doomed, path)
        if APPLY and doomed:
            gone = apply(env, doomed)
            print('  DELETED %s lines. The undo file is %s' % (gone, path))
        elif APPLY:
            print('  nothing to delete.')
        else:
            print('  nothing was written. Set PB_CLEANUP_APPLY=1 to do it.')
    print('Done.')
