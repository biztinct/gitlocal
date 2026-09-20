# -*- coding: utf-8 -*-
"""Load a demo world, and be able to take it out again.

THE ONE IDEA IN THIS FILE: a remove must never have to GUESS what a load made.

The tempting shortcut is to name everything "Demo …" and delete by prefix. It
works until the day somebody has a real supplier called Demo Logistics, or until
a seeded record's name is edited during a demo, or until a story needs a record
whose name is a date. Prefix matching is a rule about SPELLING pretending to be
a rule about ORIGIN.

So every record is written into a register at the moment it is created, with the
order it was created in. Removing walks that register backwards — children
before parents, payslips before people — and unlinks exactly those rows. A
record that has already gone (a cascade took it) is a no-op, not an error. A
record something else now depends on is reported by name rather than silently
skipped, because "it says it removed everything and a laptop is still assigned"
is the worst of the possible outcomes.

THE PROFILE IS THE DATA, THIS IS THE MACHINERY. What gets built lives in
`pb_demo_seed/seeds/`; this file knows how to run one, register what it made,
and undo it. A second tenant is a second profile.

AND THE PRODUCT MAKES DEMO RECORDS TOO. A phase testing a new screen creates a
hiring request, three candidates and an offer — real records, made by the real
code, which is the only way to prove the screen works. Those are demo data by
every test except who typed them, and the register is the right place for them.
`register()` is the public door for that: any module can hand its fixtures over
without depending on this one::

    seed = self.env.get('pb.demo.seed')
    if seed is not None:
        seed.register(records, "What these are")

They land on a seed row of their own (profile `adopted`, `programme_seed()`),
beside — never instead of — a world a profile built.
"""

import logging

from odoo import _, api, fields, models

from odoo.addons.pb_hr_payroll_formula.models.demo_approval import (
    DEMO_WRITE, is_demo_db,
)
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Models the remove will refuse to touch however it got into the register.
#:
#: Nothing in any profile creates these. The guard exists because the register
#: is the only thing standing between "remove the demo" and "remove the
#: company", and a guard that is never needed costs one comparison.
PROTECTED_MODELS = frozenset((
    'res.company', 'res.users', 'res.groups', 'ir.module.module',
    'ir.model', 'ir.model.fields', 'ir.ui.view', 'ir.actions.act_window',
    'hr.formula.config', 'hr.formula.rule',
))

#: The one protected model the register may hold — and it is SWITCHED OFF
#: rather than deleted.
#:
#: A demo login is demo data: it was made for a demo, it is named for one, and
#: leaving it behind is leaving a way into the database nobody owns. But a
#: login is also the name on every approval, every chatter line and every
#: audit row it ever touched, and deleting it would either take those with it
#: or leave them pointing at nothing. Switching it off ends the access, which
#: is the part that matters, and keeps the history readable, which is the part
#: somebody may still need.
ARCHIVE_INSTEAD_OF_DELETE = frozenset(('res.users',))

#: The register every record the PRODUCT made for a demo is written into.
#:
#: One row per company, found by this name. The name is on the screen, so it
#: says what it is in the words the panel beside it uses.
PROGRAMME_SEED_NAME = 'DEMO HR programme data'


