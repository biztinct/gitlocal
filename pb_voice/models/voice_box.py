# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.voice.box`` — where answers end up, and why nobody can trace them.

THE PRIVACY CONTRACT (owner ruling P4 — read this before adding anything)
=======================================================================
Nobody, not even HR, may be able to tell who answered what. "By
construction" means there is nothing in the database to join, not that a
screen hides it. Precedent: ``pb_ess_workforce/models/shift_pulse.py`` — and
its two lessons (``sudo()`` stamps ``create_uid``; time stamps identify people
in small teams). This design goes further than the shift pulse in four ways:

1. NO ANSWER ROW EXISTS. Not "an answer row without an employee column": no
   row per answer at all. While a round is open the database holds NO answer
   content whatsoever. Each answer is sealed into a file OUTSIDE the database
   (the database's own file store, ``<filestore>/pb_voice/<round>/``) under a
   random name. When the round closes, every sealed answer goes into the
   database IN ONE WRITE, as COUNTS per group cell (how many chose each
   step) plus the written comments sorted by their text. So:
     * no row id, sequence number or insertion order belongs to an answer;
     * no ``create_uid`` / ``write_uid`` / ``create_date`` / ``write_date``:
       the table has ``_log_access = False`` — the columns do not exist;
     * no PostgreSQL transaction id (``xmin``) ties an answer to the request
       that sent it (a sign-in record written in the SAME request — Odoo's
       ``res_device_log``, ``odoo/addons/base/models/res_device.py:94`` —
       shares that transaction); the one write happens when the round closes;
     * no time finer than the day the round closed;
     * no IP, no session, no browser.
   If fewer than the floor answered the whole round, the sealed answers are
   DESTROYED at close and nothing is kept.

2. "WHO HAS ANSWERED" IS A SEPARATE YES/NO LIST that cannot be joined. It is
   a sorted list of one-way codes (HMAC-SHA256 of the person, keyed with a
   random key). The key lives in the FILE STORE, not in the database, so a
   person with full database access cannot even work out who has answered;
   and the key is DESTROYED when the round closes, after which nobody — not a
   system administrator either — can. The list is sorted by code, so its
   order says nothing about when anybody answered. It is used for three
   things only: one answer per person, the reminder, and the person's own
   "Needs you" row.

3. CELLS ARE NEVER SMALL. Group keys (company, department, team) are fixed
   when the round opens, and each invited person's combination of keys (a
   "cell") is coarsened until every cell holds at least the floor of INVITED
   people (``pb.voice.round._voice_cells``). A stored count therefore always
   belongs to one of at least five people.

4. RESULTS ONLY AFTER CLOSE, through ONE facade (``pb.voice``), with the floor
   and the secondary suppression applied to every number AND every comment,
   on screen and in the Excel download. This model has no access right for
   any group (one all-zero line so the loader does not warn), so no list,
   export, Workflow Studio or API reaches it: only the facade, under sudo,
   behind its own gate.

WHAT THIS DOES NOT PROTECT AGAINST (said in the help text, never promised
away): somebody with access to the SERVER ITSELF (its disk and memory) while
a round is open could read sealed files or the key. That is a system
administrator, not HR, and not a database user.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil

from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)

_KEY_FILE = 'key'
_SEAL_SUFFIX = '.sealed'


class PbVoiceBox(models.Model):
    _name = 'pb.voice.box'
    _description = 'Survey answers (sealed)'
    # No create_uid / write_uid / create_date / write_date columns AT ALL.
    _log_access = False
    # No mail.thread: a chatter has authors, and this record must not have one.

    round_id = fields.Many2one('pb.voice.round', required=True, index=True,
                               ondelete='cascade')
    #: Sorted JSON list of one-way codes, one per person who answered. Wiped
    #: when the round closes (the key is destroyed then too).
    marks = fields.Text(default='[]')
    #: Filled ONCE, when the round closes: {"cells": {cell: {"n": int,
    #: "q": {qid: {value: count}}}}, "notes": [[cell, qid, text], ...]}
    #: (notes sorted by cell, question and text — never by arrival).
    sealed = fields.Text()

    _round_unique = models.Constraint('unique(round_id)',
                                      'A round has one answer box.')

    # ------------------------------------------------------------ the place
    @api.model
    def _voice_root(self):
        return os.path.join(tools.config.filestore(self.env.cr.dbname),
                            'pb_voice')

    @api.model
    def _voice_dir(self, round_id, create=False):
        path = os.path.join(self._voice_root(), str(int(round_id)))
        if create:
            os.makedirs(path, mode=0o700, exist_ok=True)
        return path

    # -------------------------------------------------------------- the key
    @api.model
    def _voice_key(self, round_id, create=False):
        """The round's random key (bytes), kept in the file store, never in
        the database. ``None`` when there is none and ``create`` is False."""
        path = os.path.join(self._voice_dir(round_id, create=create), _KEY_FILE)
        try:
            with open(path, 'rb') as fh:
                key = fh.read()
            if key:
                return key
        except FileNotFoundError:
            pass
        if not create:
            return None
        key = secrets.token_bytes(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as fh:
            fh.write(key)
            fh.flush()
            os.fsync(fh.fileno())
        return key

    @api.model
    def _voice_code(self, key, person_key):
        """One-way code of a person for one round (cannot be reversed; cannot
        be made without the key)."""
        return hmac.new(key, str(person_key).encode('utf-8'),
                        hashlib.sha256).hexdigest()[:40]

    # ------------------------------------------------------------ the marks
    def _marks(self):
        self.ensure_one()
        try:
            return set(json.loads(self.sudo().marks or '[]'))
        except ValueError:
            return set()

    # ------------------------------------------------------ the sealed files
    @api.model
    def _seal_write(self, round_id, payload):
        """Seal one answer OUTSIDE the database under a random name. Returns
        the path (so a rollback can take it back)."""
        folder = self._voice_dir(round_id, create=True)
        name = secrets.token_hex(16) + _SEAL_SUFFIX
        path = os.path.join(folder, name)
        data = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        return path

    @api.model
    def _seal_paths(self, round_id):
        folder = self._voice_dir(round_id)
        try:
            names = os.listdir(folder)
        except FileNotFoundError:
            return []
        return sorted(os.path.join(folder, n) for n in names
                      if n.endswith(_SEAL_SUFFIX))

    @api.model
    def _seal_read_all(self, round_id):
        """Every sealed answer of a round, as dicts (unreadable files skipped
        and logged without their content)."""
        out = []
        for path in self._seal_paths(round_id):
            try:
                with open(path, encoding='utf-8') as fh:
                    out.append(json.loads(fh.read()))
            except (OSError, ValueError):
                _logger.warning('pb_voice: a sealed answer could not be read '
                                'and was skipped')
        return out

    @api.model
    def _voice_destroy(self, round_id):
        """Remove the round's key and every sealed file (the folder)."""
        shutil.rmtree(self._voice_dir(round_id), ignore_errors=True)

    @api.model
    def _seal_unlink(self, path):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
