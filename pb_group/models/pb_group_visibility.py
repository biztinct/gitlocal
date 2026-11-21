# -*- coding: utf-8 -*-
"""`pb.group.visibility` — who sees what, across the whole group.

THE ONE PROMISE THIS FILE MAKES
-------------------------------
**A person with no row here sees exactly what they saw yesterday.** Not
"almost", not "unless": every helper on this model answers "no narrowing" for a
user who has not been given a row, and a test asserts it on every surface. That
is what makes it safe to install on a live payroll database: visibility is a
thing an administrator switches ON for a named person, one at a time, and until
they do the company switcher is still the only boundary there is.

THE FOUR KINDS, in the words on the screen
------------------------------------------
  * **Everything** — the group CFO, the CEO. No narrowing at all.
  * **One country** — country HR. Every company of the group registered in that
    country, and nothing else.
  * **One company** — a payroll officer inside one legal entity.
  * **One division** — a division head. Every row that belongs to their
    division, in whatever company it happens to sit in, and nothing else.

NARROWING ONLY, NEVER WIDENING
------------------------------
Every answer is intersected with `res.users.company_ids` — the companies
somebody has actually been given. A visibility row can only ever take away. So
this model can be edited by an administrator with no risk of it handing out a
company that was never theirs, and a mistake here is always a smaller screen,
never a bigger one.

WHY THE RECORD RULES READ FIELDS AND NOT METHODS
------------------------------------------------
A record rule's `domain_force` is evaluated by `safe_eval` with `user` in scope.
Reading three computed fields off that user — `pb_vis_kind`,
`pb_vis_company_ids`, `pb_vis_division_ids` — is plain attribute access, which
is exactly what every rule in the platform already does, and it keeps the
interesting logic here in Python where it can be read and tested. The fields are
COMPUTED AND NOT STORED: there is nothing to keep in step, nothing to migrate,
and a division that gains a department is honoured on the next read.

WHEN THE SCOPE NO LONGER EXISTS
-------------------------------
A division is archived, a company is switched off, a country is removed. The
honest answer is not "you now see nothing" — that is somebody locked out of
their own job with no sentence to read. It is **"everything they could see
before"**, plus a warning on the administrator's card naming the person and what
went missing. A dead scope must never become a silent lock-out.
"""

import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

#: The four kinds, and the order they read best in.
KINDS = [
    ('all', 'Everything'),
    ('country', 'One country'),
    ('company', 'One company'),
    ('division', 'One division'),
]

MAX_ROWS = 500


