# -*- coding: utf-8 -*-
"""`pb.work.segment` — the days a person spends somewhere other than home.

THE IMPLICIT SEGMENT
--------------------
A whole month at the standing employment is the normal case and is written
NOWHERE. A segment exists only for an exception: a mid-month joiner, a leaver,
a transfer, a secondment, a split month, a part-time arrangement. That is what
makes ledger rule 8 hold in its Phase-5 form — a person with no segment is
computed by exactly the code that computed them yesterday, because
`factor_for` returns `(1.0, None)` before it looks at anything.

THE TWO PATTERNS (ruling G8)
----------------------------
  each_pays  each entity pays its own days. The home payslip is reduced to the
             days that stayed at home; the host entity runs its own payslip for
             its own days, under its own scheme and in its own currency.
  home_pays  the home payslip stays whole and an internal cost line moves the
             host's share across. No accounting posting — the owner's ruling
             stands: this product has no accounting connection.

The pattern is the group's, with a per-segment override, and `effective_policy`
is the one place that decision is made.

WHY THE FACTOR IS TINY AND WRAPPED
----------------------------------
This is the only thing in the whole programme that can change a number on a
payslip. So it is one function, it is called from one place, it returns
`(1.0, None)` on ANY exception, and the exception is logged where a run
summary can read it. A segment can never break a pay run.
"""

import logging
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

#: The two payment patterns, spelled once.
POLICY_EACH = 'each_pays'
POLICY_HOME = 'home_pays'

POLICY_LABELS = {
    POLICY_EACH: "Each entity pays its own days",
    POLICY_HOME: "Home pays, host is charged",
}

#: What a segment IS, in the words the screen uses.
KINDS = [
    ('split', 'Split month — days in another entity'),
    ('transfer', 'Transfer — moved to another entity'),
    ('joiner', 'Joined part-way through the month'),
    ('leaver', 'Left part-way through the month'),
    ('parttime', 'Part-time arrangement'),
]

#: Segments the pay-run population and the factor treat as "the person was
#: simply not here for the whole month" rather than "the person was somewhere
#: else that also pays them".
PRESENCE_KINDS = ('joiner', 'leaver')

#: Derived rows a person may not edit — the nightly job owns them.
DERIVED_KINDS = ('joiner', 'leaver')

#: The provenance `via` values that mean "this number is written on the
#: contract, per month". They are the payroll engine's own spellings — the
#: contract wage branch, the contract's component lines, and that branch's
#: default — and they are the whole definition of "basic pay and fixed
#: allowances" this module uses.
CONTRACT_VIA = ('contract_field', 'contract', 'contract_default')


