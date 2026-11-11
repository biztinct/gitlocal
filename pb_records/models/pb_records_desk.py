# -*- coding: utf-8 -*-
"""`pb.records.desk` — the Records Desk's whole server side.

An AbstractModel, because the desk owns no records of its own: it is a facade
over the employee, contract, bank and contract-component destinations a pay
scheme MAPS, and every one of those already belongs to somebody else's model.

The one rule that shapes the whole file: **the desk reads and writes a mapped
field exactly the way an import does**. Every value goes through the same
helpers on `hr.payroll.import.batch` — `_mapped_record_value`,
`_coerce_mapped_value`, `_get_latest_contract`, `_get_employee_bank_partner` /
`_resolve_bank` / `_link_employee_bank_account`, `_get_contract_advantage_map`
/ `_get_or_create_advantage_template` — reached through a `.new()` probe, which
is the `preflight_spreadsheet` precedent (`pb_payrun_wizard.py:899`). Two
implementations of "what does this mapped field mean" would be two answers the
day one of them is edited.

Two things the batch helpers cannot do for us, and why:

  * `_mapped_record_value` returns the LABEL for a selection and the
    `display_name` for a many2one. A grid needs both halves — the key to write
    and the label to show — so the raw half is read off the record here while
    the LABEL still comes from that method, so what the desk displays and what
    an import sees can never drift.
  * `_coerce_mapped_value` validates a selection against its KEYS and returns
    `None` on a miss (`payroll_import_batch.py:1791`). A person picks a LABEL.
    Handing a label straight to it therefore blanks the field silently, which is
    the single worst failure this surface could have — so `_selection_key`
    turns a label into a key first, and says which choices exist when it cannot.

Nothing here writes before `apply_changes`, and `apply_changes` re-runs the
whole evaluation server-side rather than trusting the preview the client holds.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare
from odoo.tools.misc import format_date

from odoo.addons.pb_hr_payroll_formula.models.payroll_import_batch import (
    m2o_creates_missing, m2o_resolution_key)
from odoo.addons.pb_hr_payroll_formula.models.bank_account_util import (
    acc_numbers_match, sanitize_acc_number, sanitize_bank_text)
from odoo.addons.pb_records.models.records_approval import (
    LOCK_ERRORS, START_DATE_REACH)

_logger = logging.getLogger(__name__)

EMP = 'hr.employee'
CON = 'hr.contract'

#: The field types a card can offer an editor for. Anything else is not a
#: destination a person can type into, and a card that offered one would be an
#: offer the write would refuse (W29's shape).
TTYPES = ('char', 'text', 'integer', 'float', 'monetary', 'boolean',
          'date', 'datetime', 'selection', 'many2one')

#: `hr.employee` delegates its HR data to `hr.version` (`_inherits`), so a great
#: many perfectly writable destinations are RELATED and non-stored (MAPFIX E2).
#: Editability is therefore `field.readonly`, never `field.store`.
BANK_ROLE_LABELS = {
    'acc_number': 'Account number',
    'bank_name': 'Bank name',
    'bank_bic': 'SWIFT / BIC code',
    'acc_holder_name': 'Account holder name',
}
BANK_ROLE_ORDER = ('acc_number', 'bank_name', 'bank_bic', 'acc_holder_name')


class _LightRow:
    """A read-only stand-in for one record, for the shared read helpers.

    UPDATES P2a. `_mapped_record_value` and `_bank_record_value` take a
    mapping RECORD and read four or five of its attributes on every cell.
    Every attribute of every record passes through the access guard's
    `__getattribute__` hook, so a 4,575 × 73 sheet spent most of its time
    re-reading the same mapping row 333,000 times. This object answers the
    attributes those helpers ask for from plain Python attributes, copied
    once from the real row, and hands every other question to the real
    record — so the ONE implementation of "what does this mapped field
    hold" stays the only one. The record values themselves (`getattr(record,
    field.name)`) are still read through the guarded path.
    """

    def __init__(self, real, **values):
        self._real = real
        self.__dict__.update(values)

    def __getattr__(self, name):       # only for names not copied above
        return getattr(self._real, name)

    def __bool__(self):
        return bool(self._real)


class PbRecordsDesk(models.AbstractModel):
    _name = 'pb.records.desk'
    # FILTER W6 (2026-10-31): the WHO rail is the shared filter panel. Its
    # sections are the Employees list's own (the same words, so a person who
    # learnt one knows the other), plus the pay feed's employment status and
    # the hand-picked arrival from People.
    _inherit = ['pb.filter.mixin']
    _description = 'Records Desk'

    # =================================================================
    # Gates
    # =================================================================
    @api.model
    def _may_read(self):
        return (self.env.user.has_group('pb_records.group_records_viewer')
                or self.env.user.has_group('hr.group_hr_user')
                or self.env.user.has_group(
                    'pb_hr_payroll_base.group_payroll_base_officer')
                or self.env.user.has_group('base.group_system'))

    @api.model
    def _check_read(self):
        if not self._may_read():
            raise UserError(_(
                "You do not have access to employee records. Ask an "
                "administrator for the HR or Payroll Officer role."))

    @api.model
    def _may_export(self):
        return (self.env.user.has_group('pb_records.group_records_exporter')
                or self.env.user.has_group('hr.group_hr_user')
                or self.env.user.has_group('pb_hr_payroll_base.group_payroll_base_officer')
                or self.env.user.has_group('base.group_system'))

    @api.model
    def _may_write(self, model_name):
        """Can this person write on `model_name` at all?

        Asked ONCE per model and turned into a lock hint on the cards, so a cell
        this person could never save is read-only on screen instead of raising
        an access dialog after they have typed into forty of them.
        """
        if model_name in (EMP, CON) and self.env.user.has_group('pb_records.group_records_editor'):
            return True
        Model = self.env.get(model_name)
        if Model is None:
            return False
        try:
            Model.check_access('write')
            return True
        except Exception:       # noqa: BLE001 — an ACL question, not a crash
            return False

    # =================================================================
    # Schemes
    # =================================================================
    @api.model
    def _config_domain(self):
        domain = [('state', '!=', 'archived')]
        Config = self.env['hr.formula.config']
        if 'company_id' in Config._fields and self.env.companies:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', self.env.companies.ids)]
        return domain

    @api.model
    def _configs(self, config_id=0):
        """The schemes in scope. `config_id = 0` means every one of them."""
        Config = self.env['hr.formula.config'].sudo()
        configs = Config.search(self._config_domain(), order='sequence, id')
        if config_id:
            picked = configs.filtered(lambda c: c.id == int(config_id))
            return picked
        return configs

    @api.model
    def _default_config(self, configs):
        """The scheme the pay-run gate would pick, else the first one.

        Same answer as the wizard's, on purpose: a person who has just run
        payroll for a scheme and comes here to fix a field should not have to
        choose the scheme again.
        """
        Wizard = self.env.get('pb.payrun.wizard')
        if Wizard is not None:
            try:
                entries = Wizard.sudo()._spreadsheet_configs()
            except Exception:       # noqa: BLE001 — a preference, not a gate
                entries = []
            for entry in entries:
                cfg = entry.get('config')
                if cfg and cfg.id in configs.ids:
                    return cfg.id
        return configs[:1].id or 0

    @api.model
    def get_schemes(self):
        self._check_read()
        configs = self._configs(0)
        rows = []
        for cfg in configs:
            rows.append({
                'id': cfg.id,
                'name': cfg.display_name or cfg.name or '',
                'mapped_count': len(self._cards(cfg.id)),
                'is_default': False,
            })
        default_id = self._default_config(configs)
        for row in rows:
            row['is_default'] = row['id'] == default_id
        if len(rows) > 1:
            rows.insert(0, {'id': 0, 'name': _("All schemes"),
                            'mapped_count': len(self._cards(0)),
                            'is_default': False})
        return {'schemes': rows, 'default_id': default_id}

    # =================================================================
    # The field catalogue — MAPPED destinations only
    # =================================================================
    @api.model
    def _mappings(self, config_id):
        Mapping = self.env['hr.payslip.import.mapping'].sudo()
        configs = self._configs(config_id)
        if not configs:
            return Mapping
        # `order='id asc'`: the catalogue has no unique constraint, so duplicate
        # rows are possible and the LOWEST id wins — the same tie-break the
        # studio applies (`pb_formula_studio.py:342`).
        return Mapping.search([('salary_structure_id', 'in', configs.ids)],
                              order='id asc')

    @api.model
    def _component_rules(self, config_id):
        configs = self._configs(config_id)
        if not configs:
            return self.env['hr.formula.rule']
        return self.env['hr.formula.rule'].sudo().search(
            [('config_id', 'in', configs.ids),
             '|', ('is_contract_component', '=', True),
             ('is_text_component', '=', True)], order='id asc')

    @api.model
    def _studio(self):
        """`pb.formula.studio` when installed — it owns the catalogue HINTS.

        An optional dependency: the desk is perfectly usable without the hints,
        and hard-depending on the studio to explain a selection would be a
        dependency taken for a nicety.
        """
        return self.env.get('pb.formula.studio')

    @api.model
    def _notes(self):
        studio = self._studio()
        if studio is None:
            return {}
        out = {}
        for model in (EMP, CON):
            try:
                out[model] = studio.sudo()._ec_notes_for(model)
            except Exception:       # noqa: BLE001 — a hint is a nicety
                out[model] = {}
        return out

    @api.model
    def _selection_pairs(self, field):
        try:
            pairs = field._description_selection(self.env)
        except Exception:       # noqa: BLE001 — a selection needing a record
            pairs = []
        out = []
        for entry in (pairs or []):
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                out.append({'key': str(entry[0]), 'label': str(entry[1])})
            elif isinstance(entry, (list, tuple)) and entry:
                out.append({'key': str(entry[0]), 'label': str(entry[0])})
        return out

    @api.model
    def _cards(self, config_id):
        """`{card_id: card}` for every destination the scheme(s) map.

        Card ids carry their kind by inspection, the `b:` precedent the studio
        set: `f:<model>:<field>` · `b:<role>` · `c:<CODE>`. The private keys
        (prefixed `_`) hold the recordsets the writer needs and are stripped
        before anything crosses the wire.
        """
        notes = self._notes()
        cards = {}

        for mapping in self._mappings(config_id):
            rule = mapping.component_id
            sub = ''
            if rule:
                sub = _("%(name)s ← %(code)s") % {
                    'name': rule.name or rule.code or '', 'code': rule.code or ''}
            if mapping.destination_type == 'bank_account':
                role = mapping.bank_role
                if not role:
                    continue
                card_id = 'b:%s' % role
                if card_id in cards:
                    continue
                cards[card_id] = {
                    'id': card_id, 'group': 'bank',
                    'label': _(BANK_ROLE_LABELS.get(role) or role),
                    'sub': sub, 'ttype': 'bank', 'bank_role': role,
                    'selection': [], 'm2o': None,
                    'hint': {'text': _("Part of the employee's bank account."),
                             'title': _("Account number, bank, SWIFT/BIC and "
                                        "holder name are four columns that "
                                        "together make ONE bank account. A "
                                        "change is only saved when an account "
                                        "number results."),
                             'tone': ''},
                    'component': {'id': rule.id, 'code': rule.code or '',
                                  'name': rule.name or ''} if rule else None,
                    'editable': True,
                    'model': EMP,
                    '_mapping': mapping,
                }
                continue

            model_name = mapping.target_model_id.model or ''
            fname = mapping.target_field_id.name or ''
            if model_name not in (EMP, CON) or not fname:
                continue
            Model = self.env.get(model_name)
            if Model is None:
                continue
            field = Model._fields.get(fname)
            if field is None:
                continue
            card_id = 'f:%s:%s' % (model_name, fname)
            if card_id in cards:
                continue
            editable = (not field.readonly) and field.type in TTYPES
            card = {
                'id': card_id,
                'group': 'employee' if model_name == EMP else 'contract',
                'label': (mapping.target_field_id.field_description
                          or field.string or fname),
                'sub': sub,
                'ttype': field.type,
                'selection': (self._selection_pairs(field)
                              if field.type == 'selection' else []),
                'm2o': None,
                'hint': (notes.get(model_name) or {}).get(fname) or None,
                'component': {'id': rule.id, 'code': rule.code or '',
                              'name': rule.name or ''} if rule else None,
                'editable': editable,
                'model': model_name,
                'field': fname,
                '_mapping': mapping,
                '_field': field,
            }
            if field.type == 'many2one':
                comodel = self.env.get(field.comodel_name)
                if comodel is not None:
                    card['m2o'] = {
                        'comodel': field.comodel_name,
                        'creates_missing': m2o_creates_missing(comodel),
                        'key': m2o_resolution_key(comodel) or '',
                    }
            if not editable:
                card['hint'] = {
                    'text': _("Cannot be changed here"),
                    'title': _("This destination is read-only on the record, "
                               "so a value typed here would be dropped."),
                    'tone': 'warn'}
            cards[card_id] = card

        for rule in self._component_rules(config_id):
            code = (rule.code or '').strip()
            if not code:
                continue
            card_id = 'c:%s' % code
            if card_id in cards:
                continue
            cards[card_id] = self._component_card(rule, code)
        return cards

    @api.model
    def _component_card(self, rule, code):
        """The `c:<CODE>` card for one contract-component rule.

        UPDATES P2b: one builder, shared by the scheme catalogue above and
        the Updates-only "every pay item of every scheme" seam in
        `master_records.py`, so the two can never describe a pay item
        differently."""
        is_text = bool(rule.is_text_component)
        return {
            'id': 'c:%s' % code, 'group': 'component',
            'label': rule.name or code,
            'sub': _("Contract component · %s") % code,
            'ttype': 'text_component' if is_text else 'amount',
            'selection': [], 'm2o': None,
            'hint': {
                'text': (_("Text kept on the contract")
                         if is_text else _("Amount kept on the contract")),
                'title': _("Contract components live on the person's "
                           "contract, one line per component. Changing one "
                           "here writes that line and records the change."),
                'tone': ''},
            'component': {'id': rule.id, 'code': code,
                          'name': rule.name or ''},
            'editable': True,
            'model': CON,
            'code': code,
            '_rule': rule,
        }

    @api.model
    def _public_card(self, card):
        return {k: v for k, v in card.items() if not k.startswith('_')}

    @api.model
    def get_fields(self, config_id=0):
        self._check_read()
        cards = self._cards(config_id)
        writable = {EMP: self._may_write(EMP), CON: self._may_write(CON)}
        order = ('employee', 'contract', 'bank', 'component')
        labels = {
            'employee': _("Employee"), 'contract': _("Contract"),
            'bank': _("Bank"), 'component': _("Contract components"),
        }
        buckets = {k: [] for k in order}
        for card in cards.values():
            pub = self._public_card(card)
            if not writable.get(pub.get('model') or EMP, False):
                pub['editable'] = False
                pub['locked'] = True
            buckets[pub['group']].append(pub)
        groups = []
        for key in order:
            if key == 'bank':
                # The four bank roles read in the order somebody fills a paying-in
                # slip, not alphabetically.
                rows = sorted(buckets[key], key=lambda c: BANK_ROLE_ORDER.index(
                    c.get('bank_role')) if c.get('bank_role') in BANK_ROLE_ORDER
                    else 99)
            else:
                rows = sorted(buckets[key],
                              key=lambda c: (c['label'] or '').lower())
            if rows:
                groups.append({'key': key, 'label': labels[key], 'fields': rows})
        return {
            'groups': groups,
            'statuses': self._statuses(),
            'can_write': {'employee': writable[EMP], 'contract': writable[CON]},
            'can_export': self._may_export(),
        }

    # =================================================================
    # People
    # =================================================================
    @api.model
    def _statuses(self):
        Wizard = self.env.get('pb.payrun.wizard')
        if Wizard is None:
            return []
        try:
            return Wizard.sudo().employment_status_options() or []
        except Exception:       # noqa: BLE001 — a filter, never a blocker
            _logger.exception("Records Desk: could not read employment statuses")
            return []

    @api.model
    def _signals(self):
        Wizard = self.env.get('pb.payrun.wizard')
        if Wizard is None:
            return {}
        try:
            return Wizard.sudo()._employee_signals() or {}
        except Exception:       # noqa: BLE001
            return {}

    @api.model
    def _company_domain(self):
        ids = self.env.companies.ids
        if not ids:
            return []
        return ['|', ('company_id', '=', False), ('company_id', 'in', ids)]

    # =================================================================
    # The filter panel (pb_filter_kit, FILTER W6)
    #
    # The desk reads people under sudo behind its own gate (`_check_read`),
    # so the panel counts under sudo too, inside the same company scope —
    # and every kit door runs the same gate first.
    # =================================================================
    def _pbf_model(self):
        return EMP

    def _pbf_screen(self):
        return 'records'

    def _pbf_records(self):
        return self.env[EMP].sudo()

    def _pbf_base_domain(self):
        return list(self._company_domain()) + [('active', '=', True)]

    def _pbf_search_fields(self):
        return ['name', 'barcode', 'work_email', 'employee_id', 'job_title']

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    def _pbf_people(self):
        People = self.env.get('pb.people')
        return People if People is not None and hasattr(People, '_pbf_spec') else None

    def _pbf_sorts(self):
        People = self._pbf_people()
        if People is not None:
            return People._pbf_sorts()
        return [{'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'}]

    @api.model
    def _pbf_feed(self):
        """The pay feed's employment status for everyone — asked ONCE per
        request and kept on the cursor (RD11: never one question per person;
        F18/F25: every count in one panel load asks the same thing).

        `{'signals': {emp_id: {status, hours}}, 'by_status': {status: [ids]},
          'left': {status, …}}`
        """
        key = ('pb_records_feed', self.env.uid, tuple(self.env.companies.ids))
        cache = self.env.cr.cache
        if key in cache:
            return cache[key]
        signals = self._signals() or {}
        by_status = {}
        for emp_id, info in signals.items():
            status = str((info or {}).get('status') or '').strip()
            if status:
                by_status.setdefault(status, []).append(emp_id)
        left = set()
        try:
            from odoo.addons.pb_hr_payroll_formula.models import value_kind_classifier as vkc
            left = {s for s in by_status if vkc.is_left_status(s)}
        except Exception:       # noqa: BLE001 — a tone, never a blocker
            _logger.debug("Records Desk: left-status classifier unavailable", exc_info=True)
        cache[key] = {'signals': signals, 'by_status': by_status, 'left': left}
        return cache[key]

    def _pbf_employment_section(self):
        """Employment status as the pay feed reports it — one value per status
        the feed delivers (its own words: "Resigned", "Nghỉ việc"…), and the
        people it says nothing about. Ids come from `_pbf_feed`."""
        feed = self._pbf_feed()
        by_status = feed['by_status']
        if not by_status:
            return None
        stated = sorted({i for ids in by_status.values() for i in ids})
        options = [{
            'value': status, 'label': status,
            'tone': 'rose' if status in feed['left'] else 'green',
            'domain': [('id', 'in', ids)],
        } for status, ids in sorted(by_status.items(), key=lambda kv: -len(kv[1]))]
        options.append({'value': '__none', 'label': _('Not stated in the feed'), 'tone': 'slate',
                        'domain': [('id', 'not in', stated)]})
        return {'key': 'employment', 'label': _('Employment status'), 'icon': 'activity',
                'group': 'people', 'type': 'choice', 'pinned': True,
                'help': _('What the pay feed says, which can differ from the employee record.'),
                'options': options}

    def _pbf_picked_ids(self):
        ids = self._pbf_ctx().get('picked') or []
        try:
            return [int(i) for i in ids][:5000]
        except (TypeError, ValueError):
            return []

    def _pbf_spec(self):
        People = self._pbf_people()
        spec = [dict(s) for s in People._pbf_spec()] if People is not None else []
        # The Employees list pins Contract status, Payroll-ready, Department;
        # here the third question is the feed's employment status.
        for s in spec:
            if s.get('key') == 'ready':
                s['pinned'] = False
        employment = self._pbf_employment_section()
        if employment:
            at = next((i for i, s in enumerate(spec) if s.get('key') == 'department'), len(spec) - 1) + 1
            spec.insert(at, employment)
        picked = self._pbf_picked_ids()
        if picked:
            # Arrived from People with a selection: a section of its own, so
            # the chip says so and its x lets everybody back in.
            spec.insert(0, {
                'key': 'picked', 'label': _('Hand-picked'), 'icon': 'users',
                'group': 'people', 'type': 'choice',
                'options': [
                    {'value': 'yes', 'label': _('The people you picked'), 'tone': 'blue',
                     'domain': [('id', 'in', picked)]},
                    {'value': 'no', 'label': _('Everybody else'), 'tone': 'slate',
                     'domain': [('id', 'not in', picked)]},
                ]})
        return spec

    def _pbf_builtin_views(self):
        views = [
            {'key': 'all', 'label': _('All people'), 'icon': 'users', 'filters': {}},
            {'key': 'running', 'label': _('Running contracts'), 'filters': {'status': ['open']}},
            {'key': 'nocontract', 'label': _('No contract'), 'filters': {'status': ['none']}},
        ]
        left = sorted(self._pbf_feed()['left'])
        if left:
            views.append({'key': 'left', 'label': _('Resigned per feed'),
                          'filters': {'employment': left}})
        if self._pbf_picked_ids():
            views.append({'key': 'picked', 'label': _('Hand-picked'), 'icon': 'users',
                          'filters': {'picked': ['yes']}})
        return views

    @api.model
    def _pbf_worth_showing(self, s, base):
        # the arrival section is never offered as a filter of its own: it is
        # on (a chip) when somebody arrives with a selection, and gone once
        # they let everybody back in
        if s.get('key') == 'picked':
            return False
        return super()._pbf_worth_showing(s, base)

    @api.model
    def pbf_layout(self):
        if not self._may_read():
            return {'refused': _("You do not have access to employee records. Ask an "
                                 "administrator for the HR or Payroll Officer role.")}
        return super().pbf_layout()

    @api.model
    def pbf_counts(self, filters=None, search=None, keys=None, **kw):
        # **kw rides every kit argument through (kit 1.3.0 added `views`).
        self._check_read()
        return super().pbf_counts(filters=filters, search=search, keys=keys, **kw)

    @api.model
    def pbf_find_values(self, key, query, filters=None, search=None):
        self._check_read()
        return super().pbf_find_values(key, query, filters=filters, search=search)

    @api.model
    def _kit_payload(self, filters):
        """`{'pbf': {...}, 'search': '…'}` is the panel's state, as the
        desk's bulk doors (select all matching, export) now send it."""
        return isinstance(filters, dict) and isinstance(filters.get('pbf'), dict)

    @api.model
    def _people_domain(self, filters, skip=None):
        """The employee domain, with one facet optionally left out.

        `skip` is what makes the facet counts honest: a chip must say how many
        people it would ADD, which means counting with every other filter on and
        its own filter off.
        """
        filters = filters or {}
        domain = list(self._company_domain())
        q = (filters.get('q') or '').strip()
        if q:
            domain += ['|', '|', '|',
                       ('name', 'ilike', q), ('barcode', 'ilike', q),
                       ('work_email', 'ilike', q), ('employee_id', 'ilike', q)]
        if skip != 'departments' and filters.get('department_ids'):
            domain.append(('department_id', 'in',
                           [int(i) for i in filters['department_ids']]))
        if skip != 'jobs' and filters.get('job_ids'):
            domain.append(('job_id', 'in', [int(i) for i in filters['job_ids']]))
        if filters.get('employee_ids'):
            # Intersects, never overrides (the wizard's rule, `:57`).
            domain.append(('id', 'in', [int(i) for i in filters['employee_ids']]))
        return domain

    # -----------------------------------------------------------------
    # The scale rail.
    #
    # Payobook's roster is 4,533 people, and the first version of this section
    # asked each of them a question ONE AT A TIME: `_contract_state` sorted an
    # employee's `contract_ids` per person, per facet, four facets deep, on
    # every page fetch. The measured cost of one page was 147 SECONDS (RD11).
    #
    # Two rules came out of it and both are load-bearing:
    #   1. a per-person question is asked ONCE for the whole roster and kept in
    #      a dict for the rest of the request (`_ctx`);
    #   2. the FACETS are computed only when they are asked for — the client
    #      needs them on the first page and never again as the window moves.
    # -----------------------------------------------------------------
    @api.model
    def _ctx_states(self, ctx):
        """`{employee_id: contract state}` for everyone in scope — ONE query.

        The latest contract wins, which is what `_get_latest_contract` means by
        "no dates set": ordering by `date_start` ascending and letting the last
        row overwrite gives the same answer as sorting per person, at 1/4500th
        of the cost.
        """
        if 'states' in ctx:
            return ctx['states']
        out = {}
        rows = self.env[CON].sudo().search_read(
            self._company_domain(), ['employee_id', 'state'],
            order='date_start asc, id asc')
        for row in rows:
            if row.get('employee_id'):
                out[row['employee_id'][0]] = row['state']
        ctx['states'] = out
        return out

    @api.model
    def _ctx_signals(self, ctx):
        if 'signals' not in ctx:
            ctx['signals'] = self._signals()
        return ctx['signals']

    @api.model
    def _ctx_statuses(self, ctx):
        """`employment_status_options` walks every scheme on the database — 19
        of them on payobook — so it is asked once per request, not once per
        facet."""
        if 'statuses' not in ctx:
            ctx['statuses'] = self._statuses()
        return ctx['statuses']

    @api.model
    def _apply_post_filters(self, employees, filters, skip=None, ctx=None):
        """Contract state and employment status — neither is an employee field.

        The employment status is read from the FEED signal, exactly as the pay
        run wizard reads it (`pb_payrun_wizard.py:59-62`): on ABM every employee
        is active with a running contract while the source reports 85 Resigned,
        so filtering on the record would be a filter that does nothing.
        """
        filters = filters or {}
        ctx = {} if ctx is None else ctx
        states = filters.get('contract_states') or []
        statuses = filters.get('statuses') or []
        if skip != 'contract_states' and states:
            wanted = set(states)
            by_emp = self._ctx_states(ctx)
            employees = employees.filtered(
                lambda e: by_emp.get(e.id, 'none') in wanted)
        if skip != 'statuses' and statuses:
            wanted = {str(s or '').strip() for s in statuses}
            signals = self._ctx_signals(ctx)
            employees = employees.filtered(
                lambda e: (signals.get(e.id, {}).get('status') or '') in wanted)
        return employees

    @api.model
    def _matching(self, filters, skip=None, ctx=None):
        Employee = self.env[EMP].sudo()
        if self._kit_payload(filters):
            # FILTER W6: the panel's state — one domain, the same one the
            # grid's pages and the panel's counts are built from.
            domain = self.pbf_domain(filters['pbf'], filters.get('search') or '')
            return Employee.search(domain, order=self.pbf_order(filters.get('sort')) or 'name, id')
        employees = Employee.search(self._people_domain(filters, skip=skip),
                                    order='name, id')
        return self._apply_post_filters(employees, filters, skip=skip, ctx=ctx)

    @api.model
    def _person_row(self, probe, picked, emp, signals, memo=None):
        contract = probe._get_latest_contract(emp) or self.env[CON]
        values = {}
        for card in picked:
            values[card['id']] = self._read_cell(probe, card, emp, contract, memo)
        return {
            'id': emp.id,
            'name': emp.display_name or emp.name or '',
            'code': emp.barcode or emp.employee_id or '',
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'department': emp.department_id.display_name or '',
            'job': emp.job_id.display_name or emp.job_title or '',
            'contract_id': contract.id or False,
            'contract_state': contract.state if contract else 'none',
            'status': (signals.get(emp.id) or {}).get('status') or '',
            'values': values,
        }

    @api.model
    def search_page(self, config_id=0, filters=None, search=None, sort=None,
                    field_ids=None, offset=0, limit=100):
        """One window of the grid for the filter panel's state (FILTER W6).

        One domain, one indexed search and one count; the feed status is the
        cursor-cached `_pbf_feed` (asked once per request, RD11). No facets:
        the panel counts its own sections."""
        self._check_read()
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or 100), 500))
        except (TypeError, ValueError):
            offset, limit = 0, 100
        Employee = self.env[EMP].sudo()
        domain = self.pbf_domain(filters or {}, search)
        total = Employee.search_count(domain)
        page = Employee.search(domain, order=self.pbf_order(sort) or 'name, id',
                               offset=offset, limit=limit)
        cards = self._cards(config_id)
        picked = [cards[fid] for fid in (field_ids or []) if fid in cards]
        probe = self._probe(config_id)
        signals = self._pbf_feed()['signals']
        memo = {}
        rows = [self._person_row(probe, picked, emp, signals, memo) for emp in page]
        return {'total': total, 'offset': offset, 'rows': rows}

    @api.model
    def search_people(self, config_id=0, filters=None, field_ids=None,
                      offset=0, limit=100, with_facets=None):
        self._check_read()
        filters = filters or {}
        ctx = {}
        cards = self._cards(config_id)
        picked = [cards[fid] for fid in (field_ids or []) if fid in cards]
        employees = self._matching(filters, ctx=ctx)
        total = len(employees)
        page = employees[int(offset):int(offset) + int(limit)]
        probe = self._probe(config_id)
        # The row's own status chip needs the signals; the facets need them too,
        # and both read the one copy in `ctx`.
        signals = self._ctx_signals(ctx) if self._ctx_statuses(ctx) else {}
        memo = {}
        rows = [self._person_row(probe, picked, emp, signals, memo) for emp in page]
        wants_facets = (int(offset) == 0) if with_facets is None else bool(with_facets)
        return {'total': total, 'offset': int(offset), 'rows': rows,
                'facets': self._facets(filters, ctx) if wants_facets else None}

    @api.model
    def _facets(self, filters, ctx=None):
        """The chips on the left, each counted with its OWN filter dropped.

        A chip has to say how many people it would ADD, which is the count with
        every other filter on and this one off — hence four match sets. Each is
        an indexed `search`; the counting is a `_read_group` for the two facets
        that are employee columns and a dict lookup for the two that are not.
        Never a per-employee question (RD11).
        """
        ctx = {} if ctx is None else ctx
        Employee = self.env[EMP].sudo()

        def grouped(skip, fname):
            ids = self._matching(filters, skip=skip, ctx=ctx).ids
            if not ids:
                return []
            out = []
            for record, count in Employee._read_group(
                    [('id', 'in', ids)], [fname], ['__count']):
                out.append({'id': record.id if record else 0,
                            'name': (record.display_name if record
                                     else _("Not set")),
                            'count': count})
            return sorted(out, key=lambda r: -r['count'])

        def tallied(skip, key):
            counts = {}
            for emp_id in self._matching(filters, skip=skip, ctx=ctx).ids:
                value = key(emp_id)
                counts[value] = counts.get(value, 0) + 1
            return counts

        by_emp = self._ctx_states(ctx)
        state_counts = tallied('contract_states',
                               lambda i: by_emp.get(i, 'none'))
        if self._ctx_statuses(ctx):
            signals = self._ctx_signals(ctx)
            status_counts = tallied(
                'statuses', lambda i: (signals.get(i) or {}).get('status') or '')
        else:
            status_counts = {}

        state_labels = dict(self.env[CON]._fields['state']._description_selection(
            self.env)) if 'state' in self.env[CON]._fields else {}
        state_labels['none'] = _("No contract")
        return {
            'departments': grouped('departments', 'department_id'),
            'jobs': grouped('jobs', 'job_id'),
            'contract_states': sorted(
                [{'id': s, 'name': state_labels.get(s, s), 'count': n}
                 for s, n in state_counts.items()], key=lambda r: -r['count']),
            'statuses': sorted(
                [{'id': s, 'name': s or _("Not stated"), 'count': n}
                 for s, n in status_counts.items()], key=lambda r: -r['count']),
        }

    @api.model
    def matching_ids(self, filters=None):
        """Every employee the filters match, ids only.

        "Select all 4,500 matching" has to mean the whole match set, not the
        pages that happen to be loaded — and a person who asked for all of them
        does not want to wait for 4,500 rows of values to come back first.

        FILTER W6: the desk sends the filter panel's state as
        `{'pbf': filters, 'search': text}` and this runs `pbf_domain` — the
        ids are exactly the panel's matched count.
        """
        self._check_read()
        return self._matching(filters or {}).ids

    @api.model
    def lookup_m2o(self, comodel, term='', limit=12):
        self._check_read()
        Model = self.env.get(comodel)
        if Model is None:
            return []
        key = m2o_resolution_key(Model)
        if not key:
            return []
        domain = []
        if 'company_id' in Model._fields and self.env.companies:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', self.env.companies.ids)]
        if term:
            domain.append((key, 'ilike', term))
        records = Model.sudo().search(domain, limit=int(limit))
        return [{'id': r.id, 'label': r.display_name or ''} for r in records]

    # =================================================================
    # Reading one cell
    # =================================================================
    @api.model
    def _probe(self, config_id):
        """A `.new()` batch, purely so the shared read/write helpers are METHODS
        we can call. It is never saved and it never sees a file — the
        `preflight_spreadsheet` precedent (`pb_payrun_wizard.py:899`)."""
        configs = self._configs(config_id)
        vals = {}
        if len(configs) == 1:
            vals['formula_config_id'] = configs.id
        elif configs:
            vals['formula_config_id'] = configs[0].id
        return self.env['hr.payroll.import.batch'].sudo().new(vals)

    @api.model
    def _advantage_line(self, probe, contract, code, memo=None):
        if not contract:
            return None
        if memo is None:
            return probe._get_contract_advantage_map(contract).get(code)
        # UPDATES P2a: one walk of a contract's lines per call, not one per
        # cell — 26 components × 4,575 people walked every line every time.
        key = ('adv', contract.id)
        lines = memo.get(key)
        if lines is None:
            lines = memo[key] = probe._get_contract_advantage_map(contract)
        return lines.get(code)

    @api.model
    def _light_mapping(self, card):
        """The card's mapping as a `_LightRow` — built once per card, per
        call (cards are rebuilt by every `_cards()` call, so this never
        outlives a request). See `_LightRow` for why."""
        light = card.get('_light')
        if light is None:
            mapping = card['_mapping']
            values = {'destination_type': mapping.destination_type}
            if mapping.destination_type == 'bank_account':
                values['bank_role'] = mapping.bank_role
            else:
                model = mapping.target_model_id
                field = mapping.target_field_id
                values['target_model_id'] = _LightRow(model, model=model.model)
                values['target_field_id'] = _LightRow(
                    field, name=field.name, ttype=field.ttype)
            light = card['_light'] = _LightRow(mapping, **values)
        return light

    @api.model
    def _read_cell(self, probe, card, employee, contract, memo=None):
        """`{v, label}` — the raw value to compare/write and the text to show.

        The LABEL of a selection or a many2one comes from
        `_mapped_record_value`, so the desk shows exactly what an import sees;
        the raw half is read off the record here because that method returns
        only the label and a grid needs the key it will write back.

        `memo` (UPDATES P2a, optional) is the caller's per-call dict; with it
        a contract's component lines are walked once, not once per cell.
        """
        kind = card['id'][:1]
        if kind == 'f':
            record = employee if card['model'] == EMP else contract
            if not record:
                return {'v': None, 'label': '', 'missing': True}
            field = card['_field']
            raw = record[card['field']]
            label_key = None
            if memo is not None:
                # The label is a function of (field, value) alone — the helper
                # reads exactly `record[field]` and formats it — so one call
                # per distinct value answers every cell holding that value:
                # 4,575 people in 30 departments ask it 30 times, not 4,575.
                label_key = ('label', card['id'],
                             raw.id if field.type == 'many2one' else raw)
                try:
                    if label_key in memo:
                        label = memo[label_key]
                    else:
                        label = memo[label_key] = probe._mapped_record_value(
                            self._light_mapping(card), contract=contract,
                            employee=employee)
                except TypeError:          # an unhashable value: ask directly
                    label_key = None
            if label_key is None:
                label = probe._mapped_record_value(
                    self._light_mapping(card), contract=contract,
                    employee=employee)
            if field.type == 'many2one':
                return {'v': raw.id or False, 'label': str(label or '')}
            if field.type == 'boolean':
                return {'v': bool(raw),
                        'label': _("Yes") if raw else _("No")}
            if field.type in ('integer', 'float', 'monetary'):
                # `0` is a VALUE, not an empty cell (MJ15) — and it must not be
                # tested with `raw in (None, False)`, because in Python
                # `0.0 == False`, which blanked every zero salary on the live
                # walk (RD10).
                number = raw if isinstance(raw, (int, float)) else 0
                return {'v': number, 'label': self._num(number)}
            if field.type in ('date', 'datetime'):
                return {'v': str(label or ''), 'label': str(label or '')}
            if field.type == 'selection':
                return {'v': raw or False, 'label': str(label or '')}
            return {'v': raw if raw not in (None, False) else '',
                    'label': str(label or '')}
        if kind == 'b':
            value = probe._bank_record_value(self._light_mapping(card),
                                             employee=employee)
            return {'v': value or '', 'label': str(value or '')}
        if kind == 'c':
            if not contract:
                return {'v': None, 'label': '', 'missing': True}
            line = self._advantage_line(probe, contract, card['code'], memo)
            if card['ttype'] == 'text_component':
                text = (line.text_value if line else '') or ''
                return {'v': text, 'label': text}
            # An absent line has never answered this input. Keep it distinct
            # from an explicitly saved zero, including during import preview.
            if not line:
                return {'v': None, 'label': ''}
            amount = line.amount or 0.0
            return {'v': amount, 'label': self._word_label(card, amount)}
        return {'v': None, 'label': ''}

    @api.model
    def _word_label(self, card, amount):
        """PDR P2 W4 — a component whose rule has words reads them ("Yes",
        "All tax"); everything else, and an unmatched number, reads the number."""
        rule = card.get('_rule')
        word = rule.value_label_for(amount) if rule is not None and hasattr(rule, 'value_label_for') else ''
        return word or self._num(amount)

    @api.model
    def _num(self, value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return ''
        if float_compare(number, round(number), precision_digits=6) == 0:
            return '{:,.0f}'.format(number)
        return '{:,.2f}'.format(number)

    # =================================================================
    # Coercion — a person's words into a value the record accepts
    # =================================================================
    @api.model
    def _selection_key(self, field, value):
        """A selection LABEL (or key) into the KEY, or a sentence saying why not.

        `_coerce_mapped_value` validates against KEYS and returns `None` on a
        miss (`payroll_import_batch.py:1791`), so handing it a label blanks the
        field without a word. Everything a person can type reaches the record
        through here first.

        The pairs come from `field._description_selection(env)` on the MODEL
        field — never `ir.model.fields.selection`, which is a Char holding the
        definition as TEXT and which `dict()` walks one character at a time
        (MF24, and the reason all 152 of ABM's lines once failed).
        """
        pairs = self._selection_pairs(field)
        text = '' if value is None else str(value).strip()
        if not text:
            return False, None
        by_key = {p['key']: p['key'] for p in pairs}
        if text in by_key:
            return text, None
        lowered = {}
        for pair in pairs:
            lowered.setdefault(pair['label'].strip().lower(), pair['key'])
            lowered.setdefault(pair['key'].strip().lower(), pair['key'])
        if text.lower() in lowered:
            return lowered[text.lower()], None
        shown = ", ".join(p['label'] for p in pairs[:12])
        if len(pairs) > 12:
            shown = _("%(list)s and %(n)s more") % {
                'list': shown, 'n': len(pairs) - 12}
        return None, _("'%(value)s' is not one of the choices — use %(list)s") % {
            'value': text, 'list': shown or _("one of this field's choices")}

    @api.model
    def _bool(self, value):
        if isinstance(value, bool):
            return value, None
        text = str(value if value is not None else '').strip().lower()
        if text in ('1', 'true', 'yes', 'y', 't', 'on'):
            return True, None
        if text in ('0', 'false', 'no', 'n', 'f', 'off', ''):
            return False, None
        return None, _("'%(value)s' is not a yes or a no — use Yes or No") % {
            'value': value}

    # -----------------------------------------------------------------
    # Typed names for linked records (UPDATES P2a).
    #
    # The first version searched `[(key, '=ilike', text)], limit=1` with no
    # company scope: first hit wins. On payobook an untouched full sheet read
    # as 9,933 changes — namesake working hours and managers picked instead of
    # the current one, and a department's full path ("A / B") proposed as a
    # NEW department (ledger G11). The ladder below never guesses: the current
    # value first, then one exact match inside the companies in scope (the
    # full path for a department), and a sentence when there are two.
    # -----------------------------------------------------------------
    @staticmethod
    def _m2o_norm(text):
        return ' '.join(str(text if text is not None else '').split()).lower()

    @api.model
    def _m2o_is_current(self, current, key, text):
        """Does `text` name the record already there? Case- and
        whitespace-insensitive, against what the screen shows (display
        name), the matching key, and the full path where there is one."""
        if not current:
            return False
        wanted = self._m2o_norm(text)
        if not wanted:
            return False
        shown = [current.display_name, current[key]]
        if 'complete_name' in current._fields:
            shown.append(current.complete_name)
        return any(self._m2o_norm(s) == wanted for s in shown if s)

    @api.model
    def _m2o_hits(self, Model, fname, text, scope):
        """Records whose `fname` is `text`, case-insensitively, in scope.

        `=ilike` is an exact match unless the text carries `%` or `_`, which
        ILIKE reads as wildcards; then every candidate is fetched and only
        the exact ones are kept, so "R_D" can never mean "RxD"."""
        wild = '%' in text or '_' in text
        hits = Model.search([(fname, '=ilike', text)] + scope,
                            limit=None if wild else 3)
        if wild:
            low = text.lower()
            hits = hits.filtered(lambda r: str(r[fname] or '').lower() == low)
        return hits

    @api.model
    def _m2o_lookup(self, field, comodel, key, text, memo=None):
        """Rungs 2-5 for one `(comodel, text)`, memoised in `memo` for the
        life of ONE `_evaluate` call: 4,575 rows naming 30 departments ask
        the database 30 times, not 4,575. The memo is a plain dict the caller
        owns — never a cache that outlives the request."""
        memo_key = ('m2o', comodel._name, text)
        if memo is not None and memo_key in memo:
            return memo[memo_key]
        answer = self._m2o_ladder(field, comodel, key, text)
        if memo is not None:
            memo[memo_key] = answer
        return answer

    @api.model
    def _m2o_ladder(self, field, comodel, key, text):
        Model = comodel.sudo()
        scope = []
        if 'company_id' in Model._fields:
            scope = ['|', ('company_id', '=', False),
                     ('company_id', 'in', self.env.companies.ids)]
        if comodel._name == EMP:
            return self._m2o_employee(Model, text, scope)
        # Rung 2 — one exact match inside the companies in scope (archived
        # records stay out: the default active filter applies).
        fname = key
        hits = self._m2o_hits(Model, fname, text, scope)
        # Rung 3 — a department's full path, "Parent / Child". In this build
        # `complete_name` is computed but searchable, so "searchable" is the
        # test, not "stored".
        path = Model._fields.get('complete_name')
        has_path = path is not None
        if not hits and has_path and key != 'complete_name' \
                and (path.store or path.search):
            fname = 'complete_name'
            hits = self._m2o_hits(Model, fname, text, scope)
        if len(hits) == 1:
            return hits.id, hits.display_name or text, None
        what = (self.env['ir.model'].sudo()._get(field.comodel_name).name
                or field.comodel_name).lower()
        if len(hits) > 1:
            # Rung 4 — never pick. The count is the real one, not the limit.
            count = len(hits)
            if count >= 3 and not ('%' in text or '_' in text):
                domain = [(fname, '=ilike', text)] + scope
                count = max(count, Model.search_count(domain))
            return None, '', _(
                "%(n)s %(what)s records are called '%(value)s'. Pick the right "
                "one on the Records screen, or use a name that is unique."
            ) % {'n': count, 'what': what, 'value': text}
        # Rung 5 — nothing. A slashed path is a full name somebody meant to
        # exist; turning it into a new record would invent "A / B" as one
        # department's name.
        if has_path and '/' in text:
            return None, '', _(
                "No %(what)s is called '%(value)s'. Check the full name, "
                "including the part before the slash."
            ) % {'what': what, 'value': text}
        if not m2o_creates_missing(comodel):
            return None, '', _(
                "No %(what)s called '%(value)s' exists, and %(what)s records "
                "are not created here.") % {'what': what, 'value': text}
        # Deliberately NOT created during a preview — the create happens in
        # `_write_cell`, inside the apply transaction.
        return {'create': text}, _("%s (new)") % text, None

    #: The fields a person's employee code can live in — the row matcher's
    #: own list (`pb_records_io.CODE_FIELDS`), so "the code" means the same
    #: thing for finding a row's person and for naming their manager.
    EMPLOYEE_CODE_FIELDS = ('barcode', 'employee_id', 'pb_source_ref',
                            'identification_id')

    @api.model
    def _m2o_count(self, Model, fname, text, scope, hits):
        count = len(hits)
        if count >= 3 and not ('%' in text or '_' in text):
            count = max(count, Model.search_count([(fname, '=ilike', text)] + scope))
        return count

    @api.model
    def _m2o_employee(self, Model, text, scope):
        """UPDATES P2c (owner decision D9) — a manager or coach, typed.

        After "it is already this person" (rung 1, in `_coerce`):
          2. an employee CODE, exact and case-insensitive, across the code
             fields the row matcher uses — one person wins, two are refused;
          3. a WORK EMAIL, exact and case-insensitive — one person wins;
          4. the NAME, exactly as before — namesakes are refused, and a file
             is told what to type instead;
          5. nobody — refused. A file never creates an employee.
        Company scope as every other look-up."""
        codes = Model.browse()
        for fname in self.EMPLOYEE_CODE_FIELDS:
            field = Model._fields.get(fname)
            if field is not None and field._description_searchable:
                codes |= self._m2o_hits(Model, fname, text, scope)
        if len(codes) == 1:
            return codes.id, codes.display_name or text, None
        if len(codes) > 1:
            return None, '', _(
                "%(n)s people have the employee code '%(value)s'. Type the "
                "work email of the right one instead.") % {
                    'n': len(codes), 'value': text}
        if '@' in text and 'work_email' in Model._fields:
            mails = self._m2o_hits(Model, 'work_email', text, scope)
            if len(mails) == 1:
                return mails.id, mails.display_name or text, None
            if len(mails) > 1:
                return None, '', _(
                    "%(n)s people use the work email '%(value)s'. Type the "
                    "employee code of the right one instead.") % {
                        'n': self._m2o_count(Model, 'work_email', text, scope,
                                             mails), 'value': text}
        names = self._m2o_hits(Model, 'name', text, scope)
        if len(names) == 1:
            return names.id, names.display_name or text, None
        if len(names) > 1:
            count = self._m2o_count(Model, 'name', text, scope, names)
            if self.env.context.get('records_from_file'):
                return None, '', _(
                    "%(n)s people are called '%(value)s'. Type the employee "
                    "code or work email of the right one instead.") % {
                        'n': count, 'value': text}
            what = (self.env['ir.model'].sudo()._get(EMP).name or EMP).lower()
            return None, '', _(
                "%(n)s %(what)s records are called '%(value)s'. Pick the right "
                "one on the Records screen, or use a name that is unique."
            ) % {'n': count, 'what': what, 'value': text}
        return None, '', _(
            "Nobody is called '%(value)s'. Check the spelling, or use their "
            "employee code or work email.") % {'value': text}

    @api.model
    def _field_required(self, field):
        """Is this destination required on the record it lives on?

        `hr.employee` delegates much of its data to `hr.version`, and a
        related field does not always carry its target's `required`, so the
        target is asked too."""
        if field.required:
            return True
        target = getattr(field, 'related_field', None) if field.related else None
        return bool(target is not None and target.required)

    @api.model
    def _coerce(self, probe, card, value, employee, contract, memo=None):
        """`(coerced, label, why)` — `why` is a plain sentence and means refused.

        `''` is an explicit CLEAR (the column menu's "Clear for selected" and an
        emptied cell are the same gesture), not a missing value.

        `memo` (UPDATES P2a, optional) is the caller's per-evaluation dict for
        typed-name look-ups; without it every look-up asks the database.
        """
        kind = card['id'][:1]
        if not card.get('editable'):
            return None, '', _(
                "%s cannot be changed here — it is read-only on the record.") \
                % card['label']

        # UPDATES P2b — an explicit CLEAR from a file (`records_strict_clear`,
        # set only by the Updates screen). The Records screen never sets it,
        # so its own "Clear for selected" keeps exactly today's behaviour.
        strict = bool(self.env.context.get('records_strict_clear'))
        emptied = value is None or (isinstance(value, str) and not value.strip())

        if kind == 'c':
            if card['ttype'] == 'text_component':
                text = '' if value is None else str(value).strip()
                return text, text, None
            if value in (None, ''):
                if strict:
                    return 0.0, self._word_label(card, 0.0), None
                return 0.0, '', None
            rule = card.get('_rule')
            try:
                amount = float(str(value).replace(',', '').strip())
            except (TypeError, ValueError):
                if rule is not None and hasattr(rule, 'value_from_text') and rule.value_label_options():
                    # PDR P2 — "Yes" / "N" / "All tax" for a worded component.
                    try:
                        amount = rule.value_from_text(value, card.get('label'))
                    except ValueError as error:
                        return None, '', str(error)
                    return amount, self._word_label(card, amount), None
                return None, '', _(
                    "'%(value)s' is not a number — type an amount like 1500000."
                ) % {'value': value}
            return amount, self._word_label(card, amount), None

        if kind == 'b':
            if strict and emptied:
                return None, '', _(
                    "Bank details cannot be removed from a file. Change them "
                    "on the employee record.")
            text = '' if value is None else str(value).strip()
            if card['bank_role'] == 'acc_number' and text:
                # `sanitize_acc_number` returns `(number, damaged)` — the second
                # half is the point of it: a value that WAS there and cannot be
                # trusted is refused rather than quietly dropped.
                cleaned, damaged = sanitize_acc_number(text)
                if damaged or not cleaned:
                    return None, '', _(
                        "'%(value)s' does not look like an account number — "
                        "use digits and letters only."
                    ) % {'value': text}
                return cleaned, cleaned, None
            return text, text, None

        field = card['_field']
        record = employee if card['model'] == EMP else contract
        if not record:
            return None, '', _(
                "%s has no contract, so there is nothing to change."
            ) % (employee.display_name or _("This person"))

        ftype = field.type
        if strict and emptied and self._field_required(field):
            return None, '', _("%s cannot be empty.") % card['label']
        if value in (None, ''):
            # An emptied cell clears the destination. Numbers go to zero because
            # a numeric column on a record is not nullable; everything else goes
            # to the ORM's own empty.
            if ftype in ('integer', 'float', 'monetary'):
                return 0.0, '', None
            return False, '', None

        if ftype == 'selection':
            key, why = self._selection_key(field, value)
            if why:
                return None, '', why
            labels = {p['key']: p['label'] for p in self._selection_pairs(field)}
            return key, labels.get(key, key), None

        if ftype == 'boolean':
            flag, why = self._bool(value)
            if why:
                return None, '', why
            return flag, _("Yes") if flag else _("No"), None

        if ftype == 'many2one':
            comodel = self.env.get(field.comodel_name)
            if comodel is None:
                return None, '', _("%s cannot be changed here.") % card['label']
            if isinstance(value, dict):
                rec_id = value.get('id')
                if rec_id:
                    target = comodel.sudo().browse(int(rec_id)).exists()
                    if not target:
                        return None, '', _("That choice no longer exists.")
                    return target.id, target.display_name or '', None
                value = value.get('label') or value.get('name') or ''
            text = str(value).strip()
            key = m2o_resolution_key(comodel)
            if not key:
                return None, '', _(
                    "%s has no name to match against, so it cannot be typed in "
                    "here.") % card['label']
            # UPDATES P2a, rung 1 — IT IS ALREADY THIS. Text that says what
            # the record holds today keeps today's record, so a namesake can
            # never displace the value that is already there (ledger G11).
            current = record[card['field']]
            if self._m2o_is_current(current, key, text):
                return current.id, current.display_name or text, None
            return self._m2o_lookup(field, comodel, key, text, memo)

        # char / text / numbers / date / datetime all go through the shared
        # coercer, which is what an import would do with the same cell.
        coerced = probe._coerce_mapped_value(record, field, value)
        if coerced is None:
            if ftype in ('integer', 'float', 'monetary'):
                return None, '', _(
                    "'%(value)s' is not a number — type an amount like 1500000."
                ) % {'value': value}
            if ftype in ('date', 'datetime'):
                return None, '', _(
                    "'%(value)s' is not a date — use a date like 2026-08-29."
                ) % {'value': value}
            return None, '', _("'%(value)s' cannot be stored in %(label)s.") % {
                'value': value, 'label': card['label']}
        if ftype in ('date', 'datetime'):
            return coerced, str(coerced), None
        if ftype in ('integer', 'float', 'monetary'):
            return coerced, self._num(coerced), None
        return coerced, str(coerced), None

    # =================================================================
    # Preview
    # =================================================================
    @api.model
    def _whitelist(self, config_id, changes):
        """The rail. A field id the scheme does not map never reaches a write.

        Raised BEFORE anything is written, and raised rather than refused per
        row, because an unknown destination is not a person's mistake — it is a
        stale screen or a tampered payload, and continuing with the rest of the
        batch would apply half of something nobody asked for.
        """
        cards = self._cards(config_id)
        unknown = sorted({str(c.get('field_id') or '') for c in (changes or [])
                          if str(c.get('field_id') or '') not in cards})
        if unknown:
            raise UserError(_(
                "This pay scheme does not use %(fields)s any more. Reload the "
                "desk and pick the fields again — nothing has been changed."
            ) % {'fields': ", ".join(unknown)})
        return cards

    @api.model
    def _evaluate(self, config_id, changes):
        """One pass over the requested changes. Reads only; writes nothing.

        Returns `(items, plan)` — `items` is what a person reads, `plan` is what
        `apply_changes` executes. Apply re-runs this rather than trusting the
        preview the browser is holding.
        """
        cards = self._whitelist(config_id, changes)
        probe = self._probe(config_id)
        Employee = self.env[EMP].sudo()

        wanted_ids = [int(c.get('emp_id')) for c in (changes or [])
                      if c.get('emp_id')]
        # One id per person (a full sheet repeats each id per cell).
        in_scope = set(Employee.search(
            [('id', 'in', sorted(set(wanted_ids)))] + self._company_domain()).ids)
        employees = {e.id: e for e in Employee.browse(sorted(set(wanted_ids))).exists()}
        contracts = {}
        can_write = {EMP: self._may_write(EMP), CON: self._may_write(CON)}

        items, plan = [], []
        # UPDATES P2a: typed-name look-ups, remembered for THIS call only.
        memo = {}
        strict_clear = bool(self.env.context.get('records_strict_clear'))
        # Bank changes for one person are ONE write: four roles assemble a single
        # `res.partner.bank`, so they are collected and judged together.
        bank_by_emp = {}

        for change in (changes or []):
            emp_id = int(change.get('emp_id') or 0)
            card = cards[str(change.get('field_id'))]
            employee = employees.get(emp_id)
            base = {'emp_id': emp_id, 'field_id': card['id'],
                    'field_label': card['label'],
                    'emp_name': employee.display_name if employee else ''}
            if not employee or emp_id not in in_scope:
                items.append(dict(base, old_label='', new_label='',
                                  status='refused',
                                  why=_("This person is not in the companies you "
                                        "are working in.")))
                continue
            if emp_id not in contracts:
                contracts[emp_id] = probe._get_latest_contract(employee) \
                    or self.env[CON]
            contract = contracts[emp_id]
            if not can_write.get(card.get('model') or EMP, False):
                items.append(dict(base, old_label='', new_label='',
                                  status='refused',
                                  why=_("You do not have permission to change "
                                        "this. Ask an administrator.")))
                continue

            current = self._read_cell(probe, card, employee, contract, memo)
            if current.get('missing'):
                items.append(dict(base, old_label='', new_label='',
                                  status='refused',
                                  why=_("%s has no contract, so there is nothing "
                                        "to change.") % employee.display_name))
                continue

            coerced, new_label, why = self._coerce(
                probe, card, change.get('value'), employee, contract,
                memo=memo)
            if why:
                items.append(dict(base, old_label=current['label'],
                                  new_label='', status='refused', why=why))
                continue

            if card['id'][:1] == 'b':
                bank_by_emp.setdefault(emp_id, []).append(
                    (card, coerced, new_label, current, base))
                continue

            if strict_clear and change.get('value') == '' \
                    and current['v'] in (None, False, ''):
                # UPDATES P2b: clearing a value that is already empty —
                # including a pay item the contract has no line for — is
                # "stays the same", never a new zero line.
                items.append(dict(base, old_label=current['label'],
                                  new_label=new_label, status='same',
                                  why=_("Already set to this.")))
                continue

            if self._same(card, current['v'], coerced):
                items.append(dict(base, old_label=current['label'],
                                  new_label=new_label, status='same',
                                  why=_("Already set to this.")))
                continue

            items.append(dict(base, old_label=current['label'],
                              new_label=new_label, status='ok', why=''))
            plan.append({'card': card, 'employee': employee,
                         'contract': contract, 'value': coerced,
                         'old': current['v'], 'old_label': current['label'],
                         'new_label': new_label})

        items.extend(self._evaluate_bank(probe, bank_by_emp, contracts, plan))
        counts = {
            'ok': len([i for i in items if i['status'] == 'ok']),
            'same': len([i for i in items if i['status'] == 'same']),
            'refused': len([i for i in items if i['status'] == 'refused']),
            'people': len({i['emp_id'] for i in items if i['status'] == 'ok'}),
        }
        return items, plan, counts

    @api.model
    def _evaluate_bank(self, probe, bank_by_emp, contracts, plan):
        """The four bank roles, judged as the one account they assemble.

        `_sync_employee_bank_account` refuses a row with a bank NAME and no
        account number, because that is not a bank account — it would create a
        record nobody can be paid into (`payroll_import_batch.py:3047`). The
        desk applies the same rule to the same assembly: existing parts plus
        changed parts, and no account number means no write.
        """
        items = []
        for emp_id, entries in bank_by_emp.items():
            employee = self.env[EMP].sudo().browse(emp_id)
            # The four roles are read off the ACCOUNT rather than through the
            # mappings, because only some of the roles may be mapped at all and
            # the assembly rule is about the account that results.
            account = employee.sudo().bank_account_ids[:1] \
                if 'bank_account_ids' in employee._fields \
                else employee.sudo().bank_account_id[:1]
            assembled = {
                'acc_number': (account.acc_number or '') if account else '',
                'bank_name': (account.bank_id.name or '') if account else '',
                'bank_bic': (account.bank_id.bic or '') if account else '',
                'acc_holder_name': (account.acc_holder_name or '') if account else '',
            }
            changed = {}
            for card, coerced, new_label, current, base in entries:
                changed[card['bank_role']] = (coerced, new_label, current, base,
                                              card)
                assembled[card['bank_role']] = coerced or ''
            if not (assembled.get('acc_number') or '').strip():
                for role, (coerced, new_label, current, base, card) in changed.items():
                    items.append(dict(base, old_label=current['label'],
                                      new_label=new_label, status='refused',
                                      why=_("Bank details need an account number "
                                            "— add one in the same change.")))
                continue
            ok_entries = []
            for role, (coerced, new_label, current, base, card) in changed.items():
                if str(current['v'] or '').strip() == str(coerced or '').strip():
                    items.append(dict(base, old_label=current['label'],
                                      new_label=new_label, status='same',
                                      why=_("Already set to this.")))
                    continue
                items.append(dict(base, old_label=current['label'],
                                  new_label=new_label, status='ok', why=''))
                ok_entries.append({'card': card, 'value': coerced,
                                   'old': current['v'],
                                   'old_label': current['label'],
                                   'new_label': new_label})
            if ok_entries:
                plan.append({'bank': True, 'employee': employee,
                             'contract': contracts.get(emp_id) or self.env[CON],
                             'assembled': assembled, 'entries': ok_entries})
        return items

    @api.model
    def _same(self, card, old, new):
        """Self-assign rail (J10 §3.2): a change to the value already there is
        `same`, not a write. Writing it would dirty `write_date` and put a row
        in the audit trail that no reader benefits from."""
        if isinstance(new, dict):          # a many2one that would be created
            return False
        if card['ttype'] in ('integer', 'float', 'monetary', 'amount'):
            if old is None or new is None:
                return old is new
            try:
                return float_compare(float(old or 0.0), float(new or 0.0),
                                     precision_digits=6) == 0
            except (TypeError, ValueError):
                return False
        if card['ttype'] == 'boolean':
            return bool(old) == bool(new)
        return str(old if old not in (None, False) else '') == \
            str(new if new not in (None, False) else '')

    @api.model
    def preview_changes(self, config_id=0, changes=None):
        self._check_read()
        items, _plan, counts = self._evaluate(config_id, changes or [])
        return {'items': items, 'counts': counts}

    # =================================================================
    # Apply
    # =================================================================
    @api.model
    def _write_cell(self, probe, step, apply_rec):
        """Write ONE planned change and file its audit row.

        Employee and contract fields are written as the REAL user so record
        rules apply; the bank and contract-component helpers sudo internally
        because that is what they have always done, and the gate for both is the
        employee/contract write access checked in `_evaluate`.
        """
        card = step['card']
        employee = step['employee']
        contract = step['contract']
        value = step['value']
        kind = card['id'][:1]

        if kind == 'f':
            record = employee if card['model'] == EMP else contract
            if isinstance(value, dict) and 'create' in value:
                comodel = self.env[card['_field'].comodel_name]
                vals = {'name': value['create']}
                if 'company_id' in comodel._fields and self.env.company:
                    vals['company_id'] = self.env.company.id
                value = comodel.sudo().create(vals).id
            vals = {card['field']: value}
            if card['field'] == 'barcode':
                # A barcode somebody else holds aborts the transaction on a
                # UNIQUE violation and takes the whole apply with it.
                vals = probe._drop_taken_barcode(vals, employee=employee)
                if 'barcode' not in vals:
                    return None, _(
                        "That badge id already belongs to somebody else, so it "
                        "was left off.")
            # Written as the REAL user (`sudo(False)`), not as superuser: the
            # model ACL was checked in `_evaluate`, and the record rules are the
            # finer grain that only a real-user write applies. An AccessError
            # here becomes a sentence rather than a dialog over a half-done
            # apply.
            try:
                real_record = record.sudo(False)
                if self.env.user.has_group('pb_records.group_records_editor') and not real_record.has_access('write'):
                    # The narrow capability is confined to this already-
                    # whitelisted plan. It grants no native model write ACL.
                    domain = self.env['ir.rule']._compute_domain(record._name, 'write')
                    if not real_record.filtered_domain(domain):
                        return None, _("You are not allowed to change this person's record.")
                    record.sudo().write(vals)
                else:
                    real_record.write(vals)
            except AccessError:
                return None, _(
                    "You are not allowed to change this person's record.")
            self._log(apply_rec, employee, record._name, record.id, card,
                      step['old'], value, step['old_label'], step['new_label'])
            return value, None

        if kind == 'c':
            template = card.get('_template') or probe._get_or_create_advantage_template(
                card['_rule'], {})
            wanted = 'text' if card['ttype'] == 'text_component' else 'amount'
            if 'value_type' in template._fields and template.value_type != wanted:
                # NEVER flipped. Every line filed under it was written as the
                # other kind (`_get_or_create_advantage_template`, and the same
                # sentence the batch logs).
                return None, _(
                    "%(label)s is already kept as %(kind)s on contracts, so it "
                    "cannot be changed here.") % {
                        'label': card['label'],
                        'kind': _("text") if template.value_type == 'text'
                        else _("an amount")}
            line = self._advantage_line(probe, contract, card['code'])
            if wanted == 'amount' and value is None and apply_rec.source == 'undo':
                # Undo a first explicit entry back to absence, not a saved zero.
                if line:
                    self._component_log(contract, template, apply_rec,
                                        old_amount=line.amount, new_amount=0.0)
                    line.sudo().unlink()
                self._log(apply_rec, employee, 'hr.contract', contract.id, card,
                          step['old'], None, step['old_label'], '')
                return None, None
            if not line:
                line = self.env['hr.contract.advantage'].sudo().create({
                    'contract_id': contract.id,
                    'advantage_template_id': template.id,
                })
            if wanted == 'text':
                old_text = line.text_value or ''
                line.sudo().write({'text_value': value or False})
                self._component_log(contract, template, apply_rec,
                                    old_text=old_text, new_text=value or '')
            else:
                old_amount = line.amount or 0.0
                line.sudo().write({'amount': value or 0.0})
                self._component_log(contract, template, apply_rec,
                                    old_amount=old_amount,
                                    new_amount=value or 0.0)
            self._log(apply_rec, employee, 'hr.contract', contract.id, card,
                      step['old'], value, step['old_label'], step['new_label'])
            return value, None
        return None, _("Nothing to do.")

    @api.model
    def _write_bank(self, probe, step, apply_rec):
        """The four roles as ONE account — assemble, then ADD, never replace.

        `_link_employee_bank_account` is the rule: if somebody has already chosen
        where this person is paid, the desk does not get to overrule them, so a
        different account number ADDS a second account
        (`payroll_import_batch.py:3030`).
        """
        employee = step['employee']
        parts = step['assembled']
        acc_number, damaged = sanitize_acc_number(parts.get('acc_number'))
        if damaged or not acc_number:
            return _("Bank details need an account number.")
        partner = probe._get_employee_bank_partner(employee)
        PartnerBank = self.env['res.partner.bank'].sudo()
        existing = PartnerBank.search([('partner_id', '=', partner.id)])
        account = existing.filtered(
            lambda a: acc_numbers_match(a.acc_number, acc_number))[:1]
        bank = probe._resolve_bank(sanitize_bank_text(parts.get('bank_name')) or '',
                                   sanitize_bank_text(parts.get('bank_bic')) or '')
        holder = sanitize_bank_text(parts.get('acc_holder_name')) or ''
        if account:
            updates = {}
            if bank and account.bank_id != bank:
                updates['bank_id'] = bank.id
            if holder and account.acc_holder_name != holder:
                updates['acc_holder_name'] = holder
            if updates:
                account.write(updates)
        else:
            vals = {'acc_number': acc_number, 'partner_id': partner.id}
            if bank:
                vals['bank_id'] = bank.id
            if holder:
                vals['acc_holder_name'] = holder
            if 'company_id' in PartnerBank._fields:
                vals['company_id'] = (employee.company_id
                                      or self.env.company).id
            account = PartnerBank.create(vals)
        probe._link_employee_bank_account(employee, account)
        for entry in step['entries']:
            self._log(apply_rec, employee, 'res.partner.bank', account.id,
                      entry['card'], entry['old'], entry['value'],
                      entry['old_label'], entry['new_label'])
        return None

    @api.model
    def _component_log(self, contract, template, apply_rec, old_amount=0.0,
                       new_amount=0.0, old_text=None, new_text=None):
        """The contract-component audit row, filed the way the batch files it.

        `_log_contract_component_change` writes `import_batch_id: self.id`, and
        `self` here is a `.new()` probe whose id is a NewId — which cannot be
        stored. So the row is created directly with the same keys minus that
        one, and `change_source='manual'` says where it came from (RD8).
        """
        self.env['hr.contract.advantage.change'].sudo().create({
            'contract_id': contract.id,
            'advantage_template_id': template.id,
            'old_amount': old_amount or 0.0,
            'new_amount': new_amount or 0.0,
            'old_text_value': old_text or False,
            'new_text_value': new_text or False,
            'effective_date': self._effective_date(apply_rec),
            'change_source': 'manual',
            'notes': _("Records Desk apply #%s") % apply_rec.id,
        })

    @api.model
    def _effective_date(self, apply_rec):
        """UPDATES P2c — the day a written value is recorded as starting.

        A scheduled write passes it in the context (`records_effective_date`:
        the start date when the job writes it, today for "Start now"). A
        change with a start date that has come (a past date) carries that
        date. Everything else — no date, and every undo — is today, exactly
        as before. It is a RECORD: nothing is recalculated from it."""
        forced = self.env.context.get('records_effective_date')
        if forced:
            return fields.Date.to_date(forced)
        today = fields.Date.context_today(self)
        start = apply_rec.start_date if apply_rec and 'start_date' in apply_rec._fields \
            and apply_rec.source != 'undo' else False
        if start and start <= today:
            return start
        return today

    @api.model
    def _log(self, apply_rec, employee, model, res_id, card, old, new,
             old_label, new_label):
        self.env['pb.records.change'].sudo().create({
            'effective_date': self._effective_date(apply_rec),
            'apply_id': apply_rec.id,
            'employee_id': employee.id,
            'employee_name': employee.display_name or '',
            'model': model,
            'res_id': res_id,
            'field_key': card['id'],
            'field_label': card['label'],
            'old_json': json.dumps(self._jsonable(old)),
            'new_json': json.dumps(self._jsonable(new)),
            'old_label': old_label or '',
            'new_label': new_label or '',
        })

    @api.model
    def _jsonable(self, value):
        if isinstance(value, dict):
            return value.get('create') or ''
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        return str(value)

    #: Field keys that mean "what this person is paid". A route that wants
    #: Finance to look at pay changes and nothing else conditions on
    #: `touches_salary`, and the desk has to be able to answer that before
    #: anybody has looked at the plan.
    SALARY_TOKENS = ('wage', 'salary', 'basic', 'gross', 'net', 'pay')

    @api.model
    def _plan_rows(self, plan):
        """The plan as JSON, carrying the value every field holds RIGHT NOW.

        This snapshot is what makes "somebody else changed it in between" an
        answerable question at approval time. It holds the card ID and the
        person, never a recordset — a plan has to survive a week in a column.
        """
        rows = []
        for step in plan:
            if step.get('bank'):
                for entry in step['entries']:
                    rows.append({
                        'emp_id': step['employee'].id,
                        'emp_name': step['employee'].display_name or '',
                        'field_id': entry['card']['id'],
                        'field_label': entry['card']['label'],
                        'old': self._jsonable(entry['old']),
                        'old_label': entry['old_label'] or '',
                        'new_label': entry['new_label'] or '',
                    })
                continue
            rows.append({
                'emp_id': step['employee'].id,
                'emp_name': step['employee'].display_name or '',
                'field_id': step['card']['id'],
                'field_label': step['card']['label'],
                'old': self._jsonable(step['old']),
                'old_label': step['old_label'] or '',
                'new_label': step['new_label'] or '',
            })
        return rows

    @api.model
    def _plan_moved_since(self, apply_rec):
        """Names of the values somebody else has changed since the proposal.

        All-or-nothing is deliberate. A bulk change half applied is worse than
        one not applied at all: nobody can tell by looking which half landed,
        and the person who proposed it has to work out what to re-propose.
        """
        cards = self._cards(apply_rec.config_id.id or 0)
        probe = self._probe(apply_rec.config_id.id or 0)
        moved = []
        for row in apply_rec.plan():
            card = cards.get(row.get('field_id'))
            employee = self.env[EMP].sudo().browse(
                int(row.get('emp_id') or 0)).exists()
            if not card or not employee:
                moved.append(_("%s (the field or the person is gone)")
                             % (row.get('emp_name') or ''))
                continue
            contract = probe._get_latest_contract(employee) or self.env[CON]
            current = self._read_cell(probe, card, employee, contract)
            if not self._same(card, current['v'], row.get('old')):
                moved.append('%s · %s' % (row.get('emp_name') or '',
                                          card['label']))
        return moved

    @api.model
    def _door_for(self, apply_rec):
        """The desk a proposal must be judged with. The Records screen's own
        desk here; Updates reopens its door (`pb_updates`)."""
        return self

    @api.model
    def _plan_drift(self, apply_rec):
        """UPDATES P2c — `(lost, extra)` between the stored plan and what the
        evaluation would write NOW: planned values it would refuse (a person
        out of scope, a right withdrawn) and values it would add that nobody
        planned. A scheduled write needs both empty — it writes exactly what
        was approved or nothing."""
        items, _plan, _counts = self._evaluate(apply_rec.config_id.id or 0,
                                               apply_rec.requested())
        planned = {(int(r.get('emp_id') or 0), r.get('field_id'))
                   for r in apply_rec.plan()}
        lost, extra, seen = [], [], set()
        for item in items:
            key = (item['emp_id'], item['field_id'])
            if key in planned and item['status'] != 'ok' and key not in seen:
                lost.append(item)
                seen.add(key)
            elif key not in planned and item['status'] == 'ok' and key not in seen:
                extra.append(item)
                seen.add(key)
        return lost, extra

    @api.model
    def _write_plan(self, apply_rec):
        """Carry out a proposal. Returns (written, people, refused)."""
        config_id = apply_rec.config_id.id or 0
        _items, plan, _counts = self._evaluate(config_id,
                                               apply_rec.requested())
        probe = self._probe(config_id)
        written, people, late_refusals = 0, set(), []
        for step in plan:
            # Evaluation prefetches the whole roster for efficient reads.
            # Keep that batch out of each individual write: tracked computed
            # employee fields otherwise recompute the roster after successive
            # contract/version changes invalidate them (quadratic bulk work).
            # This changes only the prefetch cohort, not access or tracking.
            step = dict(step)
            for key in ('employee', 'contract'):
                if key in step:
                    step[key] = step[key].with_prefetch(step[key].ids)
            if step.get('bank'):
                why = self._write_bank(probe, step, apply_rec)
                if why:
                    late_refusals.append({'emp_id': step['employee'].id,
                                          'field_id': 'b:acc_number',
                                          'why': why})
                    continue
                written += len(step['entries'])
                people.add(step['employee'].id)
                continue
            _value, why = self._write_cell(probe, step, apply_rec)
            if why:
                late_refusals.append({'emp_id': step['employee'].id,
                                      'field_id': step['card']['id'],
                                      'why': why})
                continue
            written += 1
            people.add(step['employee'].id)
        return written, people, late_refusals

    @api.model
    def _plan_touches(self, rows):
        """(bank, salary) — the two facts a route nearly always asks about."""
        bank = any(str(r.get('field_id') or '')[:1] == 'b' for r in rows)
        salary = False
        for row in rows:
            haystack = '%s %s' % (row.get('field_id') or '',
                                  row.get('field_label') or '')
            haystack = haystack.lower()
            if any(token in haystack for token in self.SALARY_TOKENS):
                salary = True
                break
        return bank, salary

    @api.model
    def _start_date_of(self, value):
        """UPDATES P2c — `(date or None, refusal)` for a requested start date.

        Empty, or today in the company's own time zone, is None: "today, as
        before" — the proposal is made exactly as it always was. More than a
        year back or ahead is refused in a sentence."""
        if not value:
            return None, ''
        try:
            day = fields.Date.to_date(value)
        except (TypeError, ValueError):
            day = None
        if not day:
            return None, _("'%s' is not a date. Use a date like 1 Dec 2026.") \
                % value
        today = self.env['pb.records.apply']._today_for(self.env.company,
                                                        self.env.user)
        if day == today:
            return None, ''
        if abs((day - today).days) > START_DATE_REACH:
            return None, _(
                "A start date can be up to a year back or a year ahead. "
                "%s is further away than that.") % format_date(self.env, day)
        return day, ''

    @api.model
    def apply_changes(self, config_id=0, changes=None, note='', source='desk',
                      start_date=None, hold_scope='pay'):
        """Evaluate, write the plan down, and ask.

        `source` says where the values came from — the grid (`desk`) or a
        dropped file (`import`, R3). It is a LABEL on the proposal and nothing
        else: an import takes this exact path, with this exact whitelist, this
        exact company scoping and this exact per-value log, because a second
        write path is a second set of rails to keep in step.

        Nothing is written here. The engine decides: where the business
        published "No approval needed" it applies in the same breath and the
        answer looks exactly as it always did, plus a reference; where a real
        route is published the answer says who it is with.

        UPDATES P2c: `start_date` (optional) — empty or today takes exactly
        the path above; a past date is written as above and recorded as
        starting that day; a future date is proposed and approved as above
        and then held as "Scheduled" until its day. `hold_scope` is kept as
        the record of what the person chose to hold back (`pay` / `all`).
        """
        self._check_read()
        source = source if source in ('desk', 'import') else 'desk'
        start, refusal = self._start_date_of(start_date)
        if refusal:
            return {'ok': False, 'msg': refusal, 'apply_id': 0, 'written': 0,
                    'people': 0, 'items': [], 'refused': [], 'pending': False}
        desk = self.with_context(records_from_file=True) \
            if source == 'import' else self
        items, plan, counts = desk._evaluate(config_id, changes or [])
        if not plan:
            return {'ok': True, 'apply_id': 0, 'written': 0, 'people': 0,
                    'items': items, 'counts': counts, 'pending': False,
                    'refused': [i for i in items if i['status'] == 'refused'],
                    'skipped_same': counts['same']}

        configs = self._configs(config_id)
        rows = self._plan_rows(plan)
        touches_bank, touches_salary = self._plan_touches(rows)
        apply_rec = self.env['pb.records.apply'].sudo().create({
            'name': '/',
            'note': (note or '').strip() or False,
            'source': source,
            'config_id': configs[:1].id if config_id else False,
            'count_people': 0, 'count_values': 0,
            'plan_json': json.dumps(rows),
            'changes_json': json.dumps(changes or []),
            'people_count': len({r['emp_id'] for r in rows}),
            'values_count': len(rows),
            'touches_bank': touches_bank,
            'touches_salary': touches_salary,
            'company_id': self.env.company.id,
            'start_date': start or False,
            'hold_scope': 'all' if hold_scope == 'all' else 'pay',
        })
        apply_rec.name = 'RD%05d' % apply_rec.id

        payload = self.env['biz.approval.engine'].submit(apply_rec)
        apply_rec.invalidate_recordset()
        # THE WRITE'S OWN REFUSALS COME BACK TOO. Some rows can only be refused
        # while they are being written — a contract component already kept as
        # text, a badge id somebody else holds — and the desk's answer has
        # always listed them beside the ones the evaluation refused. Under a
        # fast lane the write happened inside the submit above, so they are
        # read back off the proposal rather than lost in it.
        refused = [i for i in items if i['status'] == 'refused'] \
            + apply_rec.late_refusals()
        answer = {
            'ok': True, 'apply_id': apply_rec.id,
            'written': apply_rec.count_values, 'people': apply_rec.count_people,
            'items': items, 'counts': counts, 'refused': refused,
            'skipped_same': counts['same'], 'reference': apply_rec.name,
            # A scheduled change is approved and waiting for its DAY, not for
            # anybody's decision — it says so in its own key.
            'pending': not apply_rec.applied and apply_rec.state != 'scheduled',
            'scheduled': apply_rec.state == 'scheduled',
            'start_date': fields.Date.to_string(apply_rec.start_date)
            if apply_rec.start_date else '',
            'request_id': (payload or {}).get('id') or 0,
            'state': apply_rec.state,
            'with_whom': apply_rec._waiting_for(),
            'route': self._route_labels(apply_rec),
            'block_note': apply_rec.block_note or '',
        }
        return answer

    @api.model
    def _route_labels(self, apply_rec):
        """The steps this proposal has to pass, in order, with their people."""
        request = apply_rec.approval_request_id
        if not request:
            return []
        out = []
        for step in request.step_ids.sorted('sequence'):
            if not step.included or step.kind == 'fast':
                continue
            out.append({
                'title': step.title,
                'status': step.status,
                'people': sorted({seat.acting_user_id.name or ''
                                  for seat in step.seat_ids}),
            })
        return out

    # =================================================================
    # Undo
    # =================================================================
    @api.model
    def undo_apply(self, apply_id):
        self._check_read()
        source = self.env['pb.records.apply'].sudo().browse(int(apply_id)).exists()
        if not source:
            return {'ok': False, 'msg': _("That change is no longer on record.")}
        if source.undone:
            return {'ok': False, 'msg': _("This one has already been undone.")}
        if not source.applied and source.source != 'undo':
            # UPDATES P2c — THE DEFECT FIX. A change that has not been written
            # has nothing to put back. It used to get an empty undo row and an
            # "undone" mark that the approval ignored, so it was still written
            # later. It is now cancelled — for real — and says so.
            answer = self.cancel_apply(source.id)
            if answer.get('ok'):
                answer.update(restored=0, skipped_changed_since=0,
                              skipped_missing=0, apply_id=0)
            return answer

        config_id = source.config_id.id or 0
        cards = self._cards(config_id)
        probe = self._probe(config_id)
        # AN UNDO IS NOT A PROPOSAL. It puts back values this trail says were
        # there before, and every one of them was already approved on the way
        # in. Putting a route in front of "put it back the way it was" would
        # make a mistake harder to correct than to make.
        undo_rec = self.env['pb.records.apply'].sudo().create({
            'name': '/', 'source': 'undo',
            'config_id': source.config_id.id or False,
            'note': _("Undo of %s") % source.name,
            'count_people': 0, 'count_values': 0,
            'applied': True, 'state': 'applied',
            'applied_at': fields.Datetime.now(),
            'company_id': self.env.company.id,
        })
        undo_rec.name = 'RD%05d' % undo_rec.id

        restored, changed_since, missing = 0, 0, 0
        people = set()
        bank_people = {}
        for change in source.change_ids:
            card = cards.get(change.field_key)
            employee = change.employee_id
            if not card or not employee.exists():
                missing += 1
                continue
            if not self._may_write(card.get('model') or EMP):
                missing += 1
                continue
            contract = probe._get_latest_contract(employee) or self.env[CON]
            current = self._read_cell(probe, card, employee, contract)
            try:
                new_value = json.loads(change.new_json or 'null')
                old_value = json.loads(change.old_json or 'null')
            except ValueError:
                missing += 1
                continue
            if not self._same(card, current['v'], new_value):
                changed_since += 1
                continue
            if card['id'][:1] == 'b':
                bank_people.setdefault(employee.id, []).append(
                    (card, old_value, current))
                continue
            step = {'card': card, 'employee': employee, 'contract': contract,
                    'value': old_value, 'old': current['v'],
                    'old_label': current['label'],
                    'new_label': str(old_value if old_value not in (None, False)
                                     else '')}
            _value, why = self._write_cell(probe, step, undo_rec)
            if why:
                missing += 1
                continue
            restored += 1
            people.add(employee.id)

        for emp_id, entries in bank_people.items():
            employee = self.env[EMP].sudo().browse(emp_id)
            account = employee.bank_account_ids[:1] \
                if 'bank_account_ids' in employee._fields \
                else employee.bank_account_id[:1]
            assembled = {
                'acc_number': (account.acc_number or '') if account else '',
                'bank_name': (account.bank_id.name or '') if account else '',
                'bank_bic': (account.bank_id.bic or '') if account else '',
                'acc_holder_name': (account.acc_holder_name or '') if account else '',
            }
            plan_entries = []
            for card, old_value, current in entries:
                assembled[card['bank_role']] = old_value or ''
                plan_entries.append({'card': card, 'value': old_value or '',
                                     'old': current['v'],
                                     'old_label': current['label'],
                                     'new_label': str(old_value or '')})
            step = {'bank': True, 'employee': employee,
                    'contract': self.env[CON], 'assembled': assembled,
                    'entries': plan_entries}
            why = self._write_bank(probe, step, undo_rec)
            if why:
                missing += len(plan_entries)
                continue
            restored += len(plan_entries)
            people.add(emp_id)

        undo_rec.write({'count_values': restored, 'count_people': len(people)})
        source.write({'undone': True, 'undone_date': fields.Datetime.now(),
                      'undone_by_id': self.env.user.id})
        return {'ok': True, 'restored': restored,
                'skipped_changed_since': changed_since,
                'skipped_missing': missing, 'apply_id': undo_rec.id}

    # =================================================================
    # UPDATES P2c — Cancel and Start now
    # =================================================================
    @api.model
    def cancel_apply(self, apply_id):
        """Stop a change that has not been written: waiting for approval,
        scheduled, or sent back. Its approval request is withdrawn through
        the engine's own `cancel`, and from then on neither an approval nor
        the job can write it. Allowed for whoever proposed it, anybody asked
        to decide it, or an HR / payroll manager."""
        self._check_read()
        try:
            apply_id = int(apply_id or 0)
        except (TypeError, ValueError):
            apply_id = 0
        rec = self.env['pb.records.apply'].sudo().browse(apply_id).exists()
        if not rec:
            return {'ok': False, 'msg': _("That change is no longer on record.")}
        if rec.applied:
            return {'ok': False, 'msg': _(
                "This change has already been made, so it cannot be cancelled. "
                "Use Undo to put it back.")}
        if rec.state == 'cancelled' or rec.undone:
            return {'ok': False, 'msg': _("This change has already been cancelled.")}
        if rec.state not in ('pending', 'scheduled', 'returned'):
            return {'ok': False, 'msg': _(
                "This change was turned down, so nothing was written and there "
                "is nothing to cancel.") if rec.state == 'rejected' else _(
                "This change can no longer be cancelled.")}
        if not rec.with_env(self.env)._may_cancel():
            return {'ok': False, 'msg': _(
                "Only the person who proposed this change, someone asked to "
                "approve it, or an HR manager can cancel it.")}
        if not rec._lock_row(wait=True):
            return {'ok': False, 'msg': _(
                "This change is being written right now. Look again in a "
                "minute.")}
        if rec.applied:
            return {'ok': False, 'msg': _(
                "This change has just been made, so it cannot be cancelled. "
                "Use Undo to put it back.")}
        request = rec.approval_request_id
        if request and request.state in ('pending', 'blocked'):
            self.env['biz.approval.engine'].sudo().cancel(
                request.id, _("Cancelled before anything was changed."))
        rec.write({'state': 'cancelled', 'block_note': False,
                   'cancelled_at': fields.Datetime.now(),
                   'cancelled_by_id': self.env.uid})
        return {'ok': True, 'cancelled': True, 'apply_id': rec.id,
                'msg': _("Cancelled before anything was changed.")}

    @api.model
    def start_now(self, apply_id):
        """Write a scheduled change today instead of on its day. The same
        gate as applying (write rights on employee or contract records), the
        same all-or-none write as the job, recorded as starting today."""
        self._check_read()
        try:
            apply_id = int(apply_id or 0)
        except (TypeError, ValueError):
            apply_id = 0
        rec = self.env['pb.records.apply'].sudo().browse(apply_id).exists()
        if not rec:
            return {'ok': False, 'msg': _("That change is no longer on record.")}
        if rec.applied:
            return {'ok': False, 'msg': _("This change has already been made.")}
        if rec.state != 'scheduled' or rec.undone:
            return {'ok': False, 'msg': _(
                "Only a scheduled change can be started early.")}
        if not (self._may_write(EMP) or self._may_write(CON)):
            return {'ok': False, 'msg': _(
                "Starting a change needs permission to change employee "
                "records. Ask an administrator for the HR or Payroll Officer "
                "role.")}
        try:
            outcome, sentence = rec.with_env(self.env)._start_scheduled(
                by_job=False)
        except LOCK_ERRORS:
            outcome, sentence = 'busy', _(
                "This change is being written right now. Look again in a "
                "minute.")
        if outcome != 'started':
            return {'ok': False, 'outcome': outcome, 'msg': sentence}
        rec.invalidate_recordset()
        return {'ok': True, 'apply_id': rec.id, 'written': rec.count_values,
                'people': rec.count_people, 'reference': rec.name}

    # =================================================================
    # History
    # =================================================================
    @api.model
    def get_history(self, limit=20):
        self._check_read()
        rows = self.env['pb.records.apply'].sudo().search(
            [], order='id desc', limit=int(limit))
        out = []
        for rec in rows:
            out.append({
                'id': rec.id,
                'name': rec.name or '',
                'user': rec.user_id.display_name or '',
                'date': fields.Datetime.to_string(rec.date) if rec.date else '',
                'note': rec.note or '',
                'source': rec.source,
                'scheme': rec.config_id.display_name or '',
                'count_people': rec.count_people or rec.people_count,
                'count_values': rec.count_values or rec.values_count,
                'undone': rec.undone,
                # A proposal that has not been carried out yet belongs in
                # History too — it is the only screen that can tell somebody
                # where the change they made this morning actually is.
                'state': rec.state,
                'state_label': dict(
                    rec._fields['state'].selection).get(rec.state, ''),
                'applied': rec.applied,
                'pending': rec.state == 'pending',
                'with_whom': rec._waiting_for(),
                'request_id': rec.approval_request_id.id,
                'block_note': rec.block_note or '',
                # UPDATES P2c — a change held for its day, and one stopped
                # before anything was written. "Cancel" stands where "Undo"
                # would have marked an unwritten change undone (the defect).
                'start_date': fields.Date.to_string(rec.start_date)
                if rec.start_date else '',
                'scheduled': rec.state == 'scheduled',
                'cancelled': rec.state == 'cancelled',
                'can_cancel': bool(
                    rec.state == 'scheduled' and not rec.applied
                    and not rec.undone and rec.with_env(self.env)._may_cancel()),
            })
        return {'applies': out}
