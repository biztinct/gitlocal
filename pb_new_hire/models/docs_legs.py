# -*- coding: utf-8 -*-
"""NEWHIRE P3a — the step 5 legs of an approved studio hire, and what the
waiting hire holds (handover §2.4–§2.6).

Three welcome legs run after `own_fields` and before the sign-in, each in its
own savepoint (the P2 runner, `welcome_legs.py`):

    details   ONE write of the typed values on the employee (sudo, no
              tracking mails), each value checked again (NH8: a payload is
              replayed later, by another person); the ID number goes to its
              second store where payroll reads one (VN, SG); a Vietnam tax
              code is copied to the running contract as pb_me_tax's approval
              does (`_pbtx_vn_contract_copy`)
    papers    each file HR attached becomes a `pb.employee.document` through
              the side panel's own call (`pb.people.vault_upload_batch`,
              HR-gated, the applier is HR); the held attachment is dropped;
              `verified` stays False — HR verifies on the record
    asks      one `pb.new.hire.ask` row per "Ask <first name>" item

The bank account is NOT a leg: the old path sends it, unchanged, from
`pb.newhire.proposal._apply_employee` after the person exists (FS-16). Its
outcome is added to the legs as a row so the done card shows it.

FILES. A waiting hire holds its papers as `ir.attachment` rows of the
proposal (sudo, never public), listed in `pb_nh_files` — never in
`payload_json` / `result_json`, chatter or logs. They die with the
proposal's withdraw, reject and return. The fast lane applies inside
`propose`, before any proposal id could hold them, so `send` hands the files
to that one call through the context key `pb_nh_files`.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .studio import FILES_CTX
from .studio_docs import ID_TWIN, SECRET_FIELDS, mask
from .welcome_legs import LETTER_CTX, LegFailed

_logger = logging.getLogger(__name__)

#: "This apply is of that proposal" (the papers leg reads its held files).
PROPOSAL_CTX = 'pb_nh_proposal_id'

#: Every employee field the details leg may write (the step 5 item fields).
DETAIL_FIELDS = (
    'birthday', 'sex', 'private_street', 'private_city', 'private_phone',
    'emergency_contact', 'emergency_phone', 'identification_id',
    'vietnam_tax_code', 'pb_npwp_number', 'pb_in_pan_number',
    'pb_id_ptkp_status', 'pb_in_tax_regime', 'pb_sg_shg_fund',
    'pb_bpjs_employment_number', 'pb_bpjs_health_number',
    'vietnam_social_insurance_number', 'pb_in_uan_number', 'pb_in_esi_number',
)


#: Employee field → the running contract's own copy of it (FACTS_ONBOARD
#: §E). The VN tax code is pb_me_tax's precedent; the HR-kept numbers follow
#: it (P3b, architect answer b). Written only where the contract has the field.
CONTRACT_COPY = (
    ('vietnam_tax_code', 'vietnam_tax_code'),
    ('vietnam_social_insurance_number', 'vietnam_social_insurance_number'),
    ('pb_in_uan_number', 'uan_number'),
    ('pb_in_esi_number', 'esi_number'),
    ('singapore_nric_fin', 'singapore_nric_fin'),
)


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class PbNewHireHeld(models.AbstractModel):
    """`send`'s side: which files go with the hire."""
    _inherit = 'pb.new.hire'

    @api.model
    def _held_files(self, vals, files):
        """`{key: {name, mime, data, issue_date, expiry_date, category_id,
        label}}` for the papers the values list (already checked)."""
        by_key = self._files_by_key(files)
        out = {}
        for paper in vals.get('pb_nh_papers') or []:
            row = by_key.get(paper['key'])
            if not row:
                continue
            out[paper['key']] = {
                'name': str(row.get('name') or paper['label'])[:200],
                'mime': row.get('mime'), 'data': row.get('data'),
                'issue_date': row.get('issue_date') or False,
                'expiry_date': row.get('expiry_date') or False,
                'category_id': paper['category_id'], 'label': paper['label'],
            }
        return out


