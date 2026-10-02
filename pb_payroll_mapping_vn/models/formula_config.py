# -*- coding: utf-8 -*-
"""Apply the Vietnam record profile to one pay scheme.

WHAT THIS DOES, IN ONE SENTENCE: it teaches a Vietnam configuration where to
read every value a person should not have to type, by writing the mapping rows
the payroll engine already knows how to read.

WHAT IT DELIBERATELY DOES NOT DO:

* it never edits a column the profile does not name. A scheme carries a hundred
  and eleven columns and this profile is responsible for about thirty of them;
  the rest are the starter's, or the customer's, and are none of its business.
* it never changes a FORMULA. Not one line of arithmetic moves. Every component
  that was calculated stays calculated, from the same inputs, in the same order.
* it never removes a source somebody declared by hand. A component that already
  carries a mapping row keeps the destination it has.

IT IS IDEMPOTENT, and that is load-bearing rather than tidy: the natural way to
use it is to run it, look at the mapping board, change something, and run it
again. Running it twice must leave the same thirty rows, not sixty.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from .vn_profile import (
    COMPUTED_FIELDS, CONTRACT_COMPONENTS, EXTRA_COLUMNS, FIELD_MAPPING,
    SHEET_KEY_COLUMN, SHEET_MONEY_COLUMNS, SHEET_TIME_COLUMNS, VALUE_KINDS,
)

_logger = logging.getLogger(__name__)


def _column_letter(index):
    """Excel's own column naming, 0 -> A, 26 -> AA. Used for new columns only."""
    letters = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


