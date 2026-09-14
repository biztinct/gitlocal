# -*- coding: utf-8 -*-
"""Read the approval matrix a business already wrote in a spreadsheet.

EVERY payroll implementation has one of these. A tab called "Approval Matrix",
ten rows, columns for the maker, the reviewer, the final approver, the named
people, a threshold, an SLA and a control. It is agreed with the customer
before anything is configured, and until now it was retyped into the Matrix by
hand, one route at a time, by somebody reading across a spreadsheet.

WHAT THIS DOES. Reads that sheet and turns each row into a DRAFT route with
the steps the row describes, plus a list of what it could not resolve. It is a
head start, not a configuration:

  * **nothing is published.** Every route it makes is a draft, and somebody
    presses Publish after reading it.
  * **no account is ever guessed from a name.** "Nithya (HR Manager)" becomes
    a PROPOSED person — a line in People & backups that says where it came
    from and asks somebody to pick the real account. Matching a login to a
    first name is exactly the kind of clever that puts the wrong person in an
    approval chain.
  * **a threshold becomes a note, never a condition.** "<=200 h/person/year"
    is a rule about overtime that this product expresses somewhere else; a
    condition invented from that text would be a silent lie about what the
    route checks.
  * **an unknown row still lands.** A row this does not recognise is mapped to
    "Other request" and listed, rather than dropped.

THE SYNONYM TABLES ARE DATA, DELIBERATELY. They are the vocabulary of payroll
implementations, not of this codebase, and they grow every time a customer
writes something new. They are plain dicts at the top of this file so adding
one is a one-line change with no thinking attached.
"""

import base64
import io
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: The sheet this reads. Compared case-insensitively, with spaces squeezed.
SHEET_NAME = 'Approval Matrix'

#: The eleven columns the shape has. Only the first five are load-bearing.
COLUMNS = ('stage', 'object', 'maker', 'reviewer', 'final', 'named',
           'backup', 'threshold', 'sla', 'status', 'evidence')

#: Header text -> our column key. Everything is lower-cased and squeezed to
#: single spaces before it is looked up.
HEADER_SYNONYMS = {
    'stage': 'stage',
    'step': 'stage',
    'transaction / object': 'object',
    'transaction/object': 'object',
    'transaction': 'object',
    'object': 'object',
    'process': 'object',
    'maker role': 'maker',
    'maker': 'maker',
    'preparer': 'maker',
    'reviewer role': 'reviewer',
    'reviewer': 'reviewer',
    'checker': 'reviewer',
    'final approver role': 'final',
    'final approver': 'final',
    'approver': 'final',
    'named approver': 'named',
    'named approvers': 'named',
    'backup / delegate': 'backup',
    'backup/delegate': 'backup',
    'backup': 'backup',
    'delegate': 'backup',
    'threshold / limit': 'threshold',
    'threshold/limit': 'threshold',
    'threshold': 'threshold',
    'limit': 'threshold',
    'sla': 'sla',
    'turnaround': 'sla',
    'setup status': 'status',
    'status': 'status',
    'evidence / control': 'evidence',
    'evidence/control': 'evidence',
    'evidence': 'evidence',
    'control': 'evidence',
}

