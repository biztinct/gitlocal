# -*- coding: utf-8 -*-
"""What is on the wire when PayAI asks a model about real payroll.

WHAT THIS FILE IS PROTECTING
----------------------------
Two paths in this module send record data to an external provider, and until
LEARNOS Phase 4 both sent it with the names in.

  1. `payroll_ai_engine._process_data_query` — `json.dumps` of a query result
     that, on the individual path, is a list of employees with their job
     titles and their wages.
  2. `payroll_ai_pulse._generate_ai_summaries` — an alert's `details`, which
     for two of the four detectors is the week's joiners or leavers by name.

THE PROPERTY, and the tests are written against it rather than against a list
of cases: **the exact string that would be sent contains none of the names,
emails or phone numbers that were in the input**, in either spelling. That is
assertable without a provider because the prompt builders are pure functions
(`data_query_prompt`, `pulse_summary_prompt`), which is the whole reason they
were factored out.

NO PROVIDER, NO NETWORK, NO DATABASE in anything below except the two methods
that need `self.env`. The same battery also runs in
`docs/tutorial_poc/author/tools/replay_tests.py`, because there is no odoo-bin
on the authoring machine and a test that has never executed is not a test.

NEGATIVE CONTROL, EXECUTED: bypassing the redaction in
`_process_data_query` (passing `payroll_data` where `redacted_data` belongs)
makes `test_04` fail on the first name it finds; restoring it makes it pass.
Both runs are in the Phase 4 report.
"""
import json

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payroll_ai_insights.models.ai_redaction import (
    collect_names, extend_mapping, generic_scrub, redact_names, redact_text,
    restore_deep, restore_names,
)
from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_engine import (
    data_query_prompt,
)
from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_pulse import (
    pulse_summary_prompt, redacted_details,
)
from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_report import (
    SUMMARY_DATA_CHARS, alert_rows, redact_sections, report_executive_prompt,
    report_section_prompt,
)

# A payload in the exact shape `_query_individual_data` returns, with the
# fixture's people in it — accented, because that is how they are stored.
INDIVIDUAL_PAYLOAD = {
    'query_type': 'individual_employees',
    'title': 'Employee Salary Details',
    'data': [
        {'employee': 'Nguyễn Thị Mai', 'department': 'Retail',
         'job_title': 'Cashier', 'salary': 12000000.0},
        {'employee': 'Trần Văn Hùng', 'department': 'Retail',
         'job_title': 'Supervisor', 'salary': 18500000.0},
        {'employee': 'Đỗ Thị Lan', 'department': 'F&B',
         'job_title': 'Chef', 'salary': 15000000.0},
    ],
    'total_employees': 3,
    'currency': '₫',
    'suggested_chart': 'bar',
    'drilldown_model': 'hr.employee',
}

# TWO PEOPLE WHOSE NAMES FOLD TO THE SAME ASCII. `Hùng` and `Hưng` are
# different men; strip the tone marks and both are `Hung`. Vietnamese is full
# of these pairs (Dũng/Dụng, Lân/Lấn, Trâm/Trầm) and they are exactly what the
# first draft of `extend_mapping` merged into one entry — leaving the second
# person unmapped and his name in the prompt. The fixture is here rather than
# in one test because the property below is asserted over it.
NEIGHBOUR_PAYLOAD = {
    'query_type': 'individual_employees',
    'data': [
        {'employee': 'Trần Văn Hùng', 'department': 'Retail', 'salary': 18500000.0},
        {'employee': 'Trần Văn Hưng', 'department': 'F&B', 'salary': 17000000.0},
        {'employee': 'Nguyễn Văn Dũng', 'department': 'Retail', 'salary': 16000000.0},
        {'employee': 'Nguyễn Văn Dụng', 'department': 'Retail', 'salary': 15500000.0},
        {'employee': 'Phạm Thị Lân', 'department': 'F&B', 'salary': 14000000.0},
        {'employee': 'Phạm Thị Lấn', 'department': 'F&B', 'salary': 13500000.0},
        {'employee': 'Đỗ Thị Trâm', 'department': 'Retail', 'salary': 12500000.0},
        {'employee': 'Đỗ Thị Trầm', 'department': 'Retail', 'salary': 12000000.0},
    ],
}

