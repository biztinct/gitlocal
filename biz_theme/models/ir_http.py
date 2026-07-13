from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Expose biz_theme runtime flags to the web client.

        - ``vu_form_engine``: kill-switch for the VU Form Engine. Set
          ``biz_theme.vu_form_engine = off`` (ir.config_parameter) to revert
          every form to stock Odoo rendering without a deploy. The legacy
          ``pb_theme.vu_form_engine`` key is still honoured so live databases
          keep working after the pb_theme → biz_theme split.
        - ``biz_theme_version``: published runtime-theme version, used by the
          Theme Studio to invalidate cached tokens.css.
        """
        info = super().session_info()
        icp = self.env["ir.config_parameter"].sudo()
        info["vu_form_engine"] = icp.get_param(
            "biz_theme.vu_form_engine",
            icp.get_param("pb_theme.vu_form_engine", "on"),
        )
        info["biz_theme_version"] = icp.get_param("biz_theme.theme_version", "0")
        # Brand/app name for the browser-tab title. Same resolution chain as the
        # backend favicon/title template (webclient_templates.xml): an explicit
        # `biz_theme.app_name` knob wins, then the debrand suite's keys if
        # installed, then the current company name, then "Odoo". The core JS
        # title service hard-codes "Odoo" as its empty-title fallback and runs
        # AFTER the server-rendered <title>, so biz_title_service.js reads this
        # to keep the tab branded.
        info["biz_app_name"] = (
            icp.get_param("biz_theme.app_name")
            or icp.get_param("biz_debrand.brand_name")
            or icp.get_param("web_debranding.new_title")
            or (self.env.company.name if self.env.company else None)
            or "Odoo"
        )
        # Menu-driven sidebar: comma-separated root-menu xml_ids for which the
        # zero-config BizSidebar renders (empty = feature off).
        info["biz_menu_sidebar_apps"] = [
            x.strip()
            for x in icp.get_param("biz_theme.menu_sidebar_apps", "").split(",")
            if x.strip()
        ]
        return info
