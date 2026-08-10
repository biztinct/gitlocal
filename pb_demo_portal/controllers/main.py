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
            user = self._create_demo_user(values, email)
        except Exception as e:  # pragma: no cover - keep the portal resilient
            _logger.exception("Demo registration failed: %s", e)
            return self._render_form(values, _(
                "Something went wrong creating your demo account. Please try again."))
        # Drop a CRM lead into the pipeline so Sales can track / follow up every
        # signup. Non-fatal: never blocks the demo account if crm is absent.
        self._create_demo_lead(values, email, user.partner_id)
        return request.render('pb_demo_portal.register_done', {'email': email, 'already': False})

    def _create_demo_lead(self, values, email, partner=None):
        """Create a ``crm.lead`` for a self-service demo signup so it surfaces in
        the CRM pipeline for follow-up. No-op if the crm module isn't installed,
        and never raises into the signup flow (lead capture must not break the
        demo account)."""
        env = request.env
        if 'crm.lead' not in env:
            return
        try:
            country_id = int(values['country_id']) if values.get('country_id') else False
            source = env['utm.source'].sudo().search(
                [('name', '=', 'Demo Signup')], limit=1)
            if not source:
                source = env['utm.source'].sudo().create({'name': 'Demo Signup'})
            lead_vals = {
                'name': u"Demo signup — %s" % (values.get('company') or values.get('name')),
                'type': 'lead',
                'contact_name': values.get('name'),
                'partner_name': values.get('company'),
                'email_from': email,
                'phone': values.get('mobile'),
                'country_id': country_id,
                'source_id': source.id,
                'description': (
                    u"Self-service demo signup via payobook.com/demo/register\n"
                    u"Industry: %s\nCompany size: %s"
                    % (values.get('industry') or u'—', values.get('company_size') or u'—')),
            }
            if partner:
                lead_vals['partner_id'] = partner.id
            env['crm.lead'].sudo().create(lead_vals)
        except Exception as e:  # pragma: no cover - lead capture is best-effort
            _logger.warning("Demo signup lead not created for %s: %s", email, e)

    # ------------------------------------------------------------------ #
    #  Private-demo enquiry  (WOW landing → lead email, no account made)  #
    # ------------------------------------------------------------------ #
    def _notify_company(self):
        """The company whose *email* is the single system address used for
        outgoing mail / password resets / lead notifications. Configured in
        Settings → Companies → Email. We prefer the Payobook demo company,
        then the website company, then the current company."""
        Company = request.env['res.company'].sudo().with_context(active_test=False)
        return (Company.search([('name', '=', 'Payobook Vietnam JSC')], limit=1)
                or (request.website and request.website.company_id)
                or request.env.company)

    def _render_private_form(self, values=None, error=None):
        Country = request.env['res.country'].sudo()
        return request.render('pb_demo_portal.private_demo_page', {
            'countries': Country.search([], order='name'),
            'company_sizes': COMPANY_SIZES,
            'values': values or {},
            'error': error,
        })

    @http.route('/demo/private', type='http', auth='public', website=True, sitemap=False)
    def private_demo_form(self, **kw):
        return self._render_private_form()

    @http.route('/demo/private/submit', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def private_demo_submit(self, **post):
        values = {k: (post.get(k) or '').strip() for k in
                  ('name', 'company', 'email', 'mobile', 'country_id',
                   'company_size', 'message')}
        # --- validation ---
        required = ['name', 'company', 'email', 'mobile']
        if any(not values.get(f) for f in required):
            return self._render_private_form(values, _("Please complete all required fields."))
        email = values['email'].lower()
        if not EMAIL_RE.match(email):
            return self._render_private_form(values, _("Please enter a valid email address."))
        if email.split('@')[-1] in FREE_EMAIL_DOMAINS:
            return self._render_private_form(values, _("Please enter your business email address."))

        try:
            self._send_private_demo_emails(values, email)
        except Exception as e:  # pragma: no cover - keep the portal resilient
            _logger.exception("Private-demo enquiry failed: %s", e)
            return self._render_private_form(values, _(
                "Something went wrong sending your request. Please try again."))
        return request.render('pb_demo_portal.private_demo_done', {'email': email})

    def _send_private_demo_emails(self, values, email):
        env = request.env
        company = self._notify_company()
        notify_to = company.email or company.partner_id.email_normalized
        if not notify_to:
            _logger.warning(
                "Private-demo enquiry received but no company email is configured "
                "(Settings → Companies → Email). Lead: %s <%s>", values['name'], email)
        country = ''
        if values.get('country_id'):
            c = env['res.country'].sudo().browse(int(values['country_id']))
            country = c.name or ''
        Mail = env['mail.mail'].sudo()

        def _row(label, val):
            if not val:
                return ''
            return (u"<tr><td style='padding:6px 14px;color:#8A87A0;font-size:13px;'>%s</td>"
                    u"<td style='padding:6px 14px;color:#1B1733;font-size:13px;font-weight:600;'>%s</td></tr>"
                    % (label, val))

        # 1) Notify the Payobook team (the configured company inbox).
        if notify_to:
            rows = (_row('Name', values['name']) + _row('Company', values['company'])
                    + _row('Work email', email) + _row('Phone', values.get('mobile'))
                    + _row('Country', country) + _row('Company size', values.get('company_size')))
            msg_html = ''
            if values.get('message'):
                msg_html = (u"<div style='margin-top:16px;padding:14px 16px;background:#F4F5FB;"
                            u"border-radius:12px;color:#4B5168;font-size:14px;line-height:1.6;'>%s</div>"
                            % values['message'].replace('\n', '<br/>'))
            team_body = (
                u"<div style='font-family:Segoe UI,Roboto,Arial,sans-serif;color:#1B1733;'>"
                u"<h2 style='margin:0 0 4px;font-size:20px;'>New private-demo request</h2>"
                u"<p style='margin:0 0 16px;color:#8A87A0;font-size:13px;'>Submitted via payobook.com</p>"
                u"<table style='border-collapse:collapse;'>%s</table>%s</div>" % (rows, msg_html))
            Mail.create({
                'subject': u"Private demo request — %s (%s)" % (values['name'], values['company']),
                'email_from': company.email or notify_to,
                'email_to': notify_to,
                'reply_to': email,
                'body_html': team_body,
                'auto_delete': True,
            }).send()

        # 2) Branded confirmation back to the prospect.
        confirm_body = (
            u"<div style='margin:0;padding:0;background:#F5F6FA;'>"
            u"<table width='100%' cellpadding='0' cellspacing='0' style='background:#F5F6FA;'>"
            u"<tr><td align='center' style='padding:28px 12px;'>"
            u"<table width='560' cellpadding='0' cellspacing='0' style='width:560px;max-width:560px;"
            u"background:#fff;border:1px solid #E7E5F2;border-radius:18px;overflow:hidden;"
            u"font-family:Segoe UI,Roboto,Arial,sans-serif;'>"
            u"<tr><td style='background:#5A4BB0;padding:22px 32px;color:#fff;font-size:22px;font-weight:800;'>Payobook</td></tr>"
            u"<tr><td style='padding:34px 32px 26px;'>"
            u"<h1 style='margin:0 0 10px;font-size:23px;color:#1B1733;font-weight:800;'>Thanks, %s — we're on it.</h1>"
            u"<p style='margin:0 0 14px;font-size:15px;line-height:1.6;color:#4B5168;'>"
            u"We've received your request for a private Payobook demo. A specialist will reach out "
            u"shortly to tailor a walkthrough for <b>%s</b>.</p>"
            u"<p style='margin:0;font-size:14px;line-height:1.6;color:#4B5168;'>"
            u"In the meantime you can explore the live shared demo any time.</p>"
            u"</td></tr>"
            u"<tr><td style='padding:20px 32px 28px;border-top:1px solid #EEF0F8;font-size:12px;color:#8A87A0;'>"
            u"Payobook — payroll, unified across Asia, with an AI copilot.</td></tr>"
            u"</table></td></tr></table></div>"
            % (values['name'], values['company']))
        Mail.create({
            'subject': u"We've received your Payobook demo request",
            'email_from': company.email or (notify_to or 'noreply@payobook.com'),
            'email_to': email,
            'body_html': confirm_body,
            'auto_delete': True,
        }).send()

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
        # groups into membership at create-time). This is the full set the demo
        # experience needs — mirrors the reference demo@payobook.com user —
        # otherwise cockpits that read formula/company data (e.g. the Dashboard)
        # raise AccessError and render blank.
        group_xmlids = [
            'pb_demo.group_payobook_demo',            # demo role (read-only sandbox)
            'base.group_user',                        # internal user (backend access)
            'base.group_multi_company',               # company scope
            'pb_hr_payroll_formula.group_formula_user',  # read formula configs/tests (Dashboard, Formula Studio)
            'pb_payroll_ai_insights.group_payai_user',   # PayAI copilot
        ]
        gids = []
        for xmlid in group_xmlids:
            g = env.ref(xmlid, raise_if_not_found=False)
            if g:
                gids.append(g.id)
        if gids:
            user_vals['group_ids'] = [(6, 0, gids)]
        # Land on the Payroll dashboard right after login (not Discuss) so the
        # guided tour starts instantly on the command centre.
        dash = env.ref('pb_dashboard.action_pb_dashboard', raise_if_not_found=False)
        if dash:
            user_vals['action_id'] = dash.id
        user = Users.create(user_vals)
        # One of the six demo divisions, round-robin, so this prospect's live
        # capstone drives a June run nobody else is driving. Assigned here
        # rather than in the vals so that the same helper serves the lazy
        # back-fill of users created before the field existed.
        user.sudo()._pb_ensure_demo_division()
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
