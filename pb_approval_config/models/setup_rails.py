# -*- coding: utf-8 -*-
"""UPDATES P6 — the rails that let a client's own admin set approvals up.

WHY THIS FILE EXISTS. Owner decision D22 (2026-11-12): the Tenant
administrator role opens the Approval Matrix for its own company and chooses
who approves what. The role gets that through the Access catalogue (the
"Approval routes — publish" ability, `pb_vendor_access` 19.0.1.17.0), which
is the permission group `biz_approval_workflow.group_approval_publish`. That
group was written for the platform's own people. Handing it to a client's
admin is safe only with three rails it never needed before:

  1. THE ENGINE'S CATALOGUE IS NOT SET-UP. The "Set up approvals" tier's
     access rights include writing the process catalogue
     (`biz.approval.process`) and the responsibility catalogue
     (`biz.approval.role`) — the engine's own definitions of what a process
     is. Somebody who sets up routes chooses WHO, never WHAT a process is. So
     those two tables answer only to a system administrator (or the code
     itself, under sudo — every seed and upgrade).

  2. THE PLATFORM'S OWN ROWS. "Suspend, delete or change plan" (`tenant`) and
     the "Platform owner" responsibility decide what happens to a customer's
     whole account. They are the platform's, not the customer's, whatever
     database they sit in. Hidden from, and refused to, everybody who is not a
     system administrator. ("Support access" and "Role grants" are different:
     letting support in, and who here approves a role, are the customer's own
     decisions — `pb_tenancy/models/support_approval.py` says so.)

  3. THE PLATFORM SUPPORT LOGIN IS NOBODY'S TO NAME. The support (recovery)
     login is hidden from every Access screen (`biz_access.visible_people`).
     The set-up screens follow the same rule: it is not offered in a picker,
     it cannot be named as a holder, backup, group member, cover or route
     person, and where it already holds a seat the screen says so without
     showing the account.

Each rail is enforced TWICE: on the screen's facade (whose writes run under
sudo, so a model check would never see them) and on the models themselves (a
direct call over JSON-RPC as the person). Neither touches a decision: who is
asked, who may decide and what is written are exactly as before.
"""

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

#: Processes that decide what happens to a customer's whole account.
PLATFORM_HELD_PROCESSES = frozenset({'tenant'})
#: Responsibilities only the platform fills.
PLATFORM_HELD_ROLES = frozenset({'platform_owner'})

#: How the platform names its support (recovery) login in a database. The
#: same list `pb_records` and `biz_access` read; the default is always one.
RECOVERY_LOGIN_PARAMS = ('pb_tenancy.recovery_login',
                         'pb_tenants.break_glass_login')
RECOVERY_LOGIN_DEFAULT = 'platform.recovery@payobook.com'


def is_platform_person(env):
    """The code itself, or a system administrator."""
    if env.su:
        return True
    user = env.user
    return bool(user._is_superuser() or user._is_system() or user._is_admin())


def recovery_logins(env):
    icp = env['ir.config_parameter'].sudo()
    logins = {RECOVERY_LOGIN_DEFAULT}
    for key in RECOVERY_LOGIN_PARAMS:
        value = str(icp.get_param(key) or '').strip().lower()
        if value:
            logins.add(value)
    return logins


def recovery_user_ids(env):
    logins = recovery_logins(env)
    return set(env['res.users'].sudo().with_context(active_test=False).search(
        [('login', 'in', list(logins))]).ids)


def is_recovery(env, user):
    user = user.sudo() if user else user
    return bool(user) and (user.login or '').strip().lower() in \
        recovery_logins(env)


def definition_user_ids(definition):
    """Every person a route document names directly."""
    ids = set()
    for step in ((definition or {}).get('steps') or []):
        who = (step or {}).get('who') or {}
        if who.get('mode') in ('people', 'team'):
            for uid in who.get('user_ids') or []:
                try:
                    ids.add(int(uid))
                except (TypeError, ValueError):
                    continue
    return ids


def support_refusal():
    return _("The platform's support login is not one of your people, so it "
             "cannot be named here. Choose somebody who works in this "
             "company.")


def platform_refusal():
    return _("That belongs to the platform this runs on, not to your "
             "company, so it is not set up here.")


def catalogue_refusal():
    return _("What a kind of request is, and the list of responsibilities, "
             "are part of the product. You choose who decides; ask your "
             "provider if a kind of request or a responsibility itself is "
             "wrong.")


def check_people(env, user_ids):
    """Refuse the support login among `user_ids` for a client's admin."""
    if is_platform_person(env):
        return True
    wanted = {int(u) for u in (user_ids or []) if u}
    if wanted & recovery_user_ids(env):
        raise UserError(support_refusal())
    return True


def check_process(env, process):
    if is_platform_person(env):
        return True
    if process and process.key in PLATFORM_HELD_PROCESSES:
        raise AccessError(platform_refusal())
    return True


def check_role(env, role):
    if is_platform_person(env):
        return True
    if role and role.key in PLATFORM_HELD_ROLES:
        raise AccessError(platform_refusal())
    return True


