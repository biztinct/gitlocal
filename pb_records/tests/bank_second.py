# -*- coding: utf-8 -*-
"""UPDATES P3a — a test helper: bank details need a second person.

Fixtures that WRITE bank details (to test what the desk writes, not who
agrees to it) now have the bank part approved by whoever holds its seat —
never the proposer. Everything else about those tests is unchanged.
"""


def approve_bank(env, answer):
    """Approve every waiting bank part of a desk answer as its seat holder.
    Returns the number of parts approved."""
    done = 0
    Apply = env['pb.records.apply'].sudo()
    for part in (answer or {}).get('lanes') or []:
        if part.get('lane') != 'bank' or not part.get('pending'):
            continue
        rec = Apply.browse(part['apply_id'])
        request = rec.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(
            lambda s: s.status == 'open'
            and s.acting_user_id != rec._proposer())[:1]
        assert seat, 'no second person holds a seat on %s' % rec.name
        env['biz.approval.engine'].with_user(seat.acting_user_id).decide(
            request.id, step.key, 'approve')
        done += 1
    return done
