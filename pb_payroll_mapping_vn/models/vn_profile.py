# -*- coding: utf-8 -*-
"""THE PROFILE: which Vietnam pay column reads from which record, and why.

ONE TABLE, READ BY EVERYTHING. The fields on `hr.employee` and `hr.contract`,
the mapping rows, the value-kind corrections and the pay-data spreadsheet that
carries what is left over are all generated from the constants below. Two lists
that are supposed to agree are two lists that will one day disagree, so there is
only this one — `tools/pb_vn_pay_data.py` imports it rather than restating it.

THE SORTING RULE THE OWNER SET (2026-09-11, revised the same day after seeing it
on screen). There are three homes and a column belongs to exactly one:

  * the monthly SPREADSHEET carries the DAYS AND THE HOURS, and nothing else;
  * an AMOUNT is a contract COMPONENT, edited on the person's contract and read
    from there by every run — see `CONTRACT_COMPONENTS`;
  * everything else — every yes/no, every count, every rate — is a FIELD on the
    employee or the contract, see `FIELD_MAPPING`.

Nothing else decides it; in particular, "it would be convenient" does not.

DELIBERATELY PLAIN PYTHON — no ``odoo`` import — so the spreadsheet builder and
the regression battery can read it without a database, exactly like
``component_code`` and ``pay_period`` next door.
"""

#: Employee-level facts. `(field name, type, label, help)`.
#:
#: All four flags are BOOLEANS even though the scheme's columns are written
#: "(1 = yes)": the engine coerces True to 1.0 the way Excel does
#: (`excel_semantics.coerce_number`), so the formula comparing against 1 keeps
#: working and the person editing the record gets a tick box instead of a digit.
EMPLOYEE_FIELDS = [
    ('pb_vn_is_local', 'boolean', 'Local employee',
     "Tick for a Vietnamese national. Foreign employees follow the "
     "expatriate insurance and allowance rules."),
    ('pb_vn_in_insurance', 'boolean', 'In the statutory insurance scheme',
     "Tick when social, health and unemployment insurance are deducted."),
    ('pb_vn_union_member', 'boolean', 'Union member',
     "Tick when union dues are deducted from pay."),
    ('pb_vn_tax_resident', 'boolean', 'Tax resident',
     "Untick for somebody taxed at the flat non-resident rate."),
    ('pb_vn_tax_commitment', 'boolean', 'Signed the single-employer tax commitment',
     "Tick when the employee has signed the commitment that this is their "
     "only employer."),
    ('pb_vn_enrol_family_health', 'boolean', 'Enrolled in family health cover',
     "Tick when the employee has taken the family premium health cover."),
    ('pb_vn_enrol_private_health', 'boolean', 'Enrolled in private health cover',
     "Tick when the employee has taken private health cover for themselves."),
    ('pb_vn_enrol_dep_health', 'boolean', 'Dependants on private health cover',
     "Tick when the employee's dependants are on the private health cover."),
]

#: Contract-level facts. Same shape. `float`/`integer` carry a default.
CONTRACT_FIELDS = [
    ('pb_vn_hours_per_day', 'float', 'Hours in a working day',
     "Used to turn a monthly salary into an hourly rate for overtime."),
    ('pb_vn_pay_grade', 'integer', 'Pay grade',
     "1, 2 or 3. Decides the transport and phone allowances."),
    ('pb_vn_annual_days', 'integer', 'Working days in a full year',
     "Used to spread annual entitlements across the year."),
    ('pb_vn_qual_other_exempt', 'boolean',
     'Other exempt reimbursement — evidence held',
     "Tick when the receipts that make the reimbursement tax-exempt are on file."),
    ('pb_vn_qual_leave_encash', 'boolean',
     'Leave encashment — evidence held',
     "Tick when the unused-leave payout qualifies for the exemption."),
    ('pb_vn_qual_transport', 'boolean',
     'Additional transportation — evidence held',
     "Tick when the extra transport payment qualifies for the exemption."),
    ('pb_vn_qual_ot_weekday', 'boolean',
     'Weekday overtime — exemption evidence held',
     "Tick when the premium part of weekday overtime is tax-exempt."),
    ('pb_vn_qual_ot_weekend', 'boolean',
     'Weekend overtime — exemption evidence held',
     "Tick when the premium part of weekend overtime is tax-exempt."),
    ('pb_vn_qual_ot_holiday', 'boolean',
     'Public-holiday overtime — exemption evidence held',
     "Tick when the premium part of holiday overtime is tax-exempt."),
    ('pb_vn_qual_night', 'boolean',
     'Night work — exemption evidence held',
     "Tick when the night-work premium is tax-exempt."),
    # Not an amount, so not a contract component; not a fact about the person,
    # so not on the employee. It is a standing approval on this contract.
    ('pb_vn_variable_bonus', 'boolean', 'Variable bonus approved',
     "Tick while this contract is approved for the variable bonus. It is read "
     "every run, so untick it when the approval lapses."),
]

