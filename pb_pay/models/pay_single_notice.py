# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Pay changes and pay reviews: only the person whose turn it is is told
(WORKFLOW-2 P5a, owner decision D26, 11 Nov).

WHAT WAS TRUE BEFORE (P2b). With a live approval route the engine tells the
people the route asks ("Your approval is needed" + a to-do on the request);
the area left exactly those people out of its own "A pay … is waiting for
you" to-do, and still gave it to up to ten OTHER people of the rung's group.

WHAT IS TRUE NOW. When the engine has proven it told somebody on the step
that is waiting (`tells_approver(record)`), the rest of the group is not
given the to-do either. They still see the request under Approvals ›
Everyone — so a person who could NOT open that view (no "looks after
approvals", HR manager or payroll manager rights, or not in the request's
company) keeps the to-do exactly as before. Without a route, with the
engine's message job off, or with the switch `biz_approval.single_notice`
at 0, nothing changes: `tells_approver` is False there.

When in doubt, send: any failure here returns everybody.
"""

import logging

_logger = logging.getLogger(__name__)


def pay_group_rest(record, users):
    """The part of `users` (the rung's group, minus anybody the engine
    already told) that still gets the area's to-do."""
    if not users:
        return users
    try:
        engine = record.env['biz.approval.engine']
        if not engine.tells_approver(record):
            return users
        if 'pb.approval.inbox' not in record.env:
            return users
        request = engine._latest_request(record)
        company = request.company_id
        Inbox = record.env['pb.approval.inbox']

        def sees_everyone(person):
            if company and company not in person.company_ids:
                return False
            return bool(Inbox.with_user(person)._can_org())
        quiet = users.filtered(sees_everyone)
        if quiet:
            _logger.info('single notice: %s — %s of the pay group not given '
                         'the to-do; the approval route tells the person '
                         'whose turn it is (D26; user ids %s)',
                         record, len(quiet), quiet.ids)
        return users - quiet
    except Exception:   # noqa: BLE001 — when in doubt, send
        _logger.exception('single notice: D26 check on %s failed; the whole '
                          'group gets the to-do', record)
        return users
