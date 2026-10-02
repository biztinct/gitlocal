# -*- coding: utf-8 -*-
"""ACCESS P9 — "Your company": the one record a customer's administrator may fix.

THE DISTINCTION THIS FILE EXISTS TO HOLD.

This product runs one database per customer. Two different people administer it:
whoever runs the PLATFORM (the fleet of databases, the web addresses, the
certificates, creating and removing companies, the currency a company keeps its
books in) and whoever runs a CUSTOMER'S OWN application. Until now the second
person could not correct a typo in their own company's name, because the only
screen that edits `res.company` is Odoo's own Companies list — which edits every
company on the database, every field on it, and belongs to `base.group_system`
(ACCESS P5, Rail C, and it stays exactly as it was).

What a customer actually needs is not that screen. It is the letterhead: the
name, the address, the phone number, the tax and registration numbers and the
logo — the details that print on a payslip, on a statutory filing and on a
letter. That is what this facade opens, and nothing else.

FOUR RULES, AND EACH ONE IS THE ANSWER TO A WAY THIS COULD GO WRONG.

  1. **The caller's company is resolved HERE, from the user record, and is never
     accepted from the browser.** There is no company argument on any method in
     this file. `self.env.user.company_id` is read directly rather than
     `self.env.company`, because the second one is steered by the request's
     `allowed_company_ids` context — a value a forged call controls. A request
     that names another company therefore does not fail so much as have nowhere
     to put the name: there is no parameter for it.

  2. **The editable set is a WHITELIST, written out in full below.** Not a
     blacklist. A blacklist is a list of the fields somebody thought of, and a
     model gains fields — `currency_id`, `parent_id`, `partner_id`, `user_ids`,
     `active` and everything provisioning writes are refused not because they
     are listed as dangerous but because they are not listed as safe.

  3. **A refusal is a sentence, not a stack trace.** Everything raised here is
     a `UserError` or an `AccessError` written in the words on the screen: no
     field names, no model names, no "Odoo".

  4. **The write is `sudo()`, and that is the whole reason the facade exists.**
     `res.company` write belongs to the system administrator in Odoo's own
     ACLs. Rather than widen that ACL — which would open the entire model, every
     company and every field — the permission check happens here, the payload is
     filtered here, and only then does a bounded write run with escalated
     rights. The escalation covers thirteen named fields on exactly one record.

WHAT IS AUDITED, AND WHERE. `res.company` carries no chatter of its own in this
release, so the trail is the product's own append-only audit store
(`biz_audit_trail`): a rule watches the twelve text and relation fields, and the
mixin on `res.company` logs old→new with a FORCED actor on every write —
including a write made from the platform's own Companies screen, which is a
bonus this seam gets for free. The logo is logged from here by hand, because a
picture has no readable old value and the generic display would put a megabyte
of base64 in a column meant for a sentence.
"""
import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import format_datetime

_logger = logging.getLogger(__name__)

#: The permission that means "this person runs the platform, not a tenant".
SYSTEM_GROUP = 'base.group_system'
#: The permission that means "this person may correct their own company".
EDITOR_GROUP = 'pb_settings.group_company_editor'

