# -*- coding: utf-8 -*-
"""Column role classification — the single source of truth for "what is this column FOR?".

A salary structure imported from a spreadsheet is a flat wall of columns: the employee
code, the bank account, the joining date and the actual pay components all arrive with
the same shape and the same amount of ceremony. Everything downstream then has to
re-guess which is which, which is why the identity-marker tuple used to exist in three
separate copies inside `payroll_import_batch.py`.

This module is that guess, made once. It is DELIBERATELY plain Python — no `odoo`
import, no model class, stdlib only — so the wizards, the import batch, the upgrade
migration and the studio RPC can all share one answer, and so the table of expected
classifications in `tests/test_column_role_classifier.py` can be run with a bare
`python3` without a database.

Bias, decided at design time (CR-A6): a column we cannot place stays **payroll**. A
column wrongly left in payroll is clutter in the Formula Studio; a payroll column
wrongly filed as reference is a missing pay line. Clutter is recoverable.
"""

import datetime
import difflib
import re
import unicodedata

# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------
ROLE_PAYROLL = 'payroll'
ROLE_IDENTITY = 'identity'
ROLE_PROFILE = 'profile'
ROLE_CONTRACT = 'contract'
ROLE_BANK = 'bank'
ROLE_REFERENCE = 'reference'

ROLES = (
    ROLE_PAYROLL,
    ROLE_IDENTITY,
    ROLE_PROFILE,
    ROLE_CONTRACT,
    ROLE_BANK,
    ROLE_REFERENCE,
)

TIER_CERTAIN = 'certain'
TIER_LIKELY = 'likely'
TIER_DEFAULT = 'default'

# The one true copy. `payroll_import_batch.py` used to carry three identical
# private tuples; they now import this name.
EMPLOYEE_CODE_MARKERS = ('MSNV', 'EMP CODE', 'EMPLOYEE CODE', 'EMPLOYEE ID', 'EMPLOYEEID')

# Header candidates used by the batch when it fishes an employee code out of a raw
# row. Kept verbatim (same strings, same order) so behaviour is unchanged — this is
# now the definition and the batch imports it.
EMPLOYEE_CODE_HEADER_CANDIDATES = (
    'employee_code', 'employee code', 'emp_code', 'emp code', 'emp. code', 'empcode',
    'employee_id', 'employee id', 'emp_id', 'emp id', 'empid', 'employee no', 'employee number',
    'staff id', 'staff code', 'code', 'id', 'msnv', 'ma nv', 'manv', 'ma so nhan vien',
)

# The primary-key variant (`_find_primary_key_header`) orders and spells a few entries
# differently and adds the id-number aliases. Preserved exactly.
PRIMARY_KEY_HEADER_CANDIDATES = (
    'employee_code', 'employee code', 'emp_code', 'emp code', 'emp. code', 'empcode',
    'employee id', 'employee_id', 'emp id', 'empid', 'employee no', 'employee number',
    'staff id', 'staff code',
    'id no', 'id_no', 'id',
    'msnv', 'ma nv', 'manv', 'ma so nhan vien',
)

# Zoho-shaped rows carry their own spellings.
EXTERNAL_CODE_HEADER_CANDIDATES = (
    'employee_code', 'employee code', 'emp_code', 'emp code',
    'EmployeeID', 'employee_id', 'emp_id',
    'staff id', 'staff code', 'code', 'id',
)

EMPLOYEE_NAME_HEADER_CANDIDATES = ('employee_name', 'name', 'full_name', 'emp_name')

EXTERNAL_NAME_HEADER_CANDIDATES = (
    'employee_name', 'name', 'full_name', 'emp_name',
    'FirstName', 'Display Name',
)

# --------------------------------------------------------------------------
# Lexicons
#
# Order matters: BANK is consulted before PROFILE so "Bank Name" cannot be dragged
# into PROFILE by the word "name", and every list is matched on the NORMALISED form
# (see `normalize_header`) plus an accent-stripped alias, so "Ngày vào làm" and
# "Ngay vao lam" land in the same place.
# --------------------------------------------------------------------------

