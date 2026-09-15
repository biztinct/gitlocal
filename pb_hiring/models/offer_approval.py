# -*- coding: utf-8 -*-
"""An offer travels the route the business published: the hiring manager, then
the HR lead.

WHY THE HIRING MANAGER AND NOT "THEIR MANAGER". The person who asked for the
role is the person whose team this candidate joins and whose budget the money
comes out of. The maker is a recruiter, and a recruiter's own line manager has
no view at all on whether this candidate is worth this number — so the manager
rung asks the record who it is FOR, exactly as the advert's route does (AM50
reached from the same direction twice).

WHAT AN APPROVER IS AGREEING TO is the money and the day. Both are in the
revision stamp, so changing a figure after the hiring manager has said yes
sends it round again (AM32). The background-check status is deliberately NOT
in the stamp: it is true of the world rather than of the record — a reference
lands, a flag is cleared — and the door it guards is checked at the moment the
offer is drafted, which is the only moment it can honestly be checked.

THE MONEY THE ENGINE ROUTES ON IS THE YEAR, not the month. A business writing
"anything over X needs Finance" says it in annual terms, and it is the same
number the hiring request's own budget check was made against — one figure,
one meaning, across the two sign-offs that make up a hire.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

from .hiring_common import GROUP_MANAGER, OFFER_PERIODS

_logger = logging.getLogger(__name__)

OFFER_PROCESS_KEY = 'hiring_offer'

register_chain(
    'pb.hiring.offer', OFFER_PROCESS_KEY,
    submit_state='submitted',
    driven=('manager_ok', 'hr_ok'),
    employee_field=None,
    amount_field='annual_total',
    currency_field='currency_id',
    date_field='start_date',
)


def offer_route():
    """Today's ladder, written as a route somebody can read and change."""
    return route(
        manager_step(_('The hiring manager')),
        role_step(_('HR lead'), 'hr_lead', key='hr'),
    )


