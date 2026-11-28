# -*- coding: utf-8 -*-
"""Employment contracts in the Document studio (`pb.doc.studio`, by
inheritance only — `pb_doc_studio` is not edited).

* The contract a document is made for travels in the context
  (`pbdc_contract_id`). Every value and every "Show only when" fact the
  studio reads from "the person's contract" then reads THAT contract — the
  studio's own contract fields (start, end, type, monthly pay, own contract
  fields) included.
* "This document" fields of an employment contract are worked out here from
  the contract and the person, so the designer's field list and preview show
  real values (not "filled in when the letter is made").
* Two conditions for every document: "Contract length" (fixed term /
  open-ended) and "Trial period ends".
* The gallery gets the group "Employment contracts"; a new document made in
  it is an employment contract; a copy of a shipped contract takes its
  built-in rules, page and language along.
"""
import logging

from markupsafe import escape

from odoo import api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.pb_doc_studio.models.doc_common import MAIN_LANG

from .contract_common import (
    CONTRACT_FIELDS, CONTRACT_KEYS, CONTRACT_KIND, CONTRACT_TYPE, SHIPPED,
    SHIPPED_PAGE, TERM_LABELS, TERM_VALUES, VAULT_CATEGORY,
)

_logger = logging.getLogger(__name__)


