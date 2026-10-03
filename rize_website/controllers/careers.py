# -*- coding: utf-8 -*-
"""Rize careers list — /jobs with faceted filters.

The stock list (website_hr_recruitment) filters by office address only and,
on a first visit, silently narrows the list to the visitor's own country by
GeoIP — a candidate in Singapore looking at a Vietnam role never sees it. Rize
roles are placed by their hiring request's market, mostly carry no office or
job type, and should always open on every role. So this page owns its list:

- search      the stock fuzzy job search (same as before)
- team        hr.department, or "none"
- where       market country code: hiring request country, else office, else company
- type        hr.contract.type
- posted      7 / 30 (days)
- sort        "new" (newest first) / "az"; default keeps the stock order

Each facet counts with the OTHER facets applied (standard faceted search), and
a facet with fewer than two choices is not offered at all — a filter with one
option is noise. pb_hiring's attribution touch still runs first.
"""
from datetime import date
from urllib.parse import quote, urlencode

from odoo import fields, http
from odoo.http import request
from odoo.tools import html2plaintext

from odoo.addons.pb_hiring.controllers.application import HiringApplications

PER_PAGE = 20
FACETS = ('team', 'where', 'type', 'posted')


def _posted_label(d, today):
    if not d:
        return ''
    days = (today - d).days
    if days <= 0:
        return 'Posted today'
    if days == 1:
        return 'Posted yesterday'
    if days < 14:
        return 'Posted %d days ago' % days
    if days < 60:
        return 'Posted %d weeks ago' % (days // 7)
    return 'Posted %s' % d.strftime('%-d %b %Y')


class RizeCareers(HiringApplications):

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _rz_latest_requests(jobs):
        reqs = request.env['pb.hiring.requisition'].sudo().search(
            [('job_id', 'in', jobs.ids)], order='id desc')
        out = {}
        for req in reqs:
            out.setdefault(req.job_id.id, req)
        return out

    @staticmethod
    def _rz_card(job, req, today):
        country = (req.country_id if req else False) \
            or job.address_id.country_id or job.company_id.country_id
        summary = (req.jd_current_id.summary if req and req.jd_current_id else '') or ''
        if not summary and job.description:
            summary = html2plaintext(job.description or '')
        summary = ' '.join(summary.split())
        if len(summary) > 190:
            summary = summary[:187].rsplit(' ', 1)[0] + '…'
        posted = job.published_date or (job.create_date and job.create_date.date())
        city = job.address_id.city if job.address_id and job.address_id.country_id == country else ''
        return {
            'country': country,
            'where': ', '.join(p for p in (city, country.name if country else '') if p) or 'Remote',
            'summary': summary,
            'posted': posted,
            'posted_label': _posted_label(posted, today),
            'is_new': bool(posted) and (today - posted).days <= 7,
        }

    @staticmethod
    def _rz_keys(job, card, today):
        days = (today - card['posted']).days if card['posted'] else 10 ** 6
        return {
            'team': str(job.department_id.id) if job.department_id else 'none',
            'where': card['country'].code if card['country'] else 'none',
            'type': str(job.contract_type_id.id) if job.contract_type_id else 'none',
            'posted': {'7', '30'} if days <= 7 else ({'30'} if days <= 30 else set()),
        }

    @staticmethod
    def _rz_match(keys, picked, skip=None):
        for facet, value in picked.items():
            if facet == skip or not value:
                continue
            have = keys[facet]
            if value not in (have if isinstance(have, set) else {have}):
                return False
        return True

    # ------------------------------------------------------------ the page
    @http.route()
    def jobs(self, search=None, page=1, **kwargs):
        self._pb_hiring_touch(kwargs)
        env = request.env(context=dict(request.env.context, show_address=True, no_tag_br=True))
        website = request.website
        today = fields.Date.context_today(request.env.user) if request.env.user else date.today()

        _total, details, fuzzy = website._search_with_fuzzy(
            'jobs', search, limit=1000,
            order='is_published desc, sequence, no_of_recruitment desc',
            options={'displayDescription': True, 'allowFuzzy': not kwargs.get('noFuzzy')})
        found = details[0].get('results', env['hr.job']).sudo()
        # The headline numbers and "are there any roles at all" ignore the search
        # words: a search that matches nothing must say "no match", not "no roles".
        if search:
            _t, every, _f = website._search_with_fuzzy(
                'jobs', None, limit=1000, order='is_published desc, sequence',
                options={'displayDescription': False, 'allowFuzzy': False})
            every = every[0].get('results', env['hr.job']).sudo()
        else:
            every = found

        reqs = self._rz_latest_requests(found)
        cards = {j.id: self._rz_card(j, reqs.get(j.id), today) for j in found}
        keys = {j.id: self._rz_keys(j, cards[j.id], today) for j in found}

        picked = {f: (kwargs.get(f) or '').strip() for f in FACETS}
        if picked['posted'] not in ('7', '30'):
            picked['posted'] = ''

        # -- facets: counts with every OTHER facet applied
        def options(facet, label_of):
            counts, labels = {}, {}
            for j in found:
                if not self._rz_match(keys[j.id], picked, skip=facet):
                    continue
                k = keys[j.id][facet]
                counts[k] = counts.get(k, 0) + 1
                labels[k] = label_of(j)
            opts = [{'value': k, 'label': labels[k], 'count': c}
                    for k, c in counts.items() if k != 'none']
            opts.sort(key=lambda o: (-o['count'], o['label']))
            if 'none' in counts and opts:
                opts.append({'value': 'none', 'label': {
                    'team': 'Other teams', 'where': 'Anywhere', 'type': 'Not set'}[facet],
                    'count': counts['none']})
            return opts

        facets = []
        for facet, title, label_of in (
            ('team', 'Team', lambda j: j.department_id.name),
            ('where', 'Location', lambda j: cards[j.id]['country'].name if cards[j.id]['country'] else ''),
            ('type', 'Job type', lambda j: j.contract_type_id.name),
        ):
            opts = options(facet, label_of)
            if len(opts) >= 2 or picked[facet]:
                facets.append({'key': facet, 'title': title, 'options': opts})

        base = [j for j in found if self._rz_match(keys[j.id], picked, skip='posted')]
        week = sum(1 for j in base if '7' in keys[j.id]['posted'])
        month = sum(1 for j in base if '30' in keys[j.id]['posted'])
        if picked['posted'] or (len(base) > 1 and 0 < month < len(base)):
            facets.append({'key': 'posted', 'title': 'Posted', 'options': [
                {'value': '7', 'label': 'Past 7 days', 'count': week},
                {'value': '30', 'label': 'Past 30 days', 'count': month},
            ]})

        shown = [j for j in found if self._rz_match(keys[j.id], picked)]
        sort = kwargs.get('sort') if kwargs.get('sort') in ('new', 'az') else ''
        if sort == 'new':
            shown.sort(key=lambda j: cards[j.id]['posted'] or date.min, reverse=True)
        elif sort == 'az':
            shown.sort(key=lambda j: (j.name or '').lower())

        # -- active chips, each with the URL that removes it
        def url(key=None, value='', **changes):
            args = {'search': search or '', **picked, 'sort': sort}
            if key:
                changes[key] = value
            args.update(changes)
            q = urlencode([(k, v) for k, v in args.items() if v])
            return '/jobs' + ('?' + q if q else '')

        chips = []
        for f in facets:
            if picked[f['key']]:
                label = next((o['label'] for o in f['options'] if o['value'] == picked[f['key']]), 'This filter')
                chips.append({'label': label, 'url': url(f['key'], '')})
        if search:
            chips.insert(0, {'label': '“%s”' % search, 'url': url(search='')})

        pager = website.pager(
            url='/jobs', url_args={k: v for k, v in {'search': search, **picked, 'sort': sort}.items() if v},
            total=len(shown), page=int(page or 1), step=PER_PAGE)
        visible = env['hr.job'].sudo().browse([j.id for j in shown[pager['offset']:pager['offset'] + PER_PAGE]])

        public = every.filtered('is_published')
        teams = {j.department_id.id for j in public if j.department_id}
        every_reqs = self._rz_latest_requests(public - found) if search else {}
        markets = {(cards[j.id] if j.id in cards else self._rz_card(j, every_reqs.get(j.id), today))['country'].id
                   for j in public}
        markets.discard(False)
        where_opts = next((f['options'] for f in facets if f['key'] == 'where'), [])

        empty = env['hr.job']
        return request.render('website_hr_recruitment.index', {
            # stock keys, kept so any other inherit of the stock template still renders
            'jobs': visible, 'pager': pager, 'search': fuzzy or search, 'search_count': len(shown),
            'country_id': False, 'department_id': empty.department_id, 'office_id': False,
            'contract_type_id': empty.contract_type_id, 'industry_id': False,
            'is_remote': False, 'is_other_department': False, 'is_untyped': False,
            'is_industry_untyped': False,
            'count_per_office': {}, 'count_per_department': {}, 'count_per_employment_type': {},
            'count_per_industry': {}, 'count_per_country': {},
            # the Rize page
            'rz_cards': cards, 'rz_facets': facets, 'rz_picked': picked, 'rz_chips': chips,
            'rz_sort': sort, 'rz_url': url, 'rz_total': len(shown), 'rz_where_opts': where_opts,
            'rz_stats': {'roles': len(public), 'teams': len(teams), 'markets': len(markets)},
            'rz_any_roles': bool(every),
        })

    # ------------------------------------------------------------ one role
    @http.route()
    def job(self, job, **kwargs):
        response = super().job(job, **kwargs)
        qctx = getattr(response, 'qcontext', None)
        if qctx is None:
            return response
        today = fields.Date.context_today(request.env.user) if request.env.user else date.today()
        job_s = job.sudo()
        reqs = self._rz_latest_requests(job_s)
        qctx['rz_card'] = self._rz_card(job_s, reqs.get(job_s.id), today)
        # Up to three other open roles: same team first, then newest.
        others = request.env['hr.job'].sudo().search(
            [('id', '!=', job_s.id), ('is_published', '=', True),
             ('company_id', '=', request.website.company_id.id)],
            order='published_date desc, id desc', limit=30)
        others = others.filtered(lambda j: j.pb_hiring_accepts_applications(request.website))
        same = others.filtered(lambda j: j.department_id and j.department_id == job_s.department_id)
        more = (same | others)[:3] if same else others[:3]
        more_reqs = self._rz_latest_requests(more)
        qctx['rz_more'] = [(j, self._rz_card(j, more_reqs.get(j.id), today)) for j in more]
        # Share links point at the host the visitor is on (jobs.rize.farm once live).
        link = request.httprequest.url_root.rstrip('/') + request.httprequest.path
        enc = quote(link, safe='')
        title = quote('%s at %s' % (job_s.name, job_s.company_id.name), safe='')
        qctx['rz_share'] = {
            'url': link,
            'linkedin': 'https://www.linkedin.com/sharing/share-offsite/?url=%s' % enc,
            'whatsapp': 'https://wa.me/?text=%s%%20%s' % (title, enc),
            'mail': 'mailto:?subject=%s&body=%s' % (title, enc),
        }
        return response
