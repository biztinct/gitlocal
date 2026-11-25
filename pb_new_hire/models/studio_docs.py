# -*- coding: utf-8 -*-
"""NEWHIRE P3a — step 5 "Details and documents": what is needed, and who
gives it (handover §2.2–§2.4).

ONE server-built list drives the step (`details_options`): the screen holds no
country knowledge. Every item says whether the new person can be asked for it
on My Payobook (and on which existing page), whether HR can type it here, and
whether it may be left out. The product's own tables decide:

  papers per country      `pb.new.hire.paper.for_country` (this module)
  tax kinds and fields    `pb_me_tax` KINDS_BY_COUNTRY / NUMBER_FIELD /
                          CHOICE_FIELD and its own kind labels; its own
                          validator (`pb.me.detail.request._pb_check`)
  self-uploadable paper   `pb.employee.document.category.ess_uploadable`
  bank                    the old Add employee window's keys and checks
                          (`_pb_bank_choices`, `_pb_bank_problem`), so the
                          approved apply sends it exactly as before
  file limits             the side panel's own rules and sentences
                          (`pb.people.vault_upload_batch`)

Nothing here writes, except the papers editor (HR managers, company rows of
`pb.new.hire.paper` only). Every public method starts with the HR gate.
"""
import base64
import binascii
import logging
import re

from odoo import _, api, fields
from odoo import models
from odoo.exceptions import UserError

from .paper import NEED_RANK, stronger
from .studio import _int

_logger = logging.getLogger(__name__)

#: The answers a row can have ('number' only on the merged card rows).
CHOICES = ('ask', 'have', 'skip', 'later', 'number')

#: The side panel's file rules (`pb.people.vault_upload_batch`).
FILE_MIMES = ('image/png', 'image/jpeg', 'application/pdf')
FILE_MAX = 10 * 1024 * 1024
FILES_MAX = 50 * 1024 * 1024
MAX_FILES = 20

ID_CATEGORY = 'pb_employee_vault.cat_id_document'
TAX_CATEGORY = 'pb_me_tax.cat_tax_paper'

#: P3b (architect answer a): on the merged identity-card and tax-card rows
#: HR may have the number only — the number is saved and the CARD is asked.
NUMBER_ONLY = 'number'

#: Where on My Payobook each item is asked for (FACTS_ONBOARD §A7).
ASK_URL = {
    'personal': '/my/profile',
    'emergency': '/my/profile',
    'id_number': '/my/details/papers?kind=national_id',
    'bank': '/my/details/bank',
    'paper': '/my/documents',
}

#: Numbers shown back by their last four characters only.
SECRET_FIELDS = ('identification_id', 'vietnam_citizen_id', 'singapore_nric_fin',
                 'vietnam_tax_code', 'pb_npwp_number', 'pb_in_pan_number',
                 'pb_bpjs_employment_number', 'pb_bpjs_health_number',
                 'vietnam_social_insurance_number', 'pb_in_uan_number', 'pb_in_esi_number',
                 'account_number')

#: The ID number's second store, where payroll reads one (FACTS_ONBOARD §E,
#: open question 8): written together with `identification_id`.
ID_TWIN = {'VN': 'vietnam_citizen_id', 'SG': 'singapore_nric_fin'}

#: The bank keys of the old window (`pb.people.onboard.wizard.BANK_KEYS`).
BANK_FIELDS = ('bank_name', 'account_number', 'account_holder')

MAX_TEXT = 200


def mask(text):
    text = str(text or '').strip()
    return text if len(text) <= 4 else '•••• ' + text[-4:]


def _blank(value):
    return value is None or value is False or (isinstance(value, str) and not value.strip())


