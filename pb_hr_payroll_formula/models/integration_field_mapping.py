# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class HrIntegrationFieldMapping(models.Model):
    """
    Integration Field Mapping - Maps fields from external HR systems
    to formula rule input columns.
    """
    _name = 'hr.integration.field.mapping'
    _description = 'Integration Field Mapping'
    _order = 'sequence, source_field'
    _rec_name = 'display_name'

    # ==========================================
    # LINKS
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector',
        string='Connector',
        required=True,
        ondelete='cascade',
        index=True
    )

    connector_type = fields.Selection(
        related='connector_id.connector_type',
        store=True
    )

    # Which FEED this mapping reads from. Optional: mappings predate endpoints,
    # and a connector with one implied API is still a legitimate connector. The
    # `set null` is deliberate — deleting a feed must not delete the mapping
    # work somebody did against it; it only stops claiming which API it came
    # from.
    endpoint_id = fields.Many2one(
        'hr.integration.endpoint',
        string='Endpoint',
        ondelete='set null',
        index=True,
        help="The connector feed this source field arrives on."
    )

    # ==========================================
    # SOURCE FIELD
    # ==========================================
    source_field = fields.Char(
        string='Source Field Path',
        required=True,
        help="Field name or path in source system (e.g., 'base_salary', 'employee.department.name')"
    )

    source_field_label = fields.Char(
        string='Source Field Label',
        help="Human-readable name from source system"
    )

    source_data_type = fields.Selection([
        ('string', 'Text'),
        ('number', 'Number'),
        ('integer', 'Integer'),
        ('float', 'Decimal'),
        ('date', 'Date'),
        ('datetime', 'Date/Time'),
        ('boolean', 'Yes/No'),
        ('currency', 'Currency')
    ], string='Source Data Type', default='number')

    source_sample_value = fields.Char(
        string='Sample Value',
        help="Example value from source system"
    )

    # ==========================================
    # TARGET (Formula Rule)
    # ==========================================
    target_rule_id = fields.Many2one(
        'hr.formula.rule',
        string='Target Formula Rule',
        domain="[('column_type', '=', 'input')]",
        help="Formula rule to receive this value"
    )

    target_column_letter = fields.Char(
        related='target_rule_id.column_letter',
        string='Target Column',
        store=True
    )

    target_rule_code = fields.Char(
        related='target_rule_id.code',
        string='Target Code',
        store=True
    )

    # ==========================================
    # TRANSFORMATION
    # ==========================================
    transformation_type = fields.Selection([
        ('direct', 'Direct Copy'),
        ('multiply', 'Multiply by Factor'),
        ('divide', 'Divide by Factor'),
        ('add', 'Add Value'),
        ('subtract', 'Subtract Value'),
        ('round', 'Round to Decimals'),
        ('abs', 'Absolute Value'),
        ('default_if_empty', 'Use Default if Empty'),
        ('python', 'Python Expression')
    ], string='Transformation', default='direct')

    transformation_value = fields.Float(
        string='Factor/Value',
        default=1.0,
        help="Multiplication factor, divisor, or value to add/subtract"
    )

    transformation_decimals = fields.Integer(
        string='Decimal Places',
        default=2,
        help="For rounding transformation"
    )

    transformation_code = fields.Text(
        string='Python Expression',
        help="""
Python expression to transform the value.
Available variables (evaluated with safe_eval — no ORM access):
- value: The source value
- record: The full source record (plain dict)

Example: value * 1.1 if value > 1000 else value
        """
    )

    # ==========================================
    # VALIDATION
    # ==========================================
    is_required = fields.Boolean(
        string='Required',
        default=False,
        help="Raise error if this field is missing in source data"
    )

    default_value = fields.Float(
        string='Default Value',
        default=0.0,
        help="Value to use when source field is empty"
    )

    min_value = fields.Float(
        string='Min Value',
        help="Minimum allowed value (leave empty for no limit)"
    )

    max_value = fields.Float(
        string='Max Value',
        help="Maximum allowed value (leave empty for no limit)"
    )

    # ==========================================
    # STATUS
    # ==========================================
    is_mapped = fields.Boolean(
        string='Is Mapped',
        compute='_compute_is_mapped',
        store=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # F114 — provenance/confidence of a mapping row. 'suggested' rows came from a
    # vendor template but are NOT confirmed against the real payload, so they are
    # excluded from sync until promoted to 'active' (via the onboarding batch test).
    active_state = fields.Selection([
        ('active', 'Active'),
        ('suggested', 'Suggested'),
        ('ignored', 'Ignored'),
    ], string='Mapping State', default='active', index=True)

    notes = fields.Text(
        string='Notes'
    )

    # W62 (D-I4) — surfaced on the mapping canvas as a red badge tint. Set when a
    # `python` transform raises at sync/test time (safe_eval failure, e.g. an
    # `env`-touching expr after env was removed from the context): the value falls
    # back to `default_value` + a server log, but the FAILURE stays visible (C7),
    # not silent. Cleared the moment the same row transforms cleanly again.
    has_transform_error = fields.Boolean(
        string='Transform Error',
        default=False,
        help="A Python transform on this mapping last failed and fell back to the "
             "default value. Fix the expression in the backend form."
    )
    transform_error_msg = fields.Char(
        string='Transform Error Detail'
    )

    # ==========================================
    # DISPLAY
    # ==========================================
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    @api.depends('source_field', 'source_field_label', 'target_rule_id')
    def _compute_display_name(self):
        for record in self:
            source = record.source_field_label or record.source_field
            target = record.target_rule_id.name if record.target_rule_id else 'Unmapped'
            record.display_name = f"{source} -> {target}"

    @api.depends('target_rule_id')
    def _compute_is_mapped(self):
        for record in self:
            record.is_mapped = bool(record.target_rule_id)

    # ==========================================
    # TRANSFORMATION METHODS
    # ==========================================
    # W62 (D-I3, skeleton S-I1) — the transform is ONE function. The persisted
    # sync path (`transform_value`) and the draft-preview path (`preview_transform`,
    # driven by the studio RPC `api_transform_preview`) both run `_apply_transform_ops`
    # for the op ladder and `_clamp_result` for the min/max clamp, so a preview can
    # never show a value the sync would not produce. The numeric coercion + is_required
    # gate lives in BOTH callers identically (per the S-I1 gotcha) — never inside the
    # shared ladder.
    _T_FIELDS = ('transformation_type', 'transformation_value',
                 'transformation_decimals', 'transformation_code')

    def _apply_transform_ops(self, vals, value, record=None):
        """Pure op ladder (S-I1). `vals` = the transform fields, drawn from the
        RECORD for the sync path or from a DRAFT for previews — same function, both
        callers. Raises ValidationError on divide-by-zero (loud, never a silent 0).
        `python` runs through safe_eval with NO `env` in the context (D-I4)."""
        t = (vals.get('transformation_type') or 'direct')
        v = vals.get('transformation_value') or 0.0
        dec = vals.get('transformation_decimals')
        dec = 2 if dec is None else int(dec)

        if t == 'direct':
            return value
        if t == 'multiply':
            return value * v
        if t == 'divide':
            if v == 0:
                raise ValidationError(_("Division by zero in transformation"))
            return value / v
        if t == 'add':
            return value + v
        if t == 'subtract':
            return value - v
        if t == 'round':
            return round(value, dec)
        if t == 'abs':
            return abs(value)
        if t == 'default_if_empty':
            return value if value else v
        if t == 'python':
            expr = (vals.get('transformation_code') or '').strip()
            if not expr:
                return value
            # D-I4: safe_eval, NO env. Draft previews never reach here (the RPC
            # refuses python drafts); the sync path below catches + flags + falls back.
            from odoo.tools.safe_eval import safe_eval
            # record must be PLAIN DATA: safe_eval only blocks underscore
            # attributes, so an ORM recordset here would expose record.env.
            return safe_eval(expr, {'value': value,
                                    'record': record if isinstance(record, dict) else {}})
        return value

    def _clamp_result(self, result):
        """Min/max clamp — numeric results only, and treat 0 as "unset" (Float
        fields can't be None, so 0.0 means no bound). Shared by sync + preview so
        the clamp can never diverge (S-I1 gotcha)."""
        if isinstance(result, (int, float)) and not isinstance(result, bool):
            if self.min_value:
                result = max(result, self.min_value)
            if self.max_value:
                result = min(result, self.max_value)
        return result

    def _flag_transform_error(self, is_error, msg=''):
        """Persist the python-transform failure state so the canvas can red-tint the
        badge (D-I4, C7). Writes only on a genuine state change — the sync path calls
        this per payload across thousands of employees, so a no-op must not write."""
        try:
            msg = (msg or '')[:500] if is_error else False
            if bool(self.has_transform_error) != bool(is_error) or \
                    (is_error and (self.transform_error_msg or '') != (msg or '')):
                self.sudo().write({'has_transform_error': bool(is_error),
                                   'transform_error_msg': msg})
        except Exception:
            # never let error-flagging break the transform itself
            pass

    def transform_value(self, value, record=None):
        """Apply transformation to a value (persisted sync path)."""
        self.ensure_one()

        # Handle None/empty values
        if value is None or value == '':
            if self.is_required:
                raise ValidationError(_(
                    "Required field '%s' is missing in source data"
                ) % self.source_field)
            return self.default_value

        # Convert to float if needed
        try:
            if self.source_data_type in ('number', 'float', 'integer', 'currency'):
                value = float(value)
        except (ValueError, TypeError):
            if self.is_required:
                raise ValidationError(_(
                    "Cannot convert value '%s' to number for field '%s'"
                ) % (value, self.source_field))
            return self.default_value

        vals = {f: self[f] for f in self._T_FIELDS}
        if self.transformation_type == 'python':
            # python is caught + flagged + fallen back (never crashes the sync);
            # every other op propagates (divide-by-zero stays loud, as before).
            try:
                result = self._apply_transform_ops(vals, value, record)
                self._flag_transform_error(False)
            except Exception as e:
                _logger.error("Transformation error for %s: %s", self.source_field, e)
                self._flag_transform_error(True, str(e) or type(e).__name__)
                result = self.default_value
        else:
            result = self._apply_transform_ops(vals, value, record)

        return self._clamp_result(result)

    def preview_transform(self, draft_vals):
        """W62 draft preview (D-I3) — evaluate a DRAFT transform against this row's
        `source_sample_value` WITHOUT writing anything. `python` drafts are refused
        (the canvas keeps python read-only — D-I2). Returns a JSON-safe dict:
        {ok, sample, result} or {ok: False, readonly|error}."""
        self.ensure_one()
        draft = dict(draft_vals or {})
        t = draft.get('transformation_type') or 'direct'
        if t == 'python':
            return {'ok': False, 'readonly': True,
                    'msg': _("Python transforms are edited in the backend form, "
                             "not on the canvas.")}

        raw = self.source_sample_value
        # MIRROR the sync path exactly (S-I1 / review Major): an empty or
        # unparseable sample short-circuits to default_value WITHOUT running the
        # ladder or clamp — sync's early-return does exactly that, so a preview
        # that laddered the default showed a value sync would never produce
        # (e.g. add+5 on an empty sample: preview 5.0 vs sync 0.0).
        # ORM trap: an unset Char reads as False (not None/''), and
        # float(False) == 0.0 would silently slip an "empty" sample into the
        # ladder — the exact divergence this branch exists to prevent.
        if not raw or (isinstance(raw, str) and not raw.strip()):
            return {'ok': True, 'sample': None, 'no_sample': True,
                    'result': self._jsonable(self.default_value),
                    'msg': _("No sample value stored — sync would emit the "
                             "default (%s).") % self.default_value}
        try:
            value = float(raw) if self.source_data_type in (
                'number', 'float', 'integer', 'currency') else raw
        except (ValueError, TypeError):
            return {'ok': True, 'sample': self._jsonable(raw), 'no_sample': True,
                    'result': self._jsonable(self.default_value),
                    'msg': _("Sample is not numeric — sync would emit the "
                             "default (%s).") % self.default_value}

        try:
            result = self._clamp_result(self._apply_transform_ops(draft, value, {}))
        except ValidationError as e:
            # EXPECTED, and the message was written for a human: divide-by-zero
            # is the one the canvas produces daily. Not logged — a user typing a
            # 0 into a divisor is not an incident.
            return {'ok': False, 'error': (e.args and e.args[0]) or str(e)}
        except Exception as e:
            # W40 — this catch narrows nothing, so it must HIDE nothing either.
            # It used to return `str(e)` and say nothing anywhere else: a
            # preview that failed for a reason nobody anticipated left no trace
            # at all, and the one place it could have been diagnosed (the
            # server log) was silent while the user read a bare exception
            # string. Two changes, both about honesty rather than about
            # behaviour:
            #   * it reports, with the row and the draft that produced it, so
            #     the next unexpected failure is one grep away;
            #   * the USER gets a sentence rather than a repr. `str(e)` on an
            #     unanticipated exception is as likely to be '' or a stack-shaped
            #     internal as it is to be readable, and the canvas prints it
            #     verbatim beside a field name.
            _logger.warning(
                "Transform preview failed for mapping %s (%s) with draft %s: "
                "%s: %s", self.id, self.source_field, draft,
                type(e).__name__, e)
            return {'ok': False,
                    'error': _("This transform could not be previewed. The "
                               "details are in the server log."),
                    'exception': type(e).__name__}
        return {'ok': True,
                'sample': self._jsonable(raw),
                'result': self._jsonable(result)}

    def get_value_from_record(self, record):
        """Extract and transform value from a source record"""
        self.ensure_one()

        # Navigate nested path (e.g., "employee.department.name")
        value = record
        for key in self.source_field.split('.'):
            if isinstance(value, dict):
                value = value.get(key)
            elif hasattr(value, key):
                value = getattr(value, key)
            else:
                value = None
                break

        # Apply transformation
        return self.transform_value(value, record)

    # ==========================================
    # SOURCE FIELD DISCOVERY (T4.3)
    # ==========================================
    @api.model
    def get_available_source_fields(self, connector_id, data_type=None):
        """Flatten the connector's most recent stored payloads into dot-path
        source fields with a sample value + inferred type. Falls back to
        hr.employee's own fields (ir.model.fields) when nothing is stored yet.

        Returns [{'path', 'sample', 'type', 'label'}] sorted by path.

        `data_type` (Integrations Cycle 2) narrows the payloads to ONE feed —
        `hr.integration.endpoint.data_type` and `hr.api.data.store.data_type`
        are the same vocabulary, which is why the endpoint model imports the
        store's list rather than retyping it. Two rules the narrowing keeps:

          * an UNKNOWN data type is ignored rather than obeyed. A value that
            reaches a domain straight from the browser is the hole
            `pb.integrations.get_ledger`'s whitelist exists to close, and the
            honest failure of a typo'd feed key is "all the fields", not "no
            fields, and no reason given";
          * the `hr.employee` fallback stays keyed on "nothing was stored",
            NOT on "nothing was stored FOR THIS FEED". A leave feed with no
            rows would otherwise offer the employee schema as if it were the
            leave API's shape, which is the wrong answer stated confidently.
            An empty feed returns an empty list and the studio says so.
        """
        connector = self.env['hr.integration.connector'].browse(int(connector_id or 0))
        if not connector.exists():
            return []
        Store = self.env['hr.api.data.store']
        domain = [('connector_id', '=', connector.id)]
        known = dict(Store._fields['data_type'].selection)
        scoped = bool(data_type) and data_type in known
        if scoped:
            domain = domain + [('data_type', '=', data_type)]
        stores = Store.search(domain, order='pull_date desc, id desc', limit=20)
        found = {}
        for store in stores:
            for source in (store.raw_payload, store.extracted_data, store.computed_data):
                if isinstance(source, dict):
                    self._flatten_source(source, '', found)
        if found:
            return sorted(found.values(), key=lambda f: f['path'])
        if scoped:
            # This feed is empty. Say so with an empty list; the employee-schema
            # fallback below would be a lie about this API's shape.
            return [] if Store.search_count([('connector_id', '=', connector.id)]) else \
                self._odoo_source_fields()
        return self._odoo_source_fields()      # secondary source

    @api.model
    def _flatten_source(self, obj, prefix, out, depth=0):
        """Recursively flatten a payload dict into dot-paths. Nested dicts →
        a.b.c; a list of dicts contributes its first element's sub-paths; scalar
        lists become a single 'list' leaf. First value seen per path wins."""
        if depth > 6:
            return
        for key, val in obj.items():
            path = '%s.%s' % (prefix, key) if prefix else str(key)
            if isinstance(val, dict):
                self._flatten_source(val, path, out, depth + 1)
            elif isinstance(val, list):
                if val and isinstance(val[0], dict):
                    self._flatten_source(val[0], path, out, depth + 1)
                elif path not in out:
                    out[path] = {'path': path, 'sample': (val[0] if val else None),
                                 'type': 'list', 'label': str(key)}
            elif path not in out:
                out[path] = {'path': path, 'sample': val,
                             'type': self._infer_source_type(val), 'label': str(key)}

    @staticmethod
    def _infer_source_type(val):
        if isinstance(val, bool):
            return 'boolean'
        if isinstance(val, int):
            return 'integer'
        if isinstance(val, float):
            return 'float'
        if isinstance(val, str):
            import re as _re
            if _re.match(r'^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2})?$', val):
                return 'datetime' if len(val) > 10 else 'date'
            return 'string'
        return 'string'

    @api.model
    def _odoo_source_fields(self):
        """Fallback: offer hr.employee's own fields as source paths."""
        Emp = self.env['hr.employee']
        out = []
        for name, field in Emp._fields.items():
            if field.type in ('binary', 'one2many', 'many2many'):
                continue
            out.append({'path': name, 'sample': None,
                        'type': field.type, 'label': field.string or name})
        return sorted(out, key=lambda f: f['path'])[:200]

    # ==========================================
    # BATCH TEST (T4.5)
    # ==========================================
    def _get_test_payload(self, employee):
        """Most recent stored payload for this connector (optionally for one
        employee), raw_payload as the nested base with extracted/computed keys
        merged on top."""
        Store = self.env['hr.api.data.store']
        domain = [('connector_id', '=', self.connector_id.id)]
        if employee:
            domain = domain + [('employee_id', '=', employee.id)]
        store = Store.search(domain, order='pull_date desc, id desc', limit=1)
        if not store and employee:                       # fall back to any payload
            store = Store.search([('connector_id', '=', self.connector_id.id)],
                                 order='pull_date desc, id desc', limit=1)
        if not store:
            return None
        merged = dict(store.raw_payload or {})
        for src in (store.extracted_data, store.computed_data):
            if isinstance(src, dict):
                for k, v in src.items():
                    merged.setdefault(k, v)
        return merged

    def _navigate_path(self, payload, path):
        """Walk a dot-path, returning (value, error). A missing key / bad descent
        is an EXPLICIT error string — never a silent None (that's the whole point:
        a broken mapping must not masquerade as a real 0)."""
        if not path:
            return None, _("No source field path set")
        value = payload
        walked = []
        for key in path.split('.'):
            walked.append(key)
            here = '.'.join(walked)
            if isinstance(value, dict):
                if key not in value:
                    return None, _("Path not found: '%s' (no key '%s')") % (here, key)
                value = value[key]
            elif isinstance(value, (list, tuple)):
                if key.isdigit():
                    idx = int(key)
                    if idx >= len(value):
                        return None, _("Index out of range: '%s'") % here
                    value = value[idx]
                elif value and isinstance(value[0], dict) and key in value[0]:
                    value = value[0][key]
                else:
                    return None, _("Path not found in list: '%s'") % here
            else:
                parent = '.'.join(walked[:-1]) or 'root'
                return None, _("Cannot read '%s' — '%s' is a %s, not an object") % (
                    key, parent, type(value).__name__)
        return value, None

    @staticmethod
    def _jsonable(v):
        if v is None or isinstance(v, (str, int, float, bool)):
            return v
        return str(v)

    @api.model
    def test_mappings_batch(self, mapping_ids, employee_id):
        """Run each mapping's extraction + transformation against one employee's
        stored payload. Returns [{mapping_id, source_field, target, raw,
        transformed, error}] — errors are explicit strings, never silent."""
        mappings = self.browse(mapping_ids).exists()
        employee = self.env['hr.employee'].browse(int(employee_id)) if employee_id else self.env['hr.employee']
        results = []
        for m in mappings:
            raw, transformed, error = None, None, False
            try:
                payload = m._get_test_payload(employee)
                if payload is None:
                    error = _("No stored data on connector '%s'") % (m.connector_id.name or '')
                else:
                    raw, err = m._navigate_path(payload, m.source_field)
                    if err:
                        error = err                       # explicit path failure
                    else:
                        transformed = m.transform_value(raw, payload)
            except Exception as e:
                error = str(e) or type(e).__name__
            results.append({
                'mapping_id': m.id,
                'source_field': m.source_field or '',
                'target': m.target_column_letter or (m.target_rule_id.code if m.target_rule_id else ''),
                'raw': self._jsonable(raw),
                'transformed': self._jsonable(transformed),
                'error': error,
            })
        return results

    def action_test_against_employee(self):
        """Open the Test dialog pre-filled with this mapping's connector."""
        connector = self[:1].connector_id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Test Mappings',
            'res_model': 'hr.integration.mapping.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context, default_connector_id=connector.id),
        }

    # ==========================================
    # OPEN FORM (for inline list views)
    # ==========================================
    def action_open_form(self):
        """Open this record in a popup form dialog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': self.env.context,
        }

    # ==========================================
    # ACTIONS
    # ==========================================
    def action_test_mapping(self):
        """Test the mapping with sample data"""
        self.ensure_one()
        if not self.source_sample_value:
            raise UserError(_("Please provide a sample value to test"))

        try:
            result = self.transform_value(self.source_sample_value)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mapping Test'),
                    'message': _("Input: %s -> Output: %s") % (
                        self.source_sample_value, result
                    ),
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Mapping Error'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def action_auto_map(self):
        """Try to auto-map based on field name similarity"""
        self.ensure_one()
        if self.target_rule_id:
            return  # Already mapped

        # Get all input rules from associated formula configs
        configs = self.env['hr.formula.config'].search([
            ('connector_id', '=', self.connector_id.id)
        ])

        if not configs:
            return

        input_rules = configs.mapped('rule_ids').filtered(
            lambda r: r.column_type == 'input'
        )

        # Try exact match
        source_lower = self.source_field.lower().replace('_', '').replace('-', '')
        for rule in input_rules:
            rule_lower = rule.code.lower().replace('_', '').replace('-', '')
            if source_lower == rule_lower or source_lower in rule_lower or rule_lower in source_lower:
                self.target_rule_id = rule
                break
