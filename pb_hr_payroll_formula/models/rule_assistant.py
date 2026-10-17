# -*- coding: utf-8 -*-
""""Describe it in words" — the Rule Composer's drafting assistant.

Integrations Cycle 8. A payroll manager types

    sum Actual Pay Hour where OT Type is 150% and Approval Status is Approved

and gets the four step-cards filled in, ready to check and save. It NEVER
saves: a draft lands in the composer, the proof rail runs against real records
beside it, and the human presses the button.

WHY THIS IS NOT IN pb_formula_studio. The studio already owns an
OpenAI-compatible seam (`_llm_chat`, `_llm_propose`, `_validate_llm`), and the
obvious move is to import it. `pb_integrations` and this module do NOT depend
on `pb_formula_studio` — it depends on THEM — so importing would either invert
the dependency graph or reach for an addon that is not declared, which is how a
module-level import reorders the registry and breaks an unrelated database
(W126). What is shared instead is the CONFIGURATION: the same three
`ir.config_parameter` keys, so one API key powers both surfaces and an operator
never has to know there are two callers.

TRUST NOTHING. The studio's rule is that every referenced name must exist in
the real catalogue or the whole proposal is rejected, and it is repeated here
for a harder reason: a rule writes into `computed_data`, which a field mapping
reads, which a payslip uses. A hallucinated field name would not error — it
would resolve to nothing, the aggregate would skip every row, and the answer
would be a well-shaped 0 (W137's exact shape, on a new surface). So a proposal
whose fields are not all in the catalogue is discarded ENTIRELY rather than
repaired, and the deterministic mapper answers instead.
"""

import json
import logging
import re

try:
    import requests
except Exception:                                   # pragma: no cover
    requests = None

from odoo import api, models

from .api_transformation_rule import (
    CONDITION_OPS, GUIDED_RULE_TYPES, UNARY_OPS, VALUE_UNIT_CODES,
)

_logger = logging.getLogger(__name__)

# The SAME parameters the Mapping Studio's PayAI reads. Named here rather than
# imported for the dependency reason in the module docstring; the strings are
# the contract, and a test asserts they have not drifted.
LLM_BASE_URL = 'pb_formula_studio.llm_base_url'
LLM_API_KEY = 'pb_formula_studio.llm_api_key'
LLM_MODEL = 'pb_formula_studio.llm_model'
DEFAULT_BASE_URL = 'https://api.openai.com/v1'
DEFAULT_MODEL = 'gpt-4o-mini'


class RuleLLMUnavailable(Exception):
    """No key, no HTTP client, a timeout, a non-200 or unreadable JSON. The
    caller catches it and answers deterministically — an assistant that is
    unavailable degrades, it does not fail."""


_SYSTEM = (
    "You turn a plain-language request into ONE data-transformation rule for a "
    "payroll product. A rule takes records from a feed, keeps some of them, "
    "derives a single number and names it.\n"
    "Reply with STRICT JSON only, no prose, shaped exactly:\n"
    '{"rule_type":"count"|"sum"|"avg"|"min"|"max",'
    '"source_data_type":"<one of the feeds listed>",'
    '"record_source":"records"|"nested","nested_table_path":"<or empty>",'
    '"filter_conditions":{"join":"all"|"any","rows":['
    '{"field":"<exact field name>","op":"is"|"is_not"|"contains"|"present"'
    '|"blank"|"gt"|"gte"|"lt"|"lte","value":"<text>"}]},'
    '"value_steps":[{"field":"<exact field name>",'
    '"contains":"number"|"seconds"|"hmm"|"minutes"|"days"}],'
    '"name":"<short human name>","output_key":"<UPPERCASE, letters and digits '
    'only, no underscore>","reply":"<one sentence>"}\n'
    "Every field name MUST be copied EXACTLY from the catalogue given to you. "
    "Never invent one. For a count, value_steps is empty. Use contains=seconds "
    "when a field holds seconds, contains=hmm when it holds text like 7:30."
)


