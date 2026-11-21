# -*- coding: utf-8 -*-
import logging
import re
from datetime import date

from odoo import _, api, models

from .newhire_approval import NEWHIRE_WRITE, require_hr

_logger = logging.getLogger(__name__)


def _opts(records, name_field='name'):
    return [{'id': r.id, 'name': getattr(r, name_field, False) or r.display_name} for r in records]


class PbPeopleRefs(models.AbstractModel):
    """Shared reference lists for the People wizards."""
    _name = 'pb.people.refs'
    _description = 'Payobook People wizard reference data'

    @api.model
    def _refs(self):
        env = self.env
        company = env.company
        structs = _opts(env['hr.payroll.structure'].search([], limit=100)) \
            if 'hr.payroll.structure' in env else []
        stypes = _opts(env['hr.payroll.structure.type'].search([], limit=100)) \
            if 'hr.payroll.structure.type' in env else []
        calendars = _opts(env['resource.calendar'].search(
            [('company_id', 'in', [company.id, False])], limit=50))
        return {
            'structures': structs,
            'structure_types': stypes,
            'calendars': calendars,
            'default_calendar': company.resource_calendar_id.id or (calendars[0]['id'] if calendars else False),
            'default_struct': structs[0]['id'] if structs else False,
            'currency': (company.currency_id.symbol or ''),
            'today': date.today().isoformat(),
        }