IDENTITY_HEADERS = (
    'employee code', 'employee codes', 'emp code', 'empcode', 'employee id', 'emp id',
    'empid', 'employee no', 'employee number', 'employee num', 'staff id', 'staff code',
    'staff no', 'staff number', 'personnel number', 'personnel no', 'payroll id',
    'payroll number', 'badge id', 'badge number', 'barcode',
    'employee name', 'full name', 'fullname', 'display name', 'staff name',
    'name', 'first name', 'last name', 'middle name', 'given name', 'surname',
    'id no', 'id number', 'identity card', 'identity card no', 'identification',
    'identification no', 'identification number', 'national id', 'citizen id',
    'passport', 'passport no', 'passport number',
    # Vietnamese
    'msnv', 'ma nv', 'manv', 'ma nhan vien', 'ma so nhan vien',
    'mã nv', 'mã nhân viên', 'mã số nhân viên',
    'ho ten', 'ho va ten', 'ten nhan vien', 'ten day du',
    'họ tên', 'họ và tên', 'tên nhân viên', 'tên đầy đủ',
    'cmnd', 'cccd', 'so cmnd', 'so cccd', 'số cmnd', 'số cccd',
    'can cuoc cong dan', 'căn cước công dân', 'chung minh nhan dan',
    'chứng minh nhân dân', 'ho chieu', 'hộ chiếu',
)

PROFILE_HEADERS = (
    'phone', 'phone no', 'phone number', 'mobile', 'mobile no', 'mobile number',
    'telephone', 'contact number', 'contact no',
    'email', 'email address', 'work email', 'personal email', 'private email',
    'gender', 'sex', 'marital status', 'marital', 'date of birth', 'birth date',
    'birthday', 'dob', 'place of birth', 'nationality', 'religion',
    'address', 'home address', 'permanent address', 'current address',
    'department', 'division', 'section', 'team', 'business unit',
    'job title', 'job position', 'position', 'designation', 'job grade', 'grade',
    'employee status', 'employment status', 'staff status', 'status',
    'work location', 'location', 'work place', 'workplace', 'site',
    'cost center', 'cost centre', 'manager', 'line manager', 'reports to',
    'supervisor', 'tax code', 'tax id', 'tax number',
    'social insurance no', 'social insurance number', 'social insurance code',
    # Vietnamese
    'so dien thoai', 'số điện thoại', 'dien thoai', 'điện thoại',
    'gioi tinh', 'giới tính', 'tinh trang hon nhan', 'tình trạng hôn nhân',
    'ngay sinh', 'ngày sinh', 'noi sinh', 'nơi sinh', 'quoc tich', 'quốc tịch',
    'dia chi', 'địa chỉ', 'phong ban', 'phòng ban', 'bo phan', 'bộ phận',
    'chuc vu', 'chức vụ', 'chuc danh', 'chức danh', 'noi lam viec', 'nơi làm việc',
    'ma so thue', 'mã số thuế', 'so bhxh', 'số bhxh', 'so so bhxh',
    'trang thai', 'trạng thái', 'trang thai nhan vien', 'trạng thái nhân viên',
)

CONTRACT_HEADERS = (
    'date of joining', 'joining date', 'join date', 'date joined', 'doj',
    'hire date', 'date of hire', 'hired on', 'start date', 'date start',
    'contract start', 'contract start date', 'effective date',
    'end date', 'date end', 'contract end', 'contract end date',
    'last working day', 'last day of work', 'last day', 'leaving date',
    'resignation date', 'termination date', 'date of leaving',
    'contract type', 'contract status', 'contract no', 'contract number',
    'contract reference', 'employment type', 'employment contract',
    'probation', 'probation end', 'probation end date', 'probation period',
    'working schedule', 'work schedule', 'schedule pay',
    # Vietnamese
    'ngay vao lam', 'ngày vào làm', 'ngay vao cong ty', 'ngày vào công ty',
    'ngay bat dau', 'ngày bắt đầu', 'ngay ket thuc', 'ngày kết thúc',
    'ngay nghi viec', 'ngày nghỉ việc', 'ngay lam viec cuoi cung',
    'ngày làm việc cuối cùng', 'loai hop dong', 'loại hợp đồng',
    'so hop dong', 'số hợp đồng', 'hop dong lao dong', 'hợp đồng lao động',
    'ngay thu viec', 'ngày thử việc', 'thoi gian thu viec', 'thời gian thử việc',
)

BANK_HEADERS = (
    'bank', 'bank name', 'bank code', 'bank account', 'bank account no',
    'bank account number', 'bank acct', 'bank acc', 'bank acc no',
    'account no', 'account number', 'account', 'acct no', 'acc no', 'a c',
    'a c no', 'bank branch', 'branch', 'branch name', 'branch code',
    'swift', 'swift code', 'bic', 'iban', 'ifsc', 'ifsc code',
    'beneficiary', 'beneficiary name', 'beneficiary account',
    'account holder', 'account holder name', 'payment method',
    # Vietnamese
    'so tai khoan', 'số tài khoản', 'stk', 'tai khoan ngan hang',
    'tài khoản ngân hàng', 'ngan hang', 'ngân hàng', 'ten ngan hang',
    'tên ngân hàng', 'chi nhanh', 'chi nhánh', 'ten chu tai khoan',
    'tên chủ tài khoản', 'chu tai khoan', 'chủ tài khoản',
)

