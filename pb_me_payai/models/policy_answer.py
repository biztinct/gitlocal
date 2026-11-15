# -*- coding: utf-8 -*-
"""PayAI for employees: answers from the company's policy files, and only them.

OWNER RULING E5 (the narrower option): company policies ONLY, from the files
HR uploads. No personal figures (no leave balance, no payslip), no general
knowledge. Always says which policy it used. When it cannot answer from the
files it says so and offers "Ask HR" with the question filled in. Off by
default, switched on per company, with a daily limit per person and per
company and a count HR can see.

A SEPARATE PATH, on purpose (FACTS §6.5): nothing here calls the back-office
PayAI engine, its data queries or its actions. The only model this file reads
for an answer is `pb.policy.section`; it never reads a payslip, a leave, a
contract or any figure of the person who asks.

WHAT LEAVES THE SYSTEM (and the one function that sends it, `_send`):
  * a fixed instruction text (no company, no person),
  * the matching policy sections (company words HR published),
  * the question, after `generic_scrub` (emails, phones, long numbers,
    amounts) and the company's employee names replaced by placeholders.
Never the employee's name, login, email, id, department, job, or any record.
The egress test proves it on the exact messages handed to the provider.

THE AI ACCOUNT is the one this company already has (`payroll.ai.config`):
its own "Policy answers for employees" row first, else its own PayAI row.
Never another company's, never a document-reading engine. No row, no key:
HR sees "not set up yet" and employees see nothing.
"""
import json
import logging
import re

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.addons.pb_payroll_ai_insights.models.ai_redaction import (
    extend_mapping, generic_scrub, redact_text, restore_names,
)

from .policy_document import tokens

_logger = logging.getLogger(__name__)

#: The longest question accepted.
MAX_QUESTION = 500
#: At most this many sections go with a question.
TOP_SECTIONS = 3
#: The words of one section sent at most.
SECTION_SEND_CHARS = 1400
#: The answer's length the provider is asked for.
MAX_TOKENS = 600
#: Providers that need a key to work.
KEYED = ('openai', 'anthropic')
#: Names read for the scrub, at most.
MAX_NAMES = 20000

LANG_WORDS = {'vi_VN': 'Vietnamese', 'id_ID': 'Indonesian', 'en_US': 'English'}

#: The instruction text. Fixed, generic, and the same for every company: it
#: names no company and no person.
INSTRUCTIONS = (
    "You answer an employee's question about their employer's policies. "
    "Use ONLY the numbered policy excerpts given. Do not use any other "
    "knowledge, do not guess, and do not work out personal figures. If the "
    "excerpts do not answer the question, reply with exactly NO_ANSWER. "
    "Otherwise reply with JSON only: {\"answer\": \"<short answer in plain "
    "words>\", \"used\": [<numbers of the excerpts you used>]}. Write the "
    "answer in %(language)s."
)

OUTCOMES = ('answered', 'not_found', 'limit', 'failed')


