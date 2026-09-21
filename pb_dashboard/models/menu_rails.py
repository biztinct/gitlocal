# -*- coding: utf-8 -*-
"""Expose the stock application launcher only to platform administrators."""

from odoo import models


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