# Priority order for both exact and fuzzy resolution.
_LEXICON_ORDER = (
    (ROLE_IDENTITY, IDENTITY_HEADERS),
    (ROLE_BANK, BANK_HEADERS),
    (ROLE_CONTRACT, CONTRACT_HEADERS),
    (ROLE_PROFILE, PROFILE_HEADERS),
)

# Fuzzy matching is only allowed on entries long enough that a 0.82 similarity means
# something. "id" or "a c" would otherwise swallow half the workbook.
_MIN_FUZZY_LENGTH = 5
_FUZZY_THRESHOLD = 0.82

_PUNCT_RE = re.compile(r'[^\w\s]|_', re.UNICODE)
_WS_RE = re.compile(r'\s+', re.UNICODE)
_LEADING_ZERO_INT_RE = re.compile(r'^[+-]?0\d+$')


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------
def normalize_header(value):
    """Casefold, drop punctuation/underscores, collapse whitespace. Diacritics are
    PRESERVED — "Mã nhân viên" stays itself; the accent-stripped alias is built
    separately so both spellings resolve without conflating unrelated words."""
    if value is None:
        return ''
    text = unicodedata.normalize('NFC', str(value))
    text = text.casefold()
    text = _PUNCT_RE.sub(' ', text)
    return _WS_RE.sub(' ', text).strip()


def strip_accents(text):
    """Accent-stripped alias key. `đ`/`Đ` do not decompose under NFD, so they are
    mapped by hand — without that, "hợp đồng" and "hop dong" never meet."""
    if not text:
        return ''
    text = text.replace('đ', 'd').replace('Đ', 'd')
    decomposed = unicodedata.normalize('NFD', text)
    return ''.join(ch for ch in decomposed if unicodedata.category(ch) != 'Mn')


def _index_key(value):
    return strip_accents(normalize_header(value))


def _build_index():
    """First lexicon in priority order wins a contested key (e.g. "branch" is bank,
    not profile), so a later list can never quietly steal an earlier one's term."""
    exact = {}
    fuzzy = []
    for role, entries in _LEXICON_ORDER:
        for entry in entries:
            key = _index_key(entry)
            if not key:
                continue
            exact.setdefault(key, role)
            if len(key) >= _MIN_FUZZY_LENGTH:
                fuzzy.append((key, role))
    return exact, tuple(fuzzy)


_EXACT_INDEX, _FUZZY_INDEX = _build_index()


# --------------------------------------------------------------------------
# Sample-value inspection
# --------------------------------------------------------------------------
def _coerce_number(text):
    """Best-effort numeric read of a spreadsheet string, tolerant of the comma
    decimal separator and of thousands grouping."""
    cleaned = text.replace(' ', '').replace(' ', '')
    if cleaned.endswith('%'):
        cleaned = cleaned[:-1]
    if not cleaned:
        return None
    candidates = [cleaned]
    if ',' in cleaned:
        if '.' in cleaned:
            candidates.append(cleaned.replace(',', ''))
        else:
            candidates.append(cleaned.replace(',', '.'))
            candidates.append(cleaned.replace(',', ''))
    for candidate in candidates:
        try:
            return float(candidate)
        except (TypeError, ValueError):
            continue
    return None


def is_blank_sample(value):
    """Empty cells carry no signal and must never be counted as "all text"."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def is_texty_sample(value):
    """True when a sample value is genuinely TEXT rather than a number wearing a
    string. The load-bearing case is the leading-zero integer: "0071000123456" is a
    bank account, and float()-ing it destroys the very digit that says so."""
    if is_blank_sample(value):
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return False
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return True
    text = str(value).strip()
    if not text:
        return False
    if _LEADING_ZERO_INT_RE.match(text.replace(' ', '')):
        return True
    return _coerce_number(text) is None


# --------------------------------------------------------------------------
# Lookup
# --------------------------------------------------------------------------
def _marker_hit(header):
    """Uppercase substring test, matching the batch's historic heuristic exactly."""
    if not header:
        return False
    token = str(header).upper()
    return any(marker in token for marker in EMPLOYEE_CODE_MARKERS)


def has_employee_code_marker(header):
    """Public name for the marker test — the migration and the batch both ask it."""
    return _marker_hit(header)


def _exact_lookup(normalized):
    if not normalized:
        return None
    return _EXACT_INDEX.get(strip_accents(normalized))


