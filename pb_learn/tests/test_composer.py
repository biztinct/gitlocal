# -*- coding: utf-8 -*-
"""The composer (Phase D2): the fences, and what is on the wire.

WHAT THIS FILE IS PROTECTING
----------------------------
For three phases the Coach could say nothing that an author had not written,
and that was assertable by the absence of a method. It is now assertable only
by the fences, so every fence gets a test:

  1. OFF unless a system parameter says otherwise, and off means the Phase C
     behaviour byte for byte — not "nearly", because a tenant who never turns
     this on must not be able to tell it was added.
  2. Reached only after curated retrieval and the column glossary have both
     missed, so a composed answer can never displace one somebody wrote.
  3. The advice deny-list runs BEFORE it, and is re-asked inside it — the
     path through `resolve()` depends on a record existing.
  4. What leaves this server is a SCRUBBED question and our own tutorial text.
     Never a record.
  5. The answer is discarded on any doubt, and badged when it is kept.

The provider is stubbed throughout. A test that needed a real model would be a
test nobody runs.
"""
import ast
import os

from odoo.addons.pb_learn.models.learn_intent import _is_advice
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import load_content

FLAG = 'pb_learn.compose_enabled'

# Every one of these was DEMONSTRATED past the Phase D deny-list in review, and
# every one is obviously a request for help reducing a statutory obligation.
# The first five are the reviewer's; the rest are the same shapes in Vietnamese
# and in the phrasings the fix has to survive.
ADVICE = (
    "how do I pay less BHXH",
    "làm sao giảm BHXH",
    "how do I reduce the BHXH base",
    "how do I not pay BHXH for probation staff",
    "tips to lower employer contributions",
    "lam sao de giam bhxh",
    "cach giam bao hiem xa hoi",
    "meo giam dong bao hiem",
    "khong dong bhxh cho nhan vien thu viec duoc khong",
    "tranh dong bhyt",
    "how can we cut the insurance base",
    "any way to save on PIT",
    "how do we avoid contributions for interns",
    # Still caught by the original marker list — kept so a rewrite of the
    # markers in favour of the pair rule cannot quietly drop them.
    "how do we pay less tax on salaries",
    "how do we under declare the insurance base",
    "làm sao để giảm đóng bhxh",
)


