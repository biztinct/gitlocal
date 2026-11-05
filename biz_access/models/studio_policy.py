"""Server enforcement for the explicit Studio resource catalogue.

Native ACLs and record rules remain authoritative. Source policies are ORed,
then intersected with those native restrictions and the company boundary.
Field restrictions are checked by Odoo's own field-access hooks; masking means
no raw value is readable until a reasoned, audited reveal of one record.
"""
import copy
import functools
from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from .access_common import implied_closure
from .studio_catalogue import RESOURCES, ACTIONS
from .studio_models import STUDIO

REVEAL = object()
CREATING = object()
# PDR S4 — RESOURCES is a static, module-level catalogue (never mutated at
# runtime), so the union of its field names is fixed at import.
_CATALOGUE_FIELD_NAMES = frozenset(name for spec in RESOURCES.values() for name in spec['fields'])


class StudioPolicyService(models.AbstractModel):
    _inherit = 'pb.access'

    def _studio_sources(self, user, model):
        # Never search the protected business resource while collecting policy.
        # Baseline permission grants stay independent of assigned profiles.
        assignments = user.sudo()._pb_access_sources()
        sources = []
        base_ids = user.sudo().pb_access_baseline if user.sudo().pb_access_ready else user.sudo().group_ids.ids
        baseline = self.env['res.groups'].sudo().browse(base_ids or []).exists()
        if baseline:
            sources.append({'name': _('Direct / existing permissions'), 'role_id': 0,
                            'group_ids': implied_closure(baseline).ids, 'policy': None, 'source': 'baseline'})
        for row in assignments:
            groups = row._groups()
            if not groups:
                continue
            policy = (row.profile_id.sudo().studio_policy or {}).get(model)
            sources.append({'name': row.profile_id.name, 'role_id': row.profile_id.id,
                            'group_ids': implied_closure(groups).ids, 'policy': policy, 'source': row.source})
        return sources

    @tools.ormcache('self.env.uid', 'model', 'revision', 'today')
    def _studio_cached_sources(self, model, revision, today):
        return self._studio_sources(self.env.user, model)

    def _studio_policy_sources(self, model):
        if model not in RESOURCES or self.env.uid == 1 or self.env.context.get('install_mode'):
            return []
        user = self.env.user.sudo()
        sources = self._studio_cached_sources(model, user.pb_access_revision, fields.Date.today())
        return sources if any(s['policy'] is not None for s in sources) else []

    @tools.ormcache('model', 'mode')
    def _studio_acl_groups(self, model, mode):
        # Asked once per field of every fetched record, so it must not query.
        # Any ir.model.access create/write/unlink clears this cache.
        acls = self.env['ir.model.access'].sudo().search([
            ('model_id.model', '=', model), ('active', '=', True), ('perm_%s' % mode, '=', True)])
        return tuple(a.group_id.id for a in acls)

    def _studio_acl_sources(self, model, operation, sources):
        mode = 'read' if operation in ('export', 'download', 'reveal') else 'write' if operation in ('archive', 'reassign', 'approve') else operation
        groups = self._studio_acl_groups(model, mode)
        return [s for s in sources if any(not g or g in s['group_ids'] for g in groups)]

    def _studio_team(self, user):
        # Team means the employee hierarchy, not everybody with the same role.
        Employee = self.env['hr.employee'].with_user(1)
        roots = Employee.search([('user_id', '=', user.id), ('company_id', 'in', user.sudo().company_ids.ids)])
        children = Employee.search([('id', 'child_of', roots.ids), ('company_id', 'in', user.sudo().company_ids.ids)]) if roots else Employee
        return sorted(set(children.user_id.ids) | {user.id})

    def _studio_rule_domain(self, model, operation, rule, user):
        spec = RESOURCES[model]
        scope = rule.get(operation, 'none')
        if scope == 'none':
            return Domain.FALSE
        domain = Domain.TRUE
        if scope in ('own', 'team'):
            ids = [user.id] if scope == 'own' else self._studio_team(user)
            domain &= Domain(spec['owner'], 'in', ids)
        conditions = []
        if rule.get('department_ids') and spec.get('department'):
            conditions.append(Domain(spec['department'], 'in', rule['department_ids']))
        if rule.get('states') and spec.get('state'):
            conditions.append(Domain(spec['state'], 'in', rule['states']))
        if conditions:
            domain &= Domain.OR(conditions) if rule.get('match') == 'any' else Domain.AND(conditions)
        if operation in ('write', 'unlink') and rule.get('write_states') and spec.get('state'):
            domain &= Domain(spec['state'], 'in', rule['write_states'])
        return domain

    def _studio_domain(self, model, operation):
        sources = self._studio_policy_sources(model)
        if not sources:
            return Domain.TRUE
        sources = self._studio_acl_sources(model, operation, sources)
        domain = Domain.OR([self._studio_rule_domain(model, operation, s['policy'], self.env.user)
                            if s['policy'] is not None else Domain.TRUE for s in sources])
        if 'company_id' in self.env[model]._fields:
            domain &= Domain('company_id', 'in', self.env.companies.ids)
        return domain

    def _studio_matching_permission(self, model, operation, candidates, record_ids=None):
        if not candidates:
            return False
        if not record_ids:
            return True
        domain = Domain.OR([self._studio_rule_domain(model, operation, source['policy'], self.env.user)
                            if source['policy'] is not None else Domain.TRUE for source in candidates])
        if 'company_id' in self.env[model]._fields:
            domain &= Domain('company_id', 'in', self.env.companies.ids)
        records = self.env[model].with_user(1).browse(record_ids).exists()
        return len(records.filtered_domain(domain)) == len(set(record_ids))

    def _studio_field_allowed(self, model, name, operation, record_ids=None):
        sources = self._studio_policy_sources(model)
        if not sources:
            return True
        action = 'create' if operation == 'create' else 'write' if operation == 'write' else 'read'
        candidates = []
        for source in self._studio_acl_sources(model, action, sources):
            rule = source['policy']
            if rule is None:
                candidates.append(source)
                continue
            if rule.get(action, 'none') == 'none':
                continue
            value = rule.get('fields', {}).get(name, 'edit')
            if operation == 'create' and name in RESOURCES[model]['fields']:
                allowed = name in rule.get('create_fields', [])
            else:
                allowed = value == 'edit' or (operation == 'read' and value == 'view')
            if allowed:
                candidates.append(source)
        return self._studio_matching_permission(model, action, candidates, record_ids)

    def _studio_action_allowed(self, model, action, record_ids=None):
        sources = self._studio_policy_sources(model)
        if not sources:
            return True
        candidates = [s for s in self._studio_acl_sources(model, action, sources)
                      if s['policy'] is None or s['policy'].get(action, False)]
        operation = 'read' if action in ('export', 'download', 'reveal') else 'write'
        return self._studio_matching_permission(model, operation, candidates, record_ids)

    @api.model
    def studio_explain(self, workspace, user_id, model, record_id=False, action='read', field_name=False, without_profile=False):
        self._studio_scope(workspace, manage=False)
        if user_id != self.env.uid:
            self._studio_scope(workspace)
        if model not in RESOURCES or RESOURCES[model]['workspace'] != workspace or model not in self.env or action not in ACTIONS:
            raise UserError(_('Choose a supported resource and action.'))
        user = self._internal_user(user_id)
        if self.env.company not in user.sudo().company_ids:
            raise AccessError(_('Choose a person in this company.'))
        Access = self.with_user(user).with_context(allowed_company_ids=[self.env.company.id])
        Model = self.env[model].with_user(user).with_context(allowed_company_ids=[self.env.company.id])
        sources = Access._studio_sources(user, model)
        if without_profile:
            sources = [s for s in sources if not s['source'].startswith('package:')]
        matched = Access._studio_acl_sources(model, action, sources)
        native = Model.browse().has_access(action)
        record = Model.browse(int(record_id)).exists() if record_id else Model
        if record_id and (not record or not self.env[model].with_user(1).browse(record.id).filtered_domain([('company_id', '=', self.env.company.id)])):
            raise AccessError(_('Choose a record in this company.'))
        rows = []
        for source in matched:
            rule = source['policy']
            scope = rule.get(action, 'none') if rule is not None else 'application'
            passes = scope != 'none'
            if record and rule is not None:
                passes = bool(record.with_user(1).filtered_domain(Access._studio_rule_domain(model, action, rule, user)))
            field_mode = (rule or {}).get('fields', {}).get(field_name, 'edit') if field_name else ''
            if field_name and rule is not None:
                if action == 'create' and field_name in RESOURCES[model]['fields']:
                    passes = passes and field_name in rule.get('create_fields', [])
                else:
                    passes = passes and (field_mode == 'edit' or action == 'read' and field_mode == 'view')
            rows.append({'name': source['name'], 'source': source['source'], 'scope': scope,
                'field': field_mode, 'matches': passes, 'rule': rule or {}, 'role_id': source['role_id']})
        allowed = native and any(r['matches'] for r in rows)
        # The actual evaluator is the final answer; a simulation never adds access.
        if record:
            allowed = allowed and record.has_access(action)
        if field_name:
            if field_name not in Model._fields:
                raise UserError(_('Choose an existing field.'))
            target = (record or Model).with_context(_pb_studio_creating=CREATING) if action == 'create' else (record or Model)
            allowed = allowed and target._has_field_access(Model._fields[field_name], 'write' if action in ('create', 'write') else 'read')
        return {'user': user.name, 'resource': RESOURCES[model]['label'], 'action': action,
            'allowed': bool(allowed), 'sources': rows, 'company': self.env.company.name,
            'simulation': bool(without_profile),
            'note': _('Application ACLs, company and record rules are also checked. Choose a record to verify its ownership and conditions.')}

    @api.model
    def studio_reveal(self, model, record_id, field_name, reason):
        self._require()
        reason = self._studio_reason(reason)
        if model not in RESOURCES or field_name not in RESOURCES[model].get('sensitive', []):
            raise AccessError(_('This field does not support a reasoned reveal.'))
        Record = self.env[model].browse(int(record_id)).exists()
        Record.check_access('read')
        sources = self._studio_acl_sources(model, 'reveal', self._studio_policy_sources(model))
        if not any(s['policy'] is not None and s['policy'].get('reveal') and
                   s['policy'].get('fields', {}).get(field_name) == 'masked' and
                   Record.with_user(1).filtered_domain(self._studio_rule_domain(model, 'read', s['policy'], self.env.user)) for s in sources):
            raise AccessError(_('Your access does not allow revealing this field.'))
        field = Record._fields[field_name]
        if field.groups and not self.env.user.has_groups(field.groups):
            raise AccessError(_('The application restricts this field.'))
        value = Record.with_context(_pb_reveal=REVEAL, _pb_reveal_field=field_name)[field_name]
        event = self._studio_event(RESOURCES[model]['workspace'], _('Sensitive value revealed'), reason,
            {'model': model, 'record_id': Record.id, 'field': field_name}, self.env.user)
        return {'value': value, 'receipt': event.id}


