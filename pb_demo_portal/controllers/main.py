# -*- coding: utf-8 -*-
import logging
import re

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

# Free / consumer email providers rejected for a business demo.
FREE_EMAIL_DOMAINS = {
    'gmail.com', 'googlemail.com', 'hotmail.com', 'hotmail.co.uk', 'outlook.com',
    'live.com', 'msn.com', 'yahoo.com', 'yahoo.co.uk', 'yahoo.co.in', 'ymail.com',
    'icloud.com', 'me.com', 'mac.com', 'proton.me', 'protonmail.com', 'aol.com',
    'gmx.com', 'gmx.net', 'mail.com', 'zoho.com', 'yandex.com', 'qq.com',
    '163.com', '126.com', 'hotmail.fr', 'live.fr', 'orange.fr', 'rediffmail.com',
}
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

INDUSTRIES = ['Retail', 'Manufacturing', 'Logistics', 'Technology', 'Construction',
              'Financial Services', 'Healthcare', 'Hospitality', 'Education', 'Other']
COMPANY_SIZES = ['1–50', '51–200', '201–500', '501–1,000', '1,001–5,000', '5,000+']


class DemoPortal(http.Controller):

    def _render_form(self, values=None, error=None):
        Country = request.env['res.country'].sudo()
        return request.render('pb_demo_portal.register_page', {
            'countries': Country.search([], order='name'),
            'industries': INDUSTRIES,
            'company_sizes': COMPANY_SIZES,
            'values': values or {},
            'error': error,
        })

    @http.route(['/demo', '/demo/register'], type='http', auth='public',
                website=True, sitemap=True)
    def demo_register_form(self, **kw):
        return self._render_form()

    @http.route('/demo/register/submit', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def demo_register_submit(self, **post):
        values = {k: (post.get(k) or '').strip() for k in
                  ('name', 'company', 'email', 'mobile', 'country_id', 'industry', 'company_size')}
        # --- validation ---
        required = ['name', 'company', 'email', 'mobile', 'country_id', 'industry', 'company_size']
        if any(not values.get(f) for f in required):
            return self._render_form(values, _("Please complete all fields."))
        email = values['email'].lower()
        if not EMAIL_RE.match(email):
            return self._render_form(values, _("Please enter a valid email address."))
        domain = email.split('@')[-1]
        if domain in FREE_EMAIL_DOMAINS:
            return self._render_form(values, _("Please enter your business email address."))

        # --- already registered? offer login ---
        existing = request.env['res.users'].sudo().with_context(active_test=False).search(
            [('login', '=', email)], limit=1)
        if existing:
            return request.render('pb_demo_portal.register_done', {
                'email': email, 'already': True})

        # --- create the demo user + send the verification / set-password email ---
        try:
            self._create_demo_user(values, email)
        except Exception as e:  # pragma: no cover - keep the portal resilient
            _logger.exception("Demo registration failed: %s", e)
            return self._render_form(values, _(
                "Something went wrong creating your demo account. Please try again."))
        return request.render('pb_demo_portal.register_done', {'email': email, 'already': False})

    def _create_demo_user(self, values, email):
        env = request.env
        group = env.ref('pb_demo.group_payobook_demo', raise_if_not_found=False)
        company = env['res.company'].sudo().with_context(active_test=False).search(
            [('name', '=', 'Payobook Vietnam JSC')], limit=1) or env.company
        Users = env['res.users'].sudo().with_context(
            no_reset_password=True, mail_create_nosubscribe=True)
        country_id = int(values['country_id']) if values.get('country_id') else False
        user_vals = {
            'name': values['name'],
            'login': email,
            'email': email,
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
        }
        # Assign groups explicitly (this Odoo build does not flatten implied
        # groups into membership at create-time): demo + internal user + PayAI so
        # the copilot works for every new signup.
        gids = []
        if group:
            gids.append(group.id)
        internal = env.ref('base.group_user', raise_if_not_found=False)
        if internal:
            gids.append(internal.id)
        payai = env.ref('pb_payroll_ai_insights.group_payai_user', raise_if_not_found=False)
        if payai:
            gids.append(payai.id)
        if gids:
            user_vals['group_ids'] = [(6, 0, gids)]
        user = Users.create(user_vals)
        # enrich the partner with the captured profile (Odoo 19 res.partner has no
        # 'mobile' field — use 'phone'; fold company/size into the comment).
        user.partner_id.sudo().write({
            'phone': values.get('mobile'),
            'country_id': country_id,
            'function': values.get('industry'),
            'comment': "Demo signup — Company: %s · Industry: %s · Company size: %s" % (
                values.get('company'), values.get('industry'), values.get('company_size')),
        })
        # auth_signup: prepare a signup token and email the set-password link
        user.partner_id.sudo().signup_prepare()
        try:
            user.sudo().action_reset_password()
        except Exception as e:  # SMTP may be unconfigured on the demo box
            _logger.warning("Demo signup email not sent (mail server?): %s", e)
        return user
