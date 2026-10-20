# -*- coding: utf-8 -*-
"""LEARNREV P5a (S4) — what people asked and rated, as a report.

THE SECOND HERO: a thumbs-down on a field card, or a search that found
nothing, reaches the authors as a topic count in Learn > Settings the same
day. This model is the two halves of that, and nothing else.

WRITING (any internal user)
  `rpc_search_miss(query, lang)` — the Library's search found nothing. One
  `learn.event` row of kind `library_miss`, screen `library`, detail
  `h:<12 hex>`: a keyed hash of the folded, scrubbed phrase. The phrase itself
  is NEVER stored by this path. Only when the owner's collect-questions switch
  is on AND this person agreed (the same two gates `learn.question` enforces)
  is the scrubbed phrase also kept, as a `learn.question` row that did not
  match, so the report can print it. No new table; the event log and the
  question store already existed (handover non-goal).

READING (administrators only, asked again on the server)
  `report(days, lang)` — per screen and per field (P5b: and per lesson step /
  walkthrough card, rated through the same seam): thumbs up/down in the last
  `days` days; the helper's "no answer" counts per screen (topics only: that is
  all `coach_miss` carries); the top ten search phrases with no result.
  `export_csv(days, lang)` — the same numbers as one CSV file's text.

The report reads the event log as the administrator but with `sudo` on the log
only, because events are per-person rows. Nothing here returns a person: no
user, no name, only counts by screen, field and phrase.
"""
import csv
import hashlib
import hmac
import io
import re
import unicodedata
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

from .learn_content import text
from .learn_guide import FEEDBACK_KIND, STEP_PREFIXES, is_vi
from .learn_question import COLLECT_FLAG, _flag_on

MISS_KIND = 'library_miss'
HELPER_MISS_KIND = 'coach_miss'
SEARCH_SCREEN = 'library'
PHRASE_MAX = 80
DEFAULT_DAYS = 30
TOP_PHRASES = 10
_SPACES = re.compile(r'\s+')
_DANGEROUS = ('=', '+', '-', '@', '\t', '\r')


def fold(value):
    """Lower case, accents off, spaces collapsed, bounded: the form a phrase
    is hashed in, so 'Pay  Role' and 'pay role' count as one search."""
    s = unicodedata.normalize('NFD', str(value or '').lower().replace('đ', 'd'))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return _SPACES.sub(' ', s).strip()[:PHRASE_MAX]


def csv_cell(value):
    """A cell that a spreadsheet will not run as a formula."""
    s = '' if value is None else str(value)
    return "'" + s if s.startswith(_DANGEROUS) else s