class HrApiRuleAssistant(models.AbstractModel):
    _name = 'hr.api.rule.assistant'
    _description = 'Transformation rule drafting assistant'

    # ------------------------------------------------------------------
    # the seam
    # ------------------------------------------------------------------
    @api.model
    def _llm_chat(self, messages, json_mode=True):
        """One OpenAI-compatible chat call. Missing key raises IMMEDIATELY,
        before any network call — the same shape and the same order as the
        studio's, so the two behave identically when a key is removed."""
        if requests is None:
            raise RuleLLMUnavailable("HTTP client 'requests' is not available")
        params = self.env['ir.config_parameter'].sudo()
        api_key = (params.get_param(LLM_API_KEY) or '').strip()
        if not api_key:
            raise RuleLLMUnavailable("No assistant key configured")
        base_url = (params.get_param(LLM_BASE_URL) or DEFAULT_BASE_URL).strip().rstrip('/')
        model = (params.get_param(LLM_MODEL) or DEFAULT_MODEL).strip()
        payload = {'model': model, 'messages': messages, 'temperature': 0}
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
        try:
            response = requests.post(
                base_url + '/chat/completions',
                headers={'Authorization': 'Bearer ' + api_key,
                         'Content-Type': 'application/json'},
                json=payload, timeout=25)
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
        except Exception as error:
            raise RuleLLMUnavailable('assistant call failed: %s' % error)
        if not json_mode:
            return content
        try:
            return json.loads(content)
        except Exception as error:
            raise RuleLLMUnavailable('assistant returned unreadable JSON: %s' % error)

    @api.model
    def assistant_status(self):
        params = self.env['ir.config_parameter'].sudo()
        return {'llm': bool((params.get_param(LLM_API_KEY) or '').strip())}

    # ------------------------------------------------------------------
    # the front door
    # ------------------------------------------------------------------
    @api.model
    def propose(self, text, catalog, feeds):
        """A sentence -> a DRAFT spec. Never writes anything, ever.

        `catalog` is `[{'path', 'label', 'feed_type', 'sample'}]` — the real
        fields of the real connector. `feeds` is the list of data types those
        fields live in. Returns
        `{'ok', 'spec'|'error', 'source': 'ai'|'deterministic', 'reply'}`.
        """
        text = (text or '').strip()
        if not text:
            return {'ok': False, 'error': 'Say what the rule should work out.',
                    'source': 'deterministic'}
        try:
            data = self._llm_chat([
                {'role': 'system', 'content': _SYSTEM},
                {'role': 'user', 'content':
                    'Feeds: ' + json.dumps(sorted(feeds), ensure_ascii=False) +
                    '\nFields: ' + json.dumps(
                        [{'name': f.get('path'), 'label': f.get('label'),
                          'feed': f.get('feed_type'), 'example': f.get('sample')}
                         for f in catalog][:400], ensure_ascii=False) +
                    '\n\nRequest: ' + text},
            ])
        except RuleLLMUnavailable as error:
            _logger.info("Rule assistant unavailable, drafting locally: %s", error)
            return self._deterministic(text, catalog, feeds)

        spec = self._validate(data, catalog, feeds)
        if not spec:
            # Rejected WHOLE (see the module docstring). The user still gets a
            # draft, and it is one whose every name came off the catalogue.
            return self._deterministic(text, catalog, feeds)
        return {'ok': True, 'spec': spec, 'source': 'ai',
                'reply': str(data.get('reply') or '')[:240]}

    # ------------------------------------------------------------------
    # validation — the half that makes the other half safe
    # ------------------------------------------------------------------
    @staticmethod
    def _norm(name):
        return re.sub(r'[\s_.\-]+', '', str(name or '')).casefold()

    @api.model
    def _validate(self, data, catalog, feeds):
        """Every name in, or nothing out. Returns a clean spec or None."""
        try:
            if not isinstance(data, dict):
                return None
            by_norm = {self._norm(f.get('path')): f.get('path') for f in catalog}

            rule_type = data.get('rule_type')
            if rule_type not in GUIDED_RULE_TYPES:
                return None
            source = data.get('source_data_type')
            if source not in feeds:
                return None

            record_source = data.get('record_source') or 'records'
            if record_source not in ('records', 'nested'):
                return None
            nested_path = (data.get('nested_table_path') or '').strip()
            if record_source == 'nested' and not nested_path:
                return None

            raw_filter = data.get('filter_conditions') or {}
            join = raw_filter.get('join') or 'all'
            if join not in ('all', 'any'):
                return None
            rows = []
            for row in (raw_filter.get('rows') or []):
                op = row.get('op') or 'is'
                if op not in CONDITION_OPS:
                    return None
                path = by_norm.get(self._norm(row.get('field')))
                if not path:
                    return None                 # a field nobody has: reject ALL
                clean = {'field': path, 'op': op}
                if op not in UNARY_OPS:
                    clean['value'] = '' if row.get('value') is None else str(row['value'])
                rows.append(clean)

            steps = []
            for step in (data.get('value_steps') or []):
                path = by_norm.get(self._norm(step.get('field')))
                if not path:
                    return None
                unit = step.get('contains') or 'number'
                if unit not in VALUE_UNIT_CODES:
                    return None
                steps.append({'field': path, 'contains': unit})
            if rule_type != 'count' and not steps:
                return None
            if rule_type == 'count':
                steps = []

            return {
                'builder_mode': 'guided',
                'rule_type': rule_type,
                'source_data_type': source,
                'record_source': record_source,
                'nested_table_path': nested_path,
                'filter_conditions': {'join': join, 'rows': rows},
                'value_steps': steps,
                'name': str(data.get('name') or 'New rule')[:80],
                'output_key': self._clean_key(data.get('output_key') or data.get('name')),
                'default_value': 0.0,
            }
        except Exception as error:              # noqa: BLE001
            _logger.warning("Rule assistant validation error: %s", error)
            return None

    @staticmethod
    def _clean_key(text):
        """A candidate output key in the shape the converter contract demands:
        uppercase, letters and digits, NO underscore. Not a guarantee of
        uniqueness — `rule_save` owns that, and owns the refusal."""
        key = re.sub(r'[^A-Za-z0-9]', '', str(text or '')).upper()
        return (key or 'NEWRULE')[:20]

    # ------------------------------------------------------------------
    # the deterministic floor
    # ------------------------------------------------------------------
    _VERBS = [
        (r'\b(count|how many|number of)\b', 'count'),
        (r'\b(sum|total|add up|adds up|add together)\b', 'sum'),
        (r'\b(average|avg|mean)\b', 'avg'),
        (r'\b(smallest|minimum|min|lowest|earliest)\b', 'min'),
        (r'\b(largest|maximum|max|highest|biggest)\b', 'max'),
    ]

    @api.model
    def _deterministic(self, text, catalog, feeds):
        """No key, or a proposal that failed validation: draft it here.

        A small grammar over the catalogue's own labels — "<verb> <field>
        where <field> is <value> and <field> is <value>". It is deliberately
        modest, and the UI SAYS which one answered, because a draft the user
        believes came from an assistant and did not is worse than no draft
        (W79's family: a fallback that is indistinguishable from the real thing
        is a lie the reader has no way to catch).
        """
        lowered = ' %s ' % (text or '').lower()
        rule_type = 'sum'
        for pattern, kind in self._VERBS:
            if re.search(pattern, lowered):
                rule_type = kind
                break

        # Split on "where" so a VALUE can never be read as a field name:
        # "sum Actual Pay Hour where OT Type is 150%" has two halves and the
        # second one is conditions, not fields to add up.
        halves = re.split(r'\bwhere\b', text or '', maxsplit=1, flags=re.I)
        head = halves[0]
        tail = halves[1] if len(halves) > 1 else ''

        matches = self._match_fields(head, catalog)
        source = matches[0]['feed_type'] if matches and matches[0].get('feed_type') else (
            sorted(feeds)[0] if feeds else 'custom')

        steps = []
        if rule_type != 'count':
            for field in matches[:2]:
                steps.append({'field': field['path'],
                              'contains': self._guess_unit(field)})

        rows = []
        for clause in re.split(r'\band\b', tail or ''):
            clause = clause.strip()
            if not clause:
                continue
            found = self._match_fields(clause, catalog)
            if not found:
                continue
            value = re.split(r'\b(is not|is|equals|=)\b', clause, maxsplit=1)
            wanted = value[-1].strip(' .,"\'') if len(value) > 2 else ''
            # the field's own name is often the head of the clause; drop it
            wanted = re.sub(re.escape(found[0]['label'] or ''), '', wanted,
                            flags=re.I).strip(' .,"\'')
            if not wanted:
                continue
            rows.append({'field': found[0]['path'],
                         'op': 'is_not' if ' is not ' in ' %s ' % clause.lower() else 'is',
                         'value': wanted})

        if rule_type != 'count' and not steps:
            return {'ok': False, 'source': 'deterministic',
                    'error': 'None of those field names are in this '
                             'connector — pick them from the list instead.'}

        name = (text or '').strip()[:60] or 'New rule'
        return {
            'ok': True, 'source': 'deterministic',
            'reply': 'Drafted from your words without the assistant — check '
                     'every step before you save it.',
            'spec': {
                'builder_mode': 'guided',
                'rule_type': rule_type,
                'source_data_type': source,
                'record_source': 'records',
                'nested_table_path': '',
                'filter_conditions': {'join': 'all', 'rows': rows},
                'value_steps': steps,
                'name': name,
                'output_key': self._clean_key(
                    ''.join(w[:4] for w in re.findall(r'[A-Za-z]+', name)[:3])),
                'default_value': 0.0,
            },
        }

    @api.model
    def _match_fields(self, text, catalog):
        """Catalogue entries whose path or label appears in `text`, longest
        name first so `Actual Pay Hour` beats `Hour`."""
        haystack = ' %s ' % re.sub(r'[\s_.\-]+', ' ', (text or '').lower())
        hits = []
        for field in catalog:
            for candidate in (field.get('label') or '', field.get('path') or ''):
                needle = re.sub(r'[\s_.\-]+', ' ', str(candidate).lower()).strip()
                if len(needle) >= 3 and needle in haystack:
                    hits.append((len(needle), field))
                    break
        hits.sort(key=lambda pair: -pair[0])
        seen, out = set(), []
        for _length, field in hits:
            if field.get('path') in seen:
                continue
            seen.add(field.get('path'))
            out.append(field)
        return out

    @staticmethod
    def _guess_unit(field):
        """What the catalogue itself suggests the field holds. A guess the user
        can see and change in one click — never a silent conversion."""
        name = str(field.get('path') or '').lower()
        sample = str(field.get('sample') or '')
        if re.match(r'^\d+:\d{1,2}$', sample.strip()):
            return 'hmm'
        if 'second' in name:
            return 'seconds'
        if 'minute' in name:
            return 'minutes'
        if name.endswith('days') or ' days' in name:
            return 'days'
        return 'number'
