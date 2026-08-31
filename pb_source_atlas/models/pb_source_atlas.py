# -*- coding: utf-8 -*-
"""pb.source.atlas — the read-only facade behind the Source Atlas cockpit.

The question this answers is the oldest one in payroll: *where did this number
come from?* The SOURCING programme already made every computed payslip carry the
answer — ``hr.payslip.formula_input_sources`` is a JSON blob of
``{code: {src, key, via}}`` written in the same pass that resolved the value.
NETROLE Phase 1 then read the scheme's formulas as a signed graph, so every
component knows how it reaches net pay.

This module invents NOTHING. It reads those two existing truths, joins them back
to the raw material they name (a feed row, a spreadsheet row, a contract
component, an employee field), and hands the client three views of one state:
lanes, grid, journey.

Doctrine
--------
* **Strictly read-only.** There is no ``create``/``write``/``unlink`` anywhere in
  this module, and ``test_07`` proves it by counting rows before and after every
  endpoint. If provenance is missing the answer is "computed before source
  tracking existed", never a recomputation.
* **Gate on the real user, then read.** The gate is the pay-run officer ladder;
  the reads that follow are sudo'd only where the underlying model's ACL is
  narrower than the gate (the feed store and the import lines).
* **Two kinds of lane, never conflated.** A lane a payslip *recorded* comes out
  of the provenance blob. A lane that is *declared* — a formula component is
  ``calculated``, a constant component is ``constant`` — is a property of the
  component's own type, not a guess about a value, and every payload says which
  kind it is so the screen can too (C7: never silently wrong).
* **Never ORM-iterate the run.** The summary pass is one SQL statement over the
  slips' JSON columns; the grid is windowed server-side (C8).
"""

import json
import logging
from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.pb_hr_payroll_formula.models import input_provenance
from odoo.addons.pb_hr_payroll_formula.models.formula_net_role import (
    looks_like_a_quantity,
)

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------------- access
# Mirrors what the pay-run form itself requires: the officer tier is the lowest
# rung that may open a run, so it is the lowest rung that may ask where the
# run's numbers came from.
_GATE_GROUPS = (
    'pb_hr_payroll_base.group_payroll_base_officer',
    'pb_hr_payroll_base.group_payroll_base_manager',
    'pb_hr_payroll_base.group_payroll_super_admin',
    'om_hr_payroll.group_hr_payroll_manager',
)

# ---------------------------------------------------------------------- bounds
_GRID_LIMIT = 40        # rows rendered at once; the DOM never holds a whole run
_GRID_MAX = 200         # hard ceiling on a client-supplied limit
_XLSX_ROW_CAP = 5000    # employees per download sheet; the cap is REPORTED
_XLSX_COL_CAP = 400     # components per download sheet; likewise
_HOP_CAP = 24           # formula hops walked before we stop and say so

# ----------------------------------------------------------------------- lanes
# Order is the reading order of the landing screen: the outside world first
# (a feed, a spreadsheet), then what this system holds about the person, then
# what the scheme itself supplies, and last the honest nothing.
#
# ``kind`` is how the lane is established:
#   'recorded' — a payslip's provenance blob said so
#   'declared' — the component's own type says so (a formula is calculated)
LANES = (
    {'key': 'feed', 'label': 'Connected system', 'icon': 'plug', 'tone': 'cyan',
     'kind': 'recorded',
     'blurb': 'Values delivered by a connected system for this period.'},
    {'key': 'excel', 'label': 'Spreadsheet', 'icon': 'table', 'tone': 'green',
     'kind': 'recorded',
     'blurb': 'Values read out of an uploaded workbook.'},
    {'key': 'rule', 'label': 'Transformation rules', 'icon': 'gitMerge',
     'tone': 'indigo', 'kind': 'recorded',
     'blurb': 'Keys a transformation rule computed before payroll ran.'},
    {'key': 'employee_field', 'label': 'Payobook records', 'icon': 'user',
     'tone': 'slate', 'kind': 'recorded',
     'blurb': 'Fields read off the employee or contract record.'},
    {'key': 'contract_component', 'label': 'Contract components',
     'icon': 'fileText', 'tone': 'amber', 'kind': 'recorded',
     'blurb': 'Amounts agreed on the employee\'s contract.'},
    {'key': 'constant', 'label': 'Scheme constants', 'icon': 'sigma',
     'tone': 'slate', 'kind': 'declared',
     'blurb': 'The same number for everyone on this scheme.'},
    {'key': 'calculated', 'label': 'Computed by the scheme', 'icon': 'calculator',
     'tone': 'indigo', 'kind': 'declared',
     'blurb': 'Worked out here, by this scheme\'s own formulas.'},
    {'key': 'none', 'label': 'Fallbacks', 'icon': 'minusCircle', 'tone': 'rose',
     'kind': 'recorded',
     'blurb': 'Nothing fed these — they fell back to their default.'},
)
LANE_KEYS = tuple(lane['key'] for lane in LANES)
LANE_BY_KEY = {lane['key']: lane for lane in LANES}