class HrFormulaConfig(models.Model):
    _inherit = 'hr.formula.config'

    # ------------------------------------------------------------------
    #  The public entry point
    # ------------------------------------------------------------------
    def pb_apply_vn_mapping(self):
        """Wire this scheme's steady columns onto employee and contract records.

        Returns a dict per configuration describing what changed, so a caller
        — a script, a button, a test — can report it rather than guess.
        """
        results = {}
        for config in self:
            results[config.id] = config._pb_apply_vn_mapping_one()
        return results

    def action_pb_apply_vn_mapping(self):
        """Button wrapper: apply, then say what happened in a dialog."""
        self.ensure_one()
        report = self._pb_apply_vn_mapping_one()
        message = _(
            "%(mapped)s columns now read from an employee or contract record, "
            "%(components)s are kept as contract components, and "
            "%(added)s columns were added for the employee code and bank "
            "details.",
            mapped=report['mapped'],
            components=report['contract_components'],
            added=report['columns_added'],
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _("Mapping applied"), 'message': message,
                       'type': 'success', 'sticky': False},
        }

    # ------------------------------------------------------------------
    #  The work
    # ------------------------------------------------------------------
    def _pb_apply_vn_mapping_one(self):
        self.ensure_one()
        rules = {r.code: r for r in self.rule_ids if r.code}
        report = {'config': self.display_name, 'mapped': 0, 'already': 0,
                  'contract_components': 0, 'columns_added': 0,
                  'value_kinds': 0, 'sheet_sources': 0,
                  'sheet_sources_cleared': 0, 'flags_repaired': 0,
                  'missing': []}

        owned = self._pb_vn_ensure_extra_columns(rules, report)
        rules.update(owned)

        self._pb_vn_apply_field_mappings(rules, report)
        self._pb_vn_apply_extra_mappings(rules, owned, report)
        self._pb_vn_apply_contract_components(rules, report)
        self._pb_vn_apply_value_kinds(rules, report)
        self._pb_vn_declare_sheet_sources(rules, report)
        return report

    # -- rank 4, the field destinations ---------------------------------
    def _pb_vn_apply_field_mappings(self, rules, report):
        Mapping = self.env['hr.payslip.import.mapping']
        Model = self.env['ir.model']
        Field = self.env['ir.model.fields']
        for code, (model_name, field_name) in FIELD_MAPPING.items():
            rule = rules.get(code)
            if not rule:
                report['missing'].append(code)
                continue
            model = Model.sudo().search([('model', '=', model_name)], limit=1)
            field = Field.sudo().search(
                [('model', '=', model_name), ('name', '=', field_name)], limit=1)
            if not model or not field:
                # A profile naming a field the database does not have is a
                # BUG IN THE PROFILE, and a silent skip would hide it until
                # somebody wondered why one column still asked for a value.
                raise UserError(_(
                    "This database has no field '%(field)s' on %(model)s, so "
                    "the column '%(code)s' cannot be mapped. Install the "
                    "Vietnam record mapping module first.",
                    field=field_name, model=model_name, code=code))
            existing = Mapping.sudo().search([
                ('salary_structure_id', '=', self.id),
                ('component_id', '=', rule.id),
            ], limit=1)
            if existing:
                report['already'] += 1
                continue
            Mapping.sudo().create({
                'salary_structure_id': self.id,
                'component_id': rule.id,
                'destination_type': 'field',
                'target_model_id': model.id,
                'target_field_id': field.id,
            })
            report['mapped'] += 1

    # -- rank 4, the columns this profile added --------------------------
    def _pb_vn_apply_extra_mappings(self, rules, owned, report):
        """Wire the employee-code and bank columns to where they land.

        A bank destination is four columns assembling ONE account — there is no
        scalar field to point at, so the row names a `bank_role` instead.

        ONLY EVER APPLIED TO COLUMNS THIS PROFILE ADDED. A scheme that already
        carries bank columns of its own has them wired the way its owner wired
        them, and guessing which of their columns is the account number is
        exactly the kind of help nobody asked for.
        """
        Mapping = self.env['hr.payslip.import.mapping']
        Model = self.env['ir.model']
        Field = self.env['ir.model.fields']
        for code, _label, _role, _kind, dest in EXTRA_COLUMNS:
            if code not in owned:
                continue
            rule = rules.get(code)
            if not rule:
                continue
            if Mapping.sudo().search_count([
                    ('salary_structure_id', '=', self.id),
                    ('component_id', '=', rule.id)]):
                continue
            values = {'salary_structure_id': self.id,
                      'component_id': rule.id}
            if dest[0] == 'bank':
                values.update(destination_type='bank_account',
                              bank_role=dest[1])
            else:
                model = Model.sudo().search([('model', '=', dest[1])], limit=1)
                field = Field.sudo().search(
                    [('model', '=', dest[1]), ('name', '=', dest[2])], limit=1)
                if not (model and field):
                    continue
                values.update(destination_type='field',
                              target_model_id=model.id,
                              target_field_id=field.id)
            Mapping.sudo().create(values)
            report['mapped'] += 1

    # -- rank 5, the contract components --------------------------------
    def _pb_vn_apply_contract_components(self, rules, report):
        """The steady amounts, kept on the contract rather than mapped.

        No mapping row: the engine finds these by the component's own CODE
        (`payroll_import_batch._contract_component_amounts`). All this has to do
        is say that the column IS one, and make sure there is a template for the
        per-contract line to hang on.
        """
        # ONE definition of the templates, shared with the install hook.
        from ..hooks import ensure_advantage_templates
        ensure_advantage_templates(self.env)
        for code, _label, _upper in CONTRACT_COMPONENTS:
            rule = rules.get(code)
            if not rule:
                report['missing'].append(code)
                continue
            if not rule.is_contract_component:
                rule.sudo().is_contract_component = True
            report['contract_components'] += 1

    # -- the columns a starter has no reason to carry --------------------
    def _pb_vn_ensure_extra_columns(self, rules, report):
        """Add the employee-code and bank columns, if the scheme has none.

        A calculation starter ships the arithmetic; who somebody IS and where
        their money GOES are properties of the database it lands in.

        RETURNS EVERY COLUMN THIS PROFILE OWNS, created now or created by an
        earlier run — identified by its CODE, which is ours. That is what makes
        the whole applier idempotent: returning only what this call made would
        mean a second run found the columns already there, added no mapping for
        them, and reported success while leaving them unwired. It is also why
        this cannot hijack somebody else's bank column: a column a customer
        added is not called `BANKACC`.
        """
        Rule = self.env['hr.formula.rule'].sudo()
        existing_letters = {r.column_letter for r in self.rule_ids
                            if r.column_letter}
        next_index = len(self.rule_ids)
        next_sequence = max([r.sequence for r in self.rule_ids] or [0]) + 10
        owned = {}
        for code, label, role, kind, _dest in EXTRA_COLUMNS:
            if code in rules:
                owned[code] = rules[code]
                continue
            while _column_letter(next_index) in existing_letters:
                next_index += 1
            letter = _column_letter(next_index)
            existing_letters.add(letter)
            rule = Rule.create({
                'config_id': self.id,
                'code': code,
                'name': label,
                'column_letter': letter,
                'sequence': next_sequence,
                'column_type': 'input',
                'data_source': 'excel',
                'column_role': role,
                'column_role_source': 'user',
                'value_kind': kind,
                'value_kind_source': 'user',
                # NOT A CONTRACT COMPONENT — see `_pb_vn_normalise_extra_flags`.
                'is_text_component': False,
                'is_contract_component': False,
                'appears_on_payslip': False,
                'default_value': 0.0,
            })
            owned[code] = rule
            next_sequence += 10
            next_index += 1
            report['columns_added'] += 1
        self._pb_vn_normalise_extra_flags(owned, report)
        return owned

    def _pb_vn_normalise_extra_flags(self, owned, report):
        """An employee code is not a contract component. Nor is a bank account.

        THE DEFECT THIS REPAIRS, because it was visible and wrong. The first
        version of this profile set `is_text_component` on the five columns it
        adds, reasoning that they hold text rather than money. They do — but that
        flag does not mean "holds text". It means **"is a contract component, and
        the component holds text"**, and the Mapping board reads it exactly that
        way: every one of the five drew a second wire to "Contract component —
        text" and announced "On import: kept on the contract as text under
        BANKACC" beside the bank destination it actually has. One column, two
        destinations, one of them fiction.

        What makes a value text here is `value_kind` (`text` / `identifier`),
        which is what the resolver reads and what stops the value being coerced
        to a number. These five are left with that and nothing else.

        REPAIRS AS WELL AS PREVENTS: a scheme wired by the earlier version is
        carrying the wrong flag now, and an applier that only got it right on
        fresh schemes would leave the live one misdrawn for ever.
        """
        for code, _label, _role, _kind, _dest in EXTRA_COLUMNS:
            rule = owned.get(code)
            if not rule:
                continue
            wrong = {}
            if rule.is_text_component:
                wrong['is_text_component'] = False
            if rule.is_contract_component:
                wrong['is_contract_component'] = False
            if wrong:
                rule.sudo().write(wrong)
                report['flags_repaired'] = report.get('flags_repaired', 0) + 1

    # -- what the monthly file actually carries ---------------------------
    def _pb_vn_declare_sheet_sources(self, rules, report):
        """Say, on the record, which columns the monthly file delivers.

        WHY THIS IS NOT REDUNDANT. The importer already finds these columns by
        matching their heading against the component's name, and the pay run
        works without a single declared source. But "it works" and "a person can
        see that it works" are different things, and the Spreadsheet columns →
        Scheme board reads DECLARED sources — so a scheme that resolves perfectly
        by name shows an empty board and reads as unmapped. That is the screen
        the owner was looking at.

        It also converts a heuristic into a statement. Matching by name is a
        guess that happens to be right; a declared source is the scheme saying
        which heading it reads, which is what a later rename gets checked
        against.

        ONLY THE COLUMNS THE FILE CARRIES. Declaring a source for a column the
        file does not have would be a claim about a heading nobody sends, and the
        board would then show a wire to nothing.
        """
        carried = dict([SHEET_KEY_COLUMN] + SHEET_TIME_COLUMNS
                       + SHEET_MONEY_COLUMNS)
        for code, header in carried.items():
            rule = rules.get(code)
            if not rule:
                continue
            current = rule.source_ids.filtered(lambda s: s.kind == 'excel')
            if current and (current[0].key or '').strip() == header:
                continue
            rule.sudo().set_source_binding('excel', header, origin='board')
            report['sheet_sources'] = report.get('sheet_sources', 0) + 1

        # AND TAKE BACK THE ONES THAT ARE NO LONGER TRUE.
        #
        # The file shrank: sixteen money columns moved onto the contract. A wire
        # this profile drew last time and no longer believes is worse than no
        # wire — the board would keep promising a heading the file stopped
        # sending, and the first person to trust it would wonder why the
        # allowance came out as zero.
        #
        # ONLY OUR OWN WIRES. `origin == 'board'` is the mark this applier
        # leaves; a source somebody chose by hand says `user` and is never
        # touched, because they know something this profile does not.
        for rule in self.rule_ids:
            if (rule.code or '') in carried:
                continue
            ours = rule.source_ids.filtered(
                lambda s: s.kind == 'excel' and s.origin == 'board')
            if ours:
                ours.sudo().unlink()
                report['sheet_sources_cleared'] = (
                    report.get('sheet_sources_cleared', 0) + 1)

    # -- what a value IS -------------------------------------------------
    def _pb_vn_apply_value_kinds(self, rules, report):
        """Correct the kinds on the columns this profile is responsible for.

        The starter ships every column as `money` because that is the safe
        default when nothing is known. Now something is known: a count is a
        whole number and a shift is a quantity of hours. `integer` additionally
        rounds after coercion, which is what stops a count that went through a
        division coming back as `2.0000001`.
        """
        for kind, codes in VALUE_KINDS.items():
            for code in codes:
                rule = rules.get(code)
                if not rule or rule.value_kind == kind:
                    continue
                rule.sudo().write({'value_kind': kind,
                                   'value_kind_source': 'user'})
                report['value_kinds'] += 1

    # ------------------------------------------------------------------
    #  A reader for the profile, so a script does not re-derive it
    # ------------------------------------------------------------------
    @api.model
    def pb_vn_profile_summary(self):
        """What the profile claims, as plain data. Used by tests and scripts."""
        return {
            'field_mapping': dict(FIELD_MAPPING),
            'computed_fields': list(COMPUTED_FIELDS),
            'contract_components': [c[0] for c in CONTRACT_COMPONENTS],
            'extra_columns': [c[0] for c in EXTRA_COLUMNS],
        }
