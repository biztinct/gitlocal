# -*- coding: utf-8 -*-
"""What a fleet suite does about the platform route (ledger AM100).

Phase 7 puts the nine destructive fleet doors on a route: pausing a customer,
setting the clock that ends their data, closing them down, starting or
stopping a rollout, changing what they pay for, switching a feature across the
estate, restoring one from a backup. By default two platform owners agree
before any of that happens.

These suites are about what those doors DO once somebody has agreed — that a
pause really shuts the door, that a rollout really walks its rings, that a
feature switch really reaches every customer. They are not about who agrees.

So each of them publishes, for its own company, the choice every platform is
allowed to make: **nobody checks this one**. That is a published route and not
a bypass — the door is still the door, the typed confirmation is still
required and still exercised, and every press is still recorded as a request.
The alternative — seating two platform owners with a backup in every fleet
fixture — would test the engine's seating rules over and over in a file about
rollout rings.
"""

#: Every process a fleet screen can raise.
FLEET_PROCESSES = ('tenant',)


def no_approval_needed(env, reason='Fleet suite: these cases are about the '
                                   'door, not about who agrees'):
    """Publish "No approval needed" for the platform process, here.

    Idempotent: the second call finds the published version and the binding
    already there and changes nothing, so calling it from `setUp` costs one
    search per case.
    """
    Seed = env['biz.approval.seed']
    for key in FLEET_PROCESSES:
        try:
            Seed.set_no_approval_needed(env.company, key, reason=reason)
        except Exception:       # noqa: BLE001 — a fixture must not die here
            pass
    return True
