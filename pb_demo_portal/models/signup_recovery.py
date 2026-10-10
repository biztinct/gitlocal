# -*- coding: utf-8 -*-
"""Repair for the 2026-10-08 duplicate demo sign-ups, and the two follow-up mails.

WHAT WENT WRONG
---------------
At an event on 2026-10-08, 169 people made 334 demo accounts: the sign-up page
was slow on venue wifi, people pressed Register again, and every press made an
account (the controller now locks per email). Sign-in looks a login up with
``limit=1`` and checks the password on THAT account only, so a person who set
a password on copy B while sign-in picked copy A was refused with the right
password: 7 of the 8 people with a duplicate and a password never got in.

WHAT THIS MODEL DOES (system administrators only, every method re-checks)
-------------------------------------------------------------------------
* ``dedupe_signups(apply=False)`` keeps ONE account per email — the one with a
  password, else the one that has signed in, else the first made — and
  archives the other copies, their contacts and the duplicate sales leads.
  Archived, never deleted; the ids go into ``PARAM_ROLLBACK`` so it can be
  undone. Leads are only touched when nobody has worked them (no activity,
  no note, no stage move) — the plan reports any it skipped.
* ``send_recovery_mail(kind, user_ids)`` sends one of two branded mails:
  ``fresh_link`` (we found the problem, here is a new password link, valid
  ``FRESH_LINK_DAYS`` days), ``expired_link`` (never set a password and the
  first link expired: here is a new one) or ``login_reminder`` (your password is set,
  come back and sign in). Each person gets each kind at most once
  (``PARAM_SENT``), so a repeated call cannot spam them.
* ``preview_mail(kind)`` renders a mail with sample values for review.
"""
import json
import logging
from collections import defaultdict

import werkzeug.urls

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

PARAM_ROLLBACK = 'pb_demo_portal.dedupe_rollback'
PARAM_SENT = 'pb_demo_portal.recovery_mail_sent'
FRESH_LINK_DAYS = 7
KINDS = {
    'fresh_link': {
        'template': 'pb_demo_portal.mail_signup_fresh_link',
        'subject': u"We fixed your Payobook sign-in · Chúng tôi đã khắc phục sự cố đăng nhập",
    },
    'expired_link': {
        'template': 'pb_demo_portal.mail_signup_expired_link',
        'subject': u"Set your password for the Payobook demo · Đặt mật khẩu cho bản demo Payobook",
    },
    'login_reminder': {
        'template': 'pb_demo_portal.mail_signup_login_reminder',
        'subject': u"Your Payobook demo is ready · Bản demo Payobook của bạn đã sẵn sàng",
    },
}


