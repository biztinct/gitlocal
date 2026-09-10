# -*- coding: utf-8 -*-
"""The one door between the guided setup screen and the payroll engine.

Every method is `@api.model`, takes and returns plain dictionaries, and never
lets a traceback reach a person: a failure comes back as
``{'ok': False, 'reason': "<a sentence a payroll manager can act on>"}``.
Access failures are the exception — those raise, because a refusal that looks
like a normal answer is how data leaks.

Nothing here re-implements the engine. Components come from the template
registry's own seeder, numbers come from the same evaluator a real payslip
uses, and samples come from the existing sample model.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .blueprint import DEFAULT_OPTIONAL_STATUS, STEPS

_logger = logging.getLogger(__name__)

#: Plain-English names for the kinds of pay run. The engine's own labels are
#: shorthand ("Mid-Cycle"); these are the words on the screen.
CYCLE_LABELS = {
    'regular': "Regular payroll",
    'mid_cycle': "Mid-month advance",
    'end_cycle': "End-month payroll",
    'full_final': "Full and final",
}

#: The five numbers the pay panel shows, and the component code that carries
#: each one when the configuration follows the usual naming. Used only where
#: the engine's own classification has nothing to say (see `_pay_lines`).
FALLBACK_CODES = {
    'take_home': 'NET',
    'cash': 'GROSS',
    'deductions': 'EEDED',
    'tax': 'PIT',
    'employer': 'ERCOST',
}

#: The engine's net-pay classification (VALUEKIND / NETROLE) that answers each
#: line when the codes are not the usual ones.
ROLE_FOR_LINE = {
    'take_home': 'net',
    'cash': 'earning',
    'deductions': 'deduction',
    'employer': 'employer_cost',
}

LINE_LABELS = {
    'cash': "Cash earnings",
    'deductions': "Employee deductions",
    'tax': "Income tax",
    'employer': "Employer cost",
}

#: Sensible opening numbers for a brand-new sample employee, so the pay panel
#: shows a believable person instead of a column of zeroes. Only used when the
#: starter did not bring its own sample.
SEED_INPUTS = {
    'BASIC': 30000000.0,
    'STDDAYS': 26.0,
    'DEPS': 1.0,
}

#: The starters we ship, most complete first. A card the person reads left to
#: right should offer the fullest answer before the smaller one, and neither
#: alphabetical order nor a registry sequence says that reliably.
STARTER_ORDER = ('vn_complete_2026', 'vn_standard_2026')


def starter_tagline(key):
    """One line under a starter's name — what it actually gives you."""
    return {
        'vn_complete_2026': _(
            "Every line a Vietnamese payroll normally needs — allowances, four "
            "kinds of overtime, insurance, union, private health cover and "
            "income tax — each with a rule you can read. Remove what you do "
            "not need."),
        'vn_standard_2026': _(
            "The essentials: paid salary, overtime, insurance, income tax and "
            "take-home pay."),
    }.get(key, '')