class PbNewHireDocs(models.AbstractModel):
    _inherit = 'pb.new.hire'

    # ================================================================ tables
    @api.model
    def _tax_rules(self):
        try:
            from odoo.addons.pb_me_tax.models import tax_rules
        except ImportError:                     # pragma: no cover — a dependency
            return None
        return tax_rules

    @api.model
    def _id_label(self, code):
        return {'ID': _("NIK (identity number)"), 'VN': _("Citizen ID number"),
                'IN': _("Aadhaar number"), 'SG': _("NRIC or FIN")}.get(code, _("Identity number"))

    @api.model
    def _insurance_fields(self, code):
        """The numbers HR keeps (FACTS_ONBOARD §E "Kept by HR")."""
        rows = {
            'ID': [('pb_bpjs_employment_number', _("BPJS Ketenagakerjaan number")),
                   ('pb_bpjs_health_number', _("BPJS Kesehatan number"))],
            'VN': [('vietnam_social_insurance_number', _("Social insurance number"))],
            'IN': [('pb_in_uan_number', _("UAN (provident fund)")),
                   ('pb_in_esi_number', _("ESI number"))],
        }.get(code, [])
        fields_ = self.env['hr.employee']._fields
        return [(f, l) for f, l in rows if f in fields_]

    @api.model
    def _insurance_label(self, code):
        return {'ID': _("BPJS numbers"), 'VN': _("Social insurance number"),
                'IN': _("UAN and ESI numbers")}.get(code, _("Insurance numbers"))

    @api.model
    def _papers_for(self, code):
        """The paper rows of this country for this company, as plain dicts."""
        if not code:
            return []
        rows = self.env['pb.new.hire.paper'].sudo().for_country(code, self._company())
        out = []
        for row in rows:
            cat = row.category_id
            out.append({'category': cat, 'category_id': cat.id, 'need': row.need,
                        'label': row.display_label(), 'expiry': bool(cat.requires_expiry),
                        'self_upload': bool(getattr(cat, 'ess_uploadable', False))})
        return out

    @api.model
    def _papers_tile(self, code):
        """Step 2's "Papers needed" tile: N required, M optional."""
        papers = self._papers_for(code)
        required = [p for p in papers if p['need'] != 'optional']
        return {'required': len(required), 'optional': len(papers) - len(required),
                'first_pay': [p['label'] for p in papers if p['need'] == 'first_pay']}

    @api.model
    def _bank_options(self, code):
        """The banks the bank check knows, this country's first (the old
        window's own list; typing another bank is fine)."""
        try:
            banks = self.env['pb.people.onboard.wizard']._pb_bank_choices()
        except Exception:                       # noqa: BLE001 — a list, never a gate
            return []
        mine = [b for b in banks if b.get('country') == code]
        return [{'value': b['value'], 'label': b.get('label') or ''} for b in (mine or banks)][:200]

    @api.model
    def _field(self, name, label, kind='text', required=False, hint='', options=None):
        return {'name': name, 'label': label, 'kind': kind, 'required': bool(required),
                'hint': hint or '', 'options': options or []}

    @api.model
    def _selection_options(self, model, name):
        field = self.env[model]._fields.get(name)
        if not field:
            return []
        return [{'value': v, 'label': l} for v, l in field._description_selection(self.env)]

    # ================================================================ the list
    @api.model
    def _detail_items(self, code, first):
        """The items of step 5 for one country of work, in order (§2.3)."""
        Emp = self.env['hr.employee']
        have_field = Emp._fields
        papers = self._papers_for(code)
        id_cat = self.env.ref(ID_CATEGORY, raise_if_not_found=False)
        tax_cat = self.env.ref(TAX_CATEGORY, raise_if_not_found=False)
        rules = self._tax_rules()
        kinds = list(rules.KINDS_BY_COUNTRY.get(code, ())) if rules else []
        id_paper = next((p for p in papers if id_cat and p['category'] == id_cat), None)
        tax_paper = next((p for p in papers if tax_cat and p['category'] == tax_cat), None) \
            if 'tax_number' in kinds else None
        items = []

        def item(key, group, icon, label, sub, need, **kw):
            row = {'key': key, 'group': group, 'icon': icon, 'label': label, 'sub': sub,
                   'need': need, 'can_ask': True, 'ask_why_not': '', 'can_have': True,
                   'can_skip': need != 'first_pay', 'fields': [], 'upload': False,
                   'ask_url': ASK_URL.get(key, '')}
            row.update(kw)
            row['default'] = 'ask' if row['can_ask'] else 'later'
            items.append(row)
            return row

        def upload(paper):
            return {'category_id': paper['category_id'], 'needs_expiry': paper['expiry'],
                    'label': paper['label']}

        # 1. personal details
        personal = [f for f in (
            self._field('birthday', _("Date of birth"), 'date'),
            self._field('sex', _("Gender"), 'select',
                        options=self._selection_options('hr.employee', 'sex')),
            self._field('private_street', _("Home address")),
            self._field('private_city', _("City")),
            self._field('private_phone', _("Personal phone"), 'phone'),
        ) if f['name'] in have_field]
        item('personal', 'details', 'user', _("Personal details"),
             _("Date of birth, gender, home address and personal phone."), 'optional',
             fields=personal,
             ask_note=_("%s fills in the phone and home address on My Payobook.", first))
        # 2. emergency contact
        item('emergency', 'details', 'smartphone', _("Emergency contact"),
             _("Who to call if something happens at work."), 'optional',
             fields=[f for f in (self._field('emergency_contact', _("Contact name")),
                                 self._field('emergency_phone', _("Contact phone"), 'phone'))
                     if f['name'] in have_field])
        # 3. the ID number (and its paper, merged)
        id_label = self._id_label(code)
        id_need = stronger('first_pay', id_paper['need']) if id_paper else 'first_pay'
        if id_paper:
            # number only (answer a): the card is uploaded where the person
            # uploads that kind of paper — My documents when it is
            # self-uploadable, else the ID paper form
            item('id_number', 'papers', 'idCard',
                 _("%(paper)s and number", paper=id_paper['label']),
                 _("The card and the %(number)s on it, asked for together.", number=id_label),
                 id_need, fields=[self._field('identification_id', id_label, required=True)],
                 upload=upload(id_paper), merged=True,
                 card_url=ASK_URL['paper'] if id_paper['self_upload'] else ASK_URL['id_number'])
        else:
            item('id_number', 'details', 'idCard', id_label,
                 _("The number payroll and the insurance reports use."), id_need,
                 fields=[self._field('identification_id', id_label, required=True)])
        # 4. tax kinds of the country (pb_me_tax's own table and labels)
        if rules:
            kind_words = dict(self.env['pb.me.detail.request']._fields['kind']
                              ._description_selection(self.env))
            for kind in kinds:
                if kind == 'tax_number':
                    target = rules.NUMBER_FIELD.get(code)
                    label = Emp._pbtx_number_label(code)
                    fld = self._field(target, label, required=True,
                                      hint=_("Checked the way My Payobook checks it."))
                else:
                    target = rules.CHOICE_FIELD.get((kind, code))
                    label = kind_words.get(kind) or kind
                    fld = self._field(target, label, 'select', required=True,
                                      options=self._selection_options('hr.employee', target))
                if not target or target not in have_field:
                    continue
                need = 'first_pay' if kind == 'tax_number' else 'joining'
                url = '/my/tax/change/%s' % kind
                if kind == 'tax_number' and tax_paper:
                    item(kind, 'papers', 'receipt',
                         _("%(paper)s and number", paper=tax_paper['label']),
                         _("The card and the %(number)s on it, asked for together.", number=label),
                         stronger(need, tax_paper['need']), fields=[fld],
                         upload=upload(tax_paper), ask_url=url, merged=True,
                         # the tax page files the card as the number's proof
                         card_url=url)
                else:
                    icon = 'receipt' if kind == 'tax_number' else 'scale'
                    sub = _("Checked by HR before it is saved.") if kind == 'tax_number' \
                        else _("Decides how much income tax is taken.")
                    item(kind, 'details', icon, label, sub, need, fields=[fld], ask_url=url)
        # 5. numbers HR keeps
        ins = self._insurance_fields(code)
        if ins:
            item('insurance', 'details', 'shieldCheck', self._insurance_label(code),
                 _("Social insurance numbers, if the person already has them."), 'optional',
                 fields=[self._field(f, l) for f, l in ins], can_ask=False,
                 ask_why_not=_("These numbers are kept by HR. Add them now or later on the record."),
                 ask_url='')
        # 6. the bank account (the old window's keys, so the approved apply
        #    sends it through the bank change path unchanged)
        item('bank', 'details', 'landmark', _("Bank account"),
             _("Where the pay goes. A second person approves it, whoever types it."), 'first_pay',
             fields=[self._field('bank_name', _("Bank"), 'bank', required=True,
                                 options=self._bank_options(code)),
                     self._field('account_number', _("Account number"), required=True,
                                 hint=_("6 to 19 digits.")),
                     self._field('account_holder', _("Name on the account"),
                                 hint=_("Left empty, the person's own name is used."))])
        # 7. papers of the country (the ID and tax papers are merged above)
        for paper in papers:
            if paper is id_paper or paper is tax_paper:
                continue
            cat = paper['category']
            can_ask = paper['self_upload']
            item('paper-%s' % cat.id, 'papers', self._paper_icon(cat), paper['label'],
                 _("A scan or a photo, filed in the person's documents."), paper['need'],
                 upload=upload(paper), can_ask=can_ask,
                 ask_why_not='' if can_ask else _("Only HR can add this paper."),
                 ask_url=ASK_URL['paper'] if can_ask else '', category_id=cat.id)
        for row in items:
            row.setdefault('merged', False)
            row.setdefault('card_url', '')
            row['can_number'] = bool(row['merged'])
            row.setdefault('ask_note', '')
            row.setdefault('category_id', (row['upload'] or {}).get('category_id') or False)
        return items

    @api.model
    def _paper_icon(self, category):
        refs = {'pb_employee_vault.cat_certificate': 'award',
                'pb_employee_vault.cat_health_check': 'activity',
                'pb_employee_vault.cat_work_permit': 'stamp',
                'pb_employee_vault.cat_other': 'fileText'}
        for xmlid, icon in refs.items():
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec and rec == category:
                return icon
        return 'fileText'

    @api.model
    def details_options(self, draft):
        """Step 5: the list of what is needed for this country of work, and
        who may give each one."""
        self._gate()
        d = self._clean(draft)
        code = d.get('payroll_country') if d.get('payroll_country') in dict(self._countries()) else ''
        first = self._first_of(d.get('name'))
        out = {'country': code, 'country_name': self._country_label(code) if code else '',
               'items': [], 'papers_editable': False}
        if not code:
            return out
        out['items'] = self._detail_items(code, first)
        out['papers_editable'] = bool(self.env['pb.new.hire.paper']._can_edit())
        return out

    # ================================================================ the editor
    @api.model
    def _papers_editor_rows(self, code):
        company = self._company()
        Paper = self.env['pb.new.hire.paper'].sudo()
        eff = Paper._effective(code, company)
        defaults = {r.category_id: r for r in Paper.search(
            [('country_code', '=', code), ('company_id', '=', False)])}
        rows = []
        for cat, row in sorted(eff.items(), key=lambda kv: (kv[1].sequence, kv[0].sequence, kv[0].id)):
            default = defaults.get(cat)
            rows.append({'category_id': cat.id, 'name': Paper.plain_name(cat),
                         'need': row.need if row.active else 'none',
                         'label': row.display_label(),
                         'usual': (default.need if default else 'none'),
                         'usual_label': default.display_label() if default else Paper.plain_name(cat),
                         'self_upload': bool(getattr(cat, 'ess_uploadable', False))})
        listed = {r['category_id'] for r in rows}
        others = self.env['pb.employee.document.category'].sudo().search(
            [('active', '=', True)], order='sequence, name, id')
        return rows, [{'category_id': c.id, 'name': Paper.plain_name(c)}
                      for c in others if c.id not in listed]

    @api.model
    def papers_edit_load(self, country_code):
        """The papers editor (HR managers): every paper of this country, its
        need here and what this country calls it; the categories that could
        be added; and whether the company changed the usual list."""
        self._gate()
        self.env['pb.new.hire.paper']._require_editor()
        code = country_code if country_code in dict(self._countries()) else ''
        if not code:
            raise UserError(_("Choose the country of work in step 2 first."))
        rows, others = self._papers_editor_rows(code)
        custom = bool(self.env['pb.new.hire.paper'].sudo().with_context(active_test=False).search_count(
            [('country_code', '=', code), ('company_id', '=', self._company().id)]))
        return {'country': code, 'country_name': self._country_label(code), 'rows': rows,
                'others': others, 'custom': custom,
                'needs': [{'value': v, 'label': l} for v, l in
                          self.env['pb.new.hire.paper']._fields['need']._description_selection(self.env)]
                + [{'value': 'none', 'label': _("Not needed")}]}

    @api.model
    def papers_edit_save(self, country_code, rows):
        """Write the company's own list for this country: a company row only
        where it differs from the usual one (an inactive row = "not needed
        here"). The shipped rows are never touched."""
        self._gate()
        Paper = self.env['pb.new.hire.paper']
        Paper._require_editor()
        code = country_code if country_code in dict(self._countries()) else ''
        if not code:
            raise UserError(_("Choose the country of work in step 2 first."))
        company = self._company()
        Sudo = Paper.sudo().with_context(active_test=False)
        defaults = {r.category_id.id: r for r in Sudo.search(
            [('country_code', '=', code), ('company_id', '=', False), ('active', '=', True)])}
        cats = self.env['pb.employee.document.category'].sudo()
        wanted = []
        seen = set()
        for n, row in enumerate((rows or [])[:60]):
            if not isinstance(row, dict):
                continue
            cat = cats.browse(_int(row.get('category_id'))).exists()
            need = row.get('need')
            if not cat or cat.id in seen or need not in (*NEED_RANK, 'none'):
                continue
            seen.add(cat.id)
            label = ' '.join(str(row.get('label') or '').split())[:MAX_TEXT]
            wanted.append((n, cat, need, label))
        Sudo.search([('country_code', '=', code), ('company_id', '=', company.id)]).unlink()
        for n, cat, need, label in wanted:
            default = defaults.get(cat.id)
            seq = (n + 1) * 10
            if default:
                same_label = not label or label == default.display_label()
                if need == default.need and same_label and default.sequence == seq:
                    continue
                vals = {'need': default.need if need == 'none' else need,
                        'active': need != 'none',
                        'label': False if same_label else label}
            else:
                if need == 'none':
                    continue
                plain = Paper.plain_name(cat)
                vals = {'need': need, 'active': True,
                        'label': False if (not label or label in (cat.name, plain)) else label}
            Sudo.create(dict(vals, category_id=cat.id, country_code=code,
                             company_id=company.id, sequence=seq))
        return self.papers_edit_load(code)

    @api.model
    def papers_edit_reset(self, country_code):
        """"Back to the usual list": the company's own rows go."""
        self._gate()
        self.env['pb.new.hire.paper']._require_editor()
        code = country_code if country_code in dict(self._countries()) else ''
        self.env['pb.new.hire.paper'].sudo().with_context(active_test=False).search(
            [('country_code', '=', code), ('company_id', '=', self._company().id)]).unlink()
        return self.papers_edit_load(code)

    # ================================================================ send
    @api.model
    def _doc_choices(self, items, d):
        """`{key: choice}` for every item: what the screen sent, or the
        item's default when it sent nothing it may use."""
        given = d.get('items') if isinstance(d.get('items'), dict) else {}
        out = {}
        for item in items:
            choice = given.get(item['key'])
            if choice == 'ask' and not item['can_ask']:
                choice = None
            if choice == 'later' and item['can_ask']:
                choice = None
            if choice == 'have' and not item['can_have']:
                choice = None
            if choice == NUMBER_ONLY and not item.get('can_number'):
                choice = None
            out[item['key']] = choice if choice in CHOICES else item['default']
        return out

    @api.model
    def _have(self, d):
        """The typed values. Step 1's personal phone is the one source of the
        personal phone (the screen shows it in step 5 too)."""
        have = dict(d.get('have')) if isinstance(d.get('have'), dict) else {}
        personal = str(d.get('personal') or '').strip()
        if personal and '@' not in personal and _blank(have.get('private_phone')):
            have['private_phone'] = personal
        return have

    @api.model
    def _check_value(self, code, field, value):
        """`(clean value, problem sentence or '')` for one typed value."""
        kind = field['kind']
        if kind == 'date':
            day = self._day(value)
            if not day:
                return False, _("That date does not look right.")
            if field['name'] == 'birthday' and day > fields.Date.context_today(self):
                return False, _("The date of birth cannot be in the future.")
            return fields.Date.to_string(day), ''
        if kind == 'select':
            options = {o['value'] for o in field['options']}
            return (value, '') if value in options else (False, _("Choose one of the options."))
        text = ' '.join(str(value).split())[:MAX_TEXT]
        rules = self._tax_rules()
        if rules and field['name'] == rules.NUMBER_FIELD.get(code):
            number, problem = rules.normalise_number(code, text)
            if problem:
                # pb_me_tax's own check and sentence (an attachment is not
                # what is being judged here, so its presence is given)
                try:
                    self.env['pb.me.detail.request'].sudo().with_context(pbtx_employee=0)._pb_check(
                        'tax_number', {'t_country': code, 't_number': number}, attachment=True)
                except UserError as exc:
                    return False, exc.args[0] if exc.args else _("Write the tax number.")
                return False, _("Write the tax number.")
            return number, ''
        return text, ''

    @api.model
    def _file_problem(self, item, file, total):
        """The side panel's own rules and sentences, checked BEFORE anything
        is proposed. → (decoded bytes or None, sentence or '')."""
        if not isinstance(file, dict) or not file.get('data'):
            return None, _("Attach the %s, or choose another option.", item['upload']['label'])
        if file.get('mime') not in FILE_MIMES:
            return None, _("Only JPG, PNG or PDF documents are accepted.")
        data = file.get('data') or ''
        if len(data) > 14 * 1024 * 1024:
            return None, _("Each file must be 10 MB or smaller.")
        try:
            raw = base64.b64decode(data, validate=True)
        except (ValueError, TypeError, binascii.Error):
            return None, _("The selected file could not be read.")
        if not raw or len(raw) > FILE_MAX:
            return None, _("Choose a non-empty file up to 10 MB.")
        if total + len(raw) > FILES_MAX:
            return None, _("The selected files must total 50 MB or less.")
        issued = self._day(file.get('issue_date'))
        expires = self._day(file.get('expiry_date'))
        if item['upload']['needs_expiry'] and not expires:
            return None, _("An expiry date is required for every '%s' file.", item['upload']['label'])
        if issued and expires and expires < issued:
            return None, _("Expiry must be on or after the issue date.")
        return raw, ''

    @api.model
    def _files_by_key(self, files):
        out = {}
        for row in (files or [])[:MAX_FILES * 2] if isinstance(files, list) else []:
            if isinstance(row, dict) and row.get('key'):
                out[str(row['key'])] = row
        return out

    @api.model
    def _validate_docs(self, d, files=None):
        """`None`, or where and what to fix in step 5 (field ids are the
        screen's: `have-<field>`, `file-<item>`, `doc-<item>`)."""
        code = d.get('payroll_country')
        if code not in dict(self._countries()):
            return None
        first = self._first_of(d.get('name'))
        items = self._detail_items(code, first)
        choices = self._doc_choices(items, d)
        given = d.get('items') if isinstance(d.get('items'), dict) else {}
        have = self._have(d)
        by_key = self._files_by_key(files)
        total = 0
        for item in items:
            key = item['key']
            if given.get(key) == 'skip' and not item['can_skip']:
                return self._refuse('docs', 'doc-%s' % key, _(
                    "%(what)s is needed before the first pay, so it cannot be left out. "
                    "Ask %(first)s for it, or add it now.", what=item['label'], first=first))
            if choices[key] not in ('have', NUMBER_ONLY):
                continue
            typed = 0
            for field in item['fields']:
                value = have.get(field['name'])
                if key == 'bank' and field['name'] == 'account_holder':
                    continue
                if _blank(value):
                    if field['required']:
                        return self._refuse('docs', 'have-%s' % field['name'], _(
                            "Type the %(what)s, or choose Ask %(first)s.", what=field['label'].lower(),
                            first=first) if item['can_ask'] else _(
                            "Type the %s, or choose Later.", field['label'].lower()))
                    continue
                if key == 'bank':
                    typed += 1
                    continue
                _clean, problem = self._check_value(code, field, value)
                if problem:
                    return self._refuse('docs', 'have-%s' % field['name'], problem)
                typed += 1
            if key == 'bank':
                problem = self.env['pb.people.onboard.wizard']._pb_bank_problem(
                    self.env['pb.people.onboard.wizard']._pb_bank_entered(
                        {k: have.get(k) for k in BANK_FIELDS}))
                if problem:
                    return self._refuse('docs', 'have-account_number', problem)
            if item['upload'] and choices[key] == 'have':
                raw, problem = self._file_problem(item, by_key.get(key), total)
                if problem:
                    return self._refuse('docs', 'file-%s' % key, problem)
                total += len(raw)
            elif item['fields'] and not typed:
                return self._refuse('docs', 'have-%s' % item['fields'][0]['name'], _(
                    "Type at least one of these, or choose another option."))
        return None

    @api.model
    def _values_docs(self, d, vals, files=None):
        """The P3a keys of the ONE values dict (JSON-plain, NH8): the typed
        details, the bank in the old window's keys, which papers HR holds and
        what the new person will be asked. File CONTENT never goes here."""
        code = vals.get('payroll_country')
        names = vals.setdefault('pb_nh_names', {})
        first = self._first_of(vals.get('name'))
        items = self._detail_items(code, first)
        choices = self._doc_choices(items, d)
        have = self._have(d)
        by_key = self._files_by_key(files)
        details, shown, asks, papers, later = {}, [], [], [], []
        for n, item in enumerate(items):
            key, choice = item['key'], choices[item['key']]
            if choice == NUMBER_ONLY:
                # the number is saved now; the card itself is asked for, on
                # the page that serves that kind of paper (answer a)
                for field in item['fields']:
                    value = have.get(field['name'])
                    if _blank(value):
                        continue
                    clean, problem = self._check_value(code, field, value)
                    if problem:
                        continue
                    details[field['name']] = clean
                    shown.append([field['label'],
                                  mask(clean) if field['name'] in SECRET_FIELDS else clean])
                asks.append({'key': key, 'label': item['upload']['label'], 'need': item['need'],
                             'url': item['card_url'] or item['ask_url'], 'sequence': (n + 1) * 10,
                             'category_id': item['category_id'] or False})
                continue
            if choice == 'have':
                if key == 'bank':
                    for name in BANK_FIELDS:
                        value = ' '.join(str(have.get(name) or '').split())[:MAX_TEXT]
                        if value:
                            vals[name] = value
                    if not vals.get('account_holder'):
                        vals['account_holder'] = vals['name']
                else:
                    for field in item['fields']:
                        value = have.get(field['name'])
                        if _blank(value):
                            continue
                        clean, problem = self._check_value(code, field, value)
                        if problem:
                            continue                # _validate_docs said it already
                        details[field['name']] = clean
                        text = next((o['label'] for o in field['options'] if o['value'] == clean), clean) \
                            if field['kind'] == 'select' else clean
                        shown.append([field['label'],
                                      mask(text) if field['name'] in SECRET_FIELDS else text])
                if item['upload'] and by_key.get(key):
                    papers.append({'key': key, 'label': item['upload']['label'],
                                   'category_id': item['upload']['category_id']})
            elif choice == 'ask':
                asks.append({'key': key, 'label': item['label'], 'need': item['need'],
                             'url': item['ask_url'], 'sequence': (n + 1) * 10,
                             'category_id': item['category_id'] or False})
            elif choice == 'later':
                later.append(item['label'])
        if details:
            vals['pb_nh_details'] = details
        vals['pb_nh_asks'] = asks
        # P3b: remind the person every 2 days (and HR 3 days before day one)
        vals['nh_remind'] = d.get('remind') is not False
        vals['pb_nh_papers'] = papers
        names['details'] = shown
        names['later'] = later
        return vals