class PbPolicyAnswer(models.AbstractModel):
    _name = 'pb.policy.answer'
    _description = 'Policy answers for employees'

    # ============================================================ readiness
    @api.model
    def _config(self, company):
        """The AI account for `company`, or an empty recordset. Its own
        policy-answers row first, then its own PayAI row; never another
        company's and never a document-reading engine."""
        Cfg = self.env['payroll.ai.config'].sudo()
        if not company:
            return Cfg.browse()
        for purpose in ('policy_answers', 'insights'):
            cfg = Cfg.search([('is_active', '=', True), ('purpose', '=', purpose),
                              ('company_id', '=', company.id),
                              ('provider_type', '!=', 'tesseract')],
                             order='id', limit=1)
            if cfg and (cfg.provider_type not in KEYED or (cfg.api_key or '').strip()):
                return cfg
        return Cfg.browse()

    @api.model
    def _documents(self, employee):
        """The published policy files this employee's question may use."""
        employee = employee.sudo()
        docs = self.env['pb.policy.document'].sudo().search([
            ('company_id', '=', employee.company_id.id),
            ('published', '=', True)])
        dept = employee.department_id
        return docs.filtered(lambda d: not d.department_ids
                             or (dept and dept in d.department_ids))

    @api.model
    def _ready_for(self, employee):
        """True when this employee is offered PayAI on their pages at all:
        the company switched it on, has an AI account, and published at least
        one policy file that has words. Anything else: they see nothing."""
        if not employee:
            return False
        company = employee.sudo().company_id
        if not company.pb_policy_ai_on or not self._config(company):
            return False
        return bool(self._documents(employee).filtered('section_ids'))

    # ================================================================ search
    @api.model
    def _search(self, employee, question):
        """The best few sections for `question`, best first. A section must
        share at least two of the question's meaningful words (one for a
        one-word question); more shared words and a matching heading rank it
        higher. A long question full of greetings and contact details still
        finds its section."""
        words = tokens(question)
        if not words:
            return []
        docs = self._documents(employee)
        if not docs:
            return []
        lang = self.env.lang or 'en_US'
        sections = self.env['pb.policy.section'].sudo().search(
            [('document_id', 'in', docs.ids)])
        need = min(2, len(words))
        scored = []
        for sec in sections:
            keys = set((sec.keys or '').split())
            head = set((sec.heading_keys or '').split())
            hits = [w for w in words if w in keys]
            if len(hits) < need:
                continue
            score = len(hits) + 0.5 * len([w for w in words if w in head])
            if sec.document_id.language in (lang, 'any'):
                score += 0.25
            scored.append((score, sec))
        scored.sort(key=lambda pair: (-pair[0], pair[1].document_id.id,
                                      pair[1].sequence))
        return [sec for _score, sec in scored[:TOP_SECTIONS]]

    # ================================================================ limits
    @api.model
    def _limit_reached(self, employee):
        """'person' / 'company' when a daily limit is used up, else ''.
        Only questions that reached the AI account count (they cost)."""
        employee = employee.sudo()
        company = employee.company_id
        today = fields.Date.context_today(self)
        Log = self.env['pb.policy.question'].sudo()
        mine = Log.search_count([('employee_id', '=', employee.id),
                                 ('day', '=', today), ('called_ai', '=', True)])
        if mine >= max(0, company.pb_policy_ai_person_day):
            return 'person'
        ours = Log.search_count([('company_id', '=', company.id),
                                 ('day', '=', today), ('called_ai', '=', True)])
        if ours >= max(0, company.pb_policy_ai_company_day):
            return 'company'
        return ''

    @api.model
    def _log(self, employee, outcome, called_ai=False, documents=None):
        employee = employee.sudo()
        self.env['pb.policy.question'].sudo().create({
            'company_id': employee.company_id.id,
            'employee_id': employee.id,
            'outcome': outcome,
            'called_ai': bool(called_ai),
            'document_ids': [(6, 0, (documents or self.env['pb.policy.document']).ids)],
        })

    # ================================================================ privacy
    @api.model
    def _scrub(self, employee, question):
        """(the question as it may leave, the name mapping that stays here).

        Out go: every full name of the company's people (the asker's first),
        the asker's own name parts and login name, then contact details, long
        numbers and amounts. The mapping never leaves the system; it puts
        names back into the answer for the person who asked."""
        employee = employee.sudo()
        names = []
        if employee.name:
            names.append(employee.name)
        if employee.user_id and employee.user_id.name:
            names.append(employee.user_id.name)
        others = self.env['hr.employee'].sudo().with_context(
            active_test=False).search_read(
                [('company_id', '=', employee.company_id.id)], ['name'],
                limit=MAX_NAMES)
        names += [row['name'] for row in others if row.get('name')]
        # The asker's own given names typed alone ("I am Mai, ...").
        names += [part for part in (employee.name or '').split() if len(part) >= 3]
        mapping = extend_mapping(names) if names else {}
        text = redact_text(question, mapping) if mapping else question
        return generic_scrub(text), mapping

    @api.model
    def _messages(self, sections, question_out):
        """The exact messages handed to the provider. Built from the scrubbed
        question and the policy sections only."""
        language = LANG_WORDS.get(self.env.lang or 'en_US', 'English')
        blocks = []
        for n, sec in enumerate(sections, start=1):
            title = sec.document_id.name or ''
            head = sec.heading if sec.heading and sec.heading != title else ''
            label = '%s — %s' % (title, head) if head else title
            blocks.append('[%s] %s\n%s' % (n, label, (sec.body or '')[:SECTION_SEND_CHARS]))
        return [
            {'role': 'system', 'content': INSTRUCTIONS % {'language': language}},
            {'role': 'user', 'content': 'Policy excerpts:\n\n%s\n\nQuestion: %s'
             % ('\n\n'.join(blocks), question_out)},
        ]

    @api.model
    def _send(self, config, messages):
        """THE ONE PLACE anything leaves the system for an answer. Tests
        replace it; nothing else in this module talks to a provider."""
        provider = config.get_provider()
        return provider.generate_chat(messages, max_tokens=MAX_TOKENS,
                                      temperature=0.1)

    @api.model
    def _parse(self, reply, count):
        """(answer, [indexes used]) or (None, []) for "not in the files"."""
        text = (reply or '').strip()
        if not text or 'NO_ANSWER' in text.upper().replace(' ', '_'):
            return None, []
        match = re.search(r'\{.*\}', text, re.S)
        if not match:
            return None, []
        try:
            data = json.loads(match.group(0))
        except (TypeError, ValueError):
            return None, []
        answer = str(data.get('answer') or '').strip()
        if not answer or answer.upper() == 'NO_ANSWER':
            return None, []
        used = []
        for n in data.get('used') or []:
            try:
                n = int(n)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= count and n - 1 not in used:
                used.append(n - 1)
        return answer[:3000], used or [0]

    # ================================================================== ask
    @api.model
    def ask(self, employee, question):
        """Answer `question` for `employee` (the session's own — the caller
        proved it). Returns a dict the page draws:

            {'state': 'answered' | 'not_found' | 'limit_person' |
                      'limit_company' | 'not_ready' | 'failed' | 'empty',
             'answer': Markup or '', 'sources': [{'title', 'section'}],
             'question': the question as typed}
        """
        question = (question or '').strip()[:MAX_QUESTION]
        out = {'state': 'empty', 'answer': '', 'sources': [], 'question': question}
        if not question:
            return out
        if not self._ready_for(employee):
            out['state'] = 'not_ready'
            return out
        sections = self._search(employee, question)
        if not sections:
            self._log(employee, 'not_found')
            out['state'] = 'not_found'
            return out
        limit = self._limit_reached(employee)
        if limit:
            self._log(employee, 'limit')
            out['state'] = 'limit_' + limit
            return out
        config = self._config(employee.sudo().company_id)
        question_out, mapping = self._scrub(employee, question)
        messages = self._messages(sections, question_out)
        try:
            reply = self._send(config, messages)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_payai: the AI account did not answer',
                            exc_info=True)
            self._log(employee, 'failed', called_ai=True)
            out['state'] = 'failed'
            return out
        answer, used = self._parse(reply, len(sections))
        if answer is None:
            self._log(employee, 'not_found', called_ai=True)
            out['state'] = 'not_found'
            return out
        answer = restore_names(answer, mapping)
        picked = [sections[i] for i in used]
        self._log(employee, 'answered', called_ai=True,
                  documents=self.env['pb.policy.document'].union(
                      *[s.document_id for s in picked]))
        out.update({
            'state': 'answered',
            'answer': Markup('<br/>').join(escape(line) for line in answer.splitlines() if line.strip()),
            'sources': [{'title': s.document_id.name or '',
                         'section': s.heading if s.heading != s.document_id.name else ''}
                        for s in picked],
        })
        return out

    # ============================================================ for HR
    @api.model
    def usage(self, company):
        """The counts HR sees: today and this month, per outcome."""
        today = fields.Date.context_today(self)
        first = today.replace(day=1)
        Log = self.env['pb.policy.question'].sudo()
        res = {}
        for key, domain in (('today', [('day', '=', today)]),
                            ('month', [('day', '>=', first)])):
            base = [('company_id', '=', company.id)] + domain
            res[key] = {o: Log.search_count(base + [('outcome', '=', o)])
                        for o in OUTCOMES}
            res[key]['all'] = sum(res[key][o] for o in OUTCOMES)
            res[key]['ai'] = Log.search_count(base + [('called_ai', '=', True)])
        return res
