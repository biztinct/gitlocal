# -*- coding: utf-8 -*-
"""The fallback door: the same arrivals, out of a spreadsheet.

WHY THIS EXISTS. A live push needs somebody with admin rights in the tenant's
own Zoho account, and that person is often three approvals away. Meanwhile
joiners keep joining. This wizard takes the export HR already produces and runs
it through the SAME pipeline the webhook uses — the same rules, the same
whitelist, the same idempotency, the same audit rows — so the day the push is
finally wired up nothing about the behaviour changes.

TWO STEPS, AND THE FIRST ONE WRITES NOTHING. Uploading a file that quietly
created ninety employees would be indefensible, so the wizard reads the file,
says in plain words what it is about to do, and waits. Only "Apply" writes.

THE PREVIEW IS A DRY RUN, NOT A GUESS. It matches people, reads triggers and
asks the rules exactly as the real pass will, then throws the answers away. It
does not open a savepoint and roll it back, because a rolled-back preview would
still have burned sequences and could still have created a department.
"""

import base64
import csv
import io
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: A spreadsheet that big is a mistake, not a joiner file. Same order as the
#: webhook's own MAX_WEBHOOK_RECORDS so neither door is the soft one.
MAX_ROWS = 5000


class PbZohoUploadWizard(models.TransientModel):
    _name = 'pb.zoho.upload.wizard'
    _description = 'Upload a joiner file'

    state = fields.Selection(
        [('upload', 'Choose a file'), ('preview', 'Check it')],
        default='upload', required=True)
    file_data = fields.Binary(string='File', attachment=False)
    filename = fields.Char(string='File name')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
        help='The company these people belong to.')

    row_count = fields.Integer(string='Rows read', readonly=True)
    new_count = fields.Integer(string='People to add', readonly=True)
    update_count = fields.Integer(string='Records to update', readonly=True)
    onboard_count = fields.Integer(string='Joining checklists to start', readonly=True)
    offboard_count = fields.Integer(string='Leaving checklists to start', readonly=True)
    review_count = fields.Integer(string='Rows needing a look', readonly=True)
    ignore_count = fields.Integer(string='Rows to leave alone', readonly=True)
    duplicate_count = fields.Integer(string='Rows already received', readonly=True)
    preview_lines = fields.Text(string='Row by row', readonly=True)
    summary_note = fields.Text(string='What will happen', readonly=True)
    result_note = fields.Text(string='What happened', readonly=True)

    # ==================================================== reading the file
    def _rows_from_file(self):
        """A list of plain dicts, whatever the file was.

        Header rows are taken as they are: the pipeline's own alias index knows
        both the connected system's export spellings and the ordinary English
        ones, so this does not need a mapping screen and deliberately does not
        have one.
        """
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Choose a file first.'))
        blob = base64.b64decode(self.file_data)
        name = (self.filename or '').lower()
        if name.endswith('.csv') or (not name.endswith(('.xlsx', '.xlsm'))
                                     and blob[:2] != b'PK'):
            return self._rows_from_csv(blob)
        return self._rows_from_xlsx(blob)

    def _rows_from_csv(self, blob):
        for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
            try:
                text = blob.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise UserError(_(
                'That file could not be read as text. Save it again as CSV or '
                'as an Excel file and try once more.'))
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        rows = []
        for raw in reader:
            rows.append({(k or '').strip(): v
                         for k, v in raw.items() if k})
            if len(rows) > MAX_ROWS:
                break
        return rows

    def _rows_from_xlsx(self, blob):
        try:
            import openpyxl
        except ImportError:
            raise UserError(_(
                'Excel files cannot be read on this server. Save the file as '
                'CSV and upload that instead.'))
        try:
            book = openpyxl.load_workbook(io.BytesIO(blob), data_only=True,
                                          read_only=True)
        except Exception as err:         # noqa: BLE001 - a bad file, not a bug
            raise UserError(_(
                'That file could not be opened: %s', err))
        sheet = book.active
        rows, headers = [], []
        for index, line in enumerate(sheet.iter_rows(values_only=True)):
            if index == 0:
                headers = [str(c).strip() if c is not None else ''
                           for c in line]
                continue
            if all(c is None or str(c).strip() == '' for c in line):
                continue
            rows.append({h: c for h, c in zip(headers, line) if h})
            if len(rows) >= MAX_ROWS:
                break
        book.close()
        return rows

    # ==================================================== step one: preview
    def action_preview(self):
        self.ensure_one()
        rows = self._rows_from_file()
        if not rows:
            raise UserError(_(
                'That file has no rows in it — only a header, or nothing at '
                'all.'))
        Pipeline = self.env['pb.zoho.pipeline']
        Inbox = self.env['pb.zoho.inbox'].sudo()
        Rules = self.env['pb.zoho.event.rule']
        lines, counts = [], {'new': 0, 'update': 0, 'onboard': 0,
                             'offboard': 0, 'review': 0, 'ignore': 0,
                             'duplicate': 0}
        for raw in rows:
            rec = Pipeline._normalise(raw)
            who = rec.get('name') or rec.get('employee_number') or _('(no name)')
            event_id = rec.get('event_id') or Inbox.fingerprint(
                {k: v for k, v in rec.items() if k != '_raw'})
            if Inbox.already_seen(event_id):
                counts['duplicate'] += 1
                lines.append({'who': who, 'outcome': _('Already received')})
                continue
            employee = Pipeline._match_employee(rec)
            if len(employee) > 1:
                counts['review'] += 1
                lines.append({'who': who,
                              'outcome': _('Could be more than one person')})
                continue
            status = rec.get('employment_status') or ''
            trigger = Pipeline._read_trigger(employee, rec, status)
            rule = Rules.decide(trigger, status, self.company_id.id)
            if not rule:
                counts['review'] += 1
                lines.append({'who': who,
                              'outcome': _('No rule covers "%s" yet',
                                           status or trigger)})
                continue
            if rule.action == 'onboard':
                counts['onboard'] += 1
                if employee:
                    counts['update'] += 1
                    lines.append({'who': who,
                                  'outcome': _('Start their joining checklist')})
                else:
                    counts['new'] += 1
                    lines.append({'who': who,
                                  'outcome': _('Add them and start their '
                                               'joining checklist')})
            elif rule.action == 'offboard':
                if not employee:
                    counts['review'] += 1
                    lines.append({'who': who,
                                  'outcome': _('Nobody here to leave')})
                else:
                    counts['offboard'] += 1
                    counts['update'] += 1
                    lines.append({'who': who,
                                  'outcome': _('Start their leaving checklist')})
            elif rule.action == 'update':
                if not employee:
                    counts['review'] += 1
                    lines.append({'who': who, 'outcome': _('Nobody to update')})
                else:
                    counts['update'] += 1
                    lines.append({'who': who, 'outcome': _('Update the record')})
            elif rule.action == 'ignore':
                counts['ignore'] += 1
                lines.append({'who': who, 'outcome': _('Leave alone')})
            else:
                counts['review'] += 1
                lines.append({'who': who, 'outcome': _('Put aside for a look')})

        self.write({
            'state': 'preview',
            'row_count': len(rows),
            'new_count': counts['new'],
            'update_count': counts['update'],
            'onboard_count': counts['onboard'],
            'offboard_count': counts['offboard'],
            'review_count': counts['review'],
            'ignore_count': counts['ignore'],
            'duplicate_count': counts['duplicate'],
            # Readable lines, not a JSON dump. The person approving this
            # upload is an HR administrator deciding whether to press Apply;
            # they should not have to read a payload to do it.
            'preview_lines': '\n'.join(
                '%s  —  %s' % (ln['who'], ln['outcome']) for ln in lines),
            'summary_note': self._summary_sentence(len(rows), counts),
        })
        return self._reopen()

    def _summary_sentence(self, total, counts):
        bits = []
        if counts['new']:
            bits.append(_('%s person(s) will be added', counts['new']))
        if counts['update']:
            bits.append(_('%s record(s) will be updated', counts['update']))
        if counts['onboard']:
            bits.append(_('%s joining checklist(s) will start',
                          counts['onboard']))
        if counts['offboard']:
            bits.append(_('%s leaving checklist(s) will start',
                          counts['offboard']))
        if counts['review']:
            bits.append(_('%s row(s) will wait for someone to look at them',
                          counts['review']))
        if counts['ignore']:
            bits.append(_('%s row(s) will be left alone', counts['ignore']))
        if counts['duplicate']:
            bits.append(_('%s row(s) were already received and will be '
                          'skipped', counts['duplicate']))
        if not bits:
            return _('Nothing in this file changes anything.')
        return _('%(total)s row(s) read. ', total=total) + '; '.join(bits) + '.'

    # ==================================================== step two: apply
    def action_apply(self):
        self.ensure_one()
        rows = self._rows_from_file()
        summary = self.env['pb.zoho.pipeline'].process_records(
            rows, 'file', company_id=self.company_id.id)
        note = _(
            '%(received)s row(s) read. %(created)s person(s) added, '
            '%(updated)s record(s) updated, %(onboarding)s joining and '
            '%(offboarding)s leaving checklist(s) started, %(review)s waiting '
            'for a look, %(skipped)s already received, %(errors)s could not be '
            'applied.',
            **{k: summary.get(k, 0) for k in
               ('received', 'created', 'updated', 'onboarding', 'offboarding',
                'review', 'skipped', 'errors')})
        _logger.info('pb_zoho_bridge: file upload — %s', summary)
        self.write({'result_note': note})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Arrivals from the connected system'),
            'res_model': 'pb.zoho.inbox',
            'view_mode': 'list,form',
            'target': 'current',
            'context': {'search_default_filter_today': 1},
        }

    def action_back(self):
        self.ensure_one()
        self.write({'state': 'upload'})
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Upload a joiner file'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.onchange('file_data')
    def _onchange_file_data(self):
        """A new file means the old preview is a lie. Clear it."""
        for rec in self:
            if rec.state != 'upload':
                rec.state = 'upload'
            rec.preview_lines = False
            rec.summary_note = False