class LearnFeedback(models.AbstractModel):
    _name = 'learn.feedback'
    _description = 'Payobook Learn — what people asked and rated'

    # ------------------------------------------------------------ writing
    @api.model
    def _phrase_id(self, folded):
        """`h:<12 hex>`: keyed with this database's own secret, so a phrase
        cannot be recovered from the log by hashing a word list."""
        secret = self.env['ir.config_parameter'].sudo().get_param('database.secret') or ''
        digest = hmac.new(secret.encode(), folded.encode(), hashlib.sha256).hexdigest()
        return 'h:' + digest[:12]

    @api.model
    def _scrubbed(self, query):
        return self.env['learn.intent']._scrub(str(query or '')[:200]).strip()

    @api.model
    def rpc_search_miss(self, query, lang=None):
        """The Library's search found nothing for `query`. Returns True when a
        row was written. Too short or empty is not a search."""
        folded = fold(self._scrubbed(query))
        if len(folded) < 3:
            return False
        self.env['learn.event'].log(
            MISS_KIND, screen=SEARCH_SCREEN, detail=self._phrase_id(folded),
            lang='vi' if is_vi(lang) else 'en')
        # The words themselves: only with BOTH gates (tenant switch + this
        # person's own yes). `record` refuses quietly when either is missing.
        try:
            self.env['learn.question'].record(
                query, screen=SEARCH_SCREEN, matched=False,
                lang='vi' if is_vi(lang) else 'en')
        except AccessError:
            pass
        return True

    # ------------------------------------------------------------ reading
    @api.model
    def _check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._(
                "Only an administrator can read what people asked and rated."))

    @api.model
    def _events(self, kind, since):
        """`[(screen, detail, count)]` for one kind since `since`, in this
        person's companies. Read with sudo because the log is per-person;
        only counts leave."""
        Event = self.env['learn.event'].sudo()
        domain = [('kind', '=', kind), ('occurred_at', '>=', since),
                  ('company_id', 'in', self.env.companies.ids)]
        return [(screen or '', detail or '', count) for screen, detail, count
                in Event._read_group(domain, ['screen', 'detail'], ['__count'])]

    @api.model
    def _screen_name(self, key, lang):
        if key == SEARCH_SCREEN:
            return ''
        screen = self.env['learn.content'].screen(key)
        return text((screen or {}).get('name'), lang) or key

    @api.model
    def _field_labels(self, screen_key, lang):
        man = self.env['learn.guide'].manifest(screen_key) or {}
        return {f.get('key'): text(f.get('column'), lang) or f.get('key')
                for f in man.get('fields') or ()}

    @api.model
    def report(self, days=DEFAULT_DAYS, lang=None):
        self._check_admin()
        days = max(1, min(int(days or DEFAULT_DAYS), 365))
        lang = 'vi_VN' if is_vi(lang) else 'en_US'
        since = fields.Datetime.now() - timedelta(days=days)

        # -- thumbs, per screen and per field ---------------------------------
        by_screen = {}
        for screen, detail, count in self._events(FEEDBACK_KIND, since):
            key, _sep, verdict = detail.rpartition(':')
            if verdict not in ('up', 'down') or not key or not screen:
                continue
            row = by_screen.setdefault(screen, {'up': 0, 'down': 0, 'fields': {}})
            f = row['fields'].setdefault(key, {'up': 0, 'down': 0})
            f[verdict] += count
            row[verdict] += count
        thumbs = []
        Guide = self.env['learn.guide']
        for screen, row in by_screen.items():
            labels = self._field_labels(screen, lang)
            # LEARNREV P5b — a lesson step or a walkthrough card is rated
            # through the same seam; its row reads "<lesson> · Step 3: <title>".
            fields_ = [{'key': k,
                        'kind': 'step' if k.startswith(STEP_PREFIXES) else 'field',
                        'label': (Guide.step_label(k, lang) if k.startswith(STEP_PREFIXES)
                                  else labels.get(k) or k),
                        'up': v['up'], 'down': v['down']}
                       for k, v in row['fields'].items()]
            fields_.sort(key=lambda x: (-x['down'], -x['up'], x['label']))
            thumbs.append({'screen': screen, 'name': self._screen_name(screen, lang),
                           'up': row['up'], 'down': row['down'], 'fields': fields_})
        thumbs.sort(key=lambda x: (-x['down'], -x['up'], x['name']))

        # -- the helper had no answer (topics only) ---------------------------
        misses = {}
        for screen, detail, count in self._events(HELPER_MISS_KIND, since):
            row = misses.setdefault(screen or '', {'count': 0, 'topics': {}})
            row['count'] += count
            if detail:
                row['topics'][detail] = row['topics'].get(detail, 0) + count
        helper = [{'screen': s, 'name': self._screen_name(s, lang) if s else '',
                   'count': r['count'],
                   'topics': [{'topic': t, 'count': c} for t, c in
                              sorted(r['topics'].items(), key=lambda kv: -kv[1])[:5]]}
                  for s, r in misses.items()]
        helper.sort(key=lambda x: (-x['count'], x['name']))

        # -- searches that found nothing --------------------------------------
        collect = _flag_on(self.env, COLLECT_FLAG)
        words = {}
        if collect:
            Question = self.env['learn.question'].sudo()
            domain = [('screen', '=', SEARCH_SCREEN), ('matched', '=', False),
                      ('occurred_at', '>=', since),
                      ('company_id', 'in', self.env.companies.ids)]
            for question, _count in Question._read_group(domain, ['question'], ['__count']):
                words[self._phrase_id(fold(question))] = question
        phrases = {}
        for _screen, detail, count in self._events(MISS_KIND, since):
            phrases[detail] = phrases.get(detail, 0) + count
        top = sorted(phrases.items(), key=lambda kv: -kv[1])[:TOP_PHRASES]
        search = [{'id': pid, 'phrase': words.get(pid) or '', 'count': count}
                  for pid, count in top]

        return {
            'days': days, 'collect': collect, 'lang': lang,
            'totals': {
                'up': sum(t['up'] for t in thumbs),
                'down': sum(t['down'] for t in thumbs),
                'helper_miss': sum(h['count'] for h in helper),
                'search_miss': sum(phrases.values()),
            },
            'thumbs': thumbs, 'helper': helper, 'search': search,
        }

    @api.model
    def export_csv(self, days=DEFAULT_DAYS, lang=None):
        """The report as the text of one CSV file:
        `section, screen, item, up, down, count`. Re-checks the admin gate
        through `report`. Cells that would run as a formula get a quote."""
        data = self.report(days, lang)
        out = io.StringIO()
        w = csv.writer(out, lineterminator='\r\n')
        w.writerow(['section', 'screen', 'item', 'thumbs_up', 'thumbs_down', 'count'])
        for t in data['thumbs']:
            w.writerow(['rating', csv_cell(t['name']), '', t['up'], t['down'], t['up'] + t['down']])
            for f in t['fields']:
                w.writerow(['rating', csv_cell(t['name']), csv_cell(f['label']),
                            f['up'], f['down'], f['up'] + f['down']])
        for h in data['helper']:
            w.writerow(['helper_no_answer', csv_cell(h['name']), '', '', '', h['count']])
            for topic in h['topics']:
                w.writerow(['helper_no_answer', csv_cell(h['name']),
                            csv_cell(topic['topic']), '', '', topic['count']])
        for s in data['search']:
            w.writerow(['search_no_result', '', csv_cell(s['phrase'] or s['id']),
                        '', '', s['count']])
        return {'filename': 'learn-feedback-%s-days.csv' % data['days'],
                'csv': out.getvalue()}
