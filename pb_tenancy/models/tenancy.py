# -*- coding: utf-8 -*-
"""What this database knows about the platform it is part of.

WHY THIS MODULE EXISTS AT ALL. Until now a customer's database had no idea it
was one of several. It could not say which release of the product it was
running, it could not be told "we are updating tonight", and after an update
nobody in it could find out what had changed. The only channel between the
platform and the people using it was email, sent by hand.

THE WHOLE CONTRACT IS FIVE SETTINGS. The platform WRITES them (through the
customer's own ORM, never raw SQL — rail R5); this database READS them and
nothing else. There is no callback, no queue, no agent process and no open
port. If the platform disappears tomorrow, every screen here keeps working with
the last thing it was told.

    pb_tenancy.release       the release name, e.g. "2026.09.03"
    pb_tenancy.release_date  the day it was cut
    pb_tenancy.releases      the last ten releases as JSON, newest first
    pb_tenancy.notice        the message to show at the top of every page, JSON
    pb_tenancy.pushed_at     when the platform last wrote any of the above

READ-ONLY, FOR EVERYBODY. `state()` is chrome: it is called on every page load
by every logged-in user, so it reads the settings under `sudo()` and returns a
plain dict. It exposes nothing a user could not already see on the screen, and
it can write nothing at all.
"""
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: The five settings, in one place, so the apex and the tenant cannot drift.
P_RELEASE = 'pb_tenancy.release'
P_RELEASE_DATE = 'pb_tenancy.release_date'
P_RELEASES = 'pb_tenancy.releases'
P_NOTICE = 'pb_tenancy.notice'
P_PUSHED_AT = 'pb_tenancy.pushed_at'

#: Set on every provisioned customer by the platform cockpit. Its ABSENCE is
#: how this database knows it is the master — the master is the one database
#: nobody provisioned.
P_SLUG = 'pb.tenant.slug'

#: The two kinds of notice, and they mean different things to a reader:
#: `maintenance` is "something is about to happen to your service" (amber),
#: `info` is "here is something you should know" (indigo).
NOTICE_KINDS = ('maintenance', 'info')


def live_notice(raw, now=None):
    """The notice to show right now, or None. PURE — a test can reach it.

    A notice carries the moment it stops being true, and the platform is not
    expected to come back and clear it: "we are updating between 22:00 and
    01:00" must stop being on the screen at 01:00 whether or not anybody
    remembered. So the end time is checked HERE, on every read, on the reader's
    side. A notice with no end time stands until it is cleared.

    `raw` is whatever the setting holds — JSON, empty, or damage. Damage is
    treated as "no notice": a malformed message must never take a page down.
    """
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        _logger.warning("pb_tenancy: the notice setting is not readable; "
                        "showing nothing.")
        return None
    if not isinstance(data, dict) or not data.get('title'):
        return None
    ends = data.get('ends_at') or ''
    if ends:
        stamp = (now or fields.Datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
        # Both sides are UTC "YYYY-MM-DD HH:MM:SS", so a string comparison is a
        # time comparison — and it cannot raise on a value somebody hand-edited.
        if str(ends)[:19] <= stamp:
            return None
    if data.get('kind') not in NOTICE_KINDS:
        data['kind'] = 'info'
    return data


class PbTenancy(models.AbstractModel):
    _name = 'pb.tenancy'
    _description = 'Payobook platform link'

    @api.model
    def state(self):
        """Everything the browser needs to draw the banner, the toast and the
        What's new page — in one dict, read in one go.

        Called from `session_info`, so it runs on EVERY page load of EVERY user
        on this database. It must therefore be five parameter reads and nothing
        else; it must never raise; and it must be safe for a user with no
        permissions at all, because it is chrome rather than data.
        """
        icp = self.env['ir.config_parameter'].sudo()
        try:
            releases = json.loads(icp.get_param(P_RELEASES, '') or '[]')
            if not isinstance(releases, list):
                releases = []
        except (ValueError, TypeError):
            releases = []
        return {
            'release': icp.get_param(P_RELEASE, '') or '',
            'release_date': icp.get_param(P_RELEASE_DATE, '') or '',
            'releases': releases,
            'notice': live_notice(icp.get_param(P_NOTICE, '')),
            'pushed_at': icp.get_param(P_PUSHED_AT, '') or '',
            # The master is the database nobody provisioned, so it is the one
            # without a subdomain of its own. Used only to word a sentence:
            # nothing is hidden or shown on the strength of it.
            'is_master': not (icp.get_param(P_SLUG, '') or '').strip(),
        }