#: THE MAPPING. `component code -> ('hr.employee'|'hr.contract', field name)`.
#:
#: Four of these point at fields that ALREADY EXIST and are not ours to invent:
#: `wage` and `dependents` on the contract are the payroll's own, and re-creating
#: them under a `pb_vn_` name would give one fact two homes.
FIELD_MAPPING = {
    # --- what the contract already says -------------------------------
    'BASIC':        ('hr.contract', 'wage'),
    'DEPS':         ('hr.contract', 'dependents'),
    # --- the contract facts this module adds ---------------------------
    'HOURSDAY':     ('hr.contract', 'pb_vn_hours_per_day'),
    'ROLEGRADE':    ('hr.contract', 'pb_vn_pay_grade'),
    'ANNUALDAYS':   ('hr.contract', 'pb_vn_annual_days'),
    'CONTRACTMTH':  ('hr.contract', 'pb_vn_contract_months'),
    'SERVDAYS':     ('hr.contract', 'pb_vn_service_days'),
    'OTHEREXMQUAL': ('hr.contract', 'pb_vn_qual_other_exempt'),
    'ALENCASHQUAL': ('hr.contract', 'pb_vn_qual_leave_encash'),
    'TRANSPADQUAL': ('hr.contract', 'pb_vn_qual_transport'),
    'OTWDQUAL':     ('hr.contract', 'pb_vn_qual_ot_weekday'),
    'OTWEQUAL':     ('hr.contract', 'pb_vn_qual_ot_weekend'),
    'OTHOLQUAL':    ('hr.contract', 'pb_vn_qual_ot_holiday'),
    'NIGHTPREQUAL': ('hr.contract', 'pb_vn_qual_night'),
    'PAIDVAR':      ('hr.contract', 'pb_vn_variable_bonus'),
    # --- the person facts ---------------------------------------------
    'ISLOCAL':      ('hr.employee', 'pb_vn_is_local'),
    'ISINSURED':    ('hr.employee', 'pb_vn_in_insurance'),
    'ISUNION':      ('hr.employee', 'pb_vn_union_member'),
    'ISRESIDENT':   ('hr.employee', 'pb_vn_tax_resident'),
    'TAXCOMMIT':    ('hr.employee', 'pb_vn_tax_commitment'),
    'ENROLPREM':    ('hr.employee', 'pb_vn_enrol_family_health'),
    'ENROLHLTH':    ('hr.employee', 'pb_vn_enrol_private_health'),
    'ENROLDEP':     ('hr.employee', 'pb_vn_enrol_dep_health'),
}

#: The two mapped fields that are COMPUTED rather than typed. Named here so the
#: writeback never tries to copy a spreadsheet value onto a field that has no
#: setter, and so the spreadsheet builder knows to leave them out.
COMPUTED_FIELDS = ('pb_vn_contract_months', 'pb_vn_service_days')

#: Every AMOUNT lives on the contract as a COMPONENT. `(code, label, upper bound)`.
#:
#: THE OWNER'S RULING, 2026-09-11: the monthly spreadsheet carries the days and
#: the hours and nothing else. Allowances, incentives, benefits and deductions
#: are properties of the person's contract, are edited there, and are read from
#: there by every pay run.
#:
#: They need no mapping row — the engine finds them by the scheme's own component
#: code (`payroll_import_batch._contract_component_amounts`) — only
#: `is_contract_component` on the column and a template for the per-contract line
#: to hang on.
#:
#: WHAT THIS COSTS, STATED ONCE HERE SO NOBODY HAS TO REDISCOVER IT. A contract
#: component is a STANDING amount: it is paid every month until somebody edits
#: the contract. That is exactly right for a uniform allowance or a health
#: premium, and it means a genuinely one-off item — the referral bonus, the
#: salary advance being repaid, a prior-period correction — keeps being applied
#: until it is cleared. The four marked `one-off` below are the ones to watch;
#: a scheme that wants them to lapse on their own needs a rule that clears them,
#: not a different rung of the ladder.
#:
#: The bounds are guard rails against a mistyped figure, not policy.
CONTRACT_COMPONENTS = [
    # --- standing, month after month ----------------------------------
    ('UNIFORM', 'Uniform allowance', 50000000.0),
    ('PRIVINSAMT', 'Private insurance allowance approved', 500000000.0),
    ('HLTHEEAMT', 'Private health premium — employee', 100000000.0),
    ('HLTHDEPAMT', 'Private health premium — dependants', 100000000.0),
    ('TRANSPADD', 'Additional transportation', 50000000.0),
    ('OTHERBEN', 'Other company benefits', 200000000.0),
    ('NONCASHBEN', 'Taxable non-cash benefit', 200000000.0),
    # --- earned, and usually recurring while the role lasts -----------
    ('LOGISINC', 'Logistics incentive', 200000000.0),
    ('AGROINC', 'Season agronomy incentive', 200000000.0),
    ('LAUNCHINC', 'New product launch incentive', 200000000.0),
    ('OTHERTAX', 'Other taxable allowance', 500000000.0),
    ('ALENCASH', 'Unused annual-leave encashment', 500000000.0),
    ('OTHEREXMP', 'Other exempt reimbursement', 200000000.0),
    # --- one-off: clear these once they have been paid ----------------
    ('REFERINC', 'Referral incentive', 100000000.0),
    ('ADVANCE', 'Salary advance recovery', 500000000.0),
    ('ADJADD', 'Prior-period addition', 500000000.0),
    ('ADJDEDAMT', 'Prior-period deduction approved', 500000000.0),
    ('PRIORDED', 'Prior-period deduction', 500000000.0),
    ('OTHERDED', 'Other deduction', 500000000.0),
]

