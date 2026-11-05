# -*- coding: utf-8 -*-
"""WORKERS WITHOUT EMAIL, FIRST PASSWORDS, AND LEAVERS.

Three things a factory's administrator needs that a login screen built around
email addresses does not give them:

1. **Logins in bulk for people with no email.** `create_worker_logins` makes
   an Employee login (portal — self-service pages only, TIERS T2) for each
   chosen employee who has none, signing in with their EMPLOYEE CODE (the
   badge id, else the time-clock number, else the identification number) and a
   first password made here. The passwords come back ONCE, for the slips the
   board prints; they are never stored anywhere but the hash, never logged.
2. **Choose your own password at first sign-in.** `pb_must_change_password`
   is set on those logins and, optionally, by "Set a new password". While it
   is set, every page sends the person to `/biz_access/first-password`
   (controllers/first_password.py); the flag clears the moment THEY change
   their own password, by that page or any other.
3. **Leavers.** A daily job closes (archives) the login of anybody whose
   employee record has a departure date in the past, and opens it again when
   that date is cleared or moved to the future — but only logins this job
   closed (`pb_closed_as_leaver`). It never closes a system administrator,
   the recovery login, or the last person who manages access. Switch:
   `biz_access.close_leavers` ('1' by default).
"""
import logging
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .access_common import param, recovery_login

_logger = logging.getLogger(__name__)

#: Rows the picker lists at once; the search box is the answer past it.
WORKER_CAP = 500
#: People one press may create logins for.
BATCH_CAP = 300
LEAVERS_PARAM = 'biz_access.close_leavers'

_LETTERS = 'abcdefghjkmnpqrstuvwxyz'   # no i, l, o: read aloud, typed by hand
_DIGITS = '23456789'                   # no 0, 1


def first_password():
    """Readable over a counter and on paper: Abcd-2345-efgh."""
    pick = lambda alphabet, n: ''.join(secrets.choice(alphabet) for _ in range(n))
    word = pick(_LETTERS, 4)
    return '%s%s-%s-%s' % (word[0].upper(), word[1:], pick(_DIGITS, 4),
                           pick(_LETTERS, 4))


class ResUsers(models.Model):
    _inherit = 'res.users'

    pb_must_change_password = fields.Boolean(
        string='Must choose a new password', copy=False, default=False,
        help="Set when someone else gave this person their password. Cleared "
             "when they choose their own.")
    pb_closed_as_leaver = fields.Date(
        string='Login closed on leaving', copy=False, readonly=True,
        help="The day the daily job closed this login because the person "
             "left. Only logins closed this way are opened again by it.")

    def _change_password(self, new_passwd):
        res = super()._change_password(new_passwd)
        mine = self.filtered(lambda u: u.id == self.env.uid)
        if mine:
            mine.sudo().write({'pb_must_change_password': False})
        return res


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _pb_sign_in_code(self):
        """The code this person signs in with: badge, clock number, ID."""
        self.ensure_one()
        emp = self.sudo()
        for name in ('barcode', 'pb_clock_code', 'identification_id'):
            if name in emp._fields and emp[name]:
                return str(emp[name]).strip()
        return ''