#: What the row is ABOUT -> the catalogue key. Matched on the longest phrase
#: that appears in the cell, so "Draft payroll run" beats "payroll".
PROCESS_SYNONYMS = {
    'employee master change': 'master',
    'employee master': 'master',
    'master data': 'master',
    'salary/contract change': 'paychange',
    'salary and contract': 'paychange',
    'salary change': 'paychange',
    'pay change': 'paychange',
    'contract change': 'contract',
    'contract extension': 'extension',
    'timesheet and leave': 'timesheet',
    'timesheet': 'timesheet',
    'leave': 'leave',
    'time off': 'leave',
    'overtime': 'overtime',
    'incentive/bonus': 'awards',
    'incentive': 'awards',
    'bonus': 'awards',
    'award': 'awards',
    'draft payroll run': 'payrun',
    'payroll run': 'payrun',
    'pay run': 'payrun',
    'funding and payroll journal': 'journal',
    'payroll journal': 'journal',
    'journal': 'journal',
    'bank file creation': 'bankfile',
    'bank file': 'bankfile',
    'bank payment release': 'release',
    'payment release': 'release',
    'bank release': 'release',
    'reopen / off-cycle payroll': 'reopen',
    'reopen': 'reopen',
    'off-cycle': 'reopen',
    'off cycle': 'reopen',
    'final settlement': 'fnf',
    'full and final': 'fnf',
    'statutory filing': 'filing',
    'filing': 'filing',
    'new hire': 'newhire',
    'onboarding': 'newhire',
    'resignation': 'resign',
    'bank account change': 'bankchange',
    'pay review': 'payreview',
    'asset request': 'assets',
    'business trip': 'trip',
    'attendance correction': 'correction',
    'probation': 'verdict',
    'letter': 'letters',
    'exchange rate': 'fx',
    'budget': 'fx',
    'pay band': 'bands',
}

#: Who decides -> a responsibility key, or the word `manager` for "the person's
#: own manager", which is a step mode rather than a responsibility.
ROLE_SYNONYMS = {
    'hr lead': 'hr_lead',
    'hr': 'hr_lead',
    'hr manager': 'hr_lead',
    'hr ops': 'hr_lead',
    'hr reviewer': 'hr_lead',
    'hr/payroll': 'payroll_mgr',
    'people lead': 'hr_lead',
    'finance': 'finance',
    'finance approver': 'finance',
    'finance reviewer': 'finance',
    'finance manager': 'finance',
    'finance controller': 'finance_controller',
    'controller': 'finance_controller',
    'payroll': 'payroll_mgr',
    'payroll manager': 'payroll_mgr',
    'payroll preparer': 'payroll_mgr',
    'payroll/finance': 'payroll_mgr',
    'payroll/finance maker': 'payroll_mgr',
    'bank checker': 'finance',
    'bank maker': 'payroll_mgr',
    'country': 'director',
    'country director': 'director',
    'country approver': 'director',
    'country/finance approver': 'director',
    'director': 'director',
    'authorized signatory': 'signatory',
    'authorised signatory': 'signatory',
    'signatory': 'signatory',
    'head of pay': 'pay_head',
    'equipment': 'equipment',
    'lifecycle': 'lifecycle',
    'access': 'access',
    'budget holder': 'budget',
    'scheme owner': 'scheme_owner',
    'platform owner': 'platform_owner',
    # Not a responsibility — the person's OWN manager, which the engine
    # expresses as a step mode.
    'line manager': 'manager',
    'respective line manager': 'manager',
    'manager': 'manager',
    'functional manager': 'manager',
    'functional owner': 'manager',
    'employee/manager': 'manager',
    'department head': 'manager',
}

#: Cells that mean "nothing here". Compared lower-cased and stripped.
EMPTY_WORDS = ('', 'none', 'n/a', 'na', '-', '—', 'not applicable', 'nil',
               'none (unified)', 'tbd', 'to be decided')

_WS = re.compile(r'\s+')


def squeeze(value):
    """Lower-cased, single-spaced, stripped. Every lookup goes through it."""
    return _WS.sub(' ', str(value or '').strip()).lower()


def is_empty(value):
    return squeeze(value) in EMPTY_WORDS


def split_joint(value):
    """"HR + Finance" -> ['HR', 'Finance']; "Nithya + Monica" likewise.

    A slash is NOT a split. "HR/Payroll" is one team's name in most of these
    spreadsheets, and splitting it would invent a second signature nobody
    asked for.
    """
    raw = re.sub(r'\((?:joint|unified)\)', '', str(value or ''),
                 flags=re.IGNORECASE)
    parts = [p.strip() for p in re.split(r'\s*(?:\+|&|\band\b)\s*', raw)]
    return [p for p in parts if p and not is_empty(p)]