# Every spelling of every neighbour above. The SECOND of each pair is the one
# the merge bug let through, so it is named here explicitly.
NEIGHBOURS = (
    'Trần Văn Hùng', 'Trần Văn Hưng', 'Nguyễn Văn Dũng', 'Nguyễn Văn Dụng',
    'Phạm Thị Lân', 'Phạm Thị Lấn', 'Đỗ Thị Trâm', 'Đỗ Thị Trầm',
    'Hùng', 'Hưng', 'Dũng', 'Dụng', 'Lân', 'Lấn', 'Trâm', 'Trầm',
)

# The pulse's headcount detector, verbatim in shape.
PULSE_DETAILS = {
    'new_employees': [
        {'name': 'Bùi Anh Tuấn', 'department': 'IT Services'},
        {'name': 'Lê Thu Trang', 'department': 'Retail'},
    ],
}

# Every spelling of every person above that must not survive. The UNACCENTED
# forms are here because that is how a name arrives from a payroll import, a
# bank registry or somebody in a hurry, and a scrub that only knows the
# accented one lets through the spelling most likely to be typed.
FORBIDDEN = (
    'Nguyễn Thị Mai', 'Nguyen Thi Mai', 'Mai',
    'Trần Văn Hùng', 'Tran Van Hung', 'Hùng', 'Hung',
    'Đỗ Thị Lan', 'Do Thi Lan', 'Lan',
    'Bùi Anh Tuấn', 'Bui Anh Tuan', 'Tuấn', 'Tuan',
    'Lê Thu Trang', 'Le Thu Trang', 'Trang',
) + NEIGHBOURS


def _leaks(text, names=FORBIDDEN):
    """Every forbidden spelling present in `text`. Empty list means clean."""
    return [n for n in names if n in text]