class PbHiringOfferApproval(models.Model):
    _inherit = 'pb.hiring.offer'

    _approval_process_key = OFFER_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Offer · %(who)s, %(role)s",
                 who=self.candidate_name or '', role=self.job_title or '')

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().requisition_id.company_id[:1] or self.env.company

    def _chain_facts(self):
        """Read as the system: the facts a route is CHOSEN on must be readable
        by the engine whoever the maker is (AM40), and the maker here is a
        recruiter who may hold no permission on a candidate's money."""
        self.ensure_one()
        rec = self.sudo()
        currency = rec.currency_id.name or ''
        return {
            'monthly_total': {'value': float(rec.monthly_total or 0.0),
                              'unit': currency},
            'annual_total': {'value': float(rec.annual_total or 0.0),
                             'unit': currency},
            'start_date': {'value': str(rec.start_date or ''), 'unit': ''},
            'job_title': {'value': rec.job_title or '', 'unit': ''},
            'department': {'value': rec.requisition_id.department_id.name or '',
                           'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'monthly_total': {'type': 'decimal', 'label': _('A month of it')},
            'annual_total': {'type': 'decimal', 'label': _('A year of it')},
            'start_date': {'type': 'char', 'label': _('Starting on')},
            'job_title': {'type': 'char', 'label': _('The job title')},
            'department': {'type': 'char',
                           'label': _('Which part of the business')},
        }

    def _chain_revision_values(self):
        """THE NUMBERS ARE WHAT SOMEBODY IS SIGNING FOR, so they are in the
        stamp. Every line, in order, plus the day they start."""
        self.ensure_one()
        return {
            'start_date': str(self.start_date or ''),
            'lines': '|'.join(
                '%s:%s:%s:%s' % ((ln.name or '').strip(), ln.kind or '',
                                 round(ln.amount or 0.0, 2), ln.period or '')
                for ln in self.line_ids.sorted(lambda r: (r.sequence, r.id))),
        }

    def _approval_detail(self, request):
        self.ensure_one()
        req = self.requisition_id
        chips = [
            {'label': _('Candidate'), 'value': self.candidate_name or ''},
            {'label': _('Starting on'), 'value': str(self.start_date or '')},
            {'label': _('A month of it'),
             'value': self._money(self.monthly_total)},
            {'label': _('A year of it'),
             'value': self._money(self.annual_total)},
        ]
        if req.department_id:
            chips.append({'label': _('Part of the business'),
                          'value': req.department_id.name})
        periods = dict(OFFER_PERIODS)
        return {
            'title': _('What is being offered'),
            'columns': [_('What it is'), _('Amount'), _('How often')],
            'rows': [[ln.name or '', self._money(ln.amount),
                      periods.get(ln.period, '')]
                     for ln in self.line_ids.sorted(
                         lambda r: (r.sequence, r.id))],
            'chips': chips,
            'note': req.name or '',
        }

    # =====================================================================
    #  Who
    # =====================================================================
    def _approval_manager_uids(self):
        """The hiring manager, named on the record."""
        self.ensure_one()
        return self._offer_manager_uids()

    def _approval_skip_manager_uids(self):
        """Nobody is skipped. The hiring manager is the only person on this
        route who knows the candidate, and skipping them would leave the
        money agreed by people who have never met them."""
        self.ensure_one()
        return []

    def _offer_manager_uids(self):
        """Who is asked, in the order they are asked.

        The person who asked for the role; then the manager the candidate
        would report to; then that person's own manager. Whoever it lands on
        is NAMED in the title, so an approver is never a mystery.
        """
        self.ensure_one()
        req = self.requisition_id.sudo()
        Employee = self.env['hr.employee'].sudo()
        asked = Employee.browse(req.requested_by_id.id).exists()
        candidates = []
        if asked.user_id and asked.user_id.id != self.create_uid.id:
            candidates.append(asked.user_id.id)
        reporting = Employee.browse(
            (self.reporting_manager_id or req.reporting_manager_id).id).exists()
        if reporting.user_id:
            candidates.append(reporting.user_id.id)
        if asked.parent_id.user_id:
            candidates.append(asked.parent_id.user_id.id)
        if not candidates and asked.user_id:
            candidates.append(asked.user_id.id)
        seen, out = set(), []
        for uid in candidates:
            if uid and uid not in seen:
                seen.add(uid)
                out.append(uid)
        return out

    def _approval_can(self, from_state, to_state):
        """The manager rung is open to the RIGHT manager and to the HR team."""
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        if to_state in ('manager_ok', 'refused') and from_state == 'submitted':
            if self.env.uid in self._offer_manager_uids():
                return True
            return self.env.user.has_group(GROUP_MANAGER)
        return super()._approval_can(from_state, to_state)

    def _chain_engine_write(self, to_state):
        """The ENGINE'S OWN write of this record's status runs as the system.

        A SEAT IS A READ AND NEVER A WRITE (AM60), which is right — but this
        chain mirrors an intermediate status onto the record while the acting
        user is the approver, and that approver is by design somebody who may
        hold no hiring permission at all: the department head whose team the
        candidate is joining. The rule refused the mirror, the engine
        swallowed it (it must — a decision a person really made can never be
        undone by a consumer that cannot follow its own route), and the offer
        sat one rung behind for ever with only a line in the server log
        (R132, found on the hiring request and true of every chain in this
        module).

        The trail is unaffected: `_chain_log` still runs as the acting user,
        so the approval log keeps the real name.
        """
        return super(PbHiringOfferApproval,
                     self.sudo())._chain_engine_write(to_state)

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', GROUP_MANAGER)
        return Seed.lay(
            company, OFFER_PROCESS_KEY, 'Offer', offer_route(),
            binding_note='The route every offer follows unless a part of the '
                         'business is given its own. The hiring manager sees '
                         'the money first, because it is their team and their '
                         'budget; the HR lead sees it last, because it has to '
                         'sit beside what everybody else is paid.',
            model_name='pb.hiring.offer',
            role_keys=('hr_lead',),
            reason='Set up when offers were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.hiring.offer']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_hiring: %s has no offer route', company.name)
    return done