class PbDemoRecord(models.Model):
    """One row of the register: something a load made, and when it made it."""
    _name = 'pb.demo.record'
    _description = 'Demo Data Register'
    _order = 'sequence desc, id desc'
    _rec_name = 'label'

    seed_id = fields.Many2one(
        'pb.demo.seed', string='Demo data', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(
        string='Made', required=True, index=True,
        help="The order it was created in. Removal walks these backwards.")
    model_name = fields.Char(string='Kind', required=True, index=True)
    res_id = fields.Integer(string='Record', required=True, index=True)
    label = fields.Char(string='What it is')
    model_label = fields.Char(
        string='Kind', compute='_compute_model_label')
    gone = fields.Boolean(
        string='No longer there', compute='_compute_gone',
        help="The record has already been removed, usually by something it "
             "belonged to being removed first.")

    @api.depends('model_name')
    def _compute_model_label(self):
        names = {m.model: m.name for m in self.env['ir.model'].sudo().search(
            [('model', 'in', list(set(self.mapped('model_name'))))])}
        for row in self:
            row.model_label = names.get(row.model_name) or row.model_name

    @api.depends('model_name', 'res_id')
    def _compute_gone(self):
        for row in self:
            row.gone = not row._record().exists()

    def _record(self):
        """The live record this row points at, or an empty recordset."""
        self.ensure_one()
        model = self.env.get(self.model_name)
        if model is None:
            return self.env['pb.demo.record'].browse()
        return model.sudo().with_context(active_test=False).browse(self.res_id)


class PbDemoSeed(models.Model):
    """One demo world: load it, look at what it made, take it out."""
    _name = 'pb.demo.seed'
    _description = 'Demo Data'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, default='Demo data')
    profile = fields.Selection(
        selection='_selection_profile', string='World', required=True,
        default='rize_vn',
        help="Which demo world to build. Each one is a different set of "
             "people, teams and stories.")
    state = fields.Selection([
        ('empty', 'Not loaded'),
        ('loaded', 'Loaded'),
    ], string='Status', default='empty', required=True, readonly=True)
    loaded_on = fields.Datetime(string='Loaded on', readonly=True)
    loaded_by = fields.Many2one('res.users', string='Loaded by', readonly=True)
    record_ids = fields.One2many(
        'pb.demo.record', 'seed_id', string='What it made')
    record_count = fields.Integer(
        string='Records', compute='_compute_record_count')
    summary = fields.Text(string='What was built', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
        help="The demo people and their records are created in this company.")

    @api.model
    def _selection_profile(self):
        from ..seeds import PROFILES
        return [(key, spec['label']) for key, spec in PROFILES.items()]

    # ------------------------------------------------------------------
    #  The register, as a door other modules can use
    # ------------------------------------------------------------------
    @api.model
    def programme_seed(self):
        """The panel that holds records the product made, found or created.

        Profile `adopted`, because nothing here was BUILT by a profile: the
        records already existed and this row adopts them. It is created
        `loaded` for the same reason — there is no load to press, and a panel
        that offers one over a register full of real records is an invitation
        to a mistake.
        """
        company = self._programme_company()
        seed = self.sudo().search([
            ('name', '=', PROGRAMME_SEED_NAME),
            ('company_id', '=', company.id),
        ], limit=1)
        if seed:
            return seed
        return self.sudo().create({
            'name': PROGRAMME_SEED_NAME,
            'profile': 'adopted',
            'state': 'loaded',
            'loaded_on': fields.Datetime.now(),
            'loaded_by': self.env.user.id,
            'company_id': company.id,
        })

    @api.model
    def _programme_company(self):
        """The company demo records belong to.

        THE COMPANY WITH THE MOST PEOPLE IN IT, which is the operating company
        by definition and needs nobody to configure it.

        Not `search([], limit=1)`, which is the lowest id — on a database that
        has been through a few years of setup that is the empty shell the
        first install left, and a row stamped with it is hidden by the company
        rule from everybody who works in the real company. And not the
        session's own company either, however tempting: an administrator's own
        employee record sits in that same empty shell (R79), so a demo
        register created by an administrator would land there while every
        record on it lives somewhere else.
        """
        counts = dict(self.env['hr.employee'].sudo().with_context(
            active_test=False)._read_group([], ['company_id'], ['__count']))
        if counts:
            return max(counts, key=lambda company: counts[company])
        return self.env.company

    @api.model
    def register_ids(self, model_name, ids, label=None, last=False):
        """The same door, for a caller that only has IDS.

        WHY THIS EXISTS (ledger R176). `register()` takes a RECORDSET, and a
        recordset does not survive JSON-RPC: it arrives as a plain integer and
        the first `records._name` dies with *'int' object has no attribute
        '_name'*. So everything a browser session or a validation script
        creates had to be registered afterwards from inside the server, which
        is exactly the step somebody forgets — and a demo record that is not
        on the register is a demo record the Remove button leaves behind.

        It is a thin door and deliberately so: the browse happens here and
        every rule about WHAT may be registered stays in `_register_row`,
        which is still the only place a register row is written.
        """
        model = self.env.get(model_name)
        if model is None:
            _logger.warning("pb_demo_seed: there is no %s on this database",
                            model_name)
            return 0
        wanted = [int(one) for one in (ids or []) if one]
        if not wanted:
            return 0
        records = model.sudo().with_context(active_test=False).browse(
            wanted).exists()
        return self.register(records, label=label, last=last)

    @api.model
    def register(self, records, label=None, last=False):
        """Put records the product made onto the programme register.

        THE CALLER MUST NOT DEPEND ON THIS MODULE. Demo data is optional on a
        tenant and this module is not installed everywhere, so every caller
        asks first and carries on if the answer is no::

            seed = self.env.get('pb.demo.seed')
            if seed is not None:
                seed.register(records, "Three demo candidates")

        `last=True` puts them below everything else, so the removal reaches
        them at the END of its backwards walk — for the records that are made
        as a side effect of what depends on them (an employee's private
        contact is the one that keeps coming up).

        Returns how many rows were added. Registering the same record twice is
        not an error and adds nothing: a fixture that runs again is a fixture,
        not a second record.
        """
        if not records:
            return 0
        seed = self.programme_seed()
        added = seed._register_records(records, label=label, last=last)
        if added:
            seed.sudo().write({'summary': seed.summarise_register()})
        _logger.info(
            "pb_demo_seed: %s of %s %s registered as '%s'",
            added, len(records), getattr(records, '_name', 'record'),
            label or 'demo data')
        return added

    def _register_records(self, records, label=None, last=False):
        """NOT `_register`: that name belongs to the ORM.

        `_register` is the boolean every model class carries to say whether it
        should go into the registry, so a method of that name is shadowed by
        `True` and every call dies with `TypeError: 'bool' object is not
        callable` — from inside the model, with a traceback that points at the
        caller rather than at the clash.
        """
        self.ensure_one()
        Row = self.env['pb.demo.record'].sudo()
        top = Row.search([('seed_id', '=', self.id)],
                         order='sequence desc', limit=1).sequence or 0
        bottom = Row.search([('seed_id', '=', self.id)],
                            order='sequence asc', limit=1).sequence or 0
        added = 0
        for one in records:
            if last:
                bottom -= 1
                sequence = bottom
            else:
                top += 1
                sequence = top
            if self._register_row(one, sequence, label=label):
                added += 1
            elif last:
                bottom += 1
            else:
                top -= 1
        return added

    def _register_row(self, record, sequence, label=None):
        """THE ONLY PLACE A REGISTER ROW IS WRITTEN.

        Both doors come here — the one a profile's builder uses while it is
        creating a world, and the one another module uses to hand over
        records it made itself. Two writers would be two sets of rules about
        what may go on the register, and the day they disagree is the day the
        removal takes out something it should not have.
        """
        self.ensure_one()
        if not self._may_register(record._name):
            _logger.warning(
                "pb_demo_seed: refusing to register a %s; the removal must "
                "never be handed one.", record._name)
            return self.env['pb.demo.record'].browse()
        if self._registered_already(record):
            return self.env['pb.demo.record'].browse()
        return self.env['pb.demo.record'].sudo().create({
            'seed_id': self.id,
            'sequence': sequence,
            'model_name': record._name,
            'res_id': record.id,
            'label': label or self._row_label(record),
        })

    @api.model
    def _may_register(self, model_name):
        """Is this a kind of record the register is allowed to hold?"""
        return (model_name not in PROTECTED_MODELS
                or model_name in ARCHIVE_INSTEAD_OF_DELETE)

    def _registered_already(self, record):
        """A row may already be here from a load whose removal was blocked."""
        self.ensure_one()
        return bool(self.env['pb.demo.record'].sudo().search_count([
            ('seed_id', '=', self.id),
            ('model_name', '=', record._name),
            ('res_id', '=', record.id),
        ]))

    def summarise_register(self):
        """What is on this register, in the words the screens use.

        "119 × Journey Step", never "119 × pb.journey.task": the panel is read
        by whoever is about to press Remove, and a list of model names tells
        them nothing about what they would lose.
        """
        self.ensure_one()
        counts = dict(self.env['pb.demo.record'].sudo()._read_group(
            [('seed_id', '=', self.id)], ['model_name'], ['__count']))
        names = {m.model: m.name for m in self.env['ir.model'].sudo().search(
            [('model', 'in', list(counts))])}
        return '\n'.join(
            '%s × %s' % (count, names.get(model_name, model_name))
            for model_name, count in sorted(counts.items(),
                                            key=lambda kv: -kv[1]))

    @api.model
    def _row_label(self, record):
        try:
            return (record.display_name or '')[:120] or record._name
        except Exception:                          # noqa: BLE001
            return record._name

    @api.depends('record_ids')
    def _compute_record_count(self):
        counts = dict(self.env['pb.demo.record']._read_group(
            [('seed_id', 'in', self.ids)], ['seed_id'], ['__count']))
        for seed in self:
            seed.record_count = counts.get(seed, 0)

    # ------------------------------------------------------------------
    #  Load
    # ------------------------------------------------------------------
    def action_load(self):
        self.ensure_one()
        if self.state == 'loaded':
            raise UserError(_(
                "This demo data is already loaded. Remove it first if you want "
                "to build it again."))
        held = self._demo_proposal('load')
        if held is not None:
            return held
        report = self.load_demo()
        return self._notify(_("Demo data loaded"), report)

    # ------------------------------------------------------------------
    #  Is this a database demo data belongs on?
    # ------------------------------------------------------------------
    def _demo_proposal(self, kind):
        """Write the press down and ask, unless this is a demo database.

        Returns a notification to show, or None for "carry on as before".
        """
        self.ensure_one()
        if self.env.context.get(DEMO_WRITE) \
                or 'pb.demo.proposal' not in self.env:
            return None
        if is_demo_db(self.env):
            return None
        answer = self.env['pb.demo.proposal'].propose(
            kind,
            _("%(what)s · %(name)s",
              what=_('Load demo data') if kind == 'load'
              else _('Remove demo data'), name=self.name or ''),
            payload={'seed_id': self.id},
            snapshot={'state': self.state},
            facts={'records': {'value': self.record_count, 'unit': ''},
                   'is_demo_db': {'value': False, 'unit': ''}},
            target=self,
        ).answer()
        if answer.get('applied'):
            return None
        return self._notify(
            _("Sent for approval"),
            _("This is not a demo database, so somebody has to agree to it "
              "first. It is with %s.",
              answer.get('with_whom') or _('your approver')),
            kind='warning')

    def load_demo(self):
        """Build the world. Returns a short human summary."""
        self.ensure_one()
        from ..seeds import PROFILES
        spec = PROFILES.get(self.profile)
        if not spec:
            raise UserError(_("There is no demo world called '%s'.", self.profile))

        # NOTHING TO BUILD, AND THAT IS THE POINT. An adopted panel holds
        # records that already existed — the product made them while somebody
        # was testing a screen. There is no world to put in, only a list to
        # keep, so "load" means "this panel is in use" and nothing else.
        if not spec['builders']:
            self.sudo().write({
                'state': 'loaded',
                'loaded_on': self.loaded_on or fields.Datetime.now(),
                'loaded_by': self.loaded_by.id or self.env.user.id,
            })
            return self.summary or _(
                "This panel holds records the product made. Nothing was built.")

        # ONE DEMO WORLD AT A TIME, PER COMPANY.
        #
        # Not a policy — a fact the database enforces and this would otherwise
        # discover half way through. Several of the records a world contains are
        # unique by name (a supplier is, for one), so a second world lands on the
        # first one's suppliers and stops with a constraint error, leaving a
        # partly-built demo and a register that does not describe it. Saying so
        # before anything is created is the difference between a sentence and a
        # mess.
        other = self._other_loaded_world()
        if other:
            raise UserError(_(
                "'%(name)s' is already loaded in %(company)s. Remove it before "
                "loading another demo world — two of them share the same "
                "suppliers and the same asset codes.",
                name=other.name, company=self.company_id.display_name))

        context = SeedContext(self)
        for builder in spec['builders']:
            _logger.info("pb_demo_seed: building %s", builder.__module__)
            builder(context)

        summary = context.summary()
        self.sudo().write({
            'state': 'loaded',
            'loaded_on': fields.Datetime.now(),
            'loaded_by': self.env.user.id,
            'summary': summary,
        })
        _logger.info("pb_demo_seed: loaded %s records for %s",
                     len(context.registered), self.profile)
        return summary

    def _other_loaded_world(self):
        """A world already loaded in this company that a second would land on.

        AN ADOPTED PANEL IS NEVER ONE. It builds nothing, so it cannot land on
        anybody's suppliers, and a register of records the product made is the
        normal thing to find beside a built world rather than a rival to it.
        Ignored in both directions: it does not block a world from loading,
        and a loaded world does not stop the product handing records over.
        """
        self.ensure_one()
        return self.search([
            ('id', '!=', self.id), ('state', '=', 'loaded'),
            ('profile', '!=', 'adopted'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    # ------------------------------------------------------------------
    #  Remove
    # ------------------------------------------------------------------
    def action_remove(self):
        self.ensure_one()
        if self.state != 'loaded':
            raise UserError(_("There is no demo data loaded to remove."))
        held = self._demo_proposal('remove')
        if held is not None:
            return held
        removed, switched_off, blocked = self.remove_demo()
        # BRANCH THE WHOLE SENTENCE (R46/R117): "1 login(s)" is a programme
        # writing, and a frame with one word swapped cannot be translated.
        logins = ''
        if switched_off == 1:
            logins = '\n' + _(
                "One login was switched off rather than deleted.")
        elif switched_off:
            logins = '\n' + _(
                "%s logins were switched off rather than deleted.",
                switched_off)
        if blocked:
            return self._notify(
                _("Demo data mostly removed"),
                _("%(removed)s records were removed. %(blocked)s could not be, "
                  "because something else now refers to them:\n%(list)s",
                  removed=removed, blocked=len(blocked),
                  list='\n'.join('• %s' % b for b in blocked[:10])) + logins,
                kind='warning')
        return self._notify(
            _("Demo data removed"),
            _("%s records were removed. Nothing was left behind.",
              removed) + logins)

    def action_preview_remove(self):
        """What Remove would take out, without taking anything out."""
        self.ensure_one()
        preview = self.preview_remove()
        if not preview['total'] and not preview['users']:
            return self._notify(
                _("Nothing to remove"),
                _("Every record on this list has already gone."),
                kind='warning')
        lines = ['%s × %s' % (row['count'], row['label'])
                 for row in preview['per_model'][:12]]
        if len(preview['per_model']) > 12:
            lines.append(_("… and %s more kinds",
                           len(preview['per_model']) - 12))
        if preview['users']:
            lines.append(_("%s would be switched off rather than deleted",
                           ', '.join(preview['users'][:5])))
        if preview['gone']:
            lines.append(_("%s have already gone", preview['gone']))
        return self._notify(
            _("%s records would be removed", preview['total']),
            '\n'.join(lines), kind='warning')

    def preview_remove(self):
        """Count what Remove would take out. Reads only, changes nothing.

        The honest answer to "what exactly does that button do", asked before
        pressing it rather than after. It is also the only safe question on a
        database that is not a demo one.
        """
        self.ensure_one()
        per_model, users, gone = {}, [], 0
        for row in self.record_ids:
            record = row._record()
            if not record.exists():
                gone += 1
                continue
            if row.model_name in ARCHIVE_INSTEAD_OF_DELETE:
                users.append(row.label or record.display_name)
                continue
            per_model[row.model_name] = per_model.get(row.model_name, 0) + 1
        names = {m.model: m.name for m in self.env['ir.model'].sudo().search(
            [('model', 'in', list(per_model))])}
        return {
            'total': sum(per_model.values()),
            'per_model': [
                {'model': model_name,
                 'label': names.get(model_name, model_name),
                 'count': count}
                for model_name, count in sorted(per_model.items(),
                                                key=lambda kv: -kv[1])],
            'users': users,
            'gone': gone,
        }

    def remove_demo(self):
        """Walk the register backwards and unlink.

        Returns `(removed, switched_off, blocked)`.

        BACKWARDS BECAUSE CREATION ORDER IS DEPENDENCY ORDER. A contract is made
        after the employee it belongs to and an asset handover after both, so
        undoing in reverse means nothing is ever asked to delete a record
        somebody still points at — without this file having to know a single
        thing about which model depends on which.

        EACH UNLINK GETS ITS OWN SAVEPOINT. One record that will not go must not
        roll back the two hundred that already did: in PostgreSQL a failed
        statement poisons the whole transaction unless it is fenced.
        """
        self.ensure_one()
        removed, switched_off, blocked = 0, 0, []
        done_rows = self.env['pb.demo.record']
        self._release_before_removal()
        rows = self.record_ids.sorted(key=lambda r: (r.sequence, r.id),
                                      reverse=True)
        for row in rows:
            record = row._record()
            if row.model_name in ARCHIVE_INSTEAD_OF_DELETE:
                # A LOGIN IS SWITCHED OFF, NOT DELETED. Everything it ever
                # approved, wrote or was told about still names it.
                if record.exists() and record.active:
                    try:
                        with self.env.cr.savepoint():
                            record.sudo().write({'active': False})
                        switched_off += 1
                    except Exception as exc:       # noqa: BLE001
                        blocked.append('%s — %s' % (
                            row.label or row.model_name,
                            self._why_blocked(exc)))
                        _logger.info("pb_demo_seed: could not switch off "
                                     "%s(%s): %s",
                                     row.model_name, row.res_id, exc)
                        continue
                done_rows |= row
                continue
            if row.model_name in PROTECTED_MODELS:
                _logger.warning(
                    "pb_demo_seed: refusing to remove a %s; the register "
                    "should never have held one.", row.model_name)
                continue
            if not record.exists():
                continue
            try:
                with self.env.cr.savepoint():
                    record.unlink()
                removed += 1
            except Exception as exc:              # noqa: BLE001
                blocked.append('%s — %s' % (
                    row.label or row.model_name, self._why_blocked(exc)))
                _logger.info("pb_demo_seed: could not remove %s(%s): %s",
                             row.model_name, row.res_id, exc)
        # A SWITCHED-OFF LOGIN'S ROW GOES TOO, because the register's job on
        # it is finished. Leaving it would keep the panel for ever "loaded"
        # over a list on which there is nothing left to do.
        done_rows.unlink()
        self.record_ids.filtered(lambda r: not r._record().exists()).unlink()
        if not self.record_ids:
            self.sudo().write({'state': 'empty', 'loaded_on': False,
                               'loaded_by': False, 'summary': False})
        return removed, switched_off, blocked

    def _release_before_removal(self):
        """Undo the two states that REFUSE to be deleted, before walking.

        Some records are deliberately hard to delete, and rightly so: an asset
        handover that is still open refuses to go, because losing the row would
        lose who has the laptop. That guard is correct and this module is not
        going to argue with it — it hands the laptop back first, which is what
        a person would do, and then the row deletes like any other.

        The alternative would be a force-delete path, and a force-delete path
        in a module whose whole job is bulk deletion is a loaded gun.
        """
        self.ensure_one()

        # An open asset handover refuses to be deleted, because losing the row
        # would lose who has the laptop. Hand it back first, which is what a
        # person would do.
        assignments = self._registered('pb.asset.assignment')
        open_ones = assignments.filtered(lambda a: a.state == 'open')
        if open_ones:
            self._quietly(open_ones.write, {
                'state': 'returned', 'returned_date': fields.Date.today(),
                'condition_in': 'Demo data removed'})

        # A RUNNING CONTRACT holds its EMPLOYEE down — `hr.employee` refuses to
        # be deleted while any contract of theirs is open, which is right, and
        # which the register's reverse walk cannot fix on its own: the contract
        # is deleted first, but only if nothing blocks it, and a contract whose
        # employee is reused across loads can outlive one register. Closing them
        # first costs nothing (they are deleted seconds later) and turns a
        # refusal nobody can act on into no refusal at all.
        contracts = self._registered('hr.contract')
        running = contracts.filtered(lambda c: c.state == 'open')
        if running:
            self._quietly(running.write, {'state': 'close'})

        # An APPROVED time-off record refuses too, for the same kind of reason:
        # somebody has been told they have those days. Both of these take the
        # product's own route back to draft where there is one, because
        # approving and un-approving leave touches balances that a raw state
        # write would leave wrong.
        for model_name in ('hr.leave', 'hr.leave.allocation'):
            records = self._registered(model_name)
            live = records.filtered(lambda r: r.state not in ('draft', 'cancel'))
            for record in live:
                for action in ('action_refuse', 'action_draft', 'action_reset'):
                    method = getattr(record, action, None)
                    if method and self._quietly(method):
                        break
                if record.exists() and record.state not in ('draft', 'cancel'):
                    self._quietly(record.write, {'state': 'draft'})

    #: Why a demo record most often will not go, in words rather than in SQL.
    #:
    #: Each of these is REAL WORK somebody did on top of the demo data, and the
    #: whole reason the remove reports instead of forcing. The first one is the
    #: one that matters: a pay run built on a demo person is the most likely
    #: thing anybody will have made, and "violates foreign key constraint
    #: hr_payslip_employee_id_fkey" is not a sentence that tells them so.
    _BLOCK_REASONS = (
        ('hr_payslip', "a pay run still includes this person — delete or "
                       "cancel that run first"),
        ('hr_contract', "a contract still points at this person"),
        ('hr_leave', "a time-off record still points at this person"),
        ('linked to an employee', "the contact belongs to an employee that is "
                                  "still here"),
        ('still with somebody', "the item is still handed out"),
    )

    @api.model
    def _why_blocked(self, exc):
        text = str(exc).strip().replace('\n', ' ')
        for needle, sentence in self._BLOCK_REASONS:
            if needle in text:
                return sentence
        return text.split('  ')[0][:160]

    def _registered(self, model_name):
        """The live records of one kind that this load made."""
        self.ensure_one()
        ids = self.record_ids.filtered(
            lambda r: r.model_name == model_name).mapped('res_id')
        model = self.env.get(model_name)
        if model is None:
            return self.env['pb.demo.record'].browse()
        return model.sudo().with_context(active_test=False).browse(ids).exists()

    def _quietly(self, method, *args):
        """Run it in a savepoint; a refusal is an answer, not a failure.

        Everything this is used for is an attempt to unlock something before
        deleting it. If the attempt does not work the delete will say so, by
        name, in the report — which is a better place for the news than an
        exception thrown out of a tidy-up step.
        """
        try:
            with self.env.cr.savepoint():
                method(*args)
            return True
        except Exception as exc:                   # noqa: BLE001
            _logger.info("pb_demo_seed: could not prepare a record for "
                         "removal — %s", exc)
            return False

    # ------------------------------------------------------------------
    def action_view_records(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("What the demo data made"),
            'res_model': 'pb.demo.record',
            'view_mode': 'list',
            'domain': [('seed_id', '=', self.id)],
            # R125: a hand-built act_window dict must carry `views`, or the
            # client throws before the screen is ever drawn.
            'views': [[False, 'list']],
            'context': {'search_default_group_by_model': 1},
        }

    def _notify(self, title, message, kind='success'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': kind,
                       'sticky': kind != 'success',
                       'next': {'type': 'ir.actions.act_window_close'}},
        }


class SeedContext:
    """What a builder is handed: a place to create things, and a register.

    NOT AN ODOO MODEL, deliberately. It is scratch state for the length of one
    load — the sequence counter, the shared company, the handful of records the
    later builders need to find again. Putting it on a model would mean either
    storing it (there is nothing to store afterwards) or passing a transient
    around, which is the same object with more ceremony.
    """

    def __init__(self, seed):
        self.seed = seed
        self.env = seed.env
        self.company = seed.company_id
        self.today = fields.Date.context_today(seed)
        self.registered = []
        self._seen = set()
        # CARRY ON FROM WHAT THE REGISTER ALREADY HOLDS. A panel whose last
        # removal was blocked still has rows on it, and starting again at one
        # would interleave this load's records with the leftovers — which is
        # the one thing the order is for.
        Row = seed.env['pb.demo.record'].sudo()
        self._sequence = Row.search([('seed_id', '=', seed.id)],
                                    order='sequence desc', limit=1).sequence or 0
        self._sequence = max(self._sequence, 0)
        self._late = Row.search([('seed_id', '=', seed.id)],
                                order='sequence asc', limit=1).sequence or 0
        self._late = min(self._late, 0)
        self._named = {}
        self._counts = {}

    # -- creating ------------------------------------------------------
    def create(self, model_name, vals, label=None):
        """Create one record and register it in the same breath.

        The two are one operation on purpose. A `create` followed by a separate
        `track` is a `create` that will one day not be tracked, and an
        untracked record is a record the remove leaves behind for ever.
        """
        model = self.env[model_name].sudo()
        if 'company_id' in model._fields and 'company_id' not in vals:
            vals = dict(vals, company_id=self.company.id)
        record = model.with_context(
            tracking_disable=True, mail_create_nolog=True,
            mail_notrack=True, no_reset_password=True).create(vals)
        self.track(record, label=label)
        return record

    def try_create(self, model_name, vals, label=None):
        """Create, and shrug if the record will not be accepted.

        Used ONLY for the parts of the world a demo is nice to have rather than
        built on — a couple of days of leave, mostly. Leave in particular is
        validated against calendars, allocations and public holidays that vary
        per database, and losing two leave records is a fair price for never
        having a load stop half-built on somebody's demo morning.

        A savepoint, because in PostgreSQL a failed statement poisons the
        transaction unless it is fenced.
        """
        try:
            with self.env.cr.savepoint():
                return self.create(model_name, vals, label=label)
        except Exception as exc:                   # noqa: BLE001
            _logger.info("pb_demo_seed: skipped a %s — %s", model_name, exc)
            return self.env[model_name].browse()

    def mark(self, *model_names):
        """The highest id each of these models currently holds.

        Paired with `adopt_since`, it is how a builder says "whatever the
        product creates in the next few lines is mine to clean up" without
        having to know in advance what that will be. An id watermark rather
        than a timestamp because ids are what the register stores and because
        two records created in the same second are indistinguishable by time.
        """
        marks = {}
        for name in model_names:
            last = self.env[name].sudo().with_context(
                active_test=False).search([], order='id desc', limit=1)
            marks[name] = last.id if last else 0
        return marks

    def adopt_since(self, marks, model_name, extra_domain=None, label=None):
        """Register everything of this kind that appeared after the mark."""
        domain = [('id', '>', marks.get(model_name, 0))]
        if extra_domain:
            domain += extra_domain
        return self.adopt(model_name, domain, label=label)

    def adopt(self, model_name, domain, label=None):
        """Register records the PRODUCT made on our behalf.

        Opening a leaving checklist creates four clearances and an exit
        questionnaire; opening a joining checklist creates its steps. We want
        the product to make those — writing them here by hand would produce a
        demo that does not match what a real employee gets — but whatever it
        makes is still ours to clean up. Anything that cascades is harmless to
        register twice over; anything that does not would otherwise be left
        behind, which is the failure this whole module exists to avoid.
        """
        records = self.env[model_name].sudo().with_context(
            active_test=False).search(domain)
        for one in records:
            if (one._name, one.id) in self._seen:
                continue
            self.track(one, label=label)
        return records

    def track(self, record, label=None, last=False):
        """Register a record this load is responsible for.

        `last=True` says "remove this one AFTER everything else", and it exists
        for the one shape creation order cannot express: a record that is made
        as a SIDE EFFECT of the thing that depends on it. Creating an employee
        creates their private contact, so the contact is registered second and
        would be removed first — and Odoo refuses to delete a contact while an
        employee points at it. Giving it a sequence below zero puts it at the
        end of the backwards walk, where it belongs.

        A row may already be here from a load whose removal was blocked — a pay
        run holding an employee down, say — so the WRITER dedups, and it is the
        same writer the public `register()` door uses. Two ways of putting a
        row on the register would be two sets of rules about what may be on it.
        """
        for one in record:
            if (one._name, one.id) in self._seen:
                continue
            self._seen.add((one._name, one.id))
            if last:
                self._late -= 1
                sequence = self._late
            else:
                self._sequence += 1
                sequence = self._sequence
            if not self.seed._register_row(one, sequence, label=label):
                continue
            self.registered.append((one._name, one.id))
            self._counts[one._name] = self._counts.get(one._name, 0) + 1
        return record

    # -- remembering ---------------------------------------------------
    def set(self, key, value):
        self._named[key] = value
        return value

    def get(self, key, default=None):
        return self._named.get(key, default)

    # -- small helpers builders keep needing ---------------------------
    def days(self, offset):
        """A date `offset` days from today. Negative is in the past."""
        from datetime import timedelta
        return self.today + timedelta(days=offset)

    def months(self, offset):
        from dateutil.relativedelta import relativedelta
        return self.today + relativedelta(months=offset)

    def month_start(self, offset=0):
        from dateutil.relativedelta import relativedelta
        return (self.today + relativedelta(months=offset)).replace(day=1)

    def ref(self, xmlid):
        """An xmlid that may not be on this database. Never raises."""
        return self.env.ref(xmlid, raise_if_not_found=False)

    def find_or_create(self, model_name, domain, vals, label=None):
        """Reuse what the database already has; register only what we add.

        A demo must not create a second "Agronomy" department beside the real
        one, and it must not DELETE the real one on the way out. Anything found
        rather than created is deliberately left out of the register.
        """
        existing = self.env[model_name].sudo().with_context(
            active_test=False).search(domain, limit=1)
        if existing:
            return existing
        return self.create(model_name, vals, label=label)

    def summary(self):
        lines = []
        names = {m.model: m.name for m in self.env['ir.model'].sudo().search(
            [('model', 'in', list(self._counts))])}
        for model_name, count in sorted(self._counts.items(),
                                        key=lambda kv: -kv[1]):
            lines.append('%s × %s' % (count, names.get(model_name, model_name)))
        return '\n'.join(lines)