@tagged('post_install', '-at_install')
class TestAiRedaction(TransactionCase):

    # -- 1. the collector -------------------------------------------------
    def test_01_names_are_collected_by_key_in_order(self):
        self.assertEqual(
            collect_names(INDIVIDUAL_PAYLOAD),
            ['Nguyễn Thị Mai', 'Trần Văn Hùng', 'Đỗ Thị Lan'])
        self.assertEqual(collect_names(PULSE_DETAILS),
                         ['Bùi Anh Tuấn', 'Lê Thu Trang'])
        self.assertEqual(collect_names({'department': 'Retail'}), [],
                         "a department was collected as a person")

    def test_01b_the_payload_handed_in_is_not_mutated(self):
        """The caller keeps using the original — it is what the answer is
        built from and what `drilldown_model` is read out of."""
        before = json.dumps(INDIVIDUAL_PAYLOAD, sort_keys=True, default=str)
        redact_names(INDIVIDUAL_PAYLOAD)
        self.assertEqual(
            json.dumps(INDIVIDUAL_PAYLOAD, sort_keys=True, default=str), before)

    # -- 2. the property --------------------------------------------------
    def test_02_no_name_survives_anywhere_in_the_redacted_payload(self):
        redacted, mapping = redact_names(INDIVIDUAL_PAYLOAD)
        blob = json.dumps(redacted, ensure_ascii=False, default=str)
        self.assertFalse(_leaks(blob), "names survived redaction: %s" % _leaks(blob))
        self.assertEqual(len(mapping), 3)
        for placeholder in ('[person-1]', '[person-2]', '[person-3]'):
            self.assertIn(placeholder, blob)
        # The data that was ASKED FOR is still there. A redaction that removes
        # the answer is a refusal wearing a different hat.
        self.assertIn('18500000', blob)
        self.assertIn('Retail', blob)
        self.assertIn('Supervisor', blob)

    def test_02b_a_name_is_removed_from_a_field_it_was_not_collected_from(self):
        """The collector reads `employee`; the guard is that the name is then
        gone from EVERY string. A name correctly blanked in one field and left
        standing in a title has not been redacted."""
        payload = {
            'title': 'Salary detail for Nguyễn Thị Mai',
            'note': 'compare with Nguyen Thi Mai last month',
            'data': [{'employee': 'Nguyễn Thị Mai', 'salary': 1}],
        }
        redacted, _m = redact_names(payload)
        blob = json.dumps(redacted, ensure_ascii=False)
        self.assertFalse(_leaks(blob), "a name survived outside its own key")
        self.assertEqual(redacted['title'], 'Salary detail for [person-1]')
        self.assertEqual(redacted['note'],
                         'compare with [person-1] last month',
                         "the tone-folded spelling was not matched")

    def test_02c_a_shorter_name_does_not_eat_a_longer_one(self):
        """"Hùng" is a substring of "Trần Văn Hùng". Replacing the short one
        first leaves "Trần Văn [person-2]" — a redaction that hands the
        provider two thirds of a name and reads as a bug."""
        payload = {'data': [{'employee': 'Trần Văn Hùng'},
                            {'employee': 'Hùng'}]}
        redacted, _m = redact_names(payload)
        blob = json.dumps(redacted, ensure_ascii=False)
        self.assertFalse(_leaks(blob, ('Trần Văn Hùng', 'Hùng', 'Trần', 'Văn')),
                         "a partial name survived: %s" % blob)

    def test_02c2_the_casing_a_name_arrives_in_does_not_matter(self):
        """FOUND IN REVIEW, before it shipped. The first version of the matcher
        was case-SENSITIVE, so the two commonest real spellings walked through:
        the all-caps form a payroll import writes, and the lower-case form
        somebody types into a question. Worse, adding IGNORECASE without
        folding the lookup would have made the substitution RAISE on the first
        differently-cased match — a redactor that can be made to raise is not
        a redactor."""
        _r, mapping = redact_names(INDIVIDUAL_PAYLOAD)
        for spelling in ('NGUYEN THI MAI', 'nguyen thi mai', 'Nguyen Thi Mai',
                         'NGUYỄN THỊ MAI', 'nguyễn thị mai'):
            out = redact_text('about %s here' % spelling, mapping)
            self.assertEqual(out, 'about [person-1] here',
                             "the %r spelling survived" % spelling)

    def test_02d_emails_phones_and_record_ids_go_too(self):
        payload = {'data': [{
            'employee': 'Nguyễn Thị Mai',
            'contact': 'ha.nguyen+pay@payobook.com',
            'phone': '+84 912 345 678',
            'other': '0912 345 678',
            'ref': 'see #10421 and id 123456789',
        }]}
        redacted, _m = redact_names(payload)
        row = redacted['data'][0]
        self.assertEqual(row['contact'], '[email]')
        self.assertEqual(row['phone'], '[phone]')
        self.assertEqual(row['other'], '[phone]')
        self.assertEqual(row['ref'], 'see [record] and id [number]')

    def test_02e_a_figure_is_not_a_person(self):
        """Money in these payloads is a JSON number, never a string, so it is
        never seen by the string pass — and a redaction that removed the
        totals would make every answer useless while protecting nobody."""
        redacted, _m = redact_names(INDIVIDUAL_PAYLOAD)
        self.assertEqual(redacted['data'][1]['salary'], 18500000.0)
        self.assertEqual(redacted['total_employees'], 3)

    # -- 3. the exact prompt ----------------------------------------------
    def test_03_the_data_query_prompt_is_clean_end_to_end(self):
        """The whole string, as the provider would receive it."""
        redacted, mapping = redact_names(INDIVIDUAL_PAYLOAD)
        message = redact_text(
            "why does Nguyễn Thị Mai earn less than Tran Van Hung?", mapping)
        prompt = data_query_prompt(
            message, json.dumps(redacted, indent=2, ensure_ascii=False, default=str))
        self.assertFalse(_leaks(prompt),
                         "the prompt carries: %s" % _leaks(prompt))
        self.assertIn('[person-1]', prompt)
        self.assertIn('[person-2]', prompt)
        self.assertIn('placeholders', prompt,
                      "the model was not told what the placeholders are")

    def test_03b_the_question_is_redacted_with_the_same_mapping(self):
        """A name that leaves in the question is as gone as one that leaves in
        the payload, and it has to be the SAME placeholder or the model is
        being asked about two different people."""
        _r, mapping = redact_names(INDIVIDUAL_PAYLOAD)
        self.assertEqual(
            redact_text("compare Nguyễn Thị Mai with Nguyen Thi Mai", mapping),
            "compare [person-1] with [person-1]")

    def test_03c_the_pulse_prompt_is_clean_end_to_end(self):
        details, mapping = redacted_details(
            json.dumps(PULSE_DETAILS, ensure_ascii=False))
        prompt = pulse_summary_prompt(
            '2 New Employees Joined This Week', 'headcount', 'info',
            2.0, 0.0, 0.0, details)
        self.assertFalse(_leaks(prompt),
                         "the pulse prompt carries: %s" % _leaks(prompt))
        self.assertIn('[person-1]', prompt)
        self.assertIn('IT Services', prompt,
                      "the department was redacted — it is not a person, and "
                      "without it the summary has no subject")
        self.assertEqual(len(mapping), 2)

    def test_03d_a_details_field_that_is_not_json_is_still_cleaned(self):
        text, _m = redacted_details(
            'free text about ha.nguyen@payobook.com and #99123')
        self.assertEqual(text, 'free text about [email] and [record]')

    # -- 4. the round trip -------------------------------------------------
    def test_04_restore_puts_the_people_back(self):
        _r, mapping = redact_names(INDIVIDUAL_PAYLOAD)
        reply = "[person-2] earns the most, then [person-3], then [person-1]."
        self.assertEqual(
            restore_names(reply, mapping),
            "Trần Văn Hùng earns the most, then Đỗ Thị Lan, then Nguyễn Thị Mai.")

    def test_04b_restore_reaches_a_chart_label(self):
        _r, mapping = redact_names(INDIVIDUAL_PAYLOAD)
        result = {
            'response': 'The highest paid is [person-2].',
            'chart': {'data': {'labels': ['[person-1]', '[person-2]'],
                               'datasets': [{'label': 'Salary',
                                             'data': [12000000, 18500000]}]}},
            'insights': ['[person-3] is mid-range.'],
        }
        out = restore_deep(result, mapping)
        self.assertEqual(out['chart']['data']['labels'],
                         ['Nguyễn Thị Mai', 'Trần Văn Hùng'])
        self.assertEqual(out['insights'], ['Đỗ Thị Lan is mid-range.'])
        self.assertNotIn('[person-', json.dumps(out, ensure_ascii=False))

    def test_04c_a_placeholder_nobody_issued_is_left_alone(self):
        """`[person-1]` is a PREFIX of `[person-10]`, so a loop over the
        mapping renames the eleventh person to "Nguyễn Thị Mai0". One regex
        over the whole placeholder cannot do that — and a number the mapping
        does not know is left exactly as the model wrote it, because inventing
        a name for it is the one outcome worse than a visible placeholder."""
        mapping = {'[person-1]': 'Nguyễn Thị Mai'}
        self.assertEqual(restore_names('[person-10] and [person-1]', mapping),
                         '[person-10] and Nguyễn Thị Mai')

    def test_04d_an_empty_mapping_changes_nothing(self):
        """The ordinary case: an aggregate answer has no names in it at all."""
        payload = {'data': [{'department': 'Retail', 'total_salary': 1}]}
        redacted, mapping = redact_names(payload)
        self.assertEqual(mapping, {})
        self.assertEqual(redacted, payload)
        self.assertEqual(restore_names('nothing to do here', mapping),
                         'nothing to do here')

    # -- 4e. generic_scrub, which is all three non-data paths ever get -----
    def test_04e_generic_scrub_covers_contact_details_and_money(self):
        """No mapping needed and none available. The intent classifier runs
        before any query, and the knowledge / onboarding / general paths never
        build a mapping at all — so this is the whole protection those calls
        have, and what it does is stated exactly rather than approximately."""
        cases = [
            ("mail me at ha.nguyen+pay@payobook.com", "mail me at [email]"),
            ("call +84 912 345 678 now", "call [phone] now"),
            ("0912 345 678", "[phone]"),
            ("see #10421", "see [record]"),
            ("id 123456789 is wrong", "id [number] is wrong"),
            ("she earns 12.000.000 ₫", "she earns [amount]"),
            ("12.000.000 đồng", "[amount]"),
            ("500.000 VND", "[amount]"),
            ("net was 4,200,000 last month", "net was [amount] last month"),
        ]
        for raw, expected in cases:
            self.assertEqual(generic_scrub(raw), expected, "scrub of %r" % raw)

    def test_04f_a_rate_and_a_headcount_survive_generic_scrub(self):
        """The same ruling pb_learn made: scrubbing a rate protects nobody and
        destroys the question. A grouped-digit run under five digits is a rate
        in Vietnamese decimal notation, not money."""
        for raw in ("what does 10,5% BHYT mean", "is 8% right for BHXH",
                    "why is the rate 1.5", "we have 48 people"):
            self.assertEqual(generic_scrub(raw), raw,
                             "a figure that is not money was scrubbed: %r" % raw)

    def test_04g_generic_scrub_cannot_remove_a_name_and_says_so(self):
        """The honest half. It has nothing to match a name against, which is
        why the residual is written into the module's own list rather than
        left for a reviewer to notice."""
        self.assertEqual(generic_scrub("about Nguyễn Thị Mai"),
                         "about Nguyễn Thị Mai")
        import odoo.addons.pb_payroll_ai_insights.models.ai_redaction as mod
        self.assertIn('PRIOR-TURN NAMES IN CONVERSATION HISTORY', mod.__doc__)
        self.assertIn('DICTIONARY KEYS: SUBSTITUTED, NEVER COLLECTED FROM',
                      mod.__doc__)

    # -- 4h. the per-conversation mapping (LEARNOS Phase 6) ----------------
    def test_04h_a_placeholder_means_the_same_person_across_three_turns(self):
        """THE PHASE 4 RESIDUAL, CLOSED, replayed offline.

        Three turns of one conversation. Turn 1 asks about the Retail payroll
        and learns two people. Turn 2 is a KNOWLEDGE question whose history
        carries turn 1's restored answer — which used to go out with the names
        in, because that path built no mapping. Turn 3 asks about a different
        department and meets a third person.

        What is asserted is what a conversation needs: the numbers are stable
        (so "[person-2] again" is the same person), the history is clean on a
        path that never reads a record, and the new person gets the next free
        number rather than colliding with an old one.
        """
        # --- turn 1: the data path builds the table -----------------------
        turn1 = {'data': [{'employee': 'Nguyễn Thị Mai', 'salary': 12000000.0},
                          {'employee': 'Trần Văn Hùng', 'salary': 18500000.0}]}
        _r1, mapping = redact_names(turn1, mapping={})
        self.assertEqual(mapping, {'[person-1]': 'Nguyễn Thị Mai',
                                   '[person-2]': 'Trần Văn Hùng'})
        # The answer the reader saw, with the names put back.
        answer1 = restore_names('[person-2] earns more than [person-1].', mapping)
        self.assertEqual(answer1, 'Trần Văn Hùng earns more than Nguyễn Thị Mai.')

        # --- turn 2: a knowledge question, history carries that answer ----
        history_out = redact_text(answer1, mapping)
        self.assertFalse(_leaks(history_out),
                         "a prior-turn name went back out: %s" % history_out)
        self.assertEqual(history_out,
                         '[person-2] earns more than [person-1].',
                         "the placeholders are not the same ones as turn 1")

        # --- turn 3: a new person joins the same conversation -------------
        turn3 = {'data': [{'employee': 'Đỗ Thị Lan', 'salary': 15000000.0},
                          # …and one from turn 1, spelled without tone marks,
                          # which is how a second query often returns it.
                          {'employee': 'Nguyen Thi Mai', 'salary': 12000000.0}]}
        _r3, mapping = redact_names(turn3, mapping=mapping)
        self.assertEqual(mapping['[person-3]'], 'Đỗ Thị Lan')
        self.assertEqual(len(mapping), 3,
                         "the unaccented spelling was filed as a fourth person")
        self.assertEqual(redact_text('and Nguyễn Thị Mai again', mapping),
                         'and [person-1] again')

    def test_04h2_two_people_who_fold_to_one_name_are_two_people(self):
        """THE SHIP-BLOCKER THE PHASE 6 REVIEW FOUND, and the reason the dedupe
        key is the ACCENTED spelling.

        `_ascii` folds tone marks, and Vietnamese tone marks are what
        distinguish `Hùng` from `Hưng`. The first draft treated a folded
        collision as "already mapped", so the second man was not in the mapping
        at all — and a name that is not in the mapping is a name in the prompt.
        Four pairs, because the reviewer reproduced it with four and one pair
        is a coincidence.

        NEGATIVE CONTROL, EXECUTED: reverting `extend_mapping` to fold-dedupe
        fails this test on the first surviving name; restoring it passes. Both
        runs are in the Phase 6 fix-round report.
        """
        redacted, mapping = redact_names(NEIGHBOUR_PAYLOAD)
        blob = json.dumps(redacted, ensure_ascii=False, default=str)
        self.assertFalse(_leaks(blob, NEIGHBOURS),
                         "a diacritic neighbour survived: %s"
                         % _leaks(blob, NEIGHBOURS))
        self.assertEqual(len(mapping), 8,
                         "eight people were merged into %d entries: %s"
                         % (len(mapping), mapping))
        self.assertEqual(len(set(mapping.values())), 8)
        # …and each one is still restorable to the right person.
        self.assertEqual(restore_names('[person-1] and [person-2]', mapping),
                         'Trần Văn Hùng and Trần Văn Hưng')

    def test_04h3_a_shared_fold_stops_matching_once_it_is_ambiguous(self):
        """The secondary lookup, and where it stands down. One accented
        spelling: the unaccented form is the same person. Two accented
        spellings that fold together: the unaccented form no longer names
        either of them, so it takes its own placeholder rather than being
        attributed to whichever arrived first. Redacted either way — the
        difference is only which placeholder, and guessing is the thing to
        avoid."""
        _r, one = redact_names({'data': [{'employee': 'Trần Văn Hùng'}]})
        _r, same = redact_names({'data': [{'employee': 'Tran Van Hung'}]},
                                mapping=one)
        self.assertEqual(len(same), 1, "an unaccented respelling forked")

        _r, two = redact_names({'data': [{'employee': 'Trần Văn Hùng'},
                                         {'employee': 'Trần Văn Hưng'}]})
        _r, three = redact_names({'data': [{'employee': 'Tran Van Hung'}]},
                                 mapping=two)
        self.assertEqual(len(three), 3,
                         "the ambiguous fold was attributed to one of them")
        self.assertFalse(_leaks(redact_text('Tran Van Hung was paid', three),
                                NEIGHBOURS),
                         "the ambiguous spelling was left in free text")

    def test_04i_extend_mapping_never_renumbers_and_never_reuses(self):
        """The two ways this could go wrong, stated separately. Renumbering
        breaks the restore of an answer already on screen; reusing a number
        puts one person's name on another person's sentence."""
        m = extend_mapping(['A Name'], {})
        m = extend_mapping(['B Name'], m)
        self.assertEqual(m, {'[person-1]': 'A Name', '[person-2]': 'B Name'})
        # A gap (the cap dropped [person-1]) must not be filled in.
        m2 = extend_mapping(['C Name'], {'[person-7]': 'G Name'})
        self.assertEqual(m2['[person-8]'], 'C Name')
        self.assertNotIn('[person-1]', m2)
        # A junk key is not a placeholder and cannot decide the next number.
        m3 = extend_mapping(['D Name'], {'not-a-placeholder': 'X'})
        self.assertEqual(m3['[person-1]'], 'D Name')

    def test_04j_a_name_used_as_a_dictionary_key_is_substituted_too(self):
        """Phase 6 widened the property to KEYS. The pulse keys `by_type` on a
        leave type and `dept_overtime` on a department — neither is a person —
        but a payload that keys anything on somebody who is ALSO a value in it
        used to hand the provider that name in full."""
        payload = {'data': [{'employee': 'Nguyễn Thị Mai', 'salary': 1}],
                   'by_person': {'Nguyễn Thị Mai': 3, 'Retail': 4}}
        redacted, mapping = redact_names(payload)
        blob = json.dumps(redacted, ensure_ascii=False)
        self.assertFalse(_leaks(blob), "a name survived as a key: %s" % blob)
        self.assertEqual(redacted['by_person'], {'[person-1]': 3, 'Retail': 4})
        self.assertEqual(mapping, {'[person-1]': 'Nguyễn Thị Mai'})

    def test_04k_a_key_that_is_only_a_key_is_the_stated_residual(self):
        """The honest half, and it is why `test_egress::test_02d` exists. A
        name that appears NOWHERE except as a key is never collected, because
        there is no honest way to tell a person's name from a department's."""
        payload = {'by_person': {'Nguyễn Thị Mai': 3}}
        redacted, mapping = redact_names(payload)
        self.assertEqual(mapping, {})
        self.assertEqual(redacted, payload)
        import odoo.addons.pb_payroll_ai_insights.models.ai_redaction as mod
        self.assertIn('SUBSTITUTED, NEVER COLLECTED FROM', mod.__doc__)

    # -- 4l. the PDF report, repaired and redacted in one change -----------
    def test_04l_the_report_section_prompt_is_clean_end_to_end(self):
        """The exact string one section sends, with the salary section's real
        shape in it. This path was DEAD for four phases; the day it was
        repaired it had to be clean, and this is the assertion that says so
        with no provider and no database."""
        redacted, mapping = redact_names(INDIVIDUAL_PAYLOAD['data'], mapping={})
        prompt = report_section_prompt(
            'Salary Distribution by Department',
            json.dumps(redacted, ensure_ascii=False, default=str))
        self.assertFalse(_leaks(prompt), "the report section prompt carries: %s"
                         % _leaks(prompt))
        self.assertIn('[person-1]', prompt)
        self.assertIn('18500000', prompt, "the figures were redacted away too")
        self.assertIn('placeholders', prompt)
        # …and the narrative the model writes comes back with the people in it.
        self.assertEqual(
            restore_names('[person-2] is the highest paid.', mapping),
            'Trần Văn Hùng is the highest paid.')

    def test_04m_the_executive_summary_shares_the_sections_mapping(self):
        """One mapping across the whole document, driven through the SHIPPED
        function rather than a loop this test writes.

        The first version of this test re-implemented the accumulation and
        therefore proved that the test could accumulate — which is exactly the
        shape the ledger keeps recording. `redact_sections` is what both the
        narrative pass and the executive summary call; if either stops calling
        it, `test_egress::test_02f` fails, and if IT stops accumulating, this
        does.
        """
        sections = [
            {'title': 'Salary Distribution', 'data': INDIVIDUAL_PAYLOAD['data']},
            {'title': 'Headcount', 'data': [
                {'name': 'Bùi Anh Tuấn', 'department': 'IT Services'},
                {'employee': 'Nguyễn Thị Mai', 'department': 'Retail'}]},
            {'title': 'Refused', 'data': {}, 'access_refused': True,
             'narrative': 'your role is not allowed to read that'},
        ]
        prepared, mapping = redact_sections(sections, {})
        self.assertEqual([s['title'] for s, _j in prepared],
                         ['Salary Distribution', 'Headcount'],
                         "an access-refused section was sent to be narrated")
        overview = "\n".join("- %s: %s" % (sec['title'], js[:SUMMARY_DATA_CHARS])
                             for sec, js in prepared)
        prompt = report_executive_prompt('2026-07-01', '2026-07-31', overview)
        self.assertFalse(_leaks(prompt),
                         "the executive summary prompt carries: %s" % _leaks(prompt))
        self.assertEqual(mapping['[person-1]'], 'Nguyễn Thị Mai',
                         "the second section renumbered the first section's people")
        self.assertEqual(mapping['[person-4]'], 'Bùi Anh Tuấn')
        self.assertIn('IT Services', prompt,
                      "the department was redacted — it is not a person")

    # -- 4n. the anomaly section's free-text summaries ---------------------
    def test_04n_a_restored_name_in_an_alert_summary_does_not_go_out(self):
        """THE SECOND SHIP-BLOCKER, executed.

        `summary` is prose this module wrote the names back INTO before
        storing it, and it is not a person key — so the collector never saw it
        and the whole section went out with the joiners named. The details are
        now redacted first and the sentence is redacted against the mapping
        they built.
        """
        alerts = [{
            'id': 1,
            'name': '2 New Employees Joined This Week',
            'severity': 'info',
            'category': 'headcount',
            'deviation_pct': 0.0,
            'details': json.dumps(PULSE_DETAILS, ensure_ascii=False),
            'summary': ('Bùi Anh Tuấn joined IT Services and Lê Thu Trang '
                        'joined Retail this week; headcount is up two.'),
        }]
        rows, mapping = alert_rows(alerts, {})
        blob = json.dumps(rows, ensure_ascii=False)
        self.assertFalse(_leaks(blob), "the summary carries: %s" % _leaks(blob))
        self.assertIn('[person-1]', rows[0]['summary'])
        self.assertIn('[person-2]', rows[0]['summary'])
        self.assertEqual(len(mapping), 2)
        # THE TITLE IS NOT A PERSON. It is built from a count and it has to
        # stay readable — a section heading reading "[person-3]" is unreadable
        # and protects nobody.
        self.assertEqual(rows[0]['name'], '2 New Employees Joined This Week')
        self.assertEqual(rows[0]['category'], 'headcount')

    def test_04n2_an_untraceable_summary_is_dropped_not_guessed_at(self):
        """When the provenance cannot be checked the sentence does not go.
        Three shapes: details that will not parse, details that are empty, and
        a person-naming detector whose details named nobody. The row keeps its
        title, severity and deviation, which is enough to narrate from."""
        base = {'id': 2, 'name': '3 New Employees Joined This Week',
                'severity': 'info', 'category': 'headcount',
                'deviation_pct': 0.0,
                'summary': 'Bùi Anh Tuấn and Lê Thu Trang joined this week.'}
        for details in ('not json at all', '', '{"total": 3}'):
            rows, mapping = alert_rows([dict(base, details=details)], {})
            blob = json.dumps(rows, ensure_ascii=False)
            self.assertFalse(_leaks(blob),
                             "details=%r let a name through: %s"
                             % (details[:20], _leaks(blob)))
            self.assertEqual(rows[0]['summary'], 'No AI summary available.',
                             "details=%r kept an untraceable summary" % details[:20])
            self.assertEqual(mapping, {})
            self.assertEqual(rows[0]['name'], base['name'])

    def test_04n3_a_summary_a_detector_cannot_name_people_in_survives(self):
        """The other direction, so the rule is not "drop every summary". An
        overtime alert keys on a DEPARTMENT and its summary is about a
        department — dropping it would cost the report its most useful
        sentence for nothing."""
        alerts = [{
            'id': 3, 'name': 'Overtime Spike in Retail: +42%',
            'severity': 'warning', 'category': 'overtime', 'deviation_pct': 42.0,
            'details': json.dumps({'department': 'Retail', 'current_ot': 9000000}),
            'summary': 'Overtime in Retail rose 42% against last month.',
        }]
        rows, mapping = alert_rows(alerts, {})
        self.assertEqual(rows[0]['summary'],
                         'Overtime in Retail rose 42% against last month.')
        self.assertEqual(mapping, {})

    # -- 5. the whole call path, with both ends stubbed --------------------
    def test_05_the_engine_itself_sends_a_clean_prompt(self):
        """The one test in this file that exercises `_process_data_query`.

        Everything above proves the REDACTOR works; this proves it is WIRED
        IN, which is a different claim and the one a bypass breaks. Both ends
        are stubs — the query layer returns the individual payload without
        touching a database, and the provider records what it was asked — so
        there is still no network here, only an `env`.

        NEEDS A DATABASE, and therefore does not run in the offline harness.
        The offline proof that the redaction is wired in is structural
        (`test_egress::test_01`), and the executed negative control fired
        there; this is the behavioural half, for the deploy-time run.
        """
        sent = []

        class _Provider:
            def generate_chat(self, messages, **kw):
                sent.append(messages)
                return json.dumps({
                    'response': '[person-2] is the highest paid.',
                    'chart': {'data': {'labels': ['[person-1]', '[person-2]']}},
                    'insights': [], 'follow_up_questions': [],
                })

            def _parse_json_response(self, raw):
                return json.loads(raw)

        Engine = self.env['payroll.ai.engine']
        self.patch(type(self.env['payroll.data.query']), 'query_for_message',
                   lambda self_, message, context=None: dict(INDIVIDUAL_PAYLOAD))
        out = Engine._process_data_query(
            _Provider(),
            "why does Nguyễn Thị Mai earn less than Tran Van Hung?",
            [{'role': 'assistant', 'content': 'Earlier: Đỗ Thị Lan is a Chef.'}],
            {})
        self.assertTrue(sent, "the provider was never called")
        wire = json.dumps(sent[0], ensure_ascii=False)
        self.assertFalse(
            _leaks(wire),
            "these reached the provider through the engine: %s" % _leaks(wire))
        # …and the reader gets the names back, in the narrative and the chart.
        self.assertIn('Trần Văn Hùng', out['response'])
        self.assertEqual(out['chart']['data']['labels'],
                         ['Nguyễn Thị Mai', 'Trần Văn Hùng'])

    # -- 6. the dead provider call ----------------------------------------
    def test_06_the_pulse_asks_for_a_method_that_exists(self):
        """Ticket 4, pulse half. `get_provider_instance` is not a method on
        `payroll.ai.config`; the call sat inside a bare except and turned a
        typo into a feature that was permanently and silently off."""
        Config = self.env['payroll.ai.config']
        self.assertTrue(hasattr(Config, 'get_provider'))
        self.assertFalse(
            hasattr(Config, 'get_provider_instance'),
            "get_provider_instance now exists — if PayAI grew the alias, the "
            "remaining call sites listed in the Phase 4 report can be closed")