class PbNewHireLegsDocs(models.AbstractModel):
    _inherit = 'pb.new.hire.legs'

    # ================================================================ details
    @api.model
    def _leg_details(self, employee, values, state):
        details = values.get('pb_nh_details') or {}
        if not isinstance(details, dict) or not details:
            return False
        code = values.get('payroll_country') or ''
        Studio = self.env['pb.new.hire']
        items = Studio._detail_items(code, self._first(employee))
        known = {f['name']: f for item in items for f in item['fields']}
        write, refused = {}, []
        for name, value in details.items():
            field = known.get(name)
            if name not in DETAIL_FIELDS or not field or name not in employee._fields:
                _logger.debug('new hire: detail %s dropped (not asked for %s)', name, code)
                continue
            clean, problem = Studio._check_value(code, field, value)
            if problem:
                refused.append('%s: %s' % (field['label'], problem))
                continue
            write[name] = clean
        twin = ID_TWIN.get(code)
        if write.get('identification_id') and twin and twin in employee._fields:
            write[twin] = write['identification_id']
        if write:
            employee.with_context(tracking_disable=True).write(write)
        # the running contract's own copies (the VN tax code as pb_me_tax's
        # approval copies it; P3b answer b: the HR-kept numbers too)
        contract = state.get('contract')
        if contract:
            copy = {theirs: write[mine] for mine, theirs in CONTRACT_COPY
                    if write.get(mine) and theirs in contract._fields
                    and contract[theirs] != write[mine]}
            if copy:
                contract.sudo().with_context(mail_notrack=True, tracking_disable=True).write(copy)
        if refused:
            raise LegFailed('; '.join(refused))
        n = len([k for k in write if k != twin])
        return _("1 detail") if n == 1 else _("%s details", n)

    # ================================================================ papers
    @api.model
    def _held(self):
        """The files of this apply: the fast lane's context, else the
        proposal's held attachments. → ({key: file}, attachments)."""
        files = self.env.context.get(FILES_CTX)
        if isinstance(files, dict) and files:
            return files, self.env['ir.attachment']
        proposal = self.env['pb.newhire.proposal'].sudo().browse(
            _int(self.env.context.get(PROPOSAL_CTX))).exists()
        out, atts = {}, self.env['ir.attachment'].sudo()
        for key, row in (proposal.pb_nh_files or {}).items() if proposal else []:
            att = atts.browse(_int(row.get('attachment_id'))).exists()
            if not att or att.res_model != proposal._name or att.res_id != proposal.id:
                continue
            out[key] = dict(row, data=att.datas, mime=att.mimetype, name=att.name)
            atts |= att
        return out, atts

    @api.model
    def _leg_papers(self, employee, values, state):
        papers = values.get('pb_nh_papers') or []
        if not papers:
            return False
        files, held = self._held()
        People = self.env['pb.people']
        filed, missing = 0, []
        for paper in papers:
            row = files.get(paper['key'])
            category = self.env['pb.employee.document.category'].sudo().browse(
                _int(paper.get('category_id'))).exists()
            if not row or not row.get('data') or not category:
                missing.append(paper.get('label') or '')
                continue
            data = row['data']
            data = data.decode() if isinstance(data, bytes) else data
            # the side panel's own call: HR-gated, its rules, one savepoint
            People.vault_upload_batch(employee.id, category.id, [{
                'payload': {'name': row.get('name') or paper['label'], 'title': paper['label'],
                            'mime': row.get('mime'), 'data': data},
                'issue_date': row.get('issue_date') or False,
                'expiry_date': row.get('expiry_date') or False,
            }])
            filed += 1
        if held:
            held.unlink()
        if missing:
            raise LegFailed(_("the file of %s was no longer there.", ', '.join(missing)))
        return _("1 paper") if filed == 1 else _("%s papers", filed)

    # ================================================================ asks
    @api.model
    def _leg_asks(self, employee, values, state):
        asks = values.get('pb_nh_asks') or []
        if not asks or 'pb.new.hire.ask' not in self.env:
            return False
        Ask = self.env['pb.new.hire.ask'].sudo()
        have = set(Ask.search([('employee_id', '=', employee.id)]).mapped('key'))
        proposal = _int(self.env.context.get(PROPOSAL_CTX))
        rows = Ask.browse()
        for ask in asks:
            if not isinstance(ask, dict) or not ask.get('key') or ask['key'] in have:
                continue
            category = self.env['pb.employee.document.category'].sudo().browse(
                _int(ask.get('category_id'))).exists()
            rows |= Ask.create({
                'employee_id': employee.id, 'key': str(ask['key'])[:64],
                'label': str(ask.get('label') or ask['key'])[:200],
                'label_kind': ask.get('kind') if ask.get('kind') in ('item', 'card', 'number')
                else 'item',
                'need': ask.get('need') if ask.get('need') in ('first_pay', 'joining', 'optional')
                else 'optional',
                'url': str(ask.get('url') or '')[:200], 'sequence': _int(ask.get('sequence')) or 10,
                'category_id': category.id or False,
                'company_id': employee.company_id.id or self.env.company.id,
                'proposal_id': proposal or False,
            })
            have.add(ask['key'])
        rows.refresh()
        n = len(rows)
        first = self._first(employee)
        return _("1 thing to ask %s for", first) if n == 1 else \
            _("%(n)s things to ask %(first)s for", n=n, first=first)


