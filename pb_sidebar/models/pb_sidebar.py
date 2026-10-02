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

    # ========================================================== THE RULE, ONCE
    #
    # WHO SEES WHAT IS DECIDED IN EXACTLY ONE PLACE, AND THIS IS IT. Two
    # questions are asked of it: "draw MY menu" (`get_sidebar_data`, on every
    # page load) and "what does THIS PERSON'S menu look like" (`visibility_for`,
    # asked by the Access home's person passport). They are the same rule, so
    # they are the same three lines — not two copies that agree today. A second
    # copy is a copy that will one day disagree, and it would disagree by
    # telling somebody with the access board open that a colleague can reach a
    # screen the colleague cannot see.
    #
    # The rule itself: an administrator sees everything; an entry with no
    # permissions on it is open to everybody; otherwise holding ANY ONE of the
    # permissions named on it is enough, and holding is transitive
    # (`all_group_ids`, never `group_ids`, which is direct membership only).
    # Somebody who cannot reach an entry does not see it AT ALL — unless it is
    # flagged as a teaser, in which case they see it locked, with a note.

    def _access_of(self, user):
        """(is this person an administrator, everything they actually hold).

        `sudo()` because the caller may legitimately be asking about SOMEBODY
        ELSE — reading another person's group membership is not something an
        ordinary reader may do, and answering "what does their menu look like"
        is not the same as handing them the membership list.
        """
        user = user.sudo()
        # Odoo 19 renamed res.users.groups_id -> group_ids; all_group_ids
        # includes everything implied by a ladder.
        return user.has_group('base.group_system'), user.all_group_ids

    def _state_for(self, item, is_admin, user_groups):
        """(visible, locked): items the user can't access are hidden, unless
        flagged restricted — then shown locked (upsell) instead of hidden.

        THE ONE HOOK. Anything that adds a new reason to hide or lock an entry
        overrides THIS method and nothing else — `get_sidebar_data` and
        `visibility_for` both come through here, so the menu somebody is drawn
        and the menu the access board says they have cannot disagree. FLEET P4
        adds the feature switches this way.
        """
        if is_admin or not item.groups_id or bool(item.groups_id & user_groups):
            return True, False
        if item.restricted:
            return True, True
        return False, False

    def _section_state_for(self, section, is_admin):
        """(visible, locked, reason) for a whole block of the rail.

        Extracted so a section has the same single hook an item has. It was
        two identical expressions in two methods, which is a disagreement
        waiting for its first extra condition — and FLEET P4 is that condition.
        """
        locked = bool(section.restricted) and not is_admin
        return True, locked, (
            (section.restriction_reason or self._DEFAULT_UPSELL) if locked else '')

    @api.model
    def visibility_for(self, user):
        """Every entry on the left menu, as ONE PERSON sees it.

        `{'items': {id: 'on' | 'locked' | 'hidden'},
          'sections': {id: 'on' | 'locked'}}` over every ACTIVE section and
        item — including the ones this person does not get, because "what do
        they not have" is half of what somebody looking at their access is
        asking.

        Keys are integers on purpose: this is a python-to-python helper for
        another module's server code, never an RPC answer of its own. The
        Access home draws it; the rule stays here.
        """
        is_admin, user_groups = self._access_of(user)
        sections = self.env['pb.sidebar.section'].sudo().search(
            [('active', '=', True)])
        items = self.sudo().search([('active', '=', True)])
        out_items = {}
        for item in items:
            visible, locked = self._state_for(item, is_admin, user_groups)
            out_items[item.id] = ('locked' if locked
                                  else ('on' if visible else 'hidden'))
        out_sections = {}
        for sec in sections:
            visible, locked, _reason = self._section_state_for(sec, is_admin)
            out_sections[sec.id] = ('locked' if locked
                                    else ('on' if visible else 'hidden'))
        return {'items': out_items, 'sections': out_sections}

    @api.model
    def get_sidebar_data(self):
        user = self.env.user
        is_admin, user_groups = self._access_of(user)

        sections = self.env['pb.sidebar.section'].search(
            [('active', '=', True)], order='sequence, id')
        all_items = self.search(
            [('active', '=', True)], order='section_id, sequence, id')

        def _state(item):
            return self._state_for(item, is_admin, user_groups)

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
            sec_visible, sec_locked, sec_reason = self._section_state_for(
                section, is_admin)
            if not sec_visible:
                continue
            if not items and not sec_locked:
                continue
            result.append({
                'id': section.id,
                'name': section.name,
                'key': section.technical_key,
                'show_label': section.show_label,
                'restricted': sec_locked,
                'restriction_reason': sec_reason or False,
                'items': items,
            })
        return result
