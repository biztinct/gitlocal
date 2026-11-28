# -*- coding: utf-8 -*-
"""WDGAP W3-B (owner ruling RN2) — READ-ONLY check, one database at a time.

Past renewals with NO link between the new contract and the old one (the
Contracts "Renew" button wrote none before W3-B; only the contract decisions
board did), and how many people would show the red "past the rule" warning on
their latest contract if those renewals WERE linked. Changes nothing: the
transaction is switched to READ ONLY before the first read (any write would
fail loudly) and rolled back at the end. No backfill exists anywhere.

Run it inside the server's shell, piped in on standard input:

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d <db> --no-http --max-cron-threads=0 \
        < /odoo/odoo-server/addons/pb_contract_rules/tools/renew_button_links_check.py

Optional: set WINDOW (days after the old contract ends; default 31) by
editing the line below on a copy.
"""
WINDOW = 31

env.cr.rollback()                                   # noqa: F821 (shell global)
env.cr.execute("SET TRANSACTION READ ONLY")         # noqa: F821
try:
    report = env['pb.contract.rule'].renew_link_report(window_days=WINDOW)  # noqa: F821
    print('=== %s: unlinked renewals (new contract within %s days of the old one '
          'ending) ===' % (env.cr.dbname, report['window_days']))  # noqa: F821
    print('company | person | old contract | old end | new contract | new start | '
          'gap days | rule | already joined by dates')
    for row in report['pairs']:
        print(' | '.join(str(x) for x in (
            row['company'], row['person'], row['old_contract'], row['old_end'],
            row['new_contract'], row['new_start'], row['gap_days'], row['rule'] or '-',
            'yes' if row['counted_by_dates'] else 'no')))
    print('pairs: %(pair_count)s, people: %(people)s' % report)
    print('red "past the rule" warning on their latest contract (extension of '
          '%(months)s months): now %(warning_now)s, if linked %(warning_if_linked)s'
          % report)
    print('would newly show it: %s' % (', '.join(report['newly_warned']) or 'nobody'))
finally:
    env.cr.rollback()                               # noqa: F821
