# -*- coding: utf-8 -*-
"""TWO-STEP SIGN-IN, REQUIRED BY ROLE (WDGAP QF5 A). The whole kernel.

One switch, `biz_access.two_step_required`:

  * ``''`` (the default)   nobody is asked; nothing here runs past one read
  * ``'all'``              every active staff (internal) login
  * ``'12,40'``            whoever holds one of these roles right now, through
                           an active role assignment of any source (a lent
                           role counts while it is lent)

A covered person with no authenticator app is sent to `/web/two-step`
(controllers/two_step.py) by the page door in ir_http.py. The door only ever
ADDS a redirect: nothing here marks anybody as having two-step, nothing here
writes the second-factor secret (the setup page does, through the platform's
own `_totp_try_setting` on the signed-in person themself).

Never asked (`is_exempt`): the public user, the platform's recovery login and
any support session, logins listed in `biz_access.two_step_exempt_logins`
(platform-only, no screen), and members of the demo group when that group
exists on this database. Employee self-service (portal) logins are not covered
in this phase.

Kill switch: blank `biz_access.two_step_required` (psql) — the next request
reads the empty value and the door stops, no restart.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from .access_common import param, recovery_login, visible_people

_logger = logging.getLogger(__name__)

TWO_STEP_PARAM = 'biz_access.two_step_required'
EXEMPT_LOGINS_PARAM = 'biz_access.two_step_exempt_logins'
DEMO_GROUP_XMLID = 'pb_demo.group_payobook_demo'
#: People named on the card as "not set up yet"; past it, the card says the number.
MISSING_CAP = 30
MODES = ('nobody', 'roles', 'all')


# ----------------------------------------------------------------- reading
def available(env):
    """The platform's authenticator-app support is installed here."""
    return 'totp_secret' in env['res.users']._fields


def read_rule(env):
    """'' (nobody), 'all', or a frozenset of role ids (empty = nobody)."""
    raw = str(param(env, TWO_STEP_PARAM, '') or '').strip().lower()
    if not raw:
        return ''
    if raw == 'all':
        return 'all'
    ids = frozenset(int(p) for p in raw.split(',') if p.strip().isdigit())
    return ids or ''


def exempt_logins(env):
    raw = str(param(env, EXEMPT_LOGINS_PARAM, '') or '')
    return {p.strip().lower() for p in raw.split(',') if p.strip()}


def is_exempt(user, session=None, include_demo=True):
    """Never asked. Shared with the idle rule, which passes include_demo=False."""
    env = user.env
    if not user or user._is_public():
        return True
    if session is not None and session.get('pb_support_id'):
        return True
    login = (user.login or '').strip().lower()
    if login == recovery_login(env) or login in exempt_logins(env):
        return True
    if include_demo:
        demo = env.ref(DEMO_GROUP_XMLID, raise_if_not_found=False)
        if demo and demo in user.sudo().all_group_ids:
            return True
    return False


def _holding(env, role_ids, user_ids=None):
    """Users holding one of these roles now (active assignment, live loan)."""
    domain = [('profile_id', 'in', list(role_ids)), ('active', '=', True)]
    if user_ids is not None:
        domain.append(('user_id', 'in', list(user_ids)))
    rows = env['pb.role.assignment'].sudo().search(domain)
    rows = rows.filtered(lambda a: a.profile_id.active and (
        not a.delegation_id or a.delegation_id.state == 'active'))
    return rows.user_id


def required_for(user, rule=None):
    """Does the rule cover this login (exemptions aside)?"""
    env = user.env
    rule = read_rule(env) if rule is None else rule
    if not rule or not available(env):
        return False
    user = user.sudo()
    if not user.active or not user._is_internal():
        return False
    if rule == 'all':
        return True
    return bool(_holding(env, rule, [user.id]))


def needs_setup(user, session=None):
    """The page door's one question. Cheapest test first."""
    rule = read_rule(user.env)
    if not rule:
        return False
    if not required_for(user, rule) or is_exempt(user, session):
        return False
    return not user.sudo().totp_enabled


def covered_users(env, rule):
    """Everybody the rule asks (exemptions removed), as one recordset."""
    Users = env['res.users'].sudo()
    if not rule or not available(env):
        return Users.browse()
    if rule == 'all':
        users = Users.search([('share', '=', False)])
    else:
        users = _holding(env, rule)
    users = users.filtered(lambda u: u.active and u._is_internal())
    return users.filtered(lambda u: not is_exempt(u))


def encode_rule(mode, role_ids):
    """The stored text of a choice."""
    if mode == 'all':
        return 'all'
    if mode == 'roles':
        return ','.join(str(i) for i in sorted(set(role_ids)))
    return ''


def rule_of(mode, role_ids):
    """The in-memory rule of a choice, as `read_rule` would return it."""
    if mode == 'all':
        return 'all'
    if mode == 'roles':
        return frozenset(role_ids) or ''
    return ''


