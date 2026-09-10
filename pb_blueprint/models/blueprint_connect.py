# -*- coding: utf-8 -*-
"""Step 3 — Connect: where the numbers come from, and where they land.

Three tasks, and only two of them are work. **Source mapping** points the
configuration's inputs at the systems that already hold them; **payslip layout**
arranges those components on the page a person is handed; **approvals** is
information, because pay runs already follow a fixed Officer → HR → Finance
chain and a per-configuration approval rule is a later programme (owner ruling,
2026-09-10).

Nothing here re-implements either tool. Both doors open the screen that already
exists — the Mapping Studio and the payslip designer — ON THIS DRAFT, and both
come back here. What this file owns is the honest count of what has been done
(`bp_readiness`), and the small state machine that remembers whether a person
considers a task finished, skipped, or in need of another look after the
components changed underneath it.

Every gate is server-side: a task cannot be marked done while nothing is
connected, however the client asks.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .blueprint import CONNECT_STATUSES, CONNECT_TASKS

_logger = logging.getLogger(__name__)

#: A declared source kind (`hr.formula.rule.declared_sources`) → the lane a
#: person reads on the card. Four lanes, because those are the four different
#: places a number can come from, and naming a lane the reader has none of is
#: how a coverage line stops being believed.
LANE_OF_KIND = {
    'feed': 'api',
    'rule': 'api',
    'excel': 'excel',
    'employee_field': 'records',
    'contract_field': 'records',
    'bank_account': 'records',
    'contract_component': 'records',
}

#: The words for each lane, singular in the sentence "4 from the connected
#: system". Written out as literals so the extractor finds them: `_(variable)`
#: extracts nothing and ships English for ever.
def lane_label(lane):
    return {
        'api': _("from the connected system"),
        'excel': _("from spreadsheets"),
        'records': _("from employee records"),
        'cycle': _("carried from the mid-month run"),
    }.get(lane, '')


#: The three tiers a pay run already passes through, and what each one does.
#:
#: A FUNCTION, not a module-level dictionary: `_()` at import time runs before
#: any language is known and would ship English for ever (B2's helper labels and
#: B3's `value_label` exist for the same reason). The NAMES here are only the
#: fallback — the live ones are read from the pay-run screen's own field labels
#: where that module is installed, so this card can never name a stage the board
#: does not.
def tier_rows():
    return (
        ('level0', _("Officer review"),
         _("The payroll officer checks the run and sends it on.")),
        ('level1', _("HR review"),
         _("HR checks the people and the amounts.")),
        ('level2', _("Finance approval"),
         _("Finance releases the money.")),
    )


class PbBlueprintConnect(models.AbstractModel):
    _inherit = 'pb.blueprint.studio'

    # ==================================================================
    # What is connected, right now
    # ==================================================================
    @api.model
    def bp_readiness(self, config_id):
        """Everything the Connect step paints, in one call.

        Deliberately ONE call rather than one per card: the three cards are
        three views of the same configuration, and two round trips is how a
        screen ends up showing a coverage line that disagrees with its own pill.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err

        mapping = self._mapping_state(config)
        payslip = self._payslip_state(config)
        status = blueprint.optional_status() if blueprint else self._blank_status()

        # `needs_review` is decided HERE, never stored: it is a comparison
        # between what was true when somebody pressed "Mark as done" and what is
        # true now, and a stored copy of that answer is a copy that goes stale
        # the moment a component is added.
        mapping['changed_since'] = self._added(
            status['mapping'].get('snapshot'), mapping['codes'],
            status['mapping'].get('status'))
        payslip['changed_since'] = self._added(
            status['payslip'].get('snapshot_all'), payslip['all_codes'],
            status['payslip'].get('status'))
        payslip['removed_placed'] = self._removed(
            status['payslip'].get('snapshot'), payslip['placed_codes'],
            status['payslip'].get('status'))

        shown = {
            'mapping': self._shown_status(
                status['mapping'].get('status'),
                bool(mapping['changed_since'])),
            'payslip': self._shown_status(
                status['payslip'].get('status'),
                bool(payslip['changed_since'] or payslip['removed_placed'])),
            'approvals': 'info',
        }

        # Internal keys the client has no use for. Sent nowhere: a payload is
        # read by a person through a screen, and every extra list in it is
        # another thing that can be rendered by accident (BP34).
        for key in ('codes',):
            mapping.pop(key, None)
        for key in ('all_codes', 'placed_codes'):
            payslip.pop(key, None)

        return {
            'ok': True,
            'revision': blueprint.revision if blueprint else 0,
            'editable': self._connect_editable(config),
            'config': {
                'id': config.id,
                'name': config.name or '',
                'code': config.code or '',
                'company': config.company_id.name or '',
            },
            'mapping': mapping,
            'payslip': payslip,
            'status': shown,
            'stored_status': {k: v.get('status') for k, v in status.items()},
            'doors': self._connect_doors(config),
            'approvals': self._approval_tiers(),
        }

    def _blank_status(self):
        """A configuration that was not built through the guided setup still
        shows this step — it simply has nothing remembered about it."""
        from .blueprint import DEFAULT_OPTIONAL_STATUS
        return {task: dict(blank)
                for task, blank in DEFAULT_OPTIONAL_STATUS.items()}

    def _connect_editable(self, config):
        """The skip links belong to a draft. The DOORS always work: looking at
        the payslip of a live configuration is a perfectly ordinary thing to
        want, and taking the door away would be the dead end."""
        return config.state == 'draft' and not self._has_payslips(config)

    @api.model
    def _shown_status(self, stored, changed):
        stored = stored if stored in CONNECT_STATUSES else 'not_started'
        if stored == 'configured' and changed:
            return 'needs_review'
        return stored

    @api.model
    def _added(self, snapshot, current, stored_status):
        """Codes that appeared since the task was marked done.

        **An empty snapshot means "we do not know", not "there was nothing".**
        A draft finished before this phase existed carries a status and no
        snapshot, and treating that as an empty set would tell somebody every
        component in their configuration had just been added. Marking the task
        done once more records what it looks like now and the card is exact
        from then on.
        """
        if stored_status != 'configured' or not snapshot:
            return []
        return sorted(set(current or []) - set(snapshot or []))

    @api.model
    def _removed(self, snapshot, current, stored_status):
        if stored_status != 'configured' or not snapshot:
            return []
        return sorted(set(snapshot or []) - set(current or []))

    # ------------------------------------------------------------------
    # Lane 1-4 — where an input's value comes from
    # ------------------------------------------------------------------
    def _mapping_state(self, config):
        """How many of this configuration's inputs have somewhere to come from.

        An INPUT is the only kind of component that can have a source: a
        calculated column works its own value out and a fixed value already has
        one, so counting them would inflate the number with components that were
        never waiting for anything.

        Four lanes, from four different statements of fact:

          * **api** — a wire drawn on the "System fields → Scheme" board
            (`hr.integration.field.mapping.target_rule_id`), plus any component
            that DECLARES a feed or a rule output as its source;
          * **excel** — a component that declares a spreadsheet column;
          * **records** — a mapping onto an employee/contract field or a bank
            detail (`hr.payslip.import.mapping.component_id`), plus a component
            marked as coming from the contract;
          * **cycle** — a mid-cycle component carried into this end-cycle run
            (`hr.payroll.cycle.component.mapping.end_component_id`).

        The declared half and the drawn half are a UNION rather than either one
        alone: the two are recorded independently on these databases (a wire can
        exist without a binding and a binding without a wire), and counting only
        one of them would tell somebody their work had not been saved.
        """
        inputs = config.rule_ids.filtered(lambda r: r.column_type == 'input')
        input_ids = set(inputs.ids)
        lanes = {'api': set(), 'excel': set(), 'records': set(), 'cycle': set()}

        # ---- what each component DECLARES ----------------------------
        for rule in inputs:
            try:
                specs = rule.declared_sources()
            except Exception as exc:        # noqa: BLE001 — a count, never a crash
                _logger.info("Guided setup: declared sources unavailable "
                             "for rule %s: %s", rule.id, exc)
                specs = []
            for spec in specs:
                lane = LANE_OF_KIND.get(spec.get('kind'))
                if not lane:
                    continue
                if spec.get('kind') != 'contract_component' and not (
                        spec.get('key') or '').strip():
                    continue
                lanes[lane].add(rule.id)

        # ---- what somebody DREW --------------------------------------
        if input_ids:
            FM = self.env.get('hr.integration.field.mapping')
            if FM is not None:
                try:
                    for m in FM.sudo().search(
                            [('target_rule_id', 'in', list(input_ids))]):
                        lanes['api'].add(m.target_rule_id.id)
                except Exception as exc:    # noqa: BLE001
                    _logger.info("Guided setup: wire census failed: %s", exc)

            IM = self.env.get('hr.payslip.import.mapping')
            if IM is not None:
                try:
                    for m in IM.sudo().search([
                            ('salary_structure_id', '=', config.id),
                            ('component_id', 'in', list(input_ids))]):
                        lanes['records'].add(m.component_id.id)
                except Exception as exc:    # noqa: BLE001
                    _logger.info("Guided setup: record census failed: %s", exc)

            CM = self.env.get('hr.payroll.cycle.component.mapping')
            if CM is not None:
                try:
                    for m in CM.sudo().search([
                            ('end_cycle_config_id', '=', config.id),
                            ('end_component_id', 'in', list(input_ids))]):
                        lanes['cycle'].add(m.end_component_id.id)
                except Exception as exc:    # noqa: BLE001
                    _logger.info("Guided setup: cycle census failed: %s", exc)

        mapped_ids = set().union(*lanes.values()) if lanes else set()
        unmapped = [r for r in inputs if r.id not in mapped_ids]
        return {
            'inputs': len(inputs),
            'mapped': len(mapped_ids),
            'by_lane': {lane: len(ids) for lane, ids in lanes.items()},
            'lane_labels': {lane: lane_label(lane) for lane in lanes},
            # Capped: a list of ninety-nine unmapped codes is not a list
            # anybody reads, and the count above already tells the truth.
            'unmapped': [{'code': r.code or '', 'name': r.name or r.code or ''}
                         for r in unmapped[:8]],
            'unmapped_more': max(0, len(unmapped) - 8),
            'codes': sorted(r.code for r in inputs if r.code),
        }

    # ------------------------------------------------------------------
    # The payslip
    # ------------------------------------------------------------------
    def _payslip_state(self, config):
        """How much of the payslip has been arranged.

        The same three facts the payslip designer itself reads
        (`pb.formula.studio.payslip_studio_data`): a component that shows on the
        payslip and sits in a section is PLACED; one that shows but has no
        section is in the TRAY, waiting to be put somewhere; a section is an
        `hr.payslip.config` row bound to this configuration.
        """
        rules = config.rule_ids
        on_slip = rules.filtered(lambda r: r.appears_on_payslip)
        placed = on_slip.filtered(lambda r: r.payslip_identifier)
        tray = on_slip - placed
        Section = self.env.get('hr.payslip.config')
        sections = 0
        if Section is not None:
            try:
                sections = Section.search_count(
                    [('salary_structure_id', '=', config.id)])
            except Exception as exc:        # noqa: BLE001
                _logger.info("Guided setup: section count failed: %s", exc)
        return {
            'total': len(rules),
            'on_slip': len(on_slip),
            'placed': len(placed),
            'tray': len(tray),
            'sections': sections,
            'tray_names': [{'code': r.code or '', 'name': r.name or r.code or ''}
                           for r in tray[:8]],
            'tray_more': max(0, len(tray) - 8),
            'placed_codes': sorted(r.code for r in placed if r.code),
            'all_codes': sorted(r.code for r in rules if r.code),
        }

    # ------------------------------------------------------------------
    # The doors
    # ------------------------------------------------------------------
    def _connect_doors(self, config):
        """Which tools this database actually has, and whether they will open
        on THIS draft.

        A button that leads nowhere is worse than no button, so the card is told
        the truth twice: whether the screen is installed at all, and — for the
        mapping board, which silently swaps a configuration it cannot select —
        whether the draft is one of the options it offers.
        """
        mapping_action = self.env.ref('pb_formula_studio.action_pb_mapping_studio',
                                      raise_if_not_found=False)
        selectable, reason = True, ''
        if mapping_action:
            try:
                pickers = self.env['pb.formula.studio'].mapping_pickers(
                    {'config_id': config.id})
                fell_back = ((pickers or {}).get('defaults') or {}).get(
                    'fell_back') or []
                if 'config' in fell_back:
                    selectable = False
                    reason = _(
                        "The mapping screen cannot open on this configuration "
                        "yet. It lists the configurations it can read, and this "
                        "one is not among them — ask whoever looks after "
                        "payroll setup to give you access.")
            except AccessError:
                raise
            except Exception as exc:        # noqa: BLE001
                _logger.info("Guided setup: mapping pickers unavailable: %s", exc)
        studio_action = self.env.ref('pb_formula_studio.action_pb_formula_studio',
                                     raise_if_not_found=False)
        return {
            'mapping': {
                'available': bool(mapping_action),
                'selectable': selectable,
                'reason': reason,
            },
            'payslip': {'available': bool(studio_action)},
        }

    # ------------------------------------------------------------------
    # Approvals — information only
    # ------------------------------------------------------------------
    @api.model
    def _approval_tiers(self):
        """The chain a pay run already follows, in the words the pay-run screen
        uses.

        Read from that screen's own field labels where the module is installed,
        so this card can never name a stage the board does not. It changes
        nothing and offers no button: custom approval rules per configuration
        are a later release, and pretending otherwise here would be a promise
        the product does not keep.
        """
        rows = tier_rows()
        labels = {key: name for key, name, _what in rows}
        Run = self.env.get('hr.payslip.run')
        if Run is not None and 'pb_sendback_from' in Run._fields:
            try:
                live = dict(Run._fields['pb_sendback_from'].selection or [])
                for key in labels:
                    if live.get(key):
                        labels[key] = live[key]
            except Exception as exc:        # noqa: BLE001
                _logger.info("Guided setup: approval labels unavailable: %s", exc)
        return {
            'installed': Run is not None,
            'tiers': [{'key': key, 'name': labels[key], 'what': what}
                      for key, _name, what in rows],
        }

    # ==================================================================
    # The status machine
    # ==================================================================
    def _connect_guard(self, config_id, task):
        """A configuration, its setup row, and a task we are willing to change."""
        config, blueprint, err = self._guard(config_id)
        if err:
            return None, None, None, err
        task = (task or '').strip()
        if task not in CONNECT_TASKS:
            return None, None, None, {'ok': False, 'reason': _(
                "That is not one of the things this step sets up.")}
        if task == 'approvals':
            return None, None, None, {'ok': False, 'reason': _(
                "Approvals are already in place for every pay run, so there is "
                "nothing to set up or skip here.")}
        return config, blueprint, task, None

    @api.model
    def bp_task_open(self, config_id, task):
        """Remember that somebody walked through this door.

        "In progress" is not a guess: it is the honest answer to "you opened it
        and nothing is connected yet", and it exists so that coming back to a
        card that still reads zero does not look like the door failed.
        """
        config, blueprint, task, err = self._connect_guard(config_id, task)
        if err:
            return err
        status = blueprint.optional_status()
        entry = status[task]
        entry['opened_at'] = fields.Datetime.to_string(fields.Datetime.now())
        if entry.get('status') in ('not_started', 'skipped'):
            entry['status'] = 'in_progress'
        blueprint.set_optional_status(status)
        return self.bp_readiness(config.id)

    @api.model
    def bp_task_set(self, config_id, task, status):
        """Mark a task done, skipped, or not started after all.

        **Done is earned, not claimed.** The server checks the same number the
        card shows before it will store `configured`, so a hand-written call
        cannot mark an empty configuration finished and a person cannot later
        read "Done" over a coverage line that says nothing is connected. That is
        rule 9 of the ledger: the client's flags are display only.
        """
        config, blueprint, task, err = self._connect_guard(config_id, task)
        if err:
            return err
        status = (status or '').strip()
        if status not in ('configured', 'skipped', 'not_started'):
            return {'ok': False, 'reason': _(
                "That is not something a task can be set to.")}

        state = blueprint.optional_status()
        entry = state[task]
        if status == 'configured':
            if task == 'mapping':
                current = self._mapping_state(config)
                if not current['mapped']:
                    return {'ok': False, 'reason': _(
                        "Nothing is connected yet, so there is nothing to mark "
                        "as done. Open the source mapping and point at least "
                        "one input at where its value comes from.")}
                entry['snapshot'] = current['codes']
            else:
                current = self._payslip_state(config)
                if not current['placed']:
                    return {'ok': False, 'reason': _(
                        "No component has been placed on the payslip yet. Open "
                        "the payslip designer and put at least one line in a "
                        "section.")}
                entry['snapshot'] = current['placed_codes']
                entry['snapshot_all'] = current['all_codes']
            entry['status'] = 'configured'
            entry['done_at'] = fields.Datetime.to_string(fields.Datetime.now())
        else:
            entry['status'] = status
            entry['done_at'] = ''
            entry['snapshot'] = []
            if 'snapshot_all' in entry:
                entry['snapshot_all'] = []
        blueprint.set_optional_status(state)
        # A decision about what is finished IS something two people can
        # disagree about, so it bumps the revision; opening a door is not.
        blueprint.revision = blueprint.revision + 1
        return self.bp_readiness(config.id)

    @api.model
    def bp_skip_rest(self, config_id):
        """"Skip the rest and review outputs."

        Only a task nobody has touched is skipped. Something already done stays
        done, and something opened and half-finished stays that way — a bulk
        action that quietly undid work would be the last time anybody pressed
        it.
        """
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        state = blueprint.optional_status()
        skipped = []
        for task in CONNECT_TASKS:
            if task == 'approvals':
                continue
            if state[task].get('status') == 'not_started':
                state[task]['status'] = 'skipped'
                skipped.append(task)
        if skipped:
            blueprint.set_optional_status(state)
            blueprint.revision = blueprint.revision + 1
        result = self.bp_readiness(config.id)
        if result.get('ok'):
            result['skipped'] = skipped
        return result