# =============================================================================
# THE WHITELIST. THIS TUPLE IS THE RULE — there is no second list anywhere that
# can disagree with it, and everything below (the payload, the refusal, the
# audit rule and the tests) is derived from it.
#
#   (field, kind, the words a person would use for it)
#
# `kind` is what the value is allowed to BE:
#   text    a string, trimmed, capped, or emptied
#   m2o     an id of a specific model, which must exist
#   image   base64 of a picture, which must decode into one
#
# WHAT IS DELIBERATELY ABSENT, and why each one:
#   currency_id           what the books are kept in. Changing it after a single
#                         payslip exists re-prices history. Platform's.
#   parent_id / child_ids where a company sits in a group of companies. Company
#                         structure is the platform's, per the owner's ruling.
#   partner_id            the contact record this company IS. Re-pointing it
#                         would silently hand the company somebody else's
#                         address, bank accounts and history.
#   user_ids / active     who may enter this company, and whether it exists.
#   resource_calendar_id  the working-hours calendar payroll counts against.
#   Everything provisioning writes, and everything else on the model. A field
#   added to `res.company` by a future release is refused by default, which is
#   the direction a whitelist is chosen for.
# =============================================================================
FIELD_SPECS = (
    ('name',             'text',  'the company name'),
    ('street',           'text',  'the street'),
    ('street2',          'text',  'the second address line'),
    ('city',             'text',  'the city'),
    ('zip',              'text',  'the post code'),
    ('state_id',         'm2o',   'the state or province'),
    ('country_id',       'm2o',   'the country'),
    ('phone',            'text',  'the phone number'),
    ('email',            'text',  'the email address'),
    ('website',          'text',  'the website'),
    ('vat',              'text',  'the tax number'),
    ('company_registry', 'text',  'the registration number'),
    ('logo',             'image', 'the logo'),
)

#: `{field: kind}` and `{field: plain words}` — built from the one tuple above.
EDITABLE_KINDS = {f: kind for f, kind, _label in FIELD_SPECS}
EDITABLE_WORDS = {f: label for f, _kind, label in FIELD_SPECS}
#: The order the surface draws them in, and the order a refusal names them in.
EDITABLE_FIELDS = tuple(f for f, _k, _l in FIELD_SPECS)
#: What the audit rule watches: everything but the picture (see the header).
AUDITED_FIELDS = tuple(f for f in EDITABLE_FIELDS if EDITABLE_KINDS[f] != 'image')

#: Which model an `m2o` field must point into.
M2O_MODELS = {'state_id': 'res.country.state', 'country_id': 'res.country'}

# The words to use when a refusal happens to be about a field somebody might
# genuinely have expected to edit. Anything not named here gets the general
# sentence rather than having its technical name echoed back at a person.
REFUSAL_WORDS = {
    'currency_id': "the currency this company keeps its books in",
    'parent_id': "which company this one sits under",
    'child_ids': "the companies underneath this one",
    'partner_id': "the contact record behind this company",
    'user_ids': "who is allowed into this company",
    'active': "whether this company is switched on",
    'id': "which company this page is about",
    'company_id': "which company this page is about",
    'company': "which company this page is about",
    'sequence': "the order companies are listed in",
    'resource_calendar_id': "the working-hours calendar",
    'paperformat_id': "the paper size reports print on",
    'external_report_layout_id': "the document template",
    'report_header': "the tagline printed on reports",
    'report_footer': "the footer printed on reports",
    'account_no': "the bank account",
    'bank_ids': "the bank accounts",
}

#: A trimmed text value is capped rather than refused — a caller controls the
#: length, and a name is a name.
_MAX_TEXT = 256
_MAX_URL = 512
#: About 4 MB of picture. Odoo resizes what it stores; this is the bound on what
#: a single call may hand us.
_MAX_LOGO_B64 = 6 * 1024 * 1024
#: How many past changes the surface shows.
_HISTORY = 8


