# -*- coding: utf-8 -*-
"""NEWHIRE P7 — a bank account in its own country's format, defined ONCE.

Owner request (2026-11-25): "depending on the country, also allow the user to
fill in e.g. IFSC if it is India, or code if it is Singapore, etc. Whatever is
the standard format of that country." And the standing rule: what HR can type,
the employee must be able to type too.

THE ONE DEFINITION. `pb.bank.format` is the only place that knows what a
country's bank details look like. Every screen that types bank details reads
it and every check runs through it:

  * People › Add employee, step 5 (`pb_new_hire`, `details_options`);
  * the employee's own bank page on My Payobook (`/my/details/bank/<id>`,
    `pb_me_details`, through `pb_portal_view`);
  * the Bank Verification screen the side panel opens ("Open Bank
    Verification", this module's cockpit, `get_request`);
  * the approval gate of every bank change (`_before_approval_transition`).

WHERE THE CODES LIVE. A request carries `pb_bank_format` (which country's
format it follows), `x_bank_code` and `x_branch_code` (new, the only stored
fields that were missing). On approval the code the bank files read is written
to ONE place: the account's own clearing code (`res.partner.bank.
clearing_number`, core), which the payment-list bank layouts already read
first (`pb_pay_delivery` `_pb_bank_identity`). SWIFT / BIC stays where it was
(`x_swift` → the bank record's `bic`). Nothing else is added.

OLD REQUESTS ARE UNCHANGED. A request without `pb_bank_format` (everything made
before this, and the import doors — the Updates sheet, a pay data file) keeps
the old rule exactly: 6 to 19 digits, no code asked. So nobody already on record
turns "not payroll-ready", and no import starts refusing rows.

Sources for the formats (checked 2026-11-25; the bank layouts this product
ships cite the same documents, `pb_pay_delivery/data/bank_layouts_world.xml`):
  India      IFSC, 11 characters, 4 letters + "0" + 6 letters/digits (RBI;
             ICICI "File Format for Bulk upload in CIB" v3.3)
  Singapore  4-digit bank code + 3-digit branch code (OCBC "ACH Bank and Branch
             Code Guide")
  Australia  BSB, 6 digits written NNN-NNN (APCA); the ABA file holds an
             account number of at most 9 digits
  Indonesia  3-digit bank code (Bank Indonesia's sandi bank)
  Thailand   4-digit branch code (Bank of Thailand branch list)
"""
import re

from odoo import _, api, models

from .vn_bank_dictionary import swift_ok

#: The countries with their own format, in the order the "Bank account in"
#: list offers them. Anything else is OTHER (IBAN accepted).
FORMAT_CODES = ('VN', 'ID', 'IN', 'SG', 'MY', 'TH', 'KH', 'AU')
OTHER = 'other'

#: The checks, by country — numbers only; words are built in `spec()`.
#:   account   (fewest, most) characters of the account number
#:   letters   the account may hold letters (an IBAN)
#:   branch    the free-text Branch box is offered
#:   swift     the optional SWIFT / BIC box is offered
#:   codes     the national codes: key, required, kind, length
RULES = {
    'VN': {'account': (6, 19), 'branch': True, 'swift': False, 'codes': ()},
    'ID': {'account': (8, 16), 'branch': True, 'swift': False,
           'codes': (('bank_code', False, 'digits', 3),)},
    'IN': {'account': (9, 18), 'branch': False, 'swift': False,
           'codes': (('branch_code', True, 'ifsc', 11),)},
    'SG': {'account': (7, 14), 'branch': False, 'swift': False,
           'codes': (('bank_code', True, 'digits', 4), ('branch_code', False, 'digits', 3))},
    'MY': {'account': (7, 17), 'branch': False, 'swift': True, 'codes': ()},
    'TH': {'account': (10, 12), 'branch': False, 'swift': False,
           'codes': (('branch_code', False, 'digits', 4),)},
    'KH': {'account': (6, 16), 'branch': False, 'swift': True, 'codes': ()},
    'AU': {'account': (5, 9), 'branch': False, 'swift': False,
           'codes': (('branch_code', True, 'bsb', 6),)},
    OTHER: {'account': (5, 34), 'letters': True, 'branch': True, 'swift': True, 'codes': ()},
}

