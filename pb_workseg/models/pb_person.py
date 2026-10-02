# -*- coding: utf-8 -*-
"""`pb.person` — one human being, however many employments they have.

WHY
---
Until now a head count was a count of employee RECORDS. On one company that is
the same thing as a count of people. Across a group it is not: somebody
transferred from Vietnam to Singapore in March is two employee records, and
every report that counted records counted them twice — for ever, because the
old record is never deleted.

So the identity moves up one level. A person is a record of its own; an
employment (`hr.employee`) points at it. Head count is a count of DISTINCT
persons; full-time equivalents are a sum of shares over employments. Nothing
else about an employee record changes, and a database whose people each have
exactly one employment reads exactly as it did before — which is the whole of
this module's safety story.

BOOTSTRAP
---------
Installing this module gives every active employee a person of their own, one
each. That is deliberately the DULL answer: it is always right, it changes no
number anywhere (one person, one employment, share 1.0), and joining two of
them into one human is a decision a person makes on the "Same person?" review
with the evidence in front of them.

The bootstrap runs as raw SQL rather than through `create()`. Four and a half
thousand `mail.thread` creates cost minutes and produce four and a half
thousand chatter records nobody will ever read; one INSERT … SELECT costs
milliseconds. GR13's ordering is honoured around it: flush, write, invalidate
WITHOUT flushing.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Caps on anything a caller controls — the facade is reachable over JSON-RPC.
MAX_SUGGESTIONS = 200
MAX_MERGE = 50

#: How sure we are, per kind of evidence. Ruling: a national identity number is
#: a statement by a government, an email address is a statement by the person,
#: a name and a birthday is a coincidence that is usually not one.
SCORE_NATIONAL_ID = 1.0
SCORE_TAX_ID = 0.95
SCORE_EMAIL = 0.9
SCORE_NAME_BIRTHDAY = 0.7


def _clean(value):
    """A comparison key: trimmed, folded, punctuation-free."""
    text = (value or '').strip().lower()
    return ''.join(ch for ch in text if ch.isalnum())


class PbPerson(models.Model):
    _name = 'pb.person'
    _description = 'Person'
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(
        string='Name', required=True, tracking=True,
        help="What this person is called. Their employments may each spell it "
             "slightly differently; this is the one the group reads.")
    national_id = fields.Char(
        string='National identity number', index=True, tracking=True,
        help="Used to spot the same human being in two companies.")
    tax_id = fields.Char(string='Tax number', tracking=True)
    birthday = fields.Date(string='Date of birth')
    email = fields.Char(string='Work email', index=True)

    home_employee_id = fields.Many2one(
        'hr.employee', string='Standing employment', ondelete='set null',
        tracking=True,
        help="The employment this person's month belongs to unless a segment "
             "says otherwise. Their home.")
    employee_ids = fields.One2many(
        'hr.employee', 'pb_person_id', string='Employments')
    employment_count = fields.Integer(
        string='Employments', compute='_compute_employment_count')
    company_ids = fields.Many2many(
        'res.company', string='Companies', compute='_compute_company_ids',
        help="Every company this person holds an employment in.")

    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    # ---------------------------------------------------------------- compute
    @api.depends('employee_ids')
    def _compute_employment_count(self):
        for person in self:
            person.employment_count = len(person.employee_ids)

    @api.depends('employee_ids.company_id')
    def _compute_company_ids(self):
        for person in self:
            person.company_ids = person.employee_ids.mapped('company_id')

    # ------------------------------------------------------------ the helpers
    @api.model
    def _is_stored(self, model, name):
        """Is `name` a column this database can be asked about in a domain?"""
        field = model._fields.get(name)
        return bool(field is not None and field.store and field.column_type)

    @api.model
    def for_employee(self, employee):
        """The person behind an employment, creating one if there is none.

        A person is never a reason a screen cannot answer: an employee record
        made after the bootstrap ran simply gets its own person the first time
        anybody asks.
        """
        if isinstance(employee, models.BaseModel):
            employee = employee[:1]
        else:
            employee = self.env['hr.employee'].sudo().browse(
                int(employee or 0)).exists()
        if not employee:
            return self.browse()
        if employee.pb_person_id:
            return employee.pb_person_id
        person = self.sudo().with_context(
            tracking_disable=True, mail_create_nolog=True).create({
                'name': employee.name or _("Unnamed"),
                'home_employee_id': employee.id,
            })
        employee.sudo().write({'pb_person_id': person.id})
        return person

    # ---------------------------------------------------------- the bootstrap
    @api.model
    def bootstrap(self):
        """One person per active employment that has none. Returns the count.

        Idempotent by construction: it only ever touches employees whose
        `pb_person_id` is NULL, so running it twice is running it once.
        """
        cr = self.env.cr
        # GR13 — a raw statement on a column the ORM also writes needs the
        # pending ORM work flushed FIRST and the cache invalidated WITHOUT a
        # second flush afterwards, or the ORM's stale value lands on top.
        self.env.flush_all()
        cr.execute("""
            WITH todo AS (
                SELECT id, COALESCE(NULLIF(TRIM(name), ''), 'Unnamed') AS name
                  FROM hr_employee
                 WHERE active AND pb_person_id IS NULL
                 ORDER BY id
            ), made AS (
                INSERT INTO pb_person
                    (name, home_employee_id, active, create_uid, create_date,
                     write_uid, write_date)
                SELECT t.name, t.id, TRUE, %s, NOW() AT TIME ZONE 'UTC',
                       %s, NOW() AT TIME ZONE 'UTC'
                  FROM todo t
             RETURNING id, home_employee_id
            )
            UPDATE hr_employee e
               SET pb_person_id = made.id
              FROM made
             WHERE e.id = made.home_employee_id
         RETURNING e.id
        """, (self.env.uid, self.env.uid))
        made = len(cr.fetchall())
        self.env.invalidate_all(flush=False)
        if made:
            _logger.info('pb_workseg: %s person record(s) created', made)
        return made

    # --------------------------------------------------------------- suggest
    @api.model
    def suggest_merges(self, company_ids=None, limit=MAX_SUGGESTIONS):
        """Pairs of persons that look like one human, with the evidence.

        Reads employments rather than persons, because the evidence — a
        national identity number, an email, a birthday — lives on the
        employment record, and one person's two employments are exactly the
        pair this looks for.
        """
        limit = max(1, min(int(limit or MAX_SUGGESTIONS), MAX_SUGGESTIONS))
        domain = [('active', '=', True), ('pb_person_id', '!=', False)]
        if company_ids:
            domain.append(('company_id', 'in',
                           [int(c) for c in company_ids if c]))
        fields_wanted = ['name', 'company_id', 'pb_person_id']
        Employee = self.env['hr.employee'].sudo()
        # STORED columns only. On this release several of the obvious fields
        # (`department_id`, and on some builds the identity number too) are
        # NON-STORED related fields through `hr.version`, and naming one in a
        # `search_read` is a hard ValueError rather than a slow query — the
        # same trap as GR6 and GR20. The identity number is spelled
        # differently on different builds, so the FIRST stored spelling wins
        # and the rest are ignored.
        national_field = ''
        for extra in ('identification_id', 'vietnam_citizen_id',
                      'insurance_code'):
            if self._is_stored(Employee, extra):
                national_field = extra
                break
        if national_field:
            fields_wanted.append(national_field)
        for extra in ('work_email', 'private_email', 'birthday'):
            if self._is_stored(Employee, extra):
                fields_wanted.append(extra)
        rows = Employee.search_read(domain, fields_wanted, limit=20000)

        buckets = {}
        for row in rows:
            person_id = (row.get('pb_person_id') or [0])[0]
            if not person_id:
                continue
            keys = []
            national = _clean(row.get(national_field)) if national_field else ''
            if national and len(national) >= 6:
                keys.append(('national', national, SCORE_NATIONAL_ID,
                             _("Same national identity number")))
            email = (row.get('work_email') or row.get('private_email') or '')
            email = email.strip().lower()
            if email and '@' in email:
                keys.append(('email', email, SCORE_EMAIL,
                             _("Same work email")))
            name = _clean(row.get('name'))
            birthday = row.get('birthday')
            if name and birthday:
                keys.append(('name_birthday', '%s|%s' % (name, birthday),
                             SCORE_NAME_BIRTHDAY,
                             _("Same name and date of birth")))
            for kind, key, score, label in keys:
                buckets.setdefault((kind, key), {
                    'score': score, 'label': label, 'rows': [],
                })['rows'].append(row)

        pairs = {}
        for (kind, _key), bucket in buckets.items():
            persons = {}
            for row in bucket['rows']:
                persons.setdefault((row['pb_person_id'] or [0])[0], []).append(row)
            if len(persons) < 2:
                continue
            ordered = sorted(persons)
            for i, left in enumerate(ordered):
                for right in ordered[i + 1:]:
                    key = (left, right)
                    hit = pairs.setdefault(key, {
                        'person_ids': [left, right],
                        'score': 0.0, 'evidence': [],
                    })
                    if bucket['score'] > hit['score']:
                        hit['score'] = bucket['score']
                    if bucket['label'] not in hit['evidence']:
                        hit['evidence'].append(bucket['label'])
                    hit.setdefault('kinds', set()).add(kind)

        Person = self.sudo()
        wanted = set()
        for hit in pairs.values():
            wanted.update(hit['person_ids'])
        names = {p.id: p for p in Person.browse(sorted(wanted)).exists()}
        out = []
        for hit in sorted(pairs.values(), key=lambda h: -h['score'])[:limit]:
            people = [names.get(pid) for pid in hit['person_ids']]
            if not all(people):
                continue
            out.append({
                'person_ids': hit['person_ids'],
                'score': round(hit['score'], 2),
                'strong': hit['score'] >= SCORE_NATIONAL_ID,
                'evidence': hit['evidence'],
                'kinds': sorted(hit.get('kinds') or []),
                'people': [{
                    'id': person.id,
                    'name': person.name or '',
                    'employments': [{
                        'id': emp.id,
                        'name': emp.name or '',
                        'company': emp.company_id.name or '',
                        'company_id': emp.company_id.id,
                    } for emp in person.employee_ids[:6]],
                } for person in people],
            })
        return out

    # ----------------------------------------------------------------- merge
    def merge(self, person_ids=None):
        """Join several persons into one human. The oldest record survives.

        Everything that pointed at the others is re-pointed rather than
        rewritten: employments, work segments, cost transfers, and the fact
        rows the Explorer has already built. The losers are archived, never
        deleted — a merge somebody regrets has to be readable afterwards.
        """
        ids = sorted({int(p) for p in (person_ids or self.ids) if p})[:MAX_MERGE]
        people = self.sudo().browse(ids).exists()
        if len(people) < 2:
            raise UserError(_("Pick two people to join into one."))
        keeper = people.sorted(key=lambda p: p.id)[0]
        losers = people - keeper

        Employee = self.env['hr.employee'].sudo()
        moved = Employee.with_context(active_test=False).search(
            [('pb_person_id', 'in', losers.ids)])
        if moved:
            moved.write({'pb_person_id': keeper.id})
        if 'pb.work.segment' in self.env:
            segments = self.env['pb.work.segment'].sudo().with_context(
                active_test=False).search([('person_id', 'in', losers.ids)])
            if segments:
                segments.write({'person_id': keeper.id})
        if 'pb.cost.transfer' in self.env:
            transfers = self.env['pb.cost.transfer'].sudo().search(
                [('person_id', 'in', losers.ids)])
            if transfers:
                transfers.write({'person_id': keeper.id})
        # The Explorer's fact rows carry the person as a plain integer (they
        # are a reporting copy, not a relation), so they are re-pointed by
        # statement. A rebuild would answer the same thing more slowly.
        if 'pb.fact.emp' in self.env:
            self.env.flush_all()
            self.env.cr.execute(
                "UPDATE pb_fact_emp SET person_id = %s WHERE person_id = ANY(%s)",
                (keeper.id, list(losers.ids)))
            self.env.invalidate_all(flush=False)

        if not keeper.home_employee_id and keeper.employee_ids:
            keeper.home_employee_id = keeper.employee_ids.sorted(
                key=lambda e: e.id)[0]
        for field in ('national_id', 'tax_id', 'birthday', 'email'):
            if not keeper[field]:
                filled = losers.filtered(lambda p, f=field: p[f])[:1]
                if filled:
                    keeper[field] = filled[field]
        names = ', '.join(losers.mapped('name'))
        losers.write({'active': False})
        keeper.message_post(body=_(
            "Joined with %(names)s. From now on this is one person and is "
            "counted once.", names=names))
        return {'person_id': keeper.id, 'merged': len(losers)}

    @api.model
    def merge_pairs(self, pairs):
        """Merge several suggested pairs in one press."""
        done = 0
        for pair in (pairs or [])[:MAX_MERGE]:
            ids = [int(p) for p in (pair or []) if p]
            if len(ids) < 2:
                continue
            self.browse(ids[:1]).merge(ids)
            done += 1
        return {'merged': done}
