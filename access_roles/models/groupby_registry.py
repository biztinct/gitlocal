# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import re
from odoo import api, fields, models
from odoo.fields import Command


class GroupByRegistry(models.Model):
    """Stores and manages group_by filters from search views."""
    _name = 'groupby.registry'
    _description = 'GroupBy Registry'

    name = fields.Char(string='GroupBy Name', required=True)
    context = fields.Char(string='Context')
    string = fields.Char(string='Display Name')
    active = fields.Boolean(default=True)
    model_id = fields.Many2one('ir.model', string='Model', ondelete='cascade')
    view_ids = fields.Many2many('ir.ui.view', string='View')

    @api.model
    def _register_hook(self):
        """Triggers group_by extraction during module initialization.
        Gated on the ir.ui.view signature (see access.registry.sync)."""
        super()._register_hook()
        if self.env['access.registry.sync'].needs_sync('access_roles.sync.groupby'):
            self.get_all_groupby()
        return True

    def _extract_groupby_attributes(self, filter_tag):
        """Extract attributes from a group_by filter tag."""
        name_match = re.search(r'name="([^"]*)"', filter_tag)
        context_match = re.search(r'context="([^"]*)"', filter_tag)
        string_match = re.search(r'string="([^"]*)"', filter_tag)

        technical_name = name_match.group(1) if name_match else ''
        display_name = string_match.group(1) if string_match else ''

        return {
            'name': technical_name,
            'context': context_match.group(1) if context_match else '',
            'string': display_name
        }

    def get_all_groupby(self):
        """Collect all group_by filters defined in search views."""
        search_views = self.env['ir.ui.view'].search([('type', '=', 'search')])
        groupby_model = {}
        for view in search_views:
            if not view.arch:
                continue
            model_name = view.model
            if model_name not in groupby_model:
                groupby_model[model_name] = {
                    'groupby': [],
                    'view_ids': []
                }
            groupby_tags = re.findall(
                r'<filter[^>]+?context="[^"]*group_by[^"]*"[^>]*?/>', view.arch)
            for groupby_tag in groupby_tags:
                attributes = self._extract_groupby_attributes(groupby_tag)
                if not attributes['name']:
                    continue
                groupby_info = {
                    'name': attributes['name'],
                    'context': attributes['context'],
                    'string': attributes['string']
                }
                if groupby_info not in groupby_model[model_name]['groupby']:
                    groupby_model[model_name]['groupby'].append(groupby_info)
            if view.id not in groupby_model[model_name]['view_ids']:
                groupby_model[model_name]['view_ids'].append(view.id)
        for model_name, data in groupby_model.items():
            if not model_name:
                continue
            model_record = self.env['ir.model'].search([('model', '=', model_name)],
                                                       limit=1)
            if not model_record:
                continue
            for groupby_info in data['groupby']:
                self._create_or_update_groupby(
                    groupby_info['name'],
                    model_record.id,
                    data['view_ids'],
                    groupby_info['context'],
                    groupby_info['string']
                )
        return groupby_model

    def _create_or_update_groupby(self, name, model_id, view_ids, context, string):
        """Create or update a groupby registry record."""
        display_name = string if string else name
        # search by the stored value (display_name) — searching by the
        # technical name never matched, re-creating every labelled group_by
        # on every sync (same defect as filter_registry)
        existing_groupby = self.search([
            ('name', '=', display_name),
            ('model_id', '=', model_id)
        ], limit=1)
        if existing_groupby:
            # diff-aware: only touch the row when something actually changed
            updates = {}
            if existing_groupby.name != display_name:
                updates['name'] = display_name
            if (existing_groupby.context or '') != (context or ''):
                updates['context'] = context
            if (existing_groupby.string or '') != (string or ''):
                updates['string'] = string
            missing = set(view_ids) - set(existing_groupby.view_ids.ids)
            if missing:
                updates['view_ids'] = [Command.link(v) for v in missing]
            if updates:
                existing_groupby.write(updates)
        else:
            self.create({
                'name': display_name,
                'model_id': model_id,
                'view_ids': [Command.link(view) for view in view_ids],
                'context': context,
                'string': string
            })