# =========================================================================
#  The models: a direct call as the person meets the same rails
# =========================================================================
class BizApprovalProcessRails(models.Model):
    _inherit = 'biz.approval.process'

    @api.model_create_multi
    def create(self, vals_list):
        if not is_platform_person(self.env):
            raise AccessError(catalogue_refusal())
        return super().create(vals_list)

    def write(self, vals):
        if not is_platform_person(self.env):
            raise AccessError(catalogue_refusal())
        return super().write(vals)

    def unlink(self):
        if not is_platform_person(self.env):
            raise AccessError(catalogue_refusal())
        return super().unlink()


class BizApprovalRoleRails(models.Model):
    _inherit = 'biz.approval.role'

    @api.model_create_multi
    def create(self, vals_list):
        if not is_platform_person(self.env):
            raise AccessError(catalogue_refusal())
        return super().create(vals_list)

    def write(self, vals):
        if not is_platform_person(self.env):
            raise AccessError(catalogue_refusal())
        return super().write(vals)

    def unlink(self):
        if not is_platform_person(self.env):
            raise AccessError(catalogue_refusal())
        return super().unlink()


class BizApprovalWorkflowRails(models.Model):
    _inherit = 'biz.approval.workflow'

    @api.model_create_multi
    def create(self, vals_list):
        if not is_platform_person(self.env):
            Process = self.env['biz.approval.process'].sudo()
            for vals in vals_list:
                check_process(self.env, Process.browse(
                    int(vals.get('process_id') or 0)).exists())
        return super().create(vals_list)

    def write(self, vals):
        if not is_platform_person(self.env):
            for rec in self.sudo():
                check_process(self.env, rec.process_id)
            if vals.get('process_id'):
                check_process(self.env, self.env['biz.approval.process'].sudo()
                              .browse(int(vals['process_id'])).exists())
        return super().write(vals)


def _already_named(workflow):
    """People the route in use already names. A client's admin may keep or
    remove them (a draft starts as a copy of it); only ADDING the support
    login is refused."""
    published = workflow.sudo().published_version_id if workflow else None
    return definition_user_ids(published.definition) if published else set()


class BizApprovalVersionRails(models.Model):
    _inherit = 'biz.approval.workflow.version'

    @api.model_create_multi
    def create(self, vals_list):
        if not is_platform_person(self.env):
            Workflow = self.env['biz.approval.workflow'].sudo()
            for vals in vals_list:
                workflow = Workflow.browse(
                    int(vals.get('workflow_id') or 0)).exists()
                check_process(self.env, workflow.process_id)
                check_people(self.env, definition_user_ids(
                    vals.get('definition')) - _already_named(workflow))
        return super().create(vals_list)

    def write(self, vals):
        if not is_platform_person(self.env):
            for rec in self.sudo():
                check_process(self.env, rec.workflow_id.process_id)
                if 'definition' in vals:
                    check_people(self.env, definition_user_ids(
                        vals['definition']) - _already_named(rec.workflow_id))
        return super().write(vals)


class BizApprovalBindingRails(models.Model):
    _inherit = 'biz.approval.binding'

    @api.model_create_multi
    def create(self, vals_list):
        if not is_platform_person(self.env):
            Process = self.env['biz.approval.process'].sudo()
            for vals in vals_list:
                check_process(self.env, Process.browse(
                    int(vals.get('process_id') or 0)).exists())
        return super().create(vals_list)

    def write(self, vals):
        if not is_platform_person(self.env):
            for rec in self.sudo():
                check_process(self.env, rec.process_id)
            if vals.get('process_id'):
                check_process(self.env, self.env['biz.approval.process'].sudo()
                              .browse(int(vals['process_id'])).exists())
        return super().write(vals)


def _m2m_ids(value):
    """The ids a many2many command list ends up adding."""
    ids = set()
    for command in value or []:
        if not isinstance(command, (list, tuple)) or not command:
            continue
        if command[0] == 6 and len(command) > 2:
            ids |= {int(i) for i in command[2] or []}
        elif command[0] == 4 and len(command) > 1:
            ids.add(int(command[1]))
    return ids


class BizApprovalResponsibilityRails(models.Model):
    _inherit = 'biz.approval.responsibility'

    def _p6_check_vals(self, vals):
        people = {vals.get('user_id'), vals.get('backup_user_id')} - {None, False}
        if 'pool_user_ids' in vals:
            people |= _m2m_ids(vals['pool_user_ids'])
        check_people(self.env, people)
        if vals.get('role_id'):
            check_role(self.env, self.env['biz.approval.role'].sudo().browse(
                int(vals['role_id'])).exists())

    @api.model_create_multi
    def create(self, vals_list):
        if not is_platform_person(self.env):
            for vals in vals_list:
                self._p6_check_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if not is_platform_person(self.env):
            for rec in self.sudo():
                check_role(self.env, rec.role_id)
            self._p6_check_vals(vals)
        return super().write(vals)


class BizApprovalEngineRails(models.AbstractModel):
    _inherit = 'biz.approval.engine'

    @api.model
    def publish(self, version_id, expected_draft_revision=None,
                effective_from=None, reason=None, confirmations=None):
        """The platform's own rows are refused BEFORE anything else is
        looked at (the version write would refuse too, after the checks)."""
        if not is_platform_person(self.env):
            version = self.env['biz.approval.workflow.version'].sudo().browse(
                int(version_id or 0)).exists()
            check_process(self.env, version.workflow_id.process_id)
        return super().publish(version_id, expected_draft_revision,
                               effective_from, reason, confirmations)
