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

# Who hears about every registered lead (demo signup + private-demo enquiry).
# Overridable without a deploy via the ``pb_demo_portal.lead_notify_to`` system
# parameter (comma-separated). Owner ruling 2026-10-06: ash + hello + lehoa.
DEFAULT_LEAD_NOTIFY_TO = 'ash@biztinct.com,hello@payobook.com,lehoa@payobook.com'

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
        lead = self._create_demo_lead(values, email, user.partner_id)
        # Tell the team (ash + hello + lehoa) — the CRM itself sends nothing on
        # a lead created by the public user, so this is the only notification.
        try:
            self._notify_team_about_lead(
                kind='signup', values=values, email=email, lead=lead,
                subject=u"New demo signup — %s (%s)" % (values['name'], values['company']),
                heading=u"New demo signup",
                extra_rows=[('Industry', values.get('industry')),
                            ('Company size', values.get('company_size'))])
        except Exception as e:  # pragma: no cover - notification is best-effort
            _logger.warning("Demo signup team notification not sent for %s: %s", email, e)
        return request.render('pb_demo_portal.register_done', {'email': email, 'already': False})

    def _create_demo_lead(self, values, email, partner=None):
        """Create a ``crm.lead`` for a self-service demo signup so it surfaces in
        the CRM pipeline for follow-up. No-op if the crm module isn't installed,
        and never raises into the signup flow (lead capture must not break the
        demo account). Returns the lead (or None)."""
        env = request.env
        if 'crm.lead' not in env:
            return None
        try:
            country_id = int(values['country_id']) if values.get('country_id') else False
            source = env['utm.source'].sudo().search(
                [('name', '=', 'Demo Signup')], limit=1)
            if not source:
                source = env['utm.source'].sudo().create({'name': 'Demo Signup'})
            # The request runs as the website Public user; without an explicit
            # salesperson the lead would be assigned to "Public user". Hand it to
            # the default sales team's leader instead (unassigned if none).
            team = env['crm.team'].sudo()._get_default_team_id()
            lead_vals = {
                'name': u"Demo signup — %s" % (values.get('company') or values.get('name')),
                'type': 'lead',
                'contact_name': values.get('name'),
                'partner_name': values.get('company'),
                'email_from': email,
                'phone': values.get('mobile'),
                'country_id': country_id,
                'source_id': source.id,
                'user_id': team.user_id.id if team and team.user_id else False,
                'team_id': team.id if team else False,
                'description': (
                    u"Self-service demo signup via payobook.com/demo/register\n"
                    u"Industry: %s\nCompany size: %s"
                    % (values.get('industry') or u'—', values.get('company_size') or u'—')),
            }
            if partner:
                lead_vals['partner_id'] = partner.id
            # No "You have been assigned" chatter email: this database has no
            # alias domain / default sender, so that mail would only fail
            # (mail_from_missing) — the team notification below covers it.
            return env['crm.lead'].sudo().with_context(
                mail_auto_subscribe_no_notify=True).create(lead_vals)
        except Exception as e:  # pragma: no cover - lead capture is best-effort
            _logger.warning("Demo signup lead not created for %s: %s", email, e)
            return None

    # ------------------------------------------------------------------ #
    #  Team notification — one email per registered lead, to everyone in  #
    #  ``pb_demo_portal.lead_notify_to`` (default: ash + hello + lehoa).   #
    # ------------------------------------------------------------------ #
    def _lead_notify_recipients(self):
        """Comma-separated recipient list → ordered, de-duplicated, valid emails.
        Falls back to the notify company's email when the parameter is blank."""
        raw = request.env['ir.config_parameter'].sudo().get_param(
            'pb_demo_portal.lead_notify_to', DEFAULT_LEAD_NOTIFY_TO) or ''
        seen, out = set(), []
        for part in re.split(r'[,;\s]+', raw):
            addr = part.strip().lower()
            if addr and EMAIL_RE.match(addr) and addr not in seen:
                seen.add(addr)
                out.append(addr)
        if not out:
            company = self._notify_company()
            fallback = company.email or company.partner_id.email_normalized
            if fallback:
                out.append(fallback)
        return out

    def _lead_notify_from(self):
        """Sender for team notifications: the system's configured default
        (``mail.default.from`` + catchall domain), else the notify company's
        email, else a no-reply on the product domain."""
        default_from = request.env['ir.mail_server'].sudo()._get_default_from_address()
        if default_from:
            return default_from
        company = self._notify_company()
        return company.email or company.partner_id.email_normalized or 'noreply@payobook.com'

    @staticmethod
    def _html_row(label, val):
        if not val:
            return ''
        return (u"<tr><td style='padding:6px 14px;color:#8A87A0;font-size:13px;'>%s</td>"
                u"<td style='padding:6px 14px;color:#1B1733;font-size:13px;font-weight:600;'>%s</td></tr>"
                % (label, val))

    def _notify_team_about_lead(self, kind, values, email, subject, heading,
                                lead=None, extra_rows=None, message=None):
        """Send ONE email about a registered lead to every team recipient.
        ``kind`` is 'signup' or 'private' (shown as the submission source)."""
        env = request.env
        recipients = self._lead_notify_recipients()
        if not recipients:
            _logger.warning(
                "Lead received but nobody to notify — set the "
                "pb_demo_portal.lead_notify_to system parameter. Lead: %s <%s>",
                values.get('name'), email)
            return False
        country = ''
        if values.get('country_id'):
            try:
                country = env['res.country'].sudo().browse(int(values['country_id'])).name or ''
            except Exception:  # pragma: no cover - cosmetic only
                country = ''
        rows = (self._html_row('Name', values.get('name'))
                + self._html_row('Company', values.get('company'))
                + self._html_row('Work email', email)
                + self._html_row('Phone', values.get('mobile'))
                + self._html_row('Country', country))
        for label, val in (extra_rows or []):
            rows += self._html_row(label, val)
        source_line = (u"Self-service demo signup via payobook.com/demo/register"
                       if kind == 'signup' else u"Private-demo request via payobook.com")
        msg_html = ''
        if message:
            msg_html = (u"<div style='margin-top:16px;padding:14px 16px;background:#F4F5FB;"
                        u"border-radius:12px;color:#4B5168;font-size:14px;line-height:1.6;'>%s</div>"
                        % message.replace('\n', '<br/>'))
        link_html = ''
        if lead:
            base_url = env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
            link_html = (u"<p style='margin:16px 0 0;font-size:13px;'>"
                         u"<a href='%s/bizapp/action-crm.crm_lead_all_leads/%s' "
                         u"style='color:#5A4BB0;font-weight:600;'>Open this lead in the pipeline</a></p>"
                         % (base_url, lead.id))
        body = (
            u"<div style='font-family:Segoe UI,Roboto,Arial,sans-serif;color:#1B1733;'>"
            u"<h2 style='margin:0 0 4px;font-size:20px;'>%s</h2>"
            u"<p style='margin:0 0 16px;color:#8A87A0;font-size:13px;'>%s</p>"
            u"<table style='border-collapse:collapse;'>%s</table>%s%s</div>"
            % (heading, source_line, rows, msg_html, link_html))
        env['mail.mail'].sudo().create({
            'subject': subject,
            'email_from': self._lead_notify_from(),
            'email_to': ', '.join(recipients),
            'reply_to': email,
            'body_html': body,
            'auto_delete': True,
        }).send()
        return True

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
        Mail = env['mail.mail'].sudo()

        # 1) Notify the Payobook team — every registered lead goes to the same
        #    recipient list (ash + hello + lehoa by default).
        self._notify_team_about_lead(
            kind='private', values=values, email=email,
            subject=u"Private demo request — %s (%s)" % (values['name'], values['company']),
            heading=u"New private-demo request",
            extra_rows=[('Company size', values.get('company_size'))],
            message=values.get('message'))

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
            'email_from': self._lead_notify_from(),
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