class PbOnboardWizard(models.AbstractModel):
    _name = 'pb.people.onboard.wizard'
    _description = 'Payobook guided employee onboarding'

    @api.model
    def get_defaults(self):
        env = self.env
        d = env['pb.people.refs']._refs()
        d.update({
            'departments': _opts(env['hr.department'].search([], limit=200)),
            'jobs': _opts(env['hr.job'].search([], limit=200)),
            'countries': _opts(env['res.country'].search([], limit=300)),
            # FS-16: the banks the bank check knows (typing another is fine)
            'banks': self._pb_bank_choices(),
            'bank_check': self._pb_bank_door_ready(),
        })
        return d

    # ------------------------------------------------------------------
    # FS-16 — the bank details typed here go through the product's normal
    # bank change path: ONE waiting change (`pb.bank.change.request`, the
    # import/hold door of pb_bank_ocr) that a second person approves, which
    # then writes the employee's bank account and the bank-file fields.
    # Before FS-16 they were written to the two old free-text boxes
    # (`account_number` / `bank_name`, pb_hr_payroll_formula) that nothing
    # reads, inside a bare `except: pass`. Never written straight, never to
    # the old boxes; a problem is said on the screen, never dropped.
    # ------------------------------------------------------------------
    #: the keys of the screen's bank section
    BANK_KEYS = ('bank_name', 'account_number', 'account_holder')

    @api.model
    def _pb_bank_door_ready(self):
        Req = self.env.get('pb.bank.change.request')
        return Req is not None and hasattr(Req, '_pb_hold_new_hire')

    @api.model
    def _pb_bank_choices(self):
        Registry = self.env.get('pb.bank.registry')
        if Registry is None:
            return []
        out, seen = [], set()
        for bank in Registry.sudo().search([('active', '=', True)], order='short_name, name'):
            value = (bank.short_name or bank.name or '').strip()
            if not value or value.lower() in seen:
                continue
            seen.add(value.lower())
            full = (bank.name or '').strip()
            out.append({'value': value,
                        'label': full if full and full.lower() != value.lower() else '',
                        'country': bank.country_id.code or 'VN'})
        return out

    @api.model
    def _pb_bank_entered(self, vals):
        """The bank section as typed: {'bank', 'number', 'holder'}, or None
        when every box was left empty."""
        vals = vals or {}
        bank = ' '.join(str(vals.get('bank_name') or '').split())
        number = str(vals.get('account_number') or '').strip()
        holder = ' '.join(str(vals.get('account_holder') or '').split())
        if not (bank or number or holder):
            return None
        return {'bank': bank, 'number': number, 'holder': holder}

    @api.model
    def _pb_bank_problem(self, bank):
        """'' when the typed bank details can be sent; else what to fix, in
        one sentence (the rule the bank check itself applies: 6 to 19
        digits; spaces, dashes and dots are tidied away)."""
        if not bank:
            return ''
        number = bank['number']
        if not number:
            return _("Type the account number too, or leave the bank details empty.")
        if re.search(r'[^0-9 .\-]', number):
            return _("The account number can only have digits (spaces and dashes are fine).")
        digits = re.sub(r'\D', '', number)
        if not 6 <= len(digits) <= 19:
            return _("The account number must be 6 to 19 digits. This one has %s.", len(digits))
        return ''

    @api.model
    def _pb_bank_outcome(self, state, message, reference=''):
        return {'state': state, 'message': message, 'reference': reference or ''}

    @api.model
    def _pb_send_bank(self, emp, bank, proposer):
        """Send the typed details for `emp` through the bank change path.
        Returns the outcome the screen shows: state 'sent' (waiting for a
        second person), 'check' (kept for HR to look at first, with the
        reason) or 'not_sent' (nothing made, with what to fix)."""
        problem = self._pb_bank_problem(bank)
        if problem:
            return self._pb_bank_outcome('not_sent', _(
                "The bank details were not sent: %s Add them from the employee's "
                "side panel (Pay & tax › Bank).", problem))
        if not self._pb_bank_door_ready():
            return self._pb_bank_outcome('not_sent', _(
                "The bank details were not sent: bank changes are not set up on "
                "this site. Ask your administrator."))
        values = {
            'x_account_number': re.sub(r'\D', '', bank['number']),
            'x_bank_name': bank['bank'],
            'x_account_name': bank['holder'] or emp.name or '',
        }
        try:
            with self.env.cr.savepoint():
                req = self.env['pb.bank.change.request']._pb_hold_new_hire(
                    emp, values, proposer)
        except Exception as exc:                # noqa: BLE001 — said on screen
            _logger.warning('pb_people_advanced: the new hire %s bank change could '
                            'not be made', emp.id, exc_info=True)
            why = str(getattr(exc, 'name', None) or (exc.args[0] if exc.args else '') or '')
            return self._pb_bank_outcome('not_sent', _(
                "The bank details were not sent: %s Add them from the employee's "
                "side panel (Pay & tax › Bank).", why or _("the bank check refused them.")))
        if not req:
            return self._pb_bank_outcome('not_sent', _(
                "The bank details were not sent. Add them from the employee's side "
                "panel (Pay & tax › Bank)."))
        if req.state in ('hr_review', 'finance_review'):
            return self._pb_bank_outcome('sent', _("Bank details sent for approval"),
                                         req.name)
        return self._pb_bank_outcome('check', _(
            "Bank details kept for HR to look at first: %s Open Compliance › Bank.",
            req.pb_decision_note or _("the bank check found a problem.")), req.name)

    @api.model
    def _pb_bank_note(self, emp, outcome):
        """A line on the employee's record when the details did not go through
        (the screen may be long closed when an approved request is carried
        out)."""
        if outcome and outcome.get('state') != 'sent' and emp:
            try:
                emp.sudo().message_post(body=outcome.get('message') or '')
            except Exception:                   # noqa: BLE001 — a note never blocks
                _logger.warning('pb_people_advanced: no note on employee %s', emp.id)

    @api.model
    def create_employee(self, vals):
        require_hr(self.env)
        Emp = self.env['hr.employee']
        evals = {'name': (vals.get('name') or '').strip()}
        if not evals['name']:
            return {'error': 'A name is required.'}
        bank = self._pb_bank_entered(vals)
        if not self.env.context.get(NEWHIRE_WRITE) \
                and 'pb.newhire.proposal' in self.env:
            # A problem with the bank details is said NOW, while HR is on the
            # screen; the person still goes ahead without them.
            problem = self._pb_bank_problem(bank)
            values = dict(vals)
            bank_note = ''
            if problem:
                for key in self.BANK_KEYS:
                    values.pop(key, None)
                bank_note = _("The bank details were not sent: %s Add them from the "
                              "employee's side panel (Pay & tax › Bank).", problem)
                bank = None
            answer = self.env['pb.newhire.proposal'].propose(
                'employee',
                _("Add %s to the payroll", evals['name']),
                payload={'values': values},
                facts={'wage': {'value': float(vals.get('wage') or 0.0),
                                'unit': self.env.company.currency_id.name
                                or ''},
                       'has_bank': {'value': bool(bank), 'unit': ''},
                       'contract_type': {
                           'value': str(vals.get('structure_type_id') or ''),
                           'unit': ''}},
                amount=float(vals.get('wage') or 0.0),
            ).answer()
            if not answer.get('applied'):
                out = dict(answer, employee_id=0, employee_name=evals['name'],
                           contract_id=0, error=None)
                if bank_note:
                    out['bank'] = self._pb_bank_outcome('not_sent', bank_note)
                elif bank:
                    out['bank'] = self._pb_bank_outcome('later', _(
                        "The bank details go with this request. When it is approved, "
                        "they are sent to a second person for approval."))
                return out
            out = dict(answer.get('result') or {},
                       reference=answer.get('reference'))
            if bank_note:
                out['bank'] = self._pb_bank_outcome('not_sent', bank_note)
                self._pb_bank_note(Emp.browse(int(out.get('employee_id') or 0)).exists(),
                                   out['bank'])
            return out
        for k_src, k_dst in [('job_id', 'job_id'), ('department_id', 'department_id'),
                             ('country_id', 'country_id')]:
            if vals.get(k_src):
                evals[k_dst] = int(vals[k_src])
        if vals.get('job_title'):
            evals['job_title'] = vals['job_title']
        # The manager, when the form was opened from the org chart.
        try:
            if vals.get('parent_id'):
                evals['parent_id'] = int(vals['parent_id'])
        except (TypeError, ValueError):
            pass
        if vals.get('work_email'):
            evals['work_email'] = vals['work_email']
        if vals.get('work_phone'):
            evals['work_phone'] = vals['work_phone']
        try:
            emp = Emp.create(evals)
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create employee.'}

        # FS-16: bank details → the bank change path (a second person
        # approves). Proposed by the person who typed them: here the caller;
        # an approved new-hire request strips them and sends them itself as
        # the person who asked (`pb.newhire.proposal._apply_employee`).
        bank_outcome = None
        if bank:
            bank_outcome = self._pb_send_bank(emp, bank, self.env.user)
            self._pb_bank_note(emp, bank_outcome)

        # first contract
        contract_id = False
        c_err = None
        if vals.get('with_contract'):
            res = self.env['pb.people.contract.wizard'].create_contract({
                'employee_id': emp.id,
                'wage': vals.get('wage'),
                'date_start': vals.get('date_start'),
                'date_end': vals.get('date_end'),
                'struct_id': vals.get('struct_id'),
                'structure_type_id': vals.get('structure_type_id'),
                'resource_calendar_id': vals.get('resource_calendar_id'),
                'activate': vals.get('activate'),
            })
            contract_id = res.get('contract_id')
            c_err = res.get('error')

        out = {'employee_id': emp.id, 'employee_name': emp.name,
               'contract_id': contract_id, 'error': c_err}
        if bank_outcome:
            out['bank'] = bank_outcome
        return out


