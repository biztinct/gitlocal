# -*- coding: utf-8 -*-
"""Step 6 — Finish: what was built, what still needs a decision, and the gate.

Three jobs, and the third one is the reason the other two exist:

* **Say what this configuration is**, in one page somebody else could read —
  the counts, the identity, the calendar and payment choices, the rule pack it
  is aligned to, and the optional tasks that were done or skipped.
* **Name every decision still waiting for an owner**, with the door that
  resolves it. An open decision NEVER blocks finishing: a person is allowed to
  know something is unanswered and finish anyway. It is the arithmetic that has
  to be right, not the judgement calls.
* **Refuse to finish when a number would be wrong.** Every refusal is decided
  HERE, on the server (ledger rule 9), names its reason in words, and says which
  step fixes it. The client may grey the button out; it is never the reason
  anything is safe.

The gate extends B1's `bp_finish` rather than replacing it: the conversion check
(`python_formula` empty) is still the first question asked, because it is the
one the engine itself answers.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from . import recipe_compiler as rc
from .recipe_schema import review_items

_logger = logging.getLogger(__name__)

#: How many open decisions travel to the screen. A configuration with a hundred
#: unanswered questions is not helped by a list of a hundred rows; it is helped
#: by the first fifteen and a truthful count of the rest.
DECISION_CAP = 15

#: How many component names a refusal is willing to say out loud before it
#: starts counting instead.
NAME_CAP = 5


def payday_rule_label(rule):
    """The payday rule, in the words the Calendar tab uses for it."""
    return {
        'last_working': _("The last working day of the month"),
        'second_last_working': _("The second last working day of the month"),
        'fixed': _("A fixed day of the month"),
    }.get(rule, _("The last working day of the month"))


def late_policy_label(policy):
    """What happens to an input that arrives after the cut-off."""
    return {
        'next_cycle': _("It waits for the next pay run"),
        'off_cycle': _("An off-cycle run is approved for it"),
        'reopen': _("The run is reopened, with two approvals"),
    }.get(policy, _("It waits for the next pay run"))


def bank_id_label(kind):
    """Which bank identifier the payment files carry."""
    return {
        'domestic': _("Domestic account number"),
        'swift': _("SWIFT / BIC"),
    }.get(kind, _("Domestic account number"))


def task_label(task):
    """The optional setup tasks, by the names on the Connect step."""
    return {
        'mapping': _("Source mapping"),
        'payslip': _("Payslip layout"),
        'approvals': _("Approvals"),
    }.get(task, task or '')


class PbBlueprintFinish(models.AbstractModel):
    _inherit = 'pb.blueprint.studio'

    # ==================================================================
    # Everything the Finish step paints, in one call
    # ==================================================================
    @api.model
    def bp_finish_data(self, config_id):
        """One answer, because one screen.

        The tiles, the identity, the decisions, the checks line and the gate are
        five views of the same configuration, and asking five times is how a
        page ends up showing a green button over a red reason.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err

        tally, confirmed = self._finish_tally(config)
        evidence = self._evidence_payload(config, blueprint)
        # BP43 — the counters a SCREEN shows come from the live list, never from
        # the stamp. Adding a scenario changes no formula, so nothing is stale;
        # a line reading "12 of 12 passed" over a list with two rows waiting for
        # confirmation is a page disagreeing with itself.
        evidence.update({'passed': tally['passed'], 'failed': tally['attention'],
                         'pending': tally['pending'],
                         'not_run': tally['not_run'],
                         'checks': sum(tally.values())})

        reasons = self._finish_reasons(config, blueprint, tally, confirmed,
                                       evidence)
        decisions, decisions_total = self._finish_decisions(config, blueprint)
        counts = self._finish_counts(config)

        return {
            'ok': True,
            'revision': blueprint.revision if blueprint else 0,
            'state': blueprint.state if blueprint else 'draft',
            'finished': bool(blueprint and blueprint.state == 'finished'),
            # Whether the STEPS may still be edited. A configuration that has
            # stopped being a draft is read only everywhere in this journey, and
            # the Finish step says so rather than offering buttons that refuse.
            'editable': config.state == 'draft' and not self._has_payslips(config),
            'has_payslips': self._has_payslips(config),
            'counts': counts,
            'identity': self._finish_identity(config, blueprint),
            'decisions': decisions,
            'decisions_total': decisions_total,
            'checks': evidence,
            'optional': self._finish_optional(config, blueprint),
            'gate': {'ok': not reasons, 'reasons': reasons},
        }

    # ------------------------------------------------------------------
    # The three tiles
    # ------------------------------------------------------------------
    def _finish_counts(self, config):
        rules = config.rule_ids
        return {
            'components': len(rules),
            'formulas': len(rules.filtered(lambda r: r.column_type == 'formula')),
            'inputs': len(rules.filtered(lambda r: r.column_type == 'input')),
            'constants': len(rules.filtered(lambda r: r.column_type == 'constant')),
            'samples': len(config.sample_data_ids),
        }

    # ------------------------------------------------------------------
    # Who this configuration is
    # ------------------------------------------------------------------
    def _finish_identity(self, config, blueprint):
        """Name, shape, calendar, payment and rule pack — the facts, once.

        Every value is a STRING the screen prints as it stands: the words that
        describe a stored choice ("The second last working day of the month")
        are written here, beside the choice itself, rather than rebuilt from a
        key in three different places.
        """
        from .blueprint_studio import CYCLE_LABELS
        country_labels = dict(
            self.env['hr.formula.config']._fields['country_code'].selection)
        calendar, payment = self._calendar_prefs(blueprint)
        pack, aligned, differ = self._finish_pack(config, blueprint)

        return {
            'name': config.name or '',
            'code': config.code or '',
            'company': config.company_id.name or '',
            'country': country_labels.get(config.country_code, '')
            or (config.country_code or ''),
            'cycle': CYCLE_LABELS.get(config.cycle_type or 'regular', ''),
            'effective_from': (blueprint.effective_from
                               and str(blueprint.effective_from) or ''),
            'starter': (blueprint.template_name if blueprint else '')
            or _("Blank canvas"),
            'situations': self._situation_labels(blueprint),
            'calendar': {
                'cutoff_day': calendar['cutoff_day'],
                'payday_rule': calendar['payday_rule'],
                'payday_rule_label': payday_rule_label(calendar['payday_rule']),
                'payday_day': calendar['payday_day'],
                'late_inputs': calendar['late_inputs'],
                'late_label': late_policy_label(calendar['late_inputs']),
            },
            'payment': {
                'currency': config.currency_id.name or '',
                'bank_id_type': payment['bank_id_type'],
                'bank_label': bank_id_label(payment['bank_id_type']),
            },
            'pack': pack,
            'pack_aligned': aligned,
            'pack_differ': differ,
            # Who finished it and when — shown only on a completed setup, so
            # the read-only page says whose decision this was rather than
            # presenting itself as a fact of nature.
            'finished_by': (blueprint.write_uid.name or '') if blueprint
            and blueprint.state == 'finished' else '',
            'finished_at': (fields.Datetime.to_string(blueprint.write_date)
                            if blueprint and blueprint.state == 'finished'
                            and blueprint.write_date else ''),
        }

    def _situation_labels(self, blueprint):
        """"Local employees · Joiners & leavers" — the tiles that were ticked.

        The words are the ones on the Start step. They live in the client's
        `blueprint_steps.js` as well; the same sentence in two places is a
        translation risk, so the SERVER sends only the keys it stored and the
        client renders its own labels — except here, where the page has to be
        readable by somebody who is handed it, so the keys come with their words.
        """
        labels = {
            'local': _("Local employees"),
            'international': _("International employees"),
            'shortterm': _("Short-term employees"),
            'netpay': _("Guaranteed take-home pay"),
            'joiners': _("Joiners & leavers"),
            'annual': _("Annual & event-based pay"),
            'midmonth': _("Salary changes within a month"),
            'arrears': _("Corrections & arrears"),
        }
        situations = blueprint.situations() if blueprint else {}
        chosen = list(situations.get('audiences') or []) \
            + list(situations.get('reallife') or [])
        return [labels[key] for key in chosen if key in labels]

    def _finish_pack(self, config, blueprint):
        """The rule pack, and whether this configuration still agrees with it.

        Read through the Tax tab's own helpers so the Finish page can never
        report an alignment the Tax tab would deny. Never fatal: a database
        without a pack for this country simply has nothing to say about one.
        """
        try:
            pack = self._tax_pack(config, blueprint)
            if not pack:
                return None, False, 0
            values = self._pack_values(pack)
            matched = self._legis_rule_map(config, blueprint, pack)
            differ = 0
            for code, item in values.items():
                rule = matched.get(code)
                if not rule:
                    continue
                if round(rule.constant_value or 0.0, 6) != round(item['value'], 6):
                    differ += 1
            return (self._pack_payload(pack), bool(matched) and not differ, differ)
        except AccessError:
            raise
        except Exception as exc:            # noqa: BLE001 — a summary line
            _logger.info("Guided setup: pack alignment unavailable: %s", exc)
            return None, False, 0

    # ------------------------------------------------------------------
    # The checks, counted live
    # ------------------------------------------------------------------
    def _finish_tally(self, config):
        """How every scenario stands right now, and how many are confirmed.

        The same verdict the Test step shows, from the same method — there is
        one definition of "passed" in this programme and it is `_verdict`.
        """
        tally = {'passed': 0, 'attention': 0, 'pending': 0, 'not_run': 0}
        confirmed = 0
        for sample in config.sample_data_ids:
            verdict, _reason, _rows = self._verdict(config, sample)
            tally[verdict] = tally.get(verdict, 0) + 1
            if sample.expected_confirmed and self._has_expected(sample):
                confirmed += 1
        return tally, confirmed

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------
    def _finish_reasons(self, config, blueprint, tally=None, confirmed=None,
                        evidence=None):
        """Why this setup may not be finished yet — in the order to fix them.

        Arithmetic first (a formula the engine cannot read is a payslip that
        cannot be produced), then evidence (nobody has checked it, or what was
        checked has changed since). An open DECISION is never in this list.
        """
        if tally is None or confirmed is None:
            tally, confirmed = self._finish_tally(config)
        if evidence is None:
            evidence = self._evidence_payload(config, blueprint)

        reasons = []

        # --- 1. can the engine read this at all? ------------------------
        try:
            config.action_validate_formulas()
        except AccessError:
            raise
        except Exception as exc:            # noqa: BLE001 — advisory
            _logger.info("Guided setup: validation raised: %s", exc)
        config.invalidate_recordset(['has_errors', 'has_circular_refs'])

        if config.has_circular_refs:
            reasons.append({
                'code': 'circular',
                'text': _("Two components depend on each other, so no number "
                          "can be worked out. Open the components grid and "
                          "break the loop."),
                'step': 'rules', 'tab': 'components',
                'action': _("Open Pay rules"),
            })

        unreadable = config.rule_ids.filtered(
            lambda r: r.column_type == 'formula' and r.excel_formula
            and not r.python_formula)
        if unreadable:
            reasons.append({
                'code': 'unreadable',
                'text': self._name_reason(
                    unreadable,
                    one=_("The engine cannot read the calculation on %s. Fix it "
                          "on Pay rules, then finish."),
                    many=_("The engine cannot read the calculations on %s. Fix "
                           "them on Pay rules, then finish.")),
                'step': 'rules', 'tab': 'components',
                'action': _("Open Pay rules"),
            })

        # `has_errors` is trustworthy again since B2 taught the validator to
        # expand `BRACKET(...)` before it lints (BP-R12). It is asked AFTER the
        # conversion check, because "the engine cannot read this" is the more
        # useful sentence when both are true.
        broken = config.rule_ids.filtered(
            lambda r: r.column_type == 'formula' and r.excel_formula
            and not r.is_valid and r.python_formula)
        if broken:
            reasons.append({
                'code': 'invalid',
                'text': self._name_reason(
                    broken,
                    one=_("%s has a calculation the checker refuses. Open it on "
                          "Pay rules and fix it."),
                    many=_("%s have calculations the checker refuses. Open them "
                           "on Pay rules and fix them.")),
                'step': 'rules', 'tab': 'components',
                'action': _("Open Pay rules"),
            })

        # --- 2. has anybody proved it? ----------------------------------
        # A configuration with no calculations has nothing to check, so the
        # evidence gates do not apply to it: a blank canvas somebody is building
        # their own components in must still be finishable (the plan's step 8).
        has_maths = bool(config.rule_ids.filtered(
            lambda r: r.column_type == 'formula' and r.excel_formula))
        if not has_maths:
            return reasons

        if not evidence.get('ever_run'):
            reasons.append({
                'code': 'not_run',
                'text': _("The checks have not been run yet. Run them on the "
                          "Test step so the numbers are proven before anybody "
                          "is paid by them."),
                'step': 'test', 'tab': '',
                'action': _("Go to Test"),
            })
        elif evidence.get('stale'):
            reasons.append({
                'code': 'stale',
                'text': _("Something changed since the checks were last run, so "
                          "what they proved is no longer what this "
                          "configuration says. Run them again."),
                'step': 'test', 'tab': '',
                'action': _("Run the checks"),
            })

        if tally.get('attention'):
            n = tally['attention']
            reasons.append({
                'code': 'failed',
                'text': (_("1 check needs attention. A number it produced is "
                           "not the number somebody expected.") if n == 1 else
                         _("%s checks need attention. A number they produced is "
                           "not the number somebody expected.", n)),
                'step': 'test', 'tab': '',
                'action': _("Go to Test"),
            })

        if not confirmed:
            reasons.append({
                'code': 'unconfirmed',
                'text': _("No scenario has confirmed numbers behind it yet. A "
                          "number the engine produced is not yet a number "
                          "anybody agreed to — confirm at least one on the Test "
                          "step."),
                'step': 'test', 'tab': '',
                'action': _("Go to Test"),
            })
        else:
            missing = self._unproven_outputs(config)
            if missing:
                reasons.append({
                    'code': 'outputs',
                    'text': self._name_reason(
                        missing,
                        one=_("%s is what this configuration exists to produce, "
                              "and no confirmed scenario checks it. Confirm a "
                              "scenario that expects it on the Test step."),
                        many=_("%s are what this configuration exists to "
                               "produce, and no confirmed scenario checks them. "
                               "Confirm a scenario that expects them on the "
                               "Test step.")),
                    'step': 'test', 'tab': '',
                    'action': _("Go to Test"),
                })
        return reasons

    def _unproven_outputs(self, config):
        """The headline numbers no confirmed scenario asserts.

        Deliberately NOT every "final output": the Vietnam starter's own
        certification suite asserts eighteen values per person and leaves one
        intermediate total out, and refusing to finish over a total nobody looks
        at would be B1's `has_errors` trap in new clothes. What has to be proven
        is the money that reaches a person — take-home pay, and the income tax
        that came off it — resolved the same way the pay panel resolves them, so
        an imported workbook with its own naming is served too.
        """
        wanted = []
        for key in ('take_home', 'tax'):
            code = self._headline_code(config, key)
            if code:
                wanted.append(code)
        if not wanted:
            return self.env['hr.formula.rule'].browse()
        try:
            coverage = self.env['pb.formula.studio'].get_test_coverage(config.id)
        except AccessError:
            raise
        except Exception as exc:            # noqa: BLE001
            _logger.info("Guided setup: coverage unavailable at finish: %s", exc)
            return self.env['hr.formula.rule'].browse()
        if not (coverage or {}).get('ok'):
            return self.env['hr.formula.rule'].browse()
        asserted = {(row.get('code') or '').upper()
                    for row in (coverage.get('asserted') or [])}
        missing = config.rule_ids.filtered(
            lambda r: (r.code or '').upper() in wanted
            and (r.code or '').upper() not in asserted
            and r.column_type == 'formula')
        return missing

    def _headline_code(self, config, key):
        """The code that carries take-home pay (or income tax) here, if any."""
        from .blueprint_studio import FALLBACK_CODES, ROLE_FOR_LINE
        codes = {(r.code or '').upper() for r in config.rule_ids}
        wanted = FALLBACK_CODES.get(key, '')
        if wanted in codes:
            return wanted
        role = ROLE_FOR_LINE.get(key)
        if not role or 'net_role' not in config.rule_ids._fields:
            return ''
        picked = config.rule_ids.filtered(
            lambda r: r.net_role == role and not r.net_role_detail and r.code)
        return (picked[:1].code or '').upper() if picked else ''

    def _name_reason(self, rules, one, many):
        """"SIDED" / "SIDED, HIDED and 3 more" — a refusal that names names."""
        codes = [(r.code or '').upper() for r in rules if r.code]
        if not codes:
            return many % _("some components")
        shown = codes[:NAME_CAP]
        rest = len(codes) - len(shown)
        if rest > 0:
            names = _("%(names)s and %(rest)s more",
                      names=', '.join(shown), rest=rest)
        elif len(shown) > 1:
            names = _("%(names)s and %(last)s",
                      names=', '.join(shown[:-1]), last=shown[-1])
        else:
            names = shown[0]
        template = one if len(codes) == 1 else many
        return template % names

    # ------------------------------------------------------------------
    # Decisions still waiting for an owner
    # ------------------------------------------------------------------
    def _finish_decisions(self, config, blueprint):
        """Every unanswered question, with the door that answers it.

        Four sources, all of them already computed somewhere else in this
        programme — this method never invents a question of its own:

        * a component whose sentence still says "review" (`review_items`),
          which is also where B3's owner questions surface;
        * an optional task that was finished and has been undermined since
          (`bp_readiness`'s `needs_review`);
        * a scenario whose numbers nobody has agreed to yet;
        * a component the tax pack disagrees with — a value that drifted.
        """
        items = []
        included = set(rc.build_ctx(config).order)

        for rule in config.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
            recipe = rule.bp_recipe()
            for review in review_items(recipe, included):
                items.append({
                    'key': 'component-%s-%s' % (rule.id, review['code']),
                    'kind': 'component',
                    'title': rule.name or (rule.code or ''),
                    'code': (rule.code or '').upper(),
                    'text': review['text'],
                    'step': 'rules',
                    'tab': 'components',
                    'rule_id': rule.id,
                    'task': '',
                    'action': _("Open this component"),
                })

        for task, status in self._needs_review_tasks(config, blueprint).items():
            items.append({
                'key': 'task-%s' % task,
                'kind': 'task',
                'title': task_label(task),
                'code': '',
                'text': status,
                'step': 'connect',
                'tab': '',
                'rule_id': 0,
                'task': task,
                'action': _("Open Connect"),
            })

        for sample in config.sample_data_ids:
            if self._has_expected(sample) and not sample.expected_confirmed:
                items.append({
                    'key': 'sample-%s' % sample.id,
                    'kind': 'scenario',
                    'title': sample.name or _("Scenario"),
                    'code': '',
                    'text': _("Nobody has agreed to the numbers this scenario "
                              "expects, so it counts as waiting rather than as "
                              "passed."),
                    'step': 'test',
                    'tab': '',
                    'rule_id': 0,
                    'task': '',
                    'action': _("Go to Test"),
                })

        for row in self._pack_drift_rows(config, blueprint):
            items.append(row)

        return items[:DECISION_CAP], len(items)

    def _needs_review_tasks(self, config, blueprint):
        """The optional tasks that were finished and have changed since."""
        out = {}
        try:
            readiness = self.bp_readiness(config.id)
        except AccessError:
            raise
        except Exception as exc:            # noqa: BLE001
            _logger.info("Guided setup: readiness unavailable at finish: %s", exc)
            return out
        if not (readiness or {}).get('ok'):
            return out
        for task in ('mapping', 'payslip'):
            if (readiness.get('status') or {}).get(task) != 'needs_review':
                continue
            out[task] = _("This was finished, and the configuration has changed "
                          "since. Open it again and mark it done.")
        return out

    def _pack_drift_rows(self, config, blueprint):
        """A statutory value somebody moved away from the rule pack's own."""
        rows = []
        try:
            pack = self._tax_pack(config, blueprint)
            if not pack:
                return rows
            values = self._pack_values(pack)
            matched = self._legis_rule_map(config, blueprint, pack)
        except AccessError:
            raise
        except Exception as exc:            # noqa: BLE001
            _logger.info("Guided setup: drift unavailable at finish: %s", exc)
            return rows
        for code, item in values.items():
            rule = matched.get(code)
            if not rule:
                continue
            current = rule.constant_value or 0.0
            if round(current, 6) == round(item['value'], 6):
                continue
            rows.append({
                'key': 'drift-%s' % rule.id,
                'kind': 'pack',
                'title': rule.name or item['label'],
                'code': (rule.code or '').upper(),
                'text': _("This is %(mine)s here and %(theirs)s in the rule "
                          "pack. Keep yours, or take the pack's value on the "
                          "Tax tab.",
                          mine=self._money(current),
                          theirs=self._money(item['value'])),
                'step': 'rules',
                'tab': 'tax',
                'rule_id': rule.id,
                'task': '',
                'action': _("Open Tax & protection"),
            })
        return rows

    # ------------------------------------------------------------------
    # The optional tasks, as three lines
    # ------------------------------------------------------------------
    def _finish_optional(self, config, blueprint):
        """What was done, skipped or left alone on the Connect step."""
        try:
            readiness = self.bp_readiness(config.id)
        except AccessError:
            raise
        except Exception as exc:            # noqa: BLE001
            _logger.info("Guided setup: optional status unavailable: %s", exc)
            readiness = {}
        status = (readiness or {}).get('status') or {}
        mapping = (readiness or {}).get('mapping') or {}
        payslip = (readiness or {}).get('payslip') or {}
        return [
            {'task': 'mapping', 'label': task_label('mapping'),
             'status': status.get('mapping') or 'not_started',
             'mapped': mapping.get('mapped') or 0,
             'total': mapping.get('inputs') or 0},
            {'task': 'payslip', 'label': task_label('payslip'),
             'status': status.get('payslip') or 'not_started',
             'mapped': payslip.get('placed') or 0,
             'total': payslip.get('components') or 0},
            {'task': 'approvals', 'label': task_label('approvals'),
             'status': 'info', 'mapped': 0, 'total': 0},
        ]

    # ==================================================================
    # Finishing, reopening, discarding
    # ==================================================================
    @api.model
    def bp_finish(self, config_id):
        """Mark the SETUP complete. Never activates anything for real pay.

        B1's gate — did every formula convert — is still asked first, inside
        `_finish_reasons`. What this phase adds is the rest of it: the checks
        have to have been run, they have to have been run against THESE rules,
        nothing may be failing, and somebody has to have agreed to at least one
        set of numbers. Open decisions do not block: a person is allowed to know
        a question is unanswered and finish anyway.
        """
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        if blueprint.state == 'finished':
            # Idempotent by design: a second press, a double click and a retry
            # after a dropped connection all mean the same thing.
            return {'ok': True, 'config_id': config.id, 'already': True}
        if config.state != 'draft' and self._has_payslips(config):
            return {'ok': False, 'reason': _(
                "This configuration has already produced payslips, so its setup "
                "cannot be finished from here.")}

        reasons = self._finish_reasons(config, blueprint)
        if reasons:
            return {
                'ok': False,
                'reason': reasons[0]['text'],
                'reasons': reasons,
                'gate': {'ok': False, 'reasons': reasons},
            }
        blueprint.write({'state': 'finished', 'step': 'finish',
                         'revision': blueprint.revision + 1})
        return {'ok': True, 'config_id': config.id, 'already': False}

    @api.model
    def bp_reopen(self, config_id):
        """"Revisit the setup" — put a finished journey back into edit.

        Only while the configuration itself is still a draft. Once it has been
        validated, released or has paid somebody, the journey is a record of
        what was decided and the components grid is where changes belong — and
        saying that plainly is better than a button that quietly does nothing.
        """
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        if config.state != 'draft' or self._has_payslips(config):
            return {'ok': False, 'reason': _(
                "This configuration is no longer a draft, so the setup cannot "
                "be reopened. Open it in the components grid, where every "
                "change is versioned.")}
        if blueprint.state != 'finished':
            return {'ok': True, 'config_id': config.id, 'already': True}
        blueprint.write({'state': 'draft', 'revision': blueprint.revision + 1})
        return {'ok': True, 'config_id': config.id, 'already': False}

    @api.model
    def bp_discard_check(self, config_id):
        """What discarding this draft would actually destroy.

        Asked before the confirmation is shown, so the dialog names the
        configuration and counts what goes with it instead of asking somebody to
        agree to something vague. A refusal is reported HERE too, so the dialog
        never opens on a draft that cannot be discarded.
        """
        config, blueprint, err = self._guard(config_id)
        if err:
            return err
        counts = self._finish_counts(config)
        if self._has_payslips(config):
            return {'ok': True, 'allowed': False, 'name': config.name or '',
                    'counts': counts, 'reason': _(
                        "This configuration has already produced payslips, so "
                        "it cannot be discarded. Archive it instead.")}
        if blueprint.state != 'draft':
            return {'ok': True, 'allowed': False, 'name': config.name or '',
                    'counts': counts, 'reason': _(
                        "This setup is already complete, so there is nothing to "
                        "discard. Open the configuration and archive it "
                        "instead.")}
        return {'ok': True, 'allowed': True, 'name': config.name or '',
                'counts': counts, 'reason': ''}
