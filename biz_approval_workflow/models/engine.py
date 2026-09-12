# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The engine: pick the route, show it, publish it, run it.

Everything public here re-checks access and scope; a screen boolean is
decoration. Nothing falls back to "anyone in that group" — an unresolved seat
becomes a stuck request with a named fix, which is repairable, rather than a
silent choice of the wrong person. Nothing approves on its own: being late
reminds, escalates and — only when the business configured it — hands the seat
to a named backup.
"""

import logging
from datetime import datetime, time, timedelta

import psycopg2
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import format_amount

from . import definition as D
from .binding import ANY_KIND

_logger = logging.getLogger(__name__)

_CONFIG_GROUP = 'biz_approval_workflow.group_approval_config'
_PUBLISH_GROUP = 'biz_approval_workflow.group_approval_publish'
_ADMIN_GROUP = 'biz_approval_workflow.group_approval_admin'

_OPEN_STATES = ('pending', 'blocked')


class BizApprovalEngine(models.AbstractModel):
    _name = 'biz.approval.engine'
    _description = 'Approval Engine'

    # =================================================================== gates
    def _is_admin(self):
        user = self.env.user
        return (self.env.su or user._is_admin()
                or user.has_group(_ADMIN_GROUP))

    def _require_config(self):
        if self._is_admin() or self.env.user.has_group(_CONFIG_GROUP):
            return
        raise AccessError(_(
            "You are not allowed to set up approval workflows."))

    def _require_publish(self):
        if self._is_admin() or self.env.user.has_group(_PUBLISH_GROUP):
            return
        raise AccessError(_(
            "You are not allowed to publish an approval workflow."))

    # ============================================================ the route
    def _resolve_binding(self, company, process, scope_keys, kind_key,
                         at=None):
        """(binding, version, trace, error). Most specific scope wins; within
        a scope an exact kind beats "any kind"; a paused winner is a stop."""
        at = at or fields.Datetime.now()
        kind_key = kind_key or ANY_KIND
        keys = list(scope_keys or [])
        if '' not in keys:
            keys.append('')
        Binding = self.env['biz.approval.binding'].sudo()
        trace = []
        winner = None
        for rank, key in enumerate(keys, start=1):
            rows = Binding.search([
                ('company_id', '=', company.id),
                ('process_id', '=', process.id),
                ('scope_key', '=', key or ''),
                ('active', '=', True),
            ])
            rows = rows.filtered(lambda b: b._effective_at(at))
            # within a rank, an exact kind beats "any kind" (ledger AM2)
            exact = rows.filtered(lambda b: (b.kind_key or ANY_KIND) == kind_key)
            if exact:
                chosen = exact
            elif kind_key != ANY_KIND:
                chosen = rows.filtered(
                    lambda b: (b.kind_key or ANY_KIND) == ANY_KIND)
            else:
                chosen = self.env['biz.approval.binding']
            entry = {
                'rank': rank,
                'scope_key': key,
                'label': (rows[:1].scope_label or
                          (_('the whole company') if not key else key)),
                'has': bool(rows),
                'win': False,
                'note': '',
            }
            if len(chosen) > 1:
                entry['note'] = _('More than one route applies here.')
                trace.append(entry)
                return (self.env['biz.approval.binding'],
                        self.env['biz.approval.workflow.version'], trace,
                        {'code': 'ambiguous_route',
                         'message': _(
                             "Two approval routes apply to this at the same "
                             "time, so the app cannot tell which to use. "
                             "Someone who looks after approvals needs to end "
                             "or narrow one of them.")})
            if chosen and not winner:
                winner = chosen
                entry['win'] = True
                entry['note'] = _('This is the route used.')
                trace.append(entry)
                break
            if rows and not chosen:
                entry['note'] = _('Only another kind of request is covered '
                                  'here.')
            elif not rows:
                entry['note'] = _('No route set here.')
            trace.append(entry)

        if not winner:
            return (self.env['biz.approval.binding'],
                    self.env['biz.approval.workflow.version'], trace,
                    {'code': 'no_route',
                     'message': _(
                         "There is no approval set up for this yet. Someone "
                         "who looks after approvals needs to choose one "
                         "before this can be sent in.")})
        if winner.mode == 'paused':
            return (winner, self.env['biz.approval.workflow.version'], trace,
                    {'code': 'paused',
                     'message': _(
                         "Approvals for this are paused, so nothing new can "
                         "be sent in. \"%s\" says why and how to start them "
                         "again.", winner.workflow_id.name)})
        if winner.mode == 'pin':
            version = winner.pinned_version_id
        else:
            version = winner.workflow_id.published_version_id
            if version and version.effective_from and version.effective_from > at:
                # a scheduled version is not in force yet — use the one before
                earlier = winner.workflow_id.version_ids.filtered(
                    lambda v: v.status in ('published', 'superseded')
                    and (not v.effective_from or v.effective_from <= at)
                ).sorted('revision')
                version = earlier[-1:] if earlier else \
                    self.env['biz.approval.workflow.version']
        if not version:
            return (winner, self.env['biz.approval.workflow.version'], trace,
                    {'code': 'no_version',
                     'message': _(
                         "\"%s\" has not been published yet, so it cannot be "
                         "used.", winner.workflow_id.name)})
        return winner, version, trace, None

    @api.model
    def resolve_binding(self, company_id, process_key, scope_keys=None,
                        kind_key=ANY_KIND, at=None):
        """RPC form: a dict, so a caller can show the trace without an error."""
        company = self.env['res.company'].browse(int(company_id)).exists()
        if not company:
            raise UserError(_("That company no longer exists."))
        if not self.env.su and company.id not in self.env.user.company_ids.ids:
            raise AccessError(_("You cannot see that company."))
        process = self.env['biz.approval.process']._by_key(process_key)
        if not process:
            raise UserError(_("That kind of request is not in the list yet."))
        binding, version, trace, error = self._resolve_binding(
            company, process, scope_keys, kind_key,
            fields.Datetime.to_datetime(at) if at else None)
        return {
            'binding_id': binding.id,
            'version_id': version.id,
            'workflow_name': binding.workflow_id.name if binding else '',
            'trace': trace,
            'error': error,
        }

    # ============================================================ the words
    def _naming(self, definition):
        """Role and person names for one definition, for the label helpers."""
        roles = {r.key: r.name
                 for r in self.env['biz.approval.role'].sudo().search([])}
        user_ids = []
        for step in D.normalise(definition)['steps']:
            user_ids += (step.get('who') or {}).get('user_ids') or []
        names = {}
        if user_ids:
            for user in self.env['res.users'].sudo().browse(
                    list(set(user_ids))).exists():
                names[user.id] = user.name
        return roles, names

    @api.model
    def summary(self, definition):
        """One readable line for a definition the caller is still editing.

        The builder writes the same sentence in the browser so it can answer
        on every keystroke; this is the authority the two are reconciled
        against when a draft is saved.
        """
        self._require_config()
        roles, names = self._naming(definition)
        return D.sentence(definition, roles, names)

    @api.model
    def route_labels(self, definition):
        """The short chips a Matrix row shows for a definition."""
        self._require_config()
        roles, names = self._naming(definition)
        return D.route_labels(definition, roles, names)

    # ================================================================ preview
    @api.model
    def preview(self, version_or_definition, example_ctx):
        """Read-only run of a route: who, why, when, and what is wrong.

        A pure function of its inputs: it writes nothing and sends nothing.
        The submission path uses the same resolver, so a green example means
        the route really does resolve for those facts.
        """
        self._require_config()
        ctx = dict(example_ctx or {})
        definition, version = self._definition_of(version_or_definition)
        d = D.normalise(definition)
        company = self.env['res.company'].browse(
            int(ctx.get('company_id') or self.env.company.id))
        on_date = fields.Date.to_date(ctx.get('scope_date')) \
            or fields.Date.context_today(self)
        sg = d['safeguards']
        steps_out, issues = [], []
        previous = []
        included_index = 0
        for step in d['steps']:
            row = {
                'key': step['key'], 'title': step['title'],
                'kind': step['kind'], 'included': True, 'reason': '',
                'people': [], 'issue': None, 'due_at': False,
            }
            if step['kind'] == 'notify':
                uid = ctx.get('submitter_uid')
                row['people'] = self._people_payload(
                    [uid] if uid else [], _('Sent this in'))
                steps_out.append(row)
                continue
            if step['kind'] == 'fast':
                row['reason'] = _(
                    'Applied as soon as it is sent in, and recorded.')
                steps_out.append(row)
                continue
            included, reason = self._step_included(d, step, ctx)
            row['included'], row['reason'] = included, reason
            if not included:
                steps_out.append(row)
                continue
            included_index += 1
            people, issue = self._resolve_step_people(
                step, ctx, company, on_date)
            row['people'] = people
            row['issue'] = issue
            if not issue:
                issue = self._independence_issue(sg, step, people, ctx)
                row['issue'] = issue
            if not row['issue'] and sg.get('repeated') == 'different':
                people, row['issue'] = self._repeated_issue(
                    step, people, previous)
                row['people'] = people
            previous += [p['user_id'] for p in row['people']]
            row['due_at'] = fields.Datetime.to_string(
                self._due_for(company, sg, included_index)) or False
            if row['issue']:
                issues.append(dict(row['issue'], step=step['title']))
            steps_out.append(row)

        # route-level notes
        decision = [s for s in steps_out
                    if s['kind'] not in ('notify',) and s['included']]
        if any(s['kind'] == 'fast' for s in decision):
            issues.append({
                'level': 'warn', 'code': 'fast_lane', 'step': _('Route'),
                'msg': _("Nobody checks this before it happens. That is your "
                         "choice; every one is still recorded."), 'fixes': []})
        elif not decision:
            issues.append({
                'level': 'warn', 'code': 'fast_lane', 'step': _('Route'),
                'msg': _("No step applies to this example, so it would be "
                         "applied immediately and recorded."), 'fixes': []})
        level = 'block' if any(i['level'] == 'block' for i in issues) else (
            'warn' if issues else 'ready')
        via = []
        if ctx.get('process_key'):
            process = self.env['biz.approval.process']._by_key(
                ctx['process_key'])
            if process:
                _b, _v, via, _e = self._resolve_binding(
                    company, process, ctx.get('scope_keys'),
                    ctx.get('kind_key'))
        return {
            'steps': steps_out,
            'issues': issues,
            'level': level,
            'via': via,
            'summary': version.summary if version else D.sentence(definition),
        }

    def _definition_of(self, version_or_definition):
        Version = self.env['biz.approval.workflow.version']
        if isinstance(version_or_definition, dict):
            return version_or_definition, Version
        if isinstance(version_or_definition, int):
            version = Version.browse(version_or_definition).exists()
        else:
            version = version_or_definition
        if not version:
            raise UserError(_("That version of the workflow no longer "
                              "exists."))
        return version.definition, version

    # -------------------------------------------------------- step inclusion
    def _step_included(self, d, step, ctx):
        facts = ctx.get('facts') or {}
        reason = ''
        min_amount = step.get('min_amount') or 0
        if min_amount and d['tiers'].get('enabled'):
            tier_fact = d['tiers'].get('fact')
            value = D.fact_value(facts, tier_fact)
            if value is None:
                value = ctx.get('amount')
            try:
                value = float(value or 0)
            except (TypeError, ValueError):
                value = 0.0
            if value < float(min_amount):
                return False, _("Not needed: the amount is under %s.",
                                self._fmt_amount(min_amount, ctx))
            reason = _("Included: the amount is %s or more.",
                       self._fmt_amount(min_amount, ctx))
        condition = step.get('condition')
        if condition:
            if not D.condition_holds(condition, facts):
                return False, _("Not needed: %s.",
                                D.condition_phrase(condition,
                                                   ctx.get('fact_labels')))
            phrase = _("Included: %s.", D.condition_phrase(
                condition, ctx.get('fact_labels')))
            reason = '%s %s' % (reason, phrase) if reason else phrase
        return True, reason

    def _fmt_amount(self, amount, ctx):
        currency = self.env['res.currency'].browse(
            ctx.get('currency_id') or 0).exists()
        if currency:
            return format_amount(self.env, float(amount or 0), currency)
        return '{:,.0f}'.format(float(amount or 0))

    # --------------------------------------------------------- people lookup
    def _people_payload(self, user_ids, via, backup=None, cover=None):
        users = self.env['res.users'].sudo().browse(
            [u for u in user_ids if u]).exists()
        return [{
            'user_id': u.id, 'name': u.name, 'via': via,
            'backup_user_id': backup.id if backup else False,
            'cover_user_id': cover.id if cover else False,
            'active': u.active,
        } for u in users]

    def _resolve_step_people(self, step, ctx, company, on_date, record=None):
        """Who decides this step right now, and why. (people, issue)."""
        who = step.get('who') or {}
        mode = who.get('mode')
        if mode == 'role':
            role = self.env['biz.approval.role'].sudo().search(
                [('key', '=', who.get('role'))], limit=1)
            if not role:
                return [], {'level': 'block', 'code': 'unknown_role',
                            'msg': _("This step uses a responsibility that no "
                                     "longer exists."), 'fixes': []}
            keys = [''] if (who.get('scope') == 'company') \
                else list(ctx.get('scope_keys') or [])
            row, via_label = self.env['biz.approval.responsibility'].resolve(
                company, role, keys, on_date)
            if not row:
                return [], {
                    'level': 'block', 'code': 'person_missing',
                    'msg': _("Nobody holds \"%(role)s\" for %(where)s yet.",
                             role=role.name,
                             where=(ctx.get('scope_label')
                                    or _('this part of the business'))),
                    'fixes': [{'label': _('Choose a person'),
                               'act': 'assign',
                               'arg': '%s|%s' % (role.key,
                                                 (keys or [''])[0])}]}
            via = _("%(role)s for %(where)s", role=role.name, where=via_label)
            if role.is_pool:
                members = row.pool_user_ids or row.user_id
                return self._people_payload(members.ids, via), None
            return self._people_payload(
                row.user_id.ids, via, backup=row.backup_user_id), None
        if mode in ('manager', 'skip'):
            if record is not None:
                uids = (record._approval_manager_uids() if mode == 'manager'
                        else record._approval_skip_manager_uids())
            else:
                uids = ctx.get('manager_uids' if mode == 'manager'
                               else 'skip_manager_uids') or []
            if not uids:
                return [], {
                    'level': 'block', 'code': 'manager_missing',
                    'msg': _("No manager is recorded for the people this is "
                             "about, so nobody can be asked."),
                    'fixes': [{'label': _('Open the employee record'),
                               'act': 'open_subject', 'arg': ''}]}
            label = _('Their manager') if mode == 'manager' \
                else _("Their manager's manager")
            people = self._people_payload(uids, label)
            issue = None
            if len(people) > 1:
                issue = {'level': 'warn', 'code': 'split',
                         'msg': _("This is about several people with "
                                  "different managers, so more than one "
                                  "person would be asked."), 'fixes': []}
            return people, issue
        if mode in ('people', 'team'):
            uids = who.get('user_ids') or []
            via = _('Named in this workflow') if mode == 'people' \
                else _("One of %s", who.get('label') or _('the team'))
            people = self._people_payload(uids, via)
            if not people:
                return [], {'level': 'block', 'code': 'no_people',
                            'msg': _("This step names nobody."), 'fixes': []}
            gone = [u for u in uids if u not in [p['user_id'] for p in people]]
            inactive = [p for p in people if not p['active']]
            if gone or inactive:
                return people, {
                    'level': 'block', 'code': 'person_inactive',
                    'msg': _("Someone named on this step no longer has an "
                             "account in use."), 'fixes': []}
            return people, None
        if mode == 'preparer':
            uid = ctx.get('submitter_uid')
            return self._people_payload([uid] if uid else [],
                                        _('Sent this in')), None
        return [], {'level': 'block', 'code': 'bad_who',
                    'msg': _("This step does not say who decides it."),
                    'fixes': []}

    def _conflict_kind(self, uid, ctx):
        if uid and uid == ctx.get('submitter_uid'):
            return 'submitter'
        if uid and uid in (ctx.get('maker_uids') or []):
            return 'maker'
        if uid and uid in (ctx.get('subject_uids') or []):
            return 'subject'
        return None

    def _independence_issue(self, safeguards, step, people, ctx):
        if not safeguards.get('independent'):
            return None
        for person in people:
            kind = self._conflict_kind(person['user_id'], ctx)
            if not kind:
                continue
            phrase = {
                'submitter': _('sent this in'),
                'maker': _('prepared this'),
                'subject': _('this is about them'),
            }[kind]
            if (safeguards.get('self_exception') or {}).get('enabled'):
                return {'level': 'warn', 'code': 'self_exception',
                        'msg': _("%(name)s %(why)s. With a written reason "
                                 "they may still decide, and it is marked in "
                                 "the trail.", name=person['name'],
                                 why=phrase), 'fixes': []}
            fixes = []
            if person.get('backup_user_id'):
                fixes.append({'label': _('Use the backup instead'),
                              'act': 'use_backup',
                              'arg': str(person['backup_user_id'])})
            fixes.append({'label': _('Turn the independence rule off'),
                          'act': 'independence_off', 'arg': ''})
            return {'level': 'block', 'code': 'self',
                    'msg': _("%(name)s %(why)s and cannot also decide this "
                             "step while the independence rule is on.",
                             name=person['name'], why=phrase),
                    'fixes': fixes}
        return None

    def _repeated_issue(self, step, people, previous):
        """Same person twice in a row: send it to the backup, or say so."""
        if len(people) != 1:
            return people, None
        person = people[0]
        if person['user_id'] not in previous:
            return people, None
        backup = person.get('backup_user_id')
        if backup and backup not in previous:
            replacement = self._people_payload(
                [backup], _("Backup for %s (they already decided an earlier "
                            "step)", person['name']))
            return replacement, {
                'level': 'warn', 'code': 'repeat',
                'msg': _("%s already decides an earlier step, so this one "
                         "goes to their backup.", person['name']),
                'fixes': []}
        return people, {
            'level': 'warn', 'code': 'repeat_no_backup',
            'msg': _("%s already decides an earlier step and has no backup, "
                     "so they would be asked twice.", person['name']),
            'fixes': [{'label': _('Name a backup'), 'act': 'assign',
                       'arg': ''}]}

    # ------------------------------------------------------------ due dates
    def _due_for(self, company, safeguards, index, base=None):
        due = (safeguards or {}).get('due') or {}
        kind = due.get('kind') or 'none'
        if kind in ('none', 'per_request'):
            return False
        now = base or fields.Datetime.now()
        if kind == 'working_days':
            days = max(int(due.get('days') or 1), 0) * max(index, 1)
            calendar = self.env['resource.calendar'].browse(
                due.get('calendar_id')).exists() or company.resource_calendar_id
            if calendar and hasattr(calendar, 'plan_days'):
                try:
                    aware = pytz.utc.localize(now)
                    planned = calendar.plan_days(days, aware,
                                                 compute_leaves=True)
                    if planned:
                        return planned.astimezone(pytz.utc).replace(
                            tzinfo=None)
                except Exception:  # noqa: BLE001 — a calendar must never stop
                    _logger.exception('approval due date: calendar failed')
            return now + timedelta(days=days)
        if kind == 'calendar_day':
            day = max(min(int(due.get('day') or 15), 28), 1)
            tz = pytz.timezone(company.partner_id.tz or self.env.user.tz
                               or 'UTC')
            local = pytz.utc.localize(now).astimezone(tz)
            target = local.replace(day=day, hour=17, minute=0, second=0,
                                   microsecond=0)
            if target <= local:
                month = local.month + 1
                year = local.year + (1 if month > 12 else 0)
                month = 1 if month > 12 else month
                target = tz.localize(datetime.combine(
                    datetime(year, month, day).date(), time(17, 0)))
            return target.astimezone(pytz.utc).replace(tzinfo=None)
        return False

    # ============================================================== publish
    @api.model
    def validate_for_publish(self, version_id):
        """Everything that would stop or worry a publisher, in one answer."""
        self._require_config()
        version = self.env['biz.approval.workflow.version'].browse(
            int(version_id))
        version.check_access('read')
        workflow = version.workflow_id
        process = workflow.process_id
        capabilities = self._capabilities_of(process)
        result = D.validate(version.definition, capabilities, env=self.env)
        errors = list(result['errors'])
        warnings = list(result['warnings'])

        if process.money and any(w['code'] == 'single_person'
                                 for w in warnings):
            warnings.append({
                'code': 'money_single_person', 'step': None,
                'message': _("Money leaves the company on this one and only "
                             "one person signs it off. Two people are the "
                             "usual safeguard.")})

        # a tie at publish time is a structural error, not a warning
        Binding = self.env['biz.approval.binding'].sudo()
        for binding in Binding.search([('workflow_id', '=', workflow.id),
                                       ('active', '=', True)]):
            clash = Binding.search([
                ('id', '!=', binding.id),
                ('company_id', '=', binding.company_id.id),
                ('process_id', '=', binding.process_id.id),
                ('scope_key', '=', binding.scope_key or ''),
                ('kind_key', '=', binding.kind_key or ANY_KIND),
                ('active', '=', True),
            ])
            clash = clash.filtered(lambda b: b._overlaps(binding))
            if clash:
                errors.append({
                    'code': 'ambiguous_route', 'step': None,
                    'message': _("\"%s\" covers the same place and kind of "
                                 "request as this one. End or narrow one of "
                                 "them first.", clash[0].workflow_id.name)})

        # whole coverage: every place this process happens needs its people
        coverage = self.coverage_scan(version.id)
        if coverage.get('ran'):
            for row in coverage['rows']:
                for issue in row['issues']:
                    warnings.append({
                        'code': 'coverage_gap:%s' % (row['scope_key'] or
                                                     'company'),
                        'step': issue.get('step'),
                        'message': _("%(where)s: %(what)s Requests from there "
                                     "will be stuck until someone is named.",
                                     where=row['label'], what=issue['msg'])})
        else:
            warnings.append({
                'code': 'coverage_not_run', 'step': None,
                'message': _("The whole-coverage check could not run for this "
                             "kind of request, so one good example is all "
                             "there is.")})

        # a step with no backup is worth knowing about before it is late
        for step in D.decision_steps(version.definition):
            who = step.get('who') or {}
            if who.get('mode') != 'role':
                continue
            role = self.env['biz.approval.role'].sudo().search(
                [('key', '=', who.get('role'))], limit=1)
            if not role or role.is_pool:
                continue
            holders = self.env['biz.approval.responsibility'].sudo().search([
                ('company_id', '=', workflow.company_id.id),
                ('role_id', '=', role.id), ('active', '=', True)])
            if holders and not any(h.backup_user_id for h in holders):
                warnings.append({
                    'code': 'no_backup:%s' % step['key'],
                    'step': step.get('title'),
                    'message': _("\"%s\" has nobody named as a backup, so a "
                                 "holiday will hold it up.",
                                 step.get('title') or role.name)})
        return {'errors': errors, 'warnings': warnings}

    def _capabilities_of(self, process):
        model = process.model_name
        if model and model in self.env \
                and getattr(self.env[model], '_approval_process_key', None):
            return self.env[model]._approval_capabilities()
        return {}

    @api.model
    def coverage_scan(self, version_id):
        """Run the route against every place the process happens."""
        self._require_config()
        version = self.env['biz.approval.workflow.version'].browse(
            int(version_id))
        version.check_access('read')
        workflow = version.workflow_id
        process = workflow.process_id
        model = process.model_name
        if not (model and model in self.env
                and getattr(self.env[model], '_approval_process_key', None)):
            return {'ran': False, 'rows': []}
        scopes = self.env[model]._approval_coverage_scopes(
            workflow.company_id)
        d = D.normalise(version.definition)
        on_date = fields.Date.context_today(self)
        rows = []
        for scope in scopes:
            ctx = {
                'company_id': workflow.company_id.id,
                'scope_keys': scope.get('scope_keys')
                or [scope.get('scope_key') or '', ''],
                'scope_label': scope.get('label'),
                'kind_key': scope.get('kind_key') or ANY_KIND,
                'facts': scope.get('facts') or {},
            }
            issues = []
            for step in D.decision_steps(d):
                if step['kind'] == 'fast':
                    continue
                people, issue = self._resolve_step_people(
                    step, ctx, workflow.company_id, on_date)
                if issue and issue['level'] == 'block':
                    issues.append({'step': step.get('title'),
                                   'msg': issue['msg']})
            rows.append({
                'scope_key': scope.get('scope_key') or '',
                'label': scope.get('label') or _('the whole company'),
                'headcount': scope.get('headcount') or 0,
                'issues': issues,
            })
        return {'ran': True, 'rows': rows}

    @api.model
    def publish(self, version_id, expected_draft_revision=None,
                effective_from=None, reason=None, confirmations=None):
        """Make a draft the one future requests follow."""
        self._require_publish()
        Version = self.env['biz.approval.workflow.version']
        version = Version.browse(int(version_id))
        version.check_access('write')
        if version.status != 'draft':
            raise UserError(_("Only a draft can be published."))
        if expected_draft_revision is not None \
                and int(expected_draft_revision) != version.draft_revision:
            raise UserError(_(
                "This workflow changed while you were looking at it. Open it "
                "again to see the latest before publishing."))
        checks = self.validate_for_publish(version.id)
        if checks['errors']:
            raise UserError(_(
                "This cannot be published yet:\n%s",
                '\n'.join('• %s' % e['message'] for e in checks['errors'])))
        confirmed = {c.get('code') for c in (confirmations or [])
                     if isinstance(c, dict)}
        confirmed |= {c for c in (confirmations or []) if isinstance(c, str)}
        missing = [w for w in checks['warnings'] if w['code'] not in confirmed]
        if missing:
            raise UserError(_(
                "Please confirm these before publishing:\n%s",
                '\n'.join('• %s' % w['message'] for w in missing)))
        stamp = fields.Datetime.now()
        stored = []
        by_code = {w['code']: w for w in checks['warnings']}
        for code in confirmed:
            if code not in by_code:
                continue
            stored.append({
                'code': code, 'text': by_code[code]['message'],
                'user_id': self.env.uid, 'user_name': self.env.user.name,
                'stamp': fields.Datetime.to_string(stamp),
            })
        workflow = version.workflow_id
        previous = workflow.published_version_id
        effective = fields.Datetime.to_datetime(effective_from) or stamp
        # the version is still a draft at this point, so the immutability
        # guard lets this one write through — and nothing after it
        version.write({
            'status': 'published',
            'published_by_uid': self.env.uid,
            'published_at': stamp,
            'effective_from': effective,
            'publish_reason': reason or '',
            'confirmations': stored,
            'fingerprint': D.fingerprint(version.definition),
            'schema_version': D.SCHEMA_VERSION,
        })
        if previous and previous.id != version.id:
            previous.sudo().write({'status': 'superseded'})
        self.env['biz.approval.event']._log(
            'published',
            _("%(who)s published \"%(name)s\" version %(rev)s",
              who=self.env.user.name, name=workflow.name,
              rev=version.revision),
            company=workflow.company_id, workflow=workflow,
            payload={'version_id': version.id, 'revision': version.revision,
                     'reason': reason or '',
                     'confirmations': [c['code'] for c in stored]})
        return {'version_id': version.id, 'revision': version.revision,
                'published_at': fields.Datetime.to_string(stamp)}

    # =============================================================== submit
    @api.model
    def submit(self, record, res_id=None, idempotency_key=None):
        """Send a record in for approval and open the first step."""
        record = self._as_record(record, res_id)
        record.check_access('write')
        if idempotency_key:
            existing = self.env['biz.approval.request'].sudo().search(
                [('idempotency_key', '=', idempotency_key)], limit=1)
            if existing:
                return self._request_payload(existing)
        record._approval_validate()
        process = record._approval_process()
        ctx = record._approval_context()
        company = self.env['res.company'].browse(int(ctx['company_id']))
        binding, version, trace, error = self._resolve_binding(
            company, process, ctx.get('scope_keys'), ctx.get('kind_key'))
        if error:
            raise UserError(error['message'])
        d = D.normalise(version.definition)
        attempt = 1 + self.env['biz.approval.request'].sudo().search_count([
            ('res_model', '=', record._name), ('res_id', '=', record.id)])
        maker_uids = [u for u in (ctx.get('maker_uids') or []) if u]
        request = self.env['biz.approval.request'].create({
            'title': ctx.get('title') or record.display_name,
            'process_id': process.id,
            'company_id': company.id,
            'res_model': record._name,
            'res_id': record.id,
            'attempt': attempt,
            'source_revision': ctx.get('source_revision') or '',
            'scope_keys': list(ctx.get('scope_keys') or []),
            'scope_label': ctx.get('scope_label') or '',
            'kind_key': ctx.get('kind_key') or ANY_KIND,
            'facts': ctx.get('facts') or {},
            'amount': ctx.get('amount') or 0.0,
            'currency_id': ctx.get('currency_id') or False,
            'maker_uids': maker_uids,
            'maker_user_ids': [(6, 0, maker_uids)],
            'submitter_uid': ctx.get('submitter_uid') or self.env.uid,
            'subject_uids': list(ctx.get('subject_uids') or []),
            'binding_id': binding.id,
            'version_id': version.id,
            'state': 'pending',
            'submitted_at': fields.Datetime.now(),
            'confirmations': version.confirmations or [],
            'idempotency_key': idempotency_key or False,
        })
        record._approval_freeze(request)
        blocked = self._build_steps(request, d, ctx, record)
        active = request.step_ids.filtered(
            lambda s: s.included and s.kind != 'notify')
        fast = (not active) or any(s.kind == 'fast' for s in active)
        self.env['biz.approval.event']._log(
            'submitted', _("%(who)s sent \"%(what)s\" in for approval",
                           who=self.env.user.name, what=request.title),
            company=company, request=request,
            payload={'attempt': attempt, 'version_id': version.id})
        if fast:
            request.write({'state': 'approved'})
            self._run_apply(request, record)
            return self._request_payload(request)
        if blocked:
            request.write({'state': 'blocked', 'block_reason': blocked})
            self.env['biz.approval.event']._log(
                'blocked', _("\"%(what)s\" cannot go ahead: %(why)s",
                             what=request.title, why=blocked),
                company=company, request=request)
            return self._request_payload(request)
        self._activate_next(request)
        return self._request_payload(request)

    def _as_record(self, record, res_id=None):
        if isinstance(record, models.BaseModel):
            record.ensure_one()
            return record
        if isinstance(record, str) and res_id:
            if record not in self.env:
                raise UserError(_("That kind of record is not part of this "
                                  "app."))
            found = self.env[record].browse(int(res_id)).exists()
            if not found:
                raise UserError(_("That record no longer exists."))
            return found
        raise UserError(_("Nothing was given to send in for approval."))

    def _build_steps(self, request, d, ctx, record):
        """Create every step and, for the included ones, its seats."""
        Step = self.env['biz.approval.request.step']
        Seat = self.env['biz.approval.request.seat']
        company = request.company_id
        on_date = fields.Date.to_date(ctx.get('scope_date')) \
            or fields.Date.context_today(self)
        sg = d['safeguards']
        previous = []
        block_reason = ''
        index = 0
        for sequence, step in enumerate(d['steps'], start=1):
            kind = step['kind']
            included, reason = (True, '')
            if kind not in ('notify', 'fast'):
                included, reason = self._step_included(d, step, ctx)
            row = Step.create({
                'request_id': request.id,
                'company_id': company.id,
                'key': step['key'],
                'sequence': sequence * 10,
                'title': step['title'],
                'kind': kind,
                'included': included,
                'include_reason': reason,
                'status': 'pending' if included else 'skipped',
            })
            if not included or kind in ('notify', 'fast'):
                continue
            index += 1
            people, issue = self._resolve_step_people(
                step, ctx, company, on_date, record=record)
            if issue and issue['level'] == 'block':
                row.write({'status': 'blocked',
                           'block_reason': issue['msg']})
                block_reason = block_reason or issue['msg']
                continue
            if sg.get('repeated') == 'different':
                people, _issue = self._repeated_issue(step, people, previous)
            row.write({'due_at': self._due_for(company, sg, index)})
            for person in people:
                user = self.env['res.users'].sudo().browse(person['user_id'])
                Seat.create({
                    'step_id': row.id,
                    'company_id': company.id,
                    'key': 'u%s' % user.id,
                    'user_id': user.id,
                    'acting_user_id': user.id,
                    'resolved_via': person.get('via') or '',
                    'backup_user_id': person.get('backup_user_id') or False,
                    'status': 'open',
                })
            previous += [p['user_id'] for p in people]
        return block_reason

    # ------------------------------------------------------- step activation
    def _activate_next(self, request):
        """Open the first step that still needs a decision."""
        waiting = request.step_ids.filtered(
            lambda s: s.included and s.kind not in ('notify', 'fast')
            and s.status in ('pending', 'blocked')).sorted('sequence')
        stuck = waiting.filtered(lambda s: s.status == 'blocked')
        if stuck:
            # a later step nobody can fill must stop the request, never be
            # quietly skipped on the way to "approved"
            request.write({'state': 'blocked',
                           'block_reason': stuck[0].block_reason or _(
                               "Nobody could be found to decide "
                               "\"%s\".", stuck[0].title)})
            return False
        step = waiting[:1]
        if not step:
            return self._complete(request)
        if not step.seat_ids:
            request.write({'state': 'blocked',
                           'block_reason': step.block_reason or _(
                               "Nobody could be found to decide "
                               "\"%s\".", step.title)})
            return False
        # resolve a hand-over at the moment the step opens
        for seat in step.seat_ids:
            cover = self.env['biz.approval.delegation'].covering(
                seat.user_id, request.company_id)
            if cover and cover != seat.user_id:
                seat.write({'acting_user_id': cover.id,
                            'resolved_via': _("%(via)s · covered by %(who)s",
                                              via=seat.resolved_via or '',
                                              who=cover.name)})
                self.env['biz.approval.outbox']._queue(
                    'covering', cover, request,
                    payload={'step_title': step.title},
                    dedupe='covering-%s-%s-%s' % (request.id, step.id,
                                                  cover.id))
        step.write({'status': 'active',
                    'activated_at': fields.Datetime.now(),
                    'due_at': step.due_at})
        request.write({'current_step_key': step.key,
                       'due_at': step.due_at,
                       'state': 'pending'})
        for seat in step.seat_ids.filtered(lambda s: s.status == 'open'):
            self.env['biz.approval.outbox']._queue(
                'your_turn', seat.acting_user_id, request,
                payload={'step_title': step.title},
                dedupe='your_turn-%s-%s-%s' % (request.id, step.id,
                                               seat.acting_user_id.id))
        self.env['biz.approval.event']._log(
            'step_activated',
            _("\"%(step)s\" is waiting for a decision on \"%(what)s\"",
              step=step.title, what=request.title),
            company=request.company_id, request=request,
            payload={'step_key': step.key})
        return True

    def _complete(self, request):
        """Every step decided — approve, then let the adapter carry it out."""
        request.write({'state': 'approved', 'current_step_key': False,
                       'closed_at': fields.Datetime.now()})
        record = request._record()
        self._run_apply(request, record)
        return True

    def _run_apply(self, request, record=None):
        """Carry out the change, once, under the request lock."""
        record = record if record is not None else request._record()
        try:
            with self.env.cr.savepoint():
                current = (record._approval_context() or {}).get(
                    'source_revision') or ''
                if request.source_revision and current \
                        and current != request.source_revision:
                    raise UserError(_(
                        "This changed after it was sent in, so the approval "
                        "no longer covers it. Send it back and ask for it "
                        "again."))
                record._approval_apply(request)
        except Exception as exc:  # noqa: BLE001 — never half-apply
            self.env.invalidate_all()
            message = exc.args[0] if isinstance(exc, UserError) and exc.args \
                else _("The change could not be carried out. Nothing was "
                       "half-done; it can be tried again.")
            request.write({'state': 'approved', 'block_reason': message})
            self.env['biz.approval.event']._log(
                'blocked',
                _("\"%(what)s\" was approved but could not be carried out: "
                  "%(why)s", what=request.title, why=message),
                company=request.company_id, request=request)
            _logger.warning('approval apply failed on %s: %s',
                            request.id, exc)
            return False
        request.write({'state': 'applied', 'block_reason': False,
                       'closed_at': fields.Datetime.now()})
        self.env['biz.approval.event']._log(
            'applied', _("\"%s\" was carried out", request.title),
            company=request.company_id, request=request)
        if request.submitter_uid:
            self.env['biz.approval.outbox']._queue(
                'approved', request.submitter_uid, request,
                dedupe='approved-%s-%s' % (request.id, request.attempt))
        return True

    @api.model
    def retry_apply(self, request_id):
        request = self._as_request(request_id)
        if not (self._is_admin() or request.submitter_uid.id == self.env.uid):
            raise AccessError(_("You are not allowed to try this again."))
        if request.state != 'approved':
            raise UserError(_("This is not waiting to be carried out."))
        self._run_apply(request)
        return self._request_payload(request)

    # =============================================================== decide
    def _as_request(self, request):
        if isinstance(request, models.BaseModel):
            request.ensure_one()
            return request
        found = self.env['biz.approval.request'].browse(
            int(request)).exists()
        if not found:
            raise UserError(_("That request no longer exists."))
        found.check_access('read')
        return found

    def _lock(self, request):
        # raw SQL sees the table, not the ORM cache: push everything pending
        # down first, or this can block on our own unwritten rows
        self.env.flush_all()
        try:
            self.env.cr.execute(
                'SELECT id FROM biz_approval_request WHERE id = %s '
                'FOR UPDATE NOWAIT', (request.id,))
        except psycopg2.OperationalError:
            raise UserError(_(
                "Someone else is deciding this right now. Give it a moment "
                "and try again."))

    @api.model
    def decide(self, request, step_key, action, reason=None,
               expected_lock_revision=None, idempotency_key=None,
               exception_grant_id=None):
        """Record one decision, and move the request on."""
        request = self._as_request(request)
        self._lock(request)
        request.invalidate_recordset()
        if idempotency_key:
            done = self.env['biz.approval.decision'].sudo().search(
                [('idempotency_key', '=', idempotency_key)], limit=1)
            if done:
                return self._request_payload(request)
        if expected_lock_revision is not None \
                and int(expected_lock_revision) != request.lock_revision:
            raise UserError(_(
                "This request changed while you were looking at it. Reload to "
                "see the latest."))
        if action not in ('approve', 'return', 'reject'):
            raise UserError(_("That is not something you can do here."))
        if request.state not in _OPEN_STATES:
            raise UserError(_(
                "This request is already finished, so it cannot be decided "
                "again."))
        step = request.step_ids.filtered(
            lambda s: s.key == step_key and s.status == 'active')[:1]
        if not step:
            raise UserError(_("That step is not waiting for a decision."))

        user = self.env.user
        seat = step.seat_ids.filtered(
            lambda s: s.status == 'open' and s.acting_user_id.id == user.id
        )[:1]
        if not seat:
            already = step.seat_ids.filtered(
                lambda s: s.acting_user_id.id == user.id)
            if already:
                raise UserError(_(
                    "You have already given your answer on this step."))
            raise AccessError(_(
                "This step is not waiting for you."))
        if not user.active:
            raise AccessError(_("Your account is no longer in use."))
        record = request._record()
        record.check_access('read')
        if seat.acting_user_id != seat.user_id:
            still = self.env['biz.approval.delegation'].covering(
                seat.user_id, request.company_id)
            if still != seat.acting_user_id:
                raise AccessError(_(
                    "You are no longer covering this seat, so you cannot "
                    "decide it. Someone who looks after approvals can move "
                    "it."))

        # ---------------------------------------------------- independence
        sg = D.normalise(request.version_id.definition)['safeguards']
        conflict = None
        grant = self.env['biz.approval.exception.grant']
        if action == 'approve' and sg.get('independent'):
            ctx = {
                'submitter_uid': request.submitter_uid.id,
                'maker_uids': request.maker_uids or [],
                'subject_uids': request.subject_uids or [],
            }
            conflict = self._conflict_kind(user.id, ctx) \
                or self._conflict_kind(seat.user_id.id, ctx)
            if conflict:
                grant = self.env['biz.approval.exception.grant'].sudo().browse(
                    int(exception_grant_id or 0)).exists()
                if not grant or not grant.permits(request, step, user,
                                                  conflict):
                    raise UserError(_(
                        "You were part of preparing or sending this in, so "
                        "you cannot also approve it. Ask someone else, or ask "
                        "for an exception to be set up."))
                if not (reason or '').strip():
                    raise UserError(_(
                        "Write why you are approving something you were part "
                        "of. It is kept with the decision."))

        decision = self.env['biz.approval.decision'].create({
            'request_id': request.id,
            'company_id': request.company_id.id,
            'step_id': step.id,
            'seat_id': seat.id,
            'step_key': step.key,
            'acting_for_uid': seat.user_id.id
            if seat.user_id != user else False,
            'action': action,
            'reason': reason or '',
            'source_revision': request.source_revision,
            'idempotency_key': idempotency_key or False,
            'exception_grant_id': grant.id if grant else False,
            'conflict_kind': conflict or False,
        })
        request._bump_lock()
        self.env['biz.approval.event']._log(
            'decided',
            _("%(who)s %(did)s \"%(step)s\" on \"%(what)s\"",
              who=user.name, did={'approve': _('approved'),
                                  'return': _('sent back'),
                                  'reject': _('turned down')}[action],
              step=step.title, what=request.title),
            company=request.company_id, request=request,
            payload={'step_key': step.key, 'action': action,
                     'decision_id': decision.id})
        if conflict and grant:
            self.env['biz.approval.event']._log(
                'exception_used',
                _("%(who)s approved \"%(step)s\" on \"%(what)s\" using an "
                  "exception", who=user.name, step=step.title,
                  what=request.title),
                company=request.company_id, request=request,
                payload={'grant_id': grant.id, 'conflict': conflict,
                         'reason': reason or ''})
            owner = request.version_id.workflow_id.owner_user_id
            if owner:
                self.env['biz.approval.outbox']._queue(
                    'exception_used', owner, request,
                    payload={'step_title': step.title, 'reason': reason or ''},
                    dedupe='exception_used-%s' % decision.id)

        if action == 'return':
            return self._do_return(request, step, seat, reason, record)
        if action == 'reject':
            return self._do_reject(request, step, seat, reason, record)
        return self._do_approve(request, step, seat)

    def _do_approve(self, request, step, seat):
        seat.write({'status': 'approved'})
        all_required = step.kind == 'joint'
        if all_required:
            outstanding = step.seat_ids.filtered(
                lambda s: s.status == 'open')
            if outstanding:
                return self._request_payload(request)
        else:
            step.seat_ids.filtered(lambda s: s.status == 'open').write(
                {'status': 'closed'})
        step.write({'status': 'done', 'decided_at': fields.Datetime.now()})
        self._activate_next(request)
        return self._request_payload(request)

    def _do_return(self, request, step, seat, reason, record):
        seat.write({'status': 'returned'})
        step.seat_ids.filtered(lambda s: s.status == 'open').write(
            {'status': 'closed'})
        step.write({'status': 'returned',
                    'decided_at': fields.Datetime.now()})
        request.write({'state': 'returned', 'return_note': reason or '',
                       'closed_at': fields.Datetime.now(),
                       'current_step_key': False})
        record._approval_return(request, reason or '')
        self.env['biz.approval.event']._log(
            'returned', _("\"%(what)s\" was sent back: %(why)s",
                          what=request.title,
                          why=reason or _('no reason given')),
            company=request.company_id, request=request)
        if request.submitter_uid:
            self.env['biz.approval.outbox']._queue(
                'returned', request.submitter_uid, request,
                payload={'reason': reason or ''},
                dedupe='returned-%s-%s' % (request.id, request.attempt))
        return self._request_payload(request)

    def _do_reject(self, request, step, seat, reason, record):
        seat.write({'status': 'rejected'})
        step.seat_ids.filtered(lambda s: s.status == 'open').write(
            {'status': 'closed'})
        step.write({'status': 'done', 'decided_at': fields.Datetime.now()})
        request.write({'state': 'rejected', 'return_note': reason or '',
                       'closed_at': fields.Datetime.now(),
                       'current_step_key': False})
        self.env['biz.approval.event']._log(
            'rejected', _("\"%(what)s\" was turned down: %(why)s",
                          what=request.title,
                          why=reason or _('no reason given')),
            company=request.company_id, request=request)
        if request.submitter_uid:
            self.env['biz.approval.outbox']._queue(
                'rejected', request.submitter_uid, request,
                payload={'reason': reason or ''},
                dedupe='rejected-%s-%s' % (request.id, request.attempt))
        return self._request_payload(request)

    # ============================================== reassign / cancel / repair
    @api.model
    def reassign(self, request, seat_key, new_user_id, reason=None):
        request = self._as_request(request)
        owner = request.version_id.workflow_id.owner_user_id
        if not (self._is_admin() or (owner and owner.id == self.env.uid)):
            raise AccessError(_(
                "Only someone who looks after this workflow can move a step "
                "to someone else."))
        if not (reason or '').strip():
            raise UserError(_("Say why you are moving this to someone else."))
        seat = request.seat_ids.filtered(
            lambda s: s.key == seat_key and s.status == 'open')[:1]
        if not seat:
            raise UserError(_("That seat is not waiting for anyone."))
        new_user = self.env['res.users'].browse(int(new_user_id)).exists()
        if not new_user or not new_user.active or new_user.share:
            raise UserError(_("That person cannot be asked to decide this."))
        if request.company_id.id not in new_user.company_ids.ids:
            raise UserError(_(
                "%s does not work in the company this belongs to.",
                new_user.name))
        if new_user in seat.step_id.seat_ids.mapped('acting_user_id'):
            raise UserError(_(
                "%s is already on this step.", new_user.name))
        self._lock(request)
        old = seat.acting_user_id
        seat.write({'status': 'reassigned'})
        replacement = self.env['biz.approval.request.seat'].create({
            'step_id': seat.step_id.id,
            'company_id': request.company_id.id,
            'key': 'u%s' % new_user.id,
            'user_id': new_user.id,
            'acting_user_id': new_user.id,
            'resolved_via': _("Moved here by %s", self.env.user.name),
            'status': 'open',
        })
        self.env['biz.approval.decision'].create({
            'request_id': request.id,
            'company_id': request.company_id.id,
            'step_id': seat.step_id.id,
            'seat_id': seat.id,
            'step_key': seat.step_id.key,
            'action': 'reassign',
            'reason': reason,
            'source_revision': request.source_revision,
        })
        request._bump_lock()
        self.env['biz.approval.event']._log(
            'reassigned',
            _("\"%(step)s\" on \"%(what)s\" moved from %(a)s to %(b)s",
              step=seat.step_id.title, what=request.title,
              a=old.name or '', b=new_user.name),
            company=request.company_id, request=request,
            payload={'seat_key': seat_key, 'reason': reason})
        self.env['biz.approval.outbox']._queue(
            'your_turn', new_user, request,
            payload={'step_title': seat.step_id.title},
            dedupe='your_turn-%s-%s-%s' % (request.id, seat.step_id.id,
                                           new_user.id))
        return {'seat_id': replacement.id}

    @api.model
    def cancel(self, request, reason=None):
        request = self._as_request(request)
        if not (self._is_admin()
                or request.submitter_uid.id == self.env.uid):
            raise AccessError(_(
                "Only the person who sent this in can withdraw it."))
        if request.state not in _OPEN_STATES:
            raise UserError(_("This is already finished."))
        self._lock(request)
        request.seat_ids.filtered(lambda s: s.status == 'open').write(
            {'status': 'closed'})
        request.step_ids.filtered(lambda s: s.status == 'active').write(
            {'status': 'skipped'})
        request.write({'state': 'cancelled', 'current_step_key': False,
                       'closed_at': fields.Datetime.now(),
                       'return_note': reason or ''})
        request._bump_lock()
        self.env['biz.approval.decision'].create({
            'request_id': request.id,
            'company_id': request.company_id.id,
            'action': 'cancel', 'reason': reason or '',
            'source_revision': request.source_revision,
        })
        self.env['biz.approval.event']._log(
            'cancelled', _("\"%s\" was withdrawn", request.title),
            company=request.company_id, request=request)
        return self._request_payload(request)

    @api.model
    def repair(self, request):
        """Try again to find the people a stuck request could not find."""
        request = self._as_request(request)
        self._require_config()
        if request.state != 'blocked':
            raise UserError(_("This request is not stuck."))
        record = request._record()
        ctx = self._ctx_from_request(request)
        on_date = fields.Date.context_today(self)
        d = D.normalise(request.version_id.definition)
        by_key = {s['key']: s for s in d['steps']}
        still = ''
        for step in request.step_ids.filtered(
                lambda s: s.status == 'blocked'):
            spec = by_key.get(step.key)
            if not spec:
                continue
            people, issue = self._resolve_step_people(
                spec, ctx, request.company_id, on_date, record=record)
            if issue and issue['level'] == 'block':
                still = still or issue['msg']
                continue
            for person in people:
                self.env['biz.approval.request.seat'].create({
                    'step_id': step.id,
                    'company_id': request.company_id.id,
                    'key': 'u%s' % person['user_id'],
                    'user_id': person['user_id'],
                    'acting_user_id': person['user_id'],
                    'resolved_via': person.get('via') or '',
                    'backup_user_id': person.get('backup_user_id') or False,
                    'status': 'open',
                })
            step.write({'status': 'pending', 'block_reason': False})
        if still:
            request.write({'block_reason': still})
            return self._request_payload(request)
        request.write({'state': 'pending', 'block_reason': False})
        request._bump_lock()
        self._activate_next(request)
        self.env['biz.approval.event']._log(
            'step_activated', _("\"%s\" can go ahead again", request.title),
            company=request.company_id, request=request)
        return self._request_payload(request)

    def _ctx_from_request(self, request):
        """Rebuild the resolver's view of a request from its frozen facts —
        never from the record as it is today."""
        return {
            'company_id': request.company_id.id,
            'scope_keys': request.scope_keys or [],
            'scope_label': request.scope_label or '',
            'kind_key': request.kind_key or ANY_KIND,
            'facts': request.facts or {},
            'amount': request.amount,
            'currency_id': request.currency_id.id,
            'maker_uids': request.maker_uids or [],
            'submitter_uid': request.submitter_uid.id,
            'subject_uids': request.subject_uids or [],
            'process_key': request.process_id.key,
        }

    # ============================================================ escalation
    @api.model
    def escalate_cron(self):
        """Remind, then escalate, then — only if configured — hand to a
        backup. This never approves anything."""
        now = fields.Datetime.now()
        steps = self.env['biz.approval.request.step'].sudo().search([
            ('status', '=', 'active'), ('due_at', '!=', False),
            ('due_at', '<', now),
        ])
        for step in steps:
            request = step.request_id
            if request.state not in _OPEN_STATES:
                continue
            sg = D.normalise(request.version_id.definition)['safeguards']
            late = sg.get('late') or {}
            remind_after = step.due_at + timedelta(
                days=int(late.get('remind_days') or 1))
            escalate_after = step.due_at + timedelta(
                days=int(late.get('escalate_days') or 2))
            if now >= remind_after and not step.reminded_at:
                for seat in step.seat_ids.filtered(
                        lambda s: s.status == 'open'):
                    self.env['biz.approval.outbox']._queue(
                        'reminder', seat.acting_user_id, request,
                        payload={'step_title': step.title},
                        dedupe='reminder-%s-%s' % (step.id,
                                                   seat.acting_user_id.id))
                step.sudo().write({'reminded_at': now})
                self.env['biz.approval.event']._log(
                    'reminded',
                    _("A reminder went out for \"%(step)s\" on \"%(what)s\"",
                      step=step.title, what=request.title),
                    company=request.company_id, request=request)
            if now >= escalate_after and not step.escalated_at:
                owner = request.version_id.workflow_id.owner_user_id
                if owner:
                    self.env['biz.approval.outbox']._queue(
                        'escalation', owner, request,
                        payload={'step_title': step.title},
                        dedupe='escalation-%s' % step.id)
                step.sudo().write({'escalated_at': now})
                self.env['biz.approval.event']._log(
                    'escalated',
                    _("\"%(step)s\" on \"%(what)s\" is overdue and was passed "
                      "up", step=step.title, what=request.title),
                    company=request.company_id, request=request)
                if late.get('reassign'):
                    self._late_reassign(request, step)
        return True

    def _late_reassign(self, request, step):
        for seat in step.seat_ids.filtered(
                lambda s: s.status == 'open' and s.backup_user_id):
            backup = seat.backup_user_id
            if not backup.active:
                continue
            seat.sudo().write({'status': 'reassigned'})
            self.env['biz.approval.request.seat'].sudo().create({
                'step_id': step.id,
                'company_id': request.company_id.id,
                'key': 'u%s' % backup.id,
                'user_id': backup.id,
                'acting_user_id': backup.id,
                'resolved_via': _('Backup, because this was late'),
                'status': 'open',
            })
            self.env['biz.approval.decision'].sudo().create({
                'request_id': request.id,
                'company_id': request.company_id.id,
                'step_id': step.id, 'seat_id': seat.id,
                'step_key': step.key, 'action': 'reassign',
                'reason': _('Late: passed to the backup, as set up.'),
                'source_revision': request.source_revision,
            })
            self.env['biz.approval.event']._log(
                'reassigned',
                _("\"%(step)s\" on \"%(what)s\" was passed to %(who)s because "
                  "it was late", step=step.title, what=request.title,
                  who=backup.name),
                company=request.company_id, request=request)
            self.env['biz.approval.outbox']._queue(
                'your_turn', backup, request,
                payload={'step_title': step.title},
                dedupe='your_turn-%s-%s-%s' % (request.id, step.id, backup.id))

    # ============================================================= read side
    @api.model
    def list_requests(self, filters=None, limit=80, offset=0):
        """Requests this user may see. The record rules do the narrowing."""
        filters = filters or {}
        domain = []
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('mine'):
            domain += ['|', ('seat_ids.acting_user_id', '=', self.env.uid),
                       ('submitter_uid', '=', self.env.uid)]
        if filters.get('process_key'):
            domain.append(('process_id.key', '=', filters['process_key']))
        rows = self.env['biz.approval.request'].search(
            domain, limit=limit, offset=offset)
        return [self._request_payload(r, light=True) for r in rows]

    @api.model
    def get_request(self, request_id):
        request = self._as_request(request_id)
        return self._request_payload(request)

    def _request_payload(self, request, light=False):
        payload = {
            'id': request.id,
            'title': request.title,
            'state': request.state,
            'state_label': dict(
                request._fields['state'].selection).get(request.state, ''),
            'process': request.process_id.name,
            'workflow': request.version_id.workflow_id.name,
            'version': request.version_id.revision,
            'company_id': request.company_id.id,
            'lock_revision': request.lock_revision,
            'current_step_key': request.current_step_key,
            'due_at': fields.Datetime.to_string(request.due_at) or '',
            'submitted_at': fields.Datetime.to_string(
                request.submitted_at) or '',
            'block_reason': request.block_reason or '',
            'res_model': request.res_model,
            'res_id': request.res_id,
        }
        if light:
            return payload
        payload['steps'] = [{
            'key': s.key, 'title': s.title, 'kind': s.kind,
            'included': s.included, 'reason': s.include_reason,
            'status': s.status, 'block_reason': s.block_reason or '',
            'due_at': fields.Datetime.to_string(s.due_at) or '',
            'seats': [{
                'key': seat.key, 'user_id': seat.user_id.id,
                'name': seat.user_id.name,
                'acting_user_id': seat.acting_user_id.id,
                'acting_name': seat.acting_user_id.name,
                'via': seat.resolved_via or '', 'status': seat.status,
            } for seat in s.seat_ids],
        } for s in request.step_ids.sorted('sequence')]
        payload['decisions'] = [{
            'user': d.user_id.name, 'action': d.action,
            'step_key': d.step_key, 'reason': d.reason or '',
            'stamp': fields.Datetime.to_string(d.stamp),
            'exception': bool(d.exception_grant_id),
        } for d in request.decision_ids.sorted('stamp')]
        payload['confirmations'] = request.confirmations or []
        return payload
