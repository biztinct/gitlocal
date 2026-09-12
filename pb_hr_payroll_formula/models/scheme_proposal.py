# -*- coding: utf-8 -*-
"""Changing how pay is worked out is a thing somebody signs off.

WHAT WAS TRUE BEFORE. Five doors changed a live pay scheme, and every one of
them was a button: activate a scheme, merge a branch into it, seal a release,
roll a release back, archive it. Each was gated on "may this person edit
schemes?" and on nothing else — so the person who wrote a formula was the
person who put it into production, at the moment they finished writing it, with
no record of anybody agreeing.

WHAT IS TRUE NOW. Each of those doors is closed except from one place: the
apply of an APPROVED proposal. A proposal is a real record — what is changing,
against which sealed content, what the tests said — and it travels the route
the business published for "Scheme change" like any other request.

THE SEAL. `sealed_hash` is the content hash of the thing being put live (the
branch for a merge, the scheme itself for everything else). It is checked again
at apply time: if the scheme moved after somebody approved it, the approval no
longer covers it and the door stays shut with a sentence that says what to do.

THE WAY THROUGH FOR A BUSINESS THAT DOES NOT WANT THIS. There is one, because
the business decides (the flexibility ruling): a company with no published
scheme-change route, or one whose route is the fast lane, keeps the old
one-press behaviour — and the press still writes a proposal row marked
`applied`, so the trail exists either way.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: The five things a proposal can ask for.
PROPOSAL_KINDS = [
    ('activate', 'Put the scheme live'),
    ('merge', 'Merge a branch into the live scheme'),
    ('release', 'Seal a release'),
    ('rollback', 'Roll a release back'),
    ('archive', 'Retire the scheme'),
]
KIND_NAME = dict(PROPOSAL_KINDS)

#: The sentinel a door checks for. A module-level `object()` IDENTITY, so a
#: context value arriving over `call_kw` can never equal it.
SCHEME_APPLY_KEY = 'pb_scheme_apply'
SCHEME_APPLY_TOKEN = object()

#: The catalogue key this model is approved under. The row ships as "Scheme
#: change" in `pb_approval_config/data/processes.xml`.
SCHEME_PROCESS_KEY = 'scheme'

#: Category codes that mean a component is a statutory deduction — the ones
#: that make a change "touches tax" for a route that wants to ask.
_TAX_TOKENS = ('TAX', 'PIT', 'SI', 'HI', 'UI', 'INSUR', 'STAT', 'SOCIAL')


def apply_context(record):
    """The recordset a sanctioned apply uses (it carries the sentinel)."""
    return record.with_context(**{SCHEME_APPLY_KEY: SCHEME_APPLY_TOKEN})


def is_applying(env):
    return env.context.get(SCHEME_APPLY_KEY) is SCHEME_APPLY_TOKEN


class PbSchemeProposal(models.Model):
    _name = 'pb.scheme.proposal'
    _inherit = ['biz.approval.adapter.mixin']
    _description = 'Pay Scheme Change Proposal'
    _order = 'create_date desc, id desc'

    _approval_process_key = SCHEME_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    config_id = fields.Many2one('hr.formula.config', string='Pay scheme',
                                required=True, index=True, ondelete='cascade')
    kind = fields.Selection(PROPOSAL_KINDS, required=True, index=True)
    branch_id = fields.Many2one('hr.formula.config', string='Branch',
                                ondelete='set null')
    release_id = fields.Many2one('hr.formula.release', string='Release',
                                 ondelete='set null')
    from_milestone_id = fields.Many2one('hr.formula.config.milestone',
                                        string='Since', ondelete='set null')

    sealed_hash = fields.Char(string='Content stamp', readonly=True)
    diff_json = fields.Text(string='What changes (JSON)', readonly=True)
    test_summary_json = fields.Text(string='Checks (JSON)', readonly=True)
    note = fields.Char(string='Note')

    rules_changed = fields.Integer(readonly=True)
    payslips_per_month = fields.Integer(readonly=True)
    tests_passed = fields.Boolean(readonly=True)
    has_shadow_run = fields.Boolean(readonly=True)
    touches_tax = fields.Boolean(readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Waiting for approval'),
        ('approved', 'Approved'),
        ('applied', 'Carried out'),
        ('returned', 'Sent back'),
        ('rejected', 'Turned down'),
    ], default='draft', required=True, index=True, readonly=True, copy=False)
    applied_at = fields.Datetime(readonly=True, copy=False)
    applied_release_id = fields.Many2one('hr.formula.release',
                                         string='Release it produced',
                                         readonly=True, copy=False)
    apply_note = fields.Char(readonly=True, copy=False)

    @api.depends('config_id', 'kind')
    def _compute_name(self):
        for proposal in self:
            proposal.name = _(
                "%(what)s · %(scheme)s",
                what=_(KIND_NAME.get(proposal.kind, proposal.kind or '')),
                scheme=proposal.config_id.name or '')

    # ==================================================================
    # building one
    # ==================================================================
    @api.model
    def propose(self, config, kind, branch=None, release=None, note=None,
                diff=None, tests=None):
        """Create a proposal for a change that has not happened yet."""
        if kind not in KIND_NAME:
            raise UserError(_("That is not a change this can ask for."))
        config = config if isinstance(config, models.BaseModel) \
            else self.env['hr.formula.config'].browse(int(config))
        if not config.exists():
            raise UserError(_("That pay scheme no longer exists."))
        # The person proposing must be allowed to change the scheme; asking for
        # a change is not a way around that.
        config.check_access('write')
        candidate = branch or config
        proposal = self.create({
            'company_id': (config.company_id or self.env.company).id,
            'config_id': config.id,
            'kind': kind,
            'branch_id': branch.id if branch else False,
            'release_id': release.id if release else False,
            'note': (note or '')[:512] or False,
            'sealed_hash': candidate._content_hash(),
            'diff_json': json.dumps(diff or []),
            'test_summary_json': json.dumps(tests or {}),
        })
        proposal._measure(diff or [], tests or {})
        return proposal

    def _measure(self, diff, tests):
        """The facts a route may ask about, worked out once, at proposal time."""
        self.ensure_one()
        codes = []
        for row in (diff or []):
            if isinstance(row, dict):
                codes.append((row.get('code') or '').upper())
        touches_tax = any(
            any(token in code for token in _TAX_TOKENS) for code in codes)
        if not touches_tax:
            touches_tax = self._candidate()._touches_tax_rules(codes)
        slips = 0
        try:
            run = self.env['hr.payslip.run'].sudo().search(
                [('slip_ids.formula_config_id', '=', self.config_id.id)],
                order='date_start desc, id desc', limit=1)
            if run:
                slips = len(run.slip_ids)
        except Exception:       # noqa: BLE001 — a fact must never raise
            slips = 0
        passed = bool((tests or {}).get('passed')) or (
            (tests or {}).get('failed') == 0 and (tests or {}).get('run'))
        self.sudo().write({
            'rules_changed': len(diff or []),
            'touches_tax': touches_tax,
            'payslips_per_month': slips,
            'tests_passed': bool(passed),
            'has_shadow_run': bool((tests or {}).get('shadow')),
        })
        return True

    def _candidate(self):
        """The content being put live: the branch for a merge, else the scheme."""
        self.ensure_one()
        return self.branch_id if (self.kind == 'merge' and self.branch_id) \
            else self.config_id

    def diff(self):
        self.ensure_one()
        try:
            rows = json.loads(self.diff_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    def tests(self):
        self.ensure_one()
        try:
            rows = json.loads(self.test_summary_json or '{}')
        except (TypeError, ValueError):
            return {}
        return rows if isinstance(rows, dict) else {}

    # ==================================================================
    # Adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state in ('pending', 'approved', 'applied'):
            raise UserError(_(
                "This proposal has already been sent in."))
        if self.kind == 'merge' and not self.branch_id:
            raise UserError(_(
                "A merge has to say which branch it is merging."))
        if self.kind == 'rollback' and not self.release_id:
            raise UserError(_(
                "A roll-back has to say which release it is undoing."))
        return True

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        config = self.config_id
        facts = {
            'rules_changed': {'value': self.rules_changed, 'unit': ''},
            'payslips_per_month': {'value': self.payslips_per_month,
                                   'unit': ''},
            'tests_passed': {'value': bool(self.tests_passed), 'unit': ''},
            'has_shadow_run': {'value': bool(self.has_shadow_run), 'unit': ''},
            'touches_tax': {'value': bool(self.touches_tax), 'unit': ''},
            'kind': {'value': self.kind or '', 'unit': ''},
        }
        # Who wrote the formulas this proposal carries. Read for the engine
        # (ledger AM40): choosing a route is not a permission question, and a
        # scheme owner sending a change in is not thereby being handed the
        # version history of everybody else's edits.
        makers = set(self._editor_uids())
        makers.add(self.env.uid)
        return {
            'company_id': company.id,
            'title': self.name or _('Scheme change'),
            'scope_keys': ['scheme:%s' % config.id, ''],
            'scope_label': config.name or company.name,
            'kind_key': self.kind or 'any',
            'facts': facts,
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': sorted(u for u in makers if u),
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._candidate().sudo()._content_hash(),
            'evidence': self._evidence_rows(),
        }

    def _editor_uids(self):
        """Everybody who changed a formula in the content being proposed."""
        self.ensure_one()
        Version = self.env.get('hr.formula.rule.version')
        if Version is None:
            return []
        candidate = self._candidate()
        rows = Version.sudo().search(
            [('config_id', '=', candidate.id)], order='id desc', limit=400)
        return list({row.user_id.id for row in rows if row.user_id})

    def _evidence_rows(self):
        """What is attached to this proposal, as the route may ask for it."""
        self.ensure_one()
        tests = self.tests()
        # The public review link never satisfies a seat — it is not a person
        # this app knows, and a signature from outside the company cannot BE an
        # approval step. It is evidence, which is exactly what it always was.
        signoff = self._client_signoff()
        return [
            {'key': 'test_results', 'name': _('Sample-test results'),
             'ok': bool(self.tests_passed),
             'note': str(tests.get('summary') or '')[:240]},
            {'key': 'shadow_run', 'name': _('Shadow run'),
             'ok': bool(self.has_shadow_run), 'note': ''},
            {'key': 'client_signoff', 'name': _('Client acknowledgement'),
             'ok': bool(signoff),
             'note': (_("Client acknowledged on the review link on %s",
                        fields.Date.to_string(signoff.signed_off_date))
                      if signoff else '')},
        ]

    def _client_signoff(self):
        """The client's sign-off on this scheme's latest shared release."""
        self.ensure_one()
        Share = self.env.get('hr.formula.review.share')
        if Share is None:
            return None
        found = Share.sudo().search([
            ('release_id.config_id', '=', self.config_id.id),
            ('signed_off', '=', True),
        ], order='signed_off_date desc, id desc', limit=1)
        return found or None

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'rules_changed': {'type': 'int',
                                  'label': _('Components changed')},
                'payslips_per_month': {'type': 'int',
                                       'label': _('Payslips a month')},
                'tests_passed': {'type': 'bool',
                                 'label': _('The checks passed')},
                'has_shadow_run': {'type': 'bool',
                                   'label': _('Was run beside the real one')},
                'touches_tax': {'type': 'bool',
                                'label': _('Touches tax or statutory pay')},
                'kind': {'type': 'selection', 'label': _('What is changing')},
            },
            'kinds': [{'key': key, 'label': _(label)}
                      for key, label in PROPOSAL_KINDS],
            'evidence': [
                {'key': 'test_results', 'label': _('Sample-test results')},
                {'key': 'shadow_run', 'label': _('Shadow run')},
                {'key': 'client_signoff',
                 'label': _('Client acknowledgement')},
            ],
            'scope_levels': [_('Pay scheme')],
            # A scheme is not about a person, so "their manager" has no answer.
            'manager_mode': False,
        }

    @api.model
    def _approval_scope_options(self, company):
        options = []
        Config = self.env['hr.formula.config']
        domain = [('company_id', '=', company.id)]
        if 'state' in Config._fields:
            domain.append(('state', '!=', 'archived'))
        for config in Config.sudo().search(domain, limit=200, order='name'):
            options.append({'key': 'scheme:%s' % config.id,
                            'label': config.name or ''})
        if not options:
            return []
        return [{'level': 'scheme', 'label': _('Pay scheme'),
                 'options': options}]

    @api.model
    def _approval_coverage_scopes(self, company):
        rows = []
        Config = self.env['hr.formula.config']
        for config in Config.sudo().search([('company_id', '=', company.id)],
                                           limit=200, order='name'):
            rows.append({
                'scope_key': 'scheme:%s' % config.id,
                'scope_keys': ['scheme:%s' % config.id, ''],
                'label': config.name or '',
                'headcount': 0,
                'kind_key': 'activate',
                'facts': {},
            })
        if not rows:
            rows.append({'scope_key': '', 'scope_keys': [''],
                         'label': company.name, 'headcount': 0,
                         'kind_key': 'activate', 'facts': {}})
        return rows

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.rules_changed == 1:
            return _("1 component")
        return _("%s components", self.rules_changed)

    def _approval_detail(self, request):
        """What changes, component by component."""
        self.ensure_one()
        rows = []
        for row in self.diff()[:40]:
            if not isinstance(row, dict):
                continue
            rows.append({
                'head': (row.get('code') or '')[:40],
                'sub': (row.get('name') or '')[:40],
                'cells': [str(row.get('old_formula')
                              or row.get('old_value') or '')[:40],
                          str(row.get('cur_formula') or row.get('new_formula')
                              or row.get('new_value') or '')[:40]],
                'tone': 'on',
            })
        if not rows:
            return None
        chips = []
        if self.touches_tax:
            chips.append({'label': _('Touches tax'), 'value': _('Yes')})
        if self.payslips_per_month:
            chips.append({'label': _('Payslips a month'),
                          'value': str(self.payslips_per_month)})
        return {
            'title': _('What changes'),
            'columns': [_('Now'), _('Proposed')],
            'rows': rows,
            'chips': chips,
            'note': self.note or '',
        }

    # ------------------------------------------------------- the transitions
    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending'})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned',
                           'note': (reason or '')[:512] or self.note})
        return True

    def _approval_apply(self, request):
        """Carry the change out — the only door into the five doors.

        The stamp is checked again here, and not only by the engine: the engine
        compares `source_revision`, which is the same number, but the sentence
        a person needs when it does not match is about their PAY SCHEME, not
        about a revision.
        """
        self.ensure_one()
        if self.state == 'applied':
            return True
        current = self._candidate().sudo()._content_hash()
        if self.sealed_hash and current != self.sealed_hash:
            raise UserError(_(
                "The scheme changed after this proposal was sent. Send it back "
                "and propose again."))
        # THE APPLYING USER IS THE FINAL APPROVER, and their own rights on the
        # scheme are checked here (safety rail 7): an approval is permission to
        # make THIS change, never a way to act on a scheme somebody may not
        # touch.
        self.config_id.check_access('write')
        result = apply_context(self)._perform()
        self.sudo().write({
            'state': 'applied',
            'applied_at': fields.Datetime.now(),
            'applied_release_id': (result or {}).get('release_id') or False,
            'apply_note': ((result or {}).get('msg') or '')[:512] or False,
        })
        return True

    def _perform(self):
        """Do the thing, with the sentinel in the context. One place."""
        self.ensure_one()
        config, branch = self.config_id, self.branch_id
        Studio = self.env.get('pb.formula.studio')
        if self.kind == 'activate':
            config.action_activate()
            return {}
        if self.kind == 'archive':
            config.action_archive()
            return {}
        if Studio is None:
            raise UserError(_(
                "This change needs the scheme builder, which is not installed "
                "on this server."))
        studio = Studio.with_context(self.env.context)
        if self.kind == 'merge':
            result = studio.branch_merge(branch.id, self.note or '')
            if not (result or {}).get('ok'):
                raise UserError((result or {}).get('msg') or _(
                    "The branch could not be merged."))
            return {'release_id': result.get('release_id'),
                    'msg': _("%s component(s) merged.",
                             result.get('merged') or 0)}
        if self.kind == 'release':
            result = studio.release_approve(config.id, self.note or '')
            if not (result or {}).get('ok'):
                raise UserError((result or {}).get('msg') or _(
                    "The release could not be sealed."))
            return {'release_id': result.get('release_id'),
                    'msg': _("%s change(s) released.",
                             result.get('change_count') or 0)}
        if self.kind == 'rollback':
            result = studio.rollback_apply(self.release_id.id)
            if not (result or {}).get('ok'):
                raise UserError((result or {}).get('msg') or _(
                    "The release could not be rolled back."))
            return {'release_id': result.get('release_id'),
                    'msg': _("%s component(s) restored.",
                             result.get('restored') or 0)}
        raise UserError(_("That is not a change this can carry out."))

    # ==================================================================
    # doors
    # ==================================================================
    def action_submit(self):
        self.ensure_one()
        return self.env['biz.approval.engine'].submit(self)

    def action_open_request(self):
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            raise UserError(_("This proposal has not been sent in yet."))
        return {
            'type': 'ir.actions.client',
            'tag': 'pb_approval_inbox',
            'name': _('Approvals'),
            'params': {'request_id': request.id},
        }
