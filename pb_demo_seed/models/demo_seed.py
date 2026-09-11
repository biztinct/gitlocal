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
"""

import logging

from odoo import _, api, fields, models
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
        report = self.load_demo()
        return self._notify(_("Demo data loaded"), report)

    def load_demo(self):
        """Build the world. Returns a short human summary."""
        self.ensure_one()
        from ..seeds import PROFILES
        spec = PROFILES.get(self.profile)
        if not spec:
            raise UserError(_("There is no demo world called '%s'.", self.profile))

        # ONE DEMO WORLD AT A TIME, PER COMPANY.
        #
        # Not a policy — a fact the database enforces and this would otherwise
        # discover half way through. Several of the records a world contains are
        # unique by name (a supplier is, for one), so a second world lands on the
        # first one's suppliers and stops with a constraint error, leaving a
        # partly-built demo and a register that does not describe it. Saying so
        # before anything is created is the difference between a sentence and a
        # mess.
        other = self.search([
            ('id', '!=', self.id), ('state', '=', 'loaded'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
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

    # ------------------------------------------------------------------
    #  Remove
    # ------------------------------------------------------------------
    def action_remove(self):
        self.ensure_one()
        if self.state != 'loaded':
            raise UserError(_("There is no demo data loaded to remove."))
        removed, blocked = self.remove_demo()
        if blocked:
            return self._notify(
                _("Demo data mostly removed"),
                _("%(removed)s records were removed. %(blocked)s could not be, "
                  "because something else now refers to them:\n%(list)s",
                  removed=removed, blocked=len(blocked),
                  list='\n'.join('• %s' % b for b in blocked[:10])),
                kind='warning')
        return self._notify(
            _("Demo data removed"),
            _("%s records were removed. Nothing was left behind.", removed))

    def remove_demo(self):
        """Walk the register backwards and unlink. Returns `(removed, blocked)`.

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
        removed, blocked = 0, []
        self._release_before_removal()
        rows = self.record_ids.sorted(key=lambda r: (r.sequence, r.id),
                                      reverse=True)
        for row in rows:
            if row.model_name in PROTECTED_MODELS:
                _logger.warning(
                    "pb_demo_seed: refusing to remove a %s; the register "
                    "should never have held one.", row.model_name)
                continue
            record = row._record()
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
        self.record_ids.filtered(lambda r: not r._record().exists()).unlink()
        if not self.record_ids:
            self.sudo().write({'state': 'empty', 'loaded_on': False,
                               'loaded_by': False, 'summary': False})
        return removed, blocked

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
        self._sequence = 0
        self._late = 0
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
        """
        for one in record:
            if (one._name, one.id) in self._seen:
                continue
            self._seen.add((one._name, one.id))
            # A row may already be here from a load whose removal was blocked —
            # a pay run holding an employee down, say. Registering it twice
            # would make the register describe one record as two.
            if self.env['pb.demo.record'].sudo().search_count([
                    ('seed_id', '=', self.seed.id),
                    ('model_name', '=', one._name),
                    ('res_id', '=', one.id)]):
                continue
            if last:
                self._late -= 1
                sequence = self._late
            else:
                self._sequence += 1
                sequence = self._sequence
            self.env['pb.demo.record'].sudo().create({
                'seed_id': self.seed.id,
                'sequence': sequence,
                'model_name': one._name,
                'res_id': one.id,
                'label': label or self._label(one),
            })
            self.registered.append((one._name, one.id))
            self._counts[one._name] = self._counts.get(one._name, 0) + 1
        return record

    def _label(self, record):
        try:
            return (record.display_name or '')[:120] or record._name
        except Exception:                          # noqa: BLE001
            return record._name

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