class PbDocStudio(models.AbstractModel):
    _inherit = 'pb.doc.studio'

    # ============================================================ contract
    @api.model
    def _pbds_contract(self, employee):
        """The contract a document is made for (context `pbdc_contract_id`),
        when it is this person's; otherwise the studio's own choice (the
        person's current contract)."""
        cid = self.env.context.get('pbdc_contract_id')
        if cid and employee and 'hr.contract' in self.env:
            contract = self.env['hr.contract'].browse(int(cid))
            try:
                # The person's own contract is theirs to read (F-b ruling 2);
                # anybody else reads it with their own rights.
                probe = contract.sudo() if self._pbds_is_own_record(employee) else contract
                if probe.exists() and probe.employee_id.id == employee.id:
                    return contract
            except AccessError:
                pass
            return self.env['hr.contract']
        return super()._pbds_contract(employee)

    @api.model
    def _pbdc_dmy(self, value):
        return value.strftime('%d/%m/%Y') if value else ''

    # ============================================================ values
    @api.model
    def _pbds_generic_values(self, employee, company, lang, keys):
        keys = list(keys or [])
        ctx_contract = bool(self.env.context.get('pbdc_contract_id'))
        mine = [k for k in keys if k in CONTRACT_KEYS
                or (k == 'monthly_pay' and ctx_contract)]
        rest = [k for k in keys if k not in mine]
        out, blocked = super()._pbds_generic_values(employee, company, lang, rest)
        if mine and employee:
            more, more_blocked = self._pbdc_values(employee, company, lang, mine)
            out.update(more)
            blocked = set(blocked) | set(more_blocked)
        return out, blocked

    @api.model
    def _pbdc_values(self, employee, company, lang, keys):
        """`({key: escaped text}, blocked keys)` of the contract fields.
        Read as the caller; a value the caller may not read prints nothing
        (pay: blocked, see `_pbdc_pay`)."""
        env = self.with_context(lang=lang).env
        _ = env._
        # Read with this method's own rights, never the record's (ledger
        # DS-16); the person's own record is theirs to read.
        own = self._pbds_is_own_record(employee)
        emp = employee.sudo() if own else employee.with_env(self.env)
        company = company or emp.company_id or env.company
        contract = self._pbds_contract(emp)
        if contract and own:
            contract = contract.sudo()
        out, blocked = {}, set()

        def safe(fn):
            try:
                return fn() or ''
            except AccessError:
                return ''

        def cval(name):
            if not contract or name not in contract._fields:
                return False
            try:
                return contract[name]
            except AccessError:
                return False

        for key in keys:
            val = ''
            if key == 'contract_ref':
                val = cval('name') or ''
            elif key == 'contract_end_text':
                end = cval('date_end')
                if end:
                    val = self._pbds_long_date(end, lang)
                elif contract:
                    val = _('no end date')
            elif key == 'trial_end':
                val = self._pbds_long_date(cval('trial_date_end'), lang)
            elif key == 'start_dmy':
                val = self._pbdc_dmy(cval('date_start'))
            elif key == 'end_dmy':
                val = self._pbdc_dmy(cval('date_end'))
            elif key == 'trial_end_dmy':
                val = self._pbdc_dmy(cval('trial_date_end'))
            elif key == 'today_dmy':
                val = self._pbdc_dmy(fields.Date.context_today(self))
            elif key == 'working_schedule':
                cal = cval('resource_calendar_id')
                val = cal.sudo().with_context(lang=lang).name if cal else ''
            elif key == 'weekly_hours':
                cal = cval('resource_calendar_id')
                hours = cal.sudo().hours_per_week if cal and 'hours_per_week' in cal._fields else 0
                if hours:
                    val = ('%.2f' % hours).rstrip('0').rstrip('.')
            elif key == 'contract_job':
                job = cval('job_id')
                val = job.sudo().with_context(lang=lang).name if job \
                    else safe(lambda: emp.job_title or emp.job_id.name)
            elif key == 'contract_department':
                dept = cval('department_id')
                val = dept.sudo().with_context(lang=lang).name if dept \
                    else safe(lambda: emp.department_id.name)
            elif key == 'contract_location':
                val = cval('location') or safe(lambda: emp.work_location_id.name)
            elif key == 'pay_currency':
                cur = cval('currency_id') or company.currency_id
                val = cur.name if cur else ''
            elif key == 'pay_scheme':
                struct = cval('struct_id')
                val = struct.sudo().with_context(lang=lang).name if struct else ''
            elif key == 'employer_rep':
                # The signatory of the page design when the caller made the
                # document know it (`pbdc_page`), else the company.
                page = self.env.context.get('pbdc_page') or {}
                val = (page.get('sign_name') or '').strip() or company.sudo().name or ''
            elif key == 'employer_rep_title':
                page = self.env.context.get('pbdc_page') or {}
                val = (page.get('sign_title') or '').strip() or _('Authorised signatory')
            elif key == 'id_number':
                val = safe(lambda: emp.identification_id)
            elif key == 'passport_number':
                val = safe(lambda: emp.passport_id)
            elif key == 'home_address':
                val = safe(lambda: self._pbdc_address(emp, lang))
            elif key == 'birthday':
                val = safe(lambda: self._pbds_long_date(emp.birthday, lang))
            elif key == 'birthday_dmy':
                val = safe(lambda: self._pbdc_dmy(emp.birthday))
            elif key == 'nationality':
                val = safe(lambda: emp.country_id.with_context(lang=lang).name)
            elif key == 'monthly_pay':
                val = self._pbdc_pay(emp, contract, company, lang)
                if val is None:
                    blocked.add(key)
                    val = ''
            out[key] = str(escape(val or ''))
        return out, blocked

    @api.model
    def _pbdc_address(self, emp, lang):
        parts = [emp.private_street, emp.private_street2, emp.private_city,
                 emp.private_state_id.with_context(lang=lang).name if emp.private_state_id else '',
                 emp.private_zip,
                 emp.private_country_id.with_context(lang=lang).name if emp.private_country_id else '']
        return ', '.join(p.strip() for p in parts if p and p.strip())

    @api.model
    def _pbdc_pay(self, emp, contract, company, lang):
        """The monthly pay of THIS contract, formatted; '' when there is no
        contract; None when the caller may not see it (the pay rail).

        * The person's own contract: always (F-b ruling 2), read under sudo
          for that one record only.
        * Anybody else: the contract panel's own rule (the wage is shown,
          not masked) AND the field may be read as the caller (Access
          Studio, ledger DS-3/DS-8: checked explicitly, never from cache)."""
        from odoo.tools.misc import format_amount
        if not contract:
            return ''
        env = self.with_context(lang=lang).env
        own = self._pbds_is_own_record(emp)
        try:
            if own:
                rec = contract.sudo()
            else:
                if 'pb.contracts' in self.env and \
                        not self.env['pb.contracts']._cd_unmask_wage():
                    return None
                rec = contract.with_env(self.env(su=False))
                rec.check_access('read')
                rec._check_field_access(rec._fields['wage'], 'read')
            wage = rec.wage
            currency = rec.currency_id if 'currency_id' in rec._fields and rec.currency_id \
                else (company or emp.company_id).currency_id
        except AccessError:
            return None
        return format_amount(env, wage or 0.0, currency, lang_code=lang)

    # ============================================================ catalogue
    @api.model
    def _pbds_type_fields(self, letter_type, kind=None):
        rows = super()._pbds_type_fields(letter_type, kind)
        if letter_type == CONTRACT_TYPE or kind == CONTRACT_KIND:
            have = {r[0] for r in rows}
            rows += [r for r in CONTRACT_FIELDS if r[0] not in have]
        return rows

    @api.model
    def _pbds_catalogue(self, tmpl):
        """Contract fields are worked out from the person's contract: they
        show a real value (or "No ... on this person"), never "filled in
        when the letter is made"."""
        groups, flat = super()._pbds_catalogue(tmpl)
        for key in CONTRACT_KEYS:
            if key in flat and flat[key].get('group') == 'document':
                flat[key].pop('later', None)
        return groups, flat

    # ============================================================ conditions
    @api.model
    def _pbds_condition_meta(self):
        out = super()._pbds_condition_meta()
        _ = self.env._
        out.append({'key': 'contract_term', 'label': _('Contract length'), 'type': 'choice',
                    'options': [{'value': v, 'label': _(l)} for v, l in zip(TERM_VALUES, TERM_LABELS)]})
        out.append({'key': 'trial_end', 'label': _('Trial period end date'), 'type': 'date',
                    'options': []})
        return out

    @api.model
    def _pbds_condition_meta_light(self):
        out = super()._pbds_condition_meta_light()
        out += [{'key': 'contract_term', 'type': 'choice'}, {'key': 'trial_end', 'type': 'date'}]
        return out

    @api.model
    def _pbds_facts(self, employee):
        facts, meta = super()._pbds_facts(employee)
        if not employee:
            return facts, meta
        contract = self._pbds_contract(employee)
        if contract is not None and contract:
            try:
                facts['contract_term'] = 'fixed' if contract.date_end else 'open'
                facts['trial_end'] = contract.trial_date_end or False \
                    if 'trial_date_end' in contract._fields else False
            except AccessError:
                pass
        return facts, meta

    # ============================================================ gallery
    @api.model
    def board(self):
        res = super().board()
        _ = self.env._
        kinds = res.get('kinds') or []
        if not any(k['key'] == CONTRACT_KIND for k in kinds):
            pos = next((i + 1 for i, k in enumerate(kinds) if k['key'] == 'contract'), len(kinds))
            kinds.insert(pos, {'key': CONTRACT_KIND, 'label': _('Employment contracts')})
            res['kinds'] = kinds
        order = [k['key'] for k in kinds]
        cards = res.get('cards') or []
        index = {c['id']: i for i, c in enumerate(cards)}
        cards.sort(key=lambda c: (order.index(c['kind']) if c['kind'] in order else 99,
                                  index.get((c['variant_of'] or {}).get('id', c['id']), 0),
                                  bool(c['variant_of']), c['id']))
        return res

    @api.model
    def create_blank(self, kind, name=None):
        if kind != CONTRACT_KIND:
            return super().create_blank(kind, name)
        res = super().create_blank('other', name or self.env._('New employment contract'))
        tmpl = self.env['pb.letter.template'].browse(res['id'])
        category = self.env.ref(VAULT_CATEGORY, raise_if_not_found=False)
        tmpl.write({
            'letter_type': CONTRACT_TYPE,
            'pbds_kind_set': CONTRACT_KIND,
            'vault_category_id': category.id if category else False,
            'pbds_page': dict(SHIPPED_PAGE),
        })
        return res

    @api.model
    def open(self, template_id):
        res = super().open(template_id)
        tmpl = self.env['pb.letter.template'].with_context(active_test=False).browse(int(template_id))
        if not tmpl._pbdc_is_contract():
            return res
        # A shipped contract never saved here opens with its built-in rules
        # and page (they are stored at the first save, like any document's).
        if not tmpl.pbds_rules:
            rules = tmpl._pbdc_rules()
            if rules:
                meta_full = {m['key']: m for m in self._pbds_condition_meta()}
                res['rules'] = rules
                res['sentences'] = {rid: self._pbds_rule_sentence(r, meta_full)
                                    for rid, r in rules.items()}
        if not tmpl.pbds_page:
            res['page'] = self._pbds_clean_page(tmpl._pbdc_page())
        # The designer shows the sample-wording notice above the page (never
        # printed) until the customer saves their own wording.
        res['pbdc_note'] = bool(tmpl.pbdc_sample)
        return res

    @api.model
    def _pbds_preview_lang(self, tmpl, employee, draft, lang):
        """A contract previews in the language the contract panel prints it
        in for this person (`pb.contracts._pbdc_pick_lang` with no language
        asked): theirs when the wording exists in it, else their company's,
        else the main wording's. The languages are those of the draft on
        screen (main language, wordings of their own) plus the saved ones."""
        lang = super()._pbds_preview_lang(tmpl, employee, draft, lang)
        if not tmpl._pbdc_is_contract() or not employee:
            return lang
        Panel = self.env['pb.contracts']
        codes = [row['code'] for row in Panel._pbdc_langs(tmpl)]
        draft = draft if isinstance(draft, dict) else {}
        active = self._pbds_active_langs()
        main = draft.get('main_lang')
        if main in active:
            codes = [main] + [c for c in codes if c != main]
        versions = draft.get('versions') if isinstance(draft.get('versions'), dict) else {}
        for code, ver in versions.items():
            if code in active and code not in codes and ver:
                codes.append(code)
            elif code in codes and ver is None and code != codes[0]:
                codes.remove(code)
        return Panel._pbdc_pick_lang(tmpl, employee, False, [{'code': c} for c in codes])

    @api.model
    def save(self, template_id, payload):
        """The customer's first save makes the wording theirs: the sample
        notice goes away."""
        res = super().save(template_id, payload)
        tmpl = self.env['pb.letter.template'].with_context(active_test=False).browse(int(template_id))
        if tmpl.pbdc_sample:
            tmpl.sudo().pbdc_sample = False
        return res

    @api.model
    def reset(self, template_id):
        """Putting a shipped contract back brings back the sample wording,
        and with it the notice."""
        res = super().reset(template_id)
        tmpl = self.env['pb.letter.template'].with_context(active_test=False).browse(int(template_id))
        if tmpl._pbdc_xmlid() in SHIPPED:
            tmpl.sudo().pbdc_sample = True
        return res

    @api.model
    def copy_for(self, template_id, company_id=False, country_ids=None):
        """A copy of a shipped contract starts from what it prints with: the
        built-in rules, page and language travel with the words."""
        src = self.env['pb.letter.template'].with_context(active_test=False).browse(int(template_id or 0))
        res = super().copy_for(template_id, company_id, country_ids)
        if res.get('existing') or not src.exists() or not src._pbdc_is_contract():
            return res
        new = self.env['pb.letter.template'].with_context(active_test=False).browse(res['id'])
        vals = {}
        if not src.pbds_rules and src._pbdc_rules():
            vals['pbds_rules'] = src._pbdc_rules()
        if not src.pbds_page:
            vals['pbds_page'] = self._pbds_clean_page(src._pbdc_page())
        main_lang = src._pbds_main_lang()
        if not src.pbds_main_lang and main_lang != MAIN_LANG:
            vals['pbds_main_lang'] = main_lang
        # A copy of sample wording is still sample wording.
        if src.pbdc_sample:
            vals['pbdc_sample'] = True
        if vals:
            new.sudo().write(vals)
        return res
