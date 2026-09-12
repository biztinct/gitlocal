# -*- coding: utf-8 -*-
"""`pb.approval.matrix` — the only server surface the configuration screens use.

An `AbstractModel` facade in the shape `pb.group.room` and `pb.decision.room`
established: `@api.model` reads, a SERVER-SIDE gate that is the boundary, a cap
on every list a caller controls, and `_safe()` around any figure that may fail
on its own so one broken number never takes a screen down.

WHAT IT IS NOT. It holds no authority of its own. Every rule about who may
publish, whether a route resolves, whether a seat is ambiguous and whether a
warning has been confirmed lives in `biz.approval.engine`, and this file calls
it. The facade's whole job is to SHAPE: to turn the engine's records into the
rows a screen draws, in words a person reads, and to turn a screen's answer
back into the engine's own call.

SCOPE KEYS. The engine never parses a scope key (ledger AM2); this module mints
them. A key is the chosen narrowings joined most-specific-first in one canonical
order — ``scheme:<id>|division:<id>`` — with the empty string meaning the whole
company. The division level is added here for EVERY process, because a division
is a Payobook idea that no single business object owns; anything narrower comes
from the business object's own `_approval_scope_options`.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.biz_approval_workflow.models import definition as D

_logger = logging.getLogger(__name__)

CONFIG_GROUP = 'biz_approval_workflow.group_approval_config'
PUBLISH_GROUP = 'biz_approval_workflow.group_approval_publish'
ADMIN_GROUP = 'biz_approval_workflow.group_approval_admin'

#: Caps on anything a caller controls — this facade is reachable over JSON-RPC.
MAX_ROWS = 400
MAX_PEOPLE = 60
MAX_HISTORY = 60
MAX_TEXT = 240

#: The order the levels of a scope key are joined in. Most specific first, so
#: a narrower binding sorts before a wider one and the engine's rank walk means
#: what it looks like it means.
SCOPE_ORDER = ['scheme', 'division']


def _clip(text, size=MAX_TEXT):
    return (text or '')[:size]


def _preset_rows():
    """The routes somebody can start from instead of a blank page.

    Held in Python rather than as data records because a preset is a piece of
    COPY plus a definition document: it needs `_t()`, and there is no useful
    thing to do with it in the database between one press and the draft it
    creates.
    """
    def role(key, role_key, title, kind='approve', scope='company'):
        return {'key': key, 'kind': kind, 'title': title,
                'who': {'mode': 'role', 'role': role_key, 'scope': scope},
                'min_amount': 0, 'condition': None}

    def manager(key, title):
        return {'key': key, 'kind': 'review', 'title': title,
                'who': {'mode': 'manager'}, 'min_amount': 0, 'condition': None}

    def wrap(steps, tiers=None):
        return {'schema_version': D.SCHEMA_VERSION, 'steps': steps,
                'tiers': tiers or {'enabled': False, 'fact': None},
                'safeguards': D.default_safeguards()}

    return [
        {'key': 'officer',
         'title': _('Officer, then HR, then Finance'),
         'sub': _('The classic payroll chain. One person at each step.'),
         'route': [_('Payroll manager'), _('HR lead'), _('Finance approver')],
         'definition': wrap([
             role('s1', 'payroll_mgr', _('Payroll check'), kind='review'),
             role('s2', 'hr_lead', _('HR lead review'), kind='review',
                  scope='area'),
             role('s3', 'finance', _('Finance approval')),
         ])},
        {'key': 'mgr_hr',
         'title': _('Manager, then HR'),
         'sub': _('For requests about one person: their manager first, then '
                  'HR.'),
         'route': [_('Their manager'), _('HR lead')],
         'definition': wrap([
             manager('s1', _('Manager review')),
             role('s2', 'hr_lead', _('HR approval'), scope='area'),
         ])},
        # A JOINT STEP NEEDS TWO PEOPLE TO BE A JOINT STEP AT ALL, and a
        # preset cannot know who they are. Naming a responsibility held by a
        # GROUP is the only shape that is complete the moment it is created:
        # the reader chooses the signatories once, in People & backups, and
        # every route that needs them follows. A preset that started with an
        # empty list would open the builder already showing errors.
        {'key': 'joint',
         'title': _('Joint sign-off'),
         'sub': _('Everybody on the bank mandate has to approve. For bank '
                  'files and money leaving the company.'),
         'route': [_('Everybody on the bank mandate')],
         'definition': wrap([{
             'key': 's1', 'kind': 'joint', 'title': _('Joint sign-off'),
             'who': {'mode': 'role', 'role': 'signatory', 'scope': 'company'},
             'min_amount': 0, 'condition': None,
         }])},
        {'key': 'tiers',
         'title': _('Route by amount'),
         'sub': _('Small amounts stay light; big amounts bring in more '
                  'people.'),
         'route': [_('HR lead'), _('Finance approver, above an amount'),
                   _('Country director, above a bigger one')],
         'definition': wrap([
             role('s1', 'hr_lead', _('HR lead review'), kind='review',
                  scope='area'),
             dict(role('s2', 'finance', _('Finance approval')),
                  min_amount=300000000),
             dict(role('s3', 'director', _('Director sign-off')),
                  min_amount=600000000),
         ], tiers={'enabled': True, 'fact': 'amount'})},
        {'key': 'four',
         'title': _('Four eyes on a setup change'),
         'sub': _('The person who made a change never approves it.'),
         'route': [_('Payroll manager'), _('Scheme owner')],
         'definition': wrap([
             role('s1', 'payroll_mgr', _('Independent review'), kind='review'),
             role('s2', 'scheme_owner', _('Owner approval')),
         ])},
        {'key': 'blank',
         'title': _('Start blank'),
         'sub': _('Build the route step by step.'),
         'route': [],
         'definition': wrap([])},
    ]


class PbApprovalMatrix(models.AbstractModel):
    _name = 'pb.approval.matrix'
    _description = 'Approval Matrix screen data'

    # ================================================================= gates
    @api.model
    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            _logger.debug('Approval Matrix figure failed: %s', exc)
            return default

    @api.model
    def _is_admin(self):
        user = self.env.user
        return (self.env.su or user._is_admin()
                or self._safe(lambda: user.has_group(ADMIN_GROUP),
                              default=False))

    @api.model
    def _can_config(self):
        return (self._is_admin()
                or self._safe(lambda: self.env.user.has_group(CONFIG_GROUP),
                              default=False))

    @api.model
    def _can_publish(self):
        return (self._is_admin()
                or self._safe(lambda: self.env.user.has_group(PUBLISH_GROUP),
                              default=False))

    @api.model
    def _require_config(self):
        if not self._can_config():
            raise AccessError(_(
                "You can take part in approvals, but setting them up is "
                "somebody else's job. Ask whoever looks after approvals."))
        return True

    # ---------------------------------------------------------- the company
    @api.model
    def _company(self, company_id=None):
        """The company a screen is about.

        `self.env.user.company_id` and never `self.env.company`: the second one
        follows whatever is ticked in the top bar, which is not a decision
        anybody made about this screen.
        """
        if company_id:
            company = self.env['res.company'].browse(int(company_id)).exists()
            if not company:
                raise UserError(_("That company no longer exists."))
            if not self.env.su \
                    and company.id not in self.env.user.company_ids.ids:
                raise AccessError(_("You cannot see that company."))
            return company
        return self.env.user.company_id

    @api.model
    def _engine(self):
        return self.env['biz.approval.engine']

    # ============================================================= the grid
    @api.model
    def get_matrix(self, company_id=None):
        """Every process, its route in words, and whether it is in use."""
        self._require_config()
        company = self._company(company_id)
        Process = self.env['biz.approval.process'].sudo()
        Binding = self.env['biz.approval.binding'].sudo()
        processes = Process.search([], limit=MAX_ROWS)
        bindings = Binding.search([('company_id', '=', company.id),
                                   ('active', '=', True)])
        by_process = {}
        for binding in bindings:
            by_process.setdefault(binding.process_id.id, []).append(binding)

        labels = Process._area_labels()
        areas, index = [], {}
        for key, label in labels.items():
            entry = {'key': key, 'name': label,
                     'icon': Process.AREA_ICONS.get(key, 'inbox'), 'rows': []}
            areas.append(entry)
            index[key] = entry

        attention = []
        for process in processes:
            row = self._matrix_row(company, process,
                                   by_process.get(process.id) or [])
            index.setdefault(process.area or 'other', areas[-1])['rows'].append(
                row)
            if row['status'] == 'needs':
                attention.append(row)

        return {
            'company_id': company.id,
            'company_name': company.name,
            'can_publish': self._can_publish(),
            'areas': [a for a in areas if a['rows']],
            'attention': {'count': len(attention),
                          'rows': [r['process_key'] for r in attention]},
            'presets': [{'key': p['key'], 'title': p['title'],
                         'sub': p['sub'], 'route': p['route']}
                        for p in _preset_rows()],
        }

    def _matrix_row(self, company, process, bindings):
        """One row: what it is, who decides it, where, and how ready it is."""
        default = next((b for b in bindings if not (b.scope_key or '')), None)
        narrower = [b for b in bindings if (b.scope_key or '')]
        binding = default or (narrower[0] if narrower else None)
        workflow = binding.workflow_id if binding else \
            self.env['biz.approval.workflow'].sudo().search(
                [('company_id', '=', company.id),
                 ('process_id', '=', process.id)], limit=1)
        published = workflow.published_version_id if workflow else None
        draft = workflow.draft_version_id if workflow else None
        version = published or draft

        if not process.connected:
            status = 'soon'
        elif published:
            status = 'needs' if self._gap_count(published) else 'live'
        elif workflow:
            status = 'draft'
        else:
            status = 'draft'

        route = list((version.route_labels or []) if version else [])
        if version and not route:
            route = [_('Nothing is checked')]

        if binding and binding.scope_key:
            applies = binding.scope_label or _('one part of the business')
        elif binding:
            applies = _('%s — everywhere', company.name)
        else:
            applies = _('Not set up yet')
        sub = ''
        if narrower:
            sub = _('%s exception', len(narrower)) if len(narrower) == 1 \
                else _('%s exceptions', len(narrower))
        if binding and binding.mode == 'paused':
            sub = _('Paused — nothing new is accepted')

        return {
            'process_key': process.key,
            'name': process.name,
            'area': process.area or 'other',
            'icon': process._area_icon(),
            'status': status,
            'route_labels': route,
            'applies': applies,
            'sub': sub,
            'version': (_('v%s', version.revision) if published
                        else (_('Draft') if version else '')),
            'fast': bool(version and any(
                s['kind'] == 'fast' for s in D.normalise(
                    version.definition)['steps'])),
            'money': bool(process.money),
            'connected': bool(process.connected),
            'workflow_id': workflow.id if workflow else 0,
            'needs_people': self._gap_count(published) if published else 0,
        }

    def _gap_count(self, version):
        """How many places this published route cannot find a person for."""
        if not version:
            return 0
        scan = self._safe(
            lambda: self._engine().coverage_scan(version.id),
            default={'ran': False, 'rows': []})
        if not (scan or {}).get('ran'):
            return 0
        return sum(1 for row in scan['rows'] if row['issues'])

    # ======================================================= one workflow
    @api.model
    def create_workflow(self, preset_key, process_key, company_id=None,
                        name=None):
        """Start a draft from a preset. Nothing is published by doing this."""
        self._require_config()
        company = self._company(company_id)
        process = self.env['biz.approval.process']._by_key(process_key)
        if not process:
            raise UserError(_("That kind of request is not in the list."))
        preset = next((p for p in _preset_rows() if p['key'] == preset_key),
                      None)
        if not preset:
            raise UserError(_("That starting point is no longer offered."))
        workflow = self.env['biz.approval.workflow'].create({
            'name': _clip(name) or '%s — %s' % (process.name, preset['title']),
            'company_id': company.id,
            'process_id': process.id,
            'owner_user_id': self.env.uid,
        })
        version = self.env['biz.approval.workflow.version'].create({
            'workflow_id': workflow.id,
            'revision': 1,
            'status': 'draft',
            'definition': preset['definition'],
        })
        self.env['biz.approval.event']._log(
            'binding_changed',
            _("%(who)s started \"%(name)s\" as a draft",
              who=self.env.user.name, name=workflow.name),
            company=company, workflow=workflow)
        return {'workflow_id': workflow.id, 'version_id': version.id}

    @api.model
    def get_workflow(self, workflow_id):
        """Everything the builder needs for one route, in one round trip."""
        self._require_config()
        workflow = self.env['biz.approval.workflow'].browse(int(workflow_id))
        workflow.check_access('read')
        if not workflow.exists():
            raise UserError(_("That workflow no longer exists."))
        draft = workflow.draft_version_id
        if not draft:
            draft = workflow.action_new_draft()
        published = workflow.published_version_id
        process = workflow.process_id
        return {
            'workflow': {
                'id': workflow.id,
                'name': workflow.name,
                'process_key': process.key,
                'process_name': process.name,
                'connected': bool(process.connected),
                'money': bool(process.money),
                'company_id': workflow.company_id.id,
                'company_name': workflow.company_id.name,
                'owner': workflow.owner_user_id.name or '',
            },
            'draft': {
                'version_id': draft.id,
                'draft_revision': draft.draft_revision,
                'revision': draft.revision,
                'definition': D.normalise(draft.definition),
                'summary': draft.summary or '',
            },
            'published': {
                'version_id': published.id,
                'revision': published.revision,
                'definition': D.normalise(published.definition),
                'summary': published.summary or '',
                'route_labels': published.route_labels or [],
            } if published else None,
            'capabilities': self._capabilities(process),
            'scope_options': self._approval_scope_options(process,
                                                          workflow.company_id),
            'bindings': self._binding_rows(workflow),
            'roles': self._role_rows(),
            'can_publish': self._can_publish(),
            'example_defaults': self._example_defaults(workflow),
        }

    def _capabilities(self, process):
        """What a designer may ask about this kind of request.

        An unconnected process has no business object to ask, so it gets the
        generic set: an amount, who prepared it, and nothing invented.
        """
        model = process.model_name
        if model and model in self.env \
                and getattr(self.env[model], '_approval_process_key', None):
            found = self._safe(
                lambda: self.env[model]._approval_capabilities(), default=None)
            if found:
                return found
        return {
            'facts': {
                'amount': {'type': 'decimal', 'label': _('Amount'),
                           'unit': 'currency'},
            },
            'kinds': [{'key': 'any', 'label': _('Any kind')}],
            'evidence': [],
            'scope_levels': [_('Whole company')],
            'manager_mode': True,
            'generic': True,
        }

    @api.model
    def _approval_scope_options(self, process, company):
        """Where a route for this process may be narrowed to.

        The division level is added for EVERY process, because a division is a
        Payobook idea that no single business object owns. Anything narrower
        (a pay scheme, a kind of run) comes from the object itself, so a module
        that has not signed the adapter contract cannot offer a narrowing it
        could never resolve.
        """
        levels = []
        model = process.model_name if process else None
        if model and model in self.env \
                and getattr(self.env[model], '_approval_process_key', None):
            found = self._safe(
                lambda: self.env[model]._approval_scope_options(company),
                default=[]) or []
            levels += [lvl for lvl in found if isinstance(lvl, dict)]

        if 'pb.division' in self.env:
            divisions = self._safe(
                lambda: self.env['pb.division'].sudo().search(
                    [], limit=MAX_ROWS), default=None)
            options = []
            for division in (divisions or []):
                companies = self._safe(lambda d=division: d.company_ids,
                                       default=None)
                if companies and company not in companies:
                    continue
                options.append({'key': 'division:%s' % division.id,
                                'label': division.name})
            if options:
                levels.append({'level': 'division', 'label': _('Division'),
                               'options': options})

        order = {name: n for n, name in enumerate(SCOPE_ORDER)}
        levels.sort(key=lambda lvl: order.get(lvl.get('level'), 99))
        return levels

    @api.model
    def scope_key_for(self, parts):
        """Join chosen narrowings into the one key a binding carries."""
        chosen = {}
        for part in (parts or []):
            if not part or ':' not in part:
                continue
            chosen[part.split(':', 1)[0]] = part
        ordered = [chosen[name] for name in SCOPE_ORDER if name in chosen]
        ordered += [v for k, v in sorted(chosen.items())
                    if k not in SCOPE_ORDER]
        return '|'.join(ordered)

    def _binding_rows(self, workflow):
        rows = []
        bindings = self.env['biz.approval.binding'].sudo().search([
            ('workflow_id', '=', workflow.id), ('active', '=', True)])
        for binding in bindings:
            rows.append({
                'id': binding.id,
                'scope_key': binding.scope_key or '',
                'label': binding.scope_label
                or (workflow.company_id.name if not binding.scope_key
                    else binding.scope_key),
                'kind_key': binding.kind_key or 'any',
                'mode': binding.mode,
                'paused': binding.mode == 'paused',
            })
        return rows

    def _role_rows(self):
        rows = []
        for role in self.env['biz.approval.role'].sudo().search([]):
            rows.append({
                'key': role.key, 'name': role.name,
                'description': role.description or '',
                'fallback': bool(role.fallback_to_company),
                'pool': bool(role.is_pool),
            })
        return rows

    def _example_defaults(self, workflow):
        """Facts to start "Try an example" with, so it says something at once."""
        return {
            'company_id': workflow.company_id.id,
            'currency_id': workflow.company_id.currency_id.id,
            'currency_name': workflow.company_id.currency_id.name or '',
            'submitter_uid': self.env.uid,
            'scope_keys': [''],
            'scope_label': workflow.company_id.name,
            'amount': 0.0,
            'facts': {},
        }

    # ------------------------------------------------------------- editing
    @api.model
    def save_draft(self, version_id, expected_draft_revision, definition,
                   meta=None):
        """Write a draft. Saving a draft never publishes anything."""
        self._require_config()
        version = self.env['biz.approval.workflow.version'].browse(
            int(version_id))
        version.check_access('write')
        if not version.exists():
            raise UserError(_("That draft no longer exists."))
        if version.status != 'draft':
            raise UserError(_(
                "That version is in use and cannot be changed. Start a new "
                "draft instead."))
        if expected_draft_revision is not None \
                and int(expected_draft_revision) != version.draft_revision:
            raise UserError(_(
                "This workflow changed while you were editing. Reload to see "
                "the latest."))
        if not isinstance(definition, dict):
            raise UserError(_("That workflow could not be read."))

        checks = D.validate(definition,
                            self._capabilities(version.workflow_id.process_id),
                            env=self.env)
        version.write({'definition': D.normalise(definition)})
        name = (meta or {}).get('name')
        if name and _clip(name) != version.workflow_id.name:
            version.workflow_id.write({'name': _clip(name)})
        version.invalidate_recordset(['summary', 'route_labels',
                                      'draft_revision'])
        return {
            'draft_revision': version.draft_revision,
            'summary': version.summary or '',
            'route_labels': version.route_labels or [],
            'errors': checks['errors'],
            'warnings': checks['warnings'],
        }

    @api.model
    def preview(self, version_id, example=None):
        """Run the route against made-up facts. Writes nothing, sends nothing."""
        self._require_config()
        version = self.env['biz.approval.workflow.version'].browse(
            int(version_id))
        version.check_access('read')
        ctx = dict(example or {})
        workflow = version.workflow_id
        ctx.setdefault('company_id', workflow.company_id.id)
        ctx.setdefault('currency_id', workflow.company_id.currency_id.id)
        ctx.setdefault('process_key', workflow.process_id.key)
        ctx.setdefault('submitter_uid', self.env.uid)
        capabilities = self._capabilities(workflow.process_id)
        ctx.setdefault('fact_labels', {
            key: (spec or {}).get('label') or key
            for key, spec in (capabilities.get('facts') or {}).items()})
        result = self._engine().preview(version.id, ctx)
        result['summary'] = version.summary or result.get('summary') or ''
        return result

    @api.model
    def check_coverage(self, version_id):
        """Every place this route would apply, and what is missing in each."""
        self._require_config()
        version = self.env['biz.approval.workflow.version'].browse(
            int(version_id))
        version.check_access('read')
        scan = self._engine().coverage_scan(version.id)
        rows = []
        for row in scan.get('rows') or []:
            issues = []
            for issue in row['issues']:
                issues.append({
                    'step': issue.get('step') or '',
                    'msg': issue.get('msg') or '',
                    'fix': self._fix_for(version, row, issue),
                })
            rows.append({
                'scope_key': row.get('scope_key') or '',
                'label': row.get('label') or '',
                'headcount': row.get('headcount') or 0,
                'issues': issues,
            })
        return {'ran': bool(scan.get('ran')), 'rows': rows,
                'gaps': sum(1 for r in rows if r['issues'])}

    def _fix_for(self, version, row, issue):
        """The one button that actually mends this gap."""
        for step in D.decision_steps(version.definition):
            who = step.get('who') or {}
            if who.get('mode') != 'role':
                continue
            if (issue.get('step') or '') not in ('', step.get('title')):
                continue
            return {'kind': 'assign', 'role_key': who.get('role') or '',
                    'scope_key': row.get('scope_key') or ''}
        return {'kind': 'people'}

    # ------------------------------------------------------------ publish
    @api.model
    def publication_preview(self, version_id):
        """What changes, who is affected, and everything to confirm first."""
        self._require_config()
        version = self.env['biz.approval.workflow.version'].browse(
            int(version_id))
        version.check_access('read')
        workflow = version.workflow_id
        published = workflow.published_version_id
        checks = self._engine().validate_for_publish(version.id)

        diff = self._diff(published.definition if published else None,
                          version.definition)
        affected = []
        for binding in self.env['biz.approval.binding'].sudo().search([
                ('workflow_id', '=', workflow.id), ('active', '=', True)]):
            affected.append({
                'label': binding.scope_label or workflow.company_id.name,
                'follows': binding.mode == 'follow',
                'note': {'follow': _('Follows this route'),
                         'pin': _('Stays on the version it was given'),
                         'paused': _('Paused')}.get(binding.mode, ''),
            })
        in_progress = self.env['biz.approval.request'].sudo().search_count([
            ('workflow_id', '=', workflow.id),
            ('state', 'in', ('pending', 'blocked')),
        ])
        return {
            'diff': diff,
            'affected': affected,
            'in_progress': in_progress,
            'errors': checks['errors'],
            'warnings': checks['warnings'],
            'can_publish': self._can_publish(),
            'previous_revision': published.revision if published else 0,
            'revision': version.revision,
        }

    def _diff(self, before, after):
        """Two definitions, compared in whole sentences rather than in keys."""
        engine = self._engine()
        roles, names = engine._naming(after or {})
        old = {s['title']: s for s in D.decision_steps(before or {})}
        new = {s['title']: s for s in D.decision_steps(after or {})}
        rows = []
        for title, step in new.items():
            who = D.who_label(step.get('who'), roles, names)
            if title not in old:
                rows.append({
                    'kind': 'added', 'title': title,
                    'text': (_('Nobody checks this; it is applied at once '
                               'and recorded.') if step['kind'] == 'fast'
                             else _('Decided by %s.', who)),
                })
            elif old[title].get('min_amount') != step.get('min_amount'):
                amount = step.get('min_amount') or 0
                rows.append({
                    'kind': 'changed', 'title': title,
                    'text': (_('Now only from %s and above.',
                               '{:,.0f}'.format(float(amount))) if amount
                             else _('Now applies whatever the amount.')),
                })
            elif D.who_label(old[title].get('who'), roles, names) != who:
                rows.append({'kind': 'changed', 'title': title,
                             'text': _('Now decided by %s.', who)})
        for title in old:
            if title not in new:
                rows.append({'kind': 'removed', 'title': title,
                             'text': _('This check no longer happens.')})
        return rows

    @api.model
    def publish(self, version_id, expected_draft_revision=None,
                effective_from=None, reason=None, confirmations=None):
        """Make this draft the one future requests follow."""
        self._require_config()
        result = self._engine().publish(
            int(version_id), expected_draft_revision, effective_from,
            _clip(reason), confirmations or [])
        version = self.env['biz.approval.workflow.version'].browse(
            int(version_id))
        result['workflow_id'] = version.workflow_id.id
        result['name'] = version.workflow_id.name
        result['in_progress'] = self.env['biz.approval.request'].sudo(
        ).search_count([('workflow_id', '=', version.workflow_id.id),
                        ('state', 'in', ('pending', 'blocked'))])
        return result

    # ========================================================== the people
    @api.model
    def get_people(self, company_id=None):
        """Who fills each responsibility, where, with the gaps called out."""
        self._require_config()
        company = self._company(company_id)
        roles = self.env['biz.approval.role'].sudo().search([])
        scopes = [{'key': '', 'label': company.name}]
        for level in self._approval_scope_options(
                self.env['biz.approval.process'], company):
            if level.get('level') != 'division':
                continue
            scopes += [{'key': o['key'], 'label': o['label']}
                       for o in level.get('options') or []]

        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', company.id), ('active', '=', True)])
        by_seat = {}
        for row in held:
            by_seat['%s|%s' % (row.role_key, row.scope_key or '')] = row

        rows, gaps = [], []
        for role in roles:
            cells = []
            for scope in scopes:
                seat = by_seat.get('%s|%s' % (role.key, scope['key']))
                cell = {'scope_key': scope['key'], 'label': scope['label']}
                if seat:
                    cell.update(self._seat_payload(seat, company))
                elif not scope['key']:
                    cell['state'] = 'empty'
                    cell['text'] = _('Nobody for the whole company yet')
                elif role.fallback_to_company:
                    company_seat = by_seat.get('%s|' % role.key)
                    cell['state'] = 'inherited'
                    cell['text'] = (
                        _('Covered by %s', company_seat.user_id.name)
                        if company_seat and company_seat.user_id
                        else _('Nobody'))
                else:
                    cell['state'] = 'gap'
                    cell['text'] = _('Needs a person')
                    gaps.append({'role_key': role.key, 'role': role.name,
                                 'scope_key': scope['key'],
                                 'scope': scope['label']})
                cells.append(cell)
            rows.append({
                'key': role.key, 'name': role.name,
                'description': role.description or '',
                'rule': (_('the company-wide person covers a part of the '
                           'business that has nobody')
                         if role.fallback_to_company
                         else _('each part of the business needs its own '
                                'person')),
                'pool': bool(role.is_pool),
                'cells': cells,
            })

        return {
            'company_id': company.id,
            'company_name': company.name,
            'scopes': scopes,
            'roles': rows,
            'gaps': gaps,
            'delegations': self.list_delegations(company.id),
            'can_config': True,
        }

    def _seat_payload(self, seat, company):
        cover = self._safe(
            lambda: self.env['biz.approval.delegation'].covering(
                seat.user_id, company), default=None)
        return {
            'state': 'pool' if seat.role_id.is_pool else 'held',
            'id': seat.id,
            'user_id': seat.user_id.id,
            'name': seat.user_id.name or '',
            'pool_names': seat.pool_user_ids.mapped('name'),
            'backup_id': seat.backup_user_id.id,
            'backup': seat.backup_user_id.name or '',
            'since': fields.Date.to_string(seat.date_from) or '',
            'cover': cover.name if cover else '',
            'note': seat.note or '',
        }

    @api.model
    def set_responsibility(self, company_id, role_key, scope_key, user_id,
                           backup_user_id=None, date_from=None, note=None,
                           pool_user_ids=None):
        """Name the person who holds one responsibility, in one place."""
        self._require_config()
        company = self._company(company_id)
        role = self.env['biz.approval.role'].sudo().search(
            [('key', '=', role_key)], limit=1)
        if not role:
            raise UserError(_("That responsibility is no longer in the list."))
        user = self.env['res.users'].sudo().browse(int(user_id or 0)).exists()
        if not role.is_pool and (not user or user.share or not user.active):
            raise UserError(_("That person cannot hold a responsibility."))
        if user and company.id not in user.company_ids.ids:
            raise UserError(_("%s does not work in this company.", user.name))

        Responsibility = self.env['biz.approval.responsibility']
        scope_key = scope_key or ''
        existing = Responsibility.sudo().search([
            ('company_id', '=', company.id), ('role_id', '=', role.id),
            ('scope_key', '=', scope_key), ('active', '=', True)], limit=1)
        label = self._scope_label(company, scope_key)
        values = {
            'user_id': user.id if user else False,
            'backup_user_id': int(backup_user_id) if backup_user_id else False,
            'scope_label': label,
            'note': _clip(note),
        }
        if date_from:
            values['date_from'] = fields.Date.to_date(date_from)
        if role.is_pool:
            values['pool_user_ids'] = [(6, 0, [int(u) for u in
                                               (pool_user_ids or []) if u])]
        if existing:
            existing.write(values)
            seat = existing
        else:
            seat = Responsibility.create(dict(
                values, company_id=company.id, role_id=role.id,
                scope_key=scope_key))
        self.env['biz.approval.event']._log(
            'responsibility_changed',
            _("%(who)s made %(name)s the %(role)s for %(where)s",
              who=self.env.user.name,
              name=(user.name if user else _('a group of people')),
              role=role.name, where=label),
            company=company,
            payload={'role_key': role.key, 'scope_key': scope_key})
        return {'id': seat.id}

    @api.model
    def clear_responsibility(self, company_id, role_key, scope_key):
        """Leave a seat empty again. Requests from there will say so."""
        self._require_config()
        company = self._company(company_id)
        role = self.env['biz.approval.role'].sudo().search(
            [('key', '=', role_key)], limit=1)
        if not role:
            raise UserError(_("That responsibility is no longer in the list."))
        rows = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', company.id), ('role_id', '=', role.id),
            ('scope_key', '=', scope_key or ''), ('active', '=', True)])
        if rows:
            rows.write({'active': False})
            self.env['biz.approval.event']._log(
                'responsibility_changed',
                _("%(who)s left \"%(role)s\" for %(where)s with nobody in it",
                  who=self.env.user.name, role=role.name,
                  where=self._scope_label(company, scope_key)),
                company=company,
                payload={'role_key': role.key, 'scope_key': scope_key or ''})
        return {'cleared': len(rows)}

    def _scope_label(self, company, scope_key):
        if not scope_key:
            return company.name
        for level in self._approval_scope_options(
                self.env['biz.approval.process'], company):
            for option in level.get('options') or []:
                if option['key'] == scope_key:
                    return option['label']
        return scope_key

    @api.model
    def user_options(self, term=None, role_key=None, company_id=None,
                     process_key=None):
        """People who could hold a responsibility, and whether they may act.

        "Needs permission" is a real answer, not a guess: it is whether that
        person can READ the thing they would be asked to decide. Naming them
        anyway is allowed — the picker says what will still be missing.
        """
        self._require_config()
        company = self._company(company_id)
        domain = [('active', '=', True), ('share', '=', False),
                  ('company_ids', 'in', company.id)]
        term = (term or '').strip()
        if term:
            domain += ['|', ('name', 'ilike', term), ('login', 'ilike', term)]
        users = self.env['res.users'].sudo().search(
            domain, limit=MAX_PEOPLE, order='name')
        model = None
        if process_key:
            process = self.env['biz.approval.process']._by_key(process_key)
            model = process.model_name if process else None
        rows = []
        for user in users:
            allowed = True
            if model and model in self.env:
                allowed = bool(self._safe(
                    lambda m=model, u=user: self.env['ir.model.access']
                    .with_user(u).check(m, 'read', raise_exception=False),
                    default=True))
            rows.append({
                'id': user.id,
                'name': user.name,
                'title': user.job_title or user.login,
                'avatar': '/web/image/res.users/%s/avatar_128' % user.id,
                'eligible': allowed,
                'needs_permission': '' if allowed else _(
                    "Can be named, but cannot open this kind of request yet. "
                    "Give them the access first."),
            })
        return rows

    # ------------------------------------------------------- the hand-overs
    @api.model
    def list_delegations(self, company_id=None):
        self._require_config()
        company = self._company(company_id)
        rows = []
        for row in self.env['biz.approval.delegation'].sudo().search(
                [('company_id', '=', company.id)], limit=MAX_ROWS):
            rows.append({
                'id': row.id,
                'principal': row.principal_user_id.name or '',
                'principal_id': row.principal_user_id.id,
                'delegate': row.delegate_user_id.name or '',
                'delegate_id': row.delegate_user_id.id,
                'roles': row.role_ids.mapped('name'),
                'date_from': fields.Date.to_string(row.date_from) or '',
                'date_to': fields.Date.to_string(row.date_to) or '',
                'reason': row.reason or '',
                'state': row.state,
                'live': row.state == 'active'
                and bool(row.date_from) and bool(row.date_to)
                and row.date_from <= fields.Date.context_today(self)
                <= row.date_to,
            })
        return rows

    @api.model
    def set_delegation(self, vals):
        """Arrange cover. Your own is yours; anybody else's is an admin's."""
        self._require_config()
        vals = vals or {}
        company = self._company(vals.get('company_id'))
        principal = int(vals.get('principal_user_id') or self.env.uid)
        if principal != self.env.uid and not self._is_admin():
            raise AccessError(_(
                "You can arrange cover for yourself. Arranging it for "
                "somebody else is for whoever looks after approvals."))
        delegate = int(vals.get('delegate_user_id') or 0)
        if not delegate:
            raise UserError(_("Say who is covering."))
        if not (vals.get('reason') or '').strip():
            raise UserError(_("Say why, so the trail makes sense later."))
        row = self.env['biz.approval.delegation'].create({
            'company_id': company.id,
            'principal_user_id': principal,
            'delegate_user_id': delegate,
            'role_ids': [(6, 0, [int(r) for r in (vals.get('role_ids') or [])
                                 if r])],
            'date_from': fields.Date.to_date(vals.get('date_from'))
            or fields.Date.context_today(self),
            'date_to': fields.Date.to_date(vals.get('date_to')),
            'reason': _clip(vals.get('reason')),
        })
        self.env['biz.approval.event']._log(
            'delegation_changed',
            _("%(a)s is covering for %(b)s",
              a=row.delegate_user_id.name, b=row.principal_user_id.name),
            company=company, payload={'delegation_id': row.id})
        return {'id': row.id}

    @api.model
    def end_delegation(self, delegation_id, note=None):
        self._require_config()
        row = self.env['biz.approval.delegation'].browse(
            int(delegation_id)).exists()
        if not row:
            raise UserError(_("That hand-over no longer exists."))
        if row.principal_user_id.id != self.env.uid and not self._is_admin():
            raise AccessError(_(
                "Only the person being covered, or whoever looks after "
                "approvals, can stop this."))
        row.action_revoke()
        return {'id': row.id, 'state': row.state}

    # ========================================================== the trail
    @api.model
    def get_history(self, company_id=None, kind=None, cursor=None):
        """What changed and who did it, in plain words."""
        self._require_config()
        company = self._company(company_id)
        domain = ['|', ('company_id', '=', False),
                  ('company_id', '=', company.id)]
        families = {
            'publishes': ['published'],
            'decisions': ['decided', 'submitted', 'returned', 'rejected',
                          'applied', 'cancelled'],
            'exceptions': ['exception_used', 'grant_changed'],
            'handovers': ['delegation_changed', 'responsibility_changed',
                          'reassigned'],
        }
        if kind and kind in families:
            domain.append(('kind', 'in', families[kind]))
        if cursor:
            domain.append(('id', '<', int(cursor)))
        events = self.env['biz.approval.event'].search(
            domain, limit=MAX_HISTORY, order='stamp desc, id desc')
        labels = dict(self.env['biz.approval.event']._fields['kind'].selection)
        rows = [{
            'id': event.id,
            'when': fields.Datetime.to_string(event.stamp) or '',
            'who': event.user_id.name or '',
            'avatar': '/web/image/res.users/%s/avatar_128' % event.user_id.id,
            'kind': event.kind,
            'kind_label': labels.get(event.kind, ''),
            'summary': event.summary or '',
        } for event in events]
        return {'rows': rows,
                'cursor': rows[-1]['id'] if len(rows) == MAX_HISTORY else 0}

    # ================================================== where it applies
    @api.model
    def get_scheme_panel(self, process_key, scope_key=None, company_id=None):
        """Inherited / Shared / Custom for one place, and what will happen.

        The reusable panel's whole data contract. `scope_key` is the place
        being asked about; its exceptions are the bindings NARROWER than it,
        which is every binding whose key starts with this one plus a level.
        """
        self._require_config()
        company = self._company(company_id)
        process = self.env['biz.approval.process']._by_key(process_key)
        if not process:
            raise UserError(_("That kind of request is not in the list."))
        scope_key = scope_key or ''
        Binding = self.env['biz.approval.binding'].sudo()
        rows = Binding.search([('company_id', '=', company.id),
                               ('process_id', '=', process.id),
                               ('active', '=', True)])
        here = rows.filtered(lambda b: (b.scope_key or '') == scope_key)[:1]
        default = rows.filtered(lambda b: not (b.scope_key or ''))[:1]
        exceptions = rows.filtered(
            lambda b: (b.scope_key or '').startswith(scope_key + '|')
            if scope_key else bool(b.scope_key))

        if not here:
            # nothing of its own: it follows whatever the company uses
            selection = 'inherit'
            using = default
        else:
            # its own binding. Whether that is "shared" or "custom" is not a
            # stored flag — it is simply whether anywhere ELSE points at the
            # same route, which is the only definition a reader can check.
            shared = Binding.search_count([
                ('workflow_id', '=', here.workflow_id.id),
                ('active', '=', True)])
            selection = 'shared' if shared > 1 else 'custom'
            using = here

        version = using.workflow_id.published_version_id if using else None
        return {
            'company_id': company.id,
            'process_key': process.key,
            'process_name': process.name,
            'scope_key': scope_key,
            'scope_label': self._scope_label(company, scope_key),
            'selection': selection,
            'workflow_id': using.workflow_id.id if using else 0,
            'workflow_name': using.workflow_id.name if using else '',
            'route_labels': (version.route_labels or []) if version else [],
            'summary': (version.summary or '') if version else '',
            'source': self._panel_source(company, selection, using, version),
            'revision': using.revision if using else 0,
            'exceptions': [{
                'scope_key': b.scope_key or '',
                'label': b.scope_label or b.scope_key,
                'workflow_id': b.workflow_id.id,
                'workflow_name': b.workflow_id.name,
                'route_labels': (b.workflow_id.published_version_id.route_labels
                                 or []) if b.workflow_id.published_version_id
                else [],
            } for b in exceptions],
            'choices': self._panel_choices(company, process),
            'can_config': self._can_config(),
        }

    def _panel_source(self, company, selection, binding, version):
        if selection == 'inherit':
            return _('%s — the route everywhere here', company.name) \
                if binding else _('No route has been chosen yet')
        if selection == 'shared':
            return _('Shared with other parts of the business')
        return _('Only this one — it is shown on the Matrix as an exception')

    def _panel_choices(self, company, process):
        """The routes this place could be pointed at instead."""
        rows = []
        for workflow in self.env['biz.approval.workflow'].sudo().search([
                ('company_id', '=', company.id),
                ('process_id', '=', process.id), ('active', '=', True)],
                limit=MAX_ROWS):
            version = workflow.published_version_id
            rows.append({
                'workflow_id': workflow.id,
                'name': workflow.name,
                'published': bool(version),
                'route_labels': (version.route_labels or []) if version else [],
            })
        return rows

    @api.model
    def set_scheme_binding(self, process_key, scope_key, selection,
                           workflow_id=None, company_id=None,
                           expected_revision=None):
        """Point one place at a route — or back at whatever the company uses."""
        self._require_config()
        company = self._company(company_id)
        process = self.env['biz.approval.process']._by_key(process_key)
        if not process:
            raise UserError(_("That kind of request is not in the list."))
        scope_key = scope_key or ''
        if not scope_key:
            raise UserError(_(
                "The whole company's route is changed on the Matrix, not "
                "here."))
        Binding = self.env['biz.approval.binding']
        existing = Binding.sudo().search([
            ('company_id', '=', company.id),
            ('process_id', '=', process.id),
            ('scope_key', '=', scope_key), ('active', '=', True)], limit=1)
        if existing and expected_revision is not None \
                and int(expected_revision) != existing.revision:
            raise UserError(_(
                "This changed while you were looking at it. Reload to see the "
                "latest."))

        if selection == 'inherit':
            if existing:
                existing.write({'active': False})
            self.env['biz.approval.event']._log(
                'binding_changed',
                _("%(who)s put %(where)s back on the route the rest of the "
                  "company uses", who=self.env.user.name,
                  where=self._scope_label(company, scope_key)),
                company=company, payload={'scope_key': scope_key})
            return self.get_scheme_panel(process_key, scope_key, company.id)

        workflow = self.env['biz.approval.workflow'].browse(
            int(workflow_id or 0)).exists()
        if not workflow or workflow.company_id != company \
                or workflow.process_id != process:
            raise UserError(_("Choose a route for this to follow."))
        label = self._scope_label(company, scope_key)
        if existing:
            existing.write({'workflow_id': workflow.id, 'scope_label': label})
        else:
            Binding.create({
                'company_id': company.id,
                'process_id': process.id,
                'scope_key': scope_key,
                'scope_label': label,
                'kind_key': 'any',
                'workflow_id': workflow.id,
                'mode': 'follow',
            })
        self.env['biz.approval.event']._log(
            'binding_changed',
            _("%(who)s put %(where)s on \"%(name)s\"",
              who=self.env.user.name, where=label, name=workflow.name),
            company=company, workflow=workflow,
            payload={'scope_key': scope_key})
        return self.get_scheme_panel(process_key, scope_key, company.id)