def match_role(value):
    """One cell -> a responsibility key, 'manager', or None."""
    text = squeeze(value)
    if not text or is_empty(text):
        return None
    if text in ROLE_SYNONYMS:
        return ROLE_SYNONYMS[text]
    # Longest phrase that appears in the cell, so "finance controller" beats
    # "finance".
    for phrase in sorted(ROLE_SYNONYMS, key=len, reverse=True):
        if phrase in text:
            return ROLE_SYNONYMS[phrase]
    return None


def match_process(value):
    text = squeeze(value)
    if not text:
        return None
    for phrase in sorted(PROCESS_SYNONYMS, key=len, reverse=True):
        if phrase in text:
            return PROCESS_SYNONYMS[phrase]
    return None


def parse_sla(value):
    """"1 working day" -> working days; "By Day 15" -> a day of the month.

    Anything else is None and a warning, because a due date invented from
    "Case-by-case" would chase somebody on a day nobody agreed to.
    """
    text = squeeze(value)
    if not text or is_empty(text):
        return None, ''
    days = re.search(r'(\d+)\s*(?:working|business)\s*day', text)
    if days:
        return ({'kind': 'working_days', 'days': int(days.group(1)),
                 'day': 15, 'calendar_id': None}, '')
    day_of_month = re.search(r'day\s*(\d{1,2})', text)
    if day_of_month and 1 <= int(day_of_month.group(1)) <= 28:
        return ({'kind': 'calendar_day', 'days': 2,
                 'day': int(day_of_month.group(1)), 'calendar_id': None}, '')
    plain = re.search(r'(\d+)\s*day', text)
    if plain:
        return ({'kind': 'working_days', 'days': int(plain.group(1)),
                 'day': 15, 'calendar_id': None}, '')
    return None, _("The turnaround \"%s\" could not be read as a number of "
                   "days, so no chase-up date was set.", value)


class PbApprovalProposedPerson(models.Model):
    """A name off a spreadsheet, waiting for somebody to say who that is.

    NOT a `biz.approval.responsibility`: that model names a real account and
    resolving it is what gives somebody a seat. A name in a cell is a note
    about a human being, and the gap between the two is exactly where an
    importer would otherwise guess.
    """
    _name = 'pb.approval.proposed.person'
    _description = 'Proposed approver from a spreadsheet'
    _order = 'process_key, sequence, id'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    process_key = fields.Char(string='Process', required=True, index=True)
    role_key = fields.Char(string='Responsibility', required=True)
    role_label = fields.Char(string='Responsibility name')
    name_text = fields.Char(string='Name on the spreadsheet', required=True)
    kind = fields.Selection([('holder', 'Holder'), ('backup', 'Backup')],
                            default='holder', required=True)
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one('res.users', string='Chosen account')
    state = fields.Selection([('proposed', 'Waiting for an account'),
                              ('resolved', 'Given to somebody'),
                              ('dropped', 'Not needed')],
                             default='proposed', required=True, index=True)
    source_note = fields.Char(string='Where it came from')

    def payload(self):
        return [{
            'id': row.id,
            'process_key': row.process_key,
            'role_key': row.role_key,
            'role_label': row.role_label or row.role_key,
            'name_text': row.name_text,
            'kind': row.kind,
            'state': row.state,
            'user_id': row.user_id.id,
            'user_name': row.user_id.name or '',
            'source_note': row.source_note or '',
        } for row in self]


