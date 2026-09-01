# -*- coding: utf-8 -*-
"""The buddy check now reads a state instead of a date.

P3 asked "is `trial_date_end` still ahead of today?", which was the only answer
available to it and which is wrong in two directions:

  * somebody whose trial was EXTENDED has a date in the future and is correctly
    excluded — but also somebody whose date was simply never cleared after they
    passed, who is not in a trial period at all and has been silently barred
    from being a buddy ever since;
  * somebody who did not pass has a date in the PAST and reads as eligible.

`pb_probation_state` answers the question directly, so this replaces that one
check with a read of it. Everything else P3 decided — the three verdicts, the
never-hide rule, the reason beside every name — is untouched.

THIS IS AN ADDITIVE OVERRIDE AND NOT AN EDIT OF P3. `check_candidate` is called
rather than re-implemented: the super() runs first, its verdict is taken, and
only the trial-period reason is replaced. The day P3 adds a sixth rule this
inherits it without a line changing here.
"""

import logging

from odoo import api, models, _

from .probation_common import PROBATION_STATE_LABEL

_logger = logging.getLogger(__name__)

#: The states that stop somebody being a buddy, and what to say about each.
#: `failed` is deliberately a FAIL and not a warning: asking somebody who has
#: just been told they are not being confirmed to look after a new joiner is
#: not a judgement call.
BUDDY_BLOCKED = {
    'in_probation': 'They are still in their own trial period.',
    'extended': 'Their own trial period has been extended.',
    'failed': 'Their own trial period was not passed.',
}


class PbBuddyNomination(models.Model):
    _inherit = 'pb.buddy.nomination'

    @api.model
    def check_candidate(self, employee, candidate):
        """P3's verdict, with the trial-period reason answered properly."""
        verdict = super().check_candidate(employee, candidate)
        if not candidate or not candidate.exists():
            return verdict
        try:
            state = candidate.sudo().pb_probation_state or ''
        except Exception:               # noqa: BLE001 — never empty a dialog
            _logger.debug('pb_probation: no trial state readable for %s',
                          candidate.id)
            return verdict

        # Drop P3's date-based sentence, whichever way it came out, and put
        # this module's answer in its place. Matched on the wording P3 ships,
        # because that is the only handle a reason dictionary gives — and if
        # the wording ever changes the worst case is one duplicated line rather
        # than a wrong verdict.
        reasons = [r for r in (verdict.get('reasons') or [])
                   if 'trial period' not in (r.get('text') or '').lower()]

        blocked = BUDDY_BLOCKED.get(state)
        if blocked:
            reasons.append({'level': 'fail', 'text': _(blocked)})
        elif state == 'na':
            # Not a rule of its own — P3 already refuses non-permanent staff by
            # employment type, and saying it twice makes the dialog read like
            # the check is confused.
            pass

        level = 'pass'
        for reason in reasons:
            if reason.get('level') == 'fail':
                level = 'fail'
                break
            if reason.get('level') == 'warn':
                level = 'warn'
        return {'level': level, 'reasons': reasons}


class HrEmployeeBuddyProbation(models.Model):
    _inherit = 'hr.employee'

    def pb_probation_chip(self):
        """The word the buddy dialog and the lens both put on a chip."""
        self.ensure_one()
        return PROBATION_STATE_LABEL.get(self.pb_probation_state or '', '')