class _StubProvider:
    """Records what it was asked, answers what it was told to."""

    def __init__(self, reply='A composed sentence about this screen.'):
        self.reply = reply
        self.prompts = []

    def generate_text(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@tagged('post_install', '-at_install')
class TestComposer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intent = cls.env['learn.intent']
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'models', 'learn_intent.py'),
                  encoding='utf-8') as fh:
            cls.src = fh.read()

    def _on(self):
        self.env['ir.config_parameter'].sudo().set_param(FLAG, 'True')

    def _off(self):
        self.env['ir.config_parameter'].sudo().set_param(FLAG, 'False')

    def _stub(self, reply='A composed sentence about this screen.'):
        provider = _StubProvider(reply)
        self.patch(type(self.Intent), '_provider',
                   lambda self_, *a, **k: provider)
        return provider

    # -- 1. the flag ------------------------------------------------------
    def test_01_absent_parameter_means_off(self):
        """The state of every database the moment it is upgraded."""
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', FLAG)]).unlink()
        self.assertFalse(self.Intent._compose_enabled())
        self.assertIsNone(self.Intent._compose('anything', 'payslips'))

    def test_01b_only_an_affirmative_value_turns_it_on(self):
        Param = self.env['ir.config_parameter'].sudo()
        for raw in ('', 'False', 'false', '0', 'no', 'off', 'maybe', ' '):
            Param.set_param(FLAG, raw)
            self.assertFalse(self.Intent._compose_enabled(),
                             "%r switched the composer on" % raw)
        for raw in ('1', 'true', 'True', 'yes', 'ON', ' true '):
            Param.set_param(FLAG, raw)
            self.assertTrue(self.Intent._compose_enabled(),
                            "%r did not switch the composer on" % raw)

    def test_02_with_the_flag_off_nothing_is_asked_of_a_provider(self):
        """Off must mean off all the way down.

        `_compose` returns before `_provider` is consulted, so a database with
        PayAI configured and this flag unset never makes a call — which is
        also what makes the Phase C behaviour claim checkable rather than
        merely stated.
        """
        provider = self._stub()
        self._off()
        res = self.Intent.ask("how do I change the office wifi password", 'payslips')
        self.assertFalse(res['matched'])
        self.assertEqual(provider.prompts, [],
                         "a prompt was built with the composer switched off")

    def test_02b_flag_off_is_the_phase_C_miss_exactly(self):
        """The miss payload must be identical, key for key."""
        self._stub()
        self._off()
        res = self.Intent.ask("how do I change the office wifi password", 'payslips')
        self.assertEqual(set(res), {'matched', 'capability', 'suggest'},
                         "the miss payload changed shape")
        self.assertFalse(res['matched'])
        self.assertNotIn('source_kind', res)

    # -- 2. ordering ------------------------------------------------------
    def test_03_a_curated_intent_still_wins(self):
        """A composed answer must never displace one somebody wrote."""
        provider = self._stub()
        self._on()
        res = self.Intent.ask("what should I do next here", 'payruns')
        self.assertTrue(res['matched'])
        self.assertNotEqual(res.get('source_kind'), 'composed',
                            "the composer answered over a curated intent")
        self.assertEqual(provider.prompts, [],
                         "the composer ran even though retrieval had an answer")

    def test_03b_the_source_order_in_ask_is_retrieval_then_column_then_compose(self):
        """Read off the source, because the order is the guarantee.

        A behavioural test can only sample; this asserts the sequence itself.
        """
        body = self.src.split('def ask(')[1].split('\n    @api.model')[0]
        at_resolve = body.index('self.resolve(')
        at_column = body.index('self._match_column(')
        at_compose = body.index('self._compose(')
        at_miss = body.index("'matched': False")
        self.assertLess(at_resolve, at_column, "the column glossary runs before retrieval")
        self.assertLess(at_column, at_compose, "the composer runs before the column glossary")
        self.assertLess(at_compose, at_miss, "the honest miss runs before the composer")

    # -- 3. the deny-list -------------------------------------------------
    def test_04_an_advice_question_never_reaches_the_composer(self):
        """Even with the flag on, and even with no compliance intent at all.

        `resolve()` refuses advice by returning the `compliance` intent — but
        only if that content exists. Take it away and the refusal returns None,
        which falls through retrieval AND the column glossary. Without the
        second guard inside `_compose`, "how do I pay less BHXH" would arrive
        at a language model.

        The intent used to be a record that could be deactivated. It is a dict
        in a static tree now, so the absence is simulated by patching the
        lookup — which is a STRONGER version of the same test: it removes the
        content from every reader at once rather than from a `search` domain.
        """
        provider = self._stub()
        self._on()
        real = type(self.env['learn.content']).intent
        self.patch(type(self.env['learn.content']), 'intent',
                   lambda self_, key: None if key == 'compliance' else real(self_, key))
        for question in ADVICE:
            res = self.Intent.ask(question, 'payslips')
            self.assertNotEqual(
                res.get('source_kind'), 'composed',
                "an advice question was composed: %r" % question)
        self.assertEqual(
            provider.prompts, [],
            "an advice question was sent to a provider")

    def test_04b_the_guard_catches_the_phrasings_the_marker_list_missed(self):
        """The Phase D review broke the deny-list by rephrasing, five times.

        A list of exact markers is a list of the phrasings that occurred to its
        author; every string below is obviously in scope and every one walked
        through. `_is_advice` now also pairs a statutory SUBJECT with a
        minimisation VERB, which is what all five have in common and what no
        amount of rewording removes.
        """
        for question in ADVICE:
            self.assertTrue(
                _is_advice(question),
                "the deny-list does not catch: %r" % question)

    def test_04c_neither_half_of_the_pair_is_suspicious_alone(self):
        """The guard has to stay narrow or it eats the questions this system
        exists for. A statutory word with no minimiser is the core use case;
        a minimiser with no statutory subject is somebody asking about a
        discount."""
        for question in ("what does BHXH mean", "what is BHXH", "bhxh la gi",
                         "what is the BHYT rate", "what is insurance",
                         "bao hiem y te la gi", "who pays BHTN",
                         "what is a contribution register",
                         "thue tncn tinh the nao",
                         "how do I pay less", "reduce it", "lower the number",
                         "how do I skip a row in the import",
                         "how do I save the payslip",
                         "what is the lower bracket"):
            self.assertFalse(
                _is_advice(question),
                "a legitimate question was refused as advice: %r" % question)

    def test_04d_no_shipped_trigger_phrase_trips_the_guard_except_compliances_own(self):
        """A widened guard that swallows the module's own trigger phrases makes
        the intents it swallows unreachable. The ONE phrase that must trip it
        belongs to the refusal itself."""
        tripped = []
        intents = load_content()['intents']
        self.assertTrue(intents, "the intent corpus is empty — this asserts nothing")
        for intent in intents:
            for phrase in intent['phrases']:
                if _is_advice(phrase):
                    tripped.append('%s: %s' % (intent['key'], phrase))
        self.assertTrue(
            all(t.startswith('compliance:') for t in tripped),
            "the guard swallowed a phrase belonging to another intent: %s"
            % [t for t in tripped if not t.startswith('compliance:')])

    # -- 4. what leaves this server ---------------------------------------
    def test_05_the_scrub_removes_people_and_money(self):
        """Asserted on the WHOLE output, not by substring.

        The Phase D version of this test checked `assertIn('[amount]', out)`,
        which "12.000.000 ₫" -> "[amount] ₫" passes — a redaction that visibly
        missed, waved through by an assertion too weak to see it. Every case
        below states the exact string the provider would receive.
        """
        cases = [
            ("why is Nguyễn Thị Mai's net only 4.200.000",
             "why is [name]'s net only [amount]"),
            ("tai sao luong cua Nguyen Thi Mai chi con 4,200,000",
             "tai sao luong cua [name] chi con [amount]"),
            ("mail me at ha.nguyen+pay@payobook.com about #10421",
             "mail me at [email] about [record]"),
            ("employee 1234567 is wrong", "employee [number] is wrong"),
            # F2 — the currency mark must go WITH the number it belongs to.
            ("12.000.000 ₫", "[amount]"),
            ("Đỗ Thị Lan earned 12.000.000 ₫", "[name] earned [amount]"),
            ("12.000.000 đồng", "[amount]"),
            ("500.000 VND", "[amount]"),
            # F3 — the spaced international form is the one people paste.
            ("+84 912 345 678", "[phone]"),
            ("0912 345 678", "[phone]"),
            ("+84912345678", "[phone]"),
            ("call +84-912-345-678 now", "call [phone] now"),
        ]
        for raw, expected in cases:
            self.assertEqual(self.Intent._scrub(raw), expected,
                             "scrub of %r" % raw)
        joined = ' '.join(self.Intent._scrub(raw) for raw, _e in cases)
        for leaked in ('Mai', 'Nguyễn', 'Nguyen', 'Lan', '4.200.000',
                       '4,200,000', '@payobook.com', '12.000.000', '500.000',
                       '₫', 'đồng', '912', '84'):
            self.assertNotIn(leaked, joined, "%r reached the prompt" % leaked)

    def test_05b_a_rate_survives_the_scrub(self):
        """Scrubbing a rate would protect nobody and destroy the question.

        "what does 10,5% mean" with the number removed is not a question any
        model can answer, and 10.5 is not anybody's personal data.
        """
        for raw in ("what does 10,5% BHYT mean", "is 8% right for BHXH",
                    "why is the rate 1.5"):
            self.assertEqual(self.Intent._scrub(raw), raw,
                             "a rate was scrubbed out of %r" % raw)

    def test_05c_the_question_is_bounded(self):
        self.assertEqual(len(self.Intent._scrub('x' * 5000)), 400)

    def test_06_the_corpus_is_our_own_content_and_is_bounded(self):
        corpus = self.Intent._corpus('payslips', 'en_US')
        self.assertTrue(corpus.strip(), "no corpus for a screen with a station")
        self.assertLessEqual(len(corpus), 12000)
        self.assertIn('SCREEN:', corpus)

    def test_06b_the_corpus_builder_touches_no_product_model(self):
        """Asserted on the AST, so a string built by concatenation cannot hide.

        This is the whole safety argument for sending anything at all: the
        material is what we wrote, and a join to a payroll table would put
        somebody's pay in a prompt.
        """
        tree = ast.parse(self.src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == '_corpus')
        models = set()
        for node in ast.walk(fn):
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)):
                models.add(node.slice.value)
        named = {m for m in models if '.' in m}
        rogue = {m for m in named if not m.startswith('learn.')}
        self.assertFalse(rogue, "the corpus reads a non-learn model: %s" % rogue)
        self.assertTrue(named, "the corpus scan found no models at all — it is broken")

    def test_07_the_prompt_carries_the_material_and_the_refusal_contract(self):
        provider = self._stub()
        self._on()
        self.Intent.ask("what is the shape of everything here", 'payslips')
        self.assertEqual(len(provider.prompts), 1, "the composer did not run")
        prompt = provider.prompts[0]
        self.assertIn('NO_ANSWER', prompt,
                      "the model was never told how to decline")
        self.assertIn('MATERIAL:', prompt)
        for promise in ('Never invent', 'Never give tax', 'Never claim to have'):
            self.assertIn(promise, prompt,
                          "the prompt dropped: %s" % promise)

    def test_07b_the_question_reaches_the_prompt_scrubbed(self):
        provider = self._stub()
        self._on()
        self.Intent.ask("why is Nguyễn Thị Mai's net only 4.200.000 here", 'payslips')
        prompt = provider.prompts[0] if provider.prompts else ''
        self.assertTrue(prompt, "the composer did not run")
        self.assertNotIn('Nguyễn Thị Mai', prompt, "a name reached the provider")
        self.assertNotIn('4.200.000', prompt, "an amount reached the provider")
        self.assertIn('[name]', prompt)

    # -- 5. what comes back -----------------------------------------------
    def test_08_a_composed_answer_is_badged(self):
        self._stub('Here is a sentence assembled from the guide.')
        self._on()
        res = self.Intent.ask("give me the overall shape of this screen please",
                              'payslips')
        if res.get('matched') and res.get('source_kind') != 'composed':
            self.skipTest("retrieval covered this question on this database")
        self.assertTrue(res['matched'])
        self.assertEqual(res['source_kind'], 'composed')
        self.assertTrue(res['blocks'], "a composed answer with nothing in it")
        self.assertEqual(res['show_me'], [],
                         "a composed answer offered to point at a control")

    def test_09_a_refusal_or_a_doubt_is_discarded(self):
        self._on()
        for reply in ('NO_ANSWER', '  NO_ANSWER  ', '', '   ',
                      'x' * 1600, Exception('provider exploded')):
            self._stub(reply)
            res = self.Intent.ask("give me the overall shape of this screen please",
                                  'payslips')
            self.assertNotEqual(
                res.get('source_kind'), 'composed',
                "a %r reply was kept" % (str(reply)[:20],))

    def test_10_no_provider_means_no_composed_answer(self):
        self.patch(type(self.Intent), '_provider', lambda self_, *a, **k: None)
        self._on()
        res = self.Intent.ask("give me the overall shape of this screen please",
                              'payslips')
        self.assertNotEqual(res.get('source_kind'), 'composed')

    def test_10b_the_provider_lookup_never_raises(self):
        """A soft dependency that throws is a hard dependency with extra steps."""
        try:
            self.Intent._provider()
        except Exception as exc:                              # noqa: BLE001
            self.fail("_provider raised %s: %s" % (type(exc).__name__, exc))

    def test_11_the_badge_string_ships_in_both_languages(self):
        pair = load_content()['chrome'].get('composedAnswer')
        self.assertTrue(pair, "the composed badge has no chrome string")
        self.assertTrue(pair['en'] and pair['vi'])
        self.assertNotEqual(pair['en'], pair['vi'],
                            "the badge reaches a Vietnamese reader in English")
        # And the server hands out the same two strings the browser reads.
        Content = self.env['learn.content']
        self.assertEqual(Content.chrome_text('composedAnswer', 'en_US'), pair['en'])
        self.assertEqual(Content.chrome_text('composedAnswer', 'vi_VN'), pair['vi'])
