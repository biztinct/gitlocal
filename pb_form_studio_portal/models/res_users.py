# -*- coding: utf-8 -*-
"""FS-14 / FS-14b — an employee changes their own details only through the
screens that declare them changeable (My Profile's "Request a change", the
Form builder's My Payobook boxes), never by a hand-made call.

Two platform paths let a signed-in person write their OWN details directly:

1. `res.users.write` on oneself: the platform writes the "safe" fields of
   one's own user record as super-user (`base/models/res_users.py:605-615`),
   and the HR addon lists among them the fields that write straight through
   to the employee — private phone/e-mail, the whole home address,
   emergency contact, work e-mail, work phone, work mobile, … (`hr/models/
   res_users.py:27-50,125`).
2. The work contact: the employee's work e-mail and work phone ARE the e-mail
   and phone of their work contact, which for a person with a login is their
   own partner (`hr/models/hr_employee.py:122-124,824-842`). The standard
   portal address form (`/my/address/submit`) and an own-user write of
   `email` / `phone` change that partner.

Both are refused for an employee (no HR role, not an administrator) when a
value really changes; the plain message points to "Request a change". HR and
the system are never stopped, so nothing changes for what HR edits on the
employee record, nor for the approved requests (applied as the approver).
"""
from odoo import models
from odoo.exceptions import AccessError

_HR = 'hr.group_hr_user'
#: the work contact's fields that ARE the employee's work e-mail / work phone
CONTACT_FIELDS = ('email', 'phone')


def _refusal(env):
    return env._('Your details change only through "Request a change" on My Profile, where '
                 'HR approves them. Nothing was saved.')


def _is_employee_self(env):
    """The signed-in person is an employee without an HR role or the
    administrator's rights (the people these rails are for)."""
    user = env.user
    if not user or user._is_public() or user._is_superuser() or user._is_admin():
        return False
    if user.has_group(_HR):
        return False
    return bool(env['hr.employee'].sudo().with_context(active_test=False).search_count(
        [('user_id', '=', user.id)], limit=1))


def _differs(old, new):
    if hasattr(old, '_name'):
        old = old.ids[0] if len(old) == 1 else (old.ids or False)
    if isinstance(new, (list, tuple)):
        return True                 # an x2many command list: always a change
    return (old or False) != (new or False)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        if self.env.su or self != self.env.user or not vals:
            return super().write(vals)
        # every field of the user record that writes the employee record
        touched = [n for n in vals if n in self._fields and self._fields[n].related
                   and getattr(self._fields[n], 'related_field', None) is not None
                   and self._fields[n].related_field.model_name in ('hr.employee', 'hr.version')]
        if touched and _is_employee_self(self.env):
            me = self.sudo()
            if any(_differs(me[n], vals[n]) for n in touched):
                raise AccessError(_refusal(self.env))
        return super().write(vals)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        fields_ = [f for f in CONTACT_FIELDS if f in vals]
        if fields_ and self and _is_employee_self(self.env):
            # written as super-user by the portal's own forms: judge by WHO asks
            mine = self.env['hr.employee'].sudo().with_context(active_test=False).search(
                [('user_id', '=', self.env.uid), ('work_contact_id', 'in', self.ids)])
            contacts = mine.work_contact_id
            for partner in self.sudo():
                if partner in contacts and any(_differs(partner[f], vals[f]) for f in fields_):
                    raise AccessError(_refusal(self.env))
        return super().write(vals)
