# -*- coding: utf-8 -*-
"""The one line of code that makes P5's review machine do this phase's work.

P5 shipped `pb.probation.review` with a `kind` field — `probation` or
`conversion` — wrote every method against the FIELD rather than against the word
"probation", and left `_on_verdict()` deliberately empty and deliberately LAST:
by the time it runs, the state is on the employee record, the letter exists and
any next round is scheduled, so an override sees a finished world.

This is that override, and it is careful about exactly two things.

ONE: IT ONLY EVER ACTS ON `kind == 'conversion'`. A probation verdict must
behave on this database exactly as it behaved before this module was installed
— P5's cast of test employees is still on it, mid-flow, and a contract decision
firing on somebody's trial period would create a contract nobody asked for.

TWO: IT NEVER RAISES. P5's docstring says so in as many words, and the reason
is that the verdict has already been written and the person has already been
sent a letter about it. An exception here would roll that back and leave a
manager who has been told "confirmed" looking at a review that is still open.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

#: THE SAME MACHINE, ASKED A DIFFERENT QUESTION — SO IT USES DIFFERENT WORDS.
#: P5's four emails say "trial period" and "probation" in their subjects and
#: their prose, which is right for a trial period and wrong for somebody being
#: considered for a permanent contract after two years on fixed terms. The first
#: live conversion told a manager "…'s trial period ends soon — who should we
#: ask?", which is wrong in a way somebody would have to apologise for.
#:
#: Swapped HERE rather than by rewording P5's own seeds, because those are
#: `noupdate="1"` records on a live database with live reviews on them and
#: reloading one takes the `ir_model_data` dance (R57) across every probation
#: review running. Absent this module, P5 behaves exactly as it did.
CONVERSION_MAIL = {
    'pb_probation.mail_template_nominate_peers':
        'pb_contract_lifecycle.mail_template_conversion_nominate',
    'pb_probation.mail_template_review_ready':
        'pb_contract_lifecycle.mail_template_conversion_ready',
    'pb_probation.mail_template_verdict_hr':
        'pb_contract_lifecycle.mail_template_conversion_verdict',
    'pb_probation.mail_template_verdict_fail_hr':
        'pb_contract_lifecycle.mail_template_conversion_notpassed',
}


class PbProbationReview(models.Model):
    _inherit = 'pb.probation.review'

    def _mail(self, xmlid, addresses):
        """P5's sender, with this phase's wording for a conversion."""
        if self.kind == 'conversion':
            xmlid = CONVERSION_MAIL.get(xmlid, xmlid)
        return super()._mail(xmlid, addresses)

    def _has_contract_decision(self):
        """Is a contract decision waiting on this evaluation?

        The test for "this module owns what happens next". A conversion review
        somebody opened on its own is still P5's, and behaves exactly as P5
        wrote it.
        """
        self.ensure_one()
        try:
            return bool(self.env['pb.contract.review'].sudo().search_count(
                [('review_id', '=', self.id)]))
        except Exception:               # noqa: BLE001
            return False

    def _prepare_letter(self, verdict):
        """For a conversion, the letter is the contract decision's or none.

        THE THREE PROBATION LETTERS ARE ALL WRONG FOR A CONVERSION, and one of
        them is harmful. "Confirmation of Employment" duplicates this phase's
        own "Made permanent" letter, which is the one carrying the new
        contract's start date. "Your trial period has been extended" writes a
        date nobody agreed. And the not-confirmed letter tells somebody who was
        being considered for a PERMANENT contract that their employment has not
        been confirmed and their trial period is ending — which is not what
        happened, and which contradicts this board's own promise that nothing
        is created and nobody is told they failed. The first live conversion
        that did not pass sent that letter.

        So: for a conversion this module is driving, P5 prepares nothing and
        this module sends the one letter that is true.
        """
        if self.kind == 'conversion' and self._has_contract_decision():
            _logger.info(
                'pb_contract_lifecycle: evaluation %s is a contract '
                'conversion — its letter comes from the contract decision, '
                'so no probation letter is prepared', self.id)
            return self.env['pb.hr.letter'].browse()
        return super()._prepare_letter(verdict)

    def action_verdict(self, verdict, strengths=None, improvements=None,
                       extension_months=None):
        """P5's verdict, without a conversion writing a trial period.

        A CONVERSION IS NOT A TRIAL PERIOD AND MUST NOT LEAVE ONE BEHIND.
        P5's three verdict handlers each write the employee's
        `pb_probation_state` — and the extend one also moves `trial_date_end`,
        which is the single in-place employment write ruling D1 carves out for
        probation. Run against a conversion those are false records: the first
        live conversion that did not pass left a two-year contractor's file
        reading "Trial period: Not passed", about a trial period they never
        had.

        Snapshotted and restored rather than forked. P5's handlers do six other
        useful things — the letter, the mails, the rating, the next round —
        and re-implementing them here to change one write would be a second
        copy of the machine this phase exists to reuse.
        """
        if self.kind != 'conversion':
            return super().action_verdict(
                verdict, strengths=strengths, improvements=improvements,
                extension_months=extension_months)
        emp = self.employee_id.sudo()
        was_state, was_trial = None, None
        try:
            was_state = emp.pb_probation_state
            was_trial = emp.trial_date_end
        except Exception:               # noqa: BLE001
            _logger.warning('pb_contract_lifecycle: could not read the trial '
                            'fields before evaluation %s', self.id,
                            exc_info=True)
        result = super().action_verdict(
            verdict, strengths=strengths, improvements=improvements,
            extension_months=extension_months)
        try:
            restore = {}
            if emp.pb_probation_state != was_state:
                restore['pb_probation_state'] = was_state
            if emp.trial_date_end != was_trial:
                restore['trial_date_end'] = was_trial
            if restore:
                emp.write(restore)
                _logger.info(
                    'pb_contract_lifecycle: evaluation %s was a contract '
                    'conversion, so employee %s keeps the trial record they '
                    'had', self.id, emp.id)
        except Exception:               # noqa: BLE001 — never undo a verdict
            _logger.exception(
                'pb_contract_lifecycle: could not put the trial record back '
                'after conversion evaluation %s', self.id)
        return result

    def _on_verdict(self, verdict):
        res = super()._on_verdict(verdict)
        # The guard, first and unconditional. `self.kind` is the whole test.
        if self.kind != 'conversion':
            return res
        try:
            decision = self.env['pb.contract.review'].sudo().search(
                [('review_id', '=', self.id)], limit=1)
            if not decision:
                # A conversion evaluation somebody opened by hand, with no
                # contract decision behind it. Not an error — P5's machine is
                # usable on its own — so it is logged and left alone.
                _logger.info(
                    'pb_contract_lifecycle: conversion evaluation %s has no '
                    'contract decision behind it; nothing to do', self.id)
                return res
            decision._on_conversion_verdict(verdict)
        except Exception:               # noqa: BLE001 — never undo a verdict
            _logger.exception(
                'pb_contract_lifecycle: could not act on the conversion '
                'verdict of evaluation %s', self.id)
        return res
