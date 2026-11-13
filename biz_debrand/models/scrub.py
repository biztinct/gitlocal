# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
r"""One-off scrub of vendor references already written into the database.

The runtime seams (``_()`` patch, QWeb tree walker, JS ``_t()`` patch, Apps-list
``read()``) cover everything rendered *from source*. They cannot touch content
that was materialised into rows before the brand existed — chatter messages the
bot posted, activity notes, chat names, digest tips, seeded social links.

Runs from ``_biz_debrand_apply_brand``, i.e. on install, on every upgrade of
this module, and on every save of the Branding settings. Idempotent by
construction: the rewrite is a no-op once applied, and rows are only touched
when they still match.

WHITELABEL REVERSE (2026-11-01): the PRODUCT rule's rewrites are journaled in
``biz_debrand_rewrite`` and undone by ``_biz_debrand_restore_rows`` — which
runs first on every scrub — whenever the brand or the product the database is
configured with no longer matches the one a journal entry was written under.
That is what takes a tenant from the white-label level back to the standard
one with its stored text saying the product's name again.

Deliberately NOT scrubbed:
  * ``ir_module_module`` metadata — re-imported from every ``__manifest__.py``
    on each ``-u``; handled at ``read()`` instead (see ir_module_module.py).
  * ``ir_model_fields*`` — debranded at runtime, not in the row. ``-u``
    re-imports every label and tooltip from source on each upgrade, so a scrub
    of these tables is a fix with a half-life. The seam is
    ``get_field_string`` / ``get_field_help`` / ``get_field_selection``, which
    ``web_debranding`` overrides and ``models/ir_model_fields.py`` then layers
    the canonical rules on top of — ERRORS E3-1 found web_debranding's own rule
    refusing ``OdooBot`` (its word rule ends ``(?!\w)``), so "already debranded
    at runtime" was true of the 37 ``help`` rows and false of the ``Bot``-shaped
    ``field_description`` ones.
  * email *addresses* — only the display name of an address is rewritten;
    rewriting the addr-spec would silently change routing.
"""
import json
import logging
import re

from psycopg2.extras import Json

from odoo import models

from .brand import (
    HAS_ODOO_RE, brand_for_env, debrand_text, product_for_env, product_rules,
)

_logger = logging.getLogger(__name__)

# WHITELABEL REVERSE 2026-11-01. Every row the PRODUCT rule rewrites is
# journaled here — table, row, column, the raw value it had before and the
# value it was given — so that leaving the white-label level (or changing the
# brand name) can put the master product's name back in exactly the rows it
# was taken out of, and nowhere else. A tenant's own use of its brand name in
# a rule note or an email is never touched, because it was never journaled.
#
# A plain table, not a model: it is written and read by raw SQL in this file
# only, nobody edits it on a screen, and ``CREATE TABLE IF NOT EXISTS`` makes
# it exist on the first scrub after an upgrade without an ordering dependency.
JOURNAL = "biz_debrand_rewrite"
JOURNAL_DDL = (
    """
    CREATE TABLE IF NOT EXISTS {t} (
        id           serial PRIMARY KEY,
        table_name   varchar NOT NULL,
        res_id       integer NOT NULL,
        column_name  varchar NOT NULL,
        kind         varchar NOT NULL,
        product      varchar NOT NULL,
        brand        varchar NOT NULL,
        before_value text,
        after_value  text,
        written_at   timestamp NOT NULL DEFAULT (now() at time zone 'UTC')
    )
    """.format(t=JOURNAL),
    """
    CREATE UNIQUE INDEX IF NOT EXISTS {t}_cell_uniq
        ON {t} (table_name, res_id, column_name)
    """.format(t=JOURNAL),
)
JOURNAL_UPSERT = """
    INSERT INTO {t} (table_name, res_id, column_name, kind, product, brand,
                     before_value, after_value, written_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now() at time zone 'UTC')
    ON CONFLICT (table_name, res_id, column_name) DO UPDATE
       SET kind = EXCLUDED.kind, product = EXCLUDED.product,
           brand = EXCLUDED.brand, before_value = EXCLUDED.before_value,
           after_value = EXCLUDED.after_value, written_at = EXCLUDED.written_at
""".format(t=JOURNAL)


