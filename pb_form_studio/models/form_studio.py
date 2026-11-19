# -*- coding: utf-8 -*-
"""`pb.form.studio` — the Form builder facade (FS-1).

Two audiences, two sets of methods.

STUDIO methods (administrator only, R2 — `base.group_system`, checked on the
server in every one of them): `can_edit`, `get_studio`, `create_field`,
`update_field`, `delete_field`, `field_references`, `save_draft`,
`discard_draft`, `publish`, `library`, `dev_sample`.

HOST methods (anyone; they only ever hand out what the caller may already
read, and only write what the caller may already write): `render`,
`write_values`, `fields_for`, `copy_field_names`, and the Python helpers
`_pbfs_values_for` and `_pbfs_sync_native_view`.

Extension hooks for other modules (`_inherit = 'pb.form.studio'`):
`_pbfs_hosts`, `_pbfs_locked_fields`, `_pbfs_link_targets`,
`_pbfs_reference_finders`. The full contract is written out in
docs/handovers/formstudio/FS1_REPORT.md, "THE HOST CONTRACT".
"""
import base64
import csv
import io
import logging
import re
import unicodedata
from datetime import timedelta

from markupsafe import Markup
from psycopg2 import errors as pg_errors

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL

from .ir_model_fields import PREFIX

_logger = logging.getLogger(__name__)

ADMIN_GROUP = 'base.group_system'
HR_GROUP = 'hr.group_hr_user'

#: Caps (handover "Safety rails"). Plain refusals name them in screen words.
MAX_PER_MODEL = 60
MAX_PER_SECTION = 30
MAX_LABEL = 60
MAX_OPTIONS = 50
MAX_FILE_BYTES = 10 * 1024 * 1024

#: The DDL (ALTER TABLE ADD/DROP COLUMN) waits at most this long for a lock.
#: A pay-run chunk holding the table must make the Form builder give up fast,
#: never make every reader of the table queue behind it.
LOCK_TIMEOUT = '5s'
#: A draft pay run whose payslips were written this recently is "being worked
#: out" (the compute is client-driven chunks with nothing marking it — see
#: report V4 / FS_HOST_FACTS §E).
BUSY_MINUTES = 3

#: type key → (ttype, icon). Labels are given by `_pbfs_types` (translated).
TYPE_TTYPE = {
    'text': 'char', 'longtext': 'text', 'integer': 'integer', 'number': 'float',
    'money': 'monetary', 'bool': 'boolean', 'date': 'date', 'select': 'selection',
    'm2o': 'many2one', 'file': 'binary',
}
TTYPE_KIND = {v: k for k, v in TYPE_TTYPE.items()}
TTYPE_KIND.update({'datetime': 'date', 'many2many': 'readonly', 'one2many': 'readonly',
                   'html': 'longtext'})
FORMULA_TTYPES = ('integer', 'float', 'monetary', 'boolean', 'date', 'selection')

#: Models a field may never be added to, whatever a host says.
FORBIDDEN_MODELS = {
    'res.users', 'res.groups', 'res.users.log', 'res.company', 'res.partner',
    'hr.payslip', 'hr.payslip.line', 'hr.payslip.input', 'hr.payslip.worked_days',
    'hr.employee.public', 'hr.version', 'hr.contract.history',
    # the engine's own bookkeeping
    'pb.form.field.meta', 'pb.form.layout', 'pb.form.layout.draft', 'pb.form.audit',
    'pb.form.native.view',
}
FORBIDDEN_PREFIXES = ('ir.', 'res.users', 'res.groups', 'account.', 'biz.access',
                      'pb.access', 'base.', 'bus.', 'mail.')

#: R14 — kinds of field an employee may change on My Payobook (everything the
#: engine can coerce safely). Money and files can be shown only.
PORTAL_EDIT_TTYPES = ('char', 'text', 'integer', 'float', 'date', 'selection', 'boolean',
                      'many2one')
PORTAL_KEYS = ('portal_show', 'portal_edit', 'portal_mode')
#: A transaction that has held a payslip write lock longer than this is stuck,
#: not a pay-run chunk: it no longer counts as "being worked out".
BUSY_LOCK_MINUTES = 10
#: A practice run left 'computing' stops counting after this long.
BUSY_PRACTICE_MINUTES = 15

#: m2o/m2m fields pointing at ir.model.fields that are NOT a reason to keep a
#: field: our own settings, the field's own pieces, defaults and history.
REF_SKIP = {
    ('pb.form.field.meta', 'field_id'), ('ir.model.fields.selection', 'field_id'),
    ('ir.default', 'field_id'), ('mail.tracking.value', 'field_id'),
    ('ir.model.fields', 'related_field_id'), ('ir.model.constraint', 'model'),
    ('hr.payslip.import.mapping', 'target_field_id'),   # has its own finder
}


def _slug(label):
    text = unicodedata.normalize('NFKD', label or '')
    text = text.replace('đ', 'd').replace('Đ', 'D')
    text = text.encode('ascii', 'ignore').decode('ascii').lower()
    text = re.sub(r'[^a-z0-9]+', '_', text).strip('_')
    return (text[:40].strip('_')) or 'field'


