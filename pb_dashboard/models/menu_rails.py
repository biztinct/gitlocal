# -*- coding: utf-8 -*-
"""Expose the stock application launcher only to platform administrators."""

from odoo import api, models


PAYROLL_MENU_XMLID = 'om_hr_payroll.menu_hr_payroll_root'
PAYROLL_HOME_XMLID = 'pb_dashboard.action_pb_dashboard'
TENANT_SLUG_PARAM = 'pb.tenant.slug'
RECOVERY_LOGIN_PARAM = 'pb_tenancy.recovery_login'
RECOVERY_LOGIN_DEFAULT = 'platform.recovery@payobook.com'


def may_use_full_launcher(env, user=None):
    """Platform admins on the apex, and only recovery on a tenant."""
    user = user or env.user
    if not user._is_system():
        return False
    config = env['ir.config_parameter'].sudo()
    if not (config.get_param(TENANT_SLUG_PARAM, '') or '').strip():
        return True
    recovery = (config.get_param(RECOVERY_LOGIN_PARAM,
                                 RECOVERY_LOGIN_DEFAULT)
                or RECOVERY_LOGIN_DEFAULT).strip().lower()
    return (user.login or '').strip().lower() == recovery


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def get_user_roots(self):
        """Prune the root list exactly as ``load_web_menus`` prunes the tree.

        The two must agree. ``website``'s frontend "go to the backend" corner
        widget (``website/views/website_templates.xml``, rendered under
        ``groups="base.group_user"``) builds its dropdown from
        ``load_menus_root()['children']`` and, with ``force_action=True``,
        indexes ``load_web_menus()`` by each root's id
        (``website/models/ir_ui_menu.py``)::

            not menu['action'] and web_menus[menu['id']]['actionModel']

        ``load_menus_root`` is built from ``get_user_roots`` and so never saw
        the filter below, while ``web_menus`` did. Every action-less root we
        prune is therefore a ``KeyError`` raised while rendering
        ``website.layout`` — a 500 on every frontend page for every signed-in
        internal user, public visitors excepted because the widget is not
        rendered for them at all. Live on ``rize`` 2026-09-22: ``KeyError: 132``
        (the action-less *Calendar* root), reference ``SQ1J-7RQM``.

        The guard mirrors ``load_web_menus``' own ``payroll.id not in menus``,
        so in every branch both views are filtered or neither is.

        ``get_user_roots`` has exactly two readers on this build — the
        ``load_menus_root`` above and ``web/controllers/webmanifest.py``'s
        installable-app shortcuts. The backend launcher reads
        ``load_web_menus`` instead, so this override narrows no screen that the
        filter below was not already narrowing.
        """
        roots = super().get_user_roots()
        user = self.env.user
        if not user._is_internal() or may_use_full_launcher(self.env, user):
            return roots
        payroll = self.env.ref(PAYROLL_MENU_XMLID, raise_if_not_found=False)
        railed = (roots & payroll) if payroll else self.browse()
        # Empty means the payroll root is not visible to this user at all.
        # load_web_menus leaves the menus untouched in that case, so must we:
        # pruning to nothing would hand them an empty launcher.
        return railed or roots

    def load_web_menus(self, debug):
        menus = super().load_web_menus(debug)
        user = self.env.user
        if not user._is_internal() or may_use_full_launcher(self.env, user):
            return menus

        payroll = self.env.ref(PAYROLL_MENU_XMLID, raise_if_not_found=False)
        root = menus.get('root')
        if not payroll or not root or payroll.id not in menus:
            return menus

        keep = set()
        pending = [payroll.id]
        while pending:
            menu_id = pending.pop()
            if menu_id in keep or menu_id not in menus:
                continue
            keep.add(menu_id)
            pending.extend(menus[menu_id].get('children', []))

        filtered = {
            menu_id: menu for menu_id, menu in menus.items()
            if menu_id == 'root' or menu_id in keep
        }
        filtered['root'] = dict(root, children=[payroll.id])
        for menu_id in keep:
            filtered[menu_id] = dict(
                filtered[menu_id],
                children=[child for child in filtered[menu_id].get('children', [])
                          if child in keep],
            )
        return filtered


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        user = self.env.user
        if (info.get('uid') and user._is_internal() and
                not may_use_full_launcher(self.env, user)):
            payroll_home = self.env.ref(PAYROLL_HOME_XMLID,
                                        raise_if_not_found=False)
            if payroll_home:
                info['home_action_id'] = payroll_home.id
        return info
