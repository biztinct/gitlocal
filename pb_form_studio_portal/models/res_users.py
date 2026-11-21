# -*- coding: utf-8 -*-
"""FS-14 — a look-only personal box stays look-only on the user record too.

The platform lets every signed-in person write a few fields of their OWN
user record as super-user (`res.users.SELF_WRITEABLE_FIELDS`; the HR addon
adds private phone, private e-mail, address, emergency contact and phone,
which write straight through to the employee). That is a direct call around
My Profile's "Request a change". When the page builder's "Employee can
change it" switch of one of those five boxes is OFF, such a self-write of a
CHANGED value is refused. HR (and the system itself) are never stopped, and
nothing changes while the switch is on (the default — exactly as before).
"""
from odoo import models
from odoo.exceptions import AccessError

from .page_builder import PROFILE_REQUEST

_HR = 'hr.group_hr_user'


class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        touched = [n for n in PROFILE_REQUEST if n in vals and n in self._fields]
        if touched and not self.env.su and self == self.env.user \
                and not self.env.user.has_group(_HR) and not self.env.user._is_admin():
            Studio = self.env['pb.form.studio'].sudo()
            changeable = Studio._pbfp_profile_editable()
            me = self.sudo()
            for name in touched:
                if name in changeable:
                    continue
                if (vals[name] or '') != (me[name] or ''):
                    raise AccessError(self.env._(
                        'Some of these details can only be changed by HR. Nothing was sent.'))
        return super().write(vals)