class PbFormStudio(models.AbstractModel):
    _name = 'pb.form.studio'
    _description = 'Form builder'

    # ================================================================ hooks
    @api.model
    def _pbfs_hosts(self):
        """Every screen that hosts custom fields. Extend with `super()`.

        `{host_key: {model, title, icon, sections, default_layout,
        standard_fields (alias std_fields), custom_section, country_field,
        country_view_field, portal,
        copy_custom, native_views, dev}}` — see THE HOST CONTRACT.
        """
        _ = self.env._
        return {
            'pbfs_sample': {
                'model': 'pb.form.sample',
                'title': _('Sample record'),
                'icon': 'user',
                'dev': True,
                'sections': [
                    {'id': 'about', 'title': _('About'), 'icon': 'user', 'tone': 'teal',
                     'kind': 'open'},
                    {'id': 'place', 'title': _('Where they work'), 'icon': 'mapPin',
                     'tone': 'blue', 'kind': 'open'},
                    {'id': 'pay', 'title': _('Pay'), 'icon': 'banknote', 'tone': 'green',
                     'kind': 'locked',
                     'note': _('Drawn by the screen itself from the contract and the pay '
                               'scheme. Fields cannot be placed here.')},
                    {'id': 'custom', 'title': _('Company details'), 'icon': 'sparkles',
                     'tone': 'brand', 'kind': 'open'},
                ],
                'default_layout': {'about': ['name', 'email', 'phone'],
                                   'place': ['city', 'country_id', 'date_start'],
                                   'custom': []},
                'standard_fields': ['name', 'email', 'phone', 'city', 'country_id',
                                    'date_start'],
                'custom_section': 'custom',
                'country_field': 'country_id',
                'country_view_field': 'country_id',
                'copy_custom': False,
                'native_views': [],
                # R14 — this screen's record type has a self-service page.
                'portal': True,
            },
        }

    @api.model
    def _pbfs_portal_locked(self, model):
        """`{field name: reason}` — may be SHOWN on My Payobook, never changed
        there by the employee. Extend with `super()` (R14 locked list)."""
        if model == 'pb.form.sample':
            return {'country_id': self.env._('Country of Work decides which fields apply.')}
        return {}

    @api.model
    def _pbfs_portal_hidden(self, model):
        """`{field name: reason}` — never shown on My Payobook (pay figures).
        Extend with `super()`."""
        return {}

    @api.model
    def _pbfs_locked_fields(self, model):
        """`{field name: reason}` — standard fields that cannot be hidden or
        moved out of their section. Extend with `super()`."""
        if model == 'pb.form.sample':
            return {'name': self.env._('Every record needs its name.')}
        return {}

    @api.model
    def _pbfs_link_targets(self):
        """`{model: label}` — what a "Link to a record" field may point at."""
        _ = self.env._
        return {
            'hr.employee': _('Employee'),
            'hr.department': _('Department'),
            'hr.job': _('Job position'),
            'res.company': _('Company'),
            'res.partner': _('Contact'),
            'res.country': _('Country'),
        }

    @api.model
    def _pbfs_reference_finders(self):
        """Method names, each `(model, field_name) -> [{kind, label, count,
        names}]`. A non-empty answer blocks a delete and shows as "Used by".
        Extend with `super() + ['_my_finder']`."""
        return ['_pbfs_refs_import_mappings', '_pbfs_refs_relations',
                '_pbfs_refs_views', '_pbfs_refs_filters', '_pbfs_refs_saved_views',
                '_pbfs_refs_automations', '_pbfs_refs_exports']

    # ============================================================== gates
    @api.model
    def _pbfs_is_admin(self):
        return self.env.su or self.env.user.has_group(ADMIN_GROUP)

    @api.model
    def _pbfs_check_admin(self):
        if not self._pbfs_is_admin():
            raise AccessError(self.env._('Only the administrator can change forms.'))

    @api.model
    def _pbfs_host(self, host_key):
        host = self._pbfs_hosts().get(host_key or '')
        if not host:
            raise UserError(self.env._('This screen cannot take custom fields.'))
        return host

    @api.model
    def _pbfs_model_forbidden(self, model):
        if not model or model in FORBIDDEN_MODELS or model.startswith(FORBIDDEN_PREFIXES):
            return True
        Model = self.env.get(model)
        if Model is None or Model._abstract or Model._transient or not Model._auto:
            return True
        # A model another model `_inherits` (res.partner → res.users,
        # hr.version → hr.employee) would push the field into that model too.
        for other in self.env.registry.values():
            if model in (other._inherits or {}):
                return True
        return False

    @api.model
    def _pbfs_host_models(self):
        return {h['model'] for h in self._pbfs_hosts().values()}

    @api.model
    def _pbfs_std_names(self, host):
        """The standard fields a host offers (`standard_fields`; the FS-1
        name `std_fields` is still read)."""
        return list(host.get('standard_fields') or host.get('std_fields') or [])

    # ================================================================ R14
    @api.model
    def _pbfs_portal_host(self, model):
        """(host key, host) of the first host of `model` with `portal: True`."""
        for key, host in self._pbfs_hosts().items():
            if host['model'] == model and host.get('portal'):
                return key, host
        return None, None

    @api.model
    def _pbfs_portal_rules(self, model, name):
        """What My Payobook may do with one field, and why not — in screen words.
        → {can_show, show_reason, can_edit, edit_reason}."""
        _ = self.env._
        Model = self.env[model]
        field = Model._fields.get(name)
        key, host = self._pbfs_portal_host(model)
        out = {'can_show': True, 'show_reason': '', 'can_edit': True, 'edit_reason': ''}
        if not host or not field:
            reason = _('This kind of record has no self-service page.')
            return {'can_show': False, 'show_reason': reason, 'can_edit': False, 'edit_reason': reason}
        if not name.startswith(PREFIX) and name not in self._pbfs_std_names(host):
            reason = _('This field is not offered on this screen.')
            return {'can_show': False, 'show_reason': reason, 'can_edit': False, 'edit_reason': reason}
        hidden = self._pbfs_portal_hidden(model)
        if name in hidden:
            return {'can_show': False, 'show_reason': hidden[name],
                    'can_edit': False, 'edit_reason': hidden[name]}
        locked = self._pbfs_portal_locked(model)
        if name in locked:
            out.update(can_edit=False, edit_reason=locked[name])
        elif field.type not in PORTAL_EDIT_TTYPES:
            out.update(can_edit=False, edit_reason=_('Money and files can be shown, not changed by the employee.'))
        elif field.type == 'many2one' and field.comodel_name not in self._pbfs_link_targets():
            out.update(can_edit=False, edit_reason=_('This link can be shown, not changed by the employee.'))
        elif not field.store or (field.compute and not field.inverse) or field.readonly:
            out.update(can_edit=False, edit_reason=_('This value is worked out by the system.'))
        return out

    @api.model
    def _pbfs_portal_desc(self, model, name, meta):
        """The two ticks + mode as the properties panel draws them, or None
        when the record type has no self-service page."""
        key, _host = self._pbfs_portal_host(model)
        if not key:
            return None
        rules = self._pbfs_portal_rules(model, name)
        return {'show': bool(meta and meta.portal_show), 'edit': bool(meta and meta.portal_edit),
                'mode': (meta.portal_mode if meta else 'approve') or 'approve', **rules}

    @api.model
    def _pbfs_ensure_meta(self, model, name):
        """The settings row of a field, made for a STANDARD field on first use
        (no field is created; the row only carries flags)."""
        meta = self._pbfs_meta(model, [name]).get(name)
        if meta:
            return meta
        row = self._pbfs_field_row(model, name)
        if not row:
            raise UserError(self.env._('This field is not offered on this screen.'))
        return self.env['pb.form.field.meta'].sudo().create({
            'field_id': row.id, 'custom': False, 'vis': 'all'})

    @api.model
    def _pbfs_set_portal(self, model, name, vals):
        """Validate and store the My Payobook ticks of one field (server-side
        refusal of anything the hooks forbid). → list of changed words."""
        _ = self.env._
        if not any(k in vals for k in PORTAL_KEYS):
            return []
        meta = self._pbfs_ensure_meta(model, name)
        rules = self._pbfs_portal_rules(model, name)
        show = bool(vals.get('portal_show', meta.portal_show))
        edit = bool(vals.get('portal_edit', meta.portal_edit))
        mode = vals.get('portal_mode', meta.portal_mode) or 'approve'
        if mode not in ('approve', 'instant'):
            raise UserError(_('Pick how a change by the employee is saved.'))
        if 'portal_show' in vals and not show:
            edit = False                    # unticking "shown" clears "can change"
        elif edit:
            show = True                     # a field you can change is a field you can see
        if show and not rules['can_show']:
            raise UserError(rules['show_reason'])
        if edit and not rules['can_edit']:
            raise UserError(rules['edit_reason'])
        new = {'portal_show': show, 'portal_edit': edit, 'portal_mode': mode}
        changed = {k: v for k, v in new.items() if meta[k] != v}
        if not changed:
            return []
        meta.write(changed)
        return [_('My Payobook')]

    @api.model
    def _pbfs_check_model(self, model):
        if self._pbfs_model_forbidden(model) or model not in self._pbfs_host_models():
            raise UserError(self.env._('Custom fields cannot be added to this kind of record.'))

    @api.model
    def _pbfs_busy(self):
        """Plain reason why fields cannot be added or removed right now, or ''.

        DATABASE-WIDE on purpose: adding or dropping a column changes a table
        every company in the database shares, and a pay run in company A holds
        that table exactly as one in company B does. Every signal is BOUNDED
        IN TIME, so a stale one (a crashed browser between two chunks, a
        practice run left "computing", a stuck transaction) can never block
        for longer than its window:
          1. another transaction writing payslips NOW — counted only while that
             transaction is younger than BUSY_LOCK_MINUTES;
          2. a draft run's draft/verify payslip written in the last
             BUSY_MINUTES (a browser-driven compute between two chunks);
          3. a practice run 'computing', written in the last BUSY_PRACTICE_MINUTES.
        """
        msg = self.env._('A pay run is being worked out right now. Try again in a few minutes.')
        cr = self.env.cr
        cr.execute("""
            SELECT 1 FROM pg_locks l
              JOIN pg_class c ON c.oid = l.relation
              JOIN pg_stat_activity a ON a.pid = l.pid
             WHERE c.relname IN ('hr_payslip', 'hr_payslip_line')
               -- pg_locks covers the whole server, and databases copied from one
               -- template share table oids: without this, a pay run in ANOTHER
               -- database (another tenant) would block this one.
               AND l.database = (SELECT oid FROM pg_database WHERE datname = current_database())
               AND l.mode = 'RowExclusiveLock' AND l.granted
               AND l.pid <> pg_backend_pid()
               AND a.xact_start > now() - make_interval(mins => %s)
             LIMIT 1""", [BUSY_LOCK_MINUTES])
        if cr.fetchone():
            return msg
        if 'hr.payslip' in self.env and 'hr.payslip.run' in self.env:
            since = fields.Datetime.now() - timedelta(minutes=BUSY_MINUTES)
            Slip = self.env['hr.payslip'].sudo().with_context(active_test=False)
            if Slip.search_count([('state', 'in', ('draft', 'verify')),
                                  ('payslip_run_id.state', '=', 'draft'),
                                  ('write_date', '>=', since)], limit=1):
                return msg
        if 'hr.formula.shadow.run' in self.env:
            since = fields.Datetime.now() - timedelta(minutes=BUSY_PRACTICE_MINUTES)
            if self.env['hr.formula.shadow.run'].sudo().search_count(
                    [('state', '=', 'computing'), ('write_date', '>=', since)], limit=1):
                return msg
        return ''

    @api.model
    def _pbfs_check_busy(self):
        reason = self._pbfs_busy()
        if reason:
            raise UserError(reason)

    # ============================================================ helpers
    @api.model
    def _pbfs_types(self):
        _ = self.env._
        return [
            {'key': 'text', 'label': _('Text'), 'icon': 'type', 'sub': _('short, one line')},
            {'key': 'longtext', 'label': _('Long text'), 'icon': 'alignLeft', 'sub': _('notes')},
            {'key': 'integer', 'label': _('Whole number'), 'icon': 'hash', 'sub': _('0, 1, 2…')},
            {'key': 'number', 'label': _('Decimal'), 'icon': 'percent', 'sub': _('12.5')},
            {'key': 'money', 'label': _('Money'), 'icon': 'banknote',
             'sub': _('in the company money')},
            {'key': 'bool', 'label': _('Yes / No'), 'icon': 'toggle', 'sub': _('tick box')},
            {'key': 'date', 'label': _('Date'), 'icon': 'calendar', 'sub': _('a day')},
            {'key': 'select', 'label': _('Choice list'), 'icon': 'list', 'sub': _('pick one')},
            {'key': 'm2o', 'label': _('Link to a record'), 'icon': 'link',
             'sub': _('employee, department…')},
            {'key': 'file', 'label': _('File'), 'icon': 'paperclip', 'sub': _('PDF, image')},
        ]

    @api.model
    def _pbfs_type_label(self, kind):
        for t in self._pbfs_types():
            if t['key'] == kind:
                return t['label']
        return kind

    @api.model
    def _pbfs_vis_label(self, vis):
        _ = self.env._
        return {'all': _('Everyone'), 'hr': _('HR staff and administrators'),
                'admin': _('Administrators only')}.get(vis, vis)

    @api.model
    def _pbfs_groups_for(self, vis):
        if vis == 'admin':
            return ADMIN_GROUP
        if vis == 'hr':
            if self.env.ref(HR_GROUP, raise_if_not_found=False):
                return '%s,%s' % (HR_GROUP, ADMIN_GROUP)
            return ADMIN_GROUP
        return False

    @api.model
    def _pbfs_langs(self):
        return [code for code, _n in self.env['res.lang'].get_installed()]

    @api.model
    def _pbfs_field_row(self, model, name):
        return self.env['ir.model.fields'].sudo().search(
            [('model', '=', model), ('name', '=', name)], limit=1)

    @api.model
    def _pbfs_meta(self, model, names=None):
        dom = [('model', '=', model)]
        if names is not None:
            dom.append(('name', 'in', list(names)))
        return {m.name: m for m in self.env['pb.form.field.meta'].sudo().search(dom)}

    @api.model
    def _pbfs_custom_names(self, model):
        Model = self.env[model]
        return [n for n in self._pbfs_meta(model) if n.startswith(PREFIX) and n in Model._fields]

    @api.model
    def _pbfs_can_read_field(self, Model, field):
        return Model._has_field_access(field, 'read')

    @api.model
    def _pbfs_country_path(self, model):
        for host in self._pbfs_hosts().values():
            if host['model'] == model and host.get('country_field'):
                return host['country_field']
        return None

    @api.model
    def _pbfs_record_countries(self, records):
        """`{record id: res.country id or False}` — the record's Country of
        Work, read through the host's declared path. Read with elevated rights
        on purpose: WHERE a field applies is not a secret, and a reader who
        cannot follow the path must not be shown fields of every country."""
        path = self._pbfs_country_path(records._name)
        out = {}
        for rec in records:
            value = False
            if path:
                cur = rec.sudo()
                try:
                    for part in path.split('.'):
                        cur = cur[part]
                        if not cur:
                            break
                    if cur and getattr(cur, '_name', None) == 'res.country':
                        value = cur[:1].id
                except (KeyError, AccessError):
                    value = False
            out[rec.id] = value
        return out

    @api.model
    def _pbfs_applies(self, meta, country_id):
        """R10: a field limited to some countries applies only where the
        record's Country of Work is one of them; a record with no country
        recorded gets only all-countries fields."""
        if not meta or not meta.country_ids:
            return True
        return bool(country_id) and country_id in meta.country_ids.ids

    # ------------------------------------------------------------- values
    @api.model
    def _pbfs_display(self, record, field):
        _ = self.env._
        value = record[field.name]
        t = field.type
        if t == 'boolean':
            return _('Yes') if value else _('No')
        if value in (False, None, '') and t not in ('integer', 'float', 'monetary'):
            return ''
        if t == 'selection':
            return dict(field._description_selection(self.env)).get(value, value or '')
        if t == 'many2one':
            try:
                return value.display_name or ''
            except AccessError:
                return _('Restricted')
        if t == 'date':
            return tools.format_date(self.env, value)
        if t == 'datetime':
            return tools.format_datetime(self.env, value)
        if t == 'monetary':
            cur = record[field.currency_field] if field.currency_field else self.env.company.currency_id
            try:
                return tools.format_amount(self.env, value or 0.0, cur or self.env.company.currency_id)
            except Exception:                           # noqa: BLE001
                return '{:,.2f}'.format(value or 0.0)
        if t == 'integer':
            return '{:,}'.format(value or 0)
        if t == 'float':
            return ('{:,.4f}'.format(value or 0.0)).rstrip('0').rstrip('.')
        if t == 'binary':
            return _('File attached') if value else ''
        if t in ('many2many', 'one2many'):
            return ', '.join(value.mapped('display_name'))
        return str(value)

    @api.model
    def _pbfs_raw(self, record, field):
        value = record[field.name]
        if field.type == 'many2one':
            return value.id or False
        if field.type == 'binary':
            return bool(value)
        if field.type in ('date', 'datetime'):
            return fields.Date.to_string(value) if field.type == 'date' and value else (
                fields.Datetime.to_string(value) if value else False)
        if field.type in ('many2many', 'one2many'):
            return value.ids
        return value

    @api.model
    def _pbfs_options(self, field):
        if field.type != 'selection':
            return []
        return [{'value': v, 'label': l} for v, l in field._description_selection(self.env)]

    @api.model
    def _pbfs_describe(self, Model, name, meta=None, host=None, locked=None, counts=None):
        """The field as the Studio and the grids see it."""
        field = Model._fields[name]
        locked = locked if locked is not None else self._pbfs_locked_fields(Model._name)
        meta = meta if meta is not None else self._pbfs_meta(Model._name, [name]).get(name)
        custom = name.startswith(PREFIX) and bool(meta and meta.custom)
        desc = field.get_description(self.env, ['string', 'help', 'type', 'relation',
                                                'required', 'readonly'])
        kind = TTYPE_KIND.get(field.type, 'text')
        # A standard field may have a settings row too (R14 ticks only): its
        # visibility / required / list / countries stay the product's own.
        cmeta = meta if custom else None
        out = {
            'name': name,
            'label': desc.get('string') or name,
            'help': desc.get('help') or '',
            'type': field.type,
            'kind': kind,
            'type_label': self._pbfs_type_label(kind),
            'custom': custom,
            'std': not custom,
            'locked': name in locked,
            'reason': locked.get(name, ''),
            'vis': cmeta.vis if cmeta else 'all',
            'vis_label': self._pbfs_vis_label(cmeta.vis if cmeta else 'all'),
            'required': bool(cmeta.is_required) if cmeta else bool(field.required),
            'list_ok': bool(cmeta.list_ok) if cmeta else False,
            'formula_ok': bool(cmeta.formula_ok) if cmeta else False,
            'formula_possible': field.type in FORMULA_TTYPES,
            'countries': [{'id': c.id, 'name': c.name} for c in cmeta.country_ids] if cmeta else [],
            'portal': self._pbfs_portal_desc(Model._name, name, meta),
            'options': self._pbfs_options(field),
            'comodel': field.comodel_name if field.type == 'many2one' else False,
            'comodel_label': self._pbfs_link_targets().get(field.comodel_name, '')
            if field.type == 'many2one' else '',
        }
        if custom:
            # The other languages, so the properties panel can edit them.
            row = self._pbfs_field_row(Model._name, name)
            # A language with no translation of its own reads back the
            # English text; show it as empty so the box invites a translation
            # instead of pretending one exists.
            labels, helps = {}, {}
            en = row.with_context(lang='en_US')
            for lang in self._pbfs_langs():
                r = row.with_context(lang=lang)
                labels[lang] = r.field_description or ''
                helps[lang] = r.help or ''
                if lang != 'en_US':
                    if labels[lang] == (en.field_description or ''):
                        labels[lang] = ''
                    if helps[lang] == (en.help or ''):
                        helps[lang] = ''
            out['labels'] = labels
            out['helps'] = helps
            if counts is not None:
                out['filled'] = counts.get(name, 0)
        return out

    @api.model
    def _pbfs_filled_counts(self, model, names):
        Model = self.env[model].sudo().with_context(active_test=False)
        out = {}
        for name in names:
            field = Model._fields.get(name)
            if not field:
                continue
            dom = [(name, '=', True)] if field.type == 'boolean' else [(name, '!=', False)]
            out[name] = Model.search_count(dom)
        out['__total__'] = Model.search_count([])
        return out

    # ============================================================ layout
    @api.model
    def _pbfs_layout(self, host_key, company=None):
        company = company or self.env.company
        return self.env['pb.form.layout'].sudo().search(
            [('host_key', '=', host_key), ('company_id', '=', company.id)], limit=1)

    @api.model
    def _pbfs_effective(self, host_key, stored=None, company=None):
        """The full, ordered section list for a host — host order, stored
        placement, every fallback applied. Never loses a field: anything in a
        section that no longer exists (or is locked) moves to the host's
        custom section."""
        host = self._pbfs_host(host_key)
        Model = self.env[host['model']]
        if stored is None:
            layout = self._pbfs_layout(host_key, company)
            stored = layout.sections if layout else None
        locked = self._pbfs_locked_fields(host['model'])
        open_ids = [s['id'] for s in host['sections'] if s['kind'] == 'open']
        custom_id = host.get('custom_section') if host.get('custom_section') in open_ids \
            else (open_ids[-1] if open_ids else None)
        placeable = set(self._pbfs_std_names(host)) | set(self._pbfs_custom_names(host['model']))
        placeable = {n for n in placeable if n in Model._fields}

        placed = {sid: [] for sid in open_ids}
        if stored is None:
            source = [{'id': sid, 'fields': list((host.get('default_layout') or {}).get(sid, []))}
                      for sid in open_ids]
        else:
            source = stored or []
        seen = set()
        for sec in source:
            sid = sec.get('id') if isinstance(sec, dict) else None
            names = sec.get('fields') if isinstance(sec, dict) else None
            target = sid if sid in placed else custom_id
            for name in names or []:
                if isinstance(name, dict):
                    name = name.get('name')
                if not isinstance(name, str) or name in seen or name not in placeable:
                    continue
                if target is None:
                    continue
                seen.add(name)
                placed[target].append(name)
        # Locked standard fields always stay on the screen, in their home.
        default = host.get('default_layout') or {}
        for name in locked:
            if name in seen or name not in placeable:
                continue
            home = next((sid for sid, names in default.items() if name in names), custom_id)
            if home in placed:
                placed[home].insert(0, name)
                seen.add(name)
        out = []
        for sec in host['sections']:
            item = dict(sec)
            item['fields'] = placed.get(sec['id'], []) if sec['kind'] == 'open' else []
            out.append(item)
        return out

    @api.model
    def _pbfs_stored_from(self, sections):
        return [{'id': s['id'], 'fields': list(s['fields'])}
                for s in sections if s.get('kind') == 'open']

    # ============================================================ studio
    @api.model
    def can_edit(self, host_key):
        """Cheap gate for the wand button: never raises."""
        try:
            return bool(self._pbfs_is_admin() and self._pbfs_hosts().get(host_key))
        except Exception:                               # noqa: BLE001
            return False

    @api.model
    def get_studio(self, host_key):
        self._pbfs_check_admin()
        host = self._pbfs_host(host_key)
        model = host['model']
        Model = self.env[model]
        layout = self._pbfs_layout(host_key)
        sections = self._pbfs_effective(host_key)
        draft = self.env['pb.form.layout.draft'].sudo().search([
            ('host_key', '=', host_key), ('company_id', '=', self.env.company.id),
            ('user_id', '=', self.env.uid)], limit=1)
        version = layout.version if layout else 0
        names = set(self._pbfs_std_names(host)) | set(self._pbfs_custom_names(model))
        names = [n for n in names if n in Model._fields]
        metas = self._pbfs_meta(model)
        locked = self._pbfs_locked_fields(model)
        counts = self._pbfs_filled_counts(model, [n for n in names if n.startswith(PREFIX)])
        flds = {n: self._pbfs_describe(Model, n, meta=metas.get(n), locked=locked, counts=counts)
                for n in names}
        refs = {n: self.field_references(model, n) for n in names if n.startswith(PREFIX)}
        for n, r in refs.items():
            flds[n]['used_by'] = r
        targets = self._pbfs_link_targets()
        return {
            'host': {'key': host_key, 'model': model, 'title': host['title'],
                     'icon': host.get('icon') or 'fileText',
                     'custom_section': host.get('custom_section'),
                     'portal': bool(host.get('portal'))},
            'version': version,
            'published_by': layout.published_by.name if layout and layout.published_by else '',
            'published_at': fields.Datetime.to_string(layout.published_at)
            if layout and layout.published_at else '',
            'sections': sections,
            'fields': flds,
            'draft': ({'payload': draft.payload or {}, 'base_version': draft.base_version,
                       'stale': draft.base_version != version} if draft else None),
            'types': self._pbfs_types(),
            'money_ok': self._pbfs_currency_field(model) is not None,
            'comodels': [{'model': m, 'label': l} for m, l in targets.items() if m in self.env],
            'countries': [{'id': c.id, 'name': c.name, 'code': c.code}
                          for c in self.env['res.country'].search([])],
            'country_ok': bool(host.get('country_field')),
            'caps': {'per_model': MAX_PER_MODEL, 'per_section': MAX_PER_SECTION,
                     'label': MAX_LABEL},
            'custom_count': len(self._pbfs_custom_names(model)),
            'records': counts.get('__total__', 0),
            'busy': self._pbfs_busy(),
            'langs': self._pbfs_langs(),
        }

    @api.model
    def _pbfs_currency_field(self, model):
        field = self.env[model]._fields.get('currency_id')
        if field and field.type == 'many2one' and field.comodel_name == 'res.currency':
            return 'currency_id'
        return None

    @api.model
    def _pbfs_clean_label(self, label):
        label = (label or '').strip()
        if not label:
            raise UserError(self.env._('Give the field a name.'))
        if len(label) > MAX_LABEL:
            raise UserError(self.env._('A field name can be at most %s characters.', MAX_LABEL))
        return label

    @api.model
    def _pbfs_clean_options(self, options):
        labels = []
        for opt in options or []:
            label = (opt.get('label') if isinstance(opt, dict) else opt) or ''
            label = str(label).strip()
            if not label:
                continue
            if len(label) > MAX_LABEL:
                raise UserError(self.env._('A choice can be at most %s characters.', MAX_LABEL))
            if label.lower() in [l.lower() for l in labels]:
                raise UserError(self.env._('Each choice must be different: "%s" is there twice.', label))
            labels.append(label)
        if not labels:
            raise UserError(self.env._('A choice list needs at least one choice.'))
        if len(labels) > MAX_OPTIONS:
            raise UserError(self.env._('A choice list can have at most %s choices.', MAX_OPTIONS))
        return labels

    @api.model
    def _pbfs_unique_name(self, model, label):
        base = PREFIX + _slug(label)
        taken = set(self.env[model]._fields) | set(
            self.env['ir.model.fields'].sudo().search([('model', '=', model)]).mapped('name'))
        name, n = base, 2
        while name in taken:
            name = '%s_%s' % (base, n)
            n += 1
        return name

    @api.model
    def _pbfs_lock_timeout(self):
        self.env.cr.execute(SQL("SET LOCAL lock_timeout = %s", LOCK_TIMEOUT))

    @api.model
    def _pbfs_ddl_refusal(self):
        return UserError(self.env._(
            'The records are busy right now (a pay run or an import may be working on them). '
            'Try again in a few minutes.'))

    @api.model
    def _pbfs_write_translations(self, row, labels, helps):
        for lang, text in (labels or {}).items():
            if lang == 'en_US' or lang not in self._pbfs_langs() or not (text or '').strip():
                continue
            row.with_context(lang=lang).field_description = self._pbfs_clean_label(text)
        for lang, text in (helps or {}).items():
            if lang == 'en_US' or lang not in self._pbfs_langs():
                continue
            row.with_context(lang=lang).help = (text or '').strip() or False

    @api.model
    def _pbfs_audit(self, action, host_key=None, model=None, field_name=None, summary='',
                    detail=None, attachment=None):
        return self.env['pb.form.audit'].sudo().create({
            'action': action, 'host_key': host_key, 'model': model,
            'field_name': field_name, 'summary': (summary or '')[:500],
            'detail': detail or {}, 'company_id': self.env.company.id,
            'user_id': self.env.uid,
            'attachment_id': attachment.id if attachment else False,
        })

    @api.model
    def create_field(self, host_key, vals):
        """Make one real field on the host's record type.

        `vals`: `{type, label, labels?{lang:text}, help?, helps?, options?[labels],
        comodel?, vis?, is_required?, list_ok?, formula_ok?, country_ids?[ids],
        copied?}`. `copied` defaults to the host's `copy_custom` (the contract
        host passes True — owner ruling R7). Returns the field as `get_studio`
        describes it.
        """
        self._pbfs_check_admin()
        host = self._pbfs_host(host_key)
        model = host['model']
        self._pbfs_check_model(model)
        self._pbfs_check_busy()
        _ = self.env._
        vals = dict(vals or {})
        if len(self._pbfs_custom_names(model)) >= MAX_PER_MODEL:
            raise UserError(_('This record type already has %s custom fields, the most it can have. '
                              'Delete one you no longer use first.', MAX_PER_MODEL))
        kind = vals.get('type')
        if kind not in TYPE_TTYPE:
            raise UserError(_('Pick what kind of field this is.'))
        label = self._pbfs_clean_label(vals.get('label') or (vals.get('labels') or {}).get('en_US'))
        vis = vals.get('vis') or 'hr'
        if vis not in ('all', 'hr', 'admin'):
            raise UserError(_('Pick who can see this field.'))
        ttype = TYPE_TTYPE[kind]
        model_id = self.env['ir.model']._get_id(model)
        field_vals = {
            'model_id': model_id, 'name': self._pbfs_unique_name(model, label),
            'field_description': label, 'help': (vals.get('help') or '').strip() or False,
            'ttype': ttype, 'state': 'manual', 'store': True, 'required': False,
            'readonly': False, 'index': False,
            'copied': bool(vals['copied']) if 'copied' in vals else bool(host.get('copy_custom')),
            'pbfs_groups': self._pbfs_groups_for(vis),
        }
        if ttype == 'many2one':
            comodel = vals.get('comodel')
            if comodel not in self._pbfs_link_targets() or comodel not in self.env:
                raise UserError(_('Pick what this field links to.'))
            field_vals.update({'relation': comodel, 'on_delete': 'set null'})
        elif ttype == 'selection':
            labels = self._pbfs_clean_options(vals.get('options'))
            field_vals['selection_ids'] = [
                (0, 0, {'value': 'opt_%s' % (i + 1), 'name': l, 'sequence': i + 1})
                for i, l in enumerate(labels)]
        elif ttype == 'monetary':
            cur = self._pbfs_currency_field(model)
            if not cur:
                raise UserError(_('This record type has no money of its own. Use Decimal instead.'))
            field_vals['currency_field'] = cur
        self._pbfs_lock_timeout()
        try:
            row = self.env['ir.model.fields'].sudo().with_context(lang='en_US').create(field_vals)
        except (pg_errors.LockNotAvailable, pg_errors.QueryCanceled):
            raise self._pbfs_ddl_refusal() from None
        self.env.cr.execute("SET LOCAL lock_timeout = DEFAULT")
        self._pbfs_write_translations(row, vals.get('labels'), vals.get('helps'))
        meta = self.env['pb.form.field.meta'].sudo().create({
            'field_id': row.id, 'custom': True, 'vis': vis,
            'is_required': bool(vals.get('is_required')),
            'list_ok': bool(vals.get('list_ok')),
            'formula_ok': bool(vals.get('formula_ok')) and ttype in FORMULA_TTYPES,
            'country_ids': [(6, 0, self._pbfs_country_ids(vals.get('country_ids')))],
            'host_key': host_key,
        })
        self._pbfs_set_portal(model, row.name, vals)
        self._pbfs_audit('create_field', host_key, model, row.name,
                         _('Added %(label)s (%(type)s)', label=label,
                           type=self._pbfs_type_label(kind)))
        return self._pbfs_describe(self.env[model], row.name, meta=meta)

    @api.model
    def _pbfs_country_ids(self, ids):
        ids = [int(i) for i in (ids or []) if str(i).isdigit()]
        return self.env['res.country'].browse(ids).exists().ids

    @api.model
    def _pbfs_custom_row(self, model, name):
        meta = self._pbfs_meta(model, [name]).get(name)
        if not name or not name.startswith(PREFIX) or not meta or not meta.custom \
                or name not in self.env[model]._fields:
            raise UserError(self.env._('Only fields added with the Form builder can be changed here.'))
        return meta, meta.field_id

    @api.model
    def update_field(self, model, name, vals):
        """Change label / help (per language), who can see it, required, the
        list and formula switches, countries, choices. NEVER the type."""
        self._pbfs_check_admin()
        _ = self.env._
        vals = dict(vals or {})
        if 'type' in vals or 'ttype' in vals or 'comodel' in vals:
            raise UserError(_("A field's type cannot be changed. Delete it and add a new one."))
        meta, row = self._pbfs_custom_row(model, name)
        changes = []
        labels = dict(vals.get('labels') or {})
        if 'label' in vals:
            labels.setdefault('en_US', vals['label'])
        if labels.get('en_US') is not None:
            new = self._pbfs_clean_label(labels['en_US'])
            if new != row.with_context(lang='en_US').field_description:
                row.with_context(lang='en_US').field_description = new
                changes.append(_('name'))
        helps = dict(vals.get('helps') or {})
        if 'help' in vals:
            helps.setdefault('en_US', vals['help'])
        if 'en_US' in helps:
            row.with_context(lang='en_US').help = (helps['en_US'] or '').strip() or False
            changes.append(_('help text'))
        if any(l != 'en_US' for l in labels) or any(l != 'en_US' for l in helps):
            self._pbfs_write_translations(row, {k: v for k, v in labels.items() if k != 'en_US'},
                                          {k: v for k, v in helps.items() if k != 'en_US'})
            changes.append(_('translations'))
        meta_vals = {}
        if 'vis' in vals:
            if vals['vis'] not in ('all', 'hr', 'admin'):
                raise UserError(_('Pick who can see this field.'))
            if vals['vis'] != meta.vis:
                meta_vals['vis'] = vals['vis']
                row.pbfs_groups = self._pbfs_groups_for(vals['vis'])
                changes.append(_('who can see it'))
        for key in ('is_required', 'list_ok', 'formula_ok'):
            if key in vals:
                v = bool(vals[key])
                if key == 'formula_ok' and row.ttype not in FORMULA_TTYPES:
                    v = False
                if v != meta[key]:
                    meta_vals[key] = v
                    changes.append({'is_required': _('required'), 'list_ok': _('show in lists'),
                                    'formula_ok': _('use in pay formulas')}[key])
        if 'country_ids' in vals:
            ids = self._pbfs_country_ids(vals['country_ids'])
            if set(ids) != set(meta.country_ids.ids):
                meta_vals['country_ids'] = [(6, 0, ids)]
                changes.append(_('countries'))
        if meta_vals:
            meta.write(meta_vals)
        if 'options' in vals and row.ttype == 'selection':
            if self._pbfs_update_options(model, row, vals['options']):
                changes.append(_('choices'))
        changes += self._pbfs_set_portal(model, name, vals)
        if changes:
            self._pbfs_audit('update_field', meta.host_key, model, name,
                             _('Changed %(label)s: %(what)s',
                               label=row.with_context(lang=self.env.lang).field_description,
                               what=', '.join(changes)))
        return self._pbfs_describe(self.env[model], name)

    @api.model
    def _pbfs_update_options(self, model, row, options):
        """`options`: `[{value?, label}]` in order. Existing values keep their
        key (so stored answers keep meaning); a choice still in use cannot be
        removed."""
        _ = self.env._
        self._pbfs_clean_options(options)          # validates; raises in plain words
        items = []
        for opt in options or []:
            label = str((opt.get('label') if isinstance(opt, dict) else opt) or '').strip()
            if label:
                items.append((opt.get('value') if isinstance(opt, dict) else None, label))
        by_value = {s.value: s for s in row.selection_ids}
        keep, new_rows, seq, renamed = set(), [], 0, False
        for value, label in items:
            seq += 1
            if value in by_value:
                keep.add(value)
                sel = by_value[value]
                if sel.name != label:
                    renamed = True
                if sel.name != label or sel.sequence != seq:
                    sel.write({'name': label, 'sequence': seq})
            else:
                new_rows.append({'label': label, 'sequence': seq})
        removed = [s for v, s in by_value.items() if v not in keep]
        Model = self.env[model].sudo().with_context(active_test=False)
        for sel in removed:
            used = Model.search_count([(row.name, '=', sel.value)])
            if used:
                raise UserError(_('%(n)s records use the choice "%(choice)s". Change them first, '
                                  'then remove it.', n=used, choice=sel.name))
        changed = bool(removed or new_rows or renamed)
        if removed:
            self.env['ir.model.fields.selection'].sudo().browse([s.id for s in removed]).unlink()
        existing = set(row.selection_ids.mapped('value'))
        n = 1
        for item in new_rows:
            while 'opt_%s' % n in existing:
                n += 1
            existing.add('opt_%s' % n)
            self.env['ir.model.fields.selection'].sudo().create({
                'field_id': row.id, 'value': 'opt_%s' % n, 'name': item['label'],
                'sequence': item['sequence']})
        return changed

    # ------------------------------------------------------- references
    @api.model
    def field_references(self, model, name):
        """Everything that uses the field and would break (or silently lose
        data) if it were deleted. Each item: `{kind, label, count, names}`."""
        self._pbfs_check_admin()
        out = []
        for method in self._pbfs_reference_finders():
            finder = getattr(self, method, None)
            if not finder:
                continue
            try:
                out.extend(finder(model, name) or [])
            except Exception:                           # noqa: BLE001
                _logger.warning('pb_form_studio: reference finder %s failed', method,
                                exc_info=True)
        return out

    @api.model
    def _pbfs_ref(self, kind, label, records_or_names, count=None):
        names = records_or_names if isinstance(records_or_names, list) else \
            [r.display_name for r in records_or_names]
        names = [n for n in dict.fromkeys(names) if n]
        return {'kind': kind, 'label': label,
                'count': count if count is not None else len(names), 'names': names[:5]}

    @api.model
    def _pbfs_refs_import_mappings(self, model, name):
        """Pay-data import mappings cascade-delete with the field
        (`target_field_id ondelete='cascade'`, FS_HOST_FACTS §F) — silent
        loss of a customer's mapping, so they block the delete."""
        if 'hr.payslip.import.mapping' not in self.env:
            return []
        row = self._pbfs_field_row(model, name)
        Mapping = self.env['hr.payslip.import.mapping'].sudo().with_context(active_test=False)
        maps = Mapping.search([('target_field_id', '=', row.id)])
        if not maps:
            return []
        schemes = [m.salary_structure_id.display_name for m in maps
                   if 'salary_structure_id' in m._fields]
        return [self._pbfs_ref('import_mapping', self.env._('Pay data import mappings'),
                               schemes, count=len(maps))]

    @api.model
    def _pbfs_refs_relations(self, model, name):
        row = self._pbfs_field_row(model, name)
        if not row:
            return []
        out = []
        for mname, Model in self.env.registry.items():
            if Model._abstract or not Model._auto:
                continue
            for fname, field in Model._fields.items():
                if field.type not in ('many2one', 'many2many') or field.comodel_name != 'ir.model.fields' \
                        or not field.store or (mname, fname) in REF_SKIP or mname == 'ir.model.fields':
                    continue
                Rec = self.env[mname].sudo().with_context(active_test=False)
                op = '=' if field.type == 'many2one' else 'in'
                value = row.id if field.type == 'many2one' else [row.id]
                try:
                    recs = Rec.search([(fname, op, value)], limit=6)
                    count = Rec.search_count([(fname, op, value)]) if recs else 0
                except Exception:                       # noqa: BLE001
                    continue
                if count:
                    label = self.env['ir.model']._get(mname).name or mname
                    out.append(self._pbfs_ref('relation', label, recs, count=count))
        return out

    @api.model
    def _pbfs_studio_view_ids(self):
        return self.env['pb.form.native.view'].sudo().search([]).mapped('view_id').ids

    @api.model
    def _pbfs_refs_views(self, model, name):
        dom = [('arch_db', 'ilike', name), ('id', 'not in', self._pbfs_studio_view_ids())]
        count = self.env['ir.ui.view'].sudo().with_context(active_test=False).search_count(dom)
        if not count:
            return []
        return [self._pbfs_ref('view', self.env._('Screen designs that show it'), [], count=count)]

    @api.model
    def _pbfs_refs_filters(self, model, name):
        Filters = self.env['ir.filters'].sudo().with_context(active_test=False)
        recs = Filters.search(['|', '|', ('domain', 'ilike', name), ('context', 'ilike', name),
                               ('sort', 'ilike', name)])
        return [self._pbfs_ref('filter', self.env._('Saved searches'), recs)] if recs else []

    @api.model
    def _pbfs_refs_saved_views(self, model, name):
        if 'pb.filter.view' not in self.env:
            return []
        self.env.cr.execute(SQL(
            "SELECT id FROM pb_filter_view WHERE COALESCE(filters::text, '') ILIKE %s "
            "OR COALESCE(search_text, '') ILIKE %s", '%' + name + '%', '%' + name + '%'))
        ids = [r[0] for r in self.env.cr.fetchall()]
        if not ids:
            return []
        recs = self.env['pb.filter.view'].sudo().browse(ids)
        return [self._pbfs_ref('saved_view', self.env._('Saved views'), recs)]

    @api.model
    def _pbfs_refs_automations(self, model, name):
        recs = self.env['ir.actions.server'].sudo().with_context(active_test=False).search(
            [('code', 'ilike', name)])
        return [self._pbfs_ref('automation', self.env._('Automations'), recs)] if recs else []

    @api.model
    def _pbfs_refs_exports(self, model, name):
        if 'ir.exports.line' not in self.env:
            return []
        lines = self.env['ir.exports.line'].sudo().search([('name', '=like', name + '%')])
        if not lines:
            return []
        return [self._pbfs_ref('export', self.env._('Saved export lists'),
                               [l.export_id.name for l in lines], count=len(lines.mapped('export_id')))]

    # ----------------------------------------------------------- delete
    @api.model
    def _pbfs_export_values(self, model, row):
        """CSV of every record that holds a value, made BEFORE the column is
        dropped. Read with elevated rights: it is the only copy left."""
        Model = self.env[model].sudo().with_context(active_test=False)
        field = Model._fields[row.name]
        dom = [(row.name, '=', True)] if field.type == 'boolean' else [(row.name, '!=', False)]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Record', 'Name', row.with_context(lang='en_US').field_description])
        for rec in Model.search(dom):
            if field.type == 'binary':
                value = 'file'
            else:
                value = self._pbfs_display(rec, field)
            name = rec.display_name or ''
            # Spreadsheet-safe: a cell never starts with a formula character.
            cells = [rec.id] + ["'" + c if isinstance(c, str) and c[:1] in '=+-@\t\r' else c
                                for c in (name, value)]
            w.writerow(cells)
        return buf.getvalue().encode('utf-8-sig')

    @api.model
    def delete_field(self, model, name, confirm=''):
        """Delete a Form-builder field and its values everywhere.

        `confirm` must be the field's name as shown (any language), typed by
        the administrator — re-checked here, as are the blockers. The values
        are saved to a file on the history entry before the column goes.
        """
        self._pbfs_check_admin()
        _ = self.env._
        meta, row = self._pbfs_custom_row(model, name)
        labels = {(row.with_context(lang=l).field_description or '').strip().casefold()
                  for l in self._pbfs_langs()}
        if (confirm or '').strip().casefold() not in labels:
            raise UserError(_('Type the field name exactly to confirm the delete.'))
        refs = self.field_references(model, name)
        if refs:
            raise UserError(_('This field is still used by: %s. Remove it there first.',
                              '; '.join('%s (%s)' % (r['label'], r['count']) for r in refs)))
        self._pbfs_check_busy()
        label = row.with_context(lang=self.env.lang).field_description
        data = self._pbfs_export_values(model, row)
        audit = self._pbfs_audit('delete_field', meta.host_key, model, name,
                                 _('Deleted %s', label))
        att = self.env['ir.attachment'].sudo().create({
            'name': '%s-values.csv' % name, 'raw': data, 'mimetype': 'text/csv',
            'res_model': 'pb.form.audit', 'res_id': audit.id,
        })
        audit.sudo().write({'attachment_id': att.id})
        # Take it out of every published layout of this model first...
        hosts = [k for k, h in self._pbfs_hosts().items() if h['model'] == model]
        for lay in self.env['pb.form.layout'].sudo().search([('host_key', 'in', hosts)]):
            lay.sections = [{'id': s.get('id'), 'fields': [f for f in s.get('fields') or [] if f != name]}
                            for s in (lay.sections or [])]
        # ...and out of every Studio-owned native page, BEFORE the field goes:
        # core refuses to drop a field a view still names.
        self._pbfs_resync_native(model, exclude=[name])
        self._pbfs_lock_timeout()
        try:
            meta.unlink()
            row.unlink()
        except (pg_errors.LockNotAvailable, pg_errors.QueryCanceled):
            raise self._pbfs_ddl_refusal() from None
        self.env.cr.execute("SET LOCAL lock_timeout = DEFAULT")
        return {'ok': True, 'attachment_id': att.id}

    # ---------------------------------------------------- draft/publish
    @api.model
    def save_draft(self, host_key, payload):
        self._pbfs_check_admin()
        self._pbfs_host(host_key)
        layout = self._pbfs_layout(host_key)
        Draft = self.env['pb.form.layout.draft'].sudo()
        draft = Draft.search([('host_key', '=', host_key), ('company_id', '=', self.env.company.id),
                              ('user_id', '=', self.env.uid)], limit=1)
        base = (payload or {}).get('base_version')
        vals = {'payload': payload or {},
                'base_version': base if isinstance(base, int) else (layout.version if layout else 0)}
        if draft:
            draft.write(vals)
        else:
            Draft.create(dict(vals, host_key=host_key, company_id=self.env.company.id,
                              user_id=self.env.uid))
        return True

    @api.model
    def discard_draft(self, host_key):
        self._pbfs_check_admin()
        self.env['pb.form.layout.draft'].sudo().search([
            ('host_key', '=', host_key), ('company_id', '=', self.env.company.id),
            ('user_id', '=', self.env.uid)]).unlink()
        return True

    @api.model
    def publish(self, host_key, payload):
        """Make the administrator's changes live, in one transaction.

        `payload`: `{sections: [{id, fields: [name | "new:<tmp>"]}],
        creates: [{tmp, …create_field vals}], updates: {name: vals},
        deletes: [{name, confirm}], base_version, overwrite, changes: [text]}`.

        Refuses a stale draft (someone else published since it started)
        unless `overwrite` is true — the answer says who and when, plainly.
        """
        self._pbfs_check_admin()
        _ = self.env._
        host = self._pbfs_host(host_key)
        model = host['model']
        payload = payload or {}
        layout = self._pbfs_layout(host_key)
        current = layout.version if layout else 0
        base = payload.get('base_version', current)
        if base != current and not payload.get('overwrite'):
            who = layout.published_by.name or _('another administrator')
            return {'ok': False, 'stale': True,
                    'message': _('%(who)s published this screen after you started your changes. '
                                 'Publishing now would replace their layout with yours.', who=who),
                    'published_by': who,
                    'published_at': fields.Datetime.to_string(layout.published_at)
                    if layout.published_at else ''}
        created = {}
        for item in payload.get('deletes') or []:
            self.delete_field(model, item.get('name'), item.get('confirm'))
        for spec in payload.get('creates') or []:
            desc = self.create_field(host_key, spec)
            created[str(spec.get('tmp'))] = desc['name']
        for name, vals in (payload.get('updates') or {}).items():
            real = created.get(name.split(':', 1)[1], name) if name.startswith('new:') else name
            if real not in self.env[model]._fields:
                continue
            if real.startswith(PREFIX):
                self.update_field(model, real, vals)
            else:
                # a standard field: only its My Payobook ticks can change
                self.update_portal(model, real, vals)
        sections = []
        for sec in payload.get('sections') or []:
            names = []
            for n in sec.get('fields') or []:
                if isinstance(n, str) and n.startswith('new:'):
                    n = created.get(n.split(':', 1)[1])
                if n:
                    names.append(n)
            sections.append({'id': sec.get('id'), 'fields': names})
        effective = self._pbfs_effective(host_key, stored=sections)
        for sec in effective:
            if len(sec['fields']) > MAX_PER_SECTION:
                raise UserError(_('The section "%(sec)s" can hold at most %(n)s fields.',
                                  sec=sec['title'], n=MAX_PER_SECTION))
        stored = self._pbfs_stored_from(effective)
        vals = {'sections': stored, 'version': current + 1, 'published_by': self.env.uid,
                'published_at': fields.Datetime.now()}
        if layout:
            layout.write(vals)
        else:
            layout = self.env['pb.form.layout'].sudo().create(dict(
                vals, host_key=host_key, model=model, company_id=self.env.company.id))
        self.env['pb.form.layout.draft'].sudo().search([
            ('host_key', '=', host_key), ('company_id', '=', self.env.company.id),
            ('user_id', '=', self.env.uid)]).unlink()
        changes = [str(c)[:200] for c in (payload.get('changes') or [])][:100]
        self._pbfs_audit('publish', host_key, model, None,
                         _('Published %(screen)s, version %(v)s', screen=host['title'],
                           v=layout.version),
                         detail={'changes': changes, 'sections': stored, 'created': created})
        self._pbfs_resync_native(model)
        self._pbfs_notify(host_key, layout.version)
        return {'ok': True, 'version': layout.version, 'created': created}

    @api.model
    def _pbfs_notify(self, host_key, version):
        if 'bus.bus' not in self.env:
            return
        users = self.env['res.users'].sudo().search([
            ('share', '=', False), ('company_ids', 'in', self.env.company.id)])
        Bus = self.env['bus.bus'].sudo()
        for user in users:
            Bus._sendone(user.partner_id, 'pb_form_studio/published',
                         {'host_key': host_key, 'version': version})

    # ============================================================ hosts
    @api.model
    def render(self, host_key, record_id):
        """The published sections of one record, for a host to draw with
        `PbFieldGrid`. Only fields the caller may read, only fields that
        apply to the record's Country of Work. Locked sections come back with
        no fields (the host draws them). Never elevated: the record is read
        with the caller's own rights."""
        host = self._pbfs_host(host_key)
        Model = self.env[host['model']]
        record = Model.browse(int(record_id)).exists()
        if not record:
            raise UserError(self.env._('This record no longer exists.'))
        record.check_access('read')
        try:
            record.check_access('write')
            can_write = True
        except AccessError:
            can_write = False
        country = self._pbfs_record_countries(record)[record.id]
        metas = self._pbfs_meta(host['model'])
        locked = self._pbfs_locked_fields(host['model'])
        out = []
        for sec in self._pbfs_effective(host_key):
            item = {k: sec.get(k) for k in ('id', 'title', 'icon', 'tone', 'kind', 'note')}
            entries = []
            for name in sec['fields']:
                field = Model._fields.get(name)
                if not field or not self._pbfs_can_read_field(Model, field):
                    continue
                meta = metas.get(name)
                custom = name.startswith(PREFIX) and bool(meta)
                if custom and not self._pbfs_applies(meta, country):
                    continue
                desc = self._pbfs_describe(Model, name, meta=meta, locked=locked)
                desc.pop('labels', None)
                desc.pop('helps', None)
                desc.update({
                    'value': self._pbfs_raw(record, field),
                    'display': self._pbfs_display(record, field),
                    'writable': bool(custom and can_write and Model._has_field_access(field, 'write')),
                })
                if field.type == 'binary' and desc['value']:
                    desc['url'] = '/web/content?model=%s&id=%s&field=%s&download=true' % (
                        host['model'], record.id, name)
                entries.append(desc)
            item['fields'] = entries
            out.append(item)
        layout = self._pbfs_layout(host_key)
        return {'sections': out, 'version': layout.version if layout else 0,
                'can_write': can_write,
                'currency': (record.currency_id.symbol if 'currency_id' in record._fields
                             and record.currency_id else self.env.company.currency_id.symbol) or ''}

    @api.model
    def _pbfs_coerce(self, field, value, check_read=True):
        """→ (stored value, error text or None). `check_read=False` (My
        Payobook) checks a link's target exists and is one of the allowed
        kinds instead of asking whether the employee may read it."""
        _ = self.env._
        t = field.type
        if value is None or value == '' or value is False:
            return False, None
        try:
            if t in ('char', 'text'):
                return str(value).strip() or False, None
            if t == 'integer':
                text = str(value).replace(',', '').replace(' ', '')
                num = float(text)
                if num != int(num):
                    return None, _('Enter a whole number.')
                if abs(num) > 2 ** 31 - 1:
                    return None, _('That number is too big.')
                return int(num), None
            if t in ('float', 'monetary'):
                return float(str(value).replace(',', '').replace(' ', '')), None
            if t == 'boolean':
                if isinstance(value, str):
                    return value.strip().lower() in ('1', 'true', 'yes', 'y'), None
                return bool(value), None
            if t == 'date':
                return fields.Date.to_date(value), None
            if t == 'selection':
                keys = [v for v, _l in field._description_selection(self.env)]
                if value not in keys:
                    return None, _('Pick one of the choices.')
                return value, None
            if t == 'many2one':
                if not check_read:
                    if field.comodel_name not in self._pbfs_link_targets():
                        return None, _('You cannot pick that record.')
                    rec = self.env[field.comodel_name].sudo().browse(int(value)).exists()
                    if not rec:
                        return None, _('That record no longer exists.')
                    return rec.id, None
                rec = self.env[field.comodel_name].browse(int(value)).exists()
                if not rec:
                    return None, _('That record no longer exists.')
                rec.check_access('read')
                return rec.id, None
            if t == 'binary':
                data = value.split(',', 1)[1] if isinstance(value, str) and value.startswith('data:') \
                    else value
                raw = base64.b64decode(data, validate=True)
                if len(raw) > MAX_FILE_BYTES:
                    return None, _('The file is too big (at most 10 MB).')
                return base64.b64encode(raw), None
        except AccessError:
            return None, _('You cannot pick that record.')
        except (ValueError, TypeError, ValidationError):
            pass
        except Exception:                               # noqa: BLE001 (binascii.Error etc.)
            pass
        return None, {
            'integer': _('Enter a whole number.'), 'float': _('Enter a number.'),
            'monetary': _('Enter an amount.'), 'date': _('Enter a date.'),
            'binary': _('That file could not be read.'),
        }.get(t, _('That value cannot be used here.'))

    @api.model
    def write_values(self, model, record_id, vals):
        """The ONLY write path for custom fields from a host.

        Whitelist: Form-builder fields of `model` the caller may write, that
        apply to the record's Country of Work. Coerced per type; required
        (Studio-level) checked; the record written with the caller's own
        rights — record rules apply, nothing is elevated.

        → `{ok: True, values: {name: {value, display}}}` or
          `{ok: False, error?: text, errors: {name: text}}`.
        """
        _ = self.env._
        if model not in self._pbfs_host_models() or self._pbfs_model_forbidden(model):
            return {'ok': False, 'error': _('Custom fields cannot be saved on this kind of record.'),
                    'errors': {}}
        Model = self.env[model]
        record = Model.browse(int(record_id)).exists()
        if not record:
            return {'ok': False, 'error': _('This record no longer exists.'), 'errors': {}}
        try:
            record.check_access('write')
        except AccessError:
            return {'ok': False, 'error': _('You cannot change this record.'), 'errors': {}}
        metas = self._pbfs_meta(model)
        country = self._pbfs_record_countries(record)[record.id]
        clean, errors = {}, {}
        for name, value in (vals or {}).items():
            field = Model._fields.get(name)
            meta = metas.get(name)
            if not field or not name.startswith(PREFIX) or not meta or not meta.custom:
                errors[name] = _('This field cannot be changed here.')
                continue
            if not Model._has_field_access(field, 'write'):
                errors[name] = _('You cannot change this field.')
                continue
            if not self._pbfs_applies(meta, country):
                errors[name] = _("This field does not apply to this record's country of work.")
                continue
            stored, err = self._pbfs_coerce(field, value)
            if err:
                errors[name] = err
                continue
            empty = stored is False or stored is None or stored == ''
            if meta.is_required and empty and field.type != 'boolean':
                errors[name] = _('Fill this in: it is required.')
                continue
            clean[name] = stored
        if errors:
            return {'ok': False, 'errors': errors}
        if clean:
            record.write(clean)
        out = {}
        for name in clean:
            field = Model._fields[name]
            out[name] = {'value': self._pbfs_raw(record, field),
                         'display': self._pbfs_display(record, field)}
        return {'ok': True, 'values': out}

    @api.model
    def fields_for(self, model, purpose='list', record=None):
        """Fields of `model` for a list, an export, a formula catalogue or
        My Payobook. Labels in the caller's language.

        purpose 'list'     custom fields marked "Show in lists" the caller may read
                'formula'  custom fields marked "Use in pay formulas" the caller may read
                'all'      every custom field the caller may read
                'portal'   R14 — standard AND custom fields ticked "Show on My
                           Payobook", in layout order, for `record` (Country of
                           Work honoured); decided from the ticks, not from the
                           caller, so safe around a record read with elevated
                           rights. Items: {name, label, help, type, kind,
                           options, comodel, section, section_title, edit, mode}.
                'everyone' DEPRECATED alias kept for fs-5 (R3, replaced by R14):
                           custom fields whose visibility is "Everyone".
        Each list item carries `countries` (ids; empty = all) so a list can
        blank the cell for records elsewhere — `_pbfs_values_for` does that.
        """
        if model not in self._pbfs_host_models():
            return []
        if purpose == 'portal':
            return self._pbfs_portal_fields(model, record)
        Model = self.env[model]
        out = []
        for name, meta in self._pbfs_meta(model).items():
            field = Model._fields.get(name)
            if not field or not meta.custom:
                continue
            if purpose == 'everyone':
                if meta.vis != 'all':
                    continue
            elif not self._pbfs_can_read_field(Model, field):
                continue
            if purpose == 'list' and not meta.list_ok:
                continue
            if purpose == 'formula' and not (meta.formula_ok and field.type in FORMULA_TTYPES):
                continue
            desc = field.get_description(self.env, ['string', 'help'])
            kind = TTYPE_KIND.get(field.type, 'text')
            out.append({
                'name': name, 'label': desc.get('string') or name, 'help': desc.get('help') or '',
                'type': field.type, 'kind': kind, 'type_label': self._pbfs_type_label(kind),
                'vis': meta.vis, 'required': meta.is_required, 'list_ok': meta.list_ok,
                'formula_ok': meta.formula_ok, 'countries': meta.country_ids.ids,
                'options': self._pbfs_options(field),
                'comodel': field.comodel_name if field.type == 'many2one' else False,
            })
        return out

    # ------------------------------------------------------- My Payobook
    @api.model
    def _pbfs_portal_record(self, model, record, operation='read'):
        """The record a My Payobook helper works on, read with elevated rights.

        A RECORDSET comes from server code (the self-service controller), which
        has already decided the record is the employee's own: it is trusted.
        An ID can only come over the wire (RPC): then the CALLER must be allowed
        to `operation` it with their own rights — so nobody can read or change
        another person's ticked fields by sending an id."""
        if isinstance(record, int) or (isinstance(record, str) and record.isdigit()):
            rec = self.env[model].browse(int(record)).exists()
            if not rec:
                raise UserError(self.env._('This record cannot be shown here.'))
            rec.check_access(operation)
            return rec.sudo()
        if record is None or getattr(record, '_name', None) != model:
            raise UserError(self.env._('This record cannot be shown here.'))
        return record[:1].sudo()

    @api.model
    def _pbfs_portal_fields(self, model, record=None):
        key, host = self._pbfs_portal_host(model)
        if not key:
            return []
        Model = self.env[model]
        rec = self._pbfs_portal_record(model, record) if record is not None else None
        country = self._pbfs_record_countries(rec)[rec.id] if rec else False
        metas = {n: m for n, m in self._pbfs_meta(model).items() if m.portal_show}
        if not metas:
            return []
        hidden = self._pbfs_portal_hidden(model)
        company = rec.company_id if rec and 'company_id' in rec._fields and rec.company_id else None
        order, where = [], {}
        for sec in self._pbfs_effective(key, company=company):
            for name in sec['fields']:
                if name in metas and name not in where:
                    order.append(name)
                    where[name] = (sec['id'], sec['title'])
        custom_id = host.get('custom_section')
        custom_title = next((s['title'] for s in host['sections'] if s['id'] == custom_id), '')
        for name in metas:                      # ticked but not placed on the screen
            if name not in where:
                order.append(name)
                where[name] = (custom_id, custom_title)
        out = []
        for name in order:
            meta, field = metas[name], Model._fields.get(name)
            if not field or name in hidden:
                continue
            if name.startswith(PREFIX) and rec is not None and not self._pbfs_applies(meta, country):
                continue
            rules = self._pbfs_portal_rules(model, name)
            if not rules['can_show']:
                continue
            desc = field.get_description(self.env, ['string', 'help'])
            kind = TTYPE_KIND.get(field.type, 'text')
            out.append({
                'name': name, 'label': desc.get('string') or name, 'help': desc.get('help') or '',
                'type': field.type, 'kind': kind, 'options': self._pbfs_options(field),
                'comodel': field.comodel_name if field.type == 'many2one' else False,
                'section': where[name][0], 'section_title': where[name][1],
                'edit': bool(meta.portal_edit and rules['can_edit']),
                'mode': meta.portal_mode or 'approve',
                'required': bool(meta.custom and meta.is_required),
            })
        return out

    @api.model
    def portal_values(self, model, record):
        """`{name: {value, display}}` for the My Payobook fields of `record`
        (only those — nothing else is read). Safe around a sudo record."""
        rec = self._pbfs_portal_record(model, record)
        out = {}
        for spec in self._pbfs_portal_fields(model, rec):
            field = rec._fields[spec['name']]
            out[spec['name']] = {'value': self._pbfs_raw(rec, field),
                                 'display': self._pbfs_display(rec, field)}
        return out

    @api.model
    def portal_check(self, model, record, vals):
        """Validate + coerce a change proposed on My Payobook.

        → `{'instant': {name: value}, 'approve': {name: value},
            'errors': {name: text}}`. Anything not changeable for THIS record
        (not ticked, locked, hidden, another country, wrong type) lands in
        `errors` — callers refuse the whole submission when it is not empty.
        Unchanged values are dropped."""
        _ = self.env._
        rec = self._pbfs_portal_record(model, record)
        specs = {s['name']: s for s in self._pbfs_portal_fields(model, rec)}
        out = {'instant': {}, 'approve': {}, 'errors': {}}
        for name, value in (vals or {}).items():
            spec = specs.get(name)
            if not spec or not spec['edit']:
                out['errors'][name] = _('This cannot be changed here.')
                continue
            field = rec._fields[name]
            stored, err = self._pbfs_coerce(field, value, check_read=False)
            if err:
                out['errors'][name] = err
                continue
            if spec['required'] and (stored is False or stored is None or stored == ''):
                out['errors'][name] = _('Fill this in: it is required.')
                continue
            if stored == self._pbfs_raw(rec, field) or (
                    field.type == 'date' and stored and fields.Date.to_string(stored) == self._pbfs_raw(rec, field)):
                continue
            out[spec['mode'] if spec['mode'] in ('instant', 'approve') else 'approve'][name] = stored
        return out

    @api.model
    def portal_apply(self, model, record, vals, origin=None):
        """THE single write path for My Payobook changes (saved at once, or
        after HR approved). Re-checks everything (a field unticked meanwhile is
        refused), writes ONLY those fields, and leaves a history line per
        field: who proposed, who approved or "saved at once", label, old → new.

        `origin`: `{'proposed_by': user id, 'approved_by': user id or False}`
        (defaults: the caller proposed, nobody approved = saved at once).
        → `{ok: True, values: {name: {value, display}}}`."""
        _ = self.env._
        rec = self._pbfs_portal_record(model, record, "write")
        checked = self.portal_check(model, rec, vals)
        if checked['errors']:
            raise UserError('; '.join(sorted(set(checked['errors'].values()))))
        clean = dict(checked['instant'], **checked['approve'])
        if not clean:
            return {'ok': True, 'values': {}}
        origin = origin or {}
        Users = self.env['res.users'].sudo()
        proposer = Users.browse(origin.get('proposed_by') or self.env.uid).exists()
        approver = Users.browse(origin.get('approved_by') or 0).exists()
        how = (_('approved by %s', approver.name) if approver else _('saved at once'))
        before = {n: self._pbfs_display(rec.sudo(), rec._fields[n]) for n in clean}
        rec.sudo().write(clean)
        lines, out = [], {}
        for name in clean:
            field = rec._fields[name]
            label = field.get_description(self.env, ['string']).get('string') or name
            after = self._pbfs_display(rec.sudo(), field)
            out[name] = {'value': self._pbfs_raw(rec.sudo(), field), 'display': after}
            text = _('%(label)s: %(old)s → %(new)s (changed on My Payobook by %(who)s, %(how)s)',
                     label=label, old=before[name] or '—', new=after or '—',
                     who=proposer.name or '', how=how)
            lines.append(text)
            self.env['pb.form.audit'].sudo().create({
                'action': 'portal_change', 'model': model, 'field_name': name, 'res_id': rec.id,
                'summary': text[:500], 'user_id': proposer.id or self.env.uid,
                'company_id': (rec.company_id.id if 'company_id' in rec._fields else False)
                or self.env.company.id,
                'detail': {'old': before[name], 'new': after, 'proposed_by': proposer.id,
                           'approved_by': approver.id or False},
            })
        if hasattr(rec, 'message_post'):
            rec.sudo().message_post(body=Markup('<br/>').join(lines), message_type='comment',
                                    subtype_xmlid='mail.mt_note')
        return {'ok': True, 'values': out}

    @api.model
    def update_portal(self, model, name, vals):
        """Administrator: set the My Payobook ticks of a STANDARD or custom
        field (`portal_show`, `portal_edit`, `portal_mode`). Refuses what the
        host's hooks forbid, in plain words."""
        self._pbfs_check_admin()
        if model not in self._pbfs_host_models() or name not in self.env[model]._fields:
            raise UserError(self.env._('This field is not offered on this screen.'))
        changed = self._pbfs_set_portal(model, name, {k: v for k, v in (vals or {}).items()
                                                      if k in PORTAL_KEYS})
        if changed:
            label = self.env[model]._fields[name].get_description(self.env, ['string']).get('string')
            self._pbfs_audit('update_field', None, model, name,
                             self.env._('Changed %(label)s: %(what)s', label=label,
                                        what=', '.join(changed)))
        return self._pbfs_describe(self.env[model], name)

    @api.model
    def _pbfs_values_for(self, records, purpose='list'):
        """Python helper for lists / exports / self-service:
        `{record id: {field name: {value, display}}}` for `fields_for(purpose)`;
        a field that does not apply to a record's country is a blank cell.
        With purpose 'everyone' it may be handed a sudo recordset."""
        specs = self.fields_for(records._name, purpose)
        countries = self._pbfs_record_countries(records)
        metas = self._pbfs_meta(records._name, [s['name'] for s in specs])
        out = {}
        for rec in records:
            row = {}
            for spec in specs:
                field = rec._fields[spec['name']]
                if not self._pbfs_applies(metas.get(spec['name']), countries.get(rec.id)):
                    row[spec['name']] = {'value': False, 'display': ''}
                    continue
                row[spec['name']] = {'value': self._pbfs_raw(rec, field),
                                     'display': self._pbfs_display(rec, field)}
            out[rec.id] = row
        return out

    @api.model
    def values_for(self, model, record_ids, purpose='list'):
        """RPC face of `_pbfs_values_for` — caller's own rights, never
        elevated ('everyone' is refused here: it is a server-side helper)."""
        if purpose == 'everyone' or model not in self._pbfs_host_models():
            return {}
        records = self.env[model].browse([int(i) for i in record_ids or []]).exists()
        records.check_access('read')
        return self._pbfs_values_for(records, purpose)

    @api.model
    def lookup(self, model, name, term='', limit=8):
        """Choices for a "Link to a record" field, searched with the caller's
        own rights. → `[{id, label}]`."""
        Model = self.env[model] if model in self._pbfs_host_models() else None
        field = Model._fields.get(name) if Model is not None else None
        meta = self._pbfs_meta(model, [name]).get(name) if field else None
        if not field or field.type != 'many2one' or not meta or not meta.custom \
                or not Model._has_field_access(field, 'read') \
                or field.comodel_name not in self._pbfs_link_targets():
            return []
        Co = self.env[field.comodel_name]
        try:
            recs = Co.search([('display_name', 'ilike', term or '')], limit=min(int(limit or 8), 20))
        except AccessError:
            return []
        return [{'id': r.id, 'label': r.display_name} for r in recs]

    @api.model
    def copy_field_names(self, model):
        """Custom fields whose values a renewal / copy should carry over."""
        Model = self.env[model] if model in self.env else None
        if Model is None:
            return []
        return [n for n, m in self._pbfs_meta(model).items()
                if m.custom and n in Model._fields and Model._fields[n].store]

    # ============================================================ native
    @api.model
    def _pbfs_sync_native_view(self, model, parent_view_xmlid, page_title, host_key=None):
        """Keep ONE Studio-owned inherited view on `parent_view_xmlid` that
        adds a notebook page `page_title` with the published custom fields of
        `model` in layout order. Called by hosts (and again by the engine on
        every publish and delete for the views hosts registered). Removed when
        no custom field remains. Never breaks the parent: the new arch is
        validated in a savepoint and the previous one kept on failure.
        → the view record, or False when there is nothing to show."""
        return self.env['pb.form.native.view'].sudo()._pbfs_sync(
            model, parent_view_xmlid, page_title, host_key)

    @api.model
    def _pbfs_resync_native(self, model, exclude=()):
        for rec in self.env['pb.form.native.view'].sudo().search([('model', '=', model)]):
            rec._pbfs_regenerate(exclude=exclude)

    # =========================================================== library
    @api.model
    def library(self):
        """Every custom field in this company's record types, for the Field
        library (Settings › Form builder)."""
        self._pbfs_check_admin()
        hosts = self._pbfs_hosts()
        models_seen, rows, screens = [], [], []
        for key, host in hosts.items():
            if host.get('dev') and not self._pbfs_meta(host['model']):
                continue
            screens.append({'key': key, 'title': host['title'], 'model': host['model'],
                            'dev': bool(host.get('dev'))})
            if host['model'] in models_seen:
                continue
            models_seen.append(host['model'])
        for model in models_seen:
            Model = self.env[model]
            names = self._pbfs_custom_names(model)
            counts = self._pbfs_filled_counts(model, names)
            metas = self._pbfs_meta(model)
            record_type = next((h['title'] for h in hosts.values() if h['model'] == model), model)
            for name in names:
                desc = self._pbfs_describe(Model, name, meta=metas.get(name), counts=counts)
                where = []
                for key, host in hosts.items():
                    if host['model'] != model:
                        continue
                    for sec in self._pbfs_effective(key):
                        if name in sec['fields']:
                            where.append('%s › %s' % (host['title'], sec['title']))
                desc.update({'model': model, 'record_type': record_type,
                             'total': counts.get('__total__', 0), 'where': where,
                             'used_by': self.field_references(model, name)})
                rows.append(desc)
        return {'fields': rows, 'screens': screens, 'langs': self._pbfs_langs(),
                'countries': [{'id': c.id, 'name': c.name} for c in self.env['res.country'].search([])],
                'busy': self._pbfs_busy()}

    @api.model
    def dev_sample(self):
        """The dev host's sample record (made on first open, administrator
        only — nothing is made at install)."""
        self._pbfs_check_admin()
        Sample = self.env['pb.form.sample']
        rec = Sample.search([('company_id', '=', self.env.company.id)], limit=1)
        if not rec:
            rec = Sample.create({'name': 'DEMO Lan Nguyen', 'email': 'lan.demo@example.com',
                                 'phone': '+84 90 000 0000', 'city': 'Ho Chi Minh City',
                                 'country_id': self.env.ref('base.vn').id,
                                 'date_start': fields.Date.today()})
        return rec.id