class PbDemoSignupRecovery(models.AbstractModel):
    _name = 'pb.demo.signup.recovery'
    _description = 'Demo sign-up duplicate repair and follow-up mails'

    def _check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError("Only a system administrator can do this.")

    # ------------------------------------------------------------------ #
    #  Duplicate accounts                                                 #
    # ------------------------------------------------------------------ #
    @api.model
    def dedupe_signups(self, apply=False):
        """Plan (and with ``apply=True`` carry out) the duplicate tidy-up.
        Returns a JSON-safe summary; the full id lists only when applied."""
        self._check_admin()
        cr = self.env.cr
        demo_group = self.env.ref('pb_demo.group_payobook_demo')
        # Password and sign-in history are not readable through the ORM.
        cr.execute("""
            SELECT u.id, lower(u.login),
                   (u.password IS NOT NULL AND u.password <> '') AS has_pw,
                   EXISTS (SELECT 1 FROM res_users_log g WHERE g.create_uid = u.id) AS signed_in,
                   u.write_date
              FROM res_users u
              JOIN res_groups_users_rel r ON r.uid = u.id AND r.gid = %s
             WHERE u.active
               AND lower(u.login) IN (SELECT lower(login) FROM res_users
                                       WHERE active GROUP BY lower(login) HAVING count(*) > 1)
        """, [demo_group.id])
        by_email = defaultdict(list)
        for uid, email, has_pw, signed_in, write_date in cr.fetchall():
            by_email[email].append((uid, has_pw, signed_in, write_date))

        keep, drop = {}, []
        for email, rows in by_email.items():
            rows.sort(key=lambda r: (not r[1], not r[2],          # password, then signed in
                                     -(r[3].timestamp() if r[1] else 0),  # newest password
                                     r[0]))                       # else the first made
            keep[email] = rows[0][0]
            drop += [r[0] for r in rows[1:]]

        Users = self.env['res.users'].sudo()
        kept_users = Users.browse(list(keep.values()))
        drop_users = Users.browse(drop)
        Lead = self.env['crm.lead'].sudo()
        lead_keep, lead_drop, lead_skipped = [], [], []
        if by_email:
            leads = Lead.search([('email_from', '=ilike', '%@%')]).filtered(
                lambda l: (l.email_from or '').strip().lower() in keep)
            per_email = defaultdict(list)
            for lead in leads:
                per_email[lead.email_from.strip().lower()].append(lead)
            for email, group in per_email.items():
                kept_partner = Users.browse(keep[email]).partner_id
                group.sort(key=lambda l: (l.partner_id != kept_partner, l.id))
                lead_keep.append(group[0].id)
                for lead in group[1:]:
                    touched = (lead.activity_ids
                               or lead.message_ids.filtered(lambda m: m.message_type in ('comment', 'email'))
                               or lead.stage_id != group[0].stage_id
                               or lead.type != 'lead')
                    (lead_skipped if touched else lead_drop).append(lead.id)

        summary = {
            'people': len(by_email),
            'accounts_kept': len(keep),
            'accounts_archived': len(drop),
            'leads_kept': len(lead_keep),
            'leads_archived': len(lead_drop),
            'leads_skipped_worked_on': lead_skipped,
            'applied': False,
        }
        if not apply or not drop:
            return summary

        partners = drop_users.partner_id - kept_users.partner_id
        drop_users.write({'active': False})
        partners.write({'active': False})
        Lead.browse(lead_drop).write({'active': False})
        # The kept lead should point at the contact that can still sign in.
        for lead_id in lead_keep:
            lead = Lead.browse(lead_id)
            email = lead.email_from.strip().lower()
            partner = Users.browse(keep[email]).partner_id
            if lead.partner_id != partner:
                lead.partner_id = partner
        ICP = self.env['ir.config_parameter'].sudo()
        history = json.loads(ICP.get_param(PARAM_ROLLBACK) or '[]')
        history.append({
            'at': fields.Datetime.to_string(fields.Datetime.now()),
            'by': self.env.user.login,
            'users': drop, 'partners': partners.ids, 'leads': lead_drop,
        })
        ICP.set_param(PARAM_ROLLBACK, json.dumps(history))
        _logger.warning("Demo sign-up dedupe by %s: archived %s users, %s partners, %s leads",
                        self.env.user.login, len(drop), len(partners), len(lead_drop))
        summary.update(applied=True, kept_user_ids=sorted(keep.values()))
        return summary

    # ------------------------------------------------------------------ #
    #  Follow-up mails                                                    #
    # ------------------------------------------------------------------ #
    def _fresh_link(self, user):
        partner = user.partner_id.sudo()
        partner.signup_prepare(signup_type='reset')
        token = partner._generate_signup_token(expiration=FRESH_LINK_DAYS * 24)
        return '%s/web/reset_password?%s' % (
            user.get_base_url(), werkzeug.urls.url_encode({'db': self.env.cr.dbname, 'token': token}))

    def _login_link(self, user):
        return '%s/web/login?%s' % (
            user.get_base_url(), werkzeug.urls.url_encode({'login': user.login}))

    def _render(self, kind, values):
        return self.env['ir.qweb']._render(KINDS[kind]['template'], values)

    @api.model
    def preview_mail(self, kind):
        """The mail as a recipient would see it, with sample values."""
        self._check_admin()
        if kind not in KINDS:
            raise UserError("Unknown mail.")
        return {'subject': KINDS[kind]['subject'], 'body': self._render(kind, {
            'name': 'Lan Nguyen', 'email': 'lan.nguyen@yourcompany.vn',
            'url': 'https://payobook.com/web/login', 'days': FRESH_LINK_DAYS,
        })}

    @api.model
    def send_recovery_mail(self, kind, user_ids):
        """Send ``kind`` to each user once. Returns who got it and who was skipped."""
        self._check_admin()
        if kind not in KINDS:
            raise UserError("Unknown mail.")
        ICP = self.env['ir.config_parameter'].sudo()
        sent = json.loads(ICP.get_param(PARAM_SENT) or '{}')
        sender = self.env['pb.demo.signup.report']._notify_from()
        done, skipped = [], []
        for user in self.env['res.users'].sudo().browse(user_ids).exists():
            key = '%s:%s' % (kind, user.id)
            if key in sent or not user.active or not user.email:
                skipped.append(user.id)
                continue
            url = self._login_link(user) if kind == 'login_reminder' else self._fresh_link(user)
            body = self._render(kind, {
                'name': user.name, 'email': user.login, 'url': url, 'days': FRESH_LINK_DAYS,
            })
            self.env['mail.mail'].sudo().create({
                'subject': KINDS[kind]['subject'],
                'email_from': sender,
                'email_to': user.email,
                'reply_to': 'hello@payobook.com',
                'body_html': body,
                'auto_delete': True,
            })
            sent[key] = fields.Datetime.to_string(fields.Datetime.now())
            done.append(user.id)
        ICP.set_param(PARAM_SENT, json.dumps(sent))
        _logger.info("Demo recovery mail %s queued by %s for users %s (skipped %s)",
                     kind, self.env.user.login, done, skipped)
        return {'queued': done, 'skipped': skipped}