#: The four whose amount should be cleared after the run that pays them.
#: Read by nothing yet; written down because the person who wonders "why is he
#: still repaying that advance" deserves to find the answer in one place.
ONE_OFF_COMPONENTS = ('REFERINC', 'ADVANCE', 'ADJADD', 'ADJDEDAMT',
                      'PRIORDED', 'OTHERDED')

#: Columns the scheme may not have at all, added when it does not.
#: `(code, label, column role, value kind, destination)`.
#:
#: A bank destination is not a field: four columns assemble ONE bank account,
#: which is why `hr.payslip.import.mapping` carries a `bank_role` for them
#: instead of a model and field pair.
EXTRA_COLUMNS = [
    ('EMPCODE', 'Employee code', 'identity', 'identifier',
     ('field', 'hr.employee', 'employee_id')),
    ('BANKACC', 'Bank account number', 'bank', 'identifier',
     ('bank', 'acc_number')),
    ('BANKNAME', 'Bank name', 'bank', 'text', ('bank', 'bank_name')),
    ('BANKBIC', 'Bank SWIFT code', 'bank', 'identifier', ('bank', 'bank_bic')),
    ('BANKHOLDER', 'Account holder name', 'bank', 'text',
     ('bank', 'acc_holder_name')),
]

#: Value kinds this profile corrects, and only these.
#:
#: A kind is load-bearing — it decides whether a value is coerced to a number at
#: all — so the profile touches the columns it is responsible for and leaves
#: every other column exactly as the starter shipped it. `integer` additionally
#: rounds, which is what stops a count coming back as `2.0000001`.
VALUE_KINDS = {
    'integer': (
        'DEPS', 'ROLEGRADE', 'ANNUALDAYS', 'CONTRACTMTH', 'SERVDAYS',
        'ISLOCAL', 'ISINSURED', 'ISUNION', 'ISRESIDENT', 'TAXCOMMIT',
        'ENROLPREM', 'ENROLHLTH', 'ENROLDEP', 'PAIDVAR',
        'OTHEREXMQUAL', 'ALENCASHQUAL', 'TRANSPADQUAL',
        'OTWDQUAL', 'OTWEQUAL', 'OTHOLQUAL', 'NIGHTPREQUAL',
    ),
    'quantity': (
        'STDDAYS', 'PAIDDAYS', 'HOURSDAY', 'HRSWD', 'HRSWE', 'HRSHOL',
        'HRSNIGHT',
    ),
}

# ======================================================================
#  What is left in the monthly spreadsheet
# ======================================================================
#
# THE FILE IS THE TIMESHEET AND NOTHING ELSE (owner's ruling, 2026-09-11).
#
# It carries the days and the hours, because those are the only things that are
# genuinely different for a person from one month to the next. Every AMOUNT —
# allowance, incentive, benefit, deduction — is a property of the contract and is
# read from there; see `CONTRACT_COMPONENTS`. Every yes/no is a property of the
# person or the contract and is read from there; see `FIELD_MAPPING`.
#
# Eight columns, of which a payroll clerk fills in six.

#: The days and hours. Different every run by definition.
SHEET_TIME_COLUMNS = [
    ('STDDAYS', 'Standard working days'),
    ('PAIDDAYS', 'Paid working days'),
    ('HRSWD', 'Weekday overtime — hours this run'),
    ('HRSWE', 'Weekend overtime — hours this run'),
    ('HRSHOL', 'Public-holiday overtime — hours this run'),
    ('HRSNIGHT', 'Night work — hours this run'),
]

#: Kept, and deliberately EMPTY. Every amount that used to be here is now a
#: contract component. The name survives because the sheet builder, the applier
#: and the tests all read it, and because "the file carries no amounts" is a
#: statement worth being able to point at.
SHEET_MONEY_COLUMNS = []

