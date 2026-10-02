#!/usr/bin/env python3
"""Negative controls for the scenario emitter's validation rules.

    python3 docs/tutorial_poc/author/tools/test_scenario_rules.py

WHY THIS EXISTS
---------------
`gen_learn_data.py` refuses to write a content plane whose scenarios break the
rules of the mode matrix — an unguarded compute, an anchor nobody declares, a
screen that is not a replica. Every one of those refusals is a claim, and this
repository's standard is that a claim gets EXECUTED before it gets written
(ledger, Run D2). A validation nobody has ever seen fail is a validation
nobody knows is wired up: the six shipped scenarios are all valid, so the
authoring source alone can never exercise a single one of these paths.

So each rule gets a fixture that breaks exactly it, and this asserts the
generator exits 6 and names the right thing. The POSITIVE control runs last and
is the more important half — a validator that rejected everything would pass
all of the tests above it.

There is no odoo-bin on this machine and there is nothing here that needs one:
`content_scenarios` is a pure function of the dumped authoring tree.
"""
import io
import os
import sys
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_learn_data as gen                                      # noqa: E402

_DUMP = {}


def _shipped(name):
    """One table out of the real authoring source, loaded once."""
    if not _DUMP:
        _DUMP.update(gen.dump())
    return _DUMP.get(name) or {}


def _base_scenario(**over):
    """A minimal VALID scenario. Every fixture below is this with one thing
    wrong, so a failure names the rule rather than the fixture."""
    sc = {
        'key': 'sc_probe',
        'icon': 'compass',
        'line': 'payrun',
        'modes': ['watch'],
        'screens': ['runpayroll'],
        'name': {'en': 'Probe', 'vi': 'Thử nghiệm'},
        'tagline': {'en': 'A probe.', 'vi': 'Một phép thử.'},
        'entry': {'nav': 'pb_payrun_wizard.action_pb_payrun_wizard'},
        'steps': [{
            'key': 'look',
            'anchor': 'pw-division',
            'act': 'observe',
            'say': {'title': {'en': 'Look', 'vi': 'Nhìn'},
                    'body': {'en': 'At this.', 'vi': 'Vào đây.'}},
        }],
    }
    sc.update(over)
    return sc


def _run(scenario, input_anchors=None):
    """Feed one scenario through the emitter. Returns (exit_code, output).

    `inputAnchors` and `practiceAnchors` are the SHIPPED tables by default:
    both are read by rules under test, and a probe that supplied its own would
    be testing a world where the shipped ones do not exist.
    """
    data = {'scenarios': [scenario],
            'practiceAnchors': _shipped('practiceAnchors'),
            'inputAnchors': (_shipped('inputAnchors') if input_anchors is None
                             else input_anchors),
            'screenCtx': dict.fromkeys(
                ['runpayroll', 'payruns', 'payslips', 'import', 'importwizard',
                 'fullfinal', 'proration', 'retro', 'formula', 'structures',
                 'statutory', 'integrations', 'dashboard', 'approvals',
                 'employees', 'contracts', 'insights', 'explorer',
                 'workforcean', 'govreports'], {})}
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            gen.content_scenarios(data, gen.Bi())
        except SystemExit as exc:
            code = exc.code
    return code, buf.getvalue()


