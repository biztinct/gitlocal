# -*- coding: utf-8 -*-
"""The Pay rules step, server side.

Everything the Components tab and the sentence editor can do passes through
here, and every gate is enforced HERE — never in the browser (ledger rule 9).
The client is allowed to grey a button out; it is never allowed to be the
reason something is safe.

Four promises this file keeps:

* **A preview never persists.** Working out what a half-written sentence would
  pay somebody means writing the candidate formula, asking the real engine, and
  then making sure that write never happened. It runs inside a savepoint that
  is always rolled back.
* **A formula somebody typed is never overwritten.** Regeneration touches only
  the rules whose formula is still the one the sentence produced.
* **Removing a component names who needs it.** If anything that is written in
  Excel refers to it, the removal is refused with the name of that component,
  because rewriting somebody's formula for them is not ours to do.
* **Every change bumps the draft's revision**, so two browser tabs cannot
  silently overwrite each other.
"""
import json
import logging
import re

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError, ValidationError

from . import recipe_compiler as rc
from .essentials_recipes import ESSENTIALS_RECIPES, ESSENTIALS_TEMPLATE_KEY
from .recipe_schema import (
    AUDIENCES, FREQUENCY, GROUPS, HELPER_INPUTS, HELPER_SUFFIXES, INSURANCE,
    KINDS, LOCKED_GROUPS, PRORATION, RecipeError, TAX, default_recipe,
    helper_code, helper_label, helper_suffix_label, review_items,
    validate_recipe,
)

_logger = logging.getLogger(__name__)

#: The tabs on the Pay rules step, and the group each one shows.
GROUP_TABS = ('earning', 'deduction', 'benefit', 'helper', 'total')


class _Rollback(Exception):
    """Unwinds a preview's savepoint. Never reaches a person."""


