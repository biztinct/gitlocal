# -*- coding: utf-8 -*-
"""SET A NEW PASSWORD — for somebody else, from their passport on the People lens.

The everyday case: an employee walks up to the company's administrator and
says "I forgot my password", and the company has no outgoing mail (or the
person has no email). The stock "Change Password" action sits behind
`base.group_erp_manager`, which a Tenant administrator deliberately does not
hold (access_common.FORBIDDEN_GROUP_XMLIDS), so without this door the only way
out was to ask the platform.

WHO MAY: whoever may manage access here (`_require_manage`, the access team —
the Tenant administrator role carries it).

WHO MAY NOT BE TOUCHED — decided once in `_password_refusal`, shown under the
button by the passport and raised by `set_user_password`, so the two never
disagree:
  * yourself — your own password is changed from your profile, which asks
    for the current one first;
  * the platform recovery login (hidden from everybody else anyway);
  * the public user;
  * anybody holding `base.group_system` or `base.group_erp_manager`, unless
    the caller holds `base.group_system` themselves. Otherwise this would be
    the two-click road from "access team" to "owns the database" that
    FORBIDDEN_GROUP_XMLIDS exists to close.

The write goes through `res.users._change_password`, the framework's own
setter: it refuses an empty value, logs who changed whose password from which
address, and storing a new password changes the session token, so every
session the person still has open elsewhere is signed out.

The password itself is never logged, stored anywhere but the hash, or sent
back to the browser.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from .access_common import recovery_login

_logger = logging.getLogger(__name__)

#: The floor, not a policy engine. Long enough that a guessed word fails, short
#: enough that a password read out over the counter can be typed.
MIN_LENGTH = 8

#: The groups whose holders only a system administrator may re-key.
KEY_GROUPS = ('base.group_system', 'base.group_erp_manager')


class PbAccessPassword(models.AbstractModel):
    _inherit = 'pb.access'

    @api.model
    def _password_refusal(self, user):
        """The plain-words reason this person's password cannot be set here, or ''."""
        user = user.sudo()
        name = user.name or ''
        if not self.can_manage():
            return _("Only the people who manage access can set a password "
                     "for someone else.")
        if user.id == self.env.uid:
            return _("This is your own login. Change your password from your "
                     "profile; it asks for your current one first.")
        if user._is_public():
            return _("That is not a person's login.")
        if (user.login or '').strip().lower() == recovery_login(self.env):
            return _("That person does not have a login here.")
        if not user.active:
            return _("%s's login is archived. Restore it before setting a "
                     "password.", name)
        if not self._is_admin() and any(user.has_group(g) for g in KEY_GROUPS):
            return _("%s is a system administrator. Only another system "
                     "administrator can set their password.", name)
        return ''

    @api.model
    def _password_preview(self, user):
        why = self._password_refusal(user)
        return {'allowed': not why, 'why': why}

    @api.model
    def passport(self, user_id=None):
        result = super().passport(user_id)
        header = result.get('header') or {}
        if header.get('id'):
            user = self.env['res.users'].sudo().browse(header['id'])
            header['password'] = self._password_preview(user)
        return result

    @api.model
    def set_user_password(self, user_id, password):
        """Give somebody a new password. Answers a plain sentence either way."""
        self._require_manage()
        user = self.env['res.users'].sudo().with_context(
            active_test=False).browse(int(user_id or 0)).exists()
        if not user:
            raise UserError(_("That person does not have a login here."))
        why = self._password_refusal(user)
        if why:
            raise UserError(why)
        password = (password or '').strip()
        if len(password) < MIN_LENGTH:
            raise UserError(_("Use at least %s characters.", MIN_LENGTH))
        if password.lower() in {(user.login or '').strip().lower(),
                                (user.name or '').strip().lower()}:
            raise UserError(_("Use something other than their name or "
                              "sign-in."))
        # `self.env.user` must stay the CALLER so the framework's own log line
        # names who did it; `user` is sudo only for the write itself.
        user.with_env(user.env(user=self.env.uid, su=True))._change_password(
            password)
        _logger.info('biz_access: user %s set a new password for user %s on '
                     'the People lens', self.env.uid, user.id)
        return {'ok': True, 'message': _(
            "%s has a new password. Tell them in person or by phone, and ask "
            "them to change it after they sign in. They have been signed out "
            "everywhere else.", user.name)}
