# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PbSidebarSection(models.Model):
    _name = 'pb.sidebar.section'
    _description = 'Payobook Sidebar Section'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    technical_key = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    show_label = fields.Boolean(default=True, help='Render the section header label.')
    active = fields.Boolean(default=True)
    item_ids = fields.One2many('pb.sidebar.item', 'section_id', string='Menu Items')


class PbSidebarItem(models.Model):
    _name = 'pb.sidebar.item'
    _description = 'Payobook Sidebar Item'
    _order = 'section_id, sequence, id'

    name = fields.Char(required=True, translate=True)
    section_id = fields.Many2one(
        'pb.sidebar.section', required=True, ondelete='cascade', string='Section')
    parent_id = fields.Many2one(
        'pb.sidebar.item', string='Parent Item', ondelete='cascade',
        help='When set, this item is a sub-menu shown under its parent.')
    sequence = fields.Integer(default=10)
    icon = fields.Char(string='Lucide Icon', default='circle',
                       help='Lucide icon name, e.g. home, calendar, receipt')
    action_xmlid = fields.Char(
        string='Action XML ID',
        help='XML ID of the action to open on click, e.g. pb_hr_payroll_base.action_hr_payslip_payroll')
    action_tag = fields.Char(string='Client Action Tag')
    badge = fields.Char(string='Badge', help='Optional small badge text, e.g. a count')
    groups_id = fields.Many2many('res.groups', string='Allowed Groups',
                                 help='If set, only users in these groups see this item.')
    active = fields.Boolean(default=True)
    match_action_xmlids = fields.Char(string='Match Action XML IDs')
    match_action_tags = fields.Char(string='Match Action Tags')
    match_models = fields.Char(string='Match Models')

    @api.model
    def get_sidebar_data(self):
        user = self.env.user
        is_admin = user.has_group('base.group_system')

        sections = self.env['pb.sidebar.section'].search(
            [('active', '=', True)], order='sequence, id')
        all_items = self.search(
            [('active', '=', True)], order='section_id, sequence, id')

        if is_admin:
            visible = all_items
        else:
            visible = all_items.filtered(
                lambda i: not i.groups_id or (i.groups_id & user.groups_id))

        def _split(val):
            return [v.strip() for v in (val or '').split(',') if v.strip()]

        def _item_dict(item):
            return {
                'id': item.id,
                'name': item.name,
                'icon': item.icon or 'circle',
                'badge': item.badge or False,
                'action_xmlid': item.action_xmlid or False,
                'action_tag': item.action_tag or False,
                'match_action_xmlids': _split(item.match_action_xmlids),
                'match_action_tags': _split(item.match_action_tags),
                'match_models': _split(item.match_models),
                'children': [],
            }

        result = []
        for section in sections:
            sec_items = visible.filtered(lambda i, s=section: i.section_id == s)
            tops = sec_items.filtered(lambda i: not i.parent_id).sorted(lambda i: (i.sequence, i.id))
            items = []
            for top in tops:
                d = _item_dict(top)
                kids = sec_items.filtered(lambda c, p=top: c.parent_id == p).sorted(
                    lambda c: (c.sequence, c.id))
                d['children'] = [_item_dict(k) for k in kids]
                items.append(d)
            if not items:
                continue
            result.append({
                'id': section.id,
                'name': section.name,
                'key': section.technical_key,
                'show_label': section.show_label,
                'items': items,
            })
        return result