class PbCompanyProfile(models.AbstractModel):
    _name = 'pb.company.profile'
    _description = 'Your company — the details a customer may correct themselves'

    # ------------------------------------------------------------------ guard
    def _may_edit(self):
        """Is the reader allowed on this surface at all?

        Two ways in and no third: the permission written for this surface, or
        the system administrator permission, which sees everything everywhere
        by definition. A plain internal user holds neither and is refused, both
        here and — because the Settings hub asks the server who may see which
        category — is never offered the door in the first place.
        """
        user = self.env.user
        return user.has_group(EDITOR_GROUP) or user.has_group(SYSTEM_GROUP)

    def _guard(self):
        if not self._may_edit():
            raise AccessError(_(
                "Your company details can only be changed by somebody who "
                "administers this application. Ask whoever gives out roles "
                "here to give you the one that covers your company's own "
                "details."))

    def _company(self):
        """The caller's OWN company, resolved here and never passed in.

        `self.env.user.company_id` on purpose, not `self.env.company`. The
        second one reads `allowed_company_ids` out of the request context,
        which is a value the browser sends — so on a database with more than
        one company a forged call could aim the write at a company the user
        merely has access to. The user record's own company cannot be steered
        that way, and no method in this file takes a company argument, so
        there is nothing for a forged id to attach itself to.
        """
        company = self.env.user.company_id
        if not company:
            # Cannot happen through the product; a database in this state
            # deserves a sentence rather than a traceback.
            raise UserError(_(
                "Your account is not attached to a company yet, so there are "
                "no company details to show. Ask whoever set your account up."))
        return company.sudo()

    # ------------------------------------------------------------------- read
    @api.model
    def profile(self):
        """Everything the surface draws, in one call."""
        self._guard()
        company = self._company()
        return {
            'is_system': self.env.user.has_group(SYSTEM_GROUP),
            'company': self._values(company),
            # `unique` is what makes the browser fetch the picture again after
            # it has been replaced; without it the old logo sits in the cache
            # and the save looks as if it did nothing.
            'logo_url': '/web/image/res.company/%s/logo?unique=%s' % (
                company.id,
                int((company.write_date or fields.Datetime.now()).timestamp())),
            'has_logo': bool(company.logo),
            'labels': self._labels(company),
            'fixed': self._fixed(company),
            'countries': self._countries(),
            'states': self._states(company.country_id.id),
            'history': self._history(company),
        }

    def _values(self, company):
        """The whitelisted fields, and only those — the payload cannot leak a
        field the surface is not allowed to change."""
        out = {}
        for field in EDITABLE_FIELDS:
            if EDITABLE_KINDS[field] == 'image':
                continue                    # sent as a URL, never as bytes
            value = company[field]
            if EDITABLE_KINDS[field] == 'm2o':
                out[field] = value.id or False
                out[field + '_name'] = value.display_name or ''
            else:
                out[field] = value or ''
        return out

    def _labels(self, company):
        """The words this country uses for its own numbers.

        Vietnam, Singapore and India do not call the same thing by the same
        name, and Odoo already knows: `res.country.vat_label` carries it, and
        the company's contact record carries the registration-number example.
        Using them means the field is labelled the way the person filling it in
        expects, rather than the way the database happens to spell it.
        """
        country = company.country_id
        return {
            'vat': country.vat_label or _("Tax number"),
            'company_registry': _("Registration number"),
            'registry_hint': company.company_registry_placeholder or '',
            'currency': company.currency_id.name or '',
            'country': country.display_name or '',
        }

    def _fixed(self, company):
        """The honest half of the page: what this surface will NOT change.

        A settings screen that silently omits things is one people ask about
        twice. Naming them, with who to ask, is what makes the whitelist read
        as a decision rather than as a gap.
        """
        return [
            {'label': _("Currency"),
             'value': company.currency_id.name or '',
             'note': _("Set when this account was created. Changing it would "
                       "re-price every payslip already issued.")},
            {'label': _("Web address"),
             'value': '',
             'note': _("The address you sign in at, and its security "
                       "certificate, are looked after for you.")},
            {'label': _("Companies"),
             'value': '',
             'note': _("Adding, removing or re-grouping companies is done for "
                       "you — ask whoever looks after this service.")},
        ]

    @api.model
    def states(self, country_id):
        """The states or provinces of one country, for the picker.

        A separate call rather than shipping every state on the planet with the
        page: there are thousands, and all but a handful are noise.
        """
        self._guard()
        return self._states(country_id)

    def _states(self, country_id):
        try:
            country_id = int(country_id or 0)
        except (TypeError, ValueError):
            return []
        if not country_id:
            return []
        states = self.env['res.country.state'].sudo().search(
            [('country_id', '=', country_id)], order='name')
        return [{'id': s.id, 'name': s.name} for s in states]

    def _countries(self):
        countries = self.env['res.country'].sudo().search([], order='name')
        return [{'id': c.id, 'name': c.name} for c in countries]

    def _history(self, company):
        """Who changed what, and when — read back out of the audit trail.

        Shown ON the surface rather than left in a console somebody has to know
        about. It is also the proof that the trail is being written: a change
        made here appears at the top of the page a second later.
        """
        if 'biz.audit.entry' not in self.env:
            return []
        rows = self.env['biz.audit.entry'].sudo().search(
            [('model_name', '=', 'res.company'),
             ('res_id', '=', company.id),
             ('field_name', 'in', list(EDITABLE_FIELDS))],
            limit=_HISTORY)
        return [{
            'who': row.user_id.name or _("somebody"),
            'when': format_datetime(self.env, row.stamp),
            'what': EDITABLE_WORDS.get(row.field_name, row.field_label or ''),
            'from': row.old_value or '',
            'to': row.new_value or '',
        } for row in rows]

    # ------------------------------------------------------------------ write
    @api.model
    def save(self, values):
        """Write the whitelisted fields of the caller's own company.

        THE ONLY ARGUMENT IS THE VALUES. There is no company id, and adding one
        later would be the change that breaks rule 1 — say so here so that the
        next person to want one reads this line first.
        """
        self._guard()
        if not isinstance(values, dict):
            raise UserError(_("Nothing was sent to save."))
        company = self._company()
        clean = self._clean(values, company)
        if not clean:
            raise UserError(_("Nothing had changed, so nothing was saved."))

        logo_before = bool(company.logo)
        company.write(clean)
        if 'logo' in clean:
            self._log_logo(company, logo_before)

        changed = [EDITABLE_WORDS[f] for f in EDITABLE_FIELDS if f in clean]
        return {
            'saved': True,
            'sentence': self._sentence(changed),
            'profile': self.profile(),
        }

    def _sentence(self, changed):
        """"Saved — the company name and the tax number are updated." """
        if not changed:
            return _("Saved.")
        if len(changed) == 1:
            return _("Saved — %s is updated.") % changed[0]
        return _("Saved — %(most)s and %(last)s are updated.") % {
            'most': ', '.join(changed[:-1]), 'last': changed[-1]}

    # --------------------------------------------------------------- cleaning
    def _clean(self, values, company):
        """Refuse anything not on the whitelist; coerce what is.

        Two passes on purpose. EVERY refusal is decided before ANY value is
        coerced, so a call carrying one blocked field and twelve good ones
        writes nothing at all — a half-applied save is the thing a person
        cannot tell from a working one.
        """
        blocked = [k for k in values if k not in EDITABLE_KINDS]
        if blocked:
            raise UserError(self._refusal(blocked))

        clean = {}
        for field, raw in values.items():
            kind = EDITABLE_KINDS[field]
            if kind == 'text':
                value = self._text(field, raw)
            elif kind == 'm2o':
                value = self._m2o(field, raw)
            else:
                value = self._image(field, raw)
            if self._same(company, field, value):
                continue
            clean[field] = value

        if clean:
            self._check_state(clean, company)
        return clean

    def _refusal(self, blocked):
        """A sentence, naming what was refused in the words on the screen.

        A field somebody might genuinely have expected to change is named
        plainly. Anything else is NOT echoed back — a made-up name in an error
        message is a made-up name rendered on a page, and the person reading it
        gets nothing from seeing it anyway.
        """
        named = [REFUSAL_WORDS[k] for k in blocked if k in REFUSAL_WORDS]
        head = _(
            "This page changes your company's name, address, contact details, "
            "tax and registration numbers and logo. It changes nothing else "
            "about your company.")
        if not named:
            return head
        if len(named) == 1:
            return head + ' ' + (_("It cannot change %s.") % named[0])
        return head + ' ' + (_("It cannot change %(most)s or %(last)s.") % {
            'most': ', '.join(named[:-1]), 'last': named[-1]})

    def _text(self, field, raw):
        if raw in (None, False):
            return False
        if not isinstance(raw, str):
            raise UserError(_("%s must be written as text.")
                            % EDITABLE_WORDS[field].capitalize())
        value = raw.strip()
        if not value:
            # A company with no name is a company nobody can name on a
            # payslip, and the record refuses it anyway — say so in words
            # rather than letting the database phrase it.
            if field == 'name':
                raise UserError(_("A company has to have a name."))
            return False
        cap = _MAX_URL if field == 'website' else _MAX_TEXT
        value = value[:cap]
        if field == 'email' and ('@' not in value or ' ' in value):
            raise UserError(_(
                "That does not look like an email address. It needs an @ in "
                "it and no spaces."))
        return value

    def _m2o(self, field, raw):
        if raw in (None, False, '', 0, '0'):
            return False
        try:
            rec_id = int(raw)
        except (TypeError, ValueError):
            raise UserError(_("Pick %s from the list.") % EDITABLE_WORDS[field])
        record = self.env[M2O_MODELS[field]].sudo().browse(rec_id).exists()
        if not record:
            raise UserError(_("Pick %s from the list.") % EDITABLE_WORDS[field])
        return record.id

    def _image(self, field, raw):
        if raw in (None, False, ''):
            return False
        if not isinstance(raw, str):
            raise UserError(_("The logo has to be a picture file."))
        if len(raw) > _MAX_LOGO_B64:
            raise UserError(_(
                "That picture is too big. Please use one under 4 MB."))
        try:
            base64.b64decode(raw, validate=True)
        except Exception:                                   # noqa: BLE001
            raise UserError(_("That file is not a picture we can read."))
        return raw

    def _same(self, company, field, value):
        """Is this value already what the record holds?

        Dropping unchanged fields keeps the audit trail free of "changed the
        city from Ho Chi Minh City to Ho Chi Minh City", and makes the "nothing
        had changed" answer honest rather than a guess made in the browser.
        """
        current = company[field]
        if EDITABLE_KINDS[field] == 'm2o':
            return (current.id or False) == (value or False)
        if EDITABLE_KINDS[field] == 'image':
            current = current or False
            if isinstance(current, bytes):
                current = current.decode('ascii', 'ignore')
            return current == (value or False)
        return (current or False) == (value or False)

    def _check_state(self, clean, company):
        """A state has to be in the country it is filed under."""
        country_id = clean.get('country_id', company.country_id.id or False)
        state_id = clean.get('state_id', company.state_id.id or False)
        if not state_id:
            return
        state = self.env['res.country.state'].sudo().browse(state_id)
        if country_id and state.country_id.id != country_id:
            raise UserError(_(
                "%(state)s is not in %(country)s. Pick the country first, then "
                "the state or province.") % {
                    'state': state.display_name,
                    'country': self.env['res.country'].sudo().browse(
                        country_id).display_name})
        if not country_id:
            raise UserError(_(
                "Pick the country before the state or province."))

    # ------------------------------------------------------------------ audit
    def _log_logo(self, company, had_one):
        """One readable line for the picture.

        The generic audit reads a field's value and writes it down; for a
        picture that is a megabyte of encoded bytes in a column meant for a
        sentence, so the logo is left out of the watched list and logged here
        in words instead. Wrapped, because a trail that fails must never take
        a save down with it — the same rule the generic mixin follows.
        """
        if 'biz.audit.entry' not in self.env:
            return
        has_one = bool(company.logo)
        if had_one and has_one:
            old, new = _("a picture"), _("a new picture")
        elif has_one:
            old, new = _("none"), _("a picture")
        else:
            old, new = _("a picture"), _("none")
        try:
            with self.env.cr.savepoint():
                self.env['biz.audit.entry'].sudo().create({
                    'model_name': 'res.company',
                    'res_id': company.id,
                    'res_display': (company.display_name or '')[:512],
                    'field_name': 'logo',
                    'field_label': _("Logo"),
                    'old_value': old,
                    'new_value': new,
                    'company_id': company.id,
                })
        except Exception:                                   # noqa: BLE001
            _logger.exception(
                "pb_settings: could not write the audit line for the logo")
