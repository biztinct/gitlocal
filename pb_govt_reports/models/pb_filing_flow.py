# -*- coding: utf-8 -*-
"""The filing flow — a facade over the country filing wizards.

IA Cycle 4, flow doctrine card 1: the product's worst screen dies. Generating a
statutory filing used to mean a `target: "new"` modal carrying THIRTY fields, of
which between three and twelve mattered depending on which report you had
picked, and the other twenty-odd sat there empty because Odoo's `invisible=`
groups are the only progressive disclosure a stock form has. This model is what
replaced the modal's server side; `filing_flow.js` is the full-screen stepped
surface in front of it.

What it must NOT become is a second implementation of a filing. Every decision
here is still made by the country's own transient wizard — the one that knows
which XLS template to open, which employees are in range and how to fill the
sheet. This model writes its fields from an ALLOW-LIST, presses its ONE generate
button, and materialises what that button chose. Same discard-and-re-read shape
as `pb.integration.onboarding` (C3), for the same reason: a fix to a wizard
reaches this flow without anybody remembering that this flow exists.

Four things it does deliberately differently from the modal:

  * **it is generate-only, by construction.** The adapter names exactly one
    method per country and that name is a CONSTANT in this file, never anything
    the browser sends. The VN wizard also carries `action_mail_report`; this
    facade has no expression that could reach it, and `_ONLY_GENERATE` plus a
    test assert the whole registry against a send/submit vocabulary. A flow that
    could file something with an authority by accident is not a flow anybody
    should build.
  * **it asks for what the chosen filing needs, and nothing else.** The field
    descriptor is built from the wizard's OWN `_fields` — labels, types,
    selection values and defaults all come from the model, so a wizard that
    grows a parameter grows it here too, and a label is never restated in two
    places.
  * **it materialises the artifact.** The wizard's generate button returns an
    `ir.actions.report` for the client to download; the flow renders it here,
    stores it as an `ir.attachment` owned by the caller, and hands back a name,
    a byte count and a URL. That is what makes "did it work" answerable without
    a download dialog, and it is what the tests assert against.
  * **it says when a country's wizard produces no file.** Four of the five
    country wizards return a notification saying the submission file was
    "generated successfully" and write nothing at all. The flow reports what
    actually happened — `artifacts: []` and the wizard's own message — rather
    than repeating a claim that is not true (W42: a control that lies about what
    it does is the kind of lie nobody discovers).

Rights: the caller's own, throughout. No sudo anywhere in this file. Every write
goes through the wizard as the real user, and the ORM refuses what it would have
refused through the modal.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# The ONLY method names this facade is allowed to press, per country. They are
# constants here and are never taken from the payload: `getattr(wizard, name)`
# with a name off the wire is a remote-method-call primitive, and a wizard has
# `unlink` on it like every other record.
_GENERATE = {
    'VN': 'action_export',
    'SG': 'action_generate_cpf_file',
    'TH': 'action_generate_ssf_file',
    'KH': 'action_generate_nssf_file',
    'MY': 'action_generate_epf_file',
}

# A defence in depth over the table above, asserted in the tests as well: no
# adapter may ever name a method that sounds like it leaves the building.
_ONLY_GENERATE = ('mail', 'send', 'submit', 'post', 'transmit', 'email', 'sign')

# Per country: the wizard model, the field that carries WHICH filing, the field
# holding the period, and the writable field set. An allow-list, not a
# deny-list — these transients carry computed result fields (`total_employees`,
# `total_cpf_employee`) that a forged call could otherwise use to write a
# plausible outcome onto a step that never ran.
ADAPTERS = {
    'VN': {
        'model': 'pb.govt.report.wizard',
        'key_field': 'report_type',
        'period': 'range',                       # date_from + date_to
        'common': ['company_id', 'date_from', 'date_to',
                   'department_id', 'contract_type_id', 'employee_ids'],
        # The five conditional groups of the stock form, verbatim from
        # `pb_hr_govt/views/govt_report_wizard_views.xml` — the whole reason
        # this flow exists is that a form cannot show only these.
        'conditional': {
            'bhxh630': ['bhxh630_benefit_group', 'bhxh630_certificate_serial',
                        'bhxh630_supplement_batch', 'bhxh630_payment_method',
                        'bhxh630_bank_no', 'bhxh630_bank_holder',
                        'bhxh630_bank_code', 'bhxh630_route_code',
                        'bhxh630_long_illness_code'],
            'bhxhdstk01': ['bhxhdstk_contribution_method',
                           'bhxhdstk_change_content', 'bhxhdstk_hospital_code'],
            'bangke_d01': ['d01_doc_name', 'd01_doc_number', 'd01_issue_date',
                           'd01_effective_date', 'd01_agency', 'd01_summary',
                           'd01_appraisal'],
            'giam_ld': ['giam_reason', 'giam_effective_date', 'giam_region_code'],
            'tang_ld': ['tang_reason', 'tang_effective_date', 'tang_region_code'],
        },
    },
    # The other four wizards are the same shape — a name, a period, a country,
    # and a button — so they are adapted through the same facade. They are NOT
    # the same in what they produce, and `generate()` says so: none of them
    # writes a file (see the module docstring).
    'SG': {'model': 'cpf.submission.wizard', 'key_field': None, 'period': 'point',
           'common': ['name', 'submission_period'], 'conditional': {}},
    'TH': {'model': 'social.security.wizard', 'key_field': None, 'period': 'point',
           'common': ['name', 'submission_period'], 'conditional': {}},
    'KH': {'model': 'nssf.wizard', 'key_field': None, 'period': 'point',
           'common': ['name', 'submission_period'], 'conditional': {}},
    'MY': {'model': 'epf.wizard', 'key_field': None, 'period': 'point',
           'common': ['name', 'submission_period'], 'conditional': {}},
}

# Relational fields the flow offers as a bounded picker rather than as a raw id
# box: `{field: (comodel, limit)}`. Anything relational NOT listed here is
# dropped from the descriptor rather than rendered as a number nobody can type.
#
# No ORDER is named on purpose. The first version sorted departments by
# `complete_name`, which is a NON-STORED compute on this build — `_order_to_sql`
# raises for it, so every VN filing's scope step answered with a traceback, and
# it did so for a cosmetic reason. Each model's own `_order` is already the
# right answer and cannot be wrong.
_PICKERS = {
    'company_id': ('res.company', 50),
    'department_id': ('hr.department', 400),
    'contract_type_id': ('hr.contract.type', 100),
}

# `employee_ids` is a many2many over thousands of rows, so it is a TYPEAHEAD
# rather than a list — see `search_employees`.
_TYPEAHEAD = ('employee_ids',)

_MAX_EMPLOYEE_HITS = 20


class PbFilingFlow(models.AbstractModel):
    _name = 'pb.filing.flow'
    _description = 'Statutory filing — stepped flow'

    # ================================================================= catalog
    @api.model
    def _adapter(self, country):
        """The adapter for a country, or a refusal.

        `country` is looked up in ADAPTERS rather than used to index `self.env`:
        a forged country must not be able to point this method at another model
        (the same reasoning as `pb.integrations.get_ledger`'s `kind`).
        """
        spec = ADAPTERS.get((country or '').upper())
        if not spec or spec['model'] not in self.env:
            raise UserError(_("Filings for this country are not available on "
                              "this database."))
        return spec

    @api.model
    def covered_countries(self):
        """Which countries this flow can drive HERE, right now.

        A country whose wizard module is not installed is not covered, and the
        board keeps its modal for it — an offer the server would refuse is worse
        than no offer (W29).
        """
        return sorted(c for c, spec in ADAPTERS.items()
                      if spec['model'] in self.env)

    @api.model
    def start(self, country_code=None):
        """Step 1: which filings exist, for which country, and what period."""
        board = self.env['pb.govt.reports'].get_govt_reports_data(country_code)
        covered = self.covered_countries()
        cc = board['country_code']
        filings = []
        for group in board.get('groups', []):
            for rep in group.get('reports', []):
                filings.append({
                    'key': rep['key'],
                    'label': rep['en'],
                    'native': rep['vi'],
                    'group': group['label'],
                    'icon': group.get('icon') or 'fileText',
                })
        return {
            'company': board['company'],
            'country_code': cc,
            'country_label': board['country_label'],
            'countries': board['countries'],
            'multi_country': board['multi_country'],
            'covered': covered,
            'is_covered': cc in covered,
            'period': board['period'],
            'filings': filings,
        }

    # =================================================================== scope
    @api.model
    def _field_spec(self, Model, name):
        """One field, described from the MODEL — never from a restated label."""
        f = Model._fields.get(name)
        if f is None:
            return None
        spec = {
            'name': name,
            'label': f._description_string(self.env) or name,
            'type': f.type,
            'required': bool(f.required),
            'help': f._description_help(self.env) or '',
        }
        if f.type == 'selection':
            spec['options'] = [{'id': k, 'label': v}
                               for k, v in (f._description_selection(self.env) or [])]
        elif name in _PICKERS:
            comodel, limit = _PICKERS[name]
            if comodel not in self.env:
                return None
            spec['type'] = 'many2one'
            spec['options'] = [
                {'id': r.id, 'label': r.display_name}
                for r in self.env[comodel].search([], limit=limit)
            ]
        elif name in _TYPEAHEAD:
            spec['type'] = 'typeahead'
        elif f.type in ('many2one', 'one2many', 'many2many', 'reference'):
            # A relational field with no picker and no typeahead would render as
            # an id box, which is W29's door that can only produce an error.
            return None
        return spec

    @api.model
    def scope(self, country, filing_key):
        """Step 2: exactly the parameters the chosen filing needs.

        A fresh transient is created here and its id is handed to the client, so
        the wizard's own defaults (`company_id`, the selection defaults, the
        report name) are the ones on screen. Creating a TRANSIENT from what is,
        on the client, a step transition is the same exception W21 allows for
        `pb.integration.onboarding.start`: the record has no side effect outside
        itself and Odoo vacuums it. Nothing is generated until a click.
        """
        spec = self._adapter(country)
        Wiz = self.env[spec['model']]
        vals = {}
        if spec['key_field']:
            vals[spec['key_field']] = filing_key
        if spec['period'] == 'range':
            period = self.env['pb.govt.reports']._default_period(self.env.company)
            vals['date_from'] = period['from']
            vals['date_to'] = period['to']
        w = Wiz.create(vals)

        # Each field says which BLOCK it belongs to, here, once. The client
        # renders two sections from that key; deriving it there from a name
        # prefix would be the same fact in two places, and the second copy is
        # always the one that goes stale.
        fields_ = []
        for name in spec['common']:
            s = self._field_spec(Wiz, name)
            if s:
                fields_.append(dict(s, block='common'))
        for name in spec['conditional'].get(filing_key, []):
            s = self._field_spec(Wiz, name)
            if s:
                fields_.append(dict(s, block='filing'))
        return {
            'wizard_id': w.id,
            'country': (country or '').upper(),
            'filing_key': filing_key,
            'model': spec['model'],
            'period_kind': spec['period'],
            'fields': fields_,
            'values': self._values(w, [f['name'] for f in fields_]),
            # How many of the wizard's fields the chosen filing does NOT need.
            # Said out loud on the step, because "this form is shorter than the
            # old one" is the feature and a number is how you prove it.
            'hidden_count': self._hidden_count(spec, filing_key),
        }

    @api.model
    def _hidden_count(self, spec, filing_key):
        shown = set(spec['common']) | set(spec['conditional'].get(filing_key, []))
        every = set(spec['common'])
        for names in spec['conditional'].values():
            every |= set(names)
        return len(every - shown)

    @api.model
    def _values(self, w, names):
        """The wizard's current values, in a shape a browser can hold."""
        out = {}
        for n in names:
            f = w._fields.get(n)
            if f is None:
                continue
            v = w[n]
            if f.type == 'many2one':
                out[n] = v.id or False
            elif f.type in ('many2many', 'one2many'):
                out[n] = [{'id': r.id, 'label': r.display_name} for r in v]
            elif f.type in ('date', 'datetime'):
                out[n] = fields.Date.to_string(v) if v else ''
            else:
                out[n] = v if v not in (None, False) else (
                    False if f.type == 'boolean' else '')
        return out

    @api.model
    def search_employees(self, term, limit=_MAX_EMPLOYEE_HITS):
        """The typeahead behind `employee_ids`.

        `name_search`'s second parameter is `domain` in Odoo 19; it used to be
        `args`, and calling it by the old name raises a TypeError that a
        surrounding catch would turn into a control that silently deletes itself
        (W40 — that exact bug cost this program its person search for three
        phases). It is spelled positionally here so there is nothing to rename.
        """
        Emp = self.env['hr.employee']
        hits = Emp.name_search(term or '', [], 'ilike', min(int(limit or 0)
                                                            or _MAX_EMPLOYEE_HITS,
                                                            _MAX_EMPLOYEE_HITS))
        return [{'id': i, 'label': n} for i, n in hits]

    # ================================================================ generate
    @api.model
    def _writable(self, spec, filing_key):
        """The fields this filing may write. The FILING KEY is not one of them.

        It used to be, and a test caught why that is wrong: the key decides
        WHICH allow-list applies, so a call that could also change it would let
        a caller validate a scope as one filing and then export another —
        `report_type: 'bhxh630'` written against `tang_ld`'s allow-list. The key
        is set once, by `scope()`, at create time; from then on it is read.
        """
        return set(spec['common']) | set(spec['conditional'].get(filing_key, []))

    @api.model
    def _assert_key(self, spec, w, filing_key):
        """The wizard's stored filing and the one the caller names must agree.

        Belt to `_writable`'s braces: `generate` takes `filing_key` from the
        browser to pick the allow-list, while the WIZARD's own field is what
        `action_export` dispatches on. If those two ever disagreed, the scope
        would be validated for one filing and the file produced for another —
        so they are compared rather than trusted.
        """
        if not spec['key_field']:
            return
        stored = w[spec['key_field']] or ''
        if stored != (filing_key or ''):
            raise UserError(_("This filing has changed. Start it again."))

    @api.model
    def _clean(self, Wiz, allowed, vals):
        """The allow-list, applied — and typed on the way in."""
        out = {}
        for k, v in (vals or {}).items():
            if k not in allowed:
                continue
            f = Wiz._fields.get(k)
            if f is None:
                continue
            if f.type == 'many2one':
                out[k] = int(v) if v else False
            elif f.type in ('many2many', 'one2many'):
                out[k] = [(6, 0, [int(x) for x in (v or [])])]
            elif f.type in ('date', 'datetime'):
                out[k] = v or False
            elif f.type == 'boolean':
                out[k] = bool(v)
            else:
                out[k] = v if v not in (None, False) else False
        return out

    @api.model
    def save_scope(self, wizard_id, country, filing_key, vals):
        """Write the step-2 form without moving. A pure allow-listed write, so
        a Back-then-Next round trip does not lose what was typed."""
        spec = self._adapter(country)
        w = self._wizard(spec, wizard_id)
        self._assert_key(spec, w, filing_key)
        clean = self._clean(self.env[spec['model']],
                            self._writable(spec, filing_key), vals)
        if clean:
            w.write(clean)
        names = list(spec['common']) + spec['conditional'].get(filing_key, [])
        return {'wizard_id': w.id, 'values': self._values(w, names)}

    @api.model
    def _wizard(self, spec, wizard_id):
        w = self.env[spec['model']].browse(int(wizard_id or 0))
        if not w.exists():
            # A transient is vacuumed after an hour, and a flow left open over
            # lunch is the normal way to meet that. Say so — "Object does not
            # exist" would send somebody looking for a bug.
            raise UserError(_("This filing has expired. Start it again."))
        return w

    @api.model
    def generate(self, wizard_id, country, filing_key, vals):
        """Step 3. Write the allow-list, press the wizard's OWN button, keep
        whatever it produced.

        A CLICK handler's method: it writes and it creates an attachment, and
        neither of those may ever be reachable from a mount hook (W21/W41). The
        client blocks the button while one is in flight, which is what makes a
        double click one artifact set rather than two — a uniqueness guard
        cannot fix a concurrency problem (W21.1).
        """
        spec = self._adapter(country)
        w = self._wizard(spec, wizard_id)
        self._assert_key(spec, w, filing_key)
        clean = self._clean(self.env[spec['model']],
                            self._writable(spec, filing_key), vals)
        if clean:
            w.write(clean)

        method = _GENERATE[(country or '').upper()]
        # Belt and braces over a constant table: if a future adapter names a
        # method that sounds like it leaves the building, this refuses rather
        # than pressing it.
        if any(bad in method for bad in _ONLY_GENERATE):
            raise UserError(_("This filing's action is not a generate step."))
        button = getattr(w.with_context(discard_logo_check=True), method, None)
        if button is None:
            raise UserError(_("This country's filing wizard cannot generate a "
                              "file on this database."))

        # `discard_logo_check`: `ir.actions.report.report_action` hands an
        # ADMINISTRATOR a "configure your document layout" wizard instead of the
        # report when the company has no external layout — which would arrive
        # here as an act_window and read as "the button did nothing".
        try:
            outcome = button()
        except UserError:
            raise
        except Exception as e:                       # pylint: disable=broad-except
            _logger.info("Filing generate failed (%s/%s): %s",
                         country, filing_key, e)
            raise UserError(_("This filing could not be generated: %s",
                              str(getattr(e, 'name', None) or e)))

        artifacts, message = self._materialise(w, outcome)
        return {
            'wizard_id': w.id,
            'country': (country or '').upper(),
            'filing_key': filing_key,
            'artifacts': artifacts,
            'message': message,
            'done': True,
        }

    @api.model
    def _materialise(self, w, outcome):
        """Turn what the button returned into files, honestly.

        Three shapes come back from the five wizards:
          * `ir.actions.report`  — VN. Rendered here and stored, so the flow can
            name the file and its size instead of firing a download and hoping;
          * `ir.actions.client` / `display_notification` — the other four. They
            produce NO FILE at all, whatever their message says, and that is
            reported as it is rather than dressed up;
          * anything else (or nothing) — reported as nothing.
        """
        if not isinstance(outcome, dict):
            return [], _("The filing ran and produced no file.")

        if outcome.get('type') == 'ir.actions.report':
            return self._store_report(w, outcome), ''

        if outcome.get('type') == 'ir.actions.client':
            params = outcome.get('params') or {}
            # The country modules' own words, kept verbatim — but with no file
            # attached to them, which is the fact the flow is reporting.
            return [], params.get('message') or _("The filing ran and produced "
                                                  "no file.")
        return [], _("The filing ran and produced no file.")

    @api.model
    def _store_report(self, w, action):
        """Render the report the wizard chose, and keep it.

        `_render` dispatches on the report's own `report_type`, so the xlsx path
        is `report_xlsx`'s and this method knows nothing about spreadsheets. The
        attachment carries NO `res_model`: an attachment with no referenced
        record is accessible to its creator and to an administrator and to
        nobody else (`ir.attachment._check_access`), which is exactly the right
        scope for a statutory extract — and it does not dangle when the
        transient it came from is vacuumed.
        """
        report_name = action.get('report_name')
        if not report_name:
            return []
        Report = self.env['ir.actions.report']
        rec = Report._get_report(report_name)
        res_ids = (action.get('context') or {}).get('active_ids') or w.ids
        try:
            content, ext = Report._render(report_name, res_ids, action.get('data'))
        except Exception as e:                       # pylint: disable=broad-except
            _logger.info("Filing render failed (%s): %s", report_name, e)
            raise UserError(_("The filing's file could not be produced: %s",
                              str(getattr(e, 'name', None) or e)))
        base = (rec.report_file or rec.name or 'filing').replace(' ', '_')
        fname = '%s_%s.%s' % (base, fields.Date.to_string(fields.Date.context_today(self)),
                              ext or 'bin')
        att = self.env['ir.attachment'].create({
            'name': fname,
            'raw': content,
            'mimetype': 'application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet' if ext == 'xlsx' else False,
        })
        return [{
            'id': att.id,
            'name': att.name,
            'size': len(content or b''),
            'url': '/web/content/%s?download=true' % att.id,
        }]