class PbAccessWorkers(models.AbstractModel):
    _inherit = 'pb.access'

    # ------------------------------------------------- set a new password +
    @api.model
    def set_user_password(self, user_id, password, must_change=True):
        res = super().set_user_password(user_id, password)
        if must_change:
            user = self.env['res.users'].sudo().browse(int(user_id))
            user.write({'pb_must_change_password': True})
            res['message'] = _(
                "%s has a new password. Tell them in person or by phone. "
                "They choose their own when they next sign in, and have been "
                "signed out everywhere else.", user.name)
        return res

    # ------------------------------------------------- logins for workers
    @api.model
    def worker_candidates(self, search=None):
        """Employees with no login yet, and the code each would sign in with."""
        self._require_manage()
        co_ids = self.env.companies.ids or [self.env.company.id]
        dom = [('user_id', '=', False), ('company_id', 'in', co_ids)]
        needle = (search or '').strip()
        if needle:
            dom += ['|', '|', ('name', 'ilike', needle),
                    ('barcode', 'ilike', needle),
                    ('department_id.name', 'ilike', needle)]
        emps = self.env['hr.employee'].sudo().search(dom, order='name, id')
        total = len(emps)
        taken = {l.lower() for l in self.env['res.users'].sudo().with_context(
            active_test=False).search([]).mapped('login') if l}
        rows, no_code = [], 0
        for e in emps[:WORKER_CAP]:
            code = e._pb_sign_in_code()
            if not code:
                no_code += 1
            rows.append({
                'id': e.id,
                'name': e.name or '',
                'department': e.department_id.name or '',
                'code': code,
                'why': (_("No employee code.") if not code else
                        _("Someone already signs in with %s.", code)
                        if code.lower() in taken else ''),
            })
        return {'rows': rows, 'total': total, 'shown': len(rows),
                'no_code': no_code, 'cap': WORKER_CAP}

    @api.model
    def create_worker_logins(self, employee_ids):
        """Employee logins for these people. Passwords come back once."""
        self._require_manage()
        ids = [int(i) for i in (employee_ids or [])][:BATCH_CAP]
        if not ids:
            raise UserError(_("Choose at least one person."))
        co_ids = self.env.companies.ids or [self.env.company.id]
        emps = self.env['hr.employee'].sudo().browse(ids).exists().filtered(
            lambda e: e.company_id.id in co_ids)
        Users = self.env['res.users'].sudo().with_context(
            no_reset_password=True, active_test=False)
        portal = self.env.ref('base.group_portal')
        lang = self.env.company.partner_id.lang or self.env.user.lang
        created, skipped = [], []
        for e in emps:
            code = e._pb_sign_in_code()
            if e.user_id:
                skipped.append({'name': e.name, 'why': _("Already has a login.")})
                continue
            if not code:
                skipped.append({'name': e.name, 'why': _("No employee code.")})
                continue
            if Users.search_count([('login', '=ilike', code)]):
                skipped.append({'name': e.name, 'why': _(
                    "Someone already signs in with %s.", code)})
                continue
            password = first_password()
            try:
                with self.env.cr.savepoint():
                    user = Users.create({
                        'name': e.name,
                        'login': code,
                        'email': e.work_email or False,
                        'password': password,
                        'company_id': e.company_id.id,
                        'company_ids': [(6, 0, e.company_id.ids)],
                        'group_ids': [(6, 0, portal.ids)],
                        'lang': lang,
                        'tz': e.tz or self.env.company.partner_id.tz or False,
                        'pb_must_change_password': True,
                    })
                    e.write({'user_id': user.id})
            except Exception as exc:                          # noqa: BLE001
                _logger.warning('biz_access: worker login for employee %s '
                                'failed: %s', e.id, exc)
                skipped.append({'name': e.name, 'why': _(
                    "Could not be created. Try this person on their own.")})
                continue
            created.append({'employee_id': e.id, 'name': e.name,
                            'department': e.department_id.name or '',
                            'login': code, 'password': password})
        _logger.info('biz_access: user %s created %s employee logins (%s '
                     'skipped)', self.env.uid, len(created), len(skipped))
        if created and skipped:
            message = _("%(n)s logins made, %(m)s skipped. Print the slips "
                        "now: the passwords are not shown again.",
                        n=len(created), m=len(skipped))
        elif created:
            message = _("%s logins made. Print the slips now: the passwords "
                        "are not shown again.", len(created))
        else:
            message = _("No logins were made.")
        return {'created': created, 'skipped': skipped, 'message': message,
                'url': self.env['ir.config_parameter'].sudo().get_param(
                    'web.base.url') or ''}

    # ------------------------------------------------- leavers
    @api.model
    def leavers_setting(self):
        self._require_manage()
        return {'on': param(self.env, LEAVERS_PARAM, '1') == '1'}

    @api.model
    def set_leavers_setting(self, on):
        self._require_manage()
        self.env['ir.config_parameter'].sudo().set_param(
            LEAVERS_PARAM, '1' if on else '0')
        return {'on': bool(on), 'message': (
            _("Leavers' logins now close on the day after their last day.")
            if on else _("Leavers' logins stay open until someone closes "
                         "them."))}

    @api.model
    def _last_access_manager(self, user):
        group = self.env.ref('biz_access.group_access_manager',
                             raise_if_not_found=False)
        if not group or user not in group.sudo().all_user_ids:
            return False
        others = group.sudo().all_user_ids.filtered(
            lambda u: u.active and u.id != user.id and not u.share)
        return not others

    @api.model
    def cron_close_leavers(self):
        """Close the logins of people who have left; reopen ours if they return."""
        if param(self.env, LEAVERS_PARAM, '1') != '1':
            return
        today = fields.Date.context_today(self)
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        recovery = recovery_login(self.env)
        closed = opened = 0
        for e in Emp.search([('user_id', '!=', False),
                             ('departure_date', '!=', False),
                             ('departure_date', '<', today)]):
            user = e.user_id.sudo()
            if not user.active:
                continue
            if ((user.login or '').strip().lower() == recovery
                    or user.has_group('base.group_system')
                    or user.has_group('base.group_erp_manager')
                    or self._last_access_manager(user)):
                _logger.info('biz_access: leaver login %s kept open (protected)',
                             user.id)
                continue
            try:
                with self.env.cr.savepoint():
                    if 'res.device' in self.env:
                        self.env['res.device'].sudo().search(
                            [('user_id', '=', user.id),
                             ('revoked', '=', False)])._revoke()
                    user.write({'active': False, 'pb_closed_as_leaver': today})
                closed += 1
            except Exception as exc:                          # noqa: BLE001
                _logger.warning('biz_access: closing leaver login %s failed: '
                                '%s', user.id, exc)
        back = self.env['res.users'].sudo().with_context(active_test=False).search(
            [('active', '=', False), ('pb_closed_as_leaver', '!=', False)])
        for user in back:
            emp = Emp.search([('user_id', '=', user.id)], limit=1)
            if emp and emp.active and (not emp.departure_date
                                       or emp.departure_date >= today):
                try:
                    with self.env.cr.savepoint():
                        user.write({'active': True, 'pb_closed_as_leaver': False})
                    opened += 1
                except Exception as exc:                      # noqa: BLE001
                    _logger.warning('biz_access: reopening login %s failed: '
                                    '%s', user.id, exc)
        if closed or opened:
            _logger.info('biz_access: leavers job closed %s and reopened %s '
                         'logins', closed, opened)
