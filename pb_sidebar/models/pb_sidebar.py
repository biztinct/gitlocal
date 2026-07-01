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
    restricted = fields.Boolean(
        string='Restricted (upsell)', default=False,
        help='If set, non-admin users see this section LOCKED — its items stay '
             'collapsed and it cannot be expanded (shown with an upsell dialog). '
             'Admins are unaffected and can still expand it.')
    restriction_reason = fields.Text(
        string='Restriction Message',
        help='Message shown when a locked section is clicked.')


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
    restricted = fields.Boolean(
        string='Restricted (upsell)', default=False,
        help='If set, users who lack this item\'s groups still SEE it — shown locked '
             'with an upsell dialog instead of being hidden.')
    restriction_reason = fields.Text(
        string='Restriction Message',
        help='Message shown when a locked item is clicked.')

    _DEFAULT_UPSELL = ("This functionality is available in the full Payobook platform. "
                       "Please contact Payobook to arrange a personalised demonstration.")

    @api.model
    def get_sidebar_data(self):
        user = self.env.user
        is_admin = user.has_group('base.group_system')

        sections = self.env['pb.sidebar.section'].search(
            [('active', '=', True)], order='sequence, id')
        all_items = self.search(
            [('active', '=', True)], order='section_id, sequence, id')

        # Odoo 19 renamed res.users.groups_id -> group_ids; all_group_ids includes implied.
        user_groups = user.all_group_ids

        def _has_access(item):
            return is_admin or not item.groups_id or bool(item.groups_id & user_groups)

        def _state(item):
            """(visible, locked): items the user can't access are hidden, unless
            flagged restricted — then shown locked (upsell) instead of hidden."""
            if _has_access(item):
                return True, False
            if item.restricted:
                return True, True
            return False, False

        def _split(val):
            return [v.strip() for v in (val or '').split(',') if v.strip()]

        def _item_dict(item, locked):
            return {
                'id': item.id,
                'name': item.name,
                'icon': item.icon or 'circle',
                'badge': item.badge or False,
                'action_xmlid': (item.action_xmlid or False) if not locked else False,
                'action_tag': (item.action_tag or False) if not locked else False,
                'match_action_xmlids': _split(item.match_action_xmlids),
                'match_action_tags': _split(item.match_action_tags),
                'match_models': _split(item.match_models),
                'restricted': locked,
                'restriction_reason': (item.restriction_reason or self._DEFAULT_UPSELL) if locked else False,
                'children': [],
            }

        result = []
        for section in sections:
            sec_items = all_items.filtered(lambda i, s=section: i.section_id == s)
            tops = sec_items.filtered(lambda i: not i.parent_id).sorted(lambda i: (i.sequence, i.id))
            items = []
            for top in tops:
                vis, locked = _state(top)
                if not vis:
                    continue
                d = _item_dict(top, locked)
                kids = sec_items.filtered(lambda c, p=top: c.parent_id == p).sorted(
                    lambda c: (c.sequence, c.id))
                kid_dicts = []
                for k in kids:
                    kvis, klocked = _state(k)
                    if kvis:
                        kid_dicts.append(_item_dict(k, klocked))
                d['children'] = kid_dicts
                items.append(d)
            sec_locked = bool(section.restricted) and not is_admin
            if not items and not sec_locked:
                continue
            result.append({
                'id': section.id,
                'name': section.name,
                'key': section.technical_key,
                'show_label': section.show_label,
                'restricted': sec_locked,
                'restriction_reason': (section.restriction_reason or self._DEFAULT_UPSELL) if sec_locked else False,
                'items': items,
            })
        return result
