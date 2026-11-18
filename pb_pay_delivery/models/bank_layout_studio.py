# -*- coding: utf-8 -*-
"""WDGAP S2-C — Settings › Payroll › Bank layouts.

The screen behind the card: every bank layout this company may use (the ones
Payobook ships and the company's own copies), a "Make our own copy" button,
an editor for the company's copies (never for a shipped layout), and a
preview of a payment-list layout with three made-up DEMO people.

WHO. The payroll manager (and administrators), nobody else: a layout decides
which column the bank reads as the account number and which as the amount.
Every change is on the platform trail (`data/audit_rules.xml`, extended by the
19.0.1.9.0 migration to the new fields).
"""

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from .bank_file_layout import COLUMN_SOURCES, TEMPLATE_TOKENS

#: what the editor may write on a copy
LAYOUT_FIELDS = ('name', 'file_type', 'delimiter', 'encoding', 'with_header',
                 'header_template', 'trailer_template', 'amount_format',
                 'date_format', 'line_ending', 'ascii_only', 'code_label',
                 'code_pattern', 'account_pattern', 'note')
COLUMN_FIELDS = ('header', 'source', 'literal_value', 'width', 'pad',
                 'number_format', 'max_length', 'required')
MANAGER_GROUP = 'om_hr_payroll.group_hr_payroll_manager'


class PbBankLayoutStudio(models.AbstractModel):
    _name = 'pb.bank.layout.studio'
    _description = 'Bank layouts screen'

    # ------------------------------------------------------------ the door
    @api.model
    def _require(self):
        user = self.env.user
        if user._is_admin() or user.has_group(MANAGER_GROUP):
            return
        raise AccessError(_("Bank layouts are set up by the payroll manager."))

    @api.model
    def _layout(self, layout_id):
        self._require()
        layout = self.env['pb.bank.file.layout'].with_context(
            active_test=False).browse(int(layout_id or 0)).exists()
        if not layout:
            raise UserError(_("That bank layout no longer exists."))
        layout.check_access('read')
        return layout

    @api.model
    def _own_copy(self, layout_id):
        layout = self._layout(layout_id)
        if not layout.company_id or layout.company_id not in self.env.companies:
            raise UserError(_("A layout Payobook ships cannot be changed here. Make your own copy and change the copy."))
        return layout

    # ------------------------------------------------------------ reading
    @api.model
    def _summary(self, layout):
        return {
            'id': layout.id,
            'key': layout.bank_format,
            'name': layout.name,
            'country': layout.country_id.name or '',
            'country_code': layout.country_id.code or '',
            'target': layout.target,
            'target_label': dict(layout._fields['target']._description_selection(self.env)).get(layout.target, ''),
            'file_type': layout.file_type,
            'shipped': not layout.company_id,
            'company': layout.company_id.name or '',
            'inferred': bool(layout.inferred),
            'active': bool(layout.active),
            'columns': len(layout.column_ids),
            'copied_from': layout.copied_from_id.name or '',
        }

    @api.model
    def _detail(self, layout):
        out = self._summary(layout)
        for name in LAYOUT_FIELDS:
            value = layout[name]
            out[name] = value if value not in (None,) else ''
            if out[name] is False and layout._fields[name].type != 'boolean':
                out[name] = ''
        out['currency'] = layout.currency_id.name or ''
        out['editable'] = bool(layout.company_id
                               and layout.company_id in self.env.companies)
        out['column_rows'] = [{
            'id': c.id,
            'header': c.header or '',
            'source': c.source,
            'literal_value': c.literal_value or '',
            'width': c.width or 0,
            'pad': c.pad or 'right',
            'number_format': c.number_format or 'none',
            'max_length': c.max_length or 0,
            'required': bool(c.required),
        } for c in layout.column_ids.sorted(lambda c: (c.sequence, c.id))]
        return out

    @api.model
    def _choices(self, field_model, field_name):
        field = self.env[field_model]._fields[field_name]
        return [{'key': k, 'label': v} for k, v in field._description_selection(self.env)]

    @api.model
    def get_board(self):
        self._require()
        layouts = self.env['pb.bank.file.layout'].with_context(active_test=False).search(
            [], order='target desc, name')
        return {
            'layouts': [self._summary(l) for l in layouts
                        if l.active or l.company_id],
            'sources': self._choices('pb.bank.file.column', 'source'),
            'pads': self._choices('pb.bank.file.column', 'pad'),
            'number_formats': self._choices('pb.bank.file.column', 'number_format'),
            'file_types': self._choices('pb.bank.file.layout', 'file_type'),
            'amount_formats': self._choices('pb.bank.file.layout', 'amount_format'),
            'line_endings': self._choices('pb.bank.file.layout', 'line_ending'),
            'tokens': ['{%s}' % t for t in TEMPLATE_TOKENS],
            'company': self.env.company.name,
        }

    @api.model
    def get_layout(self, layout_id):
        return self._detail(self._layout(layout_id))

    # ------------------------------------------------------------ changing
    @api.model
    def copy_layout(self, layout_id):
        layout = self._layout(layout_id)
        copy = layout.pb_copy_for_company(self.env.company)
        return self._detail(copy)

    @api.model
    def save_layout(self, layout_id, values):
        layout = self._own_copy(layout_id)
        values = dict(values or {})
        write = {k: values[k] for k in LAYOUT_FIELDS if k in values}
        for key in ('header_template', 'trailer_template', 'code_label',
                    'code_pattern', 'account_pattern', 'note'):
            if key in write:
                write[key] = (write[key] or '').strip() or False
        if 'name' in write and not (write['name'] or '').strip():
            raise UserError(_("Give the layout a name."))
        known = {k for k, _label in COLUMN_SOURCES}
        rows = values.get('column_rows')
        commands = None
        if rows is not None:
            if not rows:
                raise UserError(_("A bank layout needs at least one column."))
            commands = [(5, 0, 0)]
            for seq, row in enumerate(rows, start=1):
                vals = {k: row.get(k) for k in COLUMN_FIELDS if k in row}
                if vals.get('source') not in known:
                    raise UserError(_("Choose what each column holds."))
                vals['width'] = max(int(vals.get('width') or 0), 0)
                vals['max_length'] = max(int(vals.get('max_length') or 0), 0)
                vals['sequence'] = seq * 10
                commands.append((0, 0, vals))
        if commands is not None:
            write['column_ids'] = commands
        layout.write(write)
        return self._detail(layout)

    @api.model
    def archive_layout(self, layout_id):
        layout = self._own_copy(layout_id)
        layout.write({'active': False})
        return self.get_board()

    @api.model
    def restore_layout(self, layout_id):
        layout = self._own_copy(layout_id)
        layout.write({'active': True})
        return self._detail(layout)

    @api.model
    def preview(self, layout_id):
        layout = self._layout(layout_id)
        if layout.target != 'payment_list':
            raise UserError(_("A preview with sample people is shown for payment-list layouts. The Vietnamese bank file shows its own rows on Pay & deliver."))
        return self.env['pb.payment.list']._pb_preview(layout)
