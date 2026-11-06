# -*- coding: utf-8 -*-
"""THE DESK — what an employee walks up and asks the company's administrator for.

Five actions on the passport, beside "Set a new password"
(`account_password.py`), all under the same refusal (`_password_refusal`:
the access team only; never yourself, the recovery login, an archived
login, or — unless you are one — a system administrator):

  * turn off two-step sign-in (a lost or replaced phone);
  * sign out everywhere (a lost laptop), without touching the password;
  * fix the sign-in (a typo, a changed email) and re-send the invitation;
  * when they last signed in, and from which devices;
  * their language and time zone.

Every write is one call that answers a plain sentence, re-checks the refusal
on the server, and logs who did what to whom. Nothing here reads or returns a
password or a second-factor secret.
"""
import logging

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mail import email_normalize

_logger = logging.getLogger(__name__)

#: Devices shown on the passport: enough to answer "where am I signed in?".
DEVICE_CAP = 5


class PbAccessDesk(models.AbstractModel):
    _inherit = 'pb.access'

    # ------------------------------------------------------------ helpers
    @api.model
    def _desk_user(self, user_id):
        """The person, re-checked. Raises the plain refusal."""
        self._require_manage()
        user = self.env['res.users'].sudo().with_context(
            active_test=False).browse(int(user_id or 0)).exists()
        if not user:
            raise UserError(_("That person does not have a login here."))
        why = self._password_refusal(user)
        if why:
            raise UserError(why)
        return user

    @api.model
    def _has_two_step(self):
        return 'totp_secret' in self.env['res.users']._fields

    @api.model
    def _devices(self, user):
        if 'res.device' not in self.env:
            return []
        rows = self.env['res.device'].sudo().search(
            [('user_id', '=', user.id), ('revoked', '=', False)],
            order='last_activity desc', limit=DEVICE_CAP)
        out = []
        for d in rows:
            where = ', '.join(x for x in (d.city, d.country) if x)
            out.append({
                'id': d.id,
                'kind': d.device_type or 'computer',
                'what': ' · '.join(x for x in (
                    (d.browser or '').title(), (d.platform or '').title()) if x),
                'where': where,
                'last': fields.Datetime.to_string(d.last_activity)
                if d.last_activity else '',
            })
        return out

    @api.model
    def _languages(self):
        return [{'code': code, 'name': name}
                for code, name in self.env['res.lang'].get_installed()]

    # ------------------------------------------------------------ passport
    @api.model
    def passport(self, user_id=None):
        result = super().passport(user_id)
        header = result.get('header') or {}
        if not header.get('id') or not self.can_manage() or header.get('is_me'):
            return result
        user = self.env['res.users'].sudo().browse(header['id'])
        header['desk'] = {
            'last_login': fields.Datetime.to_string(user.login_date)
            if user.login_date else '',
            'devices': self._devices(user),
            'two_step': bool(self._has_two_step() and user.totp_enabled),
            'email': user.email or '',
            'lang': user.lang or '',
            'tz': user.tz or '',
            'languages': self._languages(),
        }
        return result

    @api.model
    def time_zones(self):
        """The list for the time-zone picker, the company's own zone first."""
        self._require_manage()
        first = self.env.company.partner_id.tz or self.env.user.tz or ''
        zones = sorted(pytz.common_timezones)
        if first in zones:
            zones.remove(first)
            zones.insert(0, first)
        return zones

    # ------------------------------------------------------------ the writes
    @api.model
    def turn_off_two_step(self, user_id):
        user = self._desk_user(user_id)
        if not self._has_two_step() or not user.totp_enabled:
            return {'ok': True, 'message': _(
                "%s does not use two-step sign-in.", user.name)}
        # The framework's own action asks the CALLER to re-enter their
        # password (`check_identity`) and is gated to the settings group; the
        # access team has neither, so the two effects are applied here:
        # forget the trusted browsers, drop the secret.
        user._revoke_all_devices()
        user.write({'totp_secret': False})
        _logger.info('biz_access: user %s turned off two-step sign-in for '
                     'user %s', self.env.uid, user.id)
        return {'ok': True, 'message': _(
            "Two-step sign-in is off for %s. They sign in with their "
            "password and can set it up again from their profile.", user.name)}

    @api.model
    def sign_out_everywhere(self, user_id):
        user = self._desk_user(user_id)
        devices = self.env['res.device'].sudo().search(
            [('user_id', '=', user.id), ('revoked', '=', False)]) \
            if 'res.device' in self.env else self.env['res.users']
        n = len(devices)
        if devices:
            devices._revoke()
        if self._has_two_step():
            user._revoke_all_devices()
        _logger.info('biz_access: user %s signed user %s out everywhere '
                     '(%s devices)', self.env.uid, user.id, n)
        if n == 1:
            message = _("%s is signed out on 1 device. Their password is "
                        "unchanged.", user.name)
        elif n:
            message = _("%(name)s is signed out on %(n)s devices. Their "
                        "password is unchanged.", name=user.name, n=n)
        else:
            message = _("%s was not signed in anywhere.", user.name)
        return {'ok': True, 'message': message}

    @api.model
    def change_sign_in(self, user_id, login, also_email=True):
        """A new sign-in name: an email address, or an employee code."""
        user = self._desk_user(user_id)
        login = (login or '').strip()
        if not login:
            raise UserError(_("Enter the new sign-in."))
        if len(login) > 80 or any(c.isspace() for c in login):
            raise UserError(_("A sign-in has no spaces and at most 80 "
                              "characters."))
        email = email_normalize(login, strict=True) if '@' in login else False
        if '@' in login and not email:
            raise UserError(_("That is not a valid email address."))
        login = email or login
        if login.lower() == (user.login or '').lower():
            return {'ok': True, 'message': _(
                "%s already signs in with that.", user.name)}
        taken = self.env['res.users'].sudo().with_context(
            active_test=False).search_count(
            [('login', '=ilike', login), ('id', '!=', user.id)])
        if taken:
            raise UserError(_("Someone else already signs in with %s.", login))
        vals = {'login': login}
        if email and also_email:
            vals['email'] = email
        before = user.login
        user.write(vals)
        _logger.info('biz_access: user %s changed the sign-in of user %s '
                     'from %r to %r', self.env.uid, user.id, before, login)
        return {'ok': True, 'message': _(
            "%(name)s now signs in with %(login)s. They have been signed out "
            "everywhere and sign in again with their usual password.",
            name=user.name, login=login)}

    @api.model
    def send_invitation(self, user_id):
        """The set-a-password email (invitation or reset, the same mail)."""
        user = self._desk_user(user_id)
        if not user.email:
            raise UserError(_("%s has no email address. Set a new password "
                              "for them instead.", user.name))
        try:
            with self.env.cr.savepoint():
                user.action_reset_password()
        except Exception:
            _logger.exception('biz_access: the set-a-password email for user '
                              '%s failed', user.id)
            return {'ok': False, 'message': _(
                "The email to %s could not be sent. This company's outgoing "
                "email may not be set up. Set a new password for them "
                "instead.", user.email)}
        _logger.info('biz_access: user %s sent a set-a-password email to '
                     'user %s', self.env.uid, user.id)
        return {'ok': True, 'message': _(
            "An email to set a password is on its way to %s.", user.email)}

    @api.model
    def set_preferences(self, user_id, lang=None, tz=None):
        user = self._desk_user(user_id)
        vals = {}
        if lang:
            codes = {code for code, _name in self.env['res.lang'].get_installed()}
            if lang not in codes:
                raise UserError(_("That language is not available here."))
            vals['lang'] = lang
        if tz:
            if tz not in pytz.all_timezones_set:
                raise UserError(_("That time zone is not known."))
            vals['tz'] = tz
        if not vals:
            return {'ok': True, 'message': _("Nothing changed.")}
        user.write(vals)
        _logger.info('biz_access: user %s set %s for user %s', self.env.uid,
                     sorted(vals), user.id)
        return {'ok': True, 'message': _(
            "Saved. %s sees it the next time a page opens.", user.name)}