CASES = [
    (
        "a compute step with no guard at all",
        _base_scenario(steps=[{
            'key': 'compute', 'anchor': 'pw-compute', 'act': 'click',
            'say': {'title': {'en': 'Compute the payslips', 'vi': 'Tính lương'},
                    'body': {'en': 'Press it.', 'vi': 'Bấm đi.'}},
        }]),
        'must state guard',
    ),
    (
        "a compute step that declares guard: false",
        _base_scenario(steps=[{
            'key': 'compute', 'anchor': 'pw-compute', 'act': 'click',
            'guard': False,
            'say': {'title': {'en': 'Compute the payslips', 'vi': 'Tính lương'},
                    'body': {'en': 'Press it.', 'vi': 'Bấm đi.'}},
        }]),
        'guard: false on a control whose name says it',
    ),
    (
        "a bogus anchor",
        _base_scenario(steps=[{
            'key': 'look', 'anchor': 'pw-divisionn', 'act': 'observe',
            'say': {'title': {'en': 'Look', 'vi': 'Nhìn'},
                    'body': {'en': 'At this.', 'vi': 'Vào đây.'}},
        }]),
        'is in no block of anchors.json',
    ),
    (
        "an unknown replica screen",
        _base_scenario(modes=['watch', 'try'], screens=['runpayroll'],
                       entry={'nav': 'pb_payrun_wizard.action_pb_payrun_wizard',
                              'screen': 'runpayrol'}),
        'entry screen is not a replica screen',
    ),
    (
        "a step standing on a screen the scenario does not offer",
        _base_scenario(modes=['watch', 'try'],
                       entry={'nav': 'pb_payrun_wizard.action_pb_payrun_wizard',
                              'screen': 'runpayroll'},
                       steps=[{
                           'key': 'look', 'anchor': 'ps-list', 'act': 'observe',
                           'screen': 'payslips',
                           'say': {'title': {'en': 'Look', 'vi': 'Nhìn'},
                                   'body': {'en': 'At this.', 'vi': 'Vào đây.'}},
                       }]),
        'which the scenario does not list in `screens`',
    ),
    (
        "a nav nobody allowlisted",
        _base_scenario(entry={'nav': 'base.action_res_users'}),
        'entry nav is not in SCENARIO_NAV',
    ),
    (
        "an unknown mode",
        _base_scenario(modes=['watch', 'rehearse']),
        'unknown mode',
    ),
    (
        "a do-capable scenario that opens nowhere",
        _base_scenario(modes=['watch', 'do'], entry={}),
        'supports "do" but names no entry nav',
    ),
    (
        "a try-capable scenario with no replica screen",
        _base_scenario(modes=['watch', 'try'],
                       entry={'nav': 'pb_payrun_wizard.action_pb_payrun_wizard'}),
        'supports "try" but names no entry screen',
    ),
    (
        "an input step in a scenario with no replica",
        _base_scenario(steps=[{
            'key': 'type', 'anchor': 'pw-scope', 'act': 'input',
            'value': {'en': 'June 2026', 'vi': 'Tháng 6/2026'},
            'say': {'title': {'en': 'Type it', 'vi': 'Nhập vào'},
                    'body': {'en': 'Here.', 'vi': 'Ở đây.'}},
        }]),
        'needs a replica to type into',
    ),
    (
        "a guard on a step that cannot be pressed",
        _base_scenario(steps=[{
            'key': 'look', 'anchor': 'pw-division', 'act': 'observe',
            'guard': True,
            'say': {'title': {'en': 'Look', 'vi': 'Nhìn'},
                    'body': {'en': 'At this.', 'vi': 'Vào đây.'}},
        }]),
        'guard on a observe step means nothing',
    ),
    (
        "a scenario offered on no screen at all",
        _base_scenario(screens=[]),
        'names no screens',
    ),
    (
        "a scenario with no steps",
        _base_scenario(steps=[]),
        'no steps',
    ),
    # ---------------------------------------------------- LEARNOS Phase 5
    (
        "an input step pointed at a control that is not a field",
        _base_scenario(modes=['watch', 'try'],
                       entry={'nav': 'pb_payrun_wizard.action_pb_payrun_wizard',
                              'screen': 'runpayroll'},
                       steps=[{
                           'key': 'type', 'anchor': 'pw-summary', 'act': 'input',
                           'value': {'en': '1,200,000', 'vi': '1.200.000'},
                           'say': {'title': {'en': 'Type it', 'vi': 'Nhập vào'},
                                   'body': {'en': 'Here.', 'vi': 'Ở đây.'}},
                       }]),
        'is not declared in INPUT_ANCHORS',
    ),
    (
        "an input step with an anchor the replica draws but no field on",
        _base_scenario(modes=['watch', 'try'],
                       entry={'nav': 'pb_payrun_wizard.action_pb_payrun_wizard',
                              'screen': 'runpayroll'},
                       steps=[{
                           'key': 'type', 'anchor': 'pe-roster', 'act': 'input',
                           'value': {'en': 'x', 'vi': 'x'},
                           'screen': 'employees',
                           'say': {'title': {'en': 'Type it', 'vi': 'Nhập vào'},
                                   'body': {'en': 'Here.', 'vi': 'Ở đây.'}},
                       }]),
        'is not declared in INPUT_ANCHORS',
    ),
    (
        "a try-playable step pointed at a control the replica does not draw",
        _base_scenario(modes=['watch', 'try'],
                       entry={'nav': 'pb_payrun_wizard.action_pb_payrun_wizard',
                              'screen': 'runpayroll'},
                       steps=[{
                           'key': 'grid', 'anchor': 'grid-canvas', 'act': 'observe',
                           'say': {'title': {'en': 'Look', 'vi': 'Nhìn'},
                                   'body': {'en': 'At this.', 'vi': 'Vào đây.'}},
                       }]),
        'which the practice replica does not draw',
    ),
    (
        "a step declaring a mode its scenario does not offer",
        _base_scenario(steps=[{
            'key': 'look', 'anchor': 'pw-division', 'act': 'observe',
            'modes': ['try'],
            'say': {'title': {'en': 'Look', 'vi': 'Nhìn'},
                    'body': {'en': 'At this.', 'vi': 'Vào đây.'}},
        }]),
        'declares mode(s) the scenario does not offer',
    ),
    (
        "a step scoped to no mode at all",
        _base_scenario(steps=[{
            'key': 'look', 'anchor': 'pw-division', 'act': 'observe',
            'modes': [],
            'say': {'title': {'en': 'Look', 'vi': 'Nhìn'},
                    'body': {'en': 'At this.', 'vi': 'Vào đây.'}},
        }]),
        'no modes',
    ),
]

