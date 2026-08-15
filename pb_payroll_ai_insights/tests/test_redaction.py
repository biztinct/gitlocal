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
    collect_names, generic_scrub, redact_names, redact_text, restore_deep,
    restore_names,
)
from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_engine import (
    data_query_prompt,
)
from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_pulse import (
    pulse_summary_prompt, redacted_details,
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
)


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
        self.assertIn('DICTIONARY KEYS ARE NEVER REDACTED', mod.__doc__)

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
