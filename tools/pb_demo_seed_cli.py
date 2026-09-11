# -*- coding: utf-8 -*-
"""Load, remove or inspect the demo world from the back end.

Run it inside an Odoo shell against the tenant you mean::

    sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell \\
        -c /etc/odoo-server.conf -d rize --no-http \\
        < tools/pb_demo_seed_cli.py

The action is taken from the ``PB_DEMO_ACTION`` environment variable — ``load``,
``remove``, ``status`` or ``mapping`` — because an Odoo shell script has no
argv of its own. ``status`` is the default, so running it by accident tells you
what is there rather than changing it.

THE SAME CODE THE BUTTON RUNS. This calls `pb.demo.seed.load_demo()` and
`remove_demo()`, which are exactly what the two buttons in Settings call. There
is no back-door path that can drift away from what a customer's administrator
gets — which is the only way "it worked from the script" stays a useful
sentence.
"""

import os
import sys

ACTION = (os.environ.get('PB_DEMO_ACTION') or 'status').strip().lower()
PROFILE = (os.environ.get('PB_DEMO_PROFILE') or 'rize_vn').strip()
CONFIG_CODE = (os.environ.get('PB_DEMO_CONFIG') or 'RIZE_VIETNAM').strip()


def _seed(env):
    seed = env.ref('pb_demo_seed.demo_seed_default', raise_if_not_found=False)
    if not seed:
        seed = env['pb.demo.seed'].search([], limit=1)
    if not seed:
        seed = env['pb.demo.seed'].create({'name': 'Demo data',
                                           'profile': PROFILE})
    return seed


def status(env):
    seed = _seed(env)
    print('Demo data   : %s' % dict(
        seed._fields['state'].selection)[seed.state])
    print('World       : %s' % seed.profile)
    print('Company     : %s' % seed.company_id.display_name)
    if seed.state == 'loaded':
        print('Loaded on   : %s by %s' % (seed.loaded_on,
                                          seed.loaded_by.display_name))
        print('Records     : %s' % seed.record_count)
        print('---')
        print(seed.summary or '')
    return seed


def load(env):
    seed = _seed(env)
    if seed.state == 'loaded':
        print('Already loaded. Run with PB_DEMO_ACTION=remove first.')
        return seed
    seed.profile = PROFILE
    summary = seed.load_demo()
    env.cr.commit()
    print('Loaded %s records.' % seed.record_count)
    print(summary)
    return seed


def remove(env):
    seed = _seed(env)
    if seed.state != 'loaded':
        print('Nothing loaded.')
        return seed
    removed, blocked = seed.remove_demo()
    env.cr.commit()
    print('Removed %s records.' % removed)
    if blocked:
        print('Could not remove %s:' % len(blocked))
        for line in blocked:
            print('  - %s' % line)
    return seed


def mapping(env):
    """Wire the Vietnam record profile onto one pay scheme."""
    config = env['hr.formula.config'].search([('code', '=', CONFIG_CODE)], limit=1)
    if not config:
        print('No pay scheme with code %s on this database.' % CONFIG_CODE)
        return None
    report = config.pb_apply_vn_mapping()[config.id]
    env.cr.commit()
    print('Scheme                 : %s' % report['config'])
    print('Columns newly mapped   : %s' % report['mapped'])
    print('Columns already mapped : %s' % report['already'])
    print('Contract components    : %s' % report['contract_components'])
    print('Columns added          : %s' % report['columns_added'])
    print('Value kinds corrected  : %s' % report['value_kinds'])
    if report['missing']:
        print('Columns the scheme does not have: %s'
              % ', '.join(sorted(set(report['missing']))))
    return report


ACTIONS = {'status': status, 'load': load, 'remove': remove,
           'mapping': mapping}

# NO `if __name__ == "__main__"` GUARD, deliberately. This file is piped into
# `odoo-bin shell`, which executes it line by line in a console namespace rather
# than importing it as a module, and whether that namespace calls itself
# `__main__` depends on which console Odoo found. An unconditional call is the
# only form that behaves the same under all of them.
_handler = ACTIONS.get(ACTION)
if not _handler:
    print('Unknown action %r. Use one of: %s'
          % (ACTION, ', '.join(sorted(ACTIONS))))
    sys.exit(1)
# `env` is injected by `odoo-bin shell`.
_handler(env)                                          # noqa: F821