# The INPUT_ANCHORS table is itself validated, and it is validated against the
# REPLICA rather than against the registry — a declared field the replica does
# not draw would let every rule above pass while the learner types into
# nothing. These two probes replace the shipped table instead of the scenario.
TABLE_CASES = [
    (
        "a declared field the replica does not draw",
        {'rep-nosuchfield': {'kind': 'text'}},
        'the replica draws no control with that anchor',
    ),
    (
        "a declared field with a kind nothing implements",
        {'rep-impfix': {'kind': 'currency'}},
        'kind must be one of',
    ),
]


def main():
    failures = []
    for label, scenario, needle in CASES:
        code, out = _run(scenario)
        if code != 6:
            failures.append('%s: expected exit 6, got %r' % (label, code))
        elif needle not in out:
            failures.append('%s: refused for the wrong reason.\n      wanted: %s'
                            '\n      got: %s' % (label, needle, out.strip()))
        else:
            print('  ✓ refused: %s' % label)

    for label, table, needle in TABLE_CASES:
        code, out = _run(_base_scenario(), input_anchors=table)
        if code != 6:
            failures.append('%s: expected exit 6, got %r' % (label, code))
        elif needle not in out:
            failures.append('%s: refused for the wrong reason.\n      wanted: %s'
                            '\n      got: %s' % (label, needle, out.strip()))
        else:
            print('  ✓ refused: %s' % label)

    # THE POSITIVE CONTROL, and it is the one that matters: everything above is
    # satisfied by a validator that says no to every input.
    code, out = _run(_base_scenario())
    if code != 0:
        failures.append('the VALID fixture was refused (exit %r):\n%s' % (code, out))
    else:
        print('  ✓ accepted: a valid scenario')

    if failures:
        print('\n%d scenario-rule control(s) FAILED:' % len(failures))
        for f in failures:
            print('  ✗ %s' % f)
        return 1
    print('\n✓ %d refusals and 1 acceptance — the scenario rules are wired up.'
          % (len(CASES) + len(TABLE_CASES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
