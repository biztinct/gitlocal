# -*- coding: utf-8 -*-
"""FLEET P4 — the left menu, minus the parts this company has not got.

WHY THE GATE LIVES HERE AND NOT IN `pb_sidebar`. The rail is part of the
product; knowing which parts of the product a company has bought is part of the
PLATFORM LINK. A database running `pb_sidebar` on its own — a demo, a
developer's copy, anything the platform has never heard of — should have a menu
that does not consult a setting nobody writes. So `pb_sidebar` keeps one rule
about permissions, and this module adds one field and one condition to it.

ONE HOOK, TWO ANSWERS. `_state_for` is the single visibility rule: both the
menu somebody is drawn (`get_sidebar_data`) and the menu the Access home says
they have (`visibility_for`) come through it. Overriding it here means the
person passport on the Access board reports the SAME menu the person sees —
including the entries a switch has taken away — with nothing written twice and
nothing to keep in step by hand.

AND IT APPLIES TO ADMINISTRATORS TOO, WHICH IS THE POINT. Every other reason an
entry is hidden is a permission, and an administrator holds all of them. This
one is not a permission: the company has not bought the thing. Showing it to
their administrator would be showing them a door into a product they do not
have — which is worse than useless, because it is the one person who will then
ring up and ask why it does not work.
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PbSidebarSection(models.Model):
    _inherit = 'pb.sidebar.section'

    feature_key = fields.Char(
        string='Part of the product',
        help="When set, this whole block of the menu belongs to a part of "
             "Payobook that can be switched on or off for a company.")


class PbSidebarItem(models.Model):
    _inherit = 'pb.sidebar.item'

    feature_key = fields.Char(
        string='Part of the product',
        help="When set, this entry belongs to a part of Payobook that can be "
             "switched on or off for a company. Switched off, it is either "
             "gone or shown with a padlock — the platform decides which.")

    # =========================================== which entry is which feature
    #
    # THE MENU ENTRY IS FOUND BY THE SURFACE IT OPENS, not by its XML id. Every
    # one of these entries belongs to a different module, and this one depends
    # on none of them — so an XML id would be a hard dependency on five hubs
    # and would fail on a database that has four of them. The client action tag
    # is unique across the whole menu (`pb_sidebar` enforces one entry per
    # surface), it is what the entry is FOR, and it survives a record being
    # rebuilt.
    #
    # Home, Pay Run, People and Settings are absent on purpose: they are the
    # product, not parts of it.
    FEATURE_BY_TAG = {
        'pb_insights_hub': 'insights',
        'pb_workforce': 'workforce',
        'pb_lifecycle_hub': 'lifecycle',
        'pb_compliance_hub': 'compliance',
        'learn_journey': 'learn',
    }

    @api.model
    def _seed_feature_keys(self):
        """Stamp the five, quietly skip whatever is not on this database.

        Called from this module's data file, so it runs on install and on every
        upgrade. Writes only where the value would change: a no-op upgrade must
        not touch nine rows and invalidate a cache for nothing.
        """
        written = 0
        for tag, key in self.FEATURE_BY_TAG.items():
            items = self.sudo().with_context(active_test=False).search(
                [('action_tag', '=', tag)])
            for item in items:
                if (item.feature_key or '') != key:
                    item.write({'feature_key': key})
                    written += 1
        if written:
            _logger.info("pb_tenancy: %d menu entries linked to a part of the "
                         "product", written)
        return True

    # ------------------------------------------------------------- the rule
    def _state_for(self, item, is_admin, user_groups):
        """The permission rule first, then the one question it cannot answer.

        ORDER MATTERS AND IT IS THIS WAY ROUND ON PURPOSE. Somebody who has no
        permission for an entry does not see it whether or not the company has
        bought it — that is the older, stricter answer and it stays first. Only
        an entry the person WOULD have been shown is then asked whether the
        company has it at all.
        """
        visible, locked = super()._state_for(item, is_admin, user_groups)
        if not visible:
            return visible, locked
        on, mode, _text = self.env['pb.tenancy'].feature_state(item.feature_key)
        if on:
            return visible, locked
        if mode == 'lock':
            return True, True
        return False, False

    def _feature_lock_text(self, item):
        """The padlock's own sentence, when a switch is what locked the entry.

        `get_sidebar_data` falls back to the standard upsell line, which talks
        about "the full Payobook platform" — right for a demo, wrong for a
        customer who has the platform and not this one part of it. So the
        feature's own line wins where there is one.
        """
        on, mode, text = self.env['pb.tenancy'].feature_state(item.feature_key)
        if not on and mode == 'lock':
            return text
        return ''

    def _section_state_for(self, section, is_admin):
        """Same question for a whole block of the menu."""
        visible, locked, reason = super()._section_state_for(section, is_admin)
        if not visible:
            return visible, locked, reason
        on, mode, text = self.env['pb.tenancy'].feature_state(
            section.feature_key)
        if on:
            return visible, locked, reason
        if mode == 'lock':
            return True, True, text
        return False, False, ''

    # ------------------------------------------------- the drawn menu only
    #
    # `@api.model` HAS TO BE WRITTEN AGAIN HERE. It is not inherited: the
    # framework reads it off the function it is about to call
    # (`odoo/service/model.py:86`), so an override that leaves it out turns a
    # model-level method into a record-level one for every browser that asks —
    # and the browser sends no ids, so the whole left menu dies with
    # "list index out of range" and every page loses its navigation. Nothing in
    # a Python test can see it, because Python calls it directly and both
    # shapes work there.
    @api.model
    def get_sidebar_data(self):
        """Unchanged, except that a padlock put there by a switch says why.

        The base builds the whole tree and stamps the standard upsell line on
        anything locked. Rather than copy two hundred lines of tree-building to
        change one string, the tree is walked once afterwards and the entries
        this module locked are given their own sentence. Cheap (nine entries),
        and it cannot drift from the base's structure because it reads it.
        """
        result = super().get_sidebar_data()
        feats = self.env['pb.tenancy'].features()
        if not feats:
            return result
        by_id = {i.id: i for i in self.sudo().search([('active', '=', True)])}

        # THE HEADING MATTERS AS MUCH AS THE SENTENCE. The rail's own padlock
        # says "Available in the full platform", which is right for a
        # demonstration database and wrong for a paying customer — they ARE on
        # the full platform; they have not bought this one part of it. So a
        # padlock this module put there names itself.
        title = _("Not switched on for your company")

        def walk(entries):
            for entry in entries:
                item = by_id.get(entry.get('id'))
                if item is not None and entry.get('restricted'):
                    text = self._feature_lock_text(item)
                    if text:
                        entry['restriction_reason'] = text
                        entry['restriction_title'] = title
                walk(entry.get('children') or [])

        secs = {s.id: s for s in self.env['pb.sidebar.section'].sudo().search([])}
        for section in result:
            sec = secs.get(section.get('id'))
            if sec is not None and section.get('restricted'):
                on, mode, text = self.env['pb.tenancy'].feature_state(
                    sec.feature_key)
                if not on and mode == 'lock':
                    section['restriction_reason'] = text
                    section['restriction_title'] = title
            walk(section.get('items') or [])
        return result
