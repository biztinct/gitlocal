# -*- coding: utf-8 -*-
"""F113 — Country Starter Templates.

A *starter template* is a maintained, versioned description of a country payroll
**structure**: which components exist, their formulas, categories, payslip
sections, rate (bracket) tables, and a certification test suite. Creating a
configuration from a template materialises that structure into real
``hr.formula.rule`` rows (with frozen column letters, per F111) plus
``hr.formula.rate.table`` rows and ``hr.formula.sample.data`` test rows.

Reconciliation with B4 (design appendix A0 — A0 wins over the Part-I draft):

* A template carries **structure only**. Statutory *values* have ONE source of
  truth: the B4 ``hr.formula.legislation.pack``. A component in
  ``components_json`` may tag a constant with ``"legislation_code": "DEDUCTSELF"``;
  at seed time the seeder resolves that value from the country's **current
  published** legislation pack (highest version whose ``effective_date`` is on or
  before today). A template never hard-codes a rate a pack owns.
* Consequence: a rate change ships once (a new B4 pack version) and serves both
  existing configs (B4 apply) and future configs (template seeding). A template's
  own ``version`` bumps only on a *structural* change.
* A template's sample tests pin the pack version they were computed against
  (``"pack_version"`` in ``sample_tests_json``); the certification harness resolves
  legislation values from that exact pack version so the suite stays reproducible
  even after a newer pack publishes.

Converter contract (design D113.4): every component/rate-table code must be
underscore-free AND no code may be a substring of another (the Excel→Python
converter mangles violators to 0). Enforced as a model constraint so a bad
template fails at authoring time, never at a client's payroll run.
"""
import json
import logging
import re
from datetime import date as _date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..formula_engine.comparison import coerce_number

_logger = logging.getLogger(__name__)

# Same identifier shape the studio enforces on rename/add-component — one
# contract, two enforcement points, identical rule.
_CODE_RE = re.compile(r'^[A-Z][A-Z0-9]*$')

# Mirror hr.formula.config / hr.formula.legislation.pack country vocabulary.
_COUNTRY = [
    ('VN', 'Vietnam'), ('ID', 'Indonesia'), ('IN', 'India'), ('SG', 'Singapore'),
    ('MY', 'Malaysia'), ('TH', 'Thailand'), ('KH', 'Cambodia'), ('PH', 'Philippines'),
]