class PbGroupVisibility(models.Model):
    _name = 'pb.group.visibility'
    _description = 'Who sees what'
    _inherit = ['mail.thread']
    _order = 'user_id'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        'res.users', string='Person', required=True, ondelete='cascade',
        index=True, tracking=True,
        help="The person this applies to. Somebody with no row here sees "
             "whatever their companies already let them see.")
    kind = fields.Selection(
        selection=KINDS, string='They see', required=True, default='all',
        tracking=True)
    country_id = fields.Many2one(
        'res.country', string='Country', tracking=True,
        help="Used when they see one country.")
    company_id = fields.Many2one(
        'res.company', string='Company', tracking=True,
        help="Used when they see one company.")
    division_id = fields.Many2one(
        'pb.division', string='Division', tracking=True,
        help="Used when they see one division.")
    note = fields.Char(string='Why', help="Optional. Why this person is "
                                          "limited to this.")

    _user_uniq = models.Constraint(
        'unique(user_id)',
        'That person already has a row here. Change the one they have rather '
        'than adding a second.')

    # ------------------------------------------------------------ validation
    @api.constrains('kind', 'country_id', 'company_id', 'division_id')
    def _check_reference(self):
        for row in self:
            if row.kind == 'country' and not row.country_id:
                raise ValidationError(_("Pick the country they see."))
            if row.kind == 'company' and not row.company_id:
                raise ValidationError(_("Pick the company they see."))
            if row.kind == 'division' and not row.division_id:
                raise ValidationError(_("Pick the division they see."))

    # ------------------------------------------------ keeping the cache true
    # `_scope_tuple` is `ormcache`d per user, and a record rule's own domain is
    # cached per user per model on top of that. Both have to go the moment
    # somebody's visibility changes, or the person keeps yesterday's screen for
    # as long as the worker lives.
    def _clear(self):
        self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        rows = super().create(vals_list)
        rows._clear()
        return rows

    def write(self, vals):
        res = super().write(vals)
        self._clear()
        return res

    def unlink(self):
        res = super().unlink()
        self._clear()
        return res

    # =================================================== the scope, in one go
    @tools.ormcache('user_id')
    def _scope_tuple(self, user_id):
        """The structure of somebody's scope, with no words in it.

        Cached per user (the cache is cleared on every write above). The
        SENTENCES are built fresh by `scope_for`, because a cached sentence is
        a sentence frozen in whatever language the first reader happened to
        use.

        Returns `(has_row, kind, ref_id, ref_ok, company_ids, division_ids,
        department_ids)`; the id tuples are only meaningful when the scope
        actually narrows.
        """
        # `who`, never `user` — see GR54 on `scope_note` below. Nothing here
        # calls `_()` today; naming the local `user` anywhere in this file is
        # a trap the next edit walks into.
        who = self.env['res.users'].sudo().browse(int(user_id or 0)).exists()
        if not who:
            return (False, '', 0, True, (), (), ())
        entitled = tuple(sorted(who.company_ids.ids))
        row = self.sudo().search([('user_id', '=', who.id)], limit=1)
        if not row:
            return (False, '', 0, True, entitled, (), ())
        kind = row.kind or 'all'
        if kind == 'all':
            return (True, 'all', 0, True, entitled, (), ())

        allowed = set(entitled)
        Company = self.env['res.company'].sudo().with_context(
            active_test=False)

        if kind == 'company':
            company = row.company_id
            if not company or not company.exists() or not company.active:
                return (True, kind, company.id if company else 0, False,
                        entitled, (), ())
            ids = tuple(sorted({company.id} & allowed))
            return (True, kind, company.id, True, ids, (), ())

        if kind == 'country':
            country = row.country_id
            if not country or not country.exists():
                return (True, kind, country.id if country else 0, False,
                        entitled, (), ())
            # GR20: `res.company.country_id` is NOT STORED on this release, so
            # a domain on it is a hard ValueError, not a slow query. The match
            # happens in Python over the handful of companies in scope.
            code = country.code or ''
            ids = tuple(sorted(
                c.id for c in Company.browse(sorted(allowed)).exists()
                if (c.country_id and (c.country_id.id == country.id
                                      or (code and c.country_id.code == code)))
            ))
            return (True, kind, country.id, True, ids, (), ())

        # division
        division = row.division_id
        if not division or not division.exists() or not division.active:
            return (True, kind, division.id if division else 0, False,
                    entitled, (), ())
        links = self.env['pb.division.link'].sudo().search(
            [('division_id', '=', division.id)])
        dept_ids = set(links.mapped('department_id').ids)
        company_ids = set(links.mapped('company_id').ids) & allowed
        # An attachment at the top of a branch covers everything under it, so
        # the departments a division head sees are the attached ones AND their
        # children — the same walk the counts use.
        if dept_ids:
            children = self.env['hr.department'].sudo().with_context(
                active_test=False).search_read(
                [('company_id', 'in', sorted(company_ids or allowed))],
                ['id', 'parent_path'])
            for dept in children:
                path = (dept['parent_path'] or '').strip('/')
                chain = {int(p) for p in path.split('/') if p}
                if chain & dept_ids:
                    dept_ids.add(dept['id'])
        return (True, 'division', division.id, True,
                tuple(sorted(company_ids)), (division.id,),
                tuple(sorted(dept_ids)))

    # ------------------------------------------------------------ the public
    @api.model
    def _resolve_user(self, who=None):
        if isinstance(who, models.BaseModel):
            return who[:1]
        if isinstance(who, int) and who:
            return self.env['res.users'].sudo().browse(who).exists()
        return self.env.user

    @api.model
    def scope_for(self, who=None):
        """What this person may see, with the sentence that says so.

        Every caller in this programme goes through here. The dictionary is
        rebuilt on each call (WF11: never hand back a cached mutable), and the
        words are built in the READER's language, not the subject's.
        """
        who = self._resolve_user(who)
        if not who:
            return self._blank()
        (has_row, kind, ref_id, ref_ok, company_ids, division_ids,
         department_ids) = self._scope_tuple(who.id)
        restricted = bool(has_row and ref_ok and kind not in ('', 'all'))
        out = {
            'user_id': who.id,
            'user_name': who.name or '',
            'has_row': bool(has_row),
            'kind': kind or 'switcher',
            'restricted': restricted,
            'ref_id': ref_id,
            'ref_ok': bool(ref_ok),
            'company_ids': list(company_ids),
            'division_ids': list(division_ids),
            'department_ids': list(department_ids),
            'warning': '',
        }
        out.update(self._words(who, out))
        return out

    @api.model
    def _blank(self):
        return {
            'user_id': 0, 'user_name': '', 'has_row': False,
            'kind': 'switcher', 'restricted': False, 'ref_id': 0,
            'ref_ok': True, 'company_ids': [], 'division_ids': [],
            'department_ids': [], 'warning': '',
            'kind_label': '', 'ref_name': '', 'sentence': '',
        }

    @api.model
    def _words(self, who, scope):
        """The sentence a person reads, and the name of the thing it names."""
        # GR58 — the four words a reader sees, written here rather than read
        # back out of `fields_get`, whose selection labels come from a cache
        # a translation import in another process does not reach.
        labels = {
            'all': _("Everything"),
            'country': _("One country"),
            'company': _("One company"),
            'division': _("One division"),
        }
        kind = scope['kind']
        name = who.name or _("this person")
        ref_name = ''
        if kind == 'country':
            ref_name = self.env['res.country'].sudo().browse(
                scope['ref_id']).exists().name or ''
        elif kind == 'company':
            ref_name = self.env['res.company'].sudo().with_context(
                active_test=False).browse(
                scope['ref_id']).exists().name or ''
        elif kind == 'division':
            ref_name = self.env['pb.division'].sudo().with_context(
                active_test=False).browse(
                scope['ref_id']).exists().name or ''
        warning = ''
        if not scope['has_row']:
            sentence = _(
                "%(name)s has not been limited, so they see everything their "
                "companies already let them see.", name=name)
        elif not scope['ref_ok']:
            warning = _(
                "What %(name)s was limited to is no longer here, so they can "
                "see everything they could see before. Give them a new one.",
                name=name)
            sentence = warning
        elif kind == 'all':
            sentence = _("%(name)s sees every company in the group.",
                         name=name)
        elif kind == 'country':
            sentence = _(
                "%(name)s sees %(what)s only — %(count)s of the group's "
                "companies.", name=name, what=ref_name or _("that country"),
                count=len(scope['company_ids']))
        elif kind == 'company':
            sentence = _("%(name)s sees %(what)s only.", name=name,
                         what=ref_name or _("that company"))
        else:
            sentence = _("%(name)s sees the %(what)s division only.",
                         name=name, what=ref_name or _("chosen"))
        return {
            'kind_label': labels.get(kind, ''),
            'ref_name': ref_name,
            'sentence': sentence,
            'warning': warning,
        }

    # ------------------------------------------------- what the facades call
    @api.model
    def narrow_companies(self, company_ids, who=None):
        """The companies of `company_ids` this reader may see.

        NO ROW, OR "EVERYTHING" — the list comes back untouched. That is the
        promise at the top of this file, and it is the reason this method is
        safe to call from every facade in the programme.
        """
        ids = [int(c) for c in (company_ids or []) if c]
        scope = self.scope_for(who)
        if not scope['restricted']:
            return ids
        allowed = set(scope['company_ids'])
        return [c for c in ids if c in allowed]

    @api.model
    def visible_division_ids(self, who=None):
        """The divisions this reader is held to. `[]` means every one."""
        scope = self.scope_for(who)
        return list(scope['division_ids']) if scope['restricted'] else []

    @api.model
    def visible_department_ids(self, who=None):
        """The departments this reader is held to. `[]` means every one."""
        scope = self.scope_for(who)
        return list(scope['department_ids']) if scope['restricted'] else []

    @api.model
    def is_restricted(self, who=None):
        return bool(self.scope_for(who)['restricted'])

    @api.model
    def scope_note(self, who=None):
        """One sentence for the top of a narrowed screen, or ''.

        Written in the SECOND person, because the person reading it is the
        person it is about — "You see …", not "Nguyen sees …".

        GR54 — THE PARAMETER IS `who` AND MAY NEVER BE CALLED `user`. The
        platform's own `_()` reads the CALLING FRAME's local variables looking
        for the reader whose language to answer in
        (`odoo/tools/translate.py:517`, `int(frame.f_locals['user'])`), with no
        guard. A method that calls `_()` and happens to hold a local called
        `user` that is `None` therefore dies inside the translator with
        `int() argument must be … not 'NoneType'`, hundreds of lines away from
        anything this file wrote.
        """
        scope = self.scope_for(who)
        if not scope['restricted']:
            return ''
        if scope['kind'] == 'country':
            return _("You are seeing %(what)s only.",
                     what=scope['ref_name'] or _("one country"))
        if scope['kind'] == 'company':
            return _("You are seeing %(what)s only.",
                     what=scope['ref_name'] or _("one company"))
        return _("You are seeing the %(what)s division only.",
                 what=scope['ref_name'] or _("chosen"))

    # ============================================== what the record rules use
    @api.model
    def _rule_company_ids(self, who=None):
        scope = self.scope_for(who)
        return list(scope['company_ids']) if scope['restricted'] else []

    # ============================================================= the writes
    @api.model
    def set_for(self, user_id, kind, ref_id=None, note=None):
        """Give somebody a scope, change it, or take it away.

        `kind` of `''` (or `False`) REMOVES the row, which is how somebody goes
        back to seeing what their companies let them see. One door for all
        three, so the screen never has to decide which call to make.
        """
        # GR54 — `who`, never `user`: `_()` reads a local of that name out of
        # the calling frame and calls `int()` on it.
        who = self.env['res.users'].sudo().browse(int(user_id or 0)).exists()
        if not who:
            raise UserError(_("That person is no longer here."))
        row = self.sudo().search([('user_id', '=', who.id)], limit=1)
        if not kind:
            if row:
                row.unlink()
            return True
        if kind not in dict(KINDS):
            raise UserError(_("Pick what this person should see."))
        payload = {
            'user_id': who.id, 'kind': kind,
            'country_id': False, 'company_id': False, 'division_id': False,
            'note': (note or '').strip()[:200] or False,
        }
        ref = int(ref_id or 0)
        if kind == 'country':
            payload['country_id'] = ref
        elif kind == 'company':
            payload['company_id'] = ref
        elif kind == 'division':
            payload['division_id'] = ref
        if kind != 'all' and not ref:
            raise UserError(_("Pick the one they should see."))
        if row:
            row.write(payload)
        else:
            self.sudo().create(payload)
        return True


