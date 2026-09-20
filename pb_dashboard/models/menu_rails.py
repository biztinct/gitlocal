# -*- coding: utf-8 -*-
"""Expose the stock application launcher only to platform administrators."""

from odoo import models


PAYROLL_MENU_XMLID = 'om_hr_payroll.menu_hr_payroll_root'
PAYROLL_HOME_XMLID = 'pb_dashboard.action_pb_dashboard'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def load_web_menus(self, debug):
        menus = super().load_web_menus(debug)
        user = self.env.user
        if not user._is_internal() or user._is_system():
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
        if info.get('uid') and user._is_internal() and not user._is_system():
            payroll_home = self.env.ref(PAYROLL_HOME_XMLID,
                                        raise_if_not_found=False)
            if payroll_home:
                info['home_action_id'] = payroll_home.id
        return info
