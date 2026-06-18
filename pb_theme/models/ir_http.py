from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Expose the VU Form Engine kill-switch to the web client.

        Set ``pb_theme.vu_form_engine = off`` (ir.config_parameter) to
        instantly revert every form to stock Odoo rendering without a deploy.
        """
        info = super().session_info()
        info["vu_form_engine"] = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("pb_theme.vu_form_engine", "on")
        )
        return info