class PbContractWizard(models.AbstractModel):
    _name = 'pb.people.contract.wizard'
    _description = 'Payobook guided contract creation'

    @api.model
    def get_defaults(self, employee_id=False, renew_from=False):
        env = self.env
        d = env['pb.people.refs']._refs()
        emp = env['hr.employee'].browse(int(employee_id)) if employee_id else None
        d['employee_id'] = emp.id if emp else False
        d['employee_name'] = emp.name if emp else ''
        # prefill from an existing contract being renewed
        if renew_from:
            c = env['hr.contract'].browse(int(renew_from))
            if c.exists():
                d['prefill'] = {
                    'wage': c.wage,
                    'struct_id': c.struct_id.id if getattr(c, 'struct_id', False) else False,
                    'structure_type_id': c.structure_type_id.id if c.structure_type_id else False,
                    'resource_calendar_id': c.resource_calendar_id.id if c.resource_calendar_id else d['default_calendar'],
                    # WDGAP S8-D (EX1): the pay lines the renewal carries,
                    # shown on the form so HR can change them before saving.
                    'lines': self._renewal_lines(c),
                }
                # WDGAP W3-B (RN1): the Vietnam contract kind the renewal
                # carries (never a trial), changeable on the form.
                kinds = self._vn_kinds()
                if kinds:
                    d['vn_kinds'] = kinds
                    d['prefill']['vn_kind'] = self._renewal_kind(c)
                    d['prefill']['vn_kind_show'] = bool(
                        (c.company_id.country_id.code or '') == 'VN'
                        or d['prefill']['vn_kind'] not in ('', 'indefinite'))
                # WDGAP W3-B follow-up (RN3): the Vietnam payroll treatment
                # "Permanent" is carried (never "Probation"), changeable too.
                if self._treat_field():
                    treat = self._renewal_treatment(c)
                    d['pay_treatments'] = [{'key': '', 'label': _("Not set")},
                                           {'key': 'permanent', 'label': _("Permanent")}]
                    d['prefill']['pay_treatment'] = treat
                    d['prefill']['pay_treatment_show'] = bool(
                        (c.company_id.country_id.code or '') == 'VN'
                        or c.sudo().pb_payroll_contract_type)
        return d

    # ------------------------------------------------------------------
    # WDGAP W3-B follow-up (owner ruling RN3) — a renewal copies the Vietnam
    # payroll treatment `pb_payroll_contract_type` ONLY when the old contract
    # says "permanent"; "probation" is never copied (the new contract stays
    # empty, as before). It is read by the Vietnam pay formula, so carrying
    # "permanent" keeps the renewed contract paid exactly like the old one.
    # HR can change it on the Renew form; "Make it permanent" is unchanged.
    # The field belongs to pb_employee_vault: probed.
    # ------------------------------------------------------------------
    @api.model
    def _pb_has_approved_bank(self, emp):
        """The approved bank account: the same two stores Payroll-ready reads
        (`pb_employee_form_tidy` `pb_bank_on_record` — the employee's bank
        account, or the Vietnamese bank file's account), read here directly
        so a write in the same request is seen."""
        person = emp.sudo()
        return bool(('bank_account_ids' in person._fields and person.bank_account_ids)
                    or ('vietnam_bank_account_number' in person._fields
                        and (person.vietnam_bank_account_number or '').strip()))

    @api.model
    def _treat_field(self):
        return self.env['hr.contract']._fields.get('pb_payroll_contract_type')

    @api.model
    def _renewal_treatment(self, contract):
        if not contract or not self._treat_field():
            return ''
        return 'permanent' if contract.sudo().pb_payroll_contract_type == 'permanent' else ''

    @api.model
    def _treatment_for_new(self, vals, old):
        if not self._treat_field():
            return ''
        if 'pay_treatment' in (vals or {}):
            return 'permanent' if vals.get('pay_treatment') == 'permanent' else ''
        return self._renewal_treatment(old) if old else ''

    # ------------------------------------------------------------------
    # WDGAP W3-B (owner ruling RN1) — a renewal copies the Vietnam contract
    # kind (`vietnam_contract_type`: fixed-term / open-ended / seasonal) from
    # the old contract; NEVER the trial: a "probation" kind is not copied, and
    # the separate Vietnam payroll treatment (`pb_payroll_contract_type`) has
    # its own rule (RN3, below: "permanent" only, never "probation"). HR can
    # change the kind on the Renew form; "Make it
    # permanent" asks for open-ended. The field belongs to the Vietnam payroll
    # module, so everything here is probed.
    # ------------------------------------------------------------------
    #: The kinds a renewal may carry, in screen words. "probation" is absent
    #: on purpose: a renewal is never a trial.
    VN_KINDS = ('definite', 'indefinite', 'seasonal')

    @api.model
    def _vn_kind_field(self):
        return self.env['hr.contract']._fields.get('vietnam_contract_type')

    @api.model
    def _vn_kinds(self):
        if not self._vn_kind_field():
            return []
        words = {'definite': _("Fixed-term"), 'indefinite': _("Open-ended"),
                 'seasonal': _("Seasonal")}
        return [{'key': key, 'label': words[key]} for key in self.VN_KINDS]

    @api.model
    def _renewal_kind(self, contract):
        """The kind a renewal of `contract` carries, or '' (the default)."""
        if not contract or not self._vn_kind_field():
            return ''
        value = contract.sudo().vietnam_contract_type or ''
        return value if value in self.VN_KINDS else ''

    @api.model
    def _kind_for_new(self, vals, old):
        """The kind to write on the new contract: what HR chose on the form
        (`vn_kind`), else the old contract's (renewal), else nothing."""
        if not self._vn_kind_field():
            return ''
        if 'vn_kind' in (vals or {}):
            chosen = vals.get('vn_kind') or ''
            return chosen if chosen in self.VN_KINDS else ''
        return self._renewal_kind(old) if old else ''

    # ------------------------------------------------------------------
    # WDGAP S8-D (EX1) — a renewal carries the old contract's pay lines.
    # Before this, a renewed contract started with none of them (meal,
    # phone…), so they read 0 on the next payslip unless HR typed them again.
    # ------------------------------------------------------------------
    @api.model
    def _renewal_lines(self, contract):
        """The old contract's pay lines, as the form shows them."""
        out = []
        lines = self.env['hr.contract.advantage'].sudo().search(
            [('contract_id', '=', contract.id)], order='id')
        for line in lines:
            template = line.advantage_template_id
            if not template:
                continue
            text = (line.text_value or '') if 'text_value' in line._fields else ''
            out.append({'template_id': template.id, 'code': template.code or '',
                        'name': template.name or template.code or '',
                        'amount': line.amount or 0.0, 'text': text})
        return out

    @api.model
    def _carry_renewal_lines(self, contract, old, typed=None):
        """Put the old contract's pay lines on the NEW one (get-or-create per
        pay item). ``typed`` — the amounts HR changed on the form, by pay
        item — win over the old ones. Each line written is logged in the
        pay-line trail, dated the new contract's start. Writes nothing on the
        old contract. Returns how many lines were written."""
        if not contract or not old:
            return 0
        overrides = {}
        for row in typed or []:
            try:
                overrides[int(row.get('template_id') or 0)] = row
            except (TypeError, ValueError, AttributeError):
                continue
        Line = self.env['hr.contract.advantage'].sudo()
        Change = self.env['hr.contract.advantage.change'].sudo() \
            if 'hr.contract.advantage.change' in self.env else None
        has_text = 'text_value' in Line._fields
        written = 0
        for row in self._renewal_lines(old):
            template_id = row['template_id']
            amount, text = row['amount'], row['text']
            if template_id in overrides:
                given = overrides[template_id]
                if given.get('drop'):
                    continue
                try:
                    amount = float(given.get('amount') if given.get('amount') is not None
                                   else amount)
                except (TypeError, ValueError):
                    pass
            if not amount and not text:
                continue
            line = Line.search([('contract_id', '=', contract.id),
                                ('advantage_template_id', '=', template_id)], limit=1)
            old_amount = line.amount if line else 0.0
            vals = {'amount': amount}
            if has_text and text:
                vals['text_value'] = text
            if line:
                if abs((line.amount or 0.0) - amount) < 1e-9 and \
                        (not has_text or (line.text_value or '') == (text or '')):
                    continue
                line.write(vals)
            else:
                Line.create(dict(vals, contract_id=contract.id,
                                 advantage_template_id=template_id))
            written += 1
            if Change is not None:
                try:
                    Change.log(contract,
                               self.env['hr.contract.advantage.template'].sudo().browse(template_id),
                               old_amount, amount, 'manual',
                               notes=_("Carried from %s", old.name or ''),
                               effective_date=contract.date_start,
                               old_text=None, new_text=text or None)
                except Exception:   # noqa: BLE001 — the trail never undoes a line
                    _logger.warning('pb_people_advanced: no trail row for the renewal '
                                    'line on contract %s', contract.id, exc_info=True)
        return written

    @api.model
    def create_contract(self, vals):
        require_hr(self.env)
        if not vals.get('employee_id'):
            return {'error': 'No employee selected.'}
        emp = self.env['hr.employee'].browse(int(vals['employee_id']))
        if not self.env.context.get(NEWHIRE_WRITE) \
                and 'pb.newhire.proposal' in self.env:
            answer = self.env['pb.newhire.proposal'].propose(
                'contract',
                _("Contract for %s", emp.name or ''),
                payload={'values': vals},
                facts={'wage': {'value': float(vals.get('wage') or 0.0),
                                'unit': self.env.company.currency_id.name
                                or ''},
                       # FS-16: an APPROVED bank account on record (the
                       # rule Payroll-ready reads), not the old box.
                       'has_bank': {'value': self._pb_has_approved_bank(emp),
                                    'unit': ''},
                       'contract_type': {
                           'value': str(vals.get('structure_type_id') or ''),
                           'unit': ''}},
                target=emp,
                subject_uids=emp.user_id.ids,
                amount=float(vals.get('wage') or 0.0),
            ).answer()
            if not answer.get('applied'):
                return dict(answer, contract_id=0, name='',
                            employee_id=emp.id, error=None)
            return dict(answer.get('result') or {},
                        reference=answer.get('reference'))
        cvals = {
            'employee_id': emp.id,
            'name': vals.get('name') or ('%s - %s' % (emp.name, vals.get('date_start') or date.today())),
            'wage': float(vals.get('wage') or 0.0),
            'date_start': vals.get('date_start') or str(date.today()),
        }
        if vals.get('date_end'):
            cvals['date_end'] = vals['date_end']
        if vals.get('struct_id'):
            cvals['struct_id'] = int(vals['struct_id'])
        if vals.get('structure_type_id'):
            cvals['structure_type_id'] = int(vals['structure_type_id'])
        cal = vals.get('resource_calendar_id') or self.env.company.resource_calendar_id.id
        if cal:
            cvals['resource_calendar_id'] = int(cal)
        # The contract this one renews — only a contract of the SAME person.
        old = self.env['hr.contract'].browse()
        if vals.get('renew_from'):
            old = self.env['hr.contract'].sudo().browse(int(vals['renew_from'] or 0)).exists()
            if old and old.employee_id != emp:
                old = self.env['hr.contract'].browse()
        # WDGAP W3-B (RN1): the Vietnam contract kind (chosen on the form, else
        # carried from the renewed contract; never a trial).
        kind = self._kind_for_new(vals, old)
        if kind:
            cvals['vietnam_contract_type'] = kind
        # WDGAP W3-B follow-up (RN3): "Permanent" payroll treatment carried.
        treatment = self._treatment_for_new(vals, old)
        if treatment:
            cvals['pb_payroll_contract_type'] = treatment
        # WDGAP W3-B (RN2): from now on a renewal made here is LINKED to the
        # contract it renews — the link the fixed-term counting reads (the
        # decision board already wrote it). Past renewals are not backfilled.
        if old and 'pb_renewed_from_id' in self.env['hr.contract']._fields:
            cvals['pb_renewed_from_id'] = old.id
        try:
            c = self.env['hr.contract'].create(cvals)
            if vals.get('activate'):
                c.write({'state': 'open'})
        except Exception as e:
            return {'error': str(getattr(e, 'name', None) or e) or 'Could not create contract.'}
        # WDGAP S8-D (EX1): a renewal carries the old contract's pay lines
        # (with any amount HR changed on the form). Only from a contract of the
        # SAME person; never fatal for the new contract.
        if old:
            if old.id != c.id:
                try:
                    with self.env.cr.savepoint():
                        self._carry_renewal_lines(c, old, vals.get('lines'))
                except Exception:   # noqa: BLE001
                    _logger.exception('pb_people_advanced: pay lines not carried from '
                                      'contract %s to %s', old.id, c.id)
        # `applied` is what the dialog reads to say "Contract created" rather
        # than "No contract exists yet": a route that applies at once hands
        # this dict back through `_apply_contract`, so it must say so itself.
        return {'contract_id': c.id, 'name': c.name, 'employee_id': emp.id,
                'error': None, 'applied': True}