#: The header the importer keys the file on.
SHEET_KEY_COLUMN = ('EMPCODE', 'Employee code')

# ======================================================================
#  Reserved positions — the subtlest thing in this file
# ======================================================================
#
# THE TRAP. When a pay-data file arrives, the resolver tries each component's
# NAME, then its CODE, and then — if neither matched — the component's
# remembered COLUMN LETTER against the file's own columns. That last step is
# right for a file that IS the scheme's original workbook and wrong for one that
# is not, and the whole point of this profile is that the monthly file gets to be
# short: two dozen columns instead of a hundred and eleven.
#
# WHAT IT COST, MEASURED. On the first live run of the short file, `PAYMONTH`
# (the scheme's column F) read the sixth column of the new file and came back as
# *eight hours of weekend overtime*. The thirteenth-month bonus is written
# `IF(PAYMONTH=12, …)`; somebody who had worked twelve weekend hours would have
# been paid an extra month's salary — correctly according to the formula and
# absurdly according to anybody else, with nothing anywhere to flag it, because
# the component HAD a value and the formula DID run.
#
# WHY NOT JUST CLEAR THE LETTERS. Tried, and it is worse. The compiled formulas
# address some components BY LETTER — `GROSS` reads `values['AS']` for the
# uniform allowance — so a scheme with its letters cleared silently drops those
# components out of gross pay. The letter is load-bearing at run time; it is only
# the FILE's letters that must not be mistaken for it.
#
# THE FIX, THEREFORE, IS IN THE FILE. A column's letter is derived from its
# POSITION among the headers, so the sheet reserves the positions that belong to
# components it does not carry and leaves them empty. An empty cell resolves to
# nothing, which sends the component to where it should have gone all along — the
# contract, or the pay period. The columns are hidden, because they exist for the
# resolver rather than for the reader.
#
# `(scheme column letter, component code, the component's name)`.
RESERVED_POSITIONS = [
    ('F', 'PAYMONTH', 'Month being paid (1 to 12)'),
    ('W', 'PRIVINSAMT', 'Private insurance allowance approved'),
    ('X', 'HLTHEEAMT', 'Private health premium — employee'),
    ('Y', 'HLTHDEPAMT', 'Private health premium — dependants'),
]


def _letter_to_index(letter):
    """`A` -> 0, `Z` -> 25, `AA` -> 26."""
    index = 0
    for char in letter.upper():
        index = index * 26 + (ord(char) - 64)
    return index - 1


def sheet_layout():
    """Every position of the monthly file, in order, reserved ones included.

    Returns a list of `(code, label, reserved)`. The real columns fill the
    positions the reserved ones leave, in their own order; the arithmetic has to
    come out exactly, and it is asserted rather than assumed, because a silent
    off-by-one here reintroduces precisely the defect the reserved positions
    exist to prevent.

    ONLY THE RESERVATIONS THAT ARE STILL IN RANGE. A reservation protects a
    position the file actually occupies; one past the end of the file protects
    nothing, and honouring it anyway would pad an eight-column sheet out to
    twenty-five, seventeen of them blank. Which reservations are in range depends
    on the width, and the width depends on how many are in range — so it is
    settled by iteration rather than guessed. It converges in two passes and the
    loop is bounded so a bad reservation list cannot hang a build step.
    """
    all_reserved = {_letter_to_index(letter): (code, label)
                    for letter, code, label in RESERVED_POSITIONS}
    columns = sheet_columns()
    width = len(columns)
    reserved = {}
    for _pass in range(len(all_reserved) + 2):
        in_range = {i: v for i, v in all_reserved.items() if i < width}
        new_width = len(columns) + len(in_range)
        if new_width == width and in_range.keys() == reserved.keys():
            break
        reserved, width = in_range, new_width
    layout, queue = [], list(columns)
    for index in range(width):
        if index in reserved:
            code, label = reserved[index]
            layout.append((code, label, True))
        elif queue:
            code, label = queue.pop(0)
            layout.append((code, label, False))
        else:
            layout.append((None, '', True))
    assert not queue, 'the reserved positions do not leave room for every column'
    return layout


def sheet_codes():
    """Every component code the monthly file carries a column for."""
    return {code for code, _label in
            SHEET_TIME_COLUMNS + SHEET_MONEY_COLUMNS} | {SHEET_KEY_COLUMN[0]}


def sheet_columns():
    """Every column of the monthly pay-data file, in order.

    The employee code first because that is what each row is ABOUT, the name
    beside it because a person has to be able to read the file, then the time
    and the approved amounts.
    """
    return ([SHEET_KEY_COLUMN, ('EMPNAME', 'Employee name')]
            + SHEET_TIME_COLUMNS + SHEET_MONEY_COLUMNS)