class PbBlueprintComponents(models.AbstractModel):
    _inherit = 'pb.blueprint.studio'

    # ==================================================================
    # Reading the list
    # ==================================================================
    @api.model
    def bp_components(self, config_id, sample_id=None):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        self._backfill_essentials(config, blueprint)
        values = self._sample_values(config, sample_id)
        ctx = rc.build_ctx(config)
        included = set(ctx.order)

        groups = {key: [] for key in GROUP_TABS}
        for rule in config.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
            code = (rule.code or '').upper()
            if not code:
                continue
            recipe = rule.bp_recipe()
            group = rc.derived_group(rule, recipe)
            row = self._component_row(rule, recipe, group, values, included)
            groups.setdefault(group, []).append(row)

        removed = self._removed_rows(config, blueprint, included)
        return {
            'ok': True,
            'groups': groups,
            'removed': removed,
            'counts': {
                'included': sum(len(rows) for rows in groups.values()),
                'removed': len(removed),
            },
            'sample_values': values,
            'sample_id': self._chosen_sample_id(config, sample_id),
            'revision': blueprint.revision if blueprint else 0,
            'currency': config.currency_id.name or '',
        }

    def _component_row(self, rule, recipe, group, values, included):
        code = (rule.code or '').upper()
        review = review_items(recipe, included)
        health, health_text = self._health(rule, recipe, review)
        return {
            'id': rule.id,
            'code': code,
            'name': rule.name or code,
            'column_type': rule.column_type,
            'letter': rule.column_letter or '',
            'group': group,
            'source': rule.bp_formula_source or 'manual',
            'summary': self._summary(rule, recipe),
            'health': health,
            'health_text': health_text,
            'review': review,
            'value': values.get(code),
            'locked': group in LOCKED_GROUPS,
            'template_key': rule.bp_template_key or '',
            'on_payslip': bool(rule.appears_on_payslip),
        }

    def _health(self, rule, recipe, review):
        """Green, amber or rose — and always a reason next to it."""
        if rule.column_type == 'formula' and rule.excel_formula:
            if not rule.is_valid:
                return 'problem', (rule.validation_message
                                   or _("The engine cannot read this calculation."))
            if not rule.python_formula:
                return 'problem', _("The engine cannot read this calculation.")
            if rule.has_circular_ref:
                return 'problem', _("This depends on itself, so no number can "
                                    "be worked out.")
            if rule.has_evaluation_error:
                return 'problem', (rule.last_evaluation_error
                                   or _("This did not work out on the last run."))
        if review:
            return 'review', review[0]['text']
        return 'ok', _("Ready")

    def _summary(self, rule, recipe):
        """One line under the name — the sentence, or the Excel behind it."""
        if not recipe or (recipe.get('amount') or {}).get('kind') == 'manual' \
                or rule.bp_formula_source == 'manual':
            if rule.column_type == 'constant':
                return _("A fixed value: %s") % self._group(rule.constant_value or 0)
            if rule.column_type == 'input':
                return _("A number this payroll is given")
            display = self._display_formula(rule.config_id, rule.excel_formula or '')
            if not display:
                return _("Nothing is worked out yet")
            if len(display) > 64:
                display = display[:63] + '…'
            return _("Written as Excel · %s") % display
        return ' · '.join(self._summary_bits(recipe))

    def _summary_bits(self, recipe):
        amount = recipe.get('amount') or {}
        kind = amount.get('kind')
        bits = [{
            'input': _("An approved amount"),
            'fixed': _("A fixed amount"),
            'contract': _("Contract salary"),
            'percent_contract': _("A share of contract salary"),
            'percent_of': _("A share of another component"),
            'role': _("An amount per grade"),
            'hourly': _("Hours at an hourly rate"),
            'annual_ratio': _("A yearly payment, by service"),
            'linked': _("The same as another component"),
            'sum_group': _("Everything in a group, added up"),
            'bracket': _("Worked out from the tax bands"),
            'pit_vn': _("Income tax, by the route that applies"),
            'insurance_base': _("Insurable pay, capped"),
            'taxable_base': _("Income the tax bands apply to"),
            'net_total': _("Take-home pay"),
            'employer_total': _("What the employer pays in total"),
        }.get(kind, _("An approved amount"))]
        if recipe.get('proration') == 'working_days':
            bits.append(_("Prorated by working days"))
        elif recipe.get('proration') == 'calendar_days':
            bits.append(_("Prorated by calendar days"))
        treat = recipe.get('treatment') or {}
        if recipe.get('group') in ('earning', 'benefit'):
            bits.append({
                'taxable': _("Taxable"),
                'exempt': _("Tax free"),
                'qualified': _("Tax free with evidence"),
                'annual_cap': _("Tax free up to a yearly limit"),
                'entitlement': _("Tax free within the entitlement"),
                'inherit': _("Follows the original component"),
            }.get(treat.get('tax'), _("Taxable")))
        if recipe.get('frequency') == 'annual':
            bits.append(_("Paid once a year"))
        elif recipe.get('frequency') == 'adhoc':
            bits.append(_("Paid when approved"))
        elif recipe.get('frequency') == 'scheme':
            bits.append(_("Paid by scheme"))
        return bits

    # ------------------------------------------------------------------
    def _display_formula(self, config, formula):
        """A formula with component codes in it, for a person to read.

        The stored form is column letters, which are meaningless to anybody who
        did not build the configuration. `excel_formula_display` only strips the
        row numbers, so the substitution is done here.
        """
        if not formula:
            return ''
        text = self.env['hr.formula.rule']._normalize_excel_formula(formula)
        pairs = sorted(
            ((r.column_letter, r.code) for r in config.rule_ids
             if r.column_letter and r.code),
            key=lambda p: -len(p[0]))
        for letter, code in pairs:
            text = re.sub(r'(?<![A-Za-z0-9])%s(?![A-Za-z0-9])' % re.escape(letter),
                          code, text)
        return text

    def _codes_to_letters(self, config, formula):
        """The other direction: what a person typed, as the engine stores it."""
        if not formula:
            return ''
        text = str(formula).strip()
        pairs = sorted(
            ((r.code, r.column_letter) for r in config.rule_ids
             if r.column_letter and r.code),
            key=lambda p: -len(p[0]))
        tables = {(t.code or '').upper() for t in config.rate_table_ids}
        for code, letter in pairs:
            if code.upper() in tables:
                continue
            text = re.sub(r'(?<![A-Za-z0-9])%s(?![A-Za-z0-9])' % re.escape(code),
                          letter, text, flags=re.IGNORECASE)
        return text

    def _plain_formula_error(self, message):
        """The checker's refusal, in words a payroll manager can act on.

        `FormulaValidator` was written for engineers reading a log: "Missing 1
        closing parenthesis(es)", "Unknown column reference: QQ". Those reach a
        person here, under the calculation they just typed, so the handful that
        are actually reachable get plain wording. Anything unrecognised is
        passed through unchanged rather than swallowed — a refusal nobody can
        read still beats a refusal nobody can see.
        """
        text = (message or '').strip()
        if not text:
            return _("This calculation cannot be read.")
        hit = re.search(r'Missing (\d+) closing parenthesis', text)
        if hit:
            count = int(hit.group(1))
            return (_("A closing bracket is missing.") if count == 1
                    else _("%s closing brackets are missing.") % count)
        if 'Unexpected \')\'' in text:
            return _("There is a closing bracket with nothing to close.")
        hit = re.search(r'Unknown column reference: ([A-Za-z0-9]+)', text)
        if hit:
            return _("There is no component called %s in this configuration.",
                     hit.group(1))
        hit = re.search(r'Unsupported function: ([A-Za-z0-9_]+)', text)
        if hit:
            return _("%s is not a calculation this payroll can run.",
                     hit.group(1))
        if 'Consecutive operators' in text:
            return _("Two operators are next to each other, so the "
                     "calculation cannot be worked out.")
        if 'ends with an operator' in text:
            return _("The calculation stops after an operator.")
        if 'must start with' in text:
            return _("A calculation has to start with an equals sign.")
        return text

    def _check(self, config, formula, exclude_id=None):
        """The engine's own checker, with its answer put into plain words."""
        ok, message = self.env['pb.formula.studio']._check_formula(
            config, formula, exclude_id=exclude_id)
        return ok, ('' if ok else self._plain_formula_error(message))

    # ------------------------------------------------------------------
    def _sample_values(self, config, sample_id=None):
        """What each component pays the sample employee, by code."""
        sample_id = self._chosen_sample_id(config, sample_id)
        if not sample_id:
            return {}
        try:
            result = self.env['pb.formula.studio'].compute_preview(
                config.id, sample_id)
        except AccessError:
            raise
        except Exception as exc:            # pragma: no cover - advisory
            _logger.info("Guided setup: sample values unavailable: %s", exc)
            return {}
        by_letter = result.get('values') or {}
        return {(r.code or '').upper(): by_letter[r.column_letter]
                for r in config.rule_ids
                if r.code and r.column_letter in by_letter}

    def _chosen_sample_id(self, config, sample_id=None):
        samples = config.sample_data_ids
        if not samples:
            return False
        chosen = samples.filtered(lambda s: s.id == int(sample_id or 0))[:1]
        return (chosen or samples[:1]).id

    # ------------------------------------------------------------------
    def _removed_rows(self, config, blueprint, included):
        """Starter components this configuration no longer has."""
        template_key = blueprint.template_key if blueprint else ''
        template = self._template(template_key)
        if not template:
            return []
        rows = []
        recipes = self._template_recipes(template_key, template)
        for comp in template._components():
            code = (comp.get('code') or '').upper()
            if not code or code in included:
                continue
            recipe = recipes.get(code)
            rows.append({
                'code': code,
                'name': comp.get('name') or code,
                'group': (recipe or {}).get('group')
                or ('helper' if comp.get('type') in ('input', 'constant')
                    else 'earning'),
            })
        return rows

    def _template(self, key):
        if not key or key in ('blank', 'excel'):
            return None
        return self.env['hr.formula.config.template'].sudo().search(
            [('code', '=', key), ('state', '!=', 'superseded')], limit=1) or None

    def _template_recipes(self, key, template=None):
        """The sentences a starter ships, or the ones we know it implies."""
        out = {}
        if template:
            for comp in template._components():
                if comp.get('recipe'):
                    out[(comp.get('code') or '').upper()] = comp['recipe']
        if key == ESSENTIALS_TEMPLATE_KEY:
            for code, recipe in ESSENTIALS_RECIPES.items():
                out.setdefault(code, recipe)
        return out

    # ==================================================================
    # The backfill
    # ==================================================================
    def _backfill_essentials(self, config, blueprint):
        """Give a starter-seeded configuration the sentences it always implied.

        Runs once: the moment any rule carries a recipe there is nothing to do.
        Idempotent, silent, and never fatal — a configuration that cannot be
        backfilled still shows its components, they just read as Excel.
        """
        key = blueprint.template_key if blueprint else ''
        recipes = self._template_recipes(key, self._template(key))
        if not recipes:
            return False
        if any(r.bp_recipe_json for r in config.rule_ids):
            return False
        try:
            with self.env.cr.savepoint():
                self._apply_recipes(config, recipes, key)
                report = rc.regenerate(self.env, config, reason='refactor')
                if report['problems']:
                    _logger.warning(
                        "Guided setup: backfill of config %s reported %s",
                        config.id, report['problems'])
        except AccessError:
            raise
        except Exception as exc:
            _logger.warning("Guided setup: backfill skipped for config %s: %s",
                            config.id, exc, exc_info=True)
            return False
        return True

    def _apply_recipes(self, config, recipes, template_key=''):
        """Write the sentences onto the rules, and provision what they need."""
        by_code = {(r.code or '').upper(): r for r in config.rule_ids if r.code}
        clean = {}
        codes = set(by_code)
        tables = {(t.code or '').upper() for t in config.rate_table_ids}
        for code, recipe in recipes.items():
            if code not in by_code:
                continue
            try:
                clean[code] = validate_recipe(recipe, {
                    'codes': codes, 'rate_tables': tables, 'self_code': code})
            except RecipeError as exc:
                _logger.warning("Guided setup: %s has an unusable rule: %s",
                                code, exc)
        self._provision_helpers(config, clean)
        by_code = {(r.code or '').upper(): r for r in config.rule_ids if r.code}
        for code, recipe in clean.items():
            rule = by_code.get(code)
            if not rule:
                continue
            vals = {'bp_recipe_json': json.dumps(recipe, sort_keys=True)}
            if rule.column_type == 'formula' \
                    and (recipe.get('amount') or {}).get('kind') != 'manual':
                vals['bp_formula_source'] = 'generated'
            if template_key:
                vals['bp_template_key'] = template_key
            rule.write(vals)
        # A conditional exemption needs its own small "taxable part" rule beside
        # it, or the income the tax bands see is the whole payment.
        by_code = {(r.code or '').upper(): r for r in config.rule_ids if r.code}
        for code, recipe in clean.items():
            rule = by_code.get(code)
            if not rule:
                continue
            # Deliberately NOT limited to formula components. A payment the
            # payroll is simply GIVEN can still be tax free up to a yearly
            # limit, and without its taxable-part companion the tax bands would
            # see the whole payment.
            self._write_tax_helper(config, rule, recipe)
            self._write_share_helper(config, rule, recipe)
        return clean

    # ==================================================================
    # Helper inputs
    # ==================================================================
    def _needed_helpers(self, config, recipes):
        """Every helper input these sentences name that does not exist yet."""
        ctx = rc.build_ctx(config, extra_recipes=recipes)
        wanted = []
        for code, recipe in recipes.items():
            ctx['self_code'] = code
            try:
                _formula, needs = rc.compile_recipe(recipe, ctx)
            except RecipeError:
                needs = []
            finally:
                ctx['self_code'] = ''
            for need in needs:
                if need not in wanted:
                    wanted.append(need)
            ctx['self_code'] = code
            try:
                _tx, tx_needs = rc.taxable_helper_formula(recipe, ctx)
            except RecipeError:
                tx_needs = []
            finally:
                ctx['self_code'] = ''
            for need in tx_needs:
                if need not in wanted:
                    wanted.append(need)
            ctx['self_code'] = code
            try:
                _ee, ee_needs = rc.employee_share_formula(recipe, ctx)
            except RecipeError:
                ee_needs = []
            finally:
                ctx['self_code'] = ''
            for need in ee_needs:
                if need not in wanted:
                    wanted.append(need)
        return wanted

    def _provision_helpers(self, config, recipes):
        """Create the inputs the sentences need, once, and tell every sample.

        A new input that nobody has a value for is a silent zero in somebody's
        pay, so every existing sample employee is given the input at its
        sensible starting value at the same moment the input is created.
        """
        created = []
        for _round in range(4):
            wanted = self._needed_helpers(config, recipes)
            missing = [c for c in wanted
                       if c not in {(r.code or '').upper() for r in config.rule_ids}]
            if not missing:
                break
            for code in missing:
                rule = self._create_helper(config, code)
                if rule:
                    created.append(rule)
            config.invalidate_recordset(['rule_ids'])
        if created:
            self._seed_samples_with(config, created)
        return created

    def _create_helper(self, config, code):
        code = (code or '').upper()
        if not code:
            return None
        default = rc.helper_defaults(code)
        try:
            rule = self.env['hr.formula.rule'].create({
                'config_id': config.id,
                'code': code,
                'name': self._helper_name(config, code),
                'column_type': 'input',
                'column_role': 'payroll',
                'default_value': default,
                'is_visible_in_grid': True,
                'appears_on_payslip': False,
                'visibility_rule': 'never',
                'sequence': (max(config.rule_ids.mapped('sequence') or [0]) + 10),
                'bp_template_key': 'helper',
            })
        except (UserError, ValidationError) as exc:
            _logger.warning("Guided setup: helper %s could not be created: %s",
                            code, exc)
            return None
        return rule

    def _helper_name(self, config, code):
        """Plain words for a helper input — never the code."""
        if code in HELPER_INPUTS:
            return helper_label(code)
        for suffix in sorted(HELPER_SUFFIXES, key=len, reverse=True):
            if not code.endswith(suffix):
                continue
            stem = code[:-len(suffix)]
            owner = config.rule_ids.filtered(
                lambda r: (r.code or '').upper().startswith(stem)
                and (r.code or '').upper() != code)[:1]
            name = owner.name if owner else stem.title()
            return helper_suffix_label(suffix, name)
        return code.title()

    def _seed_samples_with(self, config, rules):
        """Every sample employee gets the new inputs at their starting value."""
        for sample in config.sample_data_ids:
            try:
                stored = json.loads(sample.input_values_json or '{}')
            except (TypeError, ValueError):
                stored = {}
            added = {r.code: float(r.default_value or 0.0)
                     for r in rules if r.code and r.code not in stored}
            if not added:
                continue
            stored.update(added)
            sample.input_values_json = json.dumps(stored)

    # ==================================================================
    # One component, opened
    # ==================================================================
    @api.model
    def bp_component_get(self, rule_id):
        rule = self.env['hr.formula.rule'].browse(int(rule_id or 0))
        if not rule.exists():
            return {'ok': False, 'reason': _("That component no longer exists.")}
        config, blueprint, err = self._guard(rule.config_id.id,
                                             require_blueprint=False)
        if err:
            return err
        recipe = rule.bp_recipe()
        ctx = rc.build_ctx(config, self_code=rule.code)
        return {
            'ok': True,
            'rule': {
                'id': rule.id,
                'code': (rule.code or '').upper(),
                'name': rule.name or '',
                'column_type': rule.column_type,
                'group': rc.derived_group(rule, recipe),
                'source': rule.bp_formula_source or 'manual',
                'on_payslip': bool(rule.appears_on_payslip),
                'constant_value': rule.constant_value or 0.0,
                'default_value': rule.default_value or 0.0,
            },
            'recipe': recipe or default_recipe(rc.derived_group(rule, recipe)),
            'has_recipe': bool(recipe),
            'generated_formula': self._display_formula(
                config, rule.bp_generated_formula or ''),
            'display_formula': self._display_formula(
                config, rule.excel_formula or ''),
            'options': self._options(config, rule),
            'provenance': self._provenance(rule, blueprint),
            'revision': blueprint.revision if blueprint else 0,
            'sample_id': self._chosen_sample_id(config),
        }

    @api.model
    def bp_component_get_new(self, config_id, group='earning'):
        """The empty sentence a brand-new component starts from."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        if group not in GROUPS:
            group = 'earning'
        return {
            'ok': True,
            'rule': {'id': False, 'code': '', 'name': '',
                     'column_type': 'formula', 'group': group,
                     'source': 'generated', 'on_payslip': True,
                     'constant_value': 0.0, 'default_value': 0.0},
            'recipe': default_recipe(group),
            'has_recipe': False,
            'generated_formula': '',
            'display_formula': '',
            'options': self._options(config),
            'provenance': {'kind': 'own', 'text': _("Added by you")},
            'revision': blueprint.revision if blueprint else 0,
            'sample_id': self._chosen_sample_id(config),
        }

    def _provenance(self, rule, blueprint):
        key = rule.bp_template_key or ''
        if key == 'helper':
            return {'kind': 'helper', 'text': _("Added for you, so a rule "
                                                "you chose has a number to work from")}
        template = self._template(key)
        if template:
            return {'kind': 'starter',
                    'text': _("Starter: %(name)s · v%(version)s",
                              name=template.name, version=template.version or '')}
        return {'kind': 'own', 'text': _("Added by you")}

    def _options(self, config, rule=None):
        """Every choice the sentence offers, with the words the person reads."""
        codes = []
        bases = []
        links = []
        me = (rule.code or '').upper() if rule else ''
        for other in config.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
            code = (other.code or '').upper()
            if not code or code == me:
                continue
            row = {'code': code, 'name': other.name or code}
            codes.append(row)
            if other.value_kind in ('money', 'decimal', 'integer', 'quantity',
                                    'rate') or other.column_type != 'input':
                bases.append(row)
            if rc.derived_group(other, other.bp_recipe()) == 'benefit':
                links.append(row)
        return {
            'audiences': self._audience_options(),
            'kinds': self._kind_options(),
            'groups': self._group_options(),
            'proration': self._proration_options(),
            'frequency': self._frequency_options(),
            'tax': self._tax_options(),
            'insurance': self._insurance_options(),
            'cash': [{'value': 'cash', 'label': _("Paid in cash")},
                     {'value': 'noncash', 'label': _("A benefit, not cash")}],
            'bearer': [{'value': 'employee', 'label': _("The employee")},
                       {'value': 'employer', 'label': _("The employer")}],
            'pit_deductible': [
                {'value': 'no', 'label': _("No")},
                {'value': 'yes', 'label': _("Yes, in full")},
                {'value': 'source', 'label': _("The same as the original component")}],
            'bases': bases,
            'links': links,
            'sources': codes,
            'tables': [{'code': (t.code or '').upper(), 'name': t.name or ''}
                       for t in config.rate_table_ids],
            'months': [{'value': i, 'label': label} for i, label in enumerate(
                [_("January"), _("February"), _("March"), _("April"), _("May"),
                 _("June"), _("July"), _("August"), _("September"),
                 _("October"), _("November"), _("December")], start=1)],
            'codes': [c['code'] for c in codes],
            'currency': config.currency_id.name or '',
        }

    def _audience_options(self):
        labels = {
            'all': _("everyone"),
            'local': _("local employees"),
            'foreign': _("foreign employees"),
            'insured': _("employees in the insurance scheme"),
            'union': _("union members"),
            'enrolled': _("employees enrolled in this"),
            'role': _("employees in eligible roles"),
            'local_insured': _("local employees in the insurance scheme"),
        }
        return [{'value': key, 'label': labels[key]} for key in AUDIENCES]

    def _kind_options(self):
        labels = {
            'input': _("an approved amount"),
            'fixed': _("a fixed amount"),
            'contract': _("the contract salary"),
            'percent_contract': _("a percentage of the contract salary"),
            'percent_of': _("a percentage of another component"),
            'role': _("an amount that depends on the grade"),
            'hourly': _("hours at an hourly rate"),
            'annual_ratio': _("a yearly payment, shared over service"),
            'linked': _("the same amount as another component"),
            'sum_group': _("everything in a group, added up"),
            'bracket': _("the amount the tax bands give"),
            'pit_vn': _("income tax, by the route that applies to the person"),
            'insurance_base': _("insurable pay, capped"),
            'taxable_base': _("the income the tax bands apply to"),
            'net_total': _("take-home pay"),
            'employer_total': _("everything the employer pays"),
            'manual': _("a calculation written as Excel"),
        }
        return [{'value': key, 'label': labels[key]} for key in KINDS]

    def _group_options(self):
        labels = {
            'earning': _("Earnings"),
            'deduction': _("Deductions"),
            'benefit': _("Benefits & employer costs"),
            'total': _("Totals"),
            'helper': _("Inputs & fixed values"),
        }
        return [{'value': key, 'label': labels[key]} for key in GROUPS]

    def _proration_options(self):
        labels = {
            'none': _("nothing"),
            'working_days': _("paid working days"),
            'calendar_days': _("paid calendar days"),
        }
        return [{'value': key, 'label': labels[key]} for key in PRORATION]

    def _frequency_options(self):
        labels = {
            'monthly': _("every pay run"),
            'annual': _("once a year"),
            'adhoc': _("when it is approved"),
            'scheme': _("when the scheme says so"),
        }
        return [{'value': key, 'label': labels[key]} for key in FREQUENCY]

    def _tax_options(self):
        labels = {
            'taxable': _("taxable"),
            'exempt': _("tax free"),
            'qualified': _("tax free with evidence"),
            'annual_cap': _("tax free up to a yearly limit"),
            'entitlement': _("tax free within an approved entitlement"),
            'inherit': _("the same as the original component"),
        }
        return [{'value': key, 'label': labels[key]} for key in TAX]

    def _insurance_options(self):
        labels = {
            'included': _("yes, it counts"),
            'excluded': _("no, it does not count"),
            'inherit': _("the same as the original component"),
            'review': _("still to be decided"),
        }
        return [{'value': key, 'label': labels[key]} for key in INSURANCE]

    # ==================================================================
    # Previewing — the one method that must never leave a trace
    # ==================================================================
    @api.model
    def bp_recipe_preview(self, config_id, rule_id=None, recipe=None,
                          excel_codes=None, sample_id=None, name=None,
                          code=None, group=None):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        out = {'ok': True, 'valid': False, 'message': '', 'value': None,
               'excel_letters': '', 'excel_codes': '', 'needs': []}
        try:
            with self.env.cr.savepoint():
                out.update(self._preview_inside(
                    config, rule_id, recipe, excel_codes, sample_id,
                    name, code, group))
                raise _Rollback()
        except _Rollback:
            pass
        except AccessError:
            raise
        except RecipeError as exc:
            return {'ok': True, 'valid': False, 'message': str(exc),
                    'value': None, 'excel_letters': '', 'excel_codes': '',
                    'needs': []}
        except Exception as exc:
            _logger.info("Guided setup: preview failed: %s", exc, exc_info=True)
            return {'ok': True, 'valid': False, 'value': None,
                    'excel_letters': '', 'excel_codes': '', 'needs': [],
                    'message': self._plain(exc)}
        return out

    def _preview_inside(self, config, rule_id, recipe, excel_codes, sample_id,
                        name=None, code=None, group=None):
        """Everything here is undone by the savepoint around it."""
        Rule = self.env['hr.formula.rule']
        rule = Rule.browse(int(rule_id or 0))
        rule = rule if rule.exists() and rule.config_id == config else None
        temp = None
        if rule is None:
            temp = self._temp_rule(config, name, code, group)
            rule = temp
        self_code = (rule.code or '').upper()

        needs = []
        if excel_codes:
            formula = self._codes_to_letters(config, excel_codes)
        else:
            clean = validate_recipe(recipe or {}, {
                'codes': {(r.code or '').upper() for r in config.rule_ids},
                'rate_tables': {(t.code or '').upper() for t in config.rate_table_ids},
                'self_code': self_code,
            })
            # What WOULD be created, captured before it is: the answer the
            # editor shows ("this adds an input called Hours this run").
            needs = self._needed_helpers(config, {self_code: clean})
            self._provision_helpers(config, {self_code: clean})
            # Named in WORDS: "this adds Paid working days", never "PAIDDAYS".
            needs = [self._helper_name(config, code) for code in needs]
            ctx = rc.build_ctx(config, self_code=self_code,
                               extra_recipes={self_code: clean})
            formula, _still = rc.compile_recipe(clean, ctx)
            if formula is None:
                return {'valid': True, 'message': '', 'excel_letters': '',
                        'excel_codes': '',
                        'value': self._value_of(config, self_code, sample_id),
                        'needs': needs}

        ok, message = self._check(config, formula, exclude_id=rule.id)
        if not ok:
            return {'valid': False, 'message': message,
                    'excel_letters': formula,
                    'excel_codes': self._display_formula(config, formula),
                    'value': None, 'needs': needs}
        rule.write({'excel_formula': formula, 'column_type': 'formula',
                    'bp_formula_source': rule.bp_formula_source or 'manual'})
        value = self._value_of(config, self_code, sample_id)
        return {'valid': True, 'message': '', 'excel_letters': formula,
                'excel_codes': self._display_formula(config, formula),
                'value': value, 'needs': needs}

    def _temp_rule(self, config, name, code, group):
        """A component that only exists inside the preview's savepoint."""
        proposed = (code or '').strip().upper() or None
        result = self.env['pb.formula.studio'].add_component(config.id, {
            'name': name or _("New component"),
            'code': proposed,
            'column_type': 'formula',
        })
        return self.env['hr.formula.rule'].browse(result.get('rule_id') or 0)

    def _value_of(self, config, code, sample_id):
        values = self._sample_values(config, sample_id)
        return values.get((code or '').upper())

    # ==================================================================
    # Saving
    # ==================================================================
    @api.model
    def bp_component_save(self, config_id, rule_id, payload):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        payload = payload or {}
        conflict = self._revision_guard(blueprint, payload.get('revision'))
        if conflict:
            return conflict

        lane = payload.get('lane') or 'guided'
        try:
            with self.env.cr.savepoint():
                rule, created = self._resolve_rule(config, rule_id, payload)
                if isinstance(rule, dict):
                    return rule
                result = self._write_component(config, rule, payload, lane)
                if not result.get('ok'):
                    raise UserError(result.get('reason') or _(
                        "That rule could not be saved."))
                report = rc.regenerate(self.env, config)
                self._classify(config)
        except AccessError:
            raise
        except (UserError, ValidationError) as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        except RecipeError as exc:
            return {'ok': False, 'reason': str(exc)}
        except Exception as exc:
            _logger.warning("Guided setup: component save failed: %s", exc,
                            exc_info=True)
            return {'ok': False, 'reason': self._plain(exc)}

        blueprint.revision += 1
        return {'ok': True, 'rule_id': rule.id, 'created': created,
                'changed': report['changed'], 'problems': report['problems'],
                'revision': blueprint.revision}

    def _revision_guard(self, blueprint, revision):
        if blueprint and revision is not None and int(revision) != blueprint.revision:
            return {'ok': False, 'conflict': True, 'reason': _(
                "Someone else changed this configuration while you were "
                "editing. Reload to see their version.")}
        return None

    def _resolve_rule(self, config, rule_id, payload):
        Rule = self.env['hr.formula.rule']
        if rule_id:
            rule = Rule.browse(int(rule_id))
            if not rule.exists() or rule.config_id != config:
                return {'ok': False, 'reason': _(
                    "That component no longer exists. Reload and try again.")}, False
            return rule, False
        result = self.env['pb.formula.studio'].add_component(config.id, {
            'name': (payload.get('name') or '').strip() or _("New component"),
            'code': (payload.get('code') or '').strip().upper() or None,
            'column_type': 'formula',
        })
        rule = Rule.browse(result.get('rule_id') or 0)
        if not rule.exists():
            return {'ok': False, 'reason': _(
                "The component could not be added.")}, False
        return rule, True

    def _write_component(self, config, rule, payload, lane):
        vals = {}
        name = (payload.get('name') or '').strip()
        if name and name != rule.name:
            vals['name'] = name
        if 'on_payslip' in payload:
            vals['appears_on_payslip'] = bool(payload.get('on_payslip'))

        codes = {(r.code or '').upper() for r in config.rule_ids}
        tables = {(t.code or '').upper() for t in config.rate_table_ids}
        self_code = (rule.code or '').upper()

        if lane == 'excel':
            formula = self._codes_to_letters(config, payload.get('excel_codes') or '')
            if not formula.startswith('='):
                return {'ok': False, 'reason': _(
                    "A calculation has to start with an equals sign.")}
            ok, message = self._check(config, formula, exclude_id=rule.id)
            if not ok:
                return {'ok': False, 'reason': message}
            vals.update({'column_type': 'formula', 'excel_formula': formula,
                         'bp_formula_source': 'manual'})
            if payload.get('recipe'):
                try:
                    clean = validate_recipe(payload['recipe'], {
                        'codes': codes, 'rate_tables': tables,
                        'self_code': self_code})
                    vals['bp_recipe_json'] = json.dumps(clean, sort_keys=True)
                except RecipeError:
                    pass
            rule.write(vals)
            return {'ok': True}

        clean = validate_recipe(payload.get('recipe') or {}, {
            'codes': codes, 'rate_tables': tables, 'self_code': self_code})
        self._provision_helpers(config, {self_code: clean})
        ctx = rc.build_ctx(config, self_code=self_code,
                           extra_recipes={self_code: clean})
        formula, needs = rc.compile_recipe(clean, ctx)
        if needs:
            return {'ok': False, 'reason': _(
                "This rule needs a number that could not be created: %s.",
                ', '.join(needs))}
        vals['bp_recipe_json'] = json.dumps(clean, sort_keys=True)
        if formula is None:
            vals['bp_formula_source'] = 'manual'
            rule.write(vals)
        else:
            ok, message = self._check(config, formula, exclude_id=rule.id)
            if not ok:
                return {'ok': False, 'reason': message}
            vals.update({'column_type': 'formula', 'excel_formula': formula,
                         'bp_generated_formula': formula,
                         'bp_formula_source': 'generated',
                         'bp_generated_revision': (rule.bp_generated_revision or 0) + 1})
            rule.write(vals)
        self._write_tax_helper(config, rule, clean)
        self._write_share_helper(config, rule, clean)
        return {'ok': True}

    def _write_tax_helper(self, config, rule, recipe):
        """Keep the `<CODE>TX` companion in step with the tax choice."""
        self_code = (rule.code or '').upper()
        ctx = rc.build_ctx(config, self_code=self_code,
                           extra_recipes={self_code: recipe})
        formula, needs = rc.taxable_helper_formula(recipe, ctx)
        code = helper_code(self_code, 'TX')
        existing = config.rule_ids.filtered(lambda r: (r.code or '').upper() == code)
        if formula is None:
            if existing and existing.bp_template_key == 'helper':
                existing.unlink()
            return
        if needs:
            self._provision_helpers(config, {self_code: recipe})
            ctx = rc.build_ctx(config, self_code=self_code,
                               extra_recipes={self_code: recipe})
            formula, needs = rc.taxable_helper_formula(recipe, ctx)
            if needs:
                return
        # The helper is plumbing, and it says so in its own rule: without a
        # `helper` group it would be classified as an earning and summed into
        # the very total it exists to feed.
        vals = {'excel_formula': formula, 'bp_generated_formula': formula,
                'bp_formula_source': 'generated', 'column_type': 'formula',
                'bp_template_key': 'helper',
                'bp_recipe_json': json.dumps({
                    'v': 1, 'group': 'helper', 'audience': 'all',
                    'amount': {'kind': 'manual'}, 'proration': 'none',
                    'frequency': 'monthly', 'sign': 1, 'round': 'none',
                    'treatment': {'cash': 'cash', 'tax': 'exempt',
                                  'insurance': 'excluded'}}, sort_keys=True)}
        if existing:
            existing.write(vals)
            return
        result = self.env['pb.formula.studio'].add_component(config.id, {
            'name': _("%s — taxable part") % (rule.name or self_code),
            'code': code, 'column_type': 'formula',
        })
        created = self.env['hr.formula.rule'].browse(result.get('rule_id') or 0)
        if created.exists():
            created.write(dict(vals, appears_on_payslip=False,
                               visibility_rule='never'))

    def _write_share_helper(self, config, rule, recipe):
        """Keep the `<CODE>EE` employee share of a shared benefit in step.

        A benefit the employee pays part of is two lines on a payslip, not one:
        the employer's share under benefits and the employee's share under
        deductions. Both come from the same sentence, so changing the split
        moves both at once and they can never disagree.
        """
        self_code = (rule.code or '').upper()
        ctx = rc.build_ctx(config, self_code=self_code,
                           extra_recipes={self_code: recipe})
        formula, needs = rc.employee_share_formula(recipe, ctx)
        code = helper_code(self_code, 'EE')
        existing = config.rule_ids.filtered(lambda r: (r.code or '').upper() == code)
        if formula is None or needs:
            if existing and existing.bp_template_key == 'helper':
                existing.unlink()
            return
        share = rc.share_pct(recipe)
        ee_recipe = {
            'v': 1, 'group': 'deduction', 'audience': recipe.get('audience') or 'all',
            'amount': {'kind': 'manual'}, 'proration': 'none',
            'frequency': recipe.get('frequency') or 'monthly', 'sign': 1,
            'round': recipe.get('round', '0'),
            'treatment': {'cash': 'cash', 'tax': 'exempt', 'insurance': 'excluded',
                          'pit_deductible': 'no'},
        }
        vals = {'excel_formula': formula, 'bp_generated_formula': formula,
                'bp_formula_source': 'generated', 'column_type': 'formula',
                'bp_template_key': 'helper',
                'bp_recipe_json': json.dumps(ee_recipe, sort_keys=True)}
        if existing:
            existing.write(vals)
            return
        result = self.env['pb.formula.studio'].add_component(config.id, {
            'name': _("%(name)s — employee share (%(pct)s%%)",
                      name=rule.name or self_code,
                      pct=self._group(100.0 - share)),
            'code': code, 'column_type': 'formula',
        })
        created = self.env['hr.formula.rule'].browse(result.get('rule_id') or 0)
        if created.exists():
            created.write(vals)

    # ==================================================================
    # Removing, restoring, regenerating
    # ==================================================================
    @api.model
    def bp_component_exclude(self, config_id, rule_ids, confirm=False,
                             revision=None):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        Rule = self.env['hr.formula.rule']
        rules = Rule.browse([int(r) for r in (rule_ids or [])]).exists()
        rules = rules.filtered(lambda r: r.config_id == config)
        if not rules:
            return {'ok': False, 'reason': _("Nothing was selected to remove.")}

        locked = [r for r in rules
                  if rc.derived_group(r, r.bp_recipe()) in LOCKED_GROUPS]
        if locked:
            return {'ok': False, 'reason': _(
                "%s is part of every configuration and cannot be removed.",
                ', '.join(r.name or r.code for r in locked)),
                'blocked_by': [r.code for r in locked]}

        blocked = self._manual_dependants(config, rules)
        if blocked:
            names = ', '.join(sorted(blocked))
            return {'ok': False, 'blocked_by': sorted(blocked), 'reason': _(
                "Used by %s, which is written as Excel. Edit that calculation "
                "first.", names)}

        removed = [(r.code or '').upper() for r in rules]
        try:
            with self.env.cr.savepoint():
                helpers = self._own_helpers(config, removed)
                (rules | helpers).unlink()
                report = rc.regenerate(self.env, config)
                self._classify(config)
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        blueprint.revision += 1
        return {'ok': True, 'removed': removed,
                'regenerated': report['changed'], 'problems': report['problems'],
                'revision': blueprint.revision}

    def _own_helpers(self, config, codes):
        """The per-component helpers that only exist for these components."""
        wanted = set()
        for code in codes:
            for suffix in list(HELPER_SUFFIXES) + ['TX', 'EE']:
                wanted.add(helper_code(code, suffix))
        return config.rule_ids.filtered(
            lambda r: (r.code or '').upper() in wanted
            and r.bp_template_key == 'helper')

    def _manual_dependants(self, config, rules):
        """Hand-written formulas that name one of these components."""
        letters = {r.column_letter for r in rules if r.column_letter}
        codes = {(r.code or '').upper() for r in rules if r.code}
        gone = {r.id for r in rules}
        blocked = set()
        for other in config.rule_ids:
            if other.id in gone or other.column_type != 'formula':
                continue
            if other.bp_formula_source == 'generated':
                continue
            text = (other._normalize_excel_formula(
                other.excel_formula or '') or '').upper()
            if not text:
                continue
            tokens = set(re.findall(r'[A-Z][A-Z0-9]*', text))
            if tokens & letters or tokens & codes:
                blocked.add(other.code or other.name)
        return blocked

    @api.model
    def bp_component_include(self, config_id, code, revision=None):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        code = (code or '').strip().upper()
        key = blueprint.template_key if blueprint else ''
        template = self._template(key)
        if not template:
            return {'ok': False, 'reason': _(
                "This configuration did not come from a starter, so there is "
                "nothing to restore.")}
        comp = next((c for c in template._components()
                     if (c.get('code') or '').upper() == code), None)
        if not comp:
            return {'ok': False, 'reason': _(
                "%s is no longer part of this starter, so it cannot be "
                "brought back. Add it as a new component instead.", code)}
        if config.rule_ids.filtered(lambda r: (r.code or '').upper() == code):
            return {'ok': False, 'reason': _("%s is already here.", code)}

        recipes = self._template_recipes(key, template)
        try:
            with self.env.cr.savepoint():
                rule = self.env['hr.formula.rule'].create({
                    'config_id': config.id,
                    'code': code,
                    'name': comp.get('name') or code,
                    'column_type': comp.get('type') or 'formula',
                    'excel_formula': comp.get('excel_formula') or '',
                    'constant_value': float(comp.get('constant_value') or 0.0),
                    'default_value': float(comp.get('default_value') or 0.0),
                    'number_format': comp.get('number_format') or 'currency',
                    'appears_on_payslip': bool(comp.get('appears_on_payslip', True)),
                    'sequence': (max(config.rule_ids.mapped('sequence') or [0]) + 10),
                    'bp_template_key': key,
                })
                if code in recipes:
                    self._apply_recipes(config, {code: recipes[code]}, key)
                if rule.column_type == 'input':
                    self._seed_samples_with(config, rule)
                report = rc.regenerate(self.env, config)
                self._classify(config)
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        blueprint.revision += 1
        return {'ok': True, 'rule_id': rule.id, 'code': code,
                'regenerated': report['changed'],
                'revision': blueprint.revision}

    @api.model
    def bp_component_restore_guided(self, rule_id, revision=None):
        rule = self.env['hr.formula.rule'].browse(int(rule_id or 0))
        if not rule.exists():
            return {'ok': False, 'reason': _("That component no longer exists.")}
        config, blueprint, err = self._guard(rule.config_id.id)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        recipe = rule.bp_recipe()
        if not recipe:
            return {'ok': False, 'reason': _(
                "This component was never built from a sentence, so there is "
                "no guided version to go back to.")}
        self_code = (rule.code or '').upper()
        try:
            with self.env.cr.savepoint():
                self._provision_helpers(config, {self_code: recipe})
                ctx = rc.build_ctx(config, self_code=self_code)
                formula, needs = rc.compile_recipe(recipe, ctx)
                if formula is None or needs:
                    raise UserError(_(
                        "The guided version could not be worked out again."))
                ok, message = self._check(config, formula, exclude_id=rule.id)
                if not ok:
                    raise UserError(message)
                rule.write({'excel_formula': formula,
                            'bp_generated_formula': formula,
                            'bp_formula_source': 'generated',
                            'bp_generated_revision':
                                (rule.bp_generated_revision or 0) + 1})
                report = rc.regenerate(self.env, config)
        except AccessError:
            raise
        except (UserError, ValidationError) as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        blueprint.revision += 1
        return {'ok': True, 'rule_id': rule.id,
                'display_formula': self._display_formula(config, formula),
                'changed': report['changed'], 'revision': blueprint.revision}

    @api.model
    def bp_regenerate(self, config_id, revision=None):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        try:
            with self.env.cr.savepoint():
                report = rc.regenerate(self.env, config)
        except AccessError:
            raise
        except RecipeError as exc:
            return {'ok': False, 'reason': str(exc)}
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        blueprint.revision += 1
        return {'ok': True, 'changed': report['changed'],
                'problems': report['problems'], 'revision': blueprint.revision}

    # ==================================================================
    # Which tab was open
    # ==================================================================
    @api.model
    def bp_set_tab(self, config_id, tab):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        blueprint.set_ui('rules_tab', tab)
        return {'ok': True, 'tab': tab}
