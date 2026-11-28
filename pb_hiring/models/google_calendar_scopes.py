"""Limit Calendar consent without modifying the standard Google addons."""

from odoo import api, models


CALENDAR_SCOPE = 'https://www.googleapis.com/auth/calendar'


class GoogleService(models.AbstractModel):
    _inherit = 'google.service'

    @api.model
    def _get_authorize_uri(self, service, scope, redirect_uri, state=None,
                           approval_prompt=None, access_type=None):
        # Standard Odoo requests full Calendar access. Payobook synchronises
        # primary-calendar events and queries participant availability only.
        # Apply this at the registry hook, not a process-wide SDK monkey patch.
        if service == 'calendar':
            replacements = {
                CALENDAR_SCOPE: (CALENDAR_SCOPE + '.events.owned',
                                 CALENDAR_SCOPE + '.events.freebusy'),
                CALENDAR_SCOPE + '.readonly': (
                    CALENDAR_SCOPE + '.events.owned.readonly',
                    CALENDAR_SCOPE + '.events.freebusy'),
            }
            scopes = []
            for requested in scope.split():
                for narrowed in replacements.get(requested, (requested,)):
                    if narrowed not in scopes:
                        scopes.append(narrowed)
            scope = ' '.join(scopes)
        return super()._get_authorize_uri(
            service, scope, redirect_uri, state=state,
            approval_prompt=approval_prompt, access_type=access_type)