class PbBlueprintStudio(models.AbstractModel):
    _name = 'pb.blueprint.studio'
    _description = 'Guided Payroll Setup Service'

    # ==================================================================
    # Shared plumbing
    # ==================================================================
    def _config(self, config_id):
        """The configuration, or None. Never raises for "not found"."""
        try:
            cfg = self.env['hr.formula.config'].browse(int(config_id or 0))
            return cfg if cfg.exists() else None
        except (TypeError, ValueError):
            return None

    def _wrong_company_reason(self, config_id):
        """Why this configuration cannot be opened, in the words on the screen.

        The record rule on `hr.formula.config` refuses the read before any of
        our own checks run, and the framework's own refusal is not something a
        payroll manager should ever see: it names the technical model, offers a
        joke about cookies, and is not white-labelled. The one fact that helps
        is WHICH COMPANY to switch to, so we read just that, with sudo, and say
        it plainly. Nothing else about the record is revealed.
        """
        try:
            cfg = self.env['hr.formula.config'].sudo().browse(int(config_id or 0))
            company = cfg.exists() and cfg.company_id
        except Exception:                   # pragma: no cover - defensive
            company = None
        if company:
            return _(
                "This setup belongs to %(other)s. Switch to %(other)s in the "
                "company selector at the top of the screen to open it.",
                other=company.name)
        return _("You do not have access to this configuration. Ask whoever "
                 "looks after payroll setup to share it with you.")

    def _blueprint(self, config):
        return self.env['pb.formula.blueprint'].search(
            [('config_id', '=', config.id)], limit=1)

    def _reachable_company_ids(self):
        """Every company this user may act in, including the one they are in.

        `env.company` is NOT guaranteed to be a member of `env.companies`: a
        user's `company_id` can point at a company that is absent from their
        `company_ids`, and on that user every guard written as
        `company.id not in env.companies.ids` locks them out of the company
        they are actually standing in. Verified on p9clone, where user 1's
        current company ("Your Company") is missing from their allowed list.
        """
        return set(self.env.companies.ids) | {self.env.company.id}

    def _guard(self, config_id, require_blueprint=True):
        """Resolve a configuration for editing, or return the reason we cannot.

        Returns ``(config, blueprint, error_dict_or_None)``. The company check is
        deliberately two-layered: a company outside the user's allowed set is an
        access failure and RAISES; a company that is simply not the one selected
        in the top bar is a normal, explainable situation and comes back as a
        sentence with a next step (BP-R11).
        """
        try:
            config = self._config(config_id)
            # Force the company read HERE, inside the guard: the record rule
            # fires on first access and its own message must never reach a
            # person (it names the technical model and is not white-labelled).
            company = config.company_id if config else None
        except AccessError:
            return None, None, {'ok': False,
                                'reason': self._wrong_company_reason(config_id)}
        if not config:
            return None, None, {'ok': False, 'reason': _(
                "That configuration no longer exists. It may have been deleted.")}
        if company and company.id not in self._reachable_company_ids():
            return None, None, {'ok': False,
                                'reason': self._wrong_company_reason(config_id)}
        if company and company.id != self.env.company.id:
            return config, None, {'ok': False, 'reason': _(
                "This setup belongs to %(other)s. Switch to %(other)s in the "
                "company selector at the top of the screen to carry on.",
                other=company.name)}
        bp = self._blueprint(config)
        if require_blueprint and not bp:
            return config, None, {'ok': False, 'reason': _(
                "This configuration was not created with the guided setup, so "
                "there is nothing to resume. Open it in the components grid "
                "instead.")}
        return config, bp or None, None

    @api.model
    def _plain(self, exc):
        """The first readable line of an exception, for a person to read."""
        text = str(exc or '').strip()
        first = text.splitlines()[0] if text else ''
        return first or _("Something went wrong. Nothing was created.")

    def _has_payslips(self, config):
        """True when real pay has been produced by this configuration."""
        Payslip = self.env.get('hr.payslip')
        if Payslip is None or 'formula_config_id' not in Payslip._fields:
            return False
        return bool(Payslip.sudo().search_count(
            [('formula_config_id', '=', config.id)]))

    # ==================================================================
    # Starting points
    # ==================================================================
    @api.model
    def bp_templates(self, country_code=None):
        """The cards on "How would you like to start?".

        Every registry starter for the chosen country, then always the Excel
        workbook and the blank canvas. The legacy built-in Vietnam entry is
        dropped: the rule pack supersedes it, and two Vietnam cards with the
        same components is a choice nobody can make correctly.
        """
        country = (country_code or 'VN').upper()
        Config = self.env['hr.formula.config']
        countries = [{'code': code, 'label': label}
                     for code, label in Config._fields['country_code'].selection]
        try:
            raw = self.env['pb.formula.studio'].wizard_templates()
        except Exception as exc:            # pragma: no cover - registry outage
            _logger.warning("Guided setup: starter list unavailable: %s", exc)
            raw = []

        starters = []
        for tpl in raw:
            if tpl.get('builtin'):
                continue
            if (tpl.get('country') or '').upper() != country:
                continue
            key = tpl.get('key')
            starters.append({
                'key': key,
                'kind': 'template',
                'name': tpl.get('name') or key,
                # The registry's own description is written for an engineer
                # comparing versions. The card gets the sentence a person
                # choosing between two starters actually needs.
                'desc': starter_tagline(key) or tpl.get('desc') or '',
                'country': tpl.get('country') or '',
                'version': tpl.get('version') or '',
                'effective_date': tpl.get('effective_date') or '',
                'certified': bool(tpl.get('certified')),
                'state': tpl.get('state') or 'draft',
                'component_count': len(tpl.get('components') or []),
                'rate_table_count': len(tpl.get('rate_tables') or []),
                'default': False,
            })
        starters.sort(key=lambda s: (
            STARTER_ORDER.index(s['key']) if s['key'] in STARTER_ORDER else 9,
            not s['certified'], s['name']))

        starters.append({
            'key': 'excel', 'kind': 'excel',
            'name': _("Import Excel workbook"),
            'desc': _("Review a payroll workbook, keep its formulas, map its inputs."),
            'country': country, 'version': '', 'effective_date': '',
            'certified': False, 'state': '', 'component_count': 0,
            'rate_table_count': 0, 'default': False,
        })
        starters.append({
            'key': 'blank', 'kind': 'blank',
            'name': _("Blank canvas"),
            'desc': _("Start with your own components. The country's shared "
                      "rules stay available."),
            'country': country, 'version': '', 'effective_date': '',
            'certified': False, 'state': '', 'component_count': 0,
            'rate_table_count': 0, 'default': False,
        })

        # Pre-selection, most complete first: the fullest starter is the one a
        # person is least likely to regret, because taking a component out is
        # one click and putting a missing one in is a decision they have to
        # know to make. On a country with no starter at all, the blank canvas.
        chosen = None
        for key in STARTER_ORDER:
            chosen = next((s for s in starters if s['key'] == key), None)
            if chosen:
                break
        if not chosen:
            chosen = next((s for s in starters if s['kind'] == 'template'), None)
        if not chosen:
            chosen = next(s for s in starters if s['kind'] == 'blank')
        chosen['default'] = True

        return {
            'ok': True,
            'country': country,
            'countries': countries,
            'starters': starters,
            'has_template': any(s['kind'] == 'template' for s in starters),
            # The company chip names the company the server will FILE the draft
            # under, so it comes from the server and never from a client guess.
            'company': self.env.company.name,
        }

    # ==================================================================
    # Creating the draft
    # ==================================================================
    @api.model
    def bp_start(self, vals, token):
        """Create the draft configuration, seed the starter, make a sample.

        One transaction: either all three happened or nothing did. Never
        `create_config` — that helper hard-codes Vietnam and ignores the
        company, which on a group would silently file the draft in the wrong
        place (BP-R6).
        """
        vals = vals or {}
        token = (token or '').strip()
        if not token:
            return {'ok': False, 'reason': _(
                "The setup could not be identified. Reload the page and try again.")}

        Blueprint = self.env['pb.formula.blueprint']
        existing = Blueprint.search([
            ('token', '=', token),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if existing:
            # Second press of Continue, a double click, or a retry after the
            # connection dropped. Same draft, every time.
            return self._start_payload(existing)

        name = (vals.get('name') or '').strip()
        if not name:
            return {'ok': False, 'reason': _("Give the configuration a name first.")}

        country = (vals.get('country_code') or 'VN').upper()
        cycle = vals.get('cycle_type') or 'regular'
        if cycle not in dict(self.env['hr.formula.config']._fields['cycle_type'].selection):
            cycle = 'regular'
        template_key = vals.get('template_key') or 'blank'
        # The Excel workbook route creates an empty configuration and then
        # hands over to the import review, so it seeds exactly like a blank.
        seed_key = 'blank' if template_key in ('blank', 'excel') else template_key

        tpl = None
        if seed_key != 'blank':
            tpl = self.env['hr.formula.config.template'].sudo().search([
                ('code', '=', seed_key), ('state', '!=', 'superseded')], limit=1)
            if not tpl:
                return {'ok': False, 'reason': _(
                    "That starting point is no longer available. Choose "
                    "another one, or start from a blank canvas.")}

        try:
            with self.env.cr.savepoint():
                config = self.env['hr.formula.config'].create({
                    'name': name,
                    'country_code': country,
                    'cycle_type': cycle,
                    'company_id': self.env.company.id,
                    'state': 'draft',
                })
                if tpl:
                    try:
                        tpl.seed_config(config)
                    except (UserError, ValidationError) as exc:
                        raise UserError(_(
                            "“%(starter)s” could not be added: %(why)s",
                            starter=tpl.name, why=self._plain(exc))) from exc
                    # Everything the starter brought is a certification
                    # scenario, and the Test step says so on the row. Stamped
                    # HERE because this is the only moment anybody can tell:
                    # afterwards a starter's scenario and a person's own are
                    # both an ordinary sample with numbers in it.
                    self._stamp_origin(config.sample_data_ids, 'starter')
                self._ensure_sample(config)
                self._classify(config)
                blueprint = Blueprint.create({
                    'config_id': config.id,
                    'token': token,
                    'state': 'draft',
                    'step': 'rules',
                    'template_key': template_key,
                    'template_name': tpl.name if tpl else (
                        _("Import Excel workbook") if template_key == 'excel'
                        else _("Blank canvas")),
                    'effective_from': vals.get('effective_from') or False,
                    'situations_json': json.dumps(vals.get('situations') or {}),
                    'optional_status_json': json.dumps(DEFAULT_OPTIONAL_STATUS),
                })
                # The starter's components arrive as Excel; this gives them the
                # sentences they always implied, so the Pay rules step opens on
                # readable rules rather than on 37 rows of formulas.
                self._backfill_essentials(config, blueprint)
        except AccessError:
            raise
        except Exception as exc:
            _logger.warning("Guided setup: draft creation failed: %s", exc,
                            exc_info=True)
            return {'ok': False, 'reason': self._plain(exc)}
        return self._start_payload(blueprint)

    def _start_payload(self, blueprint):
        config = blueprint.config_id
        sample = config.sample_data_ids[:1]
        return {
            'ok': True,
            'config_id': config.id,
            'blueprint_id': blueprint.id,
            'step': blueprint.step,
            'rule_count': len(config.rule_ids),
            'sample_id': sample.id if sample else False,
        }

    def _ensure_sample(self, config):
        """Every configuration reaches the pay panel with somebody in it.

        A starter that ships certification tests already has samples; a blank
        canvas has none, and an empty panel on step 2 is the moment the whole
        idea stops being convincing.
        """
        if config.sample_data_ids:
            return config.sample_data_ids[0]
        inputs = {}
        for rule in config.rule_ids:
            if rule.column_type != 'input' or not rule.code:
                continue
            inputs[rule.code] = float(
                rule.default_value or SEED_INPUTS.get(rule.code.upper(), 0.0))
        if not inputs:
            inputs = dict(SEED_INPUTS)
        sample = self.env['hr.formula.sample.data'].create({
            'config_id': config.id,
            'name': _("Sample employee"),
            'source_type': 'manual',
            'input_values_json': json.dumps(inputs),
        })
        self._stamp_origin(sample, 'yours')
        return sample

    def _stamp_origin(self, samples, origin):
        """Remember where a scenario came from, where the field exists.

        Guarded rather than assumed: this runs during install, when the column
        may not be in the registry yet on a database mid-upgrade, and a stamp
        that cannot be written must never stop a draft from being created.
        """
        try:
            rows = samples.filtered(lambda s: not s.bp_origin) \
                if 'bp_origin' in samples._fields else samples.browse()
            if rows:
                rows.bp_origin = origin
        except Exception as exc:        # pragma: no cover - advisory only
            _logger.info("Guided setup: scenario origin not stamped: %s", exc)

    def _classify(self, config):
        """Ask the engine what each component does to net pay.

        Best effort and never fatal: it only decides which four lines the pay
        panel can label when a configuration does not use the usual codes.
        """
        try:
            if hasattr(config, 'classify_net_roles'):
                config.classify_net_roles()
        except Exception as exc:            # pragma: no cover - advisory only
            _logger.info("Guided setup: net-pay classification skipped: %s", exc)

    # ==================================================================
    # Reading a draft back
    # ==================================================================
    @api.model
    def bp_load(self, config_id):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        return self._load_payload(config, blueprint)

    def _load_payload(self, config, blueprint):
        rules = config.rule_ids.sorted(key=lambda r: (r.sequence, r.id))
        by_type = {'input': 0, 'formula': 0, 'constant': 0}
        components = []
        for rule in rules:
            by_type[rule.column_type] = by_type.get(rule.column_type, 0) + 1
            components.append({
                'id': rule.id,
                'code': rule.code or '',
                'name': rule.name or rule.code or '',
                'column_type': rule.column_type,
                'column_letter': rule.column_letter or '',
            })
        starters = self.bp_templates(config.country_code)
        country_labels = dict(
            self.env['hr.formula.config']._fields['country_code'].selection)
        return {
            'ok': True,
            'config': {
                'id': config.id,
                'name': config.name or '',
                'code': config.code or '',
                'country_code': config.country_code or '',
                'country_label': country_labels.get(config.country_code, ''),
                'cycle_type': config.cycle_type or 'regular',
                'cycle_label': CYCLE_LABELS.get(config.cycle_type or 'regular', ''),
                'currency': config.currency_id.name or '',
                'state': config.state,
                'company': config.company_id.name or '',
                'has_payslips': self._has_payslips(config),
            },
            'blueprint': {
                'id': blueprint.id,
                'state': blueprint.state,
                'step': blueprint.step,
                'template_key': blueprint.template_key or 'blank',
                'template_name': blueprint.template_name or '',
                'effective_from': blueprint.effective_from and str(
                    blueprint.effective_from) or '',
                'situations': blueprint.situations(),
                'optional_status': blueprint.optional_status(),
                'revision': blueprint.revision,
                'ui': blueprint.ui(),
                'owner': blueprint.create_uid.name or '',
                'write_date': blueprint.write_date and str(blueprint.write_date) or '',
            },
            'counts': {
                'components': len(rules),
                'formulas': by_type.get('formula', 0),
                'inputs': by_type.get('input', 0),
                'constants': by_type.get('constant', 0),
                'samples': len(config.sample_data_ids),
            },
            'components': components,
            'samples': self._sample_rows(config),
            'starters': starters,
        }

    def _sample_rows(self, config):
        rows = []
        for sample in config.sample_data_ids:
            rows.append({
                'id': sample.id,
                'name': sample.name or _("Sample"),
                'subtitle': self._sample_subtitle(config, sample),
            })
        return rows

    def _sample_subtitle(self, config, sample):
        """"Basic 30,000,000 · 1 dependant" — what this sample actually says."""
        try:
            values = json.loads(sample.input_values_json or '{}')
        except (TypeError, ValueError):
            return ''
        if not values:
            return _("No inputs yet")
        names = {r.code: (r.name or r.code) for r in config.rule_ids if r.code}
        bits = []
        for code, value in list(values.items())[:12]:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if not number:
                continue
            label = names.get(code, code)
            bits.append('%s %s' % (label, self._group(number)))
            if len(bits) == 3:
                break
        return ' · '.join(bits) or _("No amounts yet")

    @api.model
    def _group(self, number):
        if float(number).is_integer():
            return '{:,}'.format(int(number))
        return '{:,.2f}'.format(float(number))

    # ==================================================================
    # Saving
    # ==================================================================
    @api.model
    def bp_save(self, config_id, patch, revision=None):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        patch = patch or {}
        if revision is not None and int(revision) != blueprint.revision:
            return {'ok': False, 'conflict': True, 'reason': _(
                "Someone else changed this draft. Reload to see their version.")}

        bp_vals, cfg_vals = {}, {}
        if 'name' in patch:
            name = (patch.get('name') or '').strip()
            if not name:
                return {'ok': False, 'reason': _("A configuration needs a name.")}
            cfg_vals['name'] = name
        if 'cycle_type' in patch:
            cycle = patch.get('cycle_type')
            if cycle in dict(config._fields['cycle_type'].selection):
                cfg_vals['cycle_type'] = cycle
        if 'effective_from' in patch:
            bp_vals['effective_from'] = patch.get('effective_from') or False
        if 'situations' in patch:
            bp_vals['situations_json'] = json.dumps(patch.get('situations') or {})
        if 'step' in patch:
            bp_vals['step'] = patch.get('step')

        try:
            if cfg_vals:
                config.write(cfg_vals)
            bp_vals['revision'] = blueprint.revision + 1
            blueprint.write(bp_vals)
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        return {
            'ok': True,
            'revision': blueprint.revision,
            'name': config.name,
            'code': config.code or '',
            'cycle_label': CYCLE_LABELS.get(config.cycle_type or 'regular', ''),
        }

    @api.model
    def bp_close(self, config_id, step=None):
        """Remember which step to come back to. Silent, cheap, called often."""
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        if step:
            blueprint.step = step
        return {'ok': True, 'step': blueprint.step}

    # ==================================================================
    # The pay panel
    # ==================================================================
    @api.model
    def bp_preview(self, config_id, sample_id=None):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        samples = config.sample_data_ids
        if not samples:
            return {'ok': False, 'empty': True, 'reason': _(
                "This configuration has no sample employee yet.")}

        chosen = samples.filtered(lambda s: s.id == int(sample_id or 0))[:1]
        # No sample asked for — this is the panel's FIRST paint, and it decides
        # whether the whole journey looks like it works. A rule pack's
        # certification suite leads with its boundary cases (the Vietnam pack's
        # first is "Zero income"), so `samples[0]` opened the hero on a column
        # of zeroes. Try each sample in order and stop at the first one who is
        # actually PAID; the boundary cases stay one press away under "Try a
        # different situation".
        candidates = chosen or samples[:6]
        result = fallback = None
        for candidate in candidates:
            try:
                computed = self._evaluate(config, candidate)
            except AccessError:
                raise
            except Exception as exc:
                return {'ok': False, 'reason': _(
                    "The numbers could not be worked out: %s", self._plain(exc))}
            if computed is None:
                return {'ok': False, 'reason': _(
                    "The numbers could not be worked out from this sample. Check "
                    "the components for a formula the engine cannot read.")}
            fallback = fallback or (candidate, computed)
            if computed[1]['value']:
                result = (candidate, computed)
                break
        sample, (values, take_home, lines, path) = result or fallback
        currency = config.currency_id
        return {
            'ok': True,
            'sample_id': sample.id,
            'sample': {
                'id': sample.id,
                'name': sample.name or _("Sample"),
                'subtitle': self._sample_subtitle(config, sample),
            },
            'take_home': take_home,
            'lines': lines,
            'path': path,
            'currency': {
                'symbol': currency.symbol or currency.name or '',
                'code': currency.name or '',
                'decimals': currency.decimal_places if currency else 2,
            },
        }

    def _evaluate(self, config, sample):
        """Run one sample through the engine and shape the panel's five numbers.

        Returns `(values_by_code, take_home, lines, path)`, or None when the
        engine produced nothing for a configuration that does have components —
        which means a formula it cannot read, not an empty configuration.
        """
        result = self.env['pb.formula.studio'].compute_preview(config.id, sample.id)
        by_letter = result.get('values') or {}
        if not by_letter and config.rule_ids:
            return None
        values = {}
        for rule in config.rule_ids:
            if rule.code and rule.column_letter in by_letter:
                values[rule.code] = by_letter[rule.column_letter]
        lines, take_home, path = self._pay_lines(config, values)
        return values, take_home, lines, path

    def _pay_lines(self, config, values):
        """The five numbers on the pay panel, and how we found them.

        Codes first, because a configuration that uses the usual names has ONE
        component that is exactly the answer, and a sum of parts could double
        count a subtotal. Where a code is missing we ask the engine's own
        net-pay classification instead, so an imported workbook with its own
        naming still gets labelled lines rather than dashes.
        """
        rules = config.rule_ids
        has_roles = any(r.net_role for r in rules) if 'net_role' in rules._fields else False
        used = set()

        def by_code(key):
            code = FALLBACK_CODES[key]
            if code in values:
                used.add('code')
                return values[code], code
            return None, ''

        def by_role(key):
            role = ROLE_FOR_LINE.get(key)
            if not has_roles or not role:
                return None, ''
            picked = rules.filtered(
                lambda r: r.net_role == role and not r.net_role_detail and r.code)
            if not picked:
                return None, ''
            used.add('net_role')
            if role == 'net':
                rule = picked[0]
                return values.get(rule.code), rule.code
            total = sum(values.get(r.code, 0.0) for r in picked)
            return total, ', '.join(picked.mapped('code')[:4])

        def resolve(key):
            value, code = by_code(key)
            if value is None:
                value, code = by_role(key)
            return value, code

        th_value, th_code = resolve('take_home')
        take_home = {'value': th_value, 'code': th_code}

        lines = []
        for key in ('cash', 'deductions', 'tax', 'employer'):
            value, code = resolve(key)
            lines.append({
                'key': key,
                'label': LINE_LABELS[key],
                'value': value,
                'code': code,
            })
        path = '+'.join(sorted(used)) or 'none'
        return lines, take_home, path

    @api.model
    def bp_sample_inputs(self, config_id, sample_id):
        """The editable inputs behind the pay panel's "Adjust sample inputs"."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        sample = config.sample_data_ids.filtered(
            lambda s: s.id == int(sample_id or 0))[:1]
        if not sample:
            return {'ok': False, 'reason': _("That sample no longer exists.")}
        try:
            stored = json.loads(sample.input_values_json or '{}')
        except (TypeError, ValueError):
            stored = {}
        rows = []
        for rule in config.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
            if rule.column_type != 'input' or not rule.code:
                continue
            rows.append({
                'code': rule.code,
                'name': rule.name or rule.code,
                'value': stored.get(rule.code, rule.default_value or 0.0),
            })
        return {'ok': True, 'sample_id': sample.id,
                'name': sample.name or '', 'rows': rows}

    @api.model
    def bp_save_sample_inputs(self, config_id, sample_id, inputs):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        sample = config.sample_data_ids.filtered(
            lambda s: s.id == int(sample_id or 0))[:1]
        if not sample:
            return {'ok': False, 'reason': _("That sample no longer exists.")}
        try:
            self.env['pb.formula.studio'].save_sample_inputs(sample.id, inputs or {})
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        return {'ok': True, 'sample_id': sample.id,
                'samples': self._sample_rows(config)}

    @api.model
    def bp_add_sample(self, config_id):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        try:
            if config.sample_data_ids:
                result = self.env['pb.formula.studio'].add_manual_sample(config.id)
                sample_id = result.get('sample_id')
                self._stamp_origin(
                    self.env['hr.formula.sample.data'].browse(sample_id or 0),
                    'yours')
            else:
                sample_id = self._ensure_sample(config).id
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        if not sample_id:
            return {'ok': False, 'reason': _("The sample could not be added.")}
        return {'ok': True, 'sample_id': sample_id,
                'samples': self._sample_rows(config)}

    # ==================================================================
    # Changing the starting point
    # ==================================================================
    @api.model
    def bp_restart(self, config_id, template_key):
        """Throw away the draft's components and seed a different starter."""
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        if config.state != 'draft':
            return {'ok': False, 'reason': _(
                "This configuration is no longer a draft, so its components "
                "cannot be replaced. Make a copy and start again there.")}
        if self._has_payslips(config):
            return {'ok': False, 'reason': _(
                "This configuration has already produced payslips, so its "
                "components cannot be replaced.")}

        seed_key = 'blank' if template_key in ('blank', 'excel') else template_key
        tpl = None
        if seed_key != 'blank':
            tpl = self.env['hr.formula.config.template'].sudo().search([
                ('code', '=', seed_key), ('state', '!=', 'superseded')], limit=1)
            if not tpl:
                return {'ok': False, 'reason': _(
                    "That starting point is no longer available.")}
        try:
            with self.env.cr.savepoint():
                config.rule_ids.unlink()
                config.rate_table_ids.unlink()
                config.sample_data_ids.unlink()
                if 'col_letter_hwm' in config._fields:
                    config.col_letter_hwm = 0
                if tpl:
                    try:
                        tpl.seed_config(config)
                    except (UserError, ValidationError) as exc:
                        raise UserError(_(
                            "“%(starter)s” could not be added: %(why)s",
                            starter=tpl.name, why=self._plain(exc))) from exc
                    self._stamp_origin(config.sample_data_ids, 'starter')
                self._ensure_sample(config)
                self._classify(config)
                blueprint.write({
                    'template_key': template_key,
                    'template_name': tpl.name if tpl else (
                        _("Import Excel workbook") if template_key == 'excel'
                        else _("Blank canvas")),
                    'revision': blueprint.revision + 1,
                })
                self._backfill_essentials(config, blueprint)
        except AccessError:
            raise
        except Exception as exc:
            _logger.warning("Guided setup: restart failed: %s", exc, exc_info=True)
            return {'ok': False, 'reason': self._plain(exc)}
        return {'ok': True, 'rule_count': len(config.rule_ids)}

    # ==================================================================
    # Finishing and discarding
    # ==================================================================
    @api.model
    def bp_finish(self, config_id):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        if blueprint.state == 'finished':
            return {'ok': True, 'config_id': config.id, 'already': True}
        try:
            config.action_validate_formulas()
        except AccessError:
            raise
        except Exception as exc:
            _logger.info("Guided setup: validation raised: %s", exc)
        config.invalidate_recordset(['has_errors', 'has_circular_refs'])
        if config.has_circular_refs:
            return {'ok': False, 'reason': _(
                "Two components depend on each other, so no number can be "
                "worked out. Open the components grid and break the loop.")}
        # "The engine cannot read this" is `python_formula` being empty after
        # regeneration — the conversion the engine actually executes, and the
        # exact test `hr.formula.config.template.seed_config` uses to refuse a
        # bad starter (`formula_config_template.py:308-315`).
        #
        # Deliberately NOT `has_errors`. That flag is `any(not rule.is_valid)`,
        # and `is_valid` is a STATIC lint whose function list does not include
        # the engine's own `BRACKET(...)` — the progressive-tax primitive the
        # whole Vietnam rule pack is built on. Every configuration seeded from
        # that pack therefore reports an error for a formula that computes
        # perfectly (measured: PIT 14,896,200 on the 90m sample while the same
        # rule was flagged "Unsupported function: BRACKET"). Gating Finish on it
        # made the journey's own default starter impossible to finish.
        # Widening the validator's function list is an engine change with a
        # blast radius across every configuration on every database; it is
        # logged for B2, not smuggled in here.
        unreadable = config.rule_ids.filtered(
            lambda r: r.column_type == 'formula' and r.excel_formula
            and not r.python_formula)
        if unreadable:
            names = ', '.join(unreadable.mapped('code')[:5])
            return {'ok': False, 'reason': _(
                "The engine cannot read the formula on %(names)s. Open the "
                "components grid to fix it, then finish.", names=names)}
        blueprint.write({'state': 'finished', 'step': 'finish',
                         'revision': blueprint.revision + 1})
        return {'ok': True, 'config_id': config.id, 'already': False}

    @api.model
    def bp_discard(self, config_id):
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        if blueprint.state != 'draft':
            return {'ok': False, 'reason': _(
                "This setup is already complete, so there is nothing to "
                "discard. Open the configuration and archive it instead.")}
        if self._has_payslips(config):
            return {'ok': False, 'reason': _(
                "This configuration has already produced payslips, so it "
                "cannot be discarded. Archive it instead.")}
        try:
            config.unlink()
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        return {'ok': True}

    # ==================================================================
    # Doors
    # ==================================================================
    @api.model
    def bp_studio_action(self, config_id):
        """The escape hatch into the components grid, as an action dict."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        action = self.env.ref('pb_formula_studio.action_pb_formula_studio',
                              raise_if_not_found=False)
        if not action:
            return {'ok': False, 'reason': _(
                "The components grid is not available on this database.")}
        signal = {'config_id': config.id}
        return {
            'ok': True,
            'action': {
                'type': 'ir.actions.client',
                'tag': action.tag,
                'name': action.name,
                'target': 'current',
                'params': dict(signal),
                'context': dict(signal),
            },
        }

    @api.model
    def bp_steps(self):
        """The step keys, so a client never has to hard-code the order twice."""
        return {'ok': True, 'steps': list(STEPS)}