class StudioRecordRules(models.Model):
    _inherit = 'ir.rule'
    def _compute_domain(self, model_name, mode='read'):
        domain = super()._compute_domain(model_name, mode)
        if model_name in RESOURCES and not self.env.su:
            domain &= self.env['pb.access']._studio_domain(model_name, mode)
        return domain


class StudioResourceGuard(models.AbstractModel):
    _inherit = 'base'

    def _studio_guarded(self):
        return self._name in RESOURCES and bool(self.env['pb.access']._studio_policy_sources(self._name))

    def _studio_attribute_check(self, name):
        # Explicitly protected scalar fields must remain protected when an
        # application facade uses sudo for labels, including values already in
        # Odoo's shared field cache. Do not alter sudo itself: the ORM needs it
        # to compile recursive native record rules safely.
        if self._name not in RESOURCES or name not in RESOURCES[self._name]['fields'] or self.env.uid == 1:
            return
        if self.env.context.get('_pb_reveal') is REVEAL and self.env.context.get('_pb_reveal_field') == name:
            return
        ids = self.ids if self and all(isinstance(i, int) for i in self.ids) else None
        if not self.env['pb.access']._studio_field_allowed(self._name, name, 'read', ids):
            raise AccessError(_('This field is hidden or outside your permitted records.'))

    def __getattribute__(self, name):
        # Only the small, explicit resource/field catalogue takes this path.
        # Other models and non-field attributes use the unchanged ORM.
        # PDR S4 — this hook runs on EVERY attribute of EVERY record, so a
        # name no catalogue field carries leaves on one set lookup.
        if name not in _CATALOGUE_FIELD_NAMES:
            return super().__getattribute__(name)
        if not name.startswith('_') and name not in ('env', 'ids', 'id'):
            model = object.__getattribute__(self, '_name')
            if model in RESOURCES and name in RESOURCES[model]['fields']:
                object.__getattribute__(self, '_studio_attribute_check')(name)
        return super().__getattribute__(name)

    def __getitem__(self, key):
        if isinstance(key, str):
            self._studio_attribute_check(key)
        return super().__getitem__(key)

    def _has_field_access(self, field, operation):
        if not super()._has_field_access(field, operation):
            return False
        if self._name not in RESOURCES or self.env.context.get('_pb_reveal') is REVEAL and self.env.context.get('_pb_reveal_field') == field.name:
            return True
        if operation == 'read' and not self.env.su and field.name not in RESOURCES[self._name]['fields']:
            # A field outside the catalogue has no field rule: its answer is the
            # record scope alone, which every non-sudo fetch and search already
            # enforces through _check_access and the record-rule domain. Sudo
            # keeps the full check (no record rules run there).
            return True
        return self.env['pb.access']._studio_field_allowed(self._name, field.name, 'create' if self.env.context.get('_pb_studio_creating') is CREATING and operation == 'write' else operation, self.ids if self and all(isinstance(i, int) for i in self.ids) else None)

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result or not self._studio_guarded():
            return result
        domain = self.env['pb.access']._studio_domain(self._name, operation)
        denied = self - self.with_user(1).filtered_domain(domain) if self else self
        if domain.is_false() or denied:
            return denied, lambda: AccessError(_('Access Studio does not allow this operation for these records.'))
        return None

    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        if self._studio_guarded():
            domain = Domain(domain) & self.env['pb.access']._studio_domain(self._name, 'read')
        return super()._search(domain, offset, limit, order, active_test=active_test, bypass_access=bypass_access)

    def _read_format(self, fnames, load='_classic_read'):
        if self._studio_guarded():
            self.sudo(False).check_access('read')
            for name in fnames:
                self._check_field_access(self._fields[name], 'read')
        return super()._read_format(fnames, load)

    @api.model_create_multi
    def create(self, vals_list):
        guarded = self._studio_guarded()
        if guarded:
            access = self.env['pb.access']
            for vals in vals_list:
                for name in vals:
                    if not access._studio_field_allowed(self._name, name, 'create'):
                        raise AccessError(_('This field cannot be supplied when creating this record: %s', name))
        records = super(StudioResourceGuard, self.with_context(_pb_studio_creating=CREATING) if guarded else self).create(vals_list)
        if guarded:
            # Includes defaulted ownership/company values and cannot be bypassed
            # by omitting a field. A rejection rolls back the whole transaction.
            records.sudo(False).check_access('create')
        return records

    def write(self, vals):
        if self._studio_guarded():
            access = self.env['pb.access']
            self.sudo(False).check_access('write')
            for name in vals:
                if not access._studio_field_allowed(self._name, name, 'write', self.ids):
                    raise AccessError(_('This field is read-only or hidden: %s', name))
            spec = RESOURCES[self._name]
            checks = {'archive': 'active' in vals and vals['active'] is False,
                      'reassign': spec['owner'].split('.')[0] in vals,
                      'approve': vals.get(spec.get('state')) in ('done', 'approved', 'agreed', 'paid', 'manager_ok', 'hr_ok') or vals.get('request_state') == 'agreed'}
            for action, applies in checks.items():
                if applies and not access._studio_action_allowed(self._name, action, self.ids):
                    raise AccessError(_('Your role does not allow this business action: %s', action))
        return super().write(vals)

    def unlink(self):
        if self._studio_guarded():
            self.sudo(False).check_access('unlink')
        return super().unlink()

    def export_data(self, fields_to_export):
        if self._name in RESOURCES and not self.env['pb.access']._studio_action_allowed(self._name, 'export', self.ids):
            raise AccessError(_('Export is not allowed by your access policy.'))
        return super().export_data(fields_to_export)


class StudioAttachmentGuard(models.Model):
    _inherit = 'ir.attachment'

    def _studio_download_check(self):
        for attachment in self.with_user(1):
            if attachment.res_model not in RESOURCES or not attachment.res_id:
                continue
            Access = self.env['pb.access']
            if not Access._studio_policy_sources(attachment.res_model):
                continue
            record = self.env[attachment.res_model].sudo(False).browse(attachment.res_id)
            record.check_access('read')
            if not Access._studio_action_allowed(attachment.res_model, 'download', record.ids):
                raise AccessError(_('Downloading attachments is not allowed by your access policy.'))

    def _to_http_stream(self):
        self._studio_download_check()
        return super()._to_http_stream()

    def _read_format(self, fnames, load='_classic_read'):
        if {'raw', 'datas', 'db_datas'} & set(fnames):
            self._studio_download_check()
        return super()._read_format(fnames, load)
