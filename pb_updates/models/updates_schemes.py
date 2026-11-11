# -*- coding: utf-8 -*-
"""UPDATES P2b — pay items judged against each person's own pay scheme.

Decision D5 (ledger): the person never picks a pay scheme. It is worked out
per person by the scheme map — `pb.scheme.map.resolve_many`, the pay run's own
resolver (`pb_payrun_wizard.py:321`) — and a value for a pay item that is not
in that person's scheme is greyed out and skipped, never written.

This file is the ONE place that decides "is this pay item in this person's
scheme". `review`, `recheck` and `apply` (`updates_desk.py`) all ask it, so
what the screen shows and what the server lets through can never disagree.

The scheme map is only READ here, never written.
"""
from odoo import _, api, models

# Loaded after `updates_desk` (models/__init__.py), which defines the model
# this file extends and the context that opens the Records Desk's seams.
from odoo.addons.pb_updates.models.updates_desk import DOOR_CONTEXT


class PbUpdatesSchemes(models.AbstractModel):
    _inherit = 'pb.updates.desk'

    # -----------------------------------------------------------------
    # Pay schemes and their pay items
    # -----------------------------------------------------------------
    @api.model
    def _scheme_items(self, desk, extra_ids=()):
        """`{config_id: {'name', 'codes': {CODE}}}` for every pay scheme this
        person can see (`desk._configs(0)`), plus any scheme somebody in the
        file is paid under that is not among them. ONE search for all."""
        ids = set(desk._configs(0).ids) | {int(i) for i in extra_ids if i}
        if not ids:
            return {}
        configs = self.env['hr.formula.config'].sudo().browse(sorted(ids)).exists()
        out = {c.id: {'name': c.name or c.display_name or '', 'codes': set()}
               for c in configs}
        rules = self.env['hr.formula.rule'].sudo().search_read(
            [('config_id', 'in', list(out)),
             '|', ('is_contract_component', '=', True),
             ('is_text_component', '=', True)], ['config_id', 'code'])
        for rule in rules:
            code = (rule.get('code') or '').strip()
            config = rule.get('config_id')
            if code and config and config[0] in out:
                out[config[0]]['codes'].add(code)
        return out

    @api.model
    def _people_schemes(self, emp_ids, on_date=None):
        """`{emp_id: {'ids': {config_id}, 'name', 'via'}}`.

        `on_date` (UPDATES P2d, optional): who pays them ON that day — the
        pay month of a one-off sheet. Left out it is today, as before.

        A person can be paid under more than one scheme (a monthly one and an
        off-cycle one), so the map is asked about "any kind of run" AND once
        per kind of run it actually has lines for, and the answers are joined.
        `name`/`via` come from the "any kind" answer, else the first one that
        says something. Empty `ids` = nobody could say which scheme pays them.
        """
        ids = sorted({int(i) for i in (emp_ids or []) if i})
        out = {i: {'ids': set(), 'name': '', 'via': ''} for i in ids}
        if not ids:
            return out
        Map = self.env['pb.scheme.map']
        kinds = self.env['hr.formula.scheme.assignment'].sudo()._read_group(
            [('active', '=', True)], ['cycle_type'])
        cycles = ['any'] + sorted({k for (k,) in kinds if k and k != 'any'})
        for cycle in cycles:
            answers = Map.resolve_many(ids, cycle, on_date) if on_date \
                else Map.resolve_many(ids, cycle)
            for emp_id, answer in (answers or {}).items():
                person = out.get(emp_id)
                config_id = (answer or {}).get('config_id') or 0
                if person is None or not config_id:
                    continue
                person['ids'].add(config_id)
                if cycle == 'any' or not person['name']:
                    person['name'] = answer.get('config_name') or ''
                    person['via'] = answer.get('via') or ''
        return out

    @api.model
    def _lines_held(self, desk, emp_ids, codes):
        """`{(emp_id, CODE)}` — pay items that already have a line on the
        person's contract (the contract the desk itself judges against,
        ledger G16). Such a value is real and visible on the contract today,
        so it is never greyed out, whatever the scheme says."""
        codes = {c for c in codes if c}
        if not emp_ids or not codes:
            return set()
        people = desk._matching({'employee_ids': list(emp_ids)}, ctx={})
        contracts = desk._io_contracts(people)
        owner = {c.id: emp_id for emp_id, c in contracts.items()}
        if not owner:
            return set()
        held = set()
        # `advantage_template_code` is the template's code (a related field),
        # the same key `_get_contract_advantage_map` files a line under.
        rows = self.env['hr.contract.advantage'].sudo().search_read(
            [('contract_id', 'in', list(owner)),
             ('advantage_template_id.code', 'in', sorted(codes))],
            ['contract_id', 'advantage_template_code'])
        for row in rows:
            contract = row.get('contract_id')
            if contract and row.get('advantage_template_code') in codes:
                held.add((owner.get(contract[0]), row['advantage_template_code']))
        return held

    @api.model
    def _scheme_context(self, desk, emp_ids, codes):
        """Everything one review/recheck/apply needs to judge pay items, asked
        once: who is paid under which schemes, which pay items each scheme
        has, and which lines are already on the contracts."""
        people = self._people_schemes(emp_ids)
        extra = {cid for p in people.values() for cid in p['ids']}
        return {
            'people': people,
            'items': self._scheme_items(desk, extra),
            'held': self._lines_held(desk, emp_ids, codes),
        }

    # -----------------------------------------------------------------
    # The verdict for one pay-item cell
    # -----------------------------------------------------------------
    @api.model
    def _is_off_scheme(self, ctx, emp_id, field_id):
        """True when this value must be greyed out and skipped:
        the person's schemes are known, none of them has the pay item, and
        their contract has no line for it today."""
        if not ctx or str(field_id or '')[:2] != 'c:':
            return False
        person = ctx['people'].get(emp_id)
        if not person or not person['ids']:
            return False
        code = str(field_id)[2:]
        items = ctx['items']
        if any(code in (items.get(cid) or {}).get('codes', ()) for cid in person['ids']):
            return False
        return (emp_id, code) not in ctx['held']

    @api.model
    def _scheme_names(self, ctx, person):
        items = ctx['items']
        names = [items[cid]['name'] for cid in sorted(person['ids'])
                 if cid in items and items[cid]['name']]
        if not names and person.get('name'):
            names = [person['name']]
        return names

    @api.model
    def _off_scheme_why(self, ctx, emp_id, emp_name, item_label):
        """"<Name> is paid under <scheme> (<how we know>), which has no <pay
        item>." — screen words only: no codes, no ids."""
        person = ctx['people'].get(emp_id) or {}
        names = self._scheme_names(ctx, person)
        who = emp_name or _("This person")
        via = person.get('via') or ''
        if len(names) > 1:
            schemes = _("%(first)s and %(last)s") % {
                'first': ", ".join(names[:-1]), 'last': names[-1]}
            return _("%(who)s is paid under %(schemes)s, which have no "
                     "%(item)s.") % {'who': who, 'schemes': schemes,
                                     'item': item_label}
        scheme = names[0] if names else _("their pay scheme")
        if via:
            return _("%(who)s is paid under %(scheme)s (%(via)s), which has "
                     "no %(item)s.") % {'who': who, 'scheme': scheme,
                                        'via': via, 'item': item_label}
        return _("%(who)s is paid under %(scheme)s, which has no %(item)s.") % {
            'who': who, 'scheme': scheme, 'item': item_label}

    @api.model
    def _person_scheme(self, ctx, emp_id):
        """What the screen shows about one person's scheme: the name for the
        person cell's second line, the ids for the scheme strip's filter, and
        whether nobody could say (the amber dot)."""
        person = (ctx or {}).get('people', {}).get(emp_id)
        if not person:
            return {'scheme': '', 'scheme_ids': [], 'no_scheme': False}
        names = self._scheme_names(ctx, person)
        return {'scheme': ", ".join(names), 'scheme_ids': sorted(person['ids']),
                'no_scheme': not person['ids']}

    @api.model
    def _strip(self, ctx, emp_ids):
        """"Pay schemes in this file": one chip per scheme with its head-count,
        biggest first, and how many people no scheme covers."""
        counts, nobody = {}, 0
        for emp_id in set(emp_ids):
            person = ctx['people'].get(emp_id)
            if not person:
                continue
            if not person['ids']:
                nobody += 1
                continue
            for cid in person['ids']:
                counts[cid] = counts.get(cid, 0) + 1
        items = ctx['items']
        schemes = [{'id': cid, 'name': (items.get(cid) or {}).get('name') or '',
                    'count': n} for cid, n in counts.items()]
        schemes.sort(key=lambda s: (-s['count'], s['name'].lower()))
        return {'schemes': schemes, 'no_scheme': nobody}

    @api.model
    def _drop_off_scheme(self, desk, changes):
        """The server's own rail for `apply`: the same verdict as the screen,
        asked again. `(kept, skipped)` — a dropped change is reported, never
        silently lost and never an error."""
        pay = [c for c in changes if str(c.get('field_id') or '')[:2] == 'c:']
        if not pay:
            return changes, []
        emp_ids = {int(c.get('emp_id') or 0) for c in pay} - {0}
        ctx = self._scheme_context(desk, emp_ids,
                                   {str(c['field_id'])[2:] for c in pay})
        kept, skipped = [], []
        for change in changes:
            try:
                emp_id = int(change.get('emp_id') or 0)
            except (TypeError, ValueError):
                emp_id = 0
            if self._is_off_scheme(ctx, emp_id, change.get('field_id')):
                skipped.append(change)
            else:
                kept.append(change)
        return kept, skipped