# Which lanes carry a raw-material sheet of their own in the download.
_RAW_LANES = ('feed', 'excel')

# Roles whose values are money. A quantity (hours, days, headcount) is excluded
# even when its role is 'earning', because summing hours into a currency total is
# the kind of number that looks authoritative and means nothing.
_MONEY_ROLES = ('earning', 'deduction', 'employer_cost', 'net')

# `via` is the finer axis: WHY this source won. Labels live here rather than in
# input_provenance because that module is deliberately import-free (no _()).
VIA_LABELS = {
    'binding': 'you bound this component to that source',
    'binding_empty': 'the bound source carried nothing this run',
    'fallback': 'the bound source was empty, so the other one was used',
    'header': 'the column header matched this component',
    'column_letter': 'the spreadsheet column letter lined up',
    'connector_mapping': 'a field mapping on the connected system supplies it',
    'employee_mapping': 'a record-field mapping supplies it',
    'contract': 'the contract carries this component',
    'contract_default': 'it is a contract component and the contract had none',
    'contract_field': 'read straight off a contract field',
    'worked_days': 'taken from a worked-days line',
    'overtime_request': 'from the employee\'s approved overtime',
    'business_trip': 'from the employee\'s approved business trip',
    'constant': 'it is a fixed value',
    'proration': 'this component exists because of proration',
    'retro': 'this component exists because of a retro adjustment',
    'carryover': 'this component exists because of a carry-over',
    'default': 'nothing matched, so its own default was used',
}

_SRC_LABELS = {lane['key']: lane['label'] for lane in LANES}


