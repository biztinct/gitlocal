# -*- coding: utf-8 -*-
"""What the drawer's own suites do about the contract route (ledger AM100).

Phase 7 puts a change to somebody's PAY — their wage, their dates, their
salary structure, any component — on a route. These three suites are about
what the drawer WRITES once somebody has agreed: which values it judges,
which it refuses and why, what it logs, what it puts back. They are not about
who agrees.

So each publishes, for its own company, the choice every company is allowed to
make: nobody checks this one. That is a published route and not a bypass — the
door is still the door, the write gate is still the write gate, and every save
is still recorded as a request. `test_cd4_approval.py` is the suite that
proves the routed path, and it deliberately does not take the lane.
"""


def no_approval_needed(env, reason='Contract drawer suite: these cases are '
                                   'about the write, not about who agrees'):
    """Publish "No approval needed" for contract changes, here. Idempotent."""
    Seed = env.get('biz.approval.seed')
    if Seed is None:
        return False
    for company in {env.company, env.user.company_id}:
        try:
            Seed.set_no_approval_needed(company, 'contract', reason=reason)
        except Exception:       # noqa: BLE001 — a fixture must not die here
            pass
    return True
