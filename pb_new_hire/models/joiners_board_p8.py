# -*- coding: utf-8 -*-
"""NEWHIRE P8 E — HR managers see the New joiners board.

The board (`pb.onboarding`) was gated on the Lifecycle roles; HR managers
without one saw a lock card (ledger NH30). The architect's ruling (2026-11-26):
NOT the Lifecycle Manager role (it also opens final settlements, the Vendors
board, contract reviews…), but a NEW narrow right, "New joiners board"
(`pb_new_hire.group_joiners_board`, implied by `hr.group_hr_manager`), that
opens only this board, its rows, the joiner drawer and the board's own
actions (choose / cover a buddy, run a step now).

HOW, without touching any Lifecycle access rule: a reader who holds ONLY the
narrow right (no Lifecycle role, not the administrator) runs the board's own
methods with the system's rights, inside the board's own scope —
the companies their login really opens (worked out BEFORE the switch, so a
forged company list in the request context is refused by the framework), and
only live joining checklists (`_scope`). Every id that comes from the screen
(a checklist, a step, a person) is checked against that scope first. The two
company-wide jobs (the daily run, the HR partner back-fill) stay the
Lifecycle team's. A Lifecycle role, or the administrator, takes the board's
own path exactly as before.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

BOARD_GROUP = 'pb_new_hire.group_joiners_board'
#: "This call is the New joiners board's own, for a narrow-right reader". An
#: object: no value a client sends can equal it.
_BOARD = object()
_BOARD_CTX = 'pbnh_joiners_board'


class PbOnboardingNH(models.AbstractModel):
    _inherit = 'pb.onboarding'

    # ------------------------------------------------------------ gates
    @api.model
    def _pbnh_board_only(self):
        """True for a reader with the narrow right and no Lifecycle role."""
        user = self.env.user
        if not user or user._is_public() or not user.has_group(BOARD_GROUP):
            return False
        return not super()._can_read()

    @api.model
    def _can_read(self):
        return super()._can_read() or self._pbnh_board_only()

    @api.model
    def _can_write(self):
        return super()._can_write() or self._pbnh_board_only()

    @api.model
    def _pbnh_board(self):
        """This board with the system's rights, held to the reader's own
        companies (validated now, before the switch)."""
        companies = self.env.companies.ids or [self.env.company.id]
        return self.with_context(allowed_company_ids=companies,
                                 **{_BOARD_CTX: _BOARD}).sudo()

    @api.model
    def _pbnh_check_case(self, board, case_id):
        Case = board.env['pb.journey.case']
        if not Case.search_count(board._scope() + [('id', '=', int(case_id or 0))], limit=1):
            raise AccessError(_("New joiners are looked after by the HR team."))

    @api.model
    def _pbnh_check_employee(self, board, employee_id):
        Case = board.env['pb.journey.case']
        if not Case.search_count(board._scope() + [('employee_id', '=', int(employee_id or 0))],
                                 limit=1):
            raise AccessError(_("New joiners are looked after by the HR team."))

    # ------------------------------------------------------------ reads
    @api.model
    def get_board(self):
        if self._pbnh_board_only():
            return super(PbOnboardingNH, self._pbnh_board()).get_board()
        return super().get_board()

    @api.model
    def pbf_layout(self):
        if self._pbnh_board_only():
            return super(PbOnboardingNH, self._pbnh_board()).pbf_layout()
        return super().pbf_layout()

    @api.model
    def pbf_counts(self, *args, **kwargs):
        if self._pbnh_board_only():
            return super(PbOnboardingNH, self._pbnh_board()).pbf_counts(*args, **kwargs)
        return super().pbf_counts(*args, **kwargs)

    @api.model
    def pbf_columns(self, *args, **kwargs):
        if self._pbnh_board_only():
            return super(PbOnboardingNH, self._pbnh_board()).pbf_columns(*args, **kwargs)
        return super().pbf_columns(*args, **kwargs)

    @api.model
    def pbf_export_table(self, *args, **kwargs):
        if self._pbnh_board_only():
            return super(PbOnboardingNH, self._pbnh_board()).pbf_export_table(*args, **kwargs)
        return super().pbf_export_table(*args, **kwargs)

    @api.model
    def get_joiners_page(self, *args, **kwargs):
        if self._pbnh_board_only():
            return super(PbOnboardingNH, self._pbnh_board()).get_joiners_page(*args, **kwargs)
        return super().get_joiners_page(*args, **kwargs)

    @api.model
    def get_joiner(self, case_id):
        if self._pbnh_board_only():
            board = self._pbnh_board()
            self._pbnh_check_case(board, case_id)
            return super(PbOnboardingNH, board).get_joiner(case_id)
        return super().get_joiner(case_id)

    @api.model
    def buddy_candidates(self, employee_id, term=None):
        if self._pbnh_board_only():
            board = self._pbnh_board()
            self._pbnh_check_employee(board, employee_id)
            return super(PbOnboardingNH, board).buddy_candidates(employee_id, term=term)
        return super().buddy_candidates(employee_id, term=term)

    @api.model
    def get_settings(self):
        if self._pbnh_board_only():
            out = super(PbOnboardingNH, self._pbnh_board()).get_settings()
            out['can_write'] = False            # the cog's settings stay the Lifecycle team's
            return out
        return super().get_settings()

    # ------------------------------------------------------------ the board's own actions
    @api.model
    def buddy_choose(self, employee_id, candidate_id, case_id=None):
        if self._pbnh_board_only():
            board = self._pbnh_board()
            self._pbnh_check_employee(board, employee_id)
            if case_id:
                self._pbnh_check_case(board, case_id)
            return super(PbOnboardingNH, board).buddy_choose(employee_id, candidate_id, case_id)
        return super().buddy_choose(employee_id, candidate_id, case_id)

    @api.model
    def buddy_temp(self, employee_id, temp_id, date_from=None, date_to=None):
        if self._pbnh_board_only():
            board = self._pbnh_board()
            self._pbnh_check_employee(board, employee_id)
            return super(PbOnboardingNH, board).buddy_temp(employee_id, temp_id, date_from, date_to)
        return super().buddy_temp(employee_id, temp_id, date_from, date_to)

    @api.model
    def run_step_now(self, task_id):
        if self._pbnh_board_only():
            board = self._pbnh_board()
            task = board.env['pb.journey.task'].browse(int(task_id or 0)).exists()
            self._pbnh_check_case(board, task.case_id.id if task else 0)
            return super(PbOnboardingNH, board).run_step_now(task_id)
        return super().run_step_now(task_id)

    @api.model
    def backfill_hrbp(self):
        if self._pbnh_board_only():
            raise AccessError(_("Filling in HR partners for everybody is for the lifecycle team."))
        return super().backfill_hrbp()

    @api.model
    def run_automation(self):
        if self._pbnh_board_only():
            raise AccessError(_("The daily run is for the lifecycle team."))
        return super().run_automation()


class PbJourneysNH(models.AbstractModel):
    """The joiner drawer reads its steps through `pb.journeys.get_case`,
    whose own gate is the Lifecycle roles. It opens for the board's own call
    only (the context marker is an object no request can carry)."""
    _inherit = 'pb.journeys'

    @api.model
    def _can_read(self):
        if self.env.context.get(_BOARD_CTX) is _BOARD and self.env.user.has_group(BOARD_GROUP):
            return True
        return super()._can_read()
