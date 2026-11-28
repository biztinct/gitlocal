from pathlib import PurePath

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype
from odoo.addons.pb_new_hire.models.studio_docs import FILE_MAX, FILE_MIMES, FILES_MAX, SECRET_FIELDS


def masked(value):
    text = str(value or '')
    if not text:
        return ''
    return '•••• ' + text[-4:] if len(text) > 4 else '••••'


class JoiningItem(models.Model):
    _name = 'pb.joining.item'
    _description = 'Details before joining'
    _rec_name = 'key'

    joining_id = fields.Many2one('pb.joining', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='joining_id.company_id', store=True, index=True)
    key = fields.Char(required=True)
    values = fields.Json()
    draft = fields.Json(copy=False)
    none_fields = fields.Json()
    attachment_ids = fields.Many2many('ir.attachment', copy=False)
    issue_date = fields.Date()
    expiry_date = fields.Date()
    no_expiry = fields.Boolean()
    available = fields.Boolean(default=True)
    need = fields.Selection([('first_pay', 'First pay'), ('joining', 'Joining'), ('optional', 'Optional')])
    state = fields.Selection([('empty', 'Not sent yet'), ('saved', 'Saved'), ('later', 'To finish later'),
                              ('accepted', 'Accepted'), ('returned', 'Sent back to fix')], default='empty', required=True)
    return_note = fields.Char(size=200)
    reopened = fields.Boolean()
    decided_by_id = fields.Many2one('res.users')
    decided_on = fields.Datetime()
    from_hiring = fields.Boolean()
    _key_unique = models.Constraint('UNIQUE(joining_id,key)', 'This item already belongs to the joining.')

    def _section_key(self):
        if self.key.startswith('paper-'):
            return 'papers'
        if self.key.startswith('tax_') or self.key == 'insurance':
            return 'tax'
        return self.key

    def _editable(self):
        self.ensure_one()
        j = self.joining_id
        if not self.available or self.state == 'accepted' or j.state in ('added', 'cancelled') or j.proposal_id:
            return False
        if self.state == 'later' and self.key == 'bank':
            return True
        return j.state in ('invited', 'filling') and (not j.submitted_at or self.reopened or self.state == 'returned')

    def _require_edit(self):
        self.joining_id._lock()
        self.invalidate_recordset()
        if not self._editable():
            raise UserError(_('HR is checking this item.'))

    def _draft(self, spec, values, none_fields):
        self._require_edit()
        previous = dict(self.values or {}, **((self.draft or {}).get('fields') or {}))
        boxes = spec['fields']
        if self.key == 'bank':
            fmt = self.env['pb.new.hire']._bank_format_of(values, self.joining_id.payroll_country)
            boxes = spec['bank']['fields'][fmt]
        draft = {}
        for box in boxes:
            key = box['name']
            draft[key] = str(values.get(key, previous.get(key, '')) or '')[:200]
        dates = {k: str(values.get(k) or '')[:10] for k in ('issue_date', 'expiry_date', 'no_expiry')}
        none = [b['name'] for b in boxes if b['name'] in none_fields and self.key in ('tax_number', 'insurance')]
        changed = (any(str((self.values or {}).get(k) or '') != v for k, v in draft.items()) or
                   set(none) != set(self.none_fields or []) or
                   any(str(self[k] or '') != dates[k] for k in ('issue_date', 'expiry_date')) or
                   bool(self.no_expiry) != bool(dates['no_expiry']))
        if changed:
            self.write({'draft': {'fields': draft, 'dates': dates, 'none': none},
                        'state': 'returned' if self.reopened else ('later' if self.joining_id.submitted_at and self.state == 'later' else 'empty')})
        elif self.draft:
            self.draft = False

    def _save(self, spec, values, none_fields=(), later=False):
        self._require_edit()
        j = self.joining_id
        studio = self.env['pb.new.hire'].sudo().with_company(j.company_id)
        if self.key == 'bank' and later:
            self.write({'values': {}, 'draft': False, 'none_fields': [], 'state': 'later'})
            return
        old = dict(self.values or {}, **((self.draft or {}).get('fields') or {}))
        boxes = spec['fields']
        if self.key == 'bank':
            fmt = studio._bank_format_of(values, j.payroll_country)
            boxes = spec['bank']['fields'][fmt]
        clean, none = {}, []
        for box in boxes:
            key = box['name']
            if key in none_fields and self.key in ('insurance', 'tax_number'):
                none.append(key)
                continue
            value = values.get(key)
            if key in SECRET_FIELDS and key not in values:
                value = old.get(key)
            if not value:
                if box['required']:
                    raise UserError(_('Enter %(field)s.', field=box['label']))
                continue
            clean[key], problem = studio._check_value(j.payroll_country, box, value)
            if problem:
                raise UserError(problem)
        if self.key == 'bank':
            refused = studio._validate_bank(j.payroll_country, clean, j._first(), spec)
            if refused:
                raise UserError(refused['message'])
            clean = studio._bank_values(j.payroll_country, clean, j.name)
        if self.key in ('personal', 'emergency') and (not clean or (self.key == 'emergency' and len(clean) != len(boxes))):
            raise UserError(_('Add your details before continuing.'))
        upload = spec.get('upload') or spec.get('received_upload') or {}
        if spec.get('upload') and self.need != 'optional' and not self.attachment_ids and not none:
            raise UserError(_('Add the paper before continuing.'))
        dates = {}
        if upload:
            for k in ('issue_date', 'expiry_date'):
                dates[k] = fields.Date.to_date(values.get(k)) or False
            dates['no_expiry'] = bool(values.get('no_expiry')) and self.key == 'id_number'
            if dates['no_expiry']:
                dates['expiry_date'] = False
            elif upload.get('needs_expiry') and not dates['expiry_date'] and not none:
                raise UserError(_('Add the date the paper is valid until.'))
            if dates['expiry_date'] and dates['expiry_date'] < fields.Date.today():
                raise UserError(_('That date has passed. Add a paper that is still valid.'))
        self.write(dict(dates, values=clean, draft=False, none_fields=none, state='later' if not clean and (none or self.key == 'insurance') else 'saved',
                        return_note=False, decided_on=False, decided_by_id=False))

    def _upload(self, spec, name, raw, replace=0):
        self._require_edit()
        if not spec.get('upload') or not raw or len(raw) > FILE_MAX:
            raise UserError(_('Choose a photo or PDF up to 10 MB.'))
        mime = guess_mimetype(raw)
        if mime not in FILE_MIMES:
            raise UserError(_('Choose a JPEG, PNG or PDF.'))
        old = self.attachment_ids.filtered(lambda a: a.id == replace)
        if replace and not old:
            raise UserError(_('Choose a file from this item.'))
        size = sum(self.joining_id.item_ids.attachment_ids.mapped('file_size')) - sum(old.mapped('file_size'))
        if size + len(raw) > FILES_MAX or len(self.attachment_ids - old) >= 12:
            raise UserError(_('There is no room for another file. Replace a file or use a smaller photo.'))
        attachment = self.env['ir.attachment'].create({
            'name': PurePath(name or _('Paper')).name[:160], 'type': 'binary', 'raw': raw,
            'mimetype': mime, 'public': False, 'res_model': self._name, 'res_id': self.id,
            'company_id': self.company_id.id})
        self.attachment_ids = self.attachment_ids - old | attachment
        old.unlink()
        return attachment

    def _display(self, box):
        name = box['name']
        value = (self.draft or {}).get('fields', {}).get(name, (self.values or {}).get(name, ''))
        if value and name in SECRET_FIELDS:
            return masked(value)
        return value