#: Which code the bank files read (the account's clearing code), per country.
CLEARING = {
    'IN': ('branch_code',),
    'AU': ('branch_code',),
    'SG': ('bank_code', 'branch_code'),
    'ID': ('bank_code',),
    'TH': ('branch_code',),
}

#: Where a code is looked up in the bank directory (`pb.bank.registry.clearing_code`).
#:   bank_code: the directory's code IS the bank code (filled from the chosen bank)
#:   prefix:    the directory holds the first 4 letters of every IFSC of the bank
DIRECTORY = {'SG': 'bank_code', 'ID': 'bank_code', 'IN': 'prefix'}

_IFSC = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
_SEPARATORS = re.compile(r'[\s.\-/]')


def norm_code(kind, value):
    """A typed code as stored: IFSC upper-cased without spaces, a BSB as
    NNN-NNN, digits as digits. Anything else stays as typed (the check says
    what is wrong)."""
    text = str(value or '').strip()
    if not text:
        return ''
    if kind == 'ifsc':
        return _SEPARATORS.sub('', text).upper()
    squeezed = _SEPARATORS.sub('', text)
    if kind == 'bsb':
        return '%s-%s' % (squeezed[:3], squeezed[3:]) if re.fullmatch(r'\d{6}', squeezed) else text
    if kind == 'digits':
        return squeezed if squeezed.isdigit() else text
    return text


def norm_account(value, letters=False):
    """The account number as stored: separators gone; an IBAN upper-cased."""
    text = _SEPARATORS.sub('', str(value or '').strip())
    return text.upper() if letters else text


def code_ok(kind, length, value):
    if kind == 'ifsc':
        return bool(_IFSC.match(value or ''))
    if kind == 'bsb':
        return bool(re.fullmatch(r'\d{3}-\d{3}', value or ''))
    return bool(re.fullmatch(r'\d{%d}' % length, value or ''))


def format_code(code):
    """The format key of a country code: one of FORMAT_CODES, OTHER for any
    other country, '' for none (the old rule)."""
    if code == OTHER:
        return OTHER
    code = (code or '').strip().upper()
    if not code:
        return ''
    return code if code in FORMAT_CODES else OTHER