class PbNewHireProposalDocs(models.Model):
    _inherit = 'pb.newhire.proposal'

    #: {item key: {attachment_id, category_id, label, issue_date, expiry_date}}
    pb_nh_files = fields.Json(string='Papers held for a waiting hire', copy=False,
                              readonly=True, groups='hr.group_hr_user')

    # ------------------------------------------------------------ holding
    def _pb_nh_hold_files(self, held):
        """Keep the files of a WAITING hire as private attachments of it."""
        self.ensure_one()
        Att = self.env['ir.attachment'].sudo()
        out = {}
        for key, row in (held or {}).items():
            att = Att.create({'name': row.get('name') or row.get('label') or _("Document"),
                              'datas': row['data'], 'mimetype': row.get('mime'),
                              'res_model': self._name, 'res_id': self.id, 'public': False})
            out[key] = {'attachment_id': att.id, 'category_id': row.get('category_id'),
                        'label': row.get('label') or '', 'issue_date': row.get('issue_date') or False,
                        'expiry_date': row.get('expiry_date') or False}
        self.sudo().write({'pb_nh_files': out})
        return out

    def _pb_nh_drop_files(self):
        for proposal in self.sudo():
            ids = [_int(r.get('attachment_id')) for r in (proposal.pb_nh_files or {}).values()]
            atts = self.env['ir.attachment'].sudo().browse([i for i in ids if i]).exists() \
                .filtered(lambda a: a.res_model == proposal._name and a.res_id == proposal.id)
            atts.unlink()
            if proposal.pb_nh_files:
                proposal.write({'pb_nh_files': False})
        return True

    def _approval_withdraw(self, request, reason):
        res = super()._approval_withdraw(request, reason)
        self._pb_nh_drop_files()
        return res

    def _approval_reject(self, request, reason):
        res = super()._approval_reject(request, reason)
        self._pb_nh_drop_files()
        return res

    def _approval_return(self, request, reason):
        res = super()._approval_return(request, reason)
        self._pb_nh_drop_files()
        return res

    # ------------------------------------------------------------ the apply
    def _apply_employee(self):
        """The approved write (P1/FS-16 path, unchanged) with this proposal
        named for the papers leg, then the bank outcome as a leg row."""
        values = self._pb_nh_values()
        if values is None:
            return super()._apply_employee()
        answer = super(PbNewHireProposalDocs, self.with_context(**{PROPOSAL_CTX: self.id})) \
            ._apply_employee()
        self._pb_nh_drop_files()
        bank = answer.get('bank') if isinstance(answer, dict) else None
        legs = list(answer.get('legs') or [])
        if bank and legs is not None:
            ok = bank.get('state') == 'sent'
            row = {'key': 'bank', 'ok': ok,
                   'message': _("bank account waiting for a second approval") if ok
                   else (bank.get('message') or '')}
            at = next((i + 1 for i, leg in enumerate(legs) if leg.get('key') == 'details'), 0)
            legs.insert(at, row)
            done = [leg['message'] for leg in legs if leg.get('ok')]
            answer = dict(answer, legs=legs,
                          legs_summary=_("Ready: %s.", ', '.join(done)) if done else '')
        return answer

    # ------------------------------------------------------------ the rows
    def _pb_nh_welcome_rows(self, values, names):
        rows = super()._pb_nh_welcome_rows(values, names)

        def add(label, value):
            if value not in (None, '', False, []):
                rows.append((label, '', value))

        for label, text in names.get('details') or []:
            add(label, text)
        if values.get('account_number'):
            add(_('Bank'), values.get('bank_name'))
            fmt = values.get('bank_format')
            if fmt and 'pb.bank.format' in self.env:
                # P7: the account's country and its codes, in that country's words
                Format = self.env['pb.bank.format']
                add(_('Bank account in'), dict((c['code'], c['name']) for c in Format.choices()).get(fmt))
                spec = Format.spec(fmt, banks=False)
                for code in spec['codes']:
                    add(code['label'], values.get(code['key']))
                if spec['swift']:
                    add(spec['swift']['label'], values.get('bank_swift'))
                add(_('Branch'), values.get('bank_branch'))
            add(_('Account holder'), values.get('account_holder'))
            add(_('Account number'), mask(''.join(c for c in str(values['account_number']) if c.isalnum())))
        add(_('Papers attached'), ', '.join(p.get('label') or '' for p in values.get('pb_nh_papers') or []))
        add(_('Will be asked'), ', '.join(a.get('label') or '' for a in values.get('pb_nh_asks') or []))
        add(_('Left for later'), ', '.join(names.get('later') or []))
        return rows


class PbContractsLetterNewHire(models.AbstractModel):
    """The studio's contract letter (P3a architect decision): the person who
    approved the hire approved this wage, so the letter may print it — for
    the one call the letter leg makes (`LETTER_CTX`)."""
    _inherit = 'pb.contracts'

    def _cd_unmask_wage(self):
        if self.env.context.get(LETTER_CTX):
            return True
        return super()._cd_unmask_wage()
