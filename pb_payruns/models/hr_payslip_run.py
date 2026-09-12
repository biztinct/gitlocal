# -*- coding: utf-8 -*-
"""The pay run, on the approval engine.

CLEAN REPLACEMENT (AM ledger, "no payroll is live"). The three-tier ladder that
used to live here — ``level0``/``level1``/``level2``, ``PB_TIER``, the
``officer_review`` system parameter, the send-back map and the three
``action_payslip_run_levelN_done`` entry points — is GONE, not kept beside the
engine. A pay run now has four states:

    draft → approval_pending → done,  and  cancel

and the only thing that moves it between them is
``biz.approval.engine``, through the four adapter methods below. Who signs a
run off is no longer a constant in this file; it is whatever route the business
published for this company, this pay scheme and this kind of run.

WHAT THE SEAL STILL DOES. ``write({'state': …})`` is still refused unless it
carries the module-level sentinel, for exactly the reason it always was: a
state machine nothing enforces is decoration, and a raw ``call_kw`` write to
``done`` would hand a run to the bank without an approval. Only
``_approval_freeze``, ``_approval_apply``, ``_approval_return`` and the reject
action carry it.

SCOPE. The engine never parses a scope key (ledger AM2). This adapter mints
them, most specific first, in the Matrix's own canonical order:

    scheme:<config id>|division:<division id>
    scheme:<config id>
    division:<division id>
    ''                                (the whole company)

A run whose payslips do not all land on ONE (scheme, division, currency) has no
single answer to "who approves this?", so it is refused at submission and
offered a split into one run per group.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Salary-category code buckets (mirror pb_hr_workforce payroll_report).
NET_CODES = ('NET',)
GROSS_CODES = ('GROSS',)
DED_CODES = ('DED', 'DEDUCTION', 'COMP')

#: The four states a pay run may be in, and the words for them. ONE map, read
#: by the board, the kanban and the form, so a screen can never name a stage
#: the model does not have.
PB_STATES = [
    ('draft', 'Draft'),
    ('approval_pending', 'Waiting for approval'),
    ('done', 'Done'),
    ('cancel', 'Rejected'),
]
PB_STAGE_NAME = dict(PB_STATES)
#: The columns the board draws, in order. ``cancel`` is not a column: a
#: rejected run is an outcome, not a stage on the way somewhere.
PB_BOARD_STATES = ('draft', 'approval_pending', 'done')

#: The payslip state a run in each state expects. Slips wait in the standard
#: "Waiting" state while an approval is open, so the bank export — which filters
#: on slip state ``done`` — can never see a run nobody has approved.
PB_SLIP_STATE = {'draft': 'draft', 'approval_pending': 'verify', 'done': 'done'}

# C18.24: a state machine is decorative unless write() enforces it. Without
# this, anyone holding plain write access to hr.payslip.run could call_kw
# `write({'state': 'done'})` and skip the whole approval (proven live before
# this guard existed). The key is a module-level object() IDENTITY — a
# client-supplied context value can never equal it, whereas a plain boolean flag
# would be forgeable through the call_kw context merge.
_PB_CHAIN_KEY = 'pb_chain_state_write'
_PB_CHAIN_TOKEN = object()
#: A run may be born in draft, never already approved or already under way.
_PB_BORN_SEALED = ('approval_pending', 'done', 'cancel')

#: Salary-rule codes that mean "this run contains overtime". Read as a
#: SUBSTRING of the line's own code, because a scheme built from a workbook
#: names its components after the workbook's headings.
_PB_OT_TOKENS = ('OT', 'OVERTIME', 'TANGCA')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Index the run FK — every cockpit aggregates payslips per run; without this
    # the SQL roll-ups seq-scan the payslip table as volume grows.
    payslip_run_id = fields.Many2one(index=True)

    def _pb_guard_run_slip(self):
        """A payslip that belongs to a pay run is finished BY that run.

        Safety rail 3, and it is not only about a run that is already waiting.
        The bank export pays every payslip in state `done`, so a screen that
        pushed one slip of a DRAFT run to done would let money out of a run
        nobody had even sent in — which is the whole thing the approval exists
        to stop. A payslip with no run (somebody's one-off) is untouched.
        """
        if self.env.context.get(_PB_CHAIN_KEY) is _PB_CHAIN_TOKEN:
            return
        # A run that is already `done` has had its approval; a refund or an
        # adjustment slip made off it afterwards is the caller's own business
        # and this guard has nothing to say about it.
        held = self.filtered(
            lambda s: s.payslip_run_id
            and s.payslip_run_id.state in ('draft', 'approval_pending'))
        if not held:
            return
        raise UserError(_(
            "This payslip belongs to a pay run, so it cannot be finished on "
            "its own. Send the pay run in for approval — every payslip in it "
            "is finished together, once the approval is complete."))

    def action_payslip_done(self):
        self._pb_guard_run_slip()
        return super().action_payslip_done()

    def action_payslip_level1_done(self):
        self._pb_guard_run_slip()
        return super().action_payslip_level1_done()

    def action_payslip_level2_done(self):
        self._pb_guard_run_slip()
        return super().action_payslip_level2_done()


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # Index the slip FK — payslip-line aggregations join on this; essential for
    # fast roll-ups as line volume reaches the millions.
    slip_id = fields.Many2one(index=True)


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _inherit = ['hr.payslip.run', 'biz.approval.adapter.mixin']

    #: The row in the approval catalogue this model is approved under.
    _approval_process_key = 'payrun'

    # The whole selection is REPLACED rather than added to: the two states the
    # base module ships ('level1', 'HR Manager pending' / 'level2', 'General
    # Manager pending') are the old ladder, and leaving them in the list would
    # leave a board column and a search filter for a stage nothing can reach.
    state = fields.Selection(
        selection=PB_STATES, group_expand='_pb_group_expand_state')

    # ------------------------------------------------------------ testimony
    # Rejection (who killed the run, why, when) — written only by
    # action_payslip_run_cancel below, readonly everywhere else.
    pb_reject_note = fields.Char(string='Rejection reason', readonly=True, copy=False)
    pb_reject_uid = fields.Many2one('res.users', string='Rejected by', readonly=True, copy=False)
    pb_reject_date = fields.Datetime(string='Rejected on', readonly=True, copy=False)

    # Sent back (the approver returned it to be fixed). Cleared the moment the
    # run is submitted again, so the note always answers "why is this sitting
    # here" rather than "what happened to it once, months ago".
    pb_return_note = fields.Char(string='Sent back because', readonly=True, copy=False)
    pb_return_uid = fields.Many2one('res.users', string='Sent back by', readonly=True, copy=False)
    pb_return_date = fields.Datetime(string='Sent back on', readonly=True, copy=False)

    # Who actually prepared the numbers. The Run Payroll screen writes it; the
    # payslips' own authors are added to it at submission, and together they are
    # the "makers" an independence rule keeps away from the decision.
    pb_prepared_uid = fields.Many2one(
        'res.users', string='Prepared by', readonly=True, copy=False,
        help="Who ran the payroll that produced these payslips.")

    # What the numbers looked like when the run was sent in. If they move, the
    # approval no longer covers them and the engine refuses to carry it out.
    pb_source_revision = fields.Char(
        string='Pay data stamp', readonly=True, copy=False)

    # The route, in one line, on the run's own screen. A Char and not a set of
    # fields because it is a SENTENCE — who has to say yes, and who it is with
    # right now — and a form that split that across three labelled boxes would
    # be making the reader assemble it.
    pb_approval_line = fields.Char(
        string='Approval', compute='_compute_pb_approval_line')

    @api.depends('state')
    def _compute_pb_approval_line(self):
        for run in self:
            request = run.approval_request_id
            if not request:
                run.pb_approval_line = _(
                    "Not sent in yet. Submit for approval sends it to whoever "
                    "your business has chosen for this pay scheme.")
                continue
            version = request.version_id
            route = ' → '.join(version.route_labels or []) or _('Nobody checks it')
            if request.state == 'blocked':
                run.pb_approval_line = _(
                    "%(route)s — stuck: %(why)s", route=route,
                    why=request.block_reason or '')
                continue
            step = request.step_ids.filtered(
                lambda s: s.key == request.current_step_key)[:1]
            if step:
                people = ', '.join(sorted(set(
                    step.seat_ids.filtered(lambda s: s.status == 'open')
                    .mapped('acting_user_id.name'))))
                run.pb_approval_line = _(
                    "%(route)s — now with %(who)s for “%(step)s”",
                    route=route, who=people or _('nobody yet'),
                    step=step.title or '')
                continue
            run.pb_approval_line = _(
                "%(route)s — %(state)s", route=route,
                state=dict(request._fields['state'].selection).get(
                    request.state, request.state))

    @api.model
    def _pb_group_expand_state(self, values, domain):
        return list(PB_BOARD_STATES)

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
    # structure-based payroll.
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
        # exotic one.
        self.env['hr.payslip'].flush_model(['payslip_run_id', 'state'])
        line_fields = ['slip_id', 'category_id', 'total']
        detail_aware = 'component_detail' in self.env['hr.payslip.line']._fields
        if detail_aware:
            line_fields.append('component_detail')
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
                  -- sourced nothing" and no reader may collapse the two.
                  AND p.formula_input_sources IS NOT NULL
                  AND p.formula_input_sources <> ''
                GROUP BY p.payslip_run_id
            """, (tuple(run_ids),))
            unsourced = dict(cr.fetchall())
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
            run.pb_total_gross = d.get('GROSS') or (
                d.get('BASIC', 0.0) + d.get('ALW', 0.0))
            run.pb_total_deductions = abs(d.get('DED', 0.0) + d.get('DEDUCTION', 0.0)
                                          + d.get('COMP', 0.0))
            run.pb_total_employer_cost = abs(d.get('ERCOST', 0.0))

    # ---- context-aware permission flags for kanban card buttons ----
    # NOTE: these are COSMETIC. Enforcement lives in the engine and in the
    # write seal below; a screen boolean is decoration (ledger, "server is the
    # authority").
    pb_can_submit = fields.Boolean(compute='_compute_pb_perms')
    pb_can_reject = fields.Boolean(compute='_compute_pb_perms')
    pb_is_pending = fields.Boolean(compute='_compute_pb_perms')
    pb_is_done = fields.Boolean(compute='_compute_pb_perms')
    pb_awaiting_me = fields.Boolean(
        compute='_compute_pb_awaiting_me', search='_search_pb_awaiting_me')

    @api.depends_context('uid')
    @api.depends('state')
    def _compute_pb_perms(self):
        may_write = self.env['hr.payslip.run'].has_access('write')
        for run in self:
            st = run.state or 'draft'
            run.pb_can_submit = st == 'draft' and may_write
            run.pb_can_reject = st in ('draft', 'approval_pending') and may_write
            run.pb_is_pending = st == 'approval_pending'
            run.pb_is_done = st == 'done'

    @api.depends_context('uid')
    @api.depends('state')
    def _compute_pb_awaiting_me(self):
        """Is this run waiting on a seat THIS person holds right now?

        Asked of the engine's own seats and never of a group: "anybody in HR"
        is exactly the fallback the engine refuses to make.
        """
        mine = self._pb_runs_awaiting(self.env.uid)
        for run in self:
            run.pb_awaiting_me = run.id in mine

    @api.model
    def _pb_runs_awaiting(self, uid):
        Seat = self.env['biz.approval.request.seat'].sudo()
        seats = Seat.search([
            ('acting_user_id', '=', uid), ('status', '=', 'open'),
            ('request_id.res_model', '=', 'hr.payslip.run'),
            ('request_id.state', 'in', ('pending', 'blocked')),
        ])
        return set(seats.mapped('request_id.res_id'))

    def _search_pb_awaiting_me(self, operator, value):
        ids = list(self._pb_runs_awaiting(self.env.uid)) or [0]
        positive = (operator in ('=', '!=') and bool(value)) == (operator == '=')
        return [('id', 'in', ids)] if positive else [('id', 'not in', ids)]

    # ==================================================================
    # The seal: only the adapter may move a run between states
    # ==================================================================
    def _pb_chain_ctx(self):
        """The recordset the sanctioned writers use (carries the sentinel)."""
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
                "A pay run's approval status can only change through Submit "
                "for approval, an approval decision, or Reject."))
        return super().write(vals)

    # ==================================================================
    # Adapter — what an approval of a pay run is about
    # ==================================================================
    def _pb_review_groups(self):
        """The (scheme, division, currency) groups this run's payslips fall in.

        One group is the normal case and the only one that can be approved: a
        run spanning two schemes has two different published routes and no
        honest way to pick between them.
        """
        self.ensure_one()
        Division = self.env.get('pb.division')
        by_department = {}
        groups = {}
        slips = self.slip_ids.filtered(lambda s: s.state != 'cancel')
        run_config = getattr(self, 'pb_formula_config_id', False)
        on_date = self.date_end or self.date_start or fields.Date.context_today(self)
        for slip in slips:
            config = slip.formula_config_id or run_config
            department = slip.employee_id.department_id
            key_dept = department.id or 0
            if key_dept not in by_department:
                found = self.env['pb.division']
                if Division is not None and department:
                    try:
                        found = Division.division_for(department, on_date)
                    except Exception:   # noqa: BLE001 — never stop a submission
                        _logger.warning(
                            'pb_payruns: division lookup failed on run %s',
                            self.id)
                by_department[key_dept] = found
            division = by_department[key_dept]
            company = slip.company_id or self.env.company
            currency = company.currency_id
            key = (config.id if config else 0,
                   division.id if division else 0, currency.id)
            row = groups.setdefault(key, {
                'config': config, 'division': division, 'company': company,
                'currency': currency, 'slip_ids': [], 'employee_ids': [],
            })
            row['slip_ids'].append(slip.id)
            if slip.employee_id:
                row['employee_ids'].append(slip.employee_id.id)
        return list(groups.values())

    def _pb_scope_keys(self, config, division):
        """The opaque keys the engine walks, most specific first."""
        scheme = 'scheme:%s' % config.id if config else ''
        area = 'division:%s' % division.id if division else ''
        keys = []
        if scheme and area:
            keys.append('%s|%s' % (scheme, area))
        if scheme:
            keys.append(scheme)
        if area:
            keys.append(area)
        keys.append('')
        return keys

    def _pb_kind_key(self):
        """What kind of run this is, in the scheme map's own vocabulary."""
        config = getattr(self, 'pb_formula_config_id', False) \
            or self.slip_ids[:1].formula_config_id
        return (getattr(config, 'cycle_type', False) or 'any') if config else 'any'

    def _pb_slip_money(self, slips):
        """{slip id: (net, gross)} — the same buckets the KPI band uses."""
        if not slips:
            return {}
        role_aware = 'pay_role' in self.env['hr.payslip.line']._fields
        bucket = self._pb_bucket_sql(role_aware)
        # Flush EVERY column the bucket reads: this is raw SQL, so anything
        # still in the ORM's write buffer is invisible to it — and the stamp
        # being taken in the same transaction as the write is the normal case.
        columns = ['slip_id', 'category_id', 'total']
        if role_aware:
            columns.append('pay_role')
        self.env['hr.payslip.line'].flush_model(columns)
        self.env.cr.execute("""
            SELECT pl.slip_id, """ + bucket + """ AS bucket,
                   COALESCE(SUM(pl.total), 0)
            FROM hr_payslip_line pl
            JOIN hr_salary_rule_category c ON c.id = pl.category_id
            WHERE pl.slip_id IN %s AND """ + bucket + """ IS NOT NULL
            GROUP BY pl.slip_id, 2
        """, (tuple(slips.ids),))
        agg = {}
        for slip_id, code, total in self.env.cr.fetchall():
            agg.setdefault(slip_id, {})[code] = float(total or 0.0)
        out = {}
        for slip in slips:
            d = agg.get(slip.id, {})
            gross = d.get('GROSS') or (d.get('BASIC', 0.0) + d.get('ALW', 0.0))
            out[slip.id] = (d.get('NET', 0.0), gross)
        return out

    def _pb_overtime_included(self):
        """Does this run pay overtime? Read off the components it actually has."""
        self.ensure_one()
        slips = self.slip_ids.filtered(lambda s: s.state != 'cancel')
        if not slips:
            return False
        for line in slips.mapped('line_ids'):
            code = (line.code or '').upper().replace('_', '').replace('-', '')
            if not code:
                continue
            for token in _PB_OT_TOKENS:
                if token in code:
                    return True
        return False

    def _pb_variance_pct(self, config, net_total):
        """How far this run's net pay is from the last approved one like it."""
        self.ensure_one()
        if not config or not self.date_start:
            return 0.0
        domain = [('id', '!=', self.id), ('state', '=', 'done'),
                  ('date_start', '<', self.date_start)]
        if 'pb_formula_config_id' in self._fields:
            domain.append(('pb_formula_config_id', '=', config.id))
        previous = self.sudo().search(domain, order='date_start desc, id desc',
                                      limit=1)
        if not previous or not previous.pb_total_net:
            return 0.0
        before = float(previous.pb_total_net)
        return round((float(net_total) - before) / before * 100.0, 2)

    def _approval_validate(self):
        """Everything about THIS run that would stop it being sent in."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_(
                "“%(name)s” has already been sent in (status: %(state)s).",
                name=self.name or '',
                state=_(PB_STAGE_NAME.get(self.state or 'draft',
                                          self.state or ''))))
        if not self.slip_ids.filtered(lambda s: s.state != 'cancel'):
            raise UserError(_(
                "There are no payslips in this pay run yet, so there is "
                "nothing to approve. Generate the payslips first."))
        groups = self._pb_review_groups()
        if len(groups) > 1:
            raise UserError(_(
                "This pay run covers %(n)s different groups of people — "
                "different pay schemes, parts of the business or currencies — "
                "and each of them can be approved by different people. Split "
                "it into one run per group first, using “Split into review "
                "groups” on the run.", n=len(groups)))
        return True

    def _approval_context(self):
        """The frozen truth about this run at the moment it is sent in."""
        self.ensure_one()
        groups = self._pb_review_groups()
        if not groups:
            raise UserError(_(
                "There are no payslips in this pay run yet, so there is "
                "nothing to approve."))
        group = groups[0]
        config, division = group['config'], group['division']
        company = group['company']
        currency = group['currency']
        slips = self.env['hr.payslip'].browse(group['slip_ids'])

        net_total = float(self.pb_total_net or 0.0)
        gross_total = float(self.pb_total_gross or 0.0)
        unit = currency.name or ''
        facts = {
            'net_total': {'value': net_total, 'unit': unit},
            'gross_total': {'value': gross_total, 'unit': unit},
            'payslip_count': {'value': len(slips), 'unit': ''},
            'employee_count': {'value': len(set(group['employee_ids'])),
                               'unit': ''},
            'variance_pct': {'value': self._pb_variance_pct(config, net_total),
                             'unit': ''},
            'overtime_included': {'value': self._pb_overtime_included(),
                                  'unit': ''},
        }

        makers = set(slips.mapped('create_uid').ids)
        if self.pb_prepared_uid:
            makers.add(self.pb_prepared_uid.id)
        subjects = set(slips.mapped('employee_id.user_id').ids)

        label_bits = [b for b in (config.name if config else '',
                                  division.name if division else '') if b]
        return {
            'company_id': company.id,
            'title': self.name or _('Pay run'),
            'scope_keys': self._pb_scope_keys(config, division),
            'scope_label': ' · '.join(label_bits) or company.name,
            'kind_key': self._pb_kind_key(),
            'facts': facts,
            'amount': net_total,
            'currency_id': currency.id,
            'maker_uids': sorted(makers),
            'submitter_uid': self.env.uid,
            'subject_uids': sorted(subjects),
            'source_revision': self._pb_source_revision(slips),
            'evidence': self._pb_evidence(),
        }

    def _pb_source_revision(self, slips=None):
        """A stamp of the numbers this approval covers.

        WHICH PAYSLIPS, AND WHAT EACH ONE PAYS — and deliberately NOT their
        `write_date`. Sending a run in moves every payslip from Draft to
        Waiting, which stamps a new write_date on all of them; a revision that
        included it would differ from itself the moment it was taken, and every
        approval would then be refused as "this changed after it was sent in".
        What an approver signs for is the money, so that is what is stamped:
        add a payslip, remove one, or move a single figure on one of them and
        the stamp changes.
        """
        self.ensure_one()
        if slips is None:
            slips = self.slip_ids.filtered(lambda s: s.state != 'cancel')
        money = self._pb_slip_money(slips)
        rows = sorted(
            (slip.id, round(money.get(slip.id, (0.0, 0.0))[0], 2),
             round(money.get(slip.id, (0.0, 0.0))[1], 2))
            for slip in slips)
        return self._approval_revision_of(rows)

    def _pb_evidence(self):
        """What is attached to this run, as the route may ask for it."""
        self.ensure_one()
        attachments = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', self._name), ('res_id', '=', self.id)], limit=40)
        names = [a.name or '' for a in attachments]
        control = any('control' in (n or '').lower() for n in names)
        return [{'key': 'control_report',
                 'name': _('Control report'),
                 'ok': control,
                 'note': (names[0] if control and names else '')}]

    @api.model
    def _approval_capabilities(self):
        """What a workflow designer may ask about a pay run."""
        from odoo.addons.pb_scheme_map.models.formula_scheme_assignment import (
            CYCLE_SELECTION)
        return {
            'facts': {
                'net_total': {'type': 'decimal', 'label': _('Total net pay'),
                              'unit': 'currency'},
                'gross_total': {'type': 'decimal', 'label': _('Total gross pay'),
                                'unit': 'currency'},
                'payslip_count': {'type': 'int', 'label': _('Payslips')},
                'employee_count': {'type': 'int', 'label': _('Employees')},
                'variance_pct': {'type': 'percent',
                                 'label': _('Change against the last run')},
                'overtime_included': {'type': 'bool',
                                      'label': _('Contains overtime')},
            },
            'kinds': [{'key': key, 'label': _(label)}
                      for key, label in CYCLE_SELECTION],
            'evidence': [
                {'key': 'control_report', 'label': _('Control report')},
                {'key': 'variance_note', 'label': _('Note on the changes')},
                {'key': 'bank_control_total',
                 'label': _('Bank control total')},
            ],
            # Labels rather than keys: nothing reads this yet, and the day
            # something does it will be putting it on a screen.
            'scope_levels': [_('Pay scheme'), _('Division')],
            # A pay run is a batch about many people, so "their manager" has no
            # single answer worth offering in the builder.
            'manager_mode': False,
        }

    @api.model
    def _approval_scope_options(self, company):
        """The narrowings a pay-run route may be given: which scheme, and the
        kind of run. The division level is added for every process by the
        configuration module, so it is deliberately not repeated here."""
        options = []
        Config = self.env.get('hr.formula.config')
        if Config is not None:
            domain = [('company_id', '=', company.id)]
            if 'state' in Config._fields:
                domain.append(('state', '!=', 'archived'))
            for config in Config.sudo().search(domain, limit=200,
                                               order='name'):
                options.append({'key': 'scheme:%s' % config.id,
                                'label': config.name or ''})
        if not options:
            return []
        return [{'level': 'scheme', 'label': _('Pay scheme'),
                 'options': options}]

    @api.model
    def _approval_coverage_scopes(self, company):
        """Every (scheme, division) pair pay actually happens in."""
        rows = []
        Map = self.env.get('pb.scheme.map')
        Config = self.env.get('hr.formula.config')
        if Config is None:
            return rows
        headcount = {}
        if Map is not None:
            try:
                coverage = Map.coverage(company.id)
                headcount = {int(k): v
                             for k, v in (coverage.get('by_config') or {}).items()}
            except Exception:       # noqa: BLE001 — a scan must never raise
                _logger.warning('pb_payruns: scheme coverage unavailable')
        configs = Config.sudo().search([('company_id', '=', company.id)],
                                       limit=200, order='name')
        for config in configs:
            rows.append({
                'scope_key': 'scheme:%s' % config.id,
                'scope_keys': ['scheme:%s' % config.id, ''],
                'label': config.name or '',
                'headcount': headcount.get(config.id, 0),
                'kind_key': getattr(config, 'cycle_type', False) or 'any',
                'facts': {},
            })
        if not rows:
            rows.append({'scope_key': '', 'scope_keys': [''],
                         'label': company.name, 'headcount': 0,
                         'kind_key': 'any', 'facts': {}})
        return rows

    # ------------------------------------------------------- the transitions
    def _approval_freeze(self, request):
        """Lock the numbers while somebody is deciding about them."""
        self.ensure_one()
        slips = self.slip_ids.filtered(lambda s: s.state == 'draft')
        if slips:
            slips.write({'state': 'verify'})
        self._pb_chain_ctx().write({
            'state': 'approval_pending',
            'pb_source_revision': request.source_revision or '',
            'pb_return_note': False, 'pb_return_uid': False,
            'pb_return_date': False,
        })
        return True

    def _approval_apply(self, request):
        """Carry out what the approval authorised: finish the run.

        This is the legacy "done" body, guarded exactly as it always was. A
        run whose payslips are computed by a scheme has no per-rule GL
        accounts, so posting journal entries for it either does nothing useful
        or raises a multi-company account error; those runs advance the
        workflow only and the journals are produced in the dedicated Pay Salary
        step. Traditional structure-based payroll keeps the standard accounting
        flow untouched, through `hr.payslip.action_payslip_done`.

        Idempotent: a run already `done` is left alone.
        """
        self.ensure_one()
        if self.state == 'done':
            return True

        def _accountless(run):
            return getattr(run, 'is_demo', False) or bool(run.slip_ids) and all(
                getattr(s, 'calculation_method', False) == 'formula'
                for s in run.slip_ids)

        slips = self.slip_ids.filtered(lambda s: s.state != 'cancel')
        if _accountless(self):
            if slips:
                slips.write({'state': 'done'})
        else:
            # `action_payslip_done` is where the accounting bridge posts the
            # journal entry; the sentinel lets it past the "not behind your own
            # run's back" rail, which exists for direct clicks, not for this.
            sanctioned = slips.with_context(
                **{_PB_CHAIN_KEY: _PB_CHAIN_TOKEN})
            for slip in sanctioned.sorted(lambda s: s.employee_id.name or ''):
                slip.action_payslip_done()
            slips.write({'state': 'done'})
        self._pb_chain_ctx().write({'state': 'done'})
        if hasattr(self, '_sync_analytics_state_on_done'):
            try:
                self._sync_analytics_state_on_done()
            except Exception:       # noqa: BLE001 — never half-apply
                _logger.exception(
                    'pb_payruns: analytics sync failed on run %s', self.id)
        return True

    def _approval_return(self, request, reason):
        """Sent back: the numbers become editable again, with the reason."""
        self.ensure_one()
        slips = self.slip_ids.filtered(lambda s: s.state == 'verify')
        if slips:
            slips.write({'state': 'draft'})
        self._pb_chain_ctx().write({
            'state': 'draft',
            'pb_return_note': (reason or '')[:512] or False,
            'pb_return_uid': self.env.uid,
            'pb_return_date': fields.Datetime.now(),
        })
        return True

    # ------------------------------------------------------------ submitting
    def action_approval_submit(self):
        """Send this run in for approval, and say what happened."""
        self.ensure_one()
        result = super().action_approval_submit()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sent in for approval'),
                'message': (_("“%s” is finished — nobody had to check it, and "
                              "that is recorded.", self.name or '')
                            if self.state == 'done'
                            else _("“%s” is now waiting for its approval.",
                                   self.name or '')),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        } if result else True

    # ==================================================================
    # Split into review groups
    # ==================================================================
    def action_split_review_groups(self):
        """One draft run per (scheme, division, currency) group.

        Every payslip ends up in exactly one child, the nets add back up to
        the source's net, and the source — now empty — is deleted. Anything
        short of that raises and the whole split is rolled back.
        """
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_(
                "Only a pay run that is still a draft can be split."))
        groups = self._pb_review_groups()
        if len(groups) < 2:
            raise UserError(_(
                "Everybody in this pay run is paid by the same scheme in the "
                "same part of the business, so there is nothing to split."))
        before_slips = set(self.slip_ids.ids)
        before_net = round(float(self.pb_total_net or 0.0), 2)

        children = self.browse()
        moved = set()
        has_config = 'pb_formula_config_id' in self._fields
        for group in groups:
            bits = [b for b in (group['config'].name if group['config'] else '',
                                group['division'].name if group['division']
                                else '') if b]
            suffix = ' · '.join(bits) or group['currency'].name or ''
            # CREATED, never copied: `slip_ids` is a plain one2many with no
            # `copy=False`, so `copy()` would DUPLICATE every payslip — the
            # opposite of conserving them.
            values = {
                'name': '%s · %s' % (self.name or _('Pay run'), suffix),
                'date_start': self.date_start,
                'date_end': self.date_end,
                'credit_note': self.credit_note,
            }
            if has_config and group['config']:
                values['pb_formula_config_id'] = group['config'].id
            child = self.create(values)
            slips = self.env['hr.payslip'].browse(group['slip_ids'])
            slips.write({'payslip_run_id': child.id})
            moved |= set(slips.ids)
            children |= child

        self.env['hr.payslip'].flush_model(['payslip_run_id'])
        self.invalidate_recordset()
        children.invalidate_recordset()
        if moved != before_slips:
            raise UserError(_(
                "The split was stopped because it would not have kept every "
                "payslip. Nothing was changed."))
        after_net = sum(float(child.pb_total_net or 0.0) for child in children)
        if round(after_net, 2) != round(before_net, 2):
            raise UserError(_(
                "The split was stopped because the totals did not add back "
                "up. Nothing was changed."))
        if self.slip_ids:
            raise UserError(_(
                "The split was stopped because the original pay run still has "
                "payslips in it. Nothing was changed."))
        names = ', '.join(child.name or '' for child in children)
        source_name = self.name or ''
        self.unlink()
        _logger.info('pb_payruns: split "%s" into %s runs', source_name,
                     len(children))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pay runs'),
            'res_model': 'hr.payslip.run',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', children.ids)],
            'context': {'pb_split_from': source_name, 'pb_split_names': names},
        }

    # ==================================================================
    # Rejecting a run outright
    # ==================================================================
    def action_payslip_run_cancel(self):
        """Reject the run, recording the reason and withdrawing its approval.

        Not an approval decision: it is the preparer's own "this run should not
        exist". Anyone who may edit the run may do it, and the reason rides the
        context because this is also a plain view button with no arguments; the
        actor and timestamp are forced server-side and are never
        client-supplied (C18.24/57).
        """
        note = (self.env.context.get('pb_reject_note') or '').strip()[:512]
        for run in self:
            if run.state not in ('draft', 'approval_pending'):
                raise UserError(_(
                    "“%(name)s” is already %(state)s — it can no longer be "
                    "rejected.", name=run.name or '',
                    state=_(PB_STAGE_NAME.get(run.state or '', run.state or ''))))
            run.check_access('write')
        for run in self:
            request = run.approval_request_id
            if request and request.state in ('pending', 'blocked'):
                # sudo, and the authority is the line above: whoever may edit
                # this run may reject it, and rejecting it has to withdraw the
                # request that is open on it. The engine's own `cancel` asks
                # "are you the person who sent it in?", which is the right
                # question for somebody withdrawing their own request and the
                # wrong one here.
                self.env['biz.approval.engine'].sudo().cancel(
                    request.id, note or _('The pay run was rejected.'))
        # the legacy body cancels every payslip and writes 'cancel' — sanctioned,
        # so it carries the sentinel
        res = super(HrPayslipRun, self._pb_chain_ctx()).action_payslip_run_cancel()
        self.write({'pb_reject_note': note or False,
                    'pb_reject_uid': self.env.uid,
                    'pb_reject_date': fields.Datetime.now()})
        return res

    # ------------------------------------------------------------------
    # The old ladder's three entry points, closed
    # ------------------------------------------------------------------
    # They are DEFINED in `om_hr_payroll`, so they cannot be deleted from here
    # — and a method that still exists and still writes `level1` is a live hole,
    # not dead code: anything that has not been re-pointed (an old bookmark, a
    # script, a module nobody upgraded) would move a run into a state that no
    # longer exists. Each one now refuses, in the words that say where to go
    # instead. `done_payslip_run` is the one with real callers, so it is
    # re-pointed rather than refused.
    def done_payslip_run(self):
        """Submitting, under the name the base module gave it."""
        for run in self:
            run.action_approval_submit()
        return True

    def action_payslip_run_level1_done(self):
        raise UserError(_(
            "Pay runs are no longer approved in fixed stages. This one follows "
            "the approval route your business published — open it in Approvals "
            "to make a decision."))

    def action_payslip_run_level2_done(self):
        raise UserError(_(
            "Pay runs are no longer approved in fixed stages. This one follows "
            "the approval route your business published — open it in Approvals "
            "to make a decision."))

    def draft_payslip_run(self):
        """Take a finished run back to draft.

        A separate decision from the approval itself (it is the `reopen`
        process in the catalogue, delivered later), so for now it is what it
        always was: available to whoever may edit the run, and it clears the
        stamp so a resubmission is a fresh attempt.
        """
        for run in self:
            run.check_access('write')
            if run.state == 'approval_pending':
                raise UserError(_(
                    "“%s” is waiting for its approval. Reject it, or ask the "
                    "approver to send it back.", run.name or ''))
        res = super(HrPayslipRun, self._pb_chain_ctx()).draft_payslip_run()
        self._pb_chain_ctx().write({'state': 'draft',
                                    'pb_source_revision': False})
        return res

    # ==================================================================
    # Removing a run, and removing what it produced
    # ==================================================================
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
        loose drafts on purpose, to stop a second payroll being computed on top
        of one that already exists.
        """
        if any(run.state == 'approval_pending' for run in self):
            raise UserError(_(
                "A pay run that is waiting for approval cannot be deleted. "
                "Reject it first."))
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
        """Throw away this run's draft payslips and keep the run itself."""
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
                'views': [[False, 'list'], [False, 'form']],
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
                'views': [[False, 'list'], [False, 'form']],
                'domain': [('company_id', '=', self.env.company.id),
                           ('date', '>=', self.date_start), ('date', '<=', self.date_end)]}
