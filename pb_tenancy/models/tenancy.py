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
    pb_tenancy.features      which parts of the product this company has, JSON
    pb_tenancy.pushed_at     when the platform last wrote any of the above

FEATURES, AND THE ONE RULE THAT MATTERS ABOUT THEM (FLEET P4). The platform can
say "Insights is not switched on for this company", and the rail entry, the
tiles, the search rows and the Settings card for it go away — or show a padlock
with one line about how to get it, if that is what the platform said.

  IT IS NOT A PERMISSION. A switch takes doors off a screen; it does not put a
  lock on the data behind them. Everything a person may read or write here is
  still decided by the roles they hold on this database, exactly as before.

  AND IT FAILS OPEN. A database that has never been told anything reads the
  missing setting as "everything is switched on". That is the only safe
  direction: the alternative is that a database the platform has not got round
  to yet loses half its product overnight, which is a payroll office that
  cannot pay people because a setting was absent.

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
P_FEATURES = 'pb_tenancy.features'
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


#: How an OFF feature shows on this database. Kept as literals rather than
#: imported from the platform's own module, which is not installed here and
#: never will be.
FEATURE_MODES = ('hide', 'lock')

#: The line under a padlock when the platform sent one with no words of its own.
#: A dead end is a dead end whether or not somebody remembered to fill a field.
DEFAULT_LOCK_TEXT = ("This part of Payobook is not switched on for your "
                     "company. Ask Payobook to switch it on.")


def read_features(raw):
    """`{key: {'on', 'mode', 'lock_text'}}` from the setting. PURE.

    FAIL OPEN, THREE TIMES OVER. An empty setting, a setting that is not JSON,
    and a setting whose shape is not what this version expects all produce the
    SAME answer: an empty dict, which every reader treats as "nothing is
    switched off". A database must never lose part of the product because a
    string was damaged.

    An entry may be written either as a bare boolean (`{"insights": false}`) or
    as the full object the platform sends. Both are accepted, because the short
    form is what somebody typing into the settings by hand in an emergency will
    write, and refusing it would make the emergency worse.
    """
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        _logger.warning("pb_tenancy: the feature settings are not readable; "
                        "every part of the product stays switched on.")
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for key, val in data.items():
        if not isinstance(key, str) or not key:
            continue
        if isinstance(val, dict):
            on = val.get('on', True)
            mode = val.get('mode')
            text = val.get('lock_text') or ''
        else:
            on, mode, text = val, 'hide', ''
        out[key] = {
            'on': bool(on),
            'mode': mode if mode in FEATURE_MODES else 'hide',
            'lock_text': (text or '').strip() or DEFAULT_LOCK_TEXT,
        }
    return out


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
        feats = read_features(icp.get_param(P_FEATURES, ''))
        return {
            # THREE SEPARATE MAPS, NOT ONE NESTED ONE, because the browser asks
            # three different questions of them in three different places: is
            # this on (every gate), how does it look when it is off (the shell
            # and the palette), and what does the padlock say (one dialog).
            # A nested object would have every one of those reaching two levels
            # deep for a boolean.
            'features': {k: v['on'] for k, v in feats.items()},
            'feature_mode': {k: v['mode'] for k, v in feats.items()},
            'feature_lock_text': {k: v['lock_text'] for k, v in feats.items()},
            # Has this database ever been told anything about features? Used
            # only to word a sentence for the platform owner; nothing is hidden
            # or shown on the strength of it, because "never told" already
            # means "everything on" through the empty maps above.
            'features_known': bool(feats),
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

    @api.model
    def features(self):
        """`{key: {'on', 'mode', 'lock_text'}}` — the server's own reader.

        THE RAIL ASKS THIS, ONCE PER PAGE LOAD. It is one settings read, and
        `ir.config_parameter` caches those, so the cost of consulting it for
        nine menu entries is one dictionary lookup nine times.

        Same answer as `state()['features']` by construction — both go through
        `read_features` — so the menu the server draws and the tiles the
        browser draws can never disagree about what a company has.
        """
        return read_features(
            self.env['ir.config_parameter'].sudo().get_param(P_FEATURES, ''))

    @api.model
    def feature_state(self, key):
        """(on, mode, lock_text) for ONE feature. Absent means ON."""
        if not key:
            return True, 'hide', ''
        row = self.features().get(key)
        if not row:
            return True, 'hide', ''
        return row['on'], row['mode'], row['lock_text']
