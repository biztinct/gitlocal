"""Apply the country coverage update to website-specific editor copies.

Website copy-on-write views can retain an edited old architecture after the
module's generic homepage is upgraded. Keep each copy's website and parent,
but bring its homepage content into line with the new module design.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"lang": "en_US"})
    source = env.ref("pb_website.pb_website_homepage")
    copies = env["ir.ui.view"].with_context(active_test=False).search([
        ("key", "=", source.key),
        ("website_id", "!=", False),
        ("id", "!=", source.id),
    ])
    # Website view writes operate on a singleton because of copy-on-write.
    for copy in copies:
        copy.write({"arch_db": source.arch_db, "name": source.name})

    for page in env["website.page"].search([("url", "=", "/")]):
        page.write({"website_meta_description": (
            "Intelligent global payroll. Ready templates for South East Asia + India. "
            "Supports payroll processing of all countries. Explore PayAI analytics, "
            "the formula engine, intelligent mappings and Payslip Studio."
        )})