class PbSourceAtlas(models.AbstractModel):
    _name = 'pb.source.atlas'
    _description = 'Source Atlas'

    # ==================================================================
    # access + fetch
    # ==================================================================
    @api.model
    def _atlas_gate(self):
        """Refuse anyone below the pay-run officer tier. Never sudo past this."""
        user = self.env.user
        if user._is_superuser() or user._is_admin():
            return True
        for group in _GATE_GROUPS:
            try:
                if user.has_group(group):
                    return True
            except ValueError:
                # A group xml-id from a module that is not installed here. Not a
                # reason to refuse everyone — keep checking the rest.
                continue
        raise AccessError(_(
            "The Source Atlas shows every employee's pay data for a whole run. "
            "It is open to payroll officers and above."))

    @api.model
    def _atlas_run(self, run_id):
        """The pay run, read as the real user so record rules still apply."""
        run = self.env['hr.payslip.run'].browse(int(run_id or 0))
        if not run.exists():
            raise UserError(_("That pay run no longer exists."))
        run.check_access('read')
        return run

    @api.model
    def _atlas_slip_rows(self, run, with_values=True):
        """``[(slip_id, employee_id, config_id, sources, values)]`` in one query.

        SQL rather than the ORM on purpose (C8): a 900-employee run would
        otherwise mean 900 record reads of three large text columns, and the ORM
        gives us nothing here — there is no field to compute, only JSON to parse.
        """
        cols = "p.id, p.employee_id, p.formula_config_id, p.formula_input_sources"
        if with_values:
            cols += ", p.formula_input_values, p.formula_computed_values"
        self.env.cr.execute(
            "SELECT " + cols + " FROM hr_payslip p WHERE p.payslip_run_id = %s "
            "ORDER BY p.id", (run.id,))
        return self.env.cr.fetchall()

    @staticmethod
    def _atlas_json(blob):
        """Parse a provenance/value blob. A corrupt one is empty, never fatal."""
        if not blob:
            return {}
        try:
            parsed = json.loads(blob)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    # ==================================================================
    # component metadata
    # ==================================================================
    @api.model
    def _atlas_components(self, config_ids):
        """``{CODE: meta}`` for every component of the run's schemes.

        The component list is the SCHEME's, not the blob's: a component that fed
        nothing this run still belongs on the map, and a code in the blob with no
        rule behind it is surfaced as unknown rather than dropped (C7).
        """
        meta = {}
        configs = self.env['hr.formula.config'].browse(
            [c for c in config_ids if c]).exists()
        for config in configs:
            for rule in config.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
                code = (rule.code or '').strip()
                if not code:
                    continue
                key = code.upper()
                if key in meta:
                    continue
                role = rule.net_role or ''
                quantity = looks_like_a_quantity(rule.name or '', code)
                band = (rule.component_type or '').strip() \
                    or (rule.category_id.name or '') or ''
                meta[key] = {
                    'code': code,
                    'name': rule.name or code,
                    'rule_id': rule.id,
                    'config_id': config.id,
                    'letter': rule.column_letter or '',
                    'sequence': rule.sequence or 0,
                    'column_type': rule.column_type or 'formula',
                    'category': rule.category_id.name or '',
                    'category_code': rule.category_id.code or '',
                    'band': band or _('Ungrouped'),
                    'net_role': role,
                    'net_role_detail': bool(rule.net_role_detail),
                    'net_role_reason': rule.net_role_reason or '',
                    'net_role_confidence': rule.net_role_confidence or '',
                    'quantity': quantity,
                    'money': bool(role in _MONEY_ROLES and not quantity),
                    'classified': bool(role),
                    'default_value': rule.default_value or 0.0,
                    'constant_value': rule.constant_value or 0.0,
                    'formula': rule.excel_formula or '',
                    # VALUEKIND — what the value IS, so the grid can show an
                    # employee code as `11450` rather than `11,450` and a
                    # joining date in the reader's own date format. `money`
                    # here is the field's own default, so a scheme that has
                    # never been classified renders exactly as it did before.
                    'kind': getattr(rule, 'value_kind', '') or 'money',
                    'kind_reason': getattr(rule, 'value_kind_reason', '') or '',
                }
        return meta

    @staticmethod
    def _atlas_declared_lane(component):
        """The lane a component's own TYPE establishes, or None.

        A formula component is ``calculated`` and a constant component is
        ``constant`` — both are facts about the rule, not inferences about a
        value, which is why they may stand in where the provenance blob is
        silent. Everything else must be recorded or it is not claimed.
        """
        column_type = component.get('column_type')
        if column_type == 'formula':
            return 'calculated'
        if column_type == 'constant':
            return 'constant'
        return None

    # ==================================================================
    # 1. LANES
    # ==================================================================
    @api.model
    def get_run_atlas(self, run_id):
        """Lane summary + component map for one pay run. One pass, no per-cell RPC."""
        self._atlas_gate()
        run = self._atlas_run(run_id)
        rows = self._atlas_slip_rows(run, with_values=True)

        payload = {
            'run': {
                'id': run.id,
                'name': run.name or '',
                'date_start': run.date_start and str(run.date_start) or '',
                'date_end': run.date_end and str(run.date_end) or '',
                'state': run.state or '',
                'slip_count': len(rows),
            },
            'lanes': [],
            'components': [],
            'bands': [],
            'unknown_codes': [],
            'notes': [],
            'currency': self._atlas_currency(run),
            # VALUEKIND P2 — the scheme(s) behind this run. The Field types
            # board writes through `hr.formula.config`, not through this
            # read-only facade, so it needs to know which config to address.
            'config_ids': sorted({cfg for _s, _e, cfg, *_r in rows if cfg}),
        }

        if not rows:
            payload['empty'] = 'no_slips'
            payload['notes'].append(_(
                "This pay run has no payslips yet, so there is nothing to trace. "
                "Run payroll for the period and the Atlas fills in."))
            return payload

        components = self._atlas_components({row[2] for row in rows})

        lane_components = defaultdict(set)      # lane -> {CODE}
        lane_employees = defaultdict(set)       # lane -> {slip_id}
        lane_cells = defaultdict(int)
        lane_amount = defaultdict(float)
        comp_lanes = defaultdict(lambda: defaultdict(int))   # CODE -> lane -> n
        comp_cells = defaultdict(int)
        comp_kind = {}                          # CODE -> 'recorded'|'declared'
        unknown = defaultdict(int)
        no_provenance = 0
        ignored_cells = 0
        unclassified_money = False

        for slip_id, _emp_id, _cfg_id, raw_sources, raw_values, raw_computed in rows:
            sources = self._atlas_json(raw_sources)
            values = self._atlas_json(raw_values)
            computed = self._atlas_json(raw_computed)
            if not sources:
                no_provenance += 1

            seen = set()
            for code, entry in sources.items():
                key = (code or '').upper()
                seen.add(key)
                lane = self._atlas_entry_lane(entry)
                component = components.get(key)
                if component is None:
                    unknown[code] += 1
                else:
                    comp_kind.setdefault(key, 'recorded')
                if isinstance(entry, dict) and entry.get('ignored'):
                    ignored_cells += 1
                lane_components[lane].add(key)
                lane_employees[lane].add(slip_id)
                lane_cells[lane] += 1
                comp_lanes[key][lane] += 1
                comp_cells[key] += 1
                if component and component['money']:
                    lane_amount[lane] += self._atlas_number(
                        values.get(code, computed.get(code)))
                elif component and not component['classified']:
                    unclassified_money = True

            # Declared lanes: the components the blob is silent about because
            # their value was never an INPUT. A formula component that produced a
            # number this run is on the map; one that produced nothing is not
            # claimed to have.
            for key, component in components.items():
                if key in seen:
                    continue
                lane = self._atlas_declared_lane(component)
                if not lane:
                    continue
                code = component['code']
                if code not in computed and code not in values:
                    continue
                comp_kind.setdefault(key, 'declared')
                lane_components[lane].add(key)
                lane_employees[lane].add(slip_id)
                lane_cells[lane] += 1
                comp_lanes[key][lane] += 1
                comp_cells[key] += 1
                if component['money'] and lane == 'constant':
                    # A constant's contribution is real money per employee. A
                    # calculated component is NOT summed into a lane total: it is
                    # made of the other lanes' numbers, and adding it would count
                    # the same money twice.
                    lane_amount[lane] += self._atlas_number(
                        values.get(code, computed.get(code)))

        slip_total = len(rows)
        # SC-4 — the lanes render in the SCHEME's configured priority order,
        # and a lane the scheme switched off says so rather than posing as an
        # empty one. Declared lanes (constants, calculated) and the fallback
        # lane keep their tail position.
        lane_defs = list(LANES)
        lane_enabled = {}
        try:
            cfg_ids = sorted({cfg for _s, _e, cfg, *_r in rows if cfg})
            Config = self.env['hr.formula.config'].sudo()
            config = Config.browse(cfg_ids[0]) if cfg_ids else Config
            if config and config.exists() \
                    and 'source_priority' in Config._fields:
                token_of = {'feed': 'api', 'rule': 'api', 'excel': 'excel',
                            'employee_field': 'records',
                            'contract_component': 'records'}
                order = [t.strip() for t in
                         (config.source_priority or '').split(',')
                         if t.strip() in ('api', 'excel', 'records')]
                for token in ('api', 'excel', 'records'):
                    if token not in order:
                        order.append(token)
                pos = {t: i for i, t in enumerate(order)}
                lane_defs.sort(
                    key=lambda l: pos.get(token_of.get(l['key']), 99))
                for lane in lane_defs:
                    token = token_of.get(lane['key'])
                    lane_enabled[lane['key']] = (
                        token is None or config._source_lane_ok(token))
        except Exception:       # noqa: BLE001 — display, never the atlas
            lane_enabled = {}
        for lane in lane_defs:
            key = lane['key']
            enabled = lane_enabled.get(key, True)
            employees = len(lane_employees.get(key, ()))
            payload['lanes'].append({
                'key': key,
                'label': lane['label'],
                'icon': lane['icon'],
                'tone': lane['tone'],
                'kind': lane['kind'],
                'enabled': enabled,
                'blurb': (lane['blurb'] if enabled else
                          _("Switched off in this scheme's sources settings.")),
                'components': len(lane_components.get(key, ())),
                'employees': employees,
                'cells': lane_cells.get(key, 0),
                'coverage': round(100.0 * employees / slip_total, 1) if slip_total else 0.0,
                'amount': round(lane_amount.get(key, 0.0), 2) if key != 'calculated' else None,
                'amount_note': _("Made of the other lanes' numbers — not summed here.")
                               if key == 'calculated' else '',
                'muted': not lane_cells.get(key, 0),
                'downloadable': bool(lane_cells.get(key, 0)),
            })

        band_order = []
        for key, component in sorted(
                components.items(), key=lambda kv: (kv[1]['sequence'], kv[1]['code'])):
            lanes = dict(comp_lanes.get(key, {}))
            if not lanes:
                continue
            top = max(lanes.items(), key=lambda kv: kv[1])[0]
            payload['components'].append({
                'code': component['code'],
                'name': component['name'],
                'band': component['band'],
                'category': component['category'],
                'net_role': component['net_role'],
                'net_role_detail': component['net_role_detail'],
                'quantity': component['quantity'],
                'money': component['money'],
                'column_type': component['column_type'],
                'lanes': lanes,
                'lane': top,
                'kind': comp_kind.get(key, 'recorded'),
                'cells': comp_cells.get(key, 0),
                'letter': component['letter'],
            })
            if component['band'] not in band_order:
                band_order.append(component['band'])
        payload['bands'] = band_order

        payload['unknown_codes'] = [
            {'code': code, 'cells': n}
            for code, n in sorted(unknown.items(), key=lambda kv: -kv[1])[:40]
        ]
        payload['no_provenance_slips'] = no_provenance
        payload['ignored_cells'] = ignored_cells
        if no_provenance:
            payload['notes'].append(_(
                "%(n)s of these payslips were computed before source tracking "
                "existed, so their values carry no origin.",
                n=no_provenance))
        if payload['unknown_codes']:
            payload['notes'].append(_(
                "%(n)s codes carry a source but no longer match a component on "
                "this scheme — they are listed so nothing is hidden.",
                n=len(payload['unknown_codes'])))
        if unclassified_money:
            payload['notes'].append(_(
                "Some components have no pay role yet, so they are left out of "
                "the money totals. Classify the scheme to include them."))
        return payload

    @staticmethod
    def _atlas_entry_lane(entry):
        """The lane one provenance entry names, degraded to 'none' if unreadable."""
        if not isinstance(entry, dict):
            return 'none'
        src = entry.get('src')
        return src if src in input_provenance.SOURCES else 'none'

    @staticmethod
    def _atlas_number(value):
        """A float, or 0.0 — a text component must never poison a money total."""
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(',', ''))
        except (TypeError, ValueError):
            return 0.0

    @api.model
    def _atlas_currency(self, run):
        currency = self.env.company.currency_id
        if 'pb_currency_id' in run._fields and run.pb_currency_id:
            currency = run.pb_currency_id
        return {
            'symbol': currency.symbol or '',
            'position': currency.position or 'after',
            'decimals': currency.decimal_places,
            'name': currency.name or '',
        }

    # ==================================================================
    # 2. GRID
    # ==================================================================
    @api.model
    def get_grid(self, run_id, offset=0, limit=_GRID_LIMIT, search='',
                 lane=None, band=None, codes=None):
        """One window of the employees x components matrix.

        The window is taken server-side: the client asks for rows
        ``offset..offset+limit`` and gets exactly those, so a 900-employee run
        never puts 900 rows in the DOM (C8). Searching narrows by employee name
        or code through the ORM, which keeps translated names working.
        """
        self._atlas_gate()
        run = self._atlas_run(run_id)
        offset = max(0, int(offset or 0))
        limit = max(1, min(int(limit or _GRID_LIMIT), _GRID_MAX))

        domain = [('payslip_run_id', '=', run.id)]
        term = (search or '').strip()
        if term:
            domain += ['|', '|',
                       ('employee_id.name', 'ilike', term),
                       ('employee_id.barcode', 'ilike', term),
                       ('number', 'ilike', term)]
        Payslip = self.env['hr.payslip']
        total = Payslip.search_count(domain)
        slips = Payslip.search(domain, order='employee_id, id',
                               offset=offset, limit=limit)

        components = self._atlas_components(slips.mapped('formula_config_id').ids)
        wanted = None
        if codes:
            wanted = {str(c).upper() for c in codes}

        rows = []
        for slip in slips:
            sources = self._atlas_json(slip.formula_input_sources)
            values = self._atlas_json(slip.formula_input_values)
            computed = self._atlas_json(slip.formula_computed_values)
            cells = {}
            for code, component in components.items():
                if wanted is not None and code not in wanted:
                    continue
                if band and component['band'] != band:
                    continue
                entry = sources.get(component['code']) or sources.get(code)
                if entry is not None:
                    cell_lane = self._atlas_entry_lane(entry)
                    kind = 'recorded'
                    key = (entry or {}).get('key') if isinstance(entry, dict) else None
                    via = (entry or {}).get('via') if isinstance(entry, dict) else None
                else:
                    cell_lane = self._atlas_declared_lane(component)
                    kind, key, via = 'declared', None, None
                    if not cell_lane:
                        continue
                raw = values.get(component['code'], computed.get(component['code']))
                if raw is None and entry is None:
                    continue
                if lane and cell_lane != lane:
                    continue
                cells[component['code']] = {
                    'v': raw,
                    'n': self._atlas_number(raw),
                    'l': cell_lane,
                    'k': key or '',
                    'via': via or '',
                    'kind': kind,
                    # `kind` above is how the LANE was established (recorded vs
                    # declared) and predates this field — `t` is what the VALUE
                    # is. Two different questions that both wanted the word
                    # "kind"; the short name keeps the payload small, since this
                    # rides on every cell of a 40 x 95 window.
                    't': component.get('kind') or 'money',
                }
            rows.append({
                'slip_id': slip.id,
                'employee_id': slip.employee_id.id,
                'employee': slip.employee_id.display_name or '',
                'code': slip.employee_id.barcode or '',
                'department': slip.employee_id.department_id.display_name or '',
                'has_provenance': bool(sources),
                'cells': cells,
            })

        return {
            'total': total,
            'offset': offset,
            'limit': limit,
            'rows': rows,
            'search': term,
            'lane': lane or '',
            'band': band or '',
        }

    # ==================================================================
    # 3. JOURNEY
    # ==================================================================
    @api.model
    def get_journey(self, run_id, slip_id, code):
        """One value's whole chain: where it came from, then every hop to net pay."""
        self._atlas_gate()
        run = self._atlas_run(run_id)
        slip = self.env['hr.payslip'].browse(int(slip_id or 0))
        if not slip.exists() or slip.payslip_run_id != run:
            raise UserError(_("That payslip is not part of this pay run."))
        slip.check_access('read')
        code = (code or '').strip()
        if not code:
            raise UserError(_("Pick a component to trace."))

        sources = self._atlas_json(slip.formula_input_sources)
        values = self._atlas_json(slip.formula_input_values)
        computed = self._atlas_json(slip.formula_computed_values)
        components = self._atlas_components(slip.formula_config_id.ids)
        component = components.get(code.upper())

        entry = sources.get(code) or sources.get(code.upper())
        raw_value = values.get(code, computed.get(code))
        if raw_value is None and component:
            raw_value = computed.get(component['code'], values.get(component['code']))

        journey = {
            'run_id': run.id,
            'slip_id': slip.id,
            'employee': slip.employee_id.display_name or '',
            'employee_id': slip.employee_id.id,
            'code': component['code'] if component else code,
            'name': component['name'] if component else code,
            'value': raw_value,
            'number': self._atlas_number(raw_value),
            'money': bool(component and component['money']),
            'quantity': bool(component and component['quantity']),
            'kind': (component or {}).get('kind') or 'money',
            'kind_reason': (component or {}).get('kind_reason') or '',
            'net_role': component['net_role'] if component else '',
            'net_role_reason': component['net_role_reason'] if component else '',
            'band': component['band'] if component else '',
            'category': component['category'] if component else '',
            'formula': component['formula'] if component else '',
            'column_type': component['column_type'] if component else '',
            'currency': self._atlas_currency(run),
            'warnings': [],
            'hops': [],
            'transformation': None,
            'no_provenance': not sources,
        }

        if not component:
            journey['warnings'].append(_(
                "This code carries a source but no longer matches a component on "
                "the scheme, so its journey stops here."))

        if entry is None and not sources:
            journey['lane'] = 'none'
            journey['lane_label'] = _('Not tracked')
            journey['source'] = {
                'kind': 'untracked',
                'title': _('Computed before source tracking existed'),
                'detail': _(
                    "This payslip was computed before the system recorded where "
                    "each value came from. Recomputing the run captures it."),
            }
        else:
            journey['source'] = self._atlas_source_step(slip, component, entry, code)
            journey['lane'] = journey['source']['lane']
            journey['lane_label'] = _SRC_LABELS.get(journey['lane'], journey['lane'])
            if journey['source'].get('transformation'):
                journey['transformation'] = journey['source'].pop('transformation')

        if component:
            journey['hops'] = self._atlas_formula_hops(
                slip, component, components, values, computed, journey)
        return journey

    # ------------------------------------------------------------------
    # the source step
    # ------------------------------------------------------------------
    @api.model
    def _atlas_source_step(self, slip, component, entry, code):
        """What the value arrived as, on the far side of the payroll boundary."""
        if entry is None:
            lane = self._atlas_declared_lane(component or {}) or 'none'
            if lane == 'calculated':
                return {
                    'lane': 'calculated',
                    'kind': 'declared',
                    'title': _('Worked out here'),
                    'detail': _("This component has no source of its own — this "
                                "scheme's formula produces it."),
                    'snippet': (component or {}).get('formula', ''),
                }
            if lane == 'constant':
                return {
                    'lane': 'constant',
                    'kind': 'declared',
                    'title': _('A fixed value on the scheme'),
                    'detail': _('The same number for every employee.'),
                    'raw_value': (component or {}).get('constant_value'),
                }
            return {
                'lane': 'none',
                'kind': 'declared',
                'title': _('Nothing fed this'),
                'detail': _("No source carried a value, so the component's own "
                            "default was used."),
                'raw_value': (component or {}).get('default_value'),
            }

        src = self._atlas_entry_lane(entry)
        key = entry.get('key') or ''
        via = entry.get('via') or 'default'
        step = {
            'lane': src,
            'kind': 'recorded',
            'key': key,
            'via': via,
            'via_label': VIA_LABELS.get(via, via.replace('_', ' ')),
            'fell_back': bool(entry.get('fell_back')),
            'ignored': entry.get('ignored') or None,
            'title': _SRC_LABELS.get(src, src),
            'detail': '',
        }
        if src in ('feed', 'excel', 'rule'):
            self._atlas_fill_row_source(slip, step, key, src)
        elif src == 'employee_field':
            self._atlas_fill_record_source(slip, component, step)
        elif src == 'contract_component':
            self._atlas_fill_contract_source(slip, component, step)
        elif src == 'constant':
            step['raw_value'] = (component or {}).get('constant_value')
            step['detail'] = _('The same number for every employee on this scheme.')
        else:
            step['raw_value'] = (component or {}).get('default_value')
            step['detail'] = _("No source carried a value for %s.", code)
        return step

    @api.model
    def _atlas_fill_row_source(self, slip, step, key, src):
        """The imported row this value was read out of, and the feed row behind it.

        Sudo is scoped to the two models a payroll officer may not have an ACL on
        — the import line and the feed store — and to nothing else.
        """
        line = self.env['hr.payroll.import.line'].sudo().search(
            [('payslip_id', '=', slip.id)], limit=1)
        if not line:
            line = self.env['hr.payroll.import.line'].sudo().search(
                [('employee_id', '=', slip.employee_id.id),
                 ('batch_id.date_from', '<=', slip.date_to or slip.date_from),
                 ('batch_id.date_to', '>=', slip.date_from or slip.date_to)],
                order='id desc', limit=1)
        if not line:
            step['detail'] = _(
                "The value was recorded as coming from %(src)s on key '%(key)s', "
                "but the imported row behind it is no longer on file.",
                src=_SRC_LABELS.get(src, src), key=key or '?')
            return

        batch = line.batch_id
        raw = line.get_raw_data() or {}
        topup = line.get_topup_data() or {}
        found, blob = None, ''
        if key and key in raw:
            found, blob = raw.get(key), 'primary'
        elif key and key in topup:
            found, blob = topup.get(key), 'added'
        step['raw_value'] = found
        step['row'] = {
            'batch': batch.display_name or batch.name or '',
            'batch_id': batch.id,
            'source_type': batch.source_type or '',
            'connector': batch.connector_id.display_name or '',
            'period': '%s – %s' % (batch.date_from or '', batch.date_to or ''),
            'row_no': line.sequence,
            'blob': blob,
            'sheet': getattr(batch, 'file_sheet_name', '') or '',
        }
        if src == 'excel':
            step['detail'] = _(
                "Read from column '%(key)s' of the uploaded workbook, row %(row)s.",
                key=key or '?', row=line.sequence or '?')
        else:
            step['detail'] = _(
                "Delivered by %(conn)s on key '%(key)s' for this period.",
                conn=batch.connector_id.display_name or _('a connected system'),
                key=key or '?')
            self._atlas_fill_feed_store(slip, step, key, batch, line)
        if key:
            rule = self.env['hr.api.transformation.rule'].sudo().search(
                [('output_key', '=', key)], limit=1)
            if rule:
                step['transformation'] = {
                    'name': rule.name or key,
                    'output_key': rule.output_key or key,
                    'rule_type': rule.rule_type or '',
                    'summary': rule.plain_summary or rule.excel_formula or '',
                    'source_data_type': rule.source_data_type or '',
                    'connector': rule.connector_id.display_name
                    if 'connector_id' in rule._fields else '',
                }

    @api.model
    def _atlas_fill_feed_store(self, slip, step, key, batch, line):
        """The connected system's own row — when it was pulled, and what it held."""
        Store = self.env['hr.api.data.store'].sudo()
        domain = [('import_batch_id', '=', batch.id)]
        external = line.employee_code or ''
        candidates = Store.search(domain, limit=400)
        if not candidates and batch.connector_id:
            candidates = Store.search([
                ('connector_id', '=', batch.connector_id.id),
                ('period_from', '<=', slip.date_to or slip.date_from),
                ('period_to', '>=', slip.date_from or slip.date_to),
            ], limit=400)
        for record in candidates:
            if record.employee_id and record.employee_id != slip.employee_id:
                continue
            if not record.employee_id and external and \
                    (record.employee_external_id or '') != external:
                continue
            data = record.get_mappable_data() or {}
            if key and key not in data:
                continue
            step['feed'] = {
                'data_type': record.data_type or '',
                'external_id': record.employee_external_id or '',
                'pulled': record.pull_date and str(record.pull_date) or '',
                'period': '%s – %s' % (record.period_from or '', record.period_to or ''),
                'state': record.state or '',
                'value': data.get(key),
                'endpoint': record.endpoint_id.display_name
                if 'endpoint_id' in record._fields else '',
            }
            return

    @api.model
    def _atlas_fill_record_source(self, slip, component, step):
        """The employee/contract field a record mapping points this component at."""
        mapping = None
        if component:
            mapping = self.env['hr.payslip.import.mapping'].sudo().search(
                [('salary_structure_id', '=', component['config_id']),
                 ('component_id', '=', component['rule_id'])], limit=1)
        if not mapping:
            step['detail'] = _(
                "Read off this employee's own record. The exact field is no "
                "longer mapped, so it cannot be named here.")
            return
        model = mapping.target_model_id.model or ''
        field = mapping.target_field_id.name or ''
        record = slip.employee_id if model == 'hr.employee' else slip.contract_id
        live = None
        if record and field and field in record._fields:
            try:
                live = record[field]
                if hasattr(live, 'display_name'):
                    live = live.display_name
            except Exception:       # a field the user may not read
                live = None
        step['record'] = {
            'model': mapping.target_model_id.name or model,
            'model_tech': model,
            'field': mapping.target_field_id.field_description or field,
            'field_tech': field,
            'record': record.display_name if record else '',
        }
        step['raw_value'] = live if not hasattr(live, 'id') else str(live)
        step['detail'] = _(
            "Read off %(model)s · %(field)s for this employee.",
            model=mapping.target_model_id.name or model,
            field=mapping.target_field_id.field_description or field)

    @api.model
    def _atlas_fill_contract_source(self, slip, component, step):
        """The contract line that carries this component's agreed amount."""
        contract = slip.contract_id
        step['record'] = {
            'model': _('Contract'),
            'record': contract.display_name if contract else '',
        }
        if not contract:
            step['detail'] = _(
                "Recorded as a contract component, but this payslip has no "
                "contract attached.")
            return
        wanted = (component or {}).get('code', '').upper().replace('_', '')
        for advantage in contract.advantages_ids:
            template = advantage.advantage_template_id
            adv_code = (advantage.advantage_template_code
                        or (template.code if template else '') or '')
            if adv_code.upper().replace('_', '') != wanted:
                continue
            step['raw_value'] = advantage.amount
            step['record']['field'] = (
                template.name if template else adv_code) or adv_code
            step['detail'] = _(
                "The amount agreed on this contract for %(name)s.",
                name=step['record']['field'])
            return
        step['detail'] = _(
            "This is a contract component, and this contract carries no amount "
            "for it — so it came through as zero.")

    # ------------------------------------------------------------------
    # the formula hops
    # ------------------------------------------------------------------
    @api.model
    def _atlas_formula_hops(self, slip, component, components, values, computed,
                            journey):
        """Every hop from this component to net pay, off the Phase-1 signed graph.

        The graph is NETROLE Phase 1's — ``_net_role_edges`` reads the scheme's
        own formulas and returns ``{target: [(source, sign, derived, conf)]}``.
        Inverting it once gives the direction money flows, and the shortest path
        to the net component is the chain a person actually wants to read.
        """
        config = slip.formula_config_id
        if not config:
            return []
        rules = config._net_role_rules()
        net_rule = config._net_role_find_net_rule(rules)
        if not net_rule:
            journey['warnings'].append(_(
                "This scheme has no net pay component, so the chain cannot be "
                "followed to the end."))
            return []

        by_id = {rule.id: rule for rule in rules}
        start_id = component.get('rule_id')
        if start_id not in by_id:
            return []
        journey['net_code'] = net_rule.code or ''
        journey['net_value'] = computed.get(net_rule.code, values.get(net_rule.code))

        if start_id == net_rule.id:
            journey['is_net'] = True
            return []

        incoming = config._net_role_edges(rules)
        outgoing = defaultdict(list)
        for target_id, edges in incoming.items():
            for source_id, sign, derived, confidence in edges:
                outgoing[source_id].append((target_id, sign, derived, confidence))

        # Breadth-first: the shortest chain is the honest one to show. A longer
        # path exists through nearly every aggregate, and showing it would make a
        # two-step story look like a nine-step one.
        queue = [(start_id, [])]
        seen = {start_id}
        path = None
        while queue and path is None:
            node, trail = queue.pop(0)
            if len(trail) >= _HOP_CAP:
                continue
            for target_id, sign, derived, confidence in outgoing.get(node, ()):
                if target_id in seen:
                    continue
                step = trail + [(target_id, sign, derived, confidence)]
                if target_id == net_rule.id:
                    path = step
                    break
                seen.add(target_id)
                queue.append((target_id, step))
        if path is None:
            journey['warnings'].append(_(
                "This component does not reach net pay through any formula on "
                "this scheme — it is carried for information."))
            return []

        hops, cumulative = [], 1
        for target_id, sign, derived, confidence in path:
            cumulative *= (sign or 1)
            rule = by_id.get(target_id)
            if not rule:
                continue
            meta = components.get((rule.code or '').upper(), {})
            value = computed.get(rule.code, values.get(rule.code))
            hops.append({
                'code': rule.code or '',
                'name': rule.name or rule.code or '',
                'formula': rule.excel_formula or '',
                'sign': 1 if (sign or 1) > 0 else -1,
                'cum_sign': 1 if cumulative > 0 else -1,
                'derived': bool(derived),
                'confidence': confidence or '',
                'net_role': rule.net_role or '',
                'net_role_detail': bool(rule.net_role_detail),
                'band': meta.get('band', ''),
                'value': value,
                'number': self._atlas_number(value),
                'is_net': target_id == net_rule.id,
                'money': bool(meta.get('money')),
                'kind': meta.get('kind') or 'money',
            })
        if len(hops) >= _HOP_CAP:
            journey['warnings'].append(_(
                "The chain is longer than %(n)s hops and has been cut short here.",
                n=_HOP_CAP))
        return hops
