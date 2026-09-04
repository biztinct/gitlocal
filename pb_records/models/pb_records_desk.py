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

from odoo.addons.pb_hr_payroll_formula.models.payroll_import_batch import (
    m2o_creates_missing, m2o_resolution_key)
from odoo.addons.pb_hr_payroll_formula.models.bank_account_util import (
    acc_numbers_match, sanitize_acc_number, sanitize_bank_text)

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


class PbRecordsDesk(models.AbstractModel):
    _name = 'pb.records.desk'
    _description = 'Records Desk'

    # =================================================================
    # Gates
    # =================================================================
    @api.model
    def _may_read(self):
        return (self.env.user.has_group('hr.group_hr_user')
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
    def _may_write(self, model_name):
        """Can this person write on `model_name` at all?

        Asked ONCE per model and turned into a lock hint on the cards, so a cell
        this person could never save is read-only on screen instead of raising
        an access dialog after they have typed into forty of them.
        """
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
            is_text = bool(rule.is_text_component)
            cards[card_id] = {
                'id': card_id, 'group': 'component',
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
        return cards

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
        employees = Employee.search(self._people_domain(filters, skip=skip),
                                    order='name, id')
        return self._apply_post_filters(employees, filters, skip=skip, ctx=ctx)

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
        rows = []
        for emp in page:
            contract = probe._get_latest_contract(emp) or self.env[CON]
            values = {}
            for card in picked:
                values[card['id']] = self._read_cell(probe, card, emp, contract)
            rows.append({
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
            })
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
    def _advantage_line(self, probe, contract, code):
        if not contract:
            return None
        return probe._get_contract_advantage_map(contract).get(code)

    @api.model
    def _read_cell(self, probe, card, employee, contract):
        """`{v, label}` — the raw value to compare/write and the text to show.

        The LABEL of a selection or a many2one comes from
        `_mapped_record_value`, so the desk shows exactly what an import sees;
        the raw half is read off the record here because that method returns
        only the label and a grid needs the key it will write back.
        """
        kind = card['id'][:1]
        if kind == 'f':
            record = employee if card['model'] == EMP else contract
            if not record:
                return {'v': None, 'label': '', 'missing': True}
            field = card['_field']
            raw = record[card['field']]
            label = probe._mapped_record_value(
                card['_mapping'], contract=contract, employee=employee)
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
            value = probe._bank_record_value(card['_mapping'], employee=employee)
            return {'v': value or '', 'label': str(value or '')}
        if kind == 'c':
            if not contract:
                return {'v': None, 'label': '', 'missing': True}
            line = self._advantage_line(probe, contract, card['code'])
            if card['ttype'] == 'text_component':
                text = (line.text_value if line else '') or ''
                return {'v': text, 'label': text}
            amount = (line.amount if line else 0.0) or 0.0
            return {'v': amount, 'label': ('' if not amount
                                           else self._num(amount))}
        return {'v': None, 'label': ''}

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

    @api.model
    def _coerce(self, probe, card, value, employee, contract):
        """`(coerced, label, why)` — `why` is a plain sentence and means refused.

        `''` is an explicit CLEAR (the column menu's "Clear for selected" and an
        emptied cell are the same gesture), not a missing value.
        """
        kind = card['id'][:1]
        if not card.get('editable'):
            return None, '', _(
                "%s cannot be changed here — it is read-only on the record.") \
                % card['label']

        if kind == 'c':
            if card['ttype'] == 'text_component':
                text = '' if value is None else str(value).strip()
                return text, text, None
            if value in (None, ''):
                return 0.0, '', None
            try:
                amount = float(str(value).replace(',', '').strip())
            except (TypeError, ValueError):
                return None, '', _(
                    "'%(value)s' is not a number — type an amount like 1500000."
                ) % {'value': value}
            return amount, self._num(amount), None

        if kind == 'b':
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
            existing = comodel.sudo().search([(key, '=ilike', text)], limit=1)
            if existing:
                return existing.id, existing.display_name or text, None
            if not m2o_creates_missing(comodel):
                what = (self.env['ir.model'].sudo()._get(field.comodel_name).name
                        or field.comodel_name).lower()
                return None, '', _(
                    "No %(what)s called '%(value)s' exists, and %(what)s records "
                    "are not created here.") % {'what': what, 'value': text}
            # Deliberately NOT created during a preview — the create happens in
            # `_write_cell`, inside the apply transaction.
            return {'create': text}, _("%s (new)") % text, None

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
        in_scope = set(Employee.search(
            [('id', 'in', wanted_ids)] + self._company_domain()).ids)
        employees = {e.id: e for e in Employee.browse(sorted(set(wanted_ids))).exists()}
        contracts = {}
        can_write = {EMP: self._may_write(EMP), CON: self._may_write(CON)}

        items, plan = [], []
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

            current = self._read_cell(probe, card, employee, contract)
            if current.get('missing'):
                items.append(dict(base, old_label='', new_label='',
                                  status='refused',
                                  why=_("%s has no contract, so there is nothing "
                                        "to change.") % employee.display_name))
                continue

            coerced, new_label, why = self._coerce(
                probe, card, change.get('value'), employee, contract)
            if why:
                items.append(dict(base, old_label=current['label'],
                                  new_label='', status='refused', why=why))
                continue

            if card['id'][:1] == 'b':
                bank_by_emp.setdefault(emp_id, []).append(
                    (card, coerced, new_label, current, base))
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
                record.sudo(False).write(vals)
            except AccessError:
                return None, _(
                    "You are not allowed to change this person's record.")
            self._log(apply_rec, employee, record._name, record.id, card,
                      step['old'], value, step['old_label'], step['new_label'])
            return value, None

        if kind == 'c':
            template = probe._get_or_create_advantage_template(
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
            'effective_date': fields.Date.context_today(self),
            'change_source': 'manual',
            'notes': _("Records Desk apply #%s") % apply_rec.id,
        })

    @api.model
    def _log(self, apply_rec, employee, model, res_id, card, old, new,
             old_label, new_label):
        self.env['pb.records.change'].sudo().create({
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

    @api.model
    def apply_changes(self, config_id=0, changes=None, note='', source='desk'):
        """Write the `ok` half of `changes`, and file the audit trail for it.

        `source` says where the values came from — the grid (`desk`) or a
        dropped file (`import`, R3). It is a LABEL on the audit row and nothing
        else: an import takes this exact path, with this exact whitelist, this
        exact company scoping and this exact per-value log, because a second
        write path is a second set of rails to keep in step.
        """
        self._check_read()
        source = source if source in ('desk', 'import') else 'desk'
        items, plan, counts = self._evaluate(config_id, changes or [])
        if not plan:
            return {'ok': True, 'apply_id': 0, 'written': 0, 'people': 0,
                    'items': items, 'counts': counts,
                    'refused': [i for i in items if i['status'] == 'refused'],
                    'skipped_same': counts['same']}

        probe = self._probe(config_id)
        configs = self._configs(config_id)
        apply_rec = self.env['pb.records.apply'].sudo().create({
            'name': '/',
            'note': (note or '').strip() or False,
            'source': source,
            'config_id': configs[:1].id if config_id else False,
            'count_people': 0, 'count_values': 0,
        })
        apply_rec.name = 'RD%05d' % apply_rec.id

        written, people, late_refusals = 0, set(), []
        for step in plan:
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
            value, why = self._write_cell(probe, step, apply_rec)
            if why:
                late_refusals.append({'emp_id': step['employee'].id,
                                      'field_id': step['card']['id'],
                                      'why': why})
                continue
            written += 1
            people.add(step['employee'].id)

        apply_rec.write({'count_values': written, 'count_people': len(people)})
        refused = [i for i in items if i['status'] == 'refused'] + late_refusals
        return {'ok': True, 'apply_id': apply_rec.id, 'written': written,
                'people': len(people), 'items': items, 'counts': counts,
                'refused': refused, 'skipped_same': counts['same'],
                'reference': apply_rec.name}

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

        config_id = source.config_id.id or 0
        cards = self._cards(config_id)
        probe = self._probe(config_id)
        undo_rec = self.env['pb.records.apply'].sudo().create({
            'name': '/', 'source': 'undo',
            'config_id': source.config_id.id or False,
            'note': _("Undo of %s") % source.name,
            'count_people': 0, 'count_values': 0,
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
                'count_people': rec.count_people,
                'count_values': rec.count_values,
                'undone': rec.undone,
            })
        return {'applies': out}