class PbWorkSegment(models.Model):
    _name = 'pb.work.segment'
    _description = 'Work segment'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'

    person_id = fields.Many2one(
        'pb.person', string='Person', required=True, index=True,
        ondelete='cascade', tracking=True)
    home_employee_id = fields.Many2one(
        'hr.employee', string='Home employment', required=True, index=True,
        ondelete='cascade', tracking=True,
        help="The employment whose month these days come out of.")
    home_company_id = fields.Many2one(
        'res.company', string='Home entity',
        related='home_employee_id.company_id', store=True, readonly=True)

    host_company_id = fields.Many2one(
        'res.company', string='Host entity', required=True, index=True,
        ondelete='restrict', tracking=True,
        help="Where the person actually worked these days. For a joiner or a "
             "leaver this is the same entity as home.")
    host_employee_id = fields.Many2one(
        'hr.employee', string='Host employment', ondelete='set null',
        tracking=True,
        help="The employment in the host entity that pays these days. Needed "
             "only when each entity pays its own days.")
    division_id = fields.Many2one(
        'pb.division', string='Division', ondelete='set null',
        help="The part of the business these days belong to.")
    config_id = fields.Many2one(
        'hr.formula.config', string='Host payroll scheme',
        ondelete='restrict',
        help="The scheme that pays these days. Left empty, the host entity's "
             "own map answers.")

    date_from = fields.Date(string='From', required=True, tracking=True)
    date_to = fields.Date(string='To', required=True, tracking=True)
    month = fields.Date(
        string='Month', compute='_compute_month', store=True, index=True)

    days = fields.Float(
        string='Working days', compute='_compute_days', store=True,
        readonly=False, tracking=True,
        help="Working days in this stretch, from the home employment's "
             "working calendar. You can type a different number.")
    month_days = fields.Float(
        string='Working days in the month', compute='_compute_days',
        store=True, readonly=False)
    share = fields.Float(
        string='Share of the month', compute='_compute_share', store=True,
        digits=(16, 6),
        help="These days divided by the working days in the month.")
    # NO `default=`. A stored compute with `readonly=False` treats a default
    # as a value the caller supplied, so the compute never runs and every
    # stretch of days is worth zero full-time people — which is the whole
    # figure this field exists to carry.
    fte = fields.Float(
        string='Full-time equivalent',
        compute='_compute_fte', store=True, readonly=False, digits=(16, 4),
        help="How much of a full-time person this stretch is worth. The same "
             "as the share unless somebody types otherwise, which is how "
             "part-time is written down.")

    pay_policy = fields.Selection(
        [('inherit', 'Whatever the group says'),
         (POLICY_EACH, POLICY_LABELS[POLICY_EACH]),
         (POLICY_HOME, POLICY_LABELS[POLICY_HOME])],
        string='How it is paid', default='inherit', required=True,
        tracking=True)
    effective_policy = fields.Selection(
        [(POLICY_EACH, POLICY_LABELS[POLICY_EACH]),
         (POLICY_HOME, POLICY_LABELS[POLICY_HOME])],
        string='Pattern in force', compute='_compute_effective_policy',
        store=True)

    kind = fields.Selection(KINDS, string='Kind', required=True,
                            default='split', tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'),
         ('cancelled', 'Cancelled')],
        string='Status', default='draft', required=True, index=True,
        tracking=True)
    derived = fields.Boolean(
        string='Worked out automatically', default=False, readonly=True,
        help="Written by the nightly job from the contract dates. Editing it "
             "by hand would be undone the next night.")
    note = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    # ---------------------------------------------------------------- compute
    @api.depends('date_from')
    def _compute_month(self):
        for seg in self:
            seg.month = seg.date_from.replace(day=1) if seg.date_from \
                else False

    @api.depends('date_from', 'date_to', 'home_employee_id')
    def _compute_days(self):
        for seg in self:
            if not (seg.date_from and seg.date_to
                    and seg.date_from <= seg.date_to):
                seg.days = 0.0
                seg.month_days = 0.0
                continue
            first = seg.date_from.replace(day=1)
            last = self._month_end(seg.date_from)
            seg.days = self._working_days(seg.home_employee_id,
                                          seg.date_from, seg.date_to)
            seg.month_days = self._working_days(seg.home_employee_id,
                                                first, last)

    @api.depends('days', 'month_days')
    def _compute_share(self):
        for seg in self:
            total = seg.month_days or 0.0
            seg.share = round((seg.days or 0.0) / total, 6) if total else 0.0

    @api.depends('share')
    def _compute_fte(self):
        for seg in self:
            # A share the reader has not overridden IS the full-time
            # equivalent. Typing a different one is how part-time is written.
            if not seg.fte or seg.fte <= 0:
                seg.fte = seg.share

    @api.depends('pay_policy', 'home_company_id', 'host_company_id')
    def _compute_effective_policy(self):
        default = self.env['pb.work.segment']._group_policy()
        for seg in self:
            if seg.pay_policy in (POLICY_EACH, POLICY_HOME):
                seg.effective_policy = seg.pay_policy
                continue
            seg.effective_policy = seg._group_policy(seg.home_company_id) \
                or default

    # ------------------------------------------------------------- the dates
    @api.model
    def _month_end(self, day):
        first = day.replace(day=1)
        return (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    @api.model
    def _working_days(self, employee, start, end):
        """Working days in a stretch, from the employment's own calendar.

        Falls back to calendar days when there is no calendar to read, which
        is the same fallback `_get_proration_days` already makes in the
        payroll engine — one answer, two callers.
        """
        if not start or not end or start > end:
            return 0.0
        if employee:
            try:
                data = employee.sudo()._get_work_days_data(
                    datetime.combine(start, time.min),
                    datetime.combine(end + timedelta(days=1), time.min),
                    compute_leaves=False)
                days = float(data.get('days') or 0.0)
                if days:
                    return days
            except Exception as exc:        # noqa: BLE001
                _logger.debug('Work segment: calendar days fell back: %s', exc)
        return float((end - start).days + 1)

    # ------------------------------------------------------------ the policy
    @api.model
    def _group_policy(self, company=None):
        """What the group says, or the safe default.

        `each_pays` is the default because it is the pattern that keeps each
        entity's books its own — and because it is the only one of the two
        that produces a second payslip, which is the thing a reader can see.
        """
        try:
            if 'pb.group' not in self.env:
                return POLICY_EACH
            Group = self.env['pb.group'].sudo()
            if 'split_pay_policy' not in Group._fields:
                return POLICY_EACH
            group = Group.for_company(company) if company else \
                Group.search([], order='id', limit=1)
            if not group:
                group = Group.search([], order='id', limit=1)
            return group.split_pay_policy or POLICY_EACH
        except Exception:       # noqa: BLE001
            return POLICY_EACH

    @api.model
    def policy_label(self, policy):
        return _(POLICY_LABELS.get(policy or POLICY_EACH,
                                   POLICY_LABELS[POLICY_EACH]))

    # --------------------------------------------------------- the refusals
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for seg in self:
            if not (seg.date_from and seg.date_to):
                continue
            if seg.date_from > seg.date_to:
                raise ValidationError(_(
                    "The first day has to come before the last one."))
            if (seg.date_from.year, seg.date_from.month) != \
                    (seg.date_to.year, seg.date_to.month):
                raise ValidationError(_(
                    "A stretch of days belongs to one month. Split it into "
                    "one for each month and each pay run will find its own."))

    @api.constrains('host_employee_id', 'host_company_id', 'person_id')
    def _check_host_employment(self):
        for seg in self:
            host = seg.host_employee_id
            if not host:
                continue
            if host.company_id != seg.host_company_id:
                raise ValidationError(_(
                    "%(name)s works for %(actual)s, not for %(wanted)s. Pick "
                    "an employment in the host entity.",
                    name=host.name or '',
                    actual=host.company_id.name or '',
                    wanted=seg.host_company_id.name or ''))
            if host.pb_person_id and seg.person_id \
                    and host.pb_person_id != seg.person_id:
                raise ValidationError(_(
                    "That employment belongs to somebody else. Join the two "
                    "records on the \"Same person?\" review first."))

    @api.constrains('state', 'person_id', 'date_from', 'date_to', 'share',
                    'kind')
    def _check_no_overlap_and_no_more_than_a_month(self):
        for seg in self.filtered(lambda s: s.state == 'confirmed'):
            if not (seg.date_from and seg.date_to and seg.person_id):
                continue
            siblings = self.sudo().search([
                ('id', '!=', seg.id),
                ('person_id', '=', seg.person_id.id),
                ('state', '=', 'confirmed'),
                ('date_from', '<=', seg.date_to),
                ('date_to', '>=', seg.date_from),
            ])
            clash = siblings.filtered(
                lambda s: s.home_employee_id == seg.home_employee_id
                and s.host_company_id == seg.host_company_id)
            if clash:
                raise ValidationError(_(
                    "%(name)s already has days in %(company)s between "
                    "%(start)s and %(end)s. Change those days instead of "
                    "adding a second stretch over the top.",
                    name=seg.person_id.name or '',
                    company=seg.host_company_id.name or '',
                    start=fields.Date.to_string(clash[0].date_from),
                    end=fields.Date.to_string(clash[0].date_to)))
            if seg.kind == 'parttime':
                continue
            month_start = seg.date_from.replace(day=1)
            month_end = self._month_end(seg.date_from)
            same_month = self.sudo().search([
                ('person_id', '=', seg.person_id.id),
                ('state', '=', 'confirmed'),
                ('kind', '!=', 'parttime'),
                ('date_from', '>=', month_start),
                ('date_to', '<=', month_end),
            ])
            total = sum(same_month.mapped('share'))
            if total > 1.0001:
                raise ValidationError(_(
                    "That would give %(name)s more than a full month of work "
                    "in %(month)s (%(total)s months' worth). Shorten one of "
                    "the stretches, or mark it as a part-time arrangement.",
                    name=seg.person_id.name or '',
                    month=month_start.strftime('%B %Y'),
                    total='%.2f' % total))

    @api.constrains('state', 'date_from', 'date_to', 'home_employee_id')
    def _check_the_month_is_not_already_paid(self):
        """A confirmed stretch may not land on a month that is already paid.

        Not a technical rule: a pay run that has been approved is a statement
        somebody made to a person about their money, and changing what it was
        built from afterwards is how two screens come to disagree for ever.
        The refusal names the month and the thing to do instead.
        """
        if self.env.context.get('pb_skip_closed_run_check'):
            return
        Slip = self.env.get('hr.payslip')
        if Slip is None:
            return
        for seg in self.filtered(lambda s: s.state == 'confirmed'):
            if not (seg.date_from and seg.home_employee_id):
                continue
            closed = Slip.sudo().search([
                ('employee_id', '=', seg.home_employee_id.id),
                ('date_from', '<=', seg.date_to),
                ('date_to', '>=', seg.date_from),
                ('state', 'not in', ('draft', 'cancel')),
            ], limit=1)
            if closed:
                nxt = (seg.date_from.replace(day=1) + timedelta(days=32))
                raise ValidationError(_(
                    "%(month)s is already paid for %(name)s. Add the change "
                    "in %(next_month)s instead, as a correction.",
                    month=seg.date_from.strftime('%B %Y'),
                    name=seg.home_employee_id.name or '',
                    next_month=nxt.strftime('%B %Y')))

    def write(self, vals):
        # A derived row belongs to the nightly job. Somebody editing one would
        # see their edit vanish the next morning, which is worse than being
        # told now.
        if not self.env.context.get('pb_derive'):
            locked = self.filtered(lambda s: s.derived)
            touched = set(vals) - {'active', 'note', 'state'}
            if locked and touched:
                raise ValidationError(_(
                    "This stretch is worked out from the contract dates, so "
                    "it cannot be edited by hand. Turn day-based pay off for "
                    "the entity if it should not be here."))
        return super().write(vals)

    # ------------------------------------------------------------- the doors
    def action_confirm(self):
        self.write({'state': 'confirmed'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True

    # =====================================================================
    # THE HOOK. Everything above is bookkeeping; this is the only thing that
    # can change a payslip.
    # =====================================================================
    @api.model
    def factor_for(self, payslip):
        """`(factor, meta)` for this payslip. NEVER raises.

        `(1.0, None)` means "this payslip is exactly what it was before this
        module existed" and is the answer for everybody without a confirmed
        segment in the period — which, on every database this ships to today,
        is everybody.
        """
        try:
            return self._factor_for(payslip)
        except Exception:       # noqa: BLE001 — a segment may never break a run
            _logger.warning(
                "Work segments could not be read for payslip %s — it is "
                "computed as a full month, exactly as before.",
                getattr(payslip, 'id', 0), exc_info=True)
            return 1.0, None

    @api.model
    def _segments_for(self, employee, date_from, date_to):
        """`(home, host)` confirmed segments touching this period."""
        if not (employee and date_from and date_to):
            return self.browse(), self.browse()
        rows = self.sudo().search([
            ('state', '=', 'confirmed'),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
            '|', ('home_employee_id', '=', employee.id),
                 ('host_employee_id', '=', employee.id),
        ])
        home = rows.filtered(lambda s: s.home_employee_id.id == employee.id)
        host = rows.filtered(lambda s: s.host_employee_id.id == employee.id)
        return home, host

    @api.model
    def factor_for_period(self, employee, date_from, date_to):
        """The same answer, for a caller that has no payslip.

        The import batch resolves a month's values before any payslip exists,
        so it cannot ask `factor_for`. One body, two doors — a second
        implementation of "how much of this month was worked here" is exactly
        the drift this programme exists to close.
        """
        try:
            return self._factor(employee, date_from, date_to)
        except Exception:       # noqa: BLE001
            _logger.warning(
                "Work segments could not be read for %s — the month is "
                "treated as whole, exactly as before.",
                getattr(employee, 'id', 0), exc_info=True)
            return 1.0, None

    @api.model
    def _factor_for(self, payslip):
        return self._factor(payslip.employee_id, payslip.date_from,
                            payslip.date_to)

    @api.model
    def _factor(self, employee, date_from, date_to):
        home, host = self._segments_for(employee, date_from, date_to)
        if not home and not host:
            return 1.0, None

        # ---- the HOST employment: it is paid for the days it hosted ------
        if host:
            share = min(1.0, max(0.0, sum(host.mapped('share'))))
            return share, {
                'kind': 'host',
                'factor': share,
                'segment_ids': host.ids,
                'days': sum(host.mapped('days')),
                'month_days': max(host.mapped('month_days') or [0.0]),
                'summary': self._summary(host, 'host', share),
                'transfers': [],
            }

        # ---- the HOME employment ----------------------------------------
        present = 1.0
        presence = home.filtered(lambda s: s.kind in PRESENCE_KINDS)
        if presence:
            present = min(1.0, max(0.0, sum(presence.mapped('share'))))
        away_each, transfers = 0.0, []
        for seg in home:
            if seg.kind in PRESENCE_KINDS:
                continue
            if seg.host_company_id == seg.home_company_id:
                # A stretch that never left the entity does not take days off
                # the entity's own payslip; it only moves them between
                # divisions, which is a reporting fact and not a pay one.
                continue
            if seg.effective_policy == POLICY_EACH:
                away_each += seg.share or 0.0
            else:
                transfers.append(seg.id)
        factor = min(1.0, max(0.0, present - away_each))
        meta = {
            'kind': 'home',
            'factor': factor,
            'segment_ids': home.ids,
            'days': round((factor) * (max(home.mapped('month_days') or [0.0])), 2),
            'month_days': max(home.mapped('month_days') or [0.0]),
            'summary': self._summary(home, 'home', factor),
            'transfers': transfers,
        }
        return factor, meta

    @api.model
    def _summary(self, segments, side, factor):
        """One sentence the payslip's own drawer can print."""
        if not segments:
            return ''
        first = segments[0]
        month = first.date_from.strftime('%B %Y') if first.date_from else ''
        days = sum(segments.mapped('days'))
        total = max(segments.mapped('month_days') or [0.0])
        where = ', '.join(sorted({s.host_company_id.name or ''
                                  for s in segments if s.host_company_id}))
        if side == 'host':
            return _(
                "%(days)s of %(total)s working days in %(month)s were worked "
                "here, so this payslip covers that share of the month.",
                days='%g' % days, total='%g' % total, month=month)
        return _(
            "%(kept)s of %(total)s working days in %(month)s were worked "
            "here; the rest were worked in %(where)s.",
            kept='%g' % round(factor * total, 2), total='%g' % total,
            month=month, where=where or _("another entity"))

    # =====================================================================
    # WHAT THE FACTOR IS APPLIED TO
    # =====================================================================
    @api.model
    def _prorated_codes(self, config, values, provenance=None):
        """The component codes a stretch of days may reduce, and nothing else.

        THE SCHEME'S OWN ANSWER WINS. A scheme that names its prorated
        components has already had this conversation with a person, and there
        is nothing to derive.

        FAILING THAT, THE TEST IS WHERE THE NUMBER CAME FROM, not what it is
        called. "Basic pay and fixed allowances" means, precisely, the
        standing monthly amounts written on somebody's CONTRACT — the wage,
        and the contract's own component lines. Those are the numbers that
        mean "per month", so those are the numbers a fraction of a month
        scales.

        Everything else is left exactly alone, and each for its own reason:
        a number a pay-data file or a connected system delivered is already
        THIS month's figure (halving it would halve the hours somebody
        actually worked); overtime, commission and one-off inputs are the
        same; a deduction is not pay; and a non-money column has no fraction.
        A first attempt used the net-pay classification instead — "the
        components net pay ADDS" — and on the live Retail scheme that set was
        EMPTY, because the scheme's earnings are all derived columns and its
        inputs are raw. An empty set is a silent no-op, which is the one
        answer a payroll rail may not give.

        With no provenance at all, this returns nothing but the scheme's own
        list. A caller that cannot say where a number came from cannot be
        allowed to scale it.
        """
        rules = config.rule_ids.filtered(lambda r: r.column_type == 'input')
        if not rules:
            return set()
        if getattr(config, 'use_proration', False) \
                and config.proration_component_ids:
            named = config.proration_component_ids
            return {r.code for r in named if r.code and r.code in values}
        if not provenance:
            return set()

        roles = self._roles_for(config)
        out = set()
        for rule in rules:
            if not rule.code or rule.code not in values:
                continue
            if getattr(rule, 'payroll_signal', False):
                continue
            kind = getattr(rule, 'value_kind', 'money') or 'money'
            if kind != 'money':
                continue
            entry = provenance.get(rule.code) or {}
            from_contract = ((entry.get('via') or '') in CONTRACT_VIA
                             or (entry.get('src') or '') == 'contract_component')
            if not from_contract:
                continue
            role = (roles.get(rule.id) or ('', False, 'money'))[0]
            if role in ('deduction', 'net'):
                continue
            out.add(rule.code)
        return out

    @api.model
    def _roles_for(self, config):
        """`{rule_id: (role, detail, value_kind)}` — stored, else derived.

        The same test the exact-cost lane applies (GR30): a scheme that cannot
        name which component IS net pay has not been classified, whatever else
        is ticked on it, and its own net-pay formula is walked read-only
        instead. Nothing is written back.
        """
        rules = config.rule_ids
        if not rules or 'net_role' not in rules._fields:
            return {}
        stored, has_net = {}, False
        for rule in rules:
            role = rule.net_role or ''
            if role == 'net':
                has_net = True
            stored[rule.id] = (
                role,
                bool(getattr(rule, 'net_role_detail', False)),
                getattr(rule, 'value_kind', 'money') or 'money')
        if has_net:
            return stored
        if not hasattr(config, '_build_net_role_classification'):
            return {}
        try:
            result = config._build_net_role_classification()
        except Exception as exc:        # noqa: BLE001
            _logger.info('Work segments: scheme %s cannot be classified: %s',
                         config.id, exc)
            return {}
        classification = (result or {}).get('_classification')
        if not classification:
            return {}
        return {
            rule.id: (classification.roles.get(rule.id) or '',
                      bool(classification.details.get(rule.id)),
                      getattr(rule, 'value_kind', 'money') or 'money')
            for rule in rules
        }

    @api.model
    def apply_to_inputs(self, payslip, config, values, provenance=None):
        """Reduce this payslip's fixed pay to the days it covers.

        Called from ONE place on this path — the payroll engine's input
        builder — behind a registry probe, and it returns before touching
        anything when there is no segment. Returns the meta so the caller can
        say what happened, or `None` when nothing happened at all.
        """
        return self._apply(payslip.employee_id, payslip.date_from,
                           payslip.date_to, config, values, provenance,
                           payslip=payslip)

    @api.model
    def apply_to_batch_inputs(self, batch, config, employee, contract, values,
                              provenance=None):
        """The same reduction, on the pay-data-file path.

        A run built from an uploaded pay file resolves its values in
        `hr.payroll.import.batch` and never reaches the payslip's own input
        builder — so without this door, a split month would be honoured on one
        of the two ways a run can be computed and silently ignored on the
        other. Same body, same guard, same "never break a run" wrapper.
        """
        try:
            return self._apply(employee, batch.date_from, batch.date_to,
                               config, values, provenance, batch=batch,
                               contract=contract)
        except Exception:       # noqa: BLE001
            _logger.warning(
                "Work segments could not be applied to batch %s for %s",
                getattr(batch, 'id', 0), getattr(employee, 'id', 0),
                exc_info=True)
            return None

    @api.model
    def _apply(self, employee, date_from, date_to, config, values,
               provenance=None, payslip=None, batch=None, contract=None):
        factor, meta = self.factor_for_period(employee, date_from, date_to)
        if meta is None or abs(factor - 1.0) < 1e-9:
            return None
        codes = self._prorated_codes(config, values, provenance)
        if not codes:
            # A stretch of days that reduces NOTHING is worth saying out loud:
            # it means the scheme has no standing monthly amount this rail can
            # recognise, and somebody looking at the payslip afterwards would
            # otherwise have no way to tell that from "the days did not apply".
            _logger.info(
                "Work segments: %s covers %.4f of the month for employee %s, "
                "but scheme %s has no component this rail may scale — the "
                "payslip is computed whole.",
                date_from, factor, getattr(employee, 'id', 0), config.id)
            meta['codes'] = []
            return meta
        rounding = int(getattr(config, 'proration_rounding', 0) or 0)
        changed = []
        for code in sorted(codes):
            try:
                old = float(values.get(code) or 0.0)
            except (TypeError, ValueError):
                continue
            if not old:
                continue
            new = old * factor
            if rounding:
                new = round(new, rounding)
            values[code] = new
            changed.append((code, old, new))
        meta['codes'] = [c for c, _o, _n in changed]
        self._write_proration_lines(config, meta, changed, employee,
                                    date_from, date_to, payslip=payslip,
                                    batch=batch, contract=contract)
        return meta

    @api.model
    def _write_proration_lines(self, config, meta, changed, employee,
                               date_from, date_to, payslip=None, batch=None,
                               contract=None):
        """One journal row per component the days reduced.

        The row goes in the table the payroll engine already keeps for exactly
        this — `hr.payroll.proration.line`, with `proration_basis='segment'` —
        so the payslip's provenance drawer explains a split month with the
        same words it uses for a mid-month pay rise, and nobody has to learn a
        second table.
        """
        Line = self.env.get('hr.payroll.proration.line')
        if Line is None or not changed:
            return
        if 'payslip_id' not in Line._fields:
            return
        Line = Line.sudo()
        if payslip:
            Line.search([('payslip_id', '=', payslip.id),
                         ('proration_basis', '=', 'segment')]).unlink()
        elif batch:
            Line.search([('import_batch_id', '=', batch.id),
                         ('employee_id', '=', employee.id),
                         ('proration_basis', '=', 'segment')]).unlink()
        if not contract and payslip:
            contract = payslip.contract_id
        by_code = {r.code: r for r in config.rule_ids if r.code}
        vals = []
        for code, old, new in changed:
            rule = by_code.get(code)
            if not rule:
                continue
            vals.append({
                'formula_config_id': config.id,
                'payslip_id': payslip.id if payslip else False,
                'import_batch_id': batch.id if batch else False,
                'employee_id': employee.id,
                'contract_id': contract.id if contract else False,
                'component_id': rule.id,
                'effective_date': date_from,
                'date_from': date_from,
                'date_to': date_to,
                'proration_basis': 'segment',
                'period_days': meta.get('month_days') or 0.0,
                'new_days': meta.get('days') or 0.0,
                'old_amount': old,
                'new_amount': old,
                'prorated_amount': new,
                'segment_summary': meta.get('summary') or '',
                'state': 'posted',
            })
        if vals:
            Line.create(vals)

    # =====================================================================
    # COST TRANSFERS — the other pattern's output
    # =====================================================================
    @api.model
    def write_transfers(self, payslip):
        """Under "home pays, host is charged", move the host's share across.

        Written AFTER the payslip is computed, because the amount is a share
        of what the month actually cost the employer, and that is not known
        until the components have run. Never posts to accounting: the owner's
        ruling is that this product has no accounting connection, so a
        transfer is a report line and an export.
        """
        try:
            return self._write_transfers(payslip)
        except Exception:       # noqa: BLE001
            _logger.warning(
                "Cost transfers could not be written for payslip %s",
                getattr(payslip, 'id', 0), exc_info=True)
            return self.env['pb.cost.transfer'].browse()

    @api.model
    def _write_transfers(self, payslip):
        Transfer = self.env['pb.cost.transfer'].sudo()
        employee = payslip.employee_id
        home, _host = self._segments_for(employee, payslip.date_from,
                                         payslip.date_to)
        charged = home.filtered(
            lambda s: s.effective_policy == POLICY_HOME
            and s.host_company_id != s.home_company_id
            and s.kind not in PRESENCE_KINDS)
        existing = Transfer.search([('payslip_id', '=', payslip.id)])
        if not charged:
            existing.unlink()
            return Transfer.browse()
        cost = self._employer_cost(payslip)
        existing.unlink()
        made = Transfer.browse()
        by_company = {}
        for seg in charged:
            hit = by_company.setdefault(seg.host_company_id.id,
                                        {'share': 0.0, 'segments': []})
            hit['share'] += seg.share or 0.0
            hit['segments'].append(seg.id)
        for company_id, hit in by_company.items():
            share = min(1.0, max(0.0, hit['share']))
            made |= Transfer.create({
                'person_id': (employee.pb_person_id.id
                              if employee.pb_person_id else False),
                'home_employee_id': employee.id,
                'payslip_id': payslip.id,
                'from_company_id': employee.company_id.id,
                'to_company_id': company_id,
                # RULE 7 — the amount is stored in the money it was paid in
                # and NEVER converted on the way in. A reader who wants it in
                # the group's money gets it converted at read time, with the
                # rate named, or told that nobody has priced the pair.
                'currency_id': employee.company_id.currency_id.id,
                'amount': round(cost * share, 2),
                'share': round(share, 6),
                'date_from': payslip.date_from,
                'date_to': payslip.date_to,
                'segment_ids': [(6, 0, hit['segments'])],
            })
        return made

    @api.model
    def _employer_cost(self, payslip):
        """What this month cost the employer, from the payslip's own lines.

        Employer cost when the scheme names it, and total earnings otherwise —
        a scheme with no employer-cost component has not told us what the
        on-costs are, and inventing a percentage would be inventing a number.
        """
        lines = payslip.line_ids
        if not lines:
            return 0.0
        if 'pay_role' in lines._fields:
            detail = 'component_detail' in lines._fields
            employer = sum(
                abs(line.total) for line in lines
                if line.pay_role == 'employer_cost'
                and not (detail and line.component_detail))
            earnings = sum(
                line.total for line in lines
                if line.pay_role == 'earning'
                and not (detail and line.component_detail))
            if earnings or employer:
                return float(earnings + employer)
        # No classification at all: the closest honest figure is what the
        # payslip says it paid, so the net line stands in. It is an
        # UNDER-statement of employer cost, never an over-statement, which is
        # the right way round for a figure somebody is going to be charged.
        net = lines.filtered(lambda l: (l.code or '').upper() == 'NET')
        if net:
            return float(sum(net.mapped('total')))
        return float(sum(l.total for l in lines if l.total > 0))

    # =====================================================================
    # DERIVED JOINER / LEAVER SEGMENTS
    # =====================================================================
    @api.model
    def derive_joiners_and_leavers(self, company=None, on_date=None):
        """Write (or remove) the segments the contract dates imply.

        Runs ONLY for companies whose switch is on, because turning day-based
        pay on for people who start or leave mid-month changes what those
        people are paid — and doing that to an existing customer without them
        asking is the one thing this phase is most careful not to do.
        """
        Company = self.env['res.company'].sudo()
        companies = company if company is not None else Company.search([])
        if isinstance(companies, int):
            companies = Company.browse(companies)
        made, removed = 0, 0
        day = fields.Date.to_date(on_date) if on_date else \
            fields.Date.context_today(self)
        month_start = day.replace(day=1)
        month_end = self._month_end(day)
        for one in companies:
            on = bool(getattr(one, 'prorate_joiners_leavers', False))
            existing = self.sudo().search([
                ('derived', '=', True),
                ('home_company_id', '=', one.id),
                ('date_from', '>=', month_start),
                ('date_to', '<=', month_end),
            ])
            if not on:
                removed += len(existing)
                existing.with_context(pb_derive=True).unlink()
                continue
            wanted = self._joiner_leaver_rows(one, month_start, month_end)
            seen = set()
            by_employee = {s.home_employee_id.id: s for s in existing}
            for row in wanted:
                seen.add(row['home_employee_id'])
                found = by_employee.get(row['home_employee_id'])
                if found:
                    found.with_context(pb_derive=True,
                                       pb_skip_closed_run_check=True).write(row)
                else:
                    self.sudo().with_context(
                        pb_derive=True, pb_skip_closed_run_check=True,
                        tracking_disable=True, mail_create_nolog=True,
                    ).create(row)
                    made += 1
            stale = existing.filtered(
                lambda s: s.home_employee_id.id not in seen)
            removed += len(stale)
            stale.with_context(pb_derive=True).unlink()
        return {'created': made, 'removed': removed}

    @api.model
    def _joiner_leaver_rows(self, company, month_start, month_end):
        """The people whose contract started or ended inside this month."""
        if 'hr.contract' not in self.env:
            return []
        Person = self.env['pb.person']
        rows = []
        contracts = self.env['hr.contract'].sudo().search([
            ('company_id', '=', company.id),
            ('state', 'in', ('open', 'close')),
            '|',
            '&', ('date_start', '>=', month_start),
                 ('date_start', '<=', month_end),
            '&', ('date_end', '>=', month_start),
                 ('date_end', '<=', month_end),
        ])
        for contract in contracts:
            employee = contract.employee_id
            if not employee:
                continue
            start = max(contract.date_start or month_start, month_start)
            end = min(contract.date_end or month_end, month_end)
            if start > end:
                continue
            if start == month_start and end == month_end:
                continue
            kind = 'joiner' if start > month_start else 'leaver'
            person = employee.pb_person_id or Person.for_employee(employee)
            rows.append({
                'person_id': person.id,
                'home_employee_id': employee.id,
                'host_company_id': company.id,
                'date_from': start,
                'date_to': end,
                'kind': kind,
                'state': 'confirmed',
                'derived': True,
                'pay_policy': 'inherit',
            })
        return rows

    @api.model
    def _cron_derive(self):
        """The nightly job. Guarded on the REGISTRY, never on the method.

        GR14 and GR25 between them: a cron row lands the moment the module
        installs, and the worker already running has neither this code nor
        this table. So the cron's server action names a model every worker has
        had since an earlier phase, and the body checks the registry before it
        touches anything.
        """
        if 'pb.work.segment' not in self.env:
            return False
        try:
            return self.env['pb.work.segment'].sudo().derive_joiners_and_leavers()
        except Exception:       # noqa: BLE001
            _logger.warning('The joiner and leaver job could not run',
                            exc_info=True)
            return False