class PbGroupScoped(models.AbstractModel):
    """The four lines every GROUP facade needs, in one place.

    A facade inherits this and calls `_visible_companies(...)` wherever it
    already worked out which companies a reader may see. The point of putting
    it here rather than copying five lines into seven modules is that there is
    then exactly ONE definition of "what this person may see", and the "as this
    person" preview on the Group screen is reading the same one.
    """
    _name = 'pb.group.scoped'
    _description = 'Reads that honour who sees what'

    @api.model
    def _visible_companies(self, company_ids):
        """The companies of `company_ids` this reader may see.

        Unchanged for anybody who has not been limited — that is the promise,
        and `test_p7_visibility` asserts it on every surface.
        """
        return self.env['pb.group.visibility'].narrow_companies(company_ids)

    @api.model
    def _visible_divisions(self):
        """The divisions this reader is held to. `[]` means every one."""
        return self.env['pb.group.visibility'].visible_division_ids()

    @api.model
    def _visible_departments(self):
        """The departments this reader is held to. `[]` means every one."""
        return self.env['pb.group.visibility'].visible_department_ids()

    @api.model
    def _visibility_note(self):
        """One sentence for the top of a narrowed screen, or ''."""
        return self.env['pb.group.visibility'].scope_note()


class ResUsersVisibility(models.Model):
    """Three read-only fields the record rules read off the user.

    COMPUTED AND NOT STORED on purpose. There is nothing to keep in step and
    nothing to migrate; a division that gains a department is honoured on the
    next read; and a rule's `domain_force` stays plain attribute access, which
    is what every rule in the platform already does.
    """
    _inherit = 'res.users'

    pb_vis_kind = fields.Char(
        string='Sees', compute='_compute_pb_visibility',
        help="Empty when this person has not been limited to part of the "
             "group.")
    pb_vis_company_ids = fields.Many2many(
        'res.company', string='Companies they see',
        compute='_compute_pb_visibility')
    pb_vis_division_ids = fields.Many2many(
        'pb.division', string='Divisions they see',
        compute='_compute_pb_visibility')

    # The real dependency — the visibility row — lives in another table, and
    # every write to it clears the registry cache above, which invalidates
    # these along with everything else. `company_ids` is named because taking a
    # company away from somebody must narrow this on the same read.
    @api.depends('company_ids')
    def _compute_pb_visibility(self):
        Visibility = self.env['pb.group.visibility'].sudo()
        for who in self:      # GR54: never a local called `user` near `_()`
            scope = Visibility.scope_for(who)
            restricted = scope['restricted']
            who.pb_vis_kind = scope['kind'] if restricted else False
            who.pb_vis_company_ids = [
                (6, 0, scope['company_ids'] if restricted else [])]
            who.pb_vis_division_ids = [
                (6, 0, scope['division_ids'] if restricted else [])]
