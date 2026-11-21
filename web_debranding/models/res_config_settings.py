# Copyright 2021-2022 Ivan Yelizariev <https://it-projects.info/team/yelizariev>
# License OPL-1 (https://www.odoo.com/documentation/user/14.0/legal/licenses/licenses.html#odoo-apps) for derivative work.
# Odoo 19 compatibility: fields_view_get replaced with _get_view

from lxml import etree

from odoo import api, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Odoo 19: Replaced fields_view_get with _get_view."""
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)

        if view.name != "res.config.settings.view.form":
            return arch, view

        doc = arch  # arch is already an etree Element in Odoo 19

        general_redirect_queries = [
            "//div[@id='sms']",
            "//div[@id='partner_autocomplete']",
            "//div[@id='iap_portal']",
        ]
        for query in general_redirect_queries:
            for item in doc.xpath(query):
                item.getparent().remove(item)

        crm_redirect_queries = [
            "//div[@id='crm_iap_lead_settings']",
            "//div[@id='crm_iap_lead_website_settings']",
            "//div[@id='crm_iap_lead_enrich']",
            "//div[@id='crm_iap_mine_settings']",
            "//div[@id='crm_iap_enrich_settings']",
        ]
        for query in crm_redirect_queries:
            for item in doc.xpath(query):
                checkbox = item.getprevious()
                if checkbox is not None:
                    checkbox.getparent().remove(checkbox)
                item.getparent().remove(item)

        snailmail_query = "//div[@id='send_invoices_followups']"
        for item in doc.xpath(snailmail_query):
            item.set("style", "display:none")

        sms_confirmation_query = "//div[@id='stock_sms']"
        for item in doc.xpath(sms_confirmation_query):
            item.set("style", "display:none")

        enterprise_query = "//div[div[field[@widget='upgrade_boolean']]]"
        for item in doc.xpath(enterprise_query):
            item.set("style", "display:none")

        container_query = "//div[@class='row mt16 o_settings_container']"
        for item in doc.xpath(container_query):
            if not item.getchildren():
                title = item.getprevious()
                if title is not None:
                    title.getparent().remove(title)
                item.getparent().remove(item)

        return arch, view