class HrFormulaConfigTemplate(models.Model):
    _name = 'hr.formula.config.template'
    _description = 'Country Payroll Starter Template'
    _order = 'country_code, sequence, effective_date desc, id desc'

    code = fields.Char(
        required=True, index=True,
        help="Unique per version, e.g. 'vn_standard_2026'. Referenced by the "
             "studio create-from-template wizard.")
    name = fields.Char(required=True)
    country_code = fields.Selection(_COUNTRY, string='Country', required=True, index=True)
    flag = fields.Char(help="Emoji/short flag glyph for the studio picker.")
    description = fields.Text()
    version = fields.Char(required=True, default='1.0',
                          help="Structural version, e.g. '2026.1'. Bumps on a "
                               "structure change, NOT on a statutory rate change "
                               "(rates live in B4 packs).")
    effective_date = fields.Date(
        string='Effective from', index=True,
        help="The period this structure targets. Governs which legislation-pack "
             "version the seeder resolves values from when no pin is given.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('certified', 'Certified'),
        ('superseded', 'Superseded'),
    ], default='draft', required=True, index=True,
        help="Certified = a country reviewer signed off the structure AND every "
             "⚠ VERIFY statutory item. The install-time harness proving its own "
             "sample tests is necessary but not sufficient for certification.")

    # ------------------------------------------------------------------
    # JSON payloads (the portable, data-module-friendly template body)
    # ------------------------------------------------------------------
    components_json = fields.Text(
        string='Components (JSON)', default='[]',
        help="[{code, name, type: input|formula|constant, category, "
             "excel_formula, constant_value, legislation_code, appears_on_payslip, "
             "number_format, column_letter, payslip_section}]")
    rate_tables_json = fields.Text(
        string='Rate tables (JSON)', default='[]',
        help="[{code, name, brackets: [{lower, rate}], note, legislation_ref}]")
    sample_tests_json = fields.Text(
        string='Sample tests (JSON)', default='[]',
        help="[{name, pack_version, inputs: {code: value}, expected: {code: value}, tol}]"
             " — the certification suite. Expected values are HARNESS-GENERATED "
             "and externally cross-checked, never hand-typed.")
    legislation_refs_json = fields.Text(
        string='Legislation refs (JSON)', default='[]',
        help="[{ref, title, url, effective_date}] — shown in the picker preview.")

    supersedes_id = fields.Many2one(
        'hr.formula.config.template', string='Supersedes',
        ondelete='set null',
        help="The template version this one replaces (structural change).")

    sequence = fields.Integer(default=10)
    component_count = fields.Integer(compute='_compute_counts')
    test_count = fields.Integer(compute='_compute_counts')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'A template code must be unique.'),
    ]

    # ------------------------------------------------------------------
    # computes
    # ------------------------------------------------------------------
    def _compute_counts(self):
        for t in self:
            t.component_count = len(t._components())
            t.test_count = len(t._sample_tests())

    @api.depends('name', 'version')
    def _compute_display_name(self):
        for t in self:
            t.display_name = '%s · %s' % (t.name, t.version)

    # ------------------------------------------------------------------
    # JSON accessors (tolerant of empty/None)
    # ------------------------------------------------------------------
    def _components(self):
        self.ensure_one()
        return self._loads(self.components_json)

    def _rate_tables(self):
        self.ensure_one()
        return self._loads(self.rate_tables_json)

    def _sample_tests(self):
        self.ensure_one()
        return self._loads(self.sample_tests_json)

    def _legislation_refs(self):
        self.ensure_one()
        return self._loads(self.legislation_refs_json)

    @staticmethod
    def _loads(blob):
        if not blob:
            return []
        try:
            data = json.loads(blob)
            return data if isinstance(data, list) else []
        except (ValueError, TypeError):
            return []

    # ==================================================================
    # T113.1 / D113.4 — converter-contract constraint
    # ==================================================================
    @api.constrains('components_json', 'rate_tables_json')
    def _check_converter_contract(self):
        """Every component AND rate-table code must be underscore-free and no
        code may be a substring of another. Substring collisions make the
        Excel→Python converter silently rewrite the shorter code inside the
        longer one, yielding 0 — the single worst class of formula bug. Better
        to reject the template here than to ship a config that computes wrong."""
        for t in self:
            codes = []
            for c in t._components():
                code = (c.get('code') or '').strip()
                if code:
                    codes.append(code)
            for rt in t._rate_tables():
                code = (rt.get('code') or '').strip()
                if code:
                    codes.append(code)
            t._assert_codes_convertible(codes)

    @api.model
    def _assert_codes_convertible(self, codes):
        # 1) shape: the studio's exact rename/add-component rule (uppercase
        #    letters + digits, starts with a letter — no underscores, no spaces)
        for code in codes:
            if '_' in code:
                raise ValidationError(_(
                    "Component code '%s' contains an underscore. The Excel→Python "
                    "converter cannot round-trip underscored codes — rename it "
                    "(e.g. 'SI_EMP' → 'SIEMP').") % code)
            if not _CODE_RE.match(code):
                raise ValidationError(_(
                    "Component code '%s' must be uppercase letters and digits only, "
                    "starting with a letter (no spaces).") % code)
        # 2) no code a substring of another (case-insensitive — the converter is)
        upper = [c.upper() for c in codes]
        for i, a in enumerate(upper):
            for j, b in enumerate(upper):
                if i != j and a in b:
                    raise ValidationError(_(
                        "Component code '%s' is a substring of '%s'. The converter "
                        "would rewrite the shorter code inside the longer one and "
                        "compute 0. Rename one so neither contains the other.")
                        % (codes[i], codes[j]))

    # ==================================================================
    # T113.3 — seeder v2
    # ==================================================================
    def seed_config(self, config, pack_version=None):
        """Materialise this template's structure into ``config`` (an empty
        ``hr.formula.config``). Idempotent-guarded by the caller (config must be
        empty). Returns the config.

        Steps, in order:
          1. rate tables (so BRACKET(...) references resolve during seeding),
          2. components → hr.formula.rule rows (frozen letters per F111,
             categories resolved by code, constants' values resolved from the
             B4 legislation pack when tagged),
          3. formula regeneration,
          4. sample tests → hr.formula.sample.data rows.

        ``pack_version`` pins the legislation-pack version for value resolution
        (used by the certification harness for reproducibility); when None the
        seeder uses the *current published* pack (real create-from-template).
        """
        self.ensure_one()
        Rule = self.env['hr.formula.rule']
        RateTable = self.env['hr.formula.rate.table']
        Bracket = self.env['hr.formula.rate.bracket']

        # -- 0. the config must carry the template's country ---------------
        # (currency mapping, employee→config matching and B4 pack targeting
        # are all keyed off config.country_code — a wizard default must never
        # leave an SG structure labelled VN)
        if self.country_code and config.country_code != self.country_code:
            config.country_code = self.country_code

        # -- 1. rate tables ------------------------------------------------
        for rt in self._rate_tables():
            table = RateTable.create({
                'config_id': config.id,
                'code': rt.get('code'),
                'name': rt.get('name') or rt.get('code') or _('Rate Table'),
                'note': rt.get('note') or False,
            })
            brackets = rt.get('brackets') or []
            Bracket.create([{
                'table_id': table.id,
                'lower': float(b.get('lower') or 0.0),
                'rate': float(b.get('rate') or 0.0),
            } for b in brackets])

        # -- 2. components -> rules ---------------------------------------
        # Resolve legislation values ONCE per (country, pack_version).
        legis = self._resolve_legislation_map(self.country_code, pack_version)
        cat_cache = {}
        vals_list = []
        for i, comp in enumerate(self._components()):
            ctype = comp.get('type') or 'formula'
            code = comp.get('code')
            const = float(comp.get('constant_value') or 0.0)
            legis_code = comp.get('legislation_code')
            if ctype == 'constant' and legis_code:
                # Value owned by the B4 pack — the template's constant_value is
                # documentation only. A resolution miss must FAIL, never fall
                # back: a placeholder silently becomes a statutory rate.
                if legis_code not in legis:
                    raise ValidationError(_(
                        "Template '%s': constant %s requires legislation code %s "
                        "but no published %s legislation pack carries it%s. "
                        "Publish the statutory pack before creating a "
                        "configuration from this template.") % (
                        self.code, code, legis_code, self.country_code,
                        pack_version and _(" (pinned version %s)") % pack_version or ''))
                const = legis[legis_code]
            vals = {
                'config_id': config.id,
                'code': code,
                'name': comp.get('name') or code,
                'column_type': ctype,
                'excel_formula': comp.get('excel_formula') or '',
                'constant_value': const,
                'default_value': float(comp.get('default_value') or 0.0),
                'number_format': comp.get('number_format') or 'currency',
                'appears_on_payslip': bool(comp.get('appears_on_payslip', True)),
                'sequence': (i + 1) * 10,
            }
            # F111: hand the letter explicitly so create() freezes it and the
            # config's high-water mark advances (identical mechanism the studio
            # seam already uses). Explicit letter preferred; else create() mints.
            if comp.get('column_letter'):
                vals['column_letter'] = comp['column_letter']
            cat_id = self._resolve_category(comp.get('category'), cat_cache)
            if cat_id:
                vals['category_id'] = cat_id
            vals_list.append(vals)
        Rule.create(vals_list)

        # -- 3. formula regeneration (Excel -> Python) --------------------
        # action_regenerate_formulas collects per-rule conversion errors into
        # its returned notification instead of raising — check the rules
        # themselves: a formula that failed to convert must FAIL the seed, not
        # ship a component that silently computes 0 on payslips.
        config.action_regenerate_formulas()
        broken = config.rule_ids.filtered(
            lambda r: r.column_type == 'formula' and r.excel_formula
            and not r.python_formula)
        if broken:
            raise ValidationError(_(
                "Template '%s': %d formula(s) failed Excel→Python conversion: %s")
                % (self.code, len(broken), ', '.join(broken.mapped('code'))))

        # -- 4. sample tests ----------------------------------------------
        self._seed_sample_tests(config)
        return config

    def _seed_sample_tests(self, config):
        """Import the certification suite as hr.formula.sample.data rows so the
        tests are visible AND assertable in the Test workbench — expected
        values go into ``expected_values_json``, the field the workbench's
        pass/fail comparison actually reads."""
        self.ensure_one()
        Sample = self.env['hr.formula.sample.data']
        vals_list = []
        for i, test in enumerate(self._sample_tests()):
            vals_list.append({
                'config_id': config.id,
                'name': test.get('name') or (_('Test %d') % (i + 1)),
                'description': _('Certification test (template %s v%s)') % (
                    self.code, self.version),
                'input_values_json': json.dumps(test.get('inputs') or {}),
                'expected_values_json': json.dumps(test.get('expected') or {}),
                'sequence': (i + 1) * 10,
            })
        if vals_list:
            Sample.create(vals_list)

    # ------------------------------------------------------------------
    # category resolution (by code; create-on-miss with a sane name)
    # ------------------------------------------------------------------
    _CATEGORY_NAMES = {
        'BASIC': 'Basic', 'ALW': 'Allowance', 'ALLOW': 'Allowance',
        'GROSS': 'Gross', 'DED': 'Deduction', 'COMP': 'Company Contribution',
        'NET': 'Net', 'TAX': 'Tax', 'INPUT': 'Inputs', 'OT': 'Overtime',
    }

    @api.model
    def _resolve_category(self, cat_code, cache=None):
        if not cat_code:
            return False
        if cache is not None and cat_code in cache:
            return cache[cat_code]
        Cat = self.env['hr.salary.rule.category']
        cat = Cat.search([('code', '=', cat_code)], limit=1)
        if not cat:
            cat = Cat.create({
                'code': cat_code,
                'name': self._CATEGORY_NAMES.get(cat_code.upper(), cat_code.title()),
            })
        if cache is not None:
            cache[cat_code] = cat.id
        return cat.id

    # ==================================================================
    # A0 — B4 legislation-pack value resolution
    # ==================================================================
    @api.model
    def _resolve_legislation_map(self, country_code, pack_version=None):
        """Build ``{legislation_code: value}`` for a country.

        Without a pin: merge every **published** pack for the country whose
        ``effective_date`` is on or before today, newest-effective winning per
        code (so the 2026 relief pack overrides the 2025 baseline for the two
        codes it carries, and everything else falls back to 2025).

        With ``pack_version`` pinned (certification harness): use exactly the
        pack(s) at that version — regardless of state — merged over the newest
        published baseline so a thin override pack (e.g. relief-only) still
        resolves the full statutory set. This keeps a pinned suite reproducible
        even after newer packs publish.
        """
        Pack = self.env['hr.formula.legislation.pack'].sudo()
        today = fields.Date.context_today(self)

        base_domain = [('country_code', '=', country_code)]
        published = Pack.search(base_domain + [
            ('state', '=', 'published'),
            '|', ('effective_date', '=', False), ('effective_date', '<=', today),
        ])

        result = {}

        # newest-effective wins → apply oldest first. Sort in Python: SQL ASC
        # puts NULL effective_date LAST (it would override every dated pack);
        # an undated pack is a baseline and must apply FIRST.
        def _sorted(packs):
            return packs.sorted(
                key=lambda p: (p.effective_date or _date.min, p.sequence, p.id))

        def _apply(packs):
            for p in _sorted(packs):
                for it in p.item_ids:
                    if it.code:
                        result[it.code] = it.value

        _apply(published)

        if pack_version:
            pinned = Pack.search(base_domain + [('version', '=', pack_version)])
            _apply(pinned)
        return result

    # ==================================================================
    # T113.4 — certification harness (shared helper for post_init_hook)
    # ==================================================================
    def run_certification(self, raise_on_fail=True):
        """Create a throwaway config from this template, run every sample test
        through the VALIDATED evaluator (``hr.formula.sample.data.
        _evaluate_rules_with_dependencies`` — never ``evaluate_all``, per the
        converter contract), assert all pass, then delete the config.

        Returns a report dict:
          {template, passed: bool, total, failed: [{name, code, expected,
           got, diff}], log: [str]}

        On failure with ``raise_on_fail`` (the install path) raises so the pack
        module install is blocked (D113.3). Runs in a savepoint so the throwaway
        config never persists, pass or fail.
        """
        self.ensure_one()
        report = {'template': self.code, 'passed': True, 'total': 0,
                  'failed': [], 'log': []}
        Config = self.env['hr.formula.config'].sudo()
        # Honour the suite's pack_version pin (A0 reproducibility): the tests
        # were computed against one pack version — seed the throwaway config
        # from exactly that version so a newer published pack can never turn
        # a healthy pack install into a spurious certification failure.
        pins = sorted({t.get('pack_version')
                       for t in self._sample_tests() if t.get('pack_version')})
        pin = pins[0] if pins else None
        if len(pins) > 1:
            _logger.warning(
                "F113: template %s mixes pack_version pins %s — certifying "
                "against %s", self.code, pins, pin)
        cfg = None
        try:
            # savepoint so nothing this method writes ever survives
            with self.env.cr.savepoint():
                cfg = Config.create({
                    'name': 'CERT %s %s' % (self.code, self.version),
                    'country_code': self.country_code,
                    'state': 'draft',
                })
                self.seed_config(cfg, pack_version=pin)
                report.update(self._run_suite(cfg))
                # always roll the savepoint back — never persist the throwaway
                raise _CertRollback()
        except _CertRollback:
            pass
        except Exception as e:
            report['passed'] = False
            report['log'].append('harness error: %s' % e)
            _logger.exception("F113 certification harness crashed for %s", self.code)

        if not report['passed'] and raise_on_fail:
            names = ', '.join('%s[%s] exp %s got %s' % (
                f['name'], f['code'], f['expected'], f['got'])
                for f in report['failed']) or (report['log'][-1] if report['log'] else '?')
            raise ValidationError(_(
                "Country pack '%s' failed certification — install blocked.\n"
                "Failing tests: %s") % (self.code, names))
        return report

    def _run_suite(self, config):
        """Run this template's sample tests against ``config``. Legislation
        values were materialised into constant rules at seed time, resolved at
        the suite's pinned ``pack_version`` (run_certification passes the pin
        into seed_config; mixed pins in one suite are warned and certified at
        the first pin — no shipped pack mixes them)."""
        self.ensure_one()
        Sample = self.env['hr.formula.sample.data']
        # one reusable throwaway sample bound to the config
        probe = Sample.create({
            'config_id': config.id, 'name': 'cert-probe',
            'input_values_json': '{}',
        })
        out = {'passed': True, 'total': 0, 'failed': [], 'log': []}
        for test in self._sample_tests():
            out['total'] += 1
            inputs = {k: float(v) for k, v in (test.get('inputs') or {}).items()}
            expected = test.get('expected') or {}
            tol = float(test.get('tol') or 1.0)  # ₫1 default tolerance
            results = probe._evaluate_rules_with_dependencies(inputs)
            for code, exp in expected.items():
                got_f = coerce_number(results.get(code, 0.0)) or 0.0
                if abs(got_f - float(exp)) > tol:
                    out['passed'] = False
                    out['failed'].append({
                        'name': test.get('name') or '?', 'code': code,
                        'expected': float(exp), 'got': round(got_f, 4),
                        'diff': round(got_f - float(exp), 4),
                    })
            out['log'].append('%s: %s inputs -> %d checks' % (
                test.get('name'), len(inputs), len(expected)))
        return out

    # ==================================================================
    # T113.8 — version diff report
    # ==================================================================
    def compare_template_versions(self, other):
        """Structural diff self→other (both hr.formula.config.template). Returns
        {added, removed, changed: [{code, field, from, to}], rate_tables:
        {added, removed, changed}, refs}. Used to show a consultant what a new
        template version changes before they apply it to a live config (never
        a silent auto-update — D113.5). A bracket/rate change is exactly the
        kind of update this exists for, so rate tables diff too."""
        self.ensure_one()
        if isinstance(other, int):
            other = self.browse(other)
        other.ensure_one()
        a = {c.get('code'): c for c in self._components() if c.get('code')}
        b = {c.get('code'): c for c in other._components() if c.get('code')}
        added = [b[k] for k in b if k not in a]
        removed = [a[k] for k in a if k not in b]
        changed = []
        for k in a:
            if k not in b:
                continue
            for field in ('excel_formula', 'constant_value', 'type',
                          'category', 'legislation_code'):
                av, bv = a[k].get(field), b[k].get(field)
                if av != bv:
                    changed.append({'code': k, 'field': field,
                                    'from': av, 'to': bv})
        ra = {rt.get('code'): rt for rt in self._rate_tables() if rt.get('code')}
        rb = {rt.get('code'): rt for rt in other._rate_tables() if rt.get('code')}
        rt_changed = [
            {'code': k, 'field': 'brackets',
             'from': ra[k].get('brackets') or [],
             'to': rb[k].get('brackets') or []}
            for k in ra if k in rb
            and (ra[k].get('brackets') or []) != (rb[k].get('brackets') or [])]
        return {
            'from': {'code': self.code, 'version': self.version},
            'to': {'code': other.code, 'version': other.version},
            'added': added, 'removed': removed, 'changed': changed,
            'rate_tables': {
                'added': [rb[k] for k in rb if k not in ra],
                'removed': [ra[k] for k in ra if k not in rb],
                'changed': rt_changed,
            },
            'refs': other._legislation_refs(),
        }


class _CertRollback(Exception):
    """Sentinel to unwind the certification savepoint without persisting."""
    pass