class PbApprovalMatrixImport(models.AbstractModel):
    """The door: read a workbook, make drafts, report what is unresolved."""
    _name = 'pb.approval.matrix.import'
    _description = 'Approval Matrix spreadsheet import'

    # ------------------------------------------------------------- the gate
    @api.model
    def _require_config(self):
        self.env['pb.approval.matrix']._require_config()
        return True

    # ---------------------------------------------------------- the reading
    @api.model
    def _rows_from_workbook(self, content):
        """The sheet, as a list of dicts keyed by our column names.

        Reads with the payroll engine's own Excel connector where that module
        is installed, because it already knows how to find a header row that
        is not the first one — and falls back to a plain openpyxl read of the
        same sheet where it is not, so this module never HARD-depends on the
        payroll engine.
        """
        try:
            raw = base64.b64decode(content or '')
        except Exception:       # noqa: BLE001
            raise UserError(_("That file could not be read."))
        if not raw:
            raise UserError(_("That file is empty."))
        headers, rows = self._read_with_connector(raw)
        if headers is None:
            headers, rows = self._read_with_openpyxl(raw)
        if headers is None:
            raise UserError(_(
                "This workbook has no sheet called \"%s\". Rename the tab and "
                "try again — everything else about the file is fine.",
                SHEET_NAME))
        mapping = {}
        for index, head in enumerate(headers):
            key = HEADER_SYNONYMS.get(squeeze(head))
            if key and key not in mapping:
                mapping[key] = index
        if 'object' not in mapping:
            raise UserError(_(
                "That sheet has no \"Transaction / Object\" column, so there "
                "is no way to tell what each row is about."))
        out = []
        for row in rows:
            record = {key: (row[index] if index < len(row) else '')
                      for key, index in mapping.items()}
            if is_empty(record.get('object')):
                continue
            out.append({key: ('' if record.get(key) is None
                              else str(record.get(key)).strip())
                        for key in COLUMNS})
        return out

    @api.model
    def _read_with_connector(self, raw):
        """The payroll engine's reader, when that module is installed."""
        if 'pb_hr_payroll_formula' not in self.env.registry._init_modules \
                and 'hr.formula.config' not in self.env:
            return None, []
        try:
            from odoo.addons.pb_hr_payroll_formula.integrations.excel_connector\
                import ExcelConnector
            connector = ExcelConnector()
            connector.load_workbook_multisheet(raw, include_formulas=False)
            names = {squeeze(n): n for n in connector.workbook.sheetnames}
            real = names.get(squeeze(SHEET_NAME))
            if not real:
                return None, []
            sheet = connector.load_sheet_with_detection(real)
            return (list(sheet.get('headers') or []),
                    [list(r) for r in (sheet.get('data') or [])])
        except Exception:       # noqa: BLE001 — fall back rather than fail
            _logger.info('approval import: the payroll reader could not open '
                         'this workbook; falling back to a plain read',
                         exc_info=True)
            return None, []

    @api.model
    def _read_with_openpyxl(self, raw):
        """A plain read of the same sheet, header row found by looking."""
        try:
            import openpyxl
        except ImportError:
            raise UserError(_(
                "Spreadsheets cannot be read on this server yet. Ask whoever "
                "looks after it to add the spreadsheet reader."))
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        except Exception:       # noqa: BLE001
            raise UserError(_(
                "That file is not a spreadsheet this app can read. Save it as "
                "an .xlsx and try again."))
        names = {squeeze(n): n for n in workbook.sheetnames}
        real = names.get(squeeze(SHEET_NAME))
        if not real:
            return None, []
        sheet = workbook[real]
        values = [list(r) for r in sheet.iter_rows(values_only=True)]
        header_index = None
        for index, row in enumerate(values[:30]):
            found = {HEADER_SYNONYMS.get(squeeze(c)) for c in row if c}
            if 'object' in found and ('final' in found or 'reviewer' in found):
                header_index = index
                break
        if header_index is None:
            return [], []
        return values[header_index], values[header_index + 1:]

    # ----------------------------------------------------------- the making
    @api.model
    def preview(self, content):
        """Read the file and say what would be made. Writes nothing."""
        self._require_config()
        rows = self._rows_from_workbook(content)
        return {'ok': True, 'rows': [self._plan_row(r) for r in rows],
                'sheet': SHEET_NAME}

    @api.model
    def _plan_row(self, row):
        """One spreadsheet row, read into the shape a route is built from."""
        process_key = match_process(row.get('object'))
        steps, warnings = [], []
        for column, fallback in (('reviewer', _('Reviewer')),
                                 ('final', _('Final approver'))):
            cell = row.get(column) or ''
            if is_empty(cell):
                continue
            parts = split_joint(cell) or [cell]
            for part in parts:
                role = match_role(part)
                if role is None:
                    warnings.append(_(
                        "\"%(who)s\" in the %(column)s column is not a "
                        "responsibility this app knows, so that step was left "
                        "out.", who=part.strip(), column=fallback))
                    continue
                steps.append({'role': role, 'label': part.strip(),
                              'column': column})
        due, sla_warning = parse_sla(row.get('sla'))
        if sla_warning:
            warnings.append(sla_warning)
        threshold = row.get('threshold') or ''
        note = ''
        if not is_empty(threshold):
            note = _("The spreadsheet says: %s. Limits are set where the "
                     "process itself is configured, never as a condition "
                     "invented from this text.", threshold.strip())
        people = []
        for column, kind in (('named', 'holder'), ('backup', 'backup')):
            cell = row.get(column) or ''
            if is_empty(cell):
                continue
            for part in split_joint(cell) or [cell]:
                people.append({'name_text': part.strip(), 'kind': kind})
        return {
            'stage': row.get('stage') or '',
            'object': row.get('object') or '',
            'process_key': process_key or 'generic',
            'recognised': bool(process_key),
            'steps': steps,
            'due': due,
            'sla_text': row.get('sla') or '',
            'threshold_note': note,
            'people': people,
            'warnings': warnings,
            'evidence_text': row.get('evidence') or '',
        }

    @api.model
    def run(self, content, company_id=None):
        """Make a draft route per row, and the proposed people beside them."""
        self._require_config()
        company = self.env['res.company'].browse(int(company_id or 0)) \
            or self.env.company
        if not company.exists():
            company = self.env.company
        rows = self._rows_from_workbook(content)
        made, unresolved = [], []
        for row in rows:
            plan = self._plan_row(row)
            result = self._build_draft(company, plan)
            made.append(result)
            unresolved.extend(result.get('people') or [])
        return {
            'ok': True,
            'company': company.name,
            'made': made,
            'drafts': sum(1 for m in made if m.get('workflow_id')),
            'unrecognised': [m['object'] for m in made
                             if not m.get('recognised')],
            'people': unresolved,
            'published': 0,
            'sentence': _(
                "%(drafts)s draft route(s) made from %(rows)s row(s). Nothing "
                "is in force until somebody publishes it.",
                drafts=sum(1 for m in made if m.get('workflow_id')),
                rows=len(made)),
        }

    @api.model
    def _build_draft(self, company, plan):
        """One row -> one draft workflow. Never published, ever."""
        Process = self.env['biz.approval.process']
        process = Process._by_key(plan['process_key']) \
            or Process._by_key('generic')
        if not process:
            return dict(plan, workflow_id=0, version_id=0,
                        warnings=plan['warnings'] + [_(
                            "There is no place in the list for this yet.")])
        steps = []
        seen = set()
        for index, step in enumerate(plan['steps'], start=1):
            key = 's%s' % index
            if step['role'] == 'manager':
                steps.append({'key': key, 'kind': 'approve',
                              'title': step['label'] or _('Their manager'),
                              'who': {'mode': 'manager'},
                              'min_amount': 0, 'condition': None})
                continue
            role = self.env['biz.approval.role'].sudo().search(
                [('key', '=', step['role'])], limit=1)
            if not role:
                continue
            if (step['role'], 'role') in seen and len(plan['steps']) > 1:
                # The same responsibility twice in a row is one signature.
                continue
            seen.add((step['role'], 'role'))
            steps.append({'key': key, 'kind': 'approve',
                          'title': step['label'] or role.name,
                          'who': {'mode': 'role', 'role': step['role'],
                                  'scope': 'company'},
                          'min_amount': 0, 'condition': None})
        definition = {
            'schema_version': 1,
            'steps': steps,
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {
                'independent': True,
                'self_exception': {'enabled': False},
                'repeated': 'different',
                'evidence': [],
                'due': plan['due'] or {'kind': 'none', 'days': 1, 'day': 15,
                                       'calendar_id': None},
                'late': {'remind_days': 1, 'escalate_days': 2,
                         'reassign': False},
            },
        }
        name = _("%s (from the spreadsheet)", plan['object'][:60])
        workflow = self.env['biz.approval.workflow'].sudo().create({
            'name': name,
            'company_id': company.id,
            'process_id': process.id,
            'owner_user_id': self.env.uid,
        })
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': workflow.id,
            'revision': 1,
            'status': 'draft',
            'definition': definition,
        })
        people = self._propose_people(company, plan, process)
        return dict(plan, workflow_id=workflow.id, version_id=version.id,
                    workflow_name=name, steps_made=len(steps),
                    people=people)

    @api.model
    def _propose_people(self, company, plan, process):
        """Names off the sheet, as rows somebody has to give an account to."""
        Proposed = self.env['pb.approval.proposed.person'].sudo()
        roles = [s['role'] for s in plan['steps'] if s['role'] != 'manager']
        made = []
        for index, person in enumerate(plan.get('people') or []):
            role_key = roles[min(index, len(roles) - 1)] if roles else 'hr_lead'
            role = self.env['biz.approval.role'].sudo().search(
                [('key', '=', role_key)], limit=1)
            existing = Proposed.search([
                ('company_id', '=', company.id),
                ('process_key', '=', process.key),
                ('name_text', '=', person['name_text']),
                ('kind', '=', person['kind'])], limit=1)
            row = existing or Proposed.create({
                'company_id': company.id,
                'process_key': process.key,
                'role_key': role_key,
                'role_label': role.name or role_key,
                'name_text': person['name_text'],
                'kind': person['kind'],
                'sequence': 10 + index,
                'source_note': _('Proposed from the spreadsheet · choose the '
                                 'account'),
            })
            made.extend(row.payload())
        return made

    # ------------------------------------------------- resolving the people
    @api.model
    def proposed_people(self, company_id=None):
        self._require_config()
        company = self.env['res.company'].browse(int(company_id or 0)) \
            or self.env.company
        rows = self.env['pb.approval.proposed.person'].sudo().search([
            ('company_id', '=', company.id), ('state', '=', 'proposed')])
        return rows.payload()

    @api.model
    def resolve_person(self, proposed_id, user_id):
        """Say who that name is, and give them the responsibility."""
        self._require_config()
        row = self.env['pb.approval.proposed.person'].sudo().browse(
            int(proposed_id or 0)).exists()
        if not row:
            raise UserError(_("That proposed person is no longer here."))
        user = self.env['res.users'].browse(int(user_id or 0)).exists()
        if not user:
            raise UserError(_("Pick somebody with an account."))
        role = self.env['biz.approval.role'].sudo().search(
            [('key', '=', row.role_key)], limit=1)
        if not role:
            raise UserError(_("That responsibility is no longer in the list."))
        Responsibility = self.env['biz.approval.responsibility'].sudo()
        held = Responsibility.with_context(active_test=False).search([
            ('company_id', '=', row.company_id.id),
            ('role_id', '=', role.id), ('scope_key', '=', '')], limit=1)
        if held and row.kind == 'backup':
            held.write({'backup_user_id': user.id})
        elif held:
            held.write({'user_id': user.id, 'active': True})
        else:
            Responsibility.create({
                'company_id': row.company_id.id,
                'role_id': role.id,
                'scope_key': '',
                'scope_label': row.company_id.name,
                'user_id': user.id if row.kind == 'holder' else False,
                'backup_user_id': user.id if row.kind == 'backup' else False,
                'date_from': fields.Date.context_today(self),
                'note': _('From the approval matrix spreadsheet: %s',
                          row.name_text),
            })
        row.write({'user_id': user.id, 'state': 'resolved'})
        return row.payload()[0]

    @api.model
    def drop_person(self, proposed_id):
        self._require_config()
        row = self.env['pb.approval.proposed.person'].sudo().browse(
            int(proposed_id or 0)).exists()
        if row:
            row.write({'state': 'dropped'})
        return True
