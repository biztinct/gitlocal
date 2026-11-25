# -*- coding: utf-8 -*-
"""NEWHIRE P7 — a bank change carries its country's codes (see
`bank_formats.py` for the one definition and why).

Three stored fields are added, the only ones that were missing:
  pb_bank_format   which country's format the details follow (empty on every
                   request made before this and on the import doors: the old
                   rule, exactly as before)
  x_bank_code      Singapore 4 digits, Indonesia 3 digits
  x_branch_code    India IFSC, Australia BSB, Singapore 3 digits, Thailand 4

On approval the code the bank files read is written to the account's own
clearing code (`res.partner.bank.clearing_number`), the one place the
payment-list bank layouts read first. Nothing is written anywhere else.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .bank_formats import FORMAT_CODES, OTHER, format_code, norm_code

_logger = logging.getLogger(__name__)

#: The codes a request can carry, and where each is typed (portal, cockpit,
#: an import / new-hire hold).
CODE_FIELDS = ('x_bank_code', 'x_branch_code')
#: request field → key of `pb.bank.format.check` values
CHECK_KEYS = {
    'x_bank_name': 'bank_name', 'x_bank_branch': 'bank_branch',
    'x_account_name': 'account_holder', 'x_account_number': 'account_number',
    'x_bank_code': 'bank_code', 'x_branch_code': 'branch_code', 'x_swift': 'swift',
}


class PbBankChangeRequestFormat(models.Model):
    _inherit = 'pb.bank.change.request'

    pb_bank_format = fields.Selection(
        selection='_pb_format_selection',
        string='Bank account in', copy=False,
        help="Which country's bank details these are: the codes asked for and "
             "the account number's length follow it. Empty on older changes, "
             "which keep the old check.")
    x_bank_code = fields.Char(string='Bank code', copy=False)
    x_branch_code = fields.Char(string='Branch code', copy=False)

    @api.model
    def _pb_format_selection(self):
        """The country names in the reader's language (`res.country`)."""
        return [(c['code'], c['name']) for c in self.env['pb.bank.format'].choices()]

    def _pb_formatted(self):
        """A change the country rules apply to. Vietnam's rules ARE the old
        rule (6 to 19 digits, no code), so a Vietnamese change keeps the old
        checks and sentences exactly."""
        self.ensure_one()
        return bool(self.pb_bank_format) and self.pb_bank_format != 'VN'

    # ------------------------------------------------------------ create
    @api.model_create_multi
    def create(self, vals_list):
        """A change typed on a screen follows the person's Country of Work
        when it does not say otherwise; an import keeps the old rule."""
        Format = self.env['pb.bank.format']
        for vals in vals_list:
            if 'pb_bank_format' not in vals and vals.get('pb_origin') != 'import' \
                    and vals.get('employee_id'):
                emp = self.env['hr.employee'].sudo().browse(vals['employee_id']).exists()
                fmt = Format.for_employee(emp) if emp else ''
                if fmt:
                    vals['pb_bank_format'] = fmt
            self._pb_norm_codes(vals)
        return super().create(vals_list)

    def write(self, vals):
        if any(k in vals for k in CODE_FIELDS + ('x_swift', 'pb_bank_format')):
            vals = dict(vals)
            fmt = vals.get('pb_bank_format') if 'pb_bank_format' in vals \
                else (self[:1].pb_bank_format if len(self) == 1 else None)
            self._pb_norm_codes(vals, fmt)
        return super().write(vals)

    @api.model
    def _pb_norm_codes(self, vals, fmt=None):
        """Codes as stored (IFSC upper case, BSB NNN-NNN, digits), whatever
        door typed them."""
        fmt = format_code(fmt if fmt is not None else vals.get('pb_bank_format'))
        spec = self.env['pb.bank.format'].spec(fmt, banks=False) if fmt else None
        kinds = {c['key']: c['kind'] for c in (spec or {}).get('codes', [])}
        for field, key in (('x_bank_code', 'bank_code'), ('x_branch_code', 'branch_code')):
            if vals.get(field):
                vals[field] = norm_code(kinds.get(key, 'digits'), vals[field]) or False
        if vals.get('x_swift'):
            vals['x_swift'] = norm_code('ifsc', vals['x_swift']) or False
        return vals

    # ------------------------------------------------------------ the check
    def _pb_check_values(self):
        self.ensure_one()
        return {key: self[field] or '' for field, key in CHECK_KEYS.items()}

    def _pb_format_problems(self):
        """`{key: sentence}` of the shared check — only for a change that
        follows a country's own format (older and Vietnamese changes: the
        old check, nothing new)."""
        self.ensure_one()
        if not self._pb_formatted():
            return {}
        _clean, problems = self.env['pb.bank.format'].check(
            self.pb_bank_format, self._pb_check_values())
        return problems

    def _pb_format_problem(self):
        """'' or what must be fixed before this change can be sent or
        approved (the base rule for older and Vietnamese changes)."""
        self.ensure_one()
        if not self._pb_formatted():
            return super()._pb_format_problem()
        return next(iter(self._pb_format_problems().values()), '')

    def _before_approval_transition(self, to_state):
        """Sending a change in a country's format needs that country's codes
        and a number of the right length (IFSC for India, BSB for
        Australia …) — said in one sentence, never a half-checked send."""
        if to_state == 'hr_review':
            for rec in self:
                rec = rec.sudo()
                if rec._pb_formatted() and rec.x_account_number:
                    problem = rec._pb_format_problem()
                    if problem:
                        raise UserError(problem)
        return super()._before_approval_transition(to_state)

    def action_validate(self):
        res = super().action_validate()
        Registry = self.env['pb.bank.registry']
        for rec in self:
            if not rec._pb_formatted():
                continue
            problems = rec._pb_format_problems()
            msgs = list(problems.values())
            vals = {'v_format_ok': not problems}
            fmt = rec.pb_bank_format
            if fmt != OTHER and rec.x_bank_name:
                # the bank of THIS country (the base reads the Vietnamese
                # directory only)
                bank = Registry.match(rec.x_bank_name, country=fmt)
                vals['resolved_bank_id'] = bank.id or False
                if not bank and Registry.search_count(Registry._country_domain(fmt), limit=1):
                    msgs.append(_("Bank not recognised in the registry."))
            elif fmt == OTHER:
                vals['resolved_bank_id'] = False
            vals['v_format_msg'] = ' '.join(msgs) or _("All format checks passed.")
            rec._sys_write(vals)
        return res

    # ------------------------------------------------------------ the master
    def _pb_clearing_code(self):
        self.ensure_one()
        if not self.pb_bank_format:
            return ''
        clean, _problems = self.env['pb.bank.format'].check(
            self.pb_bank_format, self._pb_check_values())
        return self.env['pb.bank.format'].clearing(self.pb_bank_format, clean)

    def _pb_mirror_to_accounts(self, emp, new):
        """The account's own clearing code = this change's code (IFSC, BSB,
        Singapore bank + branch code, Indonesian bank code, Thai branch code):
        the one place the bank files read it."""
        account = super()._pb_mirror_to_accounts(emp, new)
        code = self._pb_clearing_code()
        if account and code and 'clearing_number' in account._fields \
                and (account.clearing_number or '') != code:
            account.sudo().write({'clearing_number': code})
        return account

    # ------------------------------------------------------------ words
    def _pb_code_rows(self):
        """`[(label, value)]` of this change's codes, in its country's words."""
        self.ensure_one()
        if not self.pb_bank_format:
            return []
        spec = self.env['pb.bank.format'].spec(self.pb_bank_format, banks=False)
        out = []
        for item in spec['codes']:
            value = self['x_%s' % item['key']]
            if value:
                out.append((item['label'], value))
        if spec['swift'] and self.x_swift:
            out.append((spec['swift']['label'], self.x_swift))
        return out

    def _pb_codes_line(self):
        self.ensure_one()
        return ' · '.join('%s %s' % (label, value) for label, value in self._pb_code_rows())

    def _approval_detail(self, request):
        """The approval card shows the country and the codes too."""
        out = super()._approval_detail(request)
        if self.pb_bank_format:
            rows = list(out.get('rows') or [])
            name = dict(self._pb_format_selection()).get(self.pb_bank_format, '')
            extra = [{'head': _('Bank account in'), 'sub': '', 'cells': ['', name], 'tone': 'off'}]
            for label, value in self._pb_code_rows():
                extra.append({'head': label, 'sub': '', 'cells': [_('Empty'), value], 'tone': 'on'})
            at = next((i + 1 for i, r in enumerate(rows) if r.get('head') == _('Bank')), 1)
            out = dict(out, rows=rows[:at] + extra + rows[at:])
        return out

    def _chain_revision_values(self):
        """A code changed after somebody said yes means another account: it is
        stamped too — only when there is one, so the stamp of every older
        change stays what it was."""
        values = super()._chain_revision_values()
        for field in CODE_FIELDS + ('pb_bank_format',):
            if self[field]:
                values[field] = self[field]
        return values

    def _ocr_schema(self):
        schema = super()._ocr_schema()
        schema['fields'] = list(schema['fields']) + [
            {'name': 'x_branch_code', 'label': 'Branch / routing code', 'type': 'code',
             'hint': 'IFSC (India, 11 characters), BSB (Australia, 6 digits) or the branch '
                     'code, if printed'},
            {'name': 'x_bank_code', 'label': 'Bank code', 'type': 'code',
             'hint': 'the national bank code (Singapore 4 digits, Indonesia 3 digits), if printed'},
        ]
        return schema

    # ------------------------------------------------------------ My Payobook
    def pb_portal_view(self):
        out = super().pb_portal_view()
        rec = self.sudo()
        Format = self.env['pb.bank.format']
        fmt = rec.pb_bank_format or ''
        out.update({
            'format_code': fmt,
            'format': Format.spec(fmt) if fmt else False,
            'formats': Format.choices(),
            'bank_code': rec.x_bank_code or '',
            'branch_code': rec.x_branch_code or '',
            'swift': rec.x_swift or '',
            'code_rows': [{'label': label, 'value': value} for label, value in rec._pb_code_rows()],
        })
        return out

    def pb_portal_set_format(self, fmt):
        """The employee changes which country their account is in, while the
        change is a draft (their own request only — the caller checks)."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state != 'draft':
            return rec
        code = fmt if fmt in FORMAT_CODES or fmt == OTHER else False
        rec.write({'pb_bank_format': code})
        rec.action_validate()
        return rec