class PbRecordsDeskUpdatesDoor(models.AbstractModel):
    """An apply that came through Updates is judged with Updates' catalogue
    whenever the desk looks at it again — at approval time (`_write_plan`,
    `_plan_moved_since`) and on undo, including an undo pressed on the Records
    screen's History. Without this a pay item only Updates offers would be
    "not used any more" the day an approver approves it."""
    _inherit = 'pb.records.desk'

    def _updates_door(self, apply_rec):
        if self.env.context.get('records_scheme_items'):
            return self
        rec = apply_rec.sudo() if apply_rec else apply_rec
        if rec and 'updates_batch_id' in rec._fields and rec.updates_batch_id:
            return self.with_context(**DOOR_CONTEXT)
        return self

    @api.model
    def _write_plan(self, apply_rec):
        door = self._updates_door(apply_rec)
        return super(PbRecordsDeskUpdatesDoor, door)._write_plan(apply_rec)

    @api.model
    def _plan_moved_since(self, apply_rec):
        door = self._updates_door(apply_rec)
        return super(PbRecordsDeskUpdatesDoor, door)._plan_moved_since(apply_rec)

    @api.model
    def undo_apply(self, apply_id):
        source = self.env['pb.records.apply'].sudo().browse(int(apply_id or 0)).exists()
        door = self._updates_door(source)
        return super(PbRecordsDeskUpdatesDoor, door).undo_apply(apply_id)

    @api.model
    def _door_for(self, apply_rec):
        """UPDATES P2c — a scheduled write ("Start now" or the hourly job)
        is judged with the same catalogue and CLEAR rules as when it was
        proposed."""
        return self._updates_door(apply_rec)
