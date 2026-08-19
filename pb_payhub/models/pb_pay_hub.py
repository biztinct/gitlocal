# -*- coding: utf-8 -*-
"""The Pay Run hub's one server read: where is this month's payroll?

The period tracker is the organ Option B of the IA dossier was built around, and
the dossier's own verdict on it was that "stage tracking must be computed and
kept honest per period, or the WOW becomes a lie". So this file computes it from
the states that already exist, states nothing here invents, and says exactly
what each stage means — see `_STAGE_DOC` and the module README.

Read-only by construction. There is no `create`, no `write` and no `unlink` in
this model, and `pb_payhub/tests/test_payhub.py` asserts that: the tracker is
read on every hub mount and on every lens switch, and a surface that is read
often should not be able to write at all (W25/W41).
"""
import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

TOTAL_STAGES = 5

# ---------------------------------------------------------------------------
# THE HEURISTIC, in one place.
#
# A run's own stage comes from `hr.payslip.run.state`, whose vocabulary is
#   draft · level0 · level1 · level2 · done · cancel
# (`om_hr_payroll` ships draft/level1/level2/done/cancel; `pb_payruns` adds
# level0, the Payroll Officer tier, via `selection_add` — see
# `pb_payruns/models/hr_payslip_run.py`). Stage 5 is the only one that is NOT a
# run state: "delivered" is a `pb.payslip.delivery.batch` in state `done`
# hanging off the run (`pb_pay_delivery/models/payslip_delivery.py`), because
# `done` on a run means APPROVED and nothing more — a run can sit approved and
# unpaid indefinitely, and a tracker that called that "delivered" would be
# lying in the one direction that matters.
_RUN_STAGE = {
    'draft': 2,
    'level0': 3,
    'level1': 3,
    'level2': 3,
    'done': 4,          # promoted to 5 when a delivery batch has completed
}

_STAGE_DOC = {
    1: 'Not started — no pay run covers this month yet',
    2: 'Drafting — a run exists and is still being computed / edited',
    3: 'In approval — a run is sitting with the Officer, HR or Finance tier',
    4: 'Approved — every run is approved, none has been delivered yet',
    5: 'Delivered — payslips have been sent for every run of the period',
}


class PbPayHub(models.AbstractModel):
    _name = 'pb.pay.hub'
    _description = 'Payobook Pay Run hub — period tracker'

    # ------------------------------------------------------------------ dates
    @api.model
    def _period(self, ref=None):
        """[first, last] of `ref`'s calendar month. `ref` is a test seam."""
        d = ref or date.today()
        first = d.replace(day=1)
        last = first + relativedelta(months=1, days=-1)
        return first, last

    # ------------------------------------------------------------------- runs
    @api.model
    def _period_runs(self, first, last):
        """Runs OVERLAPPING the month, in the active companies, never cancelled.

        Overlapping rather than contained: a run is keyed by the period it pays
        for, and a mid-cycle advance or a 25th-to-24th cycle legitimately
        straddles a month boundary. A CANCELLED run is excluded outright — a
        rejected run is not a stage the period is at, it is a thing that did not
        happen (and its rejection is already on the Runs lens, in its own
        drawer).
        """
        Run = self.env['hr.payslip.run']
        dom = [('date_start', '<=', last), ('date_end', '>=', first),
               ('state', '!=', 'cancel')]
        if 'company_id' in Run._fields:
            dom.append(('company_id', 'in',
                        self.env.companies.ids or [self.env.company.id]))
        return Run.search(dom)

    @api.model
    def _delivered_run_ids(self, runs):
        """Run ids with at least one COMPLETED payslip delivery batch."""
        if not runs:
            return set()
        Batch = self.env.get('pb.payslip.delivery.batch')
        if Batch is None:
            # pb_pay_delivery is a hard dependency of this module, so this is
            # not a shrug at a missing feature — it is the honest answer on a
            # database where the model has been removed under us. Stage 5 then
            # simply never occurs, which is visibly conservative rather than
            # silently wrong.
            return set()
        done = Batch.search([('run_id', 'in', runs.ids), ('state', '=', 'done')])
        return set(done.mapped('run_id').ids)

    # ------------------------------------------------------------------ stage
    @api.model
    def _stage_for(self, run, delivered_ids):
        s = _RUN_STAGE.get(run.state, 2)
        if s == 4 and run.id in delivered_ids:
            return 5
        return s

    @api.model
    def _stage(self, runs, delivered_ids):
        """The period's stage = the LEAST advanced of its runs.

        This is the decision the rest of the tracker hangs off, so it is worth
        stating why it is a MINIMUM and not a maximum. A Vietnamese month here
        is six division runs, and "the period is delivered" has to mean all six
        went out — under a maximum, one delivered division would light the chip
        green while five thousand people were still unpaid. The minimum also
        makes the chip's CLICK meaningful: it lands on the lens where the work
        that is still outstanding lives, which is the only reason to make a
        status chip a door at all.

        Zero runs is stage 1, and that includes a month whose only runs were
        rejected: nothing stands for that month, which is exactly what stage 1
        says.
        """
        if not runs:
            return 1
        return min(self._stage_for(r, delivered_ids) for r in runs)

    # ------------------------------------------------------------------ facade
    @api.model
    def get_period_state(self, ref=None):
        """`{label, stage, total, ...}` for the current calendar month.

        `ref` (an ISO date string) exists for the tests, which cannot move the
        wall clock; the client never sends one.
        """
        if isinstance(ref, str) and ref:
            ref = date.fromisoformat(ref)
        first, last = self._period(ref)
        runs = self._period_runs(first, last)
        delivered = self._delivered_run_ids(runs)
        stage = self._stage(runs, delivered)
        return {
            'label': format_date(self.env, first, date_format='MMM y'),
            'stage': stage,
            'total': TOTAL_STAGES,
            'stage_label': _STAGE_DOC[stage],
            # what the chip is counting, so the tooltip can be specific and a
            # future reviewer can tell an empty month from a broken read
            'run_count': len(runs),
            'delivered_count': len(delivered),
            'date_start': first.isoformat(),
            'date_end': last.isoformat(),
        }

    @api.model
    def stage_documentation(self):
        """The heuristic, as data — read by the tests so the prose and the
        behaviour cannot drift into describing different things."""
        return {'run_states': dict(_RUN_STAGE), 'stages': dict(_STAGE_DOC),
                'total': TOTAL_STAGES}