def _fuzzy_lookup(normalized):
    key = strip_accents(normalized)
    if len(key) < _MIN_FUZZY_LENGTH:
        return None, 0.0
    best_role, best_ratio = None, 0.0
    matcher = difflib.SequenceMatcher()
    matcher.set_seq2(key)
    for entry, role in _FUZZY_INDEX:
        matcher.set_seq1(entry)
        if matcher.real_quick_ratio() < _FUZZY_THRESHOLD:
            continue
        if matcher.quick_ratio() < _FUZZY_THRESHOLD:
            continue
        ratio = matcher.ratio()
        if ratio >= _FUZZY_THRESHOLD and ratio > best_ratio:
            best_role, best_ratio = role, ratio
    return best_role, best_ratio


def lexicon_role(header):
    """(role, tier) from header text alone, or (None, None). Used by the migration,
    which has no sample values to lean on."""
    normalized = normalize_header(header)
    if not normalized:
        return None, None
    exact = _exact_lookup(normalized)
    if exact:
        return exact, TIER_CERTAIN
    role, _ratio = _fuzzy_lookup(normalized)
    if role:
        return role, TIER_LIKELY
    return None, None


# --------------------------------------------------------------------------
# The classifier
# --------------------------------------------------------------------------
def classify_column(header, column_type='input', is_contract_component=False,
                    is_text_component=False, on_identifier_row=False, band_label=None,
                    sample_values=None, is_referenced=False):
    """Return ``(role, tier, reason)`` for one spreadsheet column.

    First hit wins, in the order below; the reason string is human-readable because
    it is destined for a studio tooltip in a later phase.

    `is_referenced` (this column's code appears in another column's formula) and a
    non-input `column_type` are absolute: a column somebody's arithmetic depends on
    is a payroll column no matter what its header says.
    """
    samples = [v for v in (sample_values or []) if not is_blank_sample(v)]

    if column_type and column_type != 'input':
        return ROLE_PAYROLL, TIER_CERTAIN, 'calculated column — always payroll'

    if is_referenced:
        return ROLE_PAYROLL, TIER_CERTAIN, 'used by a formula — always payroll'

    if is_text_component:
        return ROLE_CONTRACT, TIER_CERTAIN, 'explicit text component'

    if is_contract_component:
        if samples and any(is_texty_sample(v) for v in samples):
            return ROLE_CONTRACT, TIER_CERTAIN, 'text component (inferred from sample values)'
        return ROLE_PAYROLL, TIER_CERTAIN, 'amount component'

    if on_identifier_row:
        return ROLE_IDENTITY, TIER_CERTAIN, 'sits on the employee identifier row'

    if _marker_hit(header):
        return ROLE_IDENTITY, TIER_CERTAIN, 'header carries an employee code marker'

    normalized = normalize_header(header)

    exact = _exact_lookup(normalized)
    if exact:
        return exact, TIER_CERTAIN, 'header matches a known %s column' % exact

    fuzzy_role, ratio = _fuzzy_lookup(normalized)
    if fuzzy_role:
        return fuzzy_role, TIER_LIKELY, 'header resembles a known %s column (%.0f%%)' % (
            fuzzy_role, ratio * 100)

    if band_label:
        band_role = _exact_lookup(normalize_header(band_label))
        if band_role:
            return band_role, TIER_LIKELY, 'sits under the "%s" category band' % band_label

    if samples and all(is_texty_sample(v) for v in samples):
        return ROLE_REFERENCE, TIER_LIKELY, 'every sample value is text'

    return ROLE_PAYROLL, TIER_DEFAULT, 'no signal — payroll by policy'


def role_rule_defaults(role):
    """The `hr.formula.rule` values a freshly classified role implies, at CREATE time.

    A column that is not a payroll column is not a pay line and not a grid column, so
    it starts hidden from both. Deliberately never applied to a rule that already
    exists: whatever visibility somebody chose for it is theirs, not ours.
    """
    role = role or ROLE_PAYROLL
    values = {'column_role': role, 'column_role_source': 'auto'}
    if role != ROLE_PAYROLL:
        values['appears_on_payslip'] = False
        values['is_visible_in_grid'] = False
    return values


def classify_rule_values(name, data_source_field=None, **kwargs):
    """Convenience wrapper: try the rule's label first, fall back to the raw source
    header it was imported from. Rules get renamed; `data_source_field` remembers
    what the spreadsheet actually said."""
    role, tier, reason = classify_column(name, **kwargs)
    if role == ROLE_PAYROLL and tier == TIER_DEFAULT and data_source_field \
            and normalize_header(data_source_field) != normalize_header(name):
        alt_role, alt_tier, alt_reason = classify_column(data_source_field, **kwargs)
        if alt_tier != TIER_DEFAULT:
            return alt_role, alt_tier, alt_reason
    return role, tier, reason
