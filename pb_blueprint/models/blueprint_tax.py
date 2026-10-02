# -*- coding: utf-8 -*-
"""Tax and the protections that come with pay — the server half.

One screen answers four questions a payroll manager actually asks:

* **Where do these numbers come from?** A country's statutory values have one
  source of truth — the rule pack — and this screen names it, dates it, cites
  the instrument it came from, and says whether the configuration still agrees
  with it. When it does not, it says which values differ and by how much, and
  offers to take the pack's again.
* **What are the tax bands?** An editable table with the upper bound of each
  band DERIVED from the next one's start, so two bands cannot overlap and no
  income can fall between them. That is not validation; it is a shape in which
  the mistake cannot be made.
* **What relief and what caps?** The constants, as numbers, each with the
  pack's own figure beside it when they differ.
* **What does it do to somebody's pay?** Every save regenerates the formulas
  and the panel on the right recomputes, so a band edit is visible in a
  take-home figure within a second.

Every gate is here, on the server (ledger rule 9): a configuration that is no
longer a draft is refused, an out-of-date revision is refused, and a band table
that does not make arithmetic sense is refused by name.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.pb_hr_payroll_formula.models.statutory_approval import (
    STATUTORY_WRITE as _STATUTORY_WRITE,
)

from . import recipe_compiler as rc
from .recipe_schema import INSURANCE_BASIS, RecipeError, validate_recipe

_logger = logging.getLogger(__name__)

#: The relief constants, in the order they are read on screen, with the
#: legislation code each one belongs to in the country's rule pack.
RELIEF_CODES = (
    ('DEDUCTSELF', 'DEDUCTSELF'),
    ('DEDUCTDEP', 'DEDUCTDEP'),
)

#: The insurance constants: caps first, then the employee's rates, then the
#: employer's. Second element is the legislation code the pack uses.
INSURANCE_CODES = (
    ('CAPLO', 'CAPLO'),
    ('CAPHI', 'CAPHI'),
    ('SIRATE', 'EESI'),
    ('HIRATE', 'EEHI'),
    ('UIRATE', 'EEUI'),
    ('SIEMPR', 'ERSI'),
    ('HIEMPR', 'ERHI'),
    ('UIEMPR', 'ERUI'),
)

#: The other ways income can be taxed. Only shown when the configuration
#: actually carries them (the Complete starter does; Essentials does not).
ROUTE_CODES = (
    ('NONRESRATE', ''),
    ('SHORTRATE', ''),
    ('SHORTTHRESH', ''),
)

def value_label(code):
    """The words on the screen for one statutory value."""
    return {
        'DEDUCTSELF': _("Personal relief"),
        'DEDUCTDEP': _("Relief per registered dependant"),
        'CAPLO': _("Social and health insurance ceiling"),
        'CAPHI': _("Unemployment insurance ceiling"),
        'SIRATE': _("Social insurance — employee"),
        'HIRATE': _("Health insurance — employee"),
        'UIRATE': _("Unemployment insurance — employee"),
        'SIEMPR': _("Social insurance — employer"),
        'HIEMPR': _("Health insurance — employer"),
        'UIEMPR': _("Unemployment insurance — employer"),
        'NONRESRATE': _("Flat rate for people who are not tax resident"),
        'SHORTRATE': _("Withholding rate on contracts under three months"),
        'SHORTTHRESH': _("Payment at which withholding starts"),
    }.get(code, code)


class PbBlueprintTax(models.AbstractModel):
    _inherit = 'pb.blueprint.studio'

    # ==================================================================
    # Reading the tab
    # ==================================================================
    @api.model
    def bp_tax_data(self, config_id):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        pack = self._tax_pack(config, blueprint)
        if blueprint and pack and not blueprint.pack_id:
            # Pinned the first time the tab is opened, so that a pack published
            # later never silently changes what this configuration was built
            # against (BP-R5: the pin lives here, not on the configuration).
            blueprint.write({'pack_id': pack.id, 'pack_version': pack.version})
        legis = self._pack_values(pack)
        matched = self._legis_rule_map(config, blueprint, pack)

        drift, unmatched = [], []
        for code, item in legis.items():
            rule = matched.get(code)
            if not rule:
                unmatched.append({'code': code, 'label': item['label'],
                                  'target': item['value'],
                                  'number_format': item['number_format']})
                continue
            current = rule.constant_value or 0.0
            if round(current, 6) != round(item['value'], 6):
                drift.append({
                    'code': code,
                    'component': (rule.code or '').upper(),
                    'label': rule.name or item['label'],
                    'current': current,
                    'target': item['value'],
                    'delta': item['value'] - current,
                    'rule_id': rule.id,
                    'number_format': item['number_format'],
                })

        status = 'na' if not pack or not matched else (
            'drift' if drift else 'aligned')
        prefs = self._tax_prefs(blueprint)
        return {
            'ok': True,
            'pack': self._pack_payload(pack),
            'status': status,
            'drift': drift,
            'unmatched': unmatched,
            'tables': self._band_tables(config),
            'values': {
                'relief': self._value_rows(config, RELIEF_CODES, legis, matched),
                'insurance': self._value_rows(config, INSURANCE_CODES, legis,
                                              matched),
                'routes': self._value_rows(config, ROUTE_CODES, legis, matched),
            },
            'prefs': prefs,
            'editable': self._tax_editable(config),
            'readonly_reason': self._tax_readonly_reason(config),
            'revision': blueprint.revision if blueprint else 0,
            'currency': config.currency_id.name or '',
            'country': config.country_code or '',
        }

    # ------------------------------------------------------------------
    def _tax_editable(self, config):
        return config.state == 'draft' and not self._has_payslips(config)

    def _tax_readonly_reason(self, config):
        if config.state == 'draft' and not self._has_payslips(config):
            return ''
        if self._has_payslips(config):
            return _("This configuration has already produced payslips. Its "
                     "values are managed from the components grid, where every "
                     "change is versioned.")
        return _("This configuration is no longer a draft. Its values are "
                 "managed from the components grid, where every change is "
                 "versioned.")

    def _tax_pack(self, config, blueprint):
        """The rule pack this configuration's statutory values belong to.

        Newest published pack for the country that was already in force on the
        date the configuration is meant to start. A pack that starts later is
        not the one this payroll runs on, however new it is.
        """
        Pack = self.env['hr.formula.legislation.pack'].sudo()
        country = config.country_code or ''
        if not country:
            return None
        if blueprint and blueprint.pack_id and blueprint.pack_id.exists():
            return blueprint.pack_id
        when = (blueprint and blueprint.effective_from) or fields.Date.context_today(self)
        packs = Pack.search([('country_code', '=', country),
                            ('state', '=', 'published')])
        if not packs:
            return None
        in_force = packs.filtered(
            lambda p: not p.effective_date or p.effective_date <= when)
        chosen = (in_force or packs).sorted(
            key=lambda p: (p.effective_date or fields.Date.to_date('1900-01-01'),
                           p.sequence, p.id), reverse=True)
        return chosen[:1] or None

    def _pack_payload(self, pack):
        """What the screen may say about a rule pack.

        Deliberately NOT the pack's own ``description``. That field is written
        for an engineer comparing pack versions and on the shipped Vietnam pack
        it reads "Serves both existing-config rollout (B4) and new-config
        template seeding (F113)" — internal vocabulary, in front of a payroll
        manager. The facts that actually answer "where do these come from" are
        the instrument, the date it took effect and how many values it carries,
        and those are all clean.
        """
        if not pack:
            return None
        return {
            'id': pack.id,
            'name': pack.name or '',
            'version': pack.version or '',
            'effective_date': pack.effective_date and str(pack.effective_date) or '',
            'authority': pack.authority or '',
            'state': pack.state,
            'item_count': len(pack.item_ids),
        }

    def _pack_values(self, pack):
        """``{legislation_code: {value, label, number_format}}``."""
        out = {}
        if not pack:
            return out
        for item in pack.item_ids.sorted(key=lambda i: i.sequence):
            if not item.code:
                continue
            out[item.code] = {
                'value': item.value or 0.0,
                'label': item.label or item.code,
                'number_format': item.number_format or 'currency',
                'note': item.note or '',
            }
        return out

    def _legis_rule_map(self, config, blueprint, pack):
        """``{legislation_code: constant rule}`` for this configuration.

        `hr.formula.rule` does not store the legislation code — only the
        template's `components_json` does, and only at seed time. So the map is
        rebuilt from the starter this configuration came from, and where that
        says nothing (a blank canvas, an imported workbook, a starter that has
        since changed) the pack's own code is tried as a component code, which
        is exactly what `_legis_constant` does for the whole estate.
        """
        Studio = self.env['pb.formula.studio']
        out = {}
        by_legis = self._template_legislation_codes(blueprint)
        for legis_code in (self._pack_values(pack) or {}):
            component = by_legis.get(legis_code)
            rule = Studio._legis_constant(config, component) if component else None
            if not rule:
                rule = Studio._legis_constant(config, legis_code)
            if rule:
                out[legis_code] = rule
        return out

    def _template_legislation_codes(self, blueprint):
        """``{legislation_code: component_code}`` from the starter, if any."""
        key = blueprint.template_key if blueprint else ''
        template = self._template(key)
        if not template:
            return {}
        out = {}
        for comp in template._components():
            legis = comp.get('legislation_code')
            if legis and comp.get('code'):
                out[legis] = (comp['code'] or '').upper()
        return out

    def _component_legislation_codes(self, blueprint):
        """The same map, the other way round: ``{component_code: legis_code}``."""
        return {v: k for k, v in self._template_legislation_codes(blueprint).items()}

    def _value_rows(self, config, wanted, legis, matched):
        """One row per statutory value this configuration actually carries."""
        Studio = self.env['pb.formula.studio']
        rows = []
        for component_code, legis_code in wanted:
            rule = Studio._legis_constant(config, component_code)
            if not rule and legis_code:
                rule = matched.get(legis_code)
            if not rule:
                continue
            pack_value = legis.get(legis_code, {}).get('value') if legis_code else None
            rows.append({
                'code': (rule.code or component_code).upper(),
                'legis_code': legis_code or '',
                'label': rule.name or value_label(component_code),
                'value': rule.constant_value or 0.0,
                'pack': pack_value,
                'differs': pack_value is not None
                and round(pack_value, 6) != round(rule.constant_value or 0.0, 6),
                'number_format': rule.number_format or 'currency',
                'rule_id': rule.id,
            })
        return rows

    def _band_tables(self, config):
        """Every band table, with what depends on it."""
        tables = []
        for table in config.rate_table_ids.sorted(key=lambda t: (t.sequence, t.id)):
            code = (table.code or '').upper()
            used_by = [(r.code or '').upper() for r in config.rule_ids
                       if r.excel_formula and code
                       and code in (r.excel_formula or '').upper()]
            tables.append({
                'id': table.id,
                'code': code,
                'name': table.name or code,
                'note': table.note or '',
                'brackets': [{'lower': b.lower or 0.0, 'rate': b.rate or 0.0}
                             for b in table.line_ids.sorted(key=lambda b: b.lower)],
                'used_by': used_by,
            })
        return tables

    def _tax_prefs(self, blueprint):
        stored = blueprint.tax_prefs() if blueprint else {}
        basis = stored.get('basis')
        rounding = stored.get('rounding')
        return {
            'basis': basis if basis in INSURANCE_BASIS else 'actual',
            'rounding': rounding if rounding in ('0', 'down') else '0',
        }

    # ==================================================================
    # Saving the bands
    # ==================================================================
    @api.model
    def bp_tax_save_bands(self, config_id, table_id, brackets, revision=None):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        if not self._tax_editable(config):
            return {'ok': False, 'reason': self._tax_readonly_reason(config)}

        table = config.rate_table_ids.filtered(lambda t: t.id == int(table_id or 0))[:1]
        if not table:
            return {'ok': False, 'reason': _(
                "That band table is no longer part of this configuration.")}

        clean, problem = self._clean_brackets(brackets)
        if problem:
            return {'ok': False, 'reason': problem}

        try:
            with self.env.cr.savepoint():
                # BP3: `save_rate_table` unlinks and recreates every bracket, so
                # the ids on the client are gone the moment this returns. The
                # screen is repainted from the answer, never from what it held.
                #
                # P7: THE GUIDED JOURNEY IS NOT HELD, AND THAT IS THE POINT.
                # A rate table on a LIVE scheme travels the statutory route,
                # because it is a statement about what a country pays. This one
                # is being written inside the setup journey, on a configuration
                # nobody is paid by yet, and the moment the whole thing IS
                # agreed to is the scheme's own activation — which Phase 4
                # already holds. A route in the middle of a setup wizard is a
                # dead end, not a safeguard.
                result = self.env['pb.formula.studio'].with_context(
                    **{_STATUTORY_WRITE: True}).save_rate_table(config.id, {
                    'id': table.id,
                    'code': (table.code or '').upper(),
                    'name': table.name or table.code,
                    'note': table.note or '',
                    'brackets': clean,
                })
                if not result.get('ok'):
                    raise UserError(result.get('msg') or _(
                        "The bands could not be saved."))
                report = rc.regenerate(self.env, config, reason='legislation')
        except AccessError:
            raise
        except (UserError, ValidationError) as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        except Exception as exc:
            _logger.warning("Guided setup: band save failed: %s", exc, exc_info=True)
            return {'ok': False, 'reason': self._plain(exc)}

        if blueprint:
            blueprint.revision += 1
        return {'ok': True, 'tables': self._band_tables(config),
                'problems': report['problems'],
                'revision': blueprint.revision if blueprint else 0}

    def _clean_brackets(self, brackets):
        """``([{lower, rate}], '')`` — or the reason this schedule is refused."""
        rows = []
        for raw in (brackets or []):
            try:
                lower = float(raw.get('lower') or 0.0)
                rate = float(raw.get('rate') or 0.0)
            except (TypeError, ValueError, AttributeError):
                return [], _("A band needs a starting amount and a rate.")
            if lower < 0:
                return [], _("A band cannot start below zero.")
            if not 0.0 <= rate <= 1.0:
                return [], _("A rate is a percentage between 0 and 100.")
            rows.append({'lower': lower, 'rate': rate})
        if not rows:
            return [], _("A tax table needs at least one band.")
        rows.sort(key=lambda r: r['lower'])
        seen = set()
        for row in rows:
            if row['lower'] in seen:
                return [], _("Two bands start at the same amount.")
            seen.add(row['lower'])
        if rows[0]['lower'] != 0.0:
            return [], _("The first band has to start at zero, or income below "
                         "it would not be taxed at all.")
        return rows, ''

    # ==================================================================
    # Saving the values and the preferences
    # ==================================================================
    @api.model
    def bp_tax_save_values(self, config_id, values=None, prefs=None, revision=None):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        if not self._tax_editable(config):
            return {'ok': False, 'reason': self._tax_readonly_reason(config)}

        Studio = self.env['pb.formula.studio']
        written = []
        try:
            with self.env.cr.savepoint():
                seen = set()
                for code, raw in (values or {}).items():
                    rule = Studio._legis_constant(config, code)
                    if not rule:
                        return {'ok': False, 'reason': _(
                            "There is no value called %s in this "
                            "configuration.", code)}
                    try:
                        number = float(raw)
                    except (TypeError, ValueError):
                        return {'ok': False, 'reason': _(
                            "%s has to be a number.", rule.name or code)}
                    if number < 0:
                        return {'ok': False, 'reason': _(
                            "%s cannot be negative.", rule.name or code)}
                    if (rule.number_format or '') == 'percentage' and number > 1.0:
                        return {'ok': False, 'reason': _(
                            "%s is a percentage between 0 and 100.",
                            rule.name or code)}
                    if round(rule.constant_value or 0.0, 6) == round(number, 6):
                        continue
                    # F7 records WHY a statutory value moved, and "legislation"
                    # is the reason a reviewer looks for later (BP-R5).
                    rule.with_context(
                        formula_version_reason='legislation',
                        formula_version_note=_("Edited during guided setup"),
                        formula_version_seen=seen).constant_value = number
                    written.append((rule.code or '').upper())
                changed_prefs = self._apply_prefs(config, blueprint, prefs)
                if changed_prefs:
                    rc.regenerate(self.env, config, reason='refactor')
        except AccessError:
            raise
        except (UserError, ValidationError) as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        except Exception as exc:
            _logger.warning("Guided setup: value save failed: %s", exc, exc_info=True)
            return {'ok': False, 'reason': self._plain(exc)}

        if blueprint:
            blueprint.revision += 1
        return {'ok': True, 'written': written, 'prefs': self._tax_prefs(blueprint),
                'revision': blueprint.revision if blueprint else 0}

    def _apply_prefs(self, config, blueprint, prefs):
        """Store the two preferences, and make them true in the formulas.

        * **Insurance basis** decides what the insurable-pay component adds up:
          "actual eligible pay" sums every earning marked as counting toward
          insurance; "contractual eligible pay" uses the contract salary itself,
          so a short month does not reduce somebody's cover.
        * **Rounding** decides whether a money component that rounds does so to
          the nearest whole amount or always downward. A component set to keep
          every decimal is LEFT ALONE — the Essentials starter is deliberately
          exact so its own certification numbers stay byte-identical.
        """
        if not prefs or not blueprint:
            return False
        current = self._tax_prefs(blueprint)
        basis = prefs.get('basis') if prefs.get('basis') in INSURANCE_BASIS \
            else current['basis']
        rounding = prefs.get('rounding') if prefs.get('rounding') in ('0', 'down') \
            else current['rounding']
        if basis == current['basis'] and rounding == current['rounding']:
            return False
        blueprint.tax_json = json.dumps({'basis': basis, 'rounding': rounding},
                                        sort_keys=True)

        codes = {(r.code or '').upper() for r in config.rule_ids}
        tables = {(t.code or '').upper() for t in config.rate_table_ids}
        touched = False
        for rule in config.rule_ids:
            recipe = rule.bp_recipe()
            if not recipe:
                continue
            amount = recipe.get('amount') or {}
            before = json.dumps(recipe, sort_keys=True)
            if amount.get('kind') == 'insurance_base':
                amount['basis'] = basis
                recipe['amount'] = amount
            if recipe.get('group') in ('earning', 'deduction', 'benefit') \
                    and str(recipe.get('round', '0')) not in ('none',):
                recipe['round'] = rounding
            if json.dumps(recipe, sort_keys=True) == before:
                continue
            try:
                clean = validate_recipe(recipe, {
                    'codes': codes, 'rate_tables': tables,
                    'self_code': (rule.code or '').upper()})
            except RecipeError as exc:
                _logger.info("Guided setup: %s kept its rule: %s", rule.code, exc)
                continue
            rule.bp_recipe_json = json.dumps(clean, sort_keys=True)
            touched = True
        return touched

    # ==================================================================
    # Taking the pack's values again
    # ==================================================================
    @api.model
    def bp_tax_sync_pack(self, config_id, revision=None):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        if not self._tax_editable(config):
            return {'ok': False, 'reason': self._tax_readonly_reason(config)}

        pack = self._tax_pack(config, blueprint)
        if not pack:
            return {'ok': False, 'reason': _(
                "There is no published rule pack for this country yet, so "
                "there is nothing to take. The values above are yours to set.")}
        legis = self._pack_values(pack)
        matched = self._legis_rule_map(config, blueprint, pack)

        applied = []
        try:
            with self.env.cr.savepoint():
                seen = set()
                for code, rule in matched.items():
                    target = legis[code]['value']
                    if round(rule.constant_value or 0.0, 6) == round(target, 6):
                        continue
                    rule.with_context(
                        formula_version_reason='legislation',
                        formula_version_note='%s %s' % (pack.name, pack.version),
                        formula_version_seen=seen).constant_value = target
                    applied.append((rule.code or '').upper())
                if applied:
                    self._record_pack_application(pack, config, len(applied))
        except AccessError:
            raise
        except Exception as exc:
            _logger.warning("Guided setup: pack sync failed: %s", exc, exc_info=True)
            return {'ok': False, 'reason': self._plain(exc)}

        if blueprint:
            blueprint.write({'pack_id': pack.id, 'pack_version': pack.version,
                             'revision': blueprint.revision + 1})
        return {'ok': True, 'applied': applied,
                'revision': blueprint.revision if blueprint else 0}

    def _record_pack_application(self, pack, config, count):
        """Leave the same audit trail the estate-wide rollout leaves.

        A statutory value that moved has to be explainable a year later, and
        "somebody pressed a button in the setup screen" is not an explanation.
        Never fatal: a missing milestone must not lose the values themselves.
        """
        try:
            milestone = self.env['hr.formula.config.milestone'].sudo().record(
                config, _("Took the values from %(pack)s %(version)s",
                          pack=pack.name, version=pack.version or ''))
            self.env['hr.formula.legislation.application'].create({
                'pack_id': pack.id, 'config_id': config.id,
                'item_count': count, 'milestone_id': milestone.id,
            })
        except Exception as exc:               # pragma: no cover - advisory
            _logger.info("Guided setup: pack application not logged: %s", exc)
