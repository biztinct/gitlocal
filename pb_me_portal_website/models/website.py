# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The employee pages' own top bar: which pages get it, and which logo it shows."""
import re

from odoo import models
from odoo.http import request

#: `/my`, `/my/...`, and the same behind a language prefix (`/vi/my/leave`).
_EMPLOYEE_PAGE = re.compile(r'^(?:/[a-z]{2,3}(?:_[A-Za-z0-9@]+)?)?/my(?:/|$)')


class Website(models.Model):
    _inherit = 'website'

    def _pbme_bare_page(self):
        """True on the employee pages (`/my…`): they get the slim top bar and
        no website footer. Exception-safe — the page can never 500 on it."""
        try:
            return bool(request and _EMPLOYEE_PAGE.match(request.httprequest.path or ''))
        except Exception:               # noqa: BLE001
            return False

    def _pbme_logo_url(self):
        """The tenant's own logo for the employee top bar: the website's logo
        if it was ever changed, else the company's, else False (the bar then
        shows the company name). Never the stock "Your Logo" placeholder."""
        self.ensure_one()
        site = self.sudo()
        if site.logo and site.logo != site._default_logo():
            return site.image_url(site, 'logo')
        company = site.company_id
        if company.logo and not company.uses_default_logo:
            return '/logo.png?company=%s' % company.id
        return False