class PbBankFormat(models.AbstractModel):
    """The one definition of a country's bank details (see the module doc)."""
    _name = 'pb.bank.format'
    _description = 'Bank details by country'

    # ------------------------------------------------------------ words
    @api.model
    def _country_name(self, code):
        if code == OTHER:
            return _("Another country")
        country = self.env['res.country'].sudo().search([('code', '=', code)], limit=1)
        return country.name or code

    @api.model
    def choices(self):
        """`[{code, name}]` for the "Bank account in" list."""
        return [{'code': c, 'name': self._country_name(c)} for c in FORMAT_CODES] \
            + [{'code': OTHER, 'name': self._country_name(OTHER)}]

    @api.model
    def _code_words(self, code, key):
        """(label, hint, placeholder, missing sentence, bad sentence)."""
        if code == 'IN':
            return (_("IFSC code"),
                    _("11 characters, on the cheque book or in the bank app."),
                    'HDFC0001234',
                    _("Type the IFSC code. It is on the cheque book or in the bank app."),
                    _("The IFSC code is 11 characters: 4 letters, a zero, then 6 letters or digits."))
        if code == 'AU':
            return (_("BSB"),
                    _("6 digits, on the bank statement or in the bank app."),
                    '062-000',
                    _("Type the BSB. It is on the bank statement or in the bank app."),
                    _("The BSB is 6 digits, like 062-000."))
        if code == 'SG' and key == 'bank_code':
            return (_("Bank code"),
                    _("4 digits. Filled in from the bank when we know it."),
                    '7171',
                    _("Type the 4-digit bank code."),
                    _("The bank code is 4 digits."))
        if code == 'SG':
            return (_("Branch code"),
                    _("3 digits, if the bank asks for one."),
                    '081',
                    _("Type the 3-digit branch code."),
                    _("The branch code is 3 digits."))
        if code == 'ID':
            return (_("Bank code"),
                    _("3 digits. Filled in from the bank when we know it."),
                    '014',
                    _("Type the 3-digit bank code."),
                    _("The bank code is 3 digits."))
        if code == 'TH':
            return (_("Branch code"),
                    _("4 digits, on the passbook. Optional."),
                    '0001',
                    _("Type the 4-digit branch code."),
                    _("The branch code is 4 digits."))
        return (key, '', '', '', '')

    @api.model
    def _account_hint(self, code, low, high, letters):
        if letters:
            return _("%(low)s to %(high)s letters and digits. An IBAN is fine.", low=low, high=high)
        return _("%(low)s to %(high)s digits.", low=low, high=high)

    @api.model
    def _banks(self, code):
        """The directory's banks of this country (Vietnam: the original rows
        with no country), as `[{value, label, code}]`."""
        if code == OTHER:
            return []
        Registry = self.env['pb.bank.registry'].sudo()
        out, seen = [], set()
        for bank in Registry.search(Registry._country_domain(code), order='short_name, name'):
            value = (bank.short_name or bank.name or '').strip()
            if not value or value.lower() in seen:
                continue
            seen.add(value.lower())
            full = (bank.name or '').strip()
            out.append({'value': value,
                        'label': full if full and full.lower() != value.lower() else '',
                        'code': (bank.clearing_code or '').strip()})
        return out[:200]

    # ------------------------------------------------------------ the definition
    @api.model
    def spec(self, code, banks=True):
        """Everything a screen needs to draw and check one country's bank
        details, JSON-plain. `code` is a country code or 'other'; empty = the
        old rule (Vietnam's: 6 to 19 digits, no code)."""
        fmt = format_code(code)
        rule = RULES[fmt or 'VN']
        low, high = rule['account']
        letters = bool(rule.get('letters'))
        codes = []
        for key, required, kind, length in rule['codes']:
            label, hint, placeholder, missing, bad = self._code_words(fmt, key)
            codes.append({
                'key': key, 'label': label, 'hint': hint, 'placeholder': placeholder,
                'required': bool(required), 'kind': kind, 'length': length,
                'max': 7 if kind == 'bsb' else (length + 2 if kind == 'digits' else length + 3),
                'missing': missing, 'bad': bad,
            })
        return {
            'code': fmt,
            'name': self._country_name(fmt) if fmt else '',
            'account': {
                'min': low, 'max': high, 'letters': letters,
                'hint': self._account_hint(fmt, low, high, letters),
                'missing': _("Type the account number."),
                'bad_chars': _("The account number can only have letters and digits.") if letters
                else _("The account number can only have digits (spaces and dashes are fine)."),
            },
            'branch': bool(rule['branch']),
            'swift': {
                'label': _("SWIFT / BIC"),
                'hint': _("Optional. 8 or 11 letters and digits, for payments from abroad."),
                'bad': _("The SWIFT / BIC code is 8 or 11 letters and digits."),
            } if rule['swift'] else False,
            'codes': codes,
            'directory': DIRECTORY.get(fmt, ''),
            'banks': self._banks(fmt or 'VN') if banks else [],
        }

    @api.model
    def specs(self, banks=True):
        """`{code: spec}` for every country in the "Bank account in" list."""
        return {c['code']: self.spec(c['code'], banks=banks) for c in self.choices()}

    @api.model
    def for_employee(self, employee):
        """Which format an employee's bank details follow by default: their
        Country of Work. '' when it is not set — the old rule, so nobody
        without a Country of Work is asked anything new."""
        emp = employee.sudo() if employee else employee
        code = ''
        if emp and 'payroll_country' in emp._fields:
            code = emp.payroll_country or ''
        return format_code(code)

    # ------------------------------------------------------------ the check
    @api.model
    def check(self, code, values):
        """`(clean, problems)` for typed bank details.

        `values` keys (all optional): bank_name, bank_branch, account_holder,
        account_number, bank_code, branch_code, swift. `clean` holds the same
        keys as they are stored; `problems` = `{key: sentence}` for what must
        be fixed, in screen order (the first one is what a screen says first).
        """
        spec = self.spec(code, banks=False)
        values = values or {}
        clean, problems = {}, {}

        def text(key, limit=120):
            return ' '.join(str(values.get(key) or '').split())[:limit]

        clean['bank_name'] = text('bank_name')
        clean['bank_branch'] = text('bank_branch') if spec['branch'] else ''
        clean['account_holder'] = text('account_holder')
        fmt = spec['code']
        for item in spec['codes']:
            value = norm_code(item['kind'], values.get(item['key']))
            if not value and item['key'] == 'bank_code' and DIRECTORY.get(fmt) == 'bank_code' \
                    and clean['bank_name']:
                # the bank directory knows this bank's code (Singapore,
                # Indonesia): filled in, as the screens do
                found = self.env['pb.bank.registry'].sudo().match(clean['bank_name'], country=fmt)
                value = (found.clearing_code or '').strip() if found else ''
            clean[item['key']] = value
            if not value:
                if item['required']:
                    problems[item['key']] = item['missing']
            elif not code_ok(item['kind'], item['length'], value):
                problems[item['key']] = item['bad']
        acc = spec['account']
        raw = str(values.get('account_number') or '').strip()
        number = norm_account(raw, acc['letters'])
        clean['account_number'] = number
        if not number:
            problems['account_number'] = acc['missing']
        elif (acc['letters'] and not number.isalnum()) or (not acc['letters'] and not number.isdigit()):
            problems['account_number'] = acc['bad_chars']
        elif not acc['min'] <= len(number) <= acc['max']:
            problems['account_number'] = (
                _("The account number must be %(low)s to %(high)s letters and digits. "
                  "This one has %(n)s.", low=acc['min'], high=acc['max'], n=len(number))
                if acc['letters'] else
                _("The account number must be %(low)s to %(high)s digits. This one has %(n)s.",
                  low=acc['min'], high=acc['max'], n=len(number)))
        swift = norm_code('ifsc', values.get('swift')) if spec['swift'] else ''
        clean['swift'] = swift
        if swift and not swift_ok(swift):
            problems['swift'] = spec['swift']['bad']
        ordered = {}
        for key in ('bank_name', 'bank_code', 'branch_code', 'account_number', 'swift'):
            if key in problems:
                ordered[key] = problems[key]
        return clean, ordered

    @api.model
    def first_problem(self, code, values):
        """'' or the first sentence to fix (a screen's one-line answer)."""
        _clean, problems = self.check(code, values)
        return next(iter(problems.values()), '')

    @api.model
    def clearing(self, code, clean):
        """The code the bank files read for this account (the account's own
        clearing code), or ''. Singapore: bank code + branch code."""
        parts = [str((clean or {}).get(k) or '') for k in CLEARING.get(format_code(code), ())]
        if format_code(code) == 'SG' and not parts[0]:
            return ''
        return ''.join(parts)

    @api.model
    def bank_from_code(self, code, value):
        """India: the bank whose IFSCs start with these 4 letters, when the
        directory knows it → `{value, label}` or False."""
        fmt = format_code(code)
        if DIRECTORY.get(fmt) != 'prefix':
            return False
        prefix = (value or '').strip().upper()[:4]
        if len(prefix) < 4:
            return False
        for bank in self._banks(fmt):
            if bank['code'].upper() == prefix:
                return {'value': bank['value'], 'label': bank['label']}
        return False
