# -*- coding: utf-8 -*-
"""JOURNEY J9 — a component's sources, plural.

WHY THIS MODEL EXISTS AT ALL

SOURCING S3 gave a component ONE declared source, as a pair of Chars on
`hr.formula.rule` (`source_binding` + `source_binding_key`). That was the right
shape for the question S3 was asking — "where does this component read from?" —
and the wrong shape for the one the owner asked next: a component may read from a
connected system AND from a spreadsheet AND be kept on the contract, and the
order between them has to be *stated* rather than inferred.

**What was missing was never the order. It was the arity.** The resolver already
walks feed → spreadsheet → contract component, in that order, and J-D5 forbids
moving a rung. A component simply could not declare more than one rung, so the
second source had to be discovered by heuristic (`side_o`, searched by the bound
key and then by the component's natural candidates) and no screen could name it.

So this is the binding in its plural form: one row per KIND, ranked by
`hr.formula.rule._SOURCE_RANK`, walked by the resolver in the order that already
existed.

TWO CHARS, NEVER A FOREIGN KEY — the reasoning at `formula_rule.py:162-178`
applies to `key` unchanged. A spreadsheet header has no record to point at, and a
foreign key to `hr.api.transformation.rule` would rebuild the exact
`ondelete='set null'` failure SOURCING S2 spent a phase repairing: twenty-three
mappings severed in silence. Storing the text means "the thing I name is gone"
stays a computed OBSERVATION (`dangling`) instead of becoming data loss.

THE CONTRACT COMPONENT IS DELIBERATELY NOT A ROW HERE. It has no key, it is a
boolean that also drives a writeback, and giving it a second representation would
create two ways to say one thing — and therefore two things to keep in step. It
joins the ranked list only in `hr.formula.rule.declared_sources()`, always last.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrFormulaRuleSource(models.Model):
    _name = 'hr.formula.rule.source'
    _description = 'Payroll Component Source'
    _order = 'rule_id, id'

    rule_id = fields.Many2one(
        'hr.formula.rule', string='Component', required=True, index=True,
        ondelete='cascade')

    #: The same three values as `source_binding`, and there must never be a
    #: fourth: these are the kinds a RUN can be asked to read, and a run carries
    #: at most two payloads (`blob_for_kind`, `payroll_import_batch.py:2970`).
    kind = fields.Selection([
        ('excel', 'Spreadsheet column'),
        ('feed', 'Connected system key'),
        ('rule', 'Rule output'),
    ], string='Source', required=True)

    key = fields.Char(
        string='Source key', required=True,
        help="The column header, feed key or rule output name this component "
             "reads.")

    origin = fields.Selection([
        ('user', 'Chosen by hand'),
        ('board', 'Drawn on a mapping board'),
        ('import', 'Set during import'),
        ('migration', 'Inferred on upgrade'),
    ], string='How the source was set', default='user')

    set_date = fields.Datetime(string='Source set on', readonly=True)
    set_uid = fields.Many2one(
        'res.users', string='Source set by', readonly=True, ondelete='set null')

    dangling = fields.Boolean(
        compute='_compute_dangling', string='Source no longer exists',
        help="This source names a key that nothing currently provides.")

    # ------------------------------------------------------------------
    # T6 — "does anything answer to this name?" is a question about the WORLD,
    # so it is per-source and unstored, exactly as `binding_dangling` was.
    # ------------------------------------------------------------------
    @api.depends('kind', 'key', 'rule_id.config_id.connector_id')
    def _compute_dangling(self):
        Rule = self.env.get('hr.api.transformation.rule')
        catalogues = {}
        for src in self:
            kind, key = src.kind, (src.key or '').strip()
            # `excel` is advisory only: a spreadsheet column exists when a
            # spreadsheet is uploaded, and calling it dangling because no file
            # happens to be loaded would be a false alarm on every fresh scheme.
            if not kind or not key or kind == 'excel':
                src.dangling = False
                continue
            connector = src.rule_id.config_id.connector_id
            if not connector:
                src.dangling = False
                continue
            if kind == 'rule':
                src.dangling = not (Rule is not None and Rule.sudo().search_count([
                    ('connector_id', '=', connector.id), ('output_key', '=', key)]))
                continue
            if connector.id not in catalogues:
                try:
                    catalogues[connector.id] = {f.get('path') for f in (
                        self.env['hr.integration.field.mapping'].sudo()
                        .get_available_source_fields(connector.id) or [])}
                except Exception:   # noqa: BLE001 — a chip must never break a form
                    catalogues[connector.id] = set()
            paths = catalogues[connector.id]
            # An EMPTY catalogue means the connector has never synced. That is
            # "unknown", not "dangling", and must not raise a false alarm.
            src.dangling = bool(paths) and key not in paths

    # ------------------------------------------------------------------
    # AT MOST ONE ROW PER (rule, kind).
    #
    # Python, not SQL: Odoo 19 silently IGNORES the legacy `_sql_constraints`
    # attribute (see the warning repeated across this module, e.g.
    # `formula_rule.py:1620`), and a `models.Constraint` unique index would make
    # the migration's idempotency a database error rather than a no-op. The
    # invariant is enforced where it can also explain itself.
    # ------------------------------------------------------------------
    @api.constrains('rule_id', 'kind')
    def _check_one_row_per_kind(self):
        for src in self:
            if not src.rule_id or not src.kind:
                continue
            twin = self.search_count([
                ('rule_id', '=', src.rule_id.id), ('kind', '=', src.kind),
                ('id', '!=', src.id)])
            if twin:
                raise ValidationError(_(
                    "“%(code)s” already reads %(src)s. A component reads each "
                    "kind of source once; change that source instead of adding "
                    "a second one.",
                    code=src.rule_id.code or src.rule_id.name or '',
                    src=dict(self._fields['kind'].selection).get(
                        src.kind, src.kind)))

    @api.constrains('key')
    def _check_key(self):
        for src in self:
            if not (src.key or '').strip():
                raise ValidationError(_(
                    "Choose which key “%s” reads, or remove the source.")
                    % (src.rule_id.code or src.rule_id.name or ''))

    # ------------------------------------------------------------------
    # T4 — a sealed column has nothing to read. The refusal lives here as well as
    # on the rule, because a source row is now the thing that CREATES a binding
    # and a guard only on the derived field would be a lock on the doorknob.
    # ------------------------------------------------------------------
    @api.constrains('rule_id', 'kind')
    def _check_column_is_importable(self):
        for src in self:
            rule = src.rule_id
            if rule and rule.column_type and rule.column_type != 'input':
                raise ValidationError(_(
                    "“%s” is calculated — it needs no source.")
                    % (rule.code or rule.name or ''))
