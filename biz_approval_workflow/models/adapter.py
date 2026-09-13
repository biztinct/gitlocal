# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The contract a business model signs to gain approvals.

A business model inherits this mixin, sets ``_approval_process_key`` and
implements four methods. The engine knows nothing else about it — in
particular it never parses a scope key, so "division" and "scheme" stay words
that only the business module understands (ledger AM2).
"""

import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .request import STATES as REQUEST_STATES


class BizApprovalAdapterMixin(models.AbstractModel):
    _name = 'biz.approval.adapter.mixin'
    _description = 'Approval Adapter Mixin'

    # the biz.approval.process.key this model is approved under
    _approval_process_key = None

    #: Every catalogue key this model can serve, when ONE model answers to more
    #: than one process. A pay-data file is the case that forced it: the same
    #: `hr.payroll.import.batch` is "this run only" when the figures are used
    #: once and "past pay data" when they are kept, and a business that wants
    #: one checked and the other waved through must be able to say so. The
    #: class attribute is the STATIC declaration (the catalogue reads it to know
    #: the row is wired up); `_approval_process_key_for` is the per-record
    #: answer. A model with a single key leaves both alone.
    _approval_process_keys = ()

    approval_request_id = fields.Many2one(
        'biz.approval.request', string='Approval', compute='_compute_approval',
        compute_sudo=True)
    approval_state = fields.Selection(
        REQUEST_STATES, string='Approval status', compute='_compute_approval',
        compute_sudo=True)

    @api.depends()
    def _compute_approval(self):
        """The latest attempt, worked out on every read: there is deliberately
        no stored link, so a request can never disagree with its record."""
        Request = self.env['biz.approval.request'].sudo()
        for rec in self:
            found = Request.search([
                ('res_model', '=', rec._name), ('res_id', '=', rec.id),
            ], order='attempt desc, id desc', limit=1)
            rec.approval_request_id = found
            rec.approval_state = found.state if found else False

    # ------------------------------------------------------ must implement
    def _approval_context(self):
        """The frozen truth about this record at submission.

        Returns a dict: company_id, title, scope_keys (most specific first,
        last one ''), kind_key, facts {key: {'value','unit'}}, amount,
        currency_id, maker_uids, submitter_uid, subject_uids, source_revision,
        evidence [{key,name,ok,note}].
        """
        raise NotImplementedError(
            "%s must say what its approval is about." % self._name)

    @api.model
    def _approval_capabilities(self):
        """What a workflow designer may ask about this kind of record."""
        raise NotImplementedError(
            "%s must say what a workflow may check." % self._name)

    @api.model
    def _approval_coverage_scopes(self, company):
        """Every place this process happens, for the whole-coverage scan."""
        raise NotImplementedError(
            "%s must list the places it applies." % self._name)

    def _approval_apply(self, request):
        """Carry out the change the approval authorised.

        Must be idempotent and must re-check the source revision; the engine
        calls it once, under the request lock, and records what happened.
        """
        raise NotImplementedError(
            "%s must say what happens once it is approved." % self._name)

    # ----------------------------------------------------- may override
    @api.model
    def _approval_scope_options(self, company):
        """The narrowings a workflow for this kind of record may be given.

        Returns a list of LEVELS, each ``{'level': key, 'label': str,
        'options': [{'key': scope fragment, 'label': str}]}``. A configuration
        screen joins the chosen fragments, most specific level first, into the
        one opaque ``scope_key`` a binding carries; the engine still never
        parses it (ledger AM2).

        The default is an empty list: a model that has said nothing offers
        only whatever the configuration module adds for every process.
        """
        return []

    def _approval_validate(self):
        """Raise a UserError for a domain reason this cannot be sent in."""
        return True

    def _approval_card_count(self, request):
        """How big this request is, in the units the THING is counted in.

        A pay run is a number of payslips; a week is a number of hours. An
        inbox that had to know which is which would be an inbox that learns a
        new process every phase, so it asks the adapter and falls back to
        counting the facts it recognises.
        """
        return ''

    def _approval_detail(self, request):
        """An optional small table the request drawer draws under the facts.

        Deliberately SHAPE-ONLY, so the drawer learns nothing about any
        particular process: ``{'title', 'columns': [str], 'rows': [{'head',
        'sub', 'cells': [str], 'tone'}], 'chips': [{'label', 'value'}],
        'note'}``. Return ``None`` for "there is nothing more to show".
        """
        return None

    def _approval_freeze(self, request):
        """Lock whatever must not move while the approval is open."""
        return True

    def _approval_advance(self, request):
        """One step was decided and the request is still open.

        The record's own status usually has to move with the route — a request
        that has passed its first approver is not in the same place it was
        when it was sent in, and a form that still says "waiting for the line
        manager" after the line manager said yes is a screen that lies. The
        engine calls this after every decision that does NOT finish the
        request; `_approval_apply` is still the only thing called when it does.

        Never raises out: a consumer that cannot follow the route must not be
        able to undo a decision somebody really made.
        """
        return True

    def _approval_return(self, request, reason):
        """Make the record editable again after it was sent back."""
        return True

    def _approval_reject(self, request, reason):
        """Turned down for good. Say so on the record.

        Separate from `_approval_return` because the two are different answers:
        sent back means "change it and ask again", turned down means "no". A
        record left reading "waiting for approval" after somebody said no is a
        screen that lies.
        """
        return True

    def _approval_manager_uids(self):
        """Users behind "their manager" — the subjects' own managers."""
        self.ensure_one()
        context = self._approval_context()
        uids = context.get('subject_uids') or []
        if not uids:
            return []
        employees = self.env['hr.employee'].sudo().search([
            ('user_id', 'in', uids)])
        managers = employees.mapped('parent_id.user_id')
        return managers.ids

    def _approval_skip_manager_uids(self):
        """Users behind "their manager's manager"."""
        self.ensure_one()
        context = self._approval_context()
        uids = context.get('subject_uids') or []
        if not uids:
            return []
        employees = self.env['hr.employee'].sudo().search([
            ('user_id', 'in', uids)])
        return employees.mapped('parent_id.parent_id.user_id').ids

    # ------------------------------------------------------- conveniences
    def action_approval_submit(self):
        self.ensure_one()
        return self.env['biz.approval.engine'].submit(self)

    @staticmethod
    def _approval_revision_of(values):
        """A short, stable stamp of the values an approval covers."""
        raw = json.dumps(values, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]

    def _approval_process_key_for(self):
        """Which catalogue row THIS record is approved under.

        The default is the class attribute, which is the whole answer for a
        model that serves one process. A model that serves several overrides
        this and lists them all in `_approval_process_keys`.
        """
        self.ensure_one()
        return self._approval_process_key

    def _approval_process(self):
        self.ensure_one()
        key = self._approval_process_key_for()
        if not key:
            raise UserError(_("This kind of record cannot be approved yet."))
        process = self.env['biz.approval.process']._by_key(key)
        if not process:
            raise UserError(_(
                "This kind of record is not set up for approvals yet."))
        return process
