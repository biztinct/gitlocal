"""Align homepage search and social metadata with the payroll redesign."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"lang": "en_US"})
    for page in env["website.page"].search([("url", "=", "/")]):
        page.write({
            "website_meta_title": "Payobook — Intelligent Global Payroll",
            "website_meta_description": (
                "Intelligent global payroll, focused on Southeast Asia and India. "
                "Explore PayAI analytics and summaries, the formula engine, "
                "intelligent mappings and Payslip Studio."
            ),
        })
