# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Salary-category code buckets (mirror pb_hr_workforce payroll_report).
NET_CODES = ('NET',)
GROSS_CODES = ('GROSS',)
DED_CODES = ('DED', 'DEDUCTION', 'COMP')

# ---------------------------------------------------------------- Phase L
# Approval chain: draft → level0 (Officer) → level1 (HR) → level2 (Finance/GM)
# → done, with cancel reachable from any pending tier.
#
# state -> (group that may ADVANCE it, human role name). This map is the SINGLE
# tier truth: the model-side gate (_pb_require_tier), the kanban button flags
# and the Approvals cockpit all read it, so button visibility can never disagree
# with enforcement — and visibility is NEVER the guard (C18.17). Every advance /
# cancel entry point runs the gate as its first line, so a raw call_kw at
# action_payslip_run_level1_done hits exactly the same wall as the button.
PB_TIER = {
    'level0': ('pb_hr_payroll_base.group_payroll_base_officer', 'Payroll Officer'),
    'level1': ('pb_hr_payroll_base.group_payroll_base_manager', 'HR Manager'),
    'level2': ('pb_hr_payroll_base.group_payroll_final_approver', 'Finance / GM'),
}
PB_PENDING_STATES = ('level0', 'level1', 'level2')

# C18.24: a state machine is decorative unless write() enforces it. The tier
# gates above guard the ACTIONS; without this, anyone holding plain write access
# to hr.payslip.run could call_kw `write({'state': 'done'})` and skip every tier
# (proven live before this guard existed). The key is a module-level object()
# IDENTITY — a client-supplied context value can never equal it, whereas a plain
# boolean flag would be forgeable through the call_kw context merge.
_PB_CHAIN_KEY = 'pb_chain_state_write'
_PB_CHAIN_TOKEN = object()
# EVERY state value is sealed on write: a raw call_kw write to 'cancel' would
# kill a run awaiting Finance without the owning tier or any testimony, and a
# raw write to 'draft' would undo a Finance decision — the exact holes the
# reject/reset gates exist to close (review finding L-2). All state changes ride
# a chain method, which attaches the sentinel; demo/cleanup paths run as
# admin/su, which the seal already exempts. The tuple below is the CREATE guard:
# a run may be born in draft, never mid-chain or decided.
_PB_BORN_SEALED = ('level0', 'level1', 'level2', 'done', 'cancel')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Index the run FK — every cockpit aggregates payslips per run; without this
    # the SQL roll-ups seq-scan the payslip table as volume grows.
    payslip_run_id = fields.Many2one(index=True)


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # Index the slip FK — payslip-line aggregations join on this; essential for
    # fast roll-ups as line volume reaches the millions.
    slip_id = fields.Many2one(index=True)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    # Always show the full pipeline as columns (even empty Officer/HR/Finance
    # stages), like the old board — native kanban hides empty selection groups
    # otherwise.
    #
    # Phase L inserts the Payroll Officer tier through selection_add so the
    # legacy om_hr_payroll base field stays byte-untouched; the ('level1',)
    # anchor positions level0 immediately BEFORE the HR tier. Existing state
    # KEYS are frozen downstream contracts ('done' is the approved signal read
    # by pb_pay_delivery and payroll analytics) — nothing is renamed.
    state = fields.Selection(
        selection_add=[('level0', 'Payroll Officer pending'), ('level1',)],
        ondelete={'level0': 'set draft'},
        group_expand='_pb_group_expand_state')

    # Rejection testimony (who refused the run, why, when) — written only by
    # action_payslip_run_cancel below, readonly everywhere else.
    pb_reject_note = fields.Char(string='Rejection reason', readonly=True, copy=False)
    pb_reject_uid = fields.Many2one('res.users', string='Rejected by', readonly=True, copy=False)
    pb_reject_date = fields.Datetime(string='Rejected on', readonly=True, copy=False)

    @api.model
    def _pb_group_expand_state(self, values, domain):
        return ['draft', 'level0', 'level1', 'level2', 'done']

    # STORED: computed once when the run's payslips change, read instantly forever.
    # Aggregating every payslip line at read time does not scale (a 600k-row
    # roll-up spills to disk on a small box and takes seconds per cockpit load).
    pb_employee_count = fields.Integer(
        string='Employees', compute='_compute_pb_totals', store=True)
    pb_total_net = fields.Monetary(
        string='Total Net', compute='_compute_pb_totals',
        currency_field='pb_currency_id', store=True, index=True)
    pb_total_gross = fields.Monetary(
        string='Total Gross', compute='_compute_pb_totals',
        currency_field='pb_currency_id', store=True)
    pb_total_deductions = fields.Monetary(
        string='Total Deductions', compute='_compute_pb_totals',
        currency_field='pb_currency_id', store=True)
    # VALUEKIND P5 — what the employer pays ON TOP of gross, which used to be
    # summed into Deductions because it shares the `COMP` category with them.
    # It is not taken off anybody's pay and it never belonged there.
    pb_total_employer_cost = fields.Monetary(
        string='Employer Cost', compute='_compute_pb_totals',
        currency_field='pb_currency_id', store=True)
    # VALUEKIND P5 — how many payslips here were computed on nothing but scheme
    # defaults. On the reference tenant a run of 36 reported a gross of
    # ₫243,000,000 and a KPI band that looked perfectly healthy; every one of
    # the 54 inputs had resolved to `src: none`, and the ₫243m was one
    # component's default value repeated 36 times. Payroll that ran on no data
    # must not be able to look like payroll that ran.
    pb_unsourced_count = fields.Integer(
        string='Payslips With No Source Data', compute='_compute_pb_totals',
        store=True)

    pb_currency_id = fields.Many2one(
        'res.currency', compute='_compute_pb_totals', store=True)
    # Division key (from the run's payslips' formula config) — powers the board
    # division filter. Empty for traditional structure-based payroll.
    pb_division = fields.Char(
        string='Division', compute='_compute_pb_division', store=True, index=True)
    # Human-readable division for the kanban card chip (e.g. "manufacturing" ->
    # "Manufacturing", "corporate_office" -> "Corporate Office"). Empty for plain
    # structure-based payroll, where the card falls back to the journal name.
    pb_division_label = fields.Char(
        string='Division (label)', compute='_compute_pb_division', store=True)

    @api.depends('slip_ids.formula_config_id')
    def _compute_pb_division(self):
        for run in self:
            div = ''
            for s in run.slip_ids:
                cfg = s.formula_config_id
                d = getattr(cfg, 'pb_division', '') if cfg else ''
                if d:
                    div = d
                    break
            run.pb_division = div
            run.pb_division_label = div.replace('_', ' ').title() if div else ''

    # `category_id` belongs here: the sums below are grouped BY category, so a
    # line moving from "Other" to "Deduction" changes every figure in the band
    # while the amounts stay untouched. Without it, re-categorising a scheme
    # left the stored KPIs reporting the old grouping until something else
    # happened to touch a total. `component_detail` lives in the formula engine,
    # which this module does not depend on, so it cannot be named here — it is
    # written at the same moment as the category on both paths that set it, and
    # this trigger covers that write.
    #: Category codes that still mean something when a line carries no pay role.
    _PB_CATEGORY_BUCKETS = ('NET', 'GROSS', 'DED', 'DEDUCTION', 'COMP',
                            'BASIC', 'ALW')

    @api.model
    def _pb_bucket_sql(self, role_aware):
        """Which KPI band a payslip line belongs in, as a SQL expression.

        VALUEKIND P5 — the bands used to come from
        `hr_salary_rule_category.code` alone, and on a scheme built by importing
        a workbook that code is whatever the workbook's own headings implied.
        On ABM every employer contribution shares the `COMP` category with the
        employee's deductions, so `Total Cost to Employer` and `SI-HI-UI Total
        21.5%` were counted as money taken off somebody's pay. They are not:
        they are what the company pays ON TOP of gross.

        The scheme already knows the difference — it derives it from its own
        net-pay formula and stamps it on the line at creation
        (`hr.payslip.line.pay_role`). Read that first, and fall back to the
        category only for lines written before the stamp existed, so an existing
        tenant's figures never move under it without a recompute.

        `info` and `mixed` deliberately return NULL: a component counted in
        hours is not an amount, and a component that is both added and taken off
        has no single band. Both are dropped from every money figure here.

        Note `employer_cost` gets a bucket of its OWN (`ERCOST`) rather than
        reusing `COMP`. A line written before the stamp existed still lands in
        `COMP` through the fallback, and `COMP` still means exactly what it
        meant then — part of the deductions figure. That is the whole of the
        promise that an existing tenant's numbers do not move until the run is
        recomputed: the separation only happens for lines that actually say
        which side they are on.
        """
        if not role_aware:
            return ("CASE WHEN c.code IN %s THEN c.code END"
                    % (str(self._PB_CATEGORY_BUCKETS),))
        return ("""
            CASE pl.pay_role
                WHEN 'earning'       THEN 'GROSS'
                WHEN 'deduction'     THEN 'DED'
                WHEN 'net'           THEN 'NET'
                WHEN 'employer_cost' THEN 'ERCOST'
                WHEN 'info'          THEN NULL
                WHEN 'mixed'         THEN NULL
                ELSE (CASE WHEN c.code IN %s THEN c.code END)
            END""" % (str(self._PB_CATEGORY_BUCKETS),))

    @api.depends('slip_ids', 'slip_ids.line_ids', 'slip_ids.line_ids.total',
                 'slip_ids.line_ids.category_id', 'slip_ids.state')
    def _compute_pb_totals(self):
        # Aggregate in SQL — iterating slip_ids.line_ids through the ORM reads
        # hundreds of thousands of records at scale and hangs the kanban.
        default_cur = self.env.company.currency_id
        for run in self:
            run.pb_employee_count = 0
            run.pb_total_net = run.pb_total_gross = run.pb_total_deductions = 0.0
            run.pb_total_employer_cost = 0.0
            run.pb_unsourced_count = 0
            company = getattr(run, 'company_id', False) or self.env.company
            run.pb_currency_id = company.currency_id or default_cur
        run_ids = [r.id for r in self if r.id]
        if not run_ids:
            return
        # This compute reads the tables directly, so anything still sitting in
        # the ORM's write buffer is invisible to it — and a recompute triggered
        # by the very write that has not landed yet is the normal case, not an
        # exotic one. Attaching payslips to a run and reading its totals in the
        # same transaction (the Run Payroll wizard does exactly that) returned
        # zeros for that reason alone.
        self.env['hr.payslip'].flush_model(['payslip_run_id', 'state'])
        line_fields = ['slip_id', 'category_id', 'total']
        # NETROLE — the flag lives in `pb_hr_payroll_formula` (the payslip-line
        # extension that already carries report_visible/component_type). This
        # cockpit does not depend on the formula engine, so the column may
        # genuinely be absent; when it is, the sums are exactly what they were.
        detail_aware = 'component_detail' in self.env['hr.payslip.line']._fields
        if detail_aware:
            line_fields.append('component_detail')
        # VALUEKIND P5 — the same column the Analytics Explorer switched to, for
        # the same reason. See `_pb_bucket_sql`.
        role_aware = 'pay_role' in self.env['hr.payslip.line']._fields
        if role_aware:
            line_fields.append('pay_role')
        self.env['hr.payslip.line'].flush_model(line_fields)
        cr = self.env.cr
        cr.execute("""
            SELECT p.payslip_run_id, count(*)
            FROM hr_payslip p
            WHERE p.payslip_run_id IN %s AND p.state != 'cancel'
            GROUP BY p.payslip_run_id
        """, (tuple(run_ids),))
        counts = dict(cr.fetchall())
        # Payslips computed entirely on defaults. The column lives in the
        # formula engine, which this cockpit does not depend on, so it may
        # genuinely be absent — when it is, the banner simply never shows.
        unsourced = {}
        if 'pb_sourced_inputs' in self.env['hr.payslip']._fields:
            self.env['hr.payslip'].flush_model(['pb_sourced_inputs'])
            cr.execute("""
                SELECT p.payslip_run_id, count(*)
                FROM hr_payslip p
                WHERE p.payslip_run_id IN %s AND p.state != 'cancel'
                  AND COALESCE(p.pb_sourced_inputs, 0) = 0
                  AND p.calculation_method = 'formula'
                  -- A payslip with no provenance blob PREDATES the recording of
                  -- it, which is a different statement from "this payslip
                  -- sourced nothing" and no reader may collapse the two. The
                  -- 19.0.1.97.0 migration counts every blob that does exist, so
                  -- what is left here is genuinely unmeasurable, not zero.
                  AND p.formula_input_sources IS NOT NULL
                  AND p.formula_input_sources <> ''
                GROUP BY p.payslip_run_id
            """, (tuple(run_ids),))
            unsourced = dict(cr.fetchall())
        # NETROLE — a component that is folded into a roll-up is counted through
        # the roll-up, never twice. `SI-HI-IU Total 10.5%`, `Monthly PIT` and
        # `Total Deduction` are all subtracted from net pay, but the third one
        # IS the first two plus one more; summing all three is how ABM's June
        # run reported ₫5,058,029,390 of deductions against ₫1.9bn of gross.
        # Net is exempt: net pay is one component, never a roll-up of others.
        # A line created before any classification has the flag NULL, so every
        # existing tenant's figures are bit-for-bit what they were.
        net_clause = ("pl.pay_role = 'net' OR c.code = 'NET'"
                      if role_aware else "c.code = 'NET'")
        detail_clause = ("AND ((" + net_clause + ") "
                         "OR pl.component_detail IS NOT TRUE)"
                         if detail_aware else "")
        bucket = self._pb_bucket_sql(role_aware)
        cr.execute("""
            SELECT p.payslip_run_id, """ + bucket + """ AS bucket,
                   COALESCE(SUM(pl.total), 0)
            FROM hr_payslip_line pl
            JOIN hr_payslip p ON p.id = pl.slip_id AND p.state != 'cancel'
            JOIN hr_salary_rule_category c ON c.id = pl.category_id
            WHERE p.payslip_run_id IN %s
              AND """ + bucket + """ IS NOT NULL
              """ + detail_clause + """
            GROUP BY p.payslip_run_id, 2
        """, (tuple(run_ids),))
        agg = {}
        for rid, code, total in cr.fetchall():
            agg.setdefault(rid, {})[code] = total or 0.0
        for run in self:
            d = agg.get(run.id, {})
            run.pb_employee_count = counts.get(run.id, 0)
            run.pb_unsourced_count = unsourced.get(run.id, 0)
            run.pb_total_net = d.get('NET', 0.0)
            # A scheme built by importing a payroll workbook rarely has a
            # component filed under "Gross" — it has a basic and a list of
            # allowances, and gross is their sum. Reading only 'GROSS' showed
            # ₫0 next to ₫1.9bn of basic pay on ABM's June run.
            run.pb_total_gross = d.get('GROSS') or (
                d.get('BASIC', 0.0) + d.get('ALW', 0.0))
            # COMP stays in this sum, unchanged. A line in that bucket is one
            # nothing has classified — on such a run, the reference tenant's
            # whole deductions KPI is COMP lines, and dropping the bucket would
            # replace a wrong number with a blank one. VALUEKIND P5 does not
            # move that money; it gives a line that DOES know it is employer
            # cost somewhere else to go.
            run.pb_total_deductions = abs(d.get('DED', 0.0) + d.get('DEDUCTION', 0.0)
                                          + d.get('COMP', 0.0))
            run.pb_total_employer_cost = abs(d.get('ERCOST', 0.0))

    # ---- context-aware permission flags for kanban card buttons ----
    # NOTE: these are COSMETIC. Enforcement lives in _pb_require_tier below;
    # both read _pb_user_roles so they can never drift apart.
    pb_can_submit = fields.Boolean(compute='_compute_pb_perms')
    pb_can_approve_officer = fields.Boolean(compute='_compute_pb_perms')
    pb_can_approve_hr = fields.Boolean(compute='_compute_pb_perms')
    pb_can_approve_gm = fields.Boolean(compute='_compute_pb_perms')
    pb_can_reject = fields.Boolean(compute='_compute_pb_perms')
    pb_is_done = fields.Boolean(compute='_compute_pb_perms')
    pb_awaiting_me = fields.Boolean(
        compute='_compute_pb_awaiting_me', search='_search_pb_awaiting_me')

    def _pb_user_roles(self):
        """(officer, manager, final) for the CURRENT user — the one role read.

        Used by both the cosmetic button flags and the model-side tier gate, so
        what a user can see and what a user may actually do are computed from
        the same three booleans.
        """
        u = self.env.user
        root = u._is_admin() \
            or u.has_group('pb_hr_payroll_base.group_payroll_super_admin')
        officer = (root
                   or u.has_group('pb_hr_payroll_base.group_payroll_base_officer')
                   or u.has_group('pb_hr_payroll_base.group_payroll_base_manager'))
        manager = root or u.has_group('pb_hr_payroll_base.group_payroll_base_manager')
        final = root or u.has_group('pb_hr_payroll_base.group_payroll_final_approver')
        return officer, manager, final

    # ---------------- Phase L: model-side tier enforcement ----------------
    def _pb_chain_ctx(self):
        """The recordset the sanctioned chain writers use (carries the sentinel)."""
        return self.with_context(**{_PB_CHAIN_KEY: _PB_CHAIN_TOKEN})

    def _pb_seal_ok(self):
        return (self.env.context.get(_PB_CHAIN_KEY) is _PB_CHAIN_TOKEN
                or self.env.su or self.env.user._is_admin())

    @api.model_create_multi
    def create(self, vals_list):
        # a run is born in draft; nobody creates one already approved
        if not self._pb_seal_ok():
            for vals in vals_list:
                if vals.get('state') in _PB_BORN_SEALED:
                    raise AccessError(_(
                        "A pay run cannot be created in an approved state."))
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals and not self._pb_seal_ok():
            raise AccessError(_(
                "A pay run's approval status can only change through the "
                "approval actions (Submit / Approve / Reject)."))
        return super().write(vals)

    def _pb_demo_user(self):
        try:
            return self.env.user.has_group('pb_demo.group_payobook_demo')
        except Exception:
            return False

    def _pb_demo_reach(self):
        """Demo logins drive the showcase chain — but their authority stops at
        the demo world: every run in ``self`` must be generator-stamped
        ``is_demo`` (review L-1: the demo group's all-records rules would
        otherwise let any demo login walk a REAL run through all three tiers)."""
        if not self or 'is_demo' not in self._fields:
            return False
        return all(bool(r.sudo().is_demo) for r in self)

    def _pb_tier_ok(self, state):
        """May the current user advance a run that sits in ``state``?

        ``env.su`` passes: a server-side sudo caller (the analytics finalize
        path) is sanctioned code — call_kw can never hand a client su.
        """
        if self.env.su:
            return True
        officer, manager, final = self._pb_user_roles()
        if {'level0': officer, 'level1': manager, 'level2': final}.get(state, False):
            return True
        return self._pb_demo_user() and self._pb_demo_reach()

    def _pb_require_tier(self, state):
        """Raise unless the current user holds the tier that owns ``state``.

        First line of EVERY advance/cancel entry point. The cockpit, the kanban
        buttons, the native form buttons and a hand-rolled call_kw all funnel
        through here — there is no path that only the UI guards (C18.17).
        """
        if state not in PB_TIER:
            raise UserError(_("This pay run is not awaiting an approval decision."))
        if not self._pb_tier_ok(state):
            raise AccessError(_(
                "This pay run is waiting on the %s tier — your user does not "
                "hold that role.", PB_TIER[state][1]))

    def _pb_guard_advance(self, expected):
        """Tier gate + state gate for an advance.

        The state check closes the second half of the found hole: the legacy
        advance methods write their target state UNCONDITIONALLY, so calling
        action_payslip_run_level1_done on a *draft* run used to jump it straight
        to level2 and skip HR entirely.
        """
        for run in self:
            if run.state != expected:
                raise UserError(_(
                    "“%(name)s” is not at the %(stage)s stage (current status: "
                    "%(state)s).",
                    name=run.name or '', stage=PB_TIER[expected][1],
                    state=run.state or 'draft'))
        self._pb_require_tier(expected)

    def draft_payslip_run(self):
        """Reset an approved run to draft.

        Not a tier advance, but it UNDOES the Finance decision and re-opens the
        whole chain — so it carries the same gate as the tier that made that
        decision. (Found while mapping the chain: like the advances, this was
        guarded by nothing but the native form button's invisible= rule.)
        """
        _officer, _manager, final = self._pb_user_roles()
        if not (self.env.su or final
                or (self._pb_demo_user() and self._pb_demo_reach())):
            raise AccessError(_(
                "Only the Finance / GM tier can reset an approved pay run to "
                "draft."))
        # the legacy body writes 'draft' — sanctioned, so it carries the sentinel
        return super(HrPayslipRun, self._pb_chain_ctx()).draft_payslip_run()

    def action_payslip_run_level0_done(self):
        """Payroll Officer review → HR review.

        No payslip cascade (the slips were confirmed once at chain entry, see
        done_payslip_run) and NO mail — the Officer tier is a pure run-level
        move (C18.47/48: no new sends on this server).
        """
        self._pb_guard_advance('level0')
        self._pb_chain_ctx().write({'state': 'level1'})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_payslip_run_level1_done(self):
        """HR review → Finance approval — gated, then the legacy body verbatim
        (slip cascade, batch analytics, the existing GM notify).

        The sentinel context travels on the recordset so the LEGACY body's own
        `write({'state': 'level2'})` passes the seal without om_hr_payroll
        knowing anything about it.
        """
        self._pb_guard_advance('level1')
        return super(HrPayslipRun, self._pb_chain_ctx()).action_payslip_run_level1_done()

    def action_payslip_run_level2_done(self):
        """Finance approval → done — gated, then the legacy body verbatim."""
        self._pb_guard_advance('level2')
        return super(HrPayslipRun, self._pb_chain_ctx()).action_payslip_run_level2_done()

    def action_payslip_run_cancel(self):
        """Reject the run from any pending tier, recording the reason.

        Gated by the tier that currently OWNS the run (a draft is owned by the
        Officer tier). The reason rides the context because the method is also
        a plain view button with no arguments; the actor and timestamp are
        forced server-side and are never client-supplied (C18.24/57).
        """
        note = (self.env.context.get('pb_reject_note') or '').strip()[:512]
        for run in self:
            st = run.state or 'draft'
            if st not in ('draft',) + PB_PENDING_STATES:
                raise UserError(_(
                    "“%(name)s” is already %(state)s — it can no longer be "
                    "rejected.", name=run.name or '', state=st))
            run._pb_require_tier('level0' if st == 'draft' else st)
        # the legacy body writes 'cancel' — sanctioned, so it carries the sentinel
        res = super(HrPayslipRun, self._pb_chain_ctx()).action_payslip_run_cancel()
        self.write({'pb_reject_note': note or False,
                    'pb_reject_uid': self.env.uid,
                    'pb_reject_date': fields.Datetime.now()})
        return res

    @api.depends_context('uid')
    @api.depends('state')
    def _compute_pb_perms(self):
        officer, manager, final = self._pb_user_roles()
        demo = self._pb_demo_user()
        for run in self:
            st = run.state
            # a demo login's flags light up only on demo-world runs (L-1)
            d = demo and run._pb_demo_reach()
            off, man, fin = officer or d, manager or d, final or d
            run.pb_can_submit = st == 'draft' and off
            run.pb_can_approve_officer = st == 'level0' and off
            run.pb_can_approve_hr = st == 'level1' and man
            run.pb_can_approve_gm = st == 'level2' and fin
            run.pb_can_reject = ((st == 'draft' and off)
                                 or (st == 'level0' and off)
                                 or (st == 'level1' and man)
                                 or (st == 'level2' and fin))
            run.pb_is_done = st == 'done'

    @api.depends_context('uid')
    @api.depends('state')
    def _compute_pb_awaiting_me(self):
        officer, manager, final = self._pb_user_roles()
        demo = self._pb_demo_user()
        for run in self:
            d = demo and run._pb_demo_reach()
            run.pb_awaiting_me = ((run.state == 'level0' and (officer or d))
                                  or (run.state == 'level1' and (manager or d))
                                  or (run.state == 'level2' and (final or d)))

    def _search_pb_awaiting_me(self, operator, value):
        officer, manager, final = self._pb_user_roles()
        states = []
        if officer:
            states.append('level0')
        if manager:
            states.append('level1')
        if final:
            states.append('level2')
        match = [('state', 'in', states)] if states else []
        if self._pb_demo_user() and 'is_demo' in self._fields:
            demo_match = ['&', ('is_demo', '=', True),
                          ('state', 'in', list(PB_PENDING_STATES))]
            match = (['|'] + match + demo_match) if match else demo_match
        if not match:
            match = [('id', '=', 0)]
        positive = (operator in ('=', '!=') and bool(value)) == (operator == '=')
        return match if positive else (['!'] + match)

    def done_payslip_run(self):
        """Chain entry: draft → level0 (Payroll Officer review).

        This is the ONLY correct draft→chain transition (Phase L: the cockpit's
        submit seam used to call the level1 advance instead, which wrote level2
        unconditionally and skipped HR).

        The base method calls action_payslip_done() on every payslip, which — via
        the accounting bridge — posts journal entries (account.move). That path is
        only valid for STRUCTURE-based payroll whose salary rules carry GL
        accounts. A run computed by the Formula Engine (calculation_method =
        'formula') or any demo run has NO per-rule accounts, so posting either
        does nothing useful or raises a multi-company account.account access error
        ("…doesn't have 'read' access to Account"). For those accountless runs we
        advance the workflow state only (journals are produced in the dedicated
        Pay Salary step); traditional structure-based payroll keeps the standard
        accounting flow untouched via super().
        """
        for run in self:
            if run.state != 'draft':
                raise UserError(_(
                    "“%(name)s” has already entered the approval chain "
                    "(status: %(state)s).", name=run.name or '', state=run.state))
        if not self._pb_tier_ok('level0'):
            raise AccessError(_(
                "Only a Payroll Officer (or above) can submit a pay run for "
                "approval."))

        def _accountless(run):
            return getattr(run, 'is_demo', False) or bool(run.slip_ids) and all(
                getattr(s, 'calculation_method', False) == 'formula' for s in run.slip_ids)
        accountless = self.filtered(_accountless)
        standard = self - accountless
        # Payslips are confirmed ONCE here, at chain entry (unchanged); the new
        # Officer tier moves only the run, so slips keep landing on 'level1'.
        if accountless:
            accountless.slip_ids.filtered(lambda s: s.state == 'draft').write({'state': 'level1'})
            accountless._pb_chain_ctx().write({'state': 'level0'})
        if standard:
            # The legacy base cascades the slips then writes 'level1'
            # unconditionally; we re-write the run to 'level0' straight after.
            # Two writes on the run, ZERO edits to om_hr_payroll — and
            # idempotent: 'level0' is the only state anyone ever observes.
            res = super(HrPayslipRun, standard._pb_chain_ctx()).done_payslip_run()
            standard._pb_chain_ctx().write({'state': 'level0'})
            return res
        return True

    # ------------------------------------------------------------------
    # Removing a run, and removing what it produced
    # ------------------------------------------------------------------
    #: The two states a payslip may be thrown away in. Anything else has been
    #: approved by somebody and is a record of a decision, not a draft.
    _PB_DISPOSABLE_SLIP_STATES = ('draft', 'cancel')

    def _pb_disposable_slips(self):
        """This run's payslips that may be deleted, and those that may not."""
        slips = self.mapped('slip_ids')
        disposable = slips.filtered(
            lambda s: s.state in self._PB_DISPOSABLE_SLIP_STATES)
        return disposable, slips - disposable

    def unlink(self):
        """Deleting a pay run takes its DRAFT payslips with it.

        It did not, and that is a trap rather than a nicety. `payslip_run_id`
        is a plain many2one, so deleting a batch left every payslip alive and
        unattached — and the Run Payroll wizard then ADOPTS this period's
        loose drafts on purpose (`_adopt_loose_slips`), to stop a second
        payroll being computed on top of one that already exists. The two
        behaviours are individually reasonable and together they mean: delete
        a run, build a new one, and the old numbers walk back in without being
        recomputed. Seen on the reference tenant on 2026-08-28 — a run created
        at 03:39 adopted 152 payslips computed two days earlier, and the only
        trace was one line in the server log.

        A payslip past draft is a different thing: somebody approved it. Those
        stop the deletion rather than being swept up in it.
        """
        disposable, protected = self._pb_disposable_slips()
        if protected:
            raise UserError(_(
                "This pay run has %(n)s payslip(s) that have been approved, so "
                "it cannot be deleted. Cancel or reject them first if you "
                "really mean to remove this run.", n=len(protected)))
        if disposable:
            _logger.info("pb_payruns: deleting run(s) %s and their %s draft "
                         "payslip(s)", self.ids, len(disposable))
            disposable.unlink()
        return super().unlink()

    def action_pb_delete_draft_payslips(self):
        """Throw away this run's draft payslips and keep the run itself.

        The way to start a period again without deleting the run: clear what
        was computed, then Generate Payslips. Doing it by deleting the run
        instead is what leaves the drafts loose for the next run to adopt.
        """
        self.ensure_one()
        disposable, protected = self._pb_disposable_slips()
        if protected:
            raise UserError(_(
                "%(n)s payslip(s) on this pay run have been approved and were "
                "not deleted. Cancel or reject them first.", n=len(protected)))
        if not disposable:
            return self._pb_toast(_("There are no draft payslips to delete."))
        count = len(disposable)
        disposable.unlink()
        _logger.info("pb_payruns: %s deleted %s draft payslip(s) from run %s",
                     self.env.user.login, count, self.id)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Draft payslips deleted'),
                'message': _("%(n)s payslip(s) removed. Press Generate "
                             "Payslips to compute the period again.", n=count),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    # ---- Pay Salary (post-approval disbursement) — surfaced on Done cards ----
    def _pb_toast(self, message):
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Pay Salary'), 'message': message,
                           'type': 'warning', 'sticky': False}}

    def action_pb_bank_export(self):
        """Open the bank-export wizard pre-scoped to this run."""
        self.ensure_one()
        if 'payroll.bank.export.wizard' not in self.env:
            return self._pb_toast(_('Bank export is not available on this server.'))
        cfg = self.slip_ids.mapped('formula_config_id')[:1]
        ctx = {'default_payslip_run_id': self.id,
               'default_date_from': self.date_start, 'default_date_to': self.date_end}
        if cfg:
            ctx['default_formula_config_id'] = cfg.id
        return {'type': 'ir.actions.act_window', 'name': _('Export Bank File'),
                'res_model': 'payroll.bank.export.wizard', 'view_mode': 'form',
                'target': 'new', 'context': ctx}

    def action_pb_journals(self):
        """Open the period's journal entries for this company."""
        self.ensure_one()
        if 'account.move' not in self.env:
            return self._pb_toast(_('Accounting is not installed.'))
        return {'type': 'ir.actions.act_window', 'name': _('Journal Entries'),
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('company_id', '=', self.env.company.id),
                           ('date', '>=', self.date_start), ('date', '<=', self.date_end)],
                'context': {'search_default_posted': 1}}

    def action_pb_payments(self):
        """Open the period's payments for this company."""
        self.ensure_one()
        if 'account.payment' not in self.env:
            return self._pb_toast(_('Accounting is not installed.'))
        return {'type': 'ir.actions.act_window', 'name': _('Payments'),
                'res_model': 'account.payment', 'view_mode': 'list,form',
                'domain': [('company_id', '=', self.env.company.id),
                           ('date', '>=', self.date_start), ('date', '<=', self.date_end)]}