def _json_cell(value):
    """One canonical text form for a jsonb cell, so two dicts compare as text."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)

# (table, [plain text/varchar columns]) — scrubbed row by row in Python so the
# rewrite rules are identical to every other seam (PostgreSQL regexes have no
# lookahead, so an equivalent SQL expression is not possible).
#
# WHITELABEL 2026-10-31: the PRODUCT rule now runs here too, on a database
# whose ``biz_debrand.product_name`` is set (a white-label tenant). The owner's
# ruling: "rewrite everything" — a tenant on the paid level must not find the
# master product's name in an old email, a lesson, a journey step or a rule
# note. On the master and on the template ``product_name`` is empty and this
# whole family of rows is left exactly as it was.
TEXT_TARGETS = [
    ("mail_message", ["body", "subject"]),
    ("mail_mail", ["body_html"]),
    ("mail_activity", ["note"]),
    ("discuss_channel", ["name", "description"]),
    ("ir_ui_view", ["name"]),
    ("ir_asset", ["name"]),
    ("ir_cron", ["cron_name"]),
    ("ir_model", ["info"]),
    ("hr_job", ["requirements"]),
    # Product-only rows (never carried the vendor's name): seeded notes and
    # step descriptions that talk about the product in the third person.
    ("pb_zoho_event_rule", ["name", "note"]),
    ("pb_journey_task", ["name", "description", "note"]),
    ("pb_journey_template_step", ["description"]),
    ("hr_formula_rule", ["application_source_note", "validation_message"]),
    ("hr_integration_mapping_template", ["note"]),
    ("pb_asset", ["notes", "supplier_note", "movable_note", "model_name"]),
]

# (table, [jsonb translated columns])
JSONB_TARGETS = [
    ("ir_actions", ["name", "help"]),
    ("ir_act_window", ["help"]),
    ("ir_act_server", ["name"]),
    ("ir_act_report_xml", ["name"]),
    ("ir_model", ["name"]),
    ("ir_model_constraint", ["message"]),
    ("res_groups", ["name", "comment"]),
    ("digest_tip", ["name", "tip_description"]),
    ("mail_template", ["name", "subject", "body_html"]),
    ("hr_skill", ["name"]),
    ("hr_resume_line", ["name"]),
    ("hr_job", ["description"]),
    ("pb_journey_template_step", ["name"]),
    # pb_learn deliberately described the legacy salary structures by the
    # vendor's name. Ruled out by the brand owner: no vendor mention anywhere,
    # legacy or not. The module's source XML is fixed too, so a reinstall does
    # not bring it back — this only catches already-loaded rows.
    #
    # WHITELABEL: every translated Learn column, because a lesson that says
    # "do this in Payobook" is read by the tenant's people verbatim — the
    # Learn runtime renders these rows without a seam.
    ("learn_station", ["name", "summary", "outline_what", "outline_why",
                       "outline_when", "outline_prereq"]),
    ("learn_station_mistake", ["name"]),
    ("learn_column", ["body", "label"]),
    ("learn_screen", ["blurb", "name", "next_step", "live_fallback"]),
    ("learn_lesson", ["name", "goal"]),
    ("learn_string", ["value"]),
    ("learn_step", ["title", "body", "kicker", "tip", "consequence"]),
    ("learn_mission", ["name", "summary", "outline_note", "anomaly_title",
                       "anomaly_body", "consequence_title", "consequence_scope",
                       "consequence_reversible", "consequence_verify"]),
    ("learn_mission_step", ["instruction", "detail", "hint"]),
    ("learn_glossary_term", ["term", "definition"]),
]

# Vendor-owned social accounts seeded into every website record.
SOCIAL_COLUMNS = [
    "social_facebook",
    "social_twitter",
    "social_linkedin",
    "social_github",
    "social_instagram",
    "social_tiktok",
    "social_youtube",
]

# Any host under the vendor's domain — including subdomains such as
# apps.odoo.com, which debrand_url deliberately leaves alone.
VENDOR_URL_RE = re.compile(r"https?://(?:[\w-]+\.)*odoo\.(?:com|sh)\b", re.IGNORECASE)

BATCH = 2000


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _biz_columns(self, table, columns):
        """Return the subset of ``columns`` that actually exists on ``table``."""
        self.env.cr.execute(
            """
            SELECT column_name FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = %s AND column_name = ANY(%s)
            """,
            (table, list(columns)),
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _biz_sql_prefilter(self, product):
        """The SQL word pattern that decides which rows Python even looks at.

        ``\\modoo`` alone on an ordinary database; ``\\m(odoo|payobook)`` on a
        white-label tenant, so the product rule's rows are fetched too. The
        product name is only put into the pattern when it is a plain word —
        anything else would need regex escaping and is not a product name
        anybody has configured.
        """
        product = (product or "").strip()
        if product and re.fullmatch(r"\w+", product):
            return "\\m(odoo|%s)" % product.lower()
        return "\\modoo"

    def _biz_scrub_text(self, table, columns, brand, website, product=None):
        columns = self._biz_columns(table, columns)
        if not columns:
            return 0
        word = self._biz_sql_prefilter(product)
        cols = ", ".join('"%s"' % c for c in columns)
        where = " OR ".join("""%s ~* '%s'""" % ('"%s"' % c, word) for c in columns)
        self.env.cr.execute('SELECT id, %s FROM "%s" WHERE %s' % (cols, table, where))
        rows = self.env.cr.fetchall()
        updates = []
        journal = []
        for row in rows:
            record_id, values = row[0], row[1:]
            new_values = [debrand_text(v, brand, website, product) if isinstance(v, str) else v for v in values]
            if any(new is not old for new, old in zip(new_values, values)):
                updates.append(tuple(new_values) + (record_id,))
                if product:
                    # Journal only the cells the PRODUCT rule changed: the
                    # vendor-only result is what the cell would have become
                    # without it, so a difference means the product's name
                    # was in there and has to be reversible.
                    for column, old, new in zip(columns, values, new_values):
                        if (new is not old and isinstance(old, str)
                                and new != debrand_text(old, brand, website)):
                            journal.append((table, record_id, column, "text",
                                            product, brand, old, new))
        if not updates:
            return 0
        assignment = ", ".join('"%s" = %%s' % c for c in columns)
        sql = 'UPDATE "%s" SET %s WHERE id = %%s' % (table, assignment)
        for start in range(0, len(updates), BATCH):
            self.env.cr.executemany(sql, updates[start:start + BATCH])
        self._biz_journal_write(journal)
        return len(updates)

    def _biz_scrub_jsonb(self, table, columns, brand, website, product=None):
        columns = self._biz_columns(table, columns)
        if not columns:
            return 0
        word = self._biz_sql_prefilter(product)
        touched = 0
        for column in columns:
            self.env.cr.execute(
                """SELECT id, "%s" FROM "%s" WHERE "%s"::text ~* '%s'"""
                % (column, table, column, word)
            )
            updates = []
            journal = []
            for record_id, value in self.env.cr.fetchall():
                if not isinstance(value, dict):
                    continue
                new_value = {
                    lang: debrand_text(text, brand, website, product) if isinstance(text, str) else text
                    for lang, text in value.items()
                }
                if new_value != value:
                    updates.append((new_value, record_id))
                    if product:
                        vendor_only = {
                            lang: debrand_text(text, brand, website) if isinstance(text, str) else text
                            for lang, text in value.items()
                        }
                        if new_value != vendor_only:
                            journal.append((table, record_id, column, "jsonb",
                                            product, brand,
                                            _json_cell(value), _json_cell(new_value)))
            if not updates:
                continue
            sql = 'UPDATE "%s" SET "%s" = %%s WHERE id = %%s' % (table, column)
            payload = [(Json(value), record_id) for value, record_id in updates]
            for start in range(0, len(payload), BATCH):
                self.env.cr.executemany(sql, payload[start:start + BATCH])
            self._biz_journal_write(journal)
            touched += len(payload)
        return touched

    # ------------------------------------------------------------------
    # WHITELABEL REVERSE — the journal and the way back
    # ------------------------------------------------------------------
    def _biz_journal_ready(self):
        for ddl in JOURNAL_DDL:
            self.env.cr.execute(ddl)

    def _biz_journal_write(self, entries):
        """Record the cells the product rule just changed. Own savepoint: a
        journal that cannot be written must not undo the rewrite it records."""
        if not entries:
            return
        try:
            with self.env.cr.savepoint():
                self._biz_journal_ready()
                for start in range(0, len(entries), BATCH):
                    self.env.cr.executemany(JOURNAL_UPSERT, entries[start:start + BATCH])
        except Exception:
            _logger.warning("biz_debrand: brand journal write failed (%s cells)",
                            len(entries), exc_info=True)

    @staticmethod
    def _biz_unbrand_rule(brand):
        """The word rule that swaps ``brand`` back for the product in a cell
        somebody edited after it was rewritten. Same guards as the forward
        rule, so ``rize.payobook.com``, ``rize_website`` and ``/rize/`` stay
        exactly as they are; case-sensitive, because the forward rule wrote
        the brand exactly as configured."""
        return re.compile(r"(?<![.\w/-])" + re.escape(brand) + r"(?![\w/\[-])(?!\.\w)")

    def _biz_debrand_restore_rows(self):
        """Put the product's name back wherever the journal says it was taken
        out under a brand this database no longer uses.

        Called at the start of every scrub, so it covers all three ways the
        level can change: the master's Tenants cockpit, the tenant's own
        Branding page, and an upgrade that follows either. Entries that still
        match the current brand AND product (a plain re-save) are left alone.

        Per cell: if it still holds exactly what the rewrite wrote, the raw
        pre-rewrite value goes back (the vendor rule then re-runs on it in
        the forward pass that follows, under the current brand). If somebody
        edited the cell since, only the brand word is swapped back, with the
        forward rule's own guards. A row deleted since is simply forgotten.
        Returns the number of cells changed.
        """
        self._biz_journal_ready()
        brand, _website = brand_for_env(self.env)
        product = product_for_env(self.env)
        active = bool(brand) and bool(product_rules(product, brand))
        self.env.cr.execute(
            "SELECT id, table_name, res_id, column_name, kind, product, brand, "
            "before_value, after_value FROM %s ORDER BY table_name, res_id" % JOURNAL
        )
        entries = self.env.cr.fetchall()
        restored, forgotten = 0, []
        for (jid, table, res_id, column, kind, j_product, j_brand,
             before, after) in entries:
            if active and j_brand == brand and j_product == product:
                continue  # same level, same words: nothing to undo
            try:
                with self.env.cr.savepoint():
                    if not self._biz_columns(table, [column]):
                        forgotten.append(jid)
                        continue
                    self.env.cr.execute(
                        'SELECT "%s" FROM "%s" WHERE id = %%s' % (column, table), (res_id,)
                    )
                    row = self.env.cr.fetchone()
                    if row is None:
                        forgotten.append(jid)
                        continue
                    current = row[0]
                    rule = self._biz_unbrand_rule(j_brand)
                    if kind == "jsonb":
                        now_text = _json_cell(current) if isinstance(current, dict) else None
                        if now_text == after:
                            new_value = json.loads(before)
                        elif isinstance(current, dict):
                            new_value = {
                                lang: rule.sub(j_product, text) if isinstance(text, str) else text
                                for lang, text in current.items()
                            }
                        else:
                            forgotten.append(jid)
                            continue
                        if new_value != current:
                            self.env.cr.execute(
                                'UPDATE "%s" SET "%s" = %%s WHERE id = %%s' % (table, column),
                                (Json(new_value), res_id),
                            )
                            restored += 1
                    else:
                        if current == after:
                            new_value = before
                        elif isinstance(current, str):
                            new_value = rule.sub(j_product, current)
                        else:
                            forgotten.append(jid)
                            continue
                        if new_value != current:
                            self.env.cr.execute(
                                'UPDATE "%s" SET "%s" = %%s WHERE id = %%s' % (table, column),
                                (new_value, res_id),
                            )
                            restored += 1
                    forgotten.append(jid)
            except Exception:
                _logger.warning("biz_debrand: restore of %s.%s#%s failed",
                                table, column, res_id, exc_info=True)
        if forgotten:
            for start in range(0, len(forgotten), BATCH):
                self.env.cr.execute(
                    "DELETE FROM %s WHERE id = ANY(%%s)" % JOURNAL,
                    (forgotten[start:start + BATCH],),
                )
        if restored:
            self.env.invalidate_all()
            self.env.registry.clear_cache("default", "templates")
            _logger.info("biz_debrand: restored %s stored cells from the brand "
                         "journal (brand now %r, product %r)", restored, brand, product)
        return restored

    def _biz_debrand_journal_count(self):
        """How many cells the journal could put back right now."""
        self._biz_journal_ready()
        self.env.cr.execute("SELECT count(*) FROM %s" % JOURNAL)
        return self.env.cr.fetchone()[0]

    def _biz_scrub_email_display_names(self, brand, website):
        """Rewrite only the display-name part of stored ``"Name" <addr>`` values.

        8,490 historical ``mail_message`` rows carry ``"OdooBot"
        <odoobot@example.com>``. The address is routing data and is left
        untouched; only the quoted name a human reads is rebranded.
        """
        touched = 0
        for table, columns in (("mail_message", ["email_from", "reply_to"]),):
            for column in self._biz_columns(table, columns):
                self.env.cr.execute(
                    """SELECT DISTINCT "%s" FROM "%s" WHERE "%s" ~* '\\modoo'"""
                    % (column, table, column)
                )
                for (value,) in self.env.cr.fetchall():
                    if not value or "<" not in value:
                        continue  # bare address: no display name to rebrand
                    display, _, rest = value.partition("<")
                    new_display = debrand_text(display, brand, website)
                    if new_display is display:
                        continue
                    self.env.cr.execute(
                        'UPDATE "%s" SET "%s" = %%s WHERE "%s" = %%s' % (table, column, column),
                        (new_display + "<" + rest, value),
                    )
                    touched += self.env.cr.rowcount
        return touched

    def _biz_scrub_socials(self):
        """Clear the vendor's own social accounts seeded into website records."""
        columns = self._biz_columns("website", SOCIAL_COLUMNS)
        if not columns:
            return 0
        clauses = " OR ".join("""%s ~* '\\modoo'""" % ('"%s"' % c) for c in columns)
        assignment = ", ".join(
            """"{c}" = CASE WHEN "{c}" ~* '\\modoo' THEN NULL ELSE "{c}" END""".format(c=c)
            for c in columns
        )
        self.env.cr.execute("UPDATE website SET %s WHERE %s" % (assignment, clauses))
        return self.env.cr.rowcount

    def _biz_scrub_demo_emails(self, brand, website):
        """Vendor addresses seeded into contact records.

        Two distinct shapes, both non-routable:
          * ``…@odoo.com`` on demo contacts -> the reserved ``example.com``;
          * ``odoobot@example.com``, the bot's placeholder local-part, which is
            what still reads "odoobot" in Technical -> Emails once the display
            name has been rebranded.
        Real customer addresses are never matched: only these two patterns are.
        """
        local = re.sub(r"[^a-z0-9]+", "", brand.lower()) or "bot"
        touched = 0
        for table, column in (
            ("res_partner", "email"),
            ("res_partner", "email_normalized"),
            ("hr_employee", "work_email"),
            ("hr_employee", "private_email"),
            ("mail_message", "email_from"),
            ("mail_message", "reply_to"),
        ):
            if not self._biz_columns(table, [column]):
                continue
            self.env.cr.execute(
                """UPDATE "{t}" SET "{c}" = regexp_replace("{c}", '@(www\\.)?odoo\\.com\\M', '@example.com', 'gi')
                    WHERE "{c}" ~* '@(www\\.)?odoo\\.com\\M'""".format(t=table, c=column)
            )
            touched += self.env.cr.rowcount
            self.env.cr.execute(
                """UPDATE "{t}" SET "{c}" = regexp_replace("{c}", '\\modoo[_-]?bot@', %s, 'gi')
                    WHERE "{c}" ~* '\\modoo[_-]?bot@'""".format(t=table, c=column),
                (local + "@",),
            )
            touched += self.env.cr.rowcount
        return touched

    def _biz_scrub_backend_links(self):
        """Retarget stored ``/odoo/...`` deep links at the rebranded prefix.

        Chatter bodies and mail templates embed absolute backend links. The
        text rewrite deliberately leaves paths alone (they are routing, not
        prose), so this is handled here — and only when a router rebrand such
        as biz_deroute is actually installed to receive them.
        """
        prefix = self._biz_debrand_webclient_prefix()
        if not prefix:
            return 0
        touched = 0
        for table, column in (
            ("mail_message", "body"),
            ("mail_template", "body_html"),
        ):
            if not self._biz_columns(table, [column]):
                continue
            self.env.cr.execute(
                """UPDATE "{t}" SET "{c}" = replace("{c}"::text, '"/odoo/', %s)::{cast}
                    WHERE "{c}"::text LIKE %s""".format(
                    t=table,
                    c=column,
                    cast="jsonb" if self._biz_is_jsonb(table, column) else "text",
                ),
                ('"%s/' % prefix, '%"/odoo/%'),
            )
            touched += self.env.cr.rowcount
        return touched

    def _biz_scrub_vendor_menus(self):
        """Archive menu items whose only purpose is to leave for the vendor.

        "Third-Party Apps" and "Theme Store" are ungrouped, active menus bound
        to ``ir.actions.act_url`` targets on ``apps.odoo.com``. Their *labels*
        are already brand-neutral, so no text rule catches them, but clicking
        one lands the user on the vendor's storefront. The subdomain is left
        out of the URL rewrite on purpose (see debrand_url), so retiring the
        entry is the honest fix.

        Scoped by destination host, not by label: only menus that actually
        navigate to a vendor domain are touched.
        """
        menus = self.env["ir.ui.menu"].sudo().search([("active", "=", True)])
        targets = menus.filtered(
            lambda m: isinstance(m.action, models.BaseModel)
            and m.action._name == "ir.actions.act_url"
            and VENDOR_URL_RE.search(m.action.url or "")
        )
        if not targets:
            return 0
        _logger.info("biz_debrand: archiving vendor menus %s", targets.mapped("name"))
        targets.write({"active": False})
        return len(targets)

    def _biz_is_jsonb(self, table, column):
        self.env.cr.execute(
            """SELECT data_type FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s AND column_name=%s""",
            (table, column),
        )
        row = self.env.cr.fetchone()
        return bool(row) and row[0] == "jsonb"

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------
    def _biz_debrand_scrub_data(self):
        brand, website = brand_for_env(self.env)
        if not brand or HAS_ODOO_RE.search(brand):
            _logger.warning("biz_debrand: refusing to scrub with brand %r", brand)
            return False
        # WHITELABEL: the product rule, exactly as the seams apply it, and off
        # (``None``) wherever product_rules() says so — master, template, the
        # "powered by" level, or a product that IS the brand.
        product = product_for_env(self.env)
        if not product_rules(product, brand):
            product = None

        # WHITELABEL REVERSE: first undo what an earlier brand did, so a tenant
        # that left the white-label level (or renamed its brand) gets the
        # product's name back before the forward pass runs under the brand
        # it has now. Its own savepoint: the way back must never block the
        # way forward.
        try:
            with self.env.cr.savepoint():
                self._biz_journal_ready()
                self._biz_debrand_restore_rows()
        except Exception:
            _logger.warning("biz_debrand: brand journal restore failed", exc_info=True)

        total = 0
        for table, columns in TEXT_TARGETS:
            try:
                # Each target in its own savepoint: a column that turns out to
                # be the wrong type on this build must not poison the cursor
                # for every target after it.
                with self.env.cr.savepoint():
                    total += self._biz_scrub_text(table, columns, brand, website, product)
            except Exception:
                _logger.warning("biz_debrand: scrub of %s failed", table, exc_info=True)
        for table, columns in JSONB_TARGETS:
            try:
                with self.env.cr.savepoint():
                    total += self._biz_scrub_jsonb(table, columns, brand, website, product)
            except Exception:
                _logger.warning("biz_debrand: jsonb scrub of %s failed", table, exc_info=True)
        for step in (
            lambda: self._biz_scrub_email_display_names(brand, website),
            self._biz_scrub_socials,
            lambda: self._biz_scrub_demo_emails(brand, website),
            self._biz_scrub_backend_links,
            self._biz_scrub_vendor_menus,
        ):
            try:
                total += step()
            except Exception:
                _logger.warning("biz_debrand: scrub step failed", exc_info=True)

        # Rewritten rows are cached: translated fields in the ORM cache, and
        # QWeb trees in the 'templates' cache keyed by view id, not by brand.
        self.env.invalidate_all()
        self.env.registry.clear_cache("default", "templates")
        _logger.info("biz_debrand: scrubbed %s stored rows as %r", total, brand)
        return total