class PbAccessTwoStep(models.AbstractModel):
    _inherit = 'pb.access'

    # ------------------------------------------------------------ the card
    @api.model
    def _two_step_roles(self):
        return self.env['pb.role.profile'].sudo().search(
            [('active', '=', True)], order='name')

    @api.model
    def _two_step_summary(self, rule):
        users = covered_users(self.env, rule)
        ready = users.filtered('totp_enabled')
        missing = visible_people(users - ready, self.env).sorted('name')
        return {
            'covered': len(users),
            'ready': len(ready),
            'missing': [{'id': u.id, 'name': u.name, 'login': u.login}
                        for u in missing[:MISSING_CAP]],
            'missing_count': len(missing),
        }

    @api.model
    def two_step_setting(self):
        self._require_manage()
        rule = read_rule(self.env)
        if rule == 'all':
            mode, ids = 'all', []
        elif rule:
            mode, ids = 'roles', sorted(rule)
        else:
            mode, ids = 'nobody', []
        roles = self._two_step_roles()
        out = {
            'available': available(self.env),
            'mode': mode,
            'role_ids': [i for i in ids if i in roles.ids],
            'roles': [{'id': r.id, 'name': r.name} for r in roles],
        }
        out.update(self._two_step_summary(rule))
        return out

    @api.model
    def _two_step_clean(self, mode, role_ids, strict=True):
        """The choice, with role ids that no longer exist dropped."""
        if mode not in MODES:
            raise UserError(_("Choose who two-step sign-in is required for."))
        ids = []
        if mode == 'roles':
            wanted = {int(i) for i in (role_ids or []) if str(i).isdigit()}
            ids = self.env['pb.role.profile'].sudo().browse(
                sorted(wanted)).exists().filtered('active').ids
            if strict and not ids:
                raise UserError(_("Tick at least one role, or choose Nobody."))
        return mode, ids

    @api.model
    def _two_step_to_sign_out(self, before, after):
        """People the new rule newly asks who have no app yet — never me."""
        return (after - before).filtered(
            lambda u: not u.totp_enabled and u.id != self.env.uid)

    @api.model
    def two_step_preview(self, mode, role_ids=None):
        """What saving this choice would do, for the dialog. Writes nothing."""
        self._require_manage()
        mode, ids = self._two_step_clean(mode, role_ids, strict=False)
        new_rule = rule_of(mode, ids)
        out = self._two_step_summary(new_rule)
        out['signed_out'] = len(self._two_step_to_sign_out(
            covered_users(self.env, read_rule(self.env)),
            covered_users(self.env, new_rule)))
        return out

    @api.model
    def set_two_step_setting(self, mode, role_ids=None):
        self._require_manage()
        mode, ids = self._two_step_clean(mode, role_ids)
        if mode != 'nobody' and not available(self.env):
            raise UserError(_("Two-step sign-in is not available on this system."))
        before = covered_users(self.env, read_rule(self.env))
        self.env['ir.config_parameter'].sudo().set_param(
            TWO_STEP_PARAM, encode_rule(mode, ids))
        after = covered_users(self.env, read_rule(self.env))
        out_users = self._two_step_to_sign_out(before, after)
        for user in out_users:
            self._two_step_sign_out(user)
        _logger.info('biz_access: user %s set two-step sign-in required to %r '
                     '(%s covered, %s signed out)', self.env.uid,
                     encode_rule(mode, ids), len(after), len(out_users))
        if mode == 'nobody':
            message = _("Two-step sign-in is no longer required. People who "
                        "set it up keep using it.")
        elif len(out_users) == 1:
            message = _("Saved. 1 person was signed out. They set it up the "
                        "next time they sign in.")
        elif out_users:
            message = _("Saved. %s people were signed out. They set it up the "
                        "next time they sign in.", len(out_users))
        else:
            message = _("Saved. Everyone this covers is asked to set it up "
                        "on their next page.")
        self._two_step_audit(_("Two-step sign-in rule changed"), message, {
            'mode': mode, 'role_ids': ids, 'covered': len(after),
            'signed_out': out_users.ids})
        result = self.two_step_setting()
        result['message'] = message
        return result

    # ------------------------------------------------------------ helpers
    @api.model
    def _two_step_sign_out(self, user):
        """The desk's 'sign out everywhere', without its per-person refusal:
        the acting administrator is excluded by the caller."""
        if 'res.device' in self.env:
            self.env['res.device'].sudo().search(
                [('user_id', '=', user.id), ('revoked', '=', False)])._revoke()
        if hasattr(user, '_revoke_all_devices'):
            user.sudo()._revoke_all_devices()

    @api.model
    def _two_step_audit(self, name, reason, details=None, user=None):
        """A row on the Access History tab; a log line if that cannot be written."""
        try:
            with self.env.cr.savepoint():
                self._studio_event('system', name, reason, details, user)
        except Exception:                                    # noqa: BLE001
            _logger.warning('biz_access: the History row for %r could not be '
                            'written', name, exc_info=True)

    @api.model
    def _two_step_required_for(self, user):
        return required_for(user)
