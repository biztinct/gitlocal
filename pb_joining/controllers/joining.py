from collections import OrderedDict, deque
from datetime import timedelta
from functools import wraps
import logging
import traceback
from threading import Lock
from time import monotonic

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools.image import image_data_uri
from odoo.addons.pb_new_hire.models.studio_docs import FILE_MAX, SECRET_FIELDS
from odoo.addons.pb_hiring.controllers.joining_pages import laptop_words
from werkzeug.exceptions import HTTPException
from psycopg2.extensions import TransactionRollbackError
from ..models.http import HEADERS

_logger = logging.getLogger(__name__)
ROUTE = dict(type='http', auth='public', website=True, sitemap=False, multilang=False)
WINDOWS = OrderedDict()
LOCK = Lock()


def limited(key, count, seconds, consume=True):
    now = monotonic()
    with LOCK:
        events = WINDOWS.setdefault(key, deque())
        while events and events[0] <= now - seconds:
            events.popleft()
        WINDOWS.move_to_end(key)
        if len(WINDOWS) > 4096:
            WINDOWS.popitem(last=False)
        if len(events) >= count:
            return True
        if consume:
            events.append(now)
        return False


def page(*, confirmed=True):
    def decorate(fn):
        @wraps(fn)
        def wrapped(self, token, **kw):
            try:
                with request.env.cr.savepoint():
                    response = self._dispatch_joining(fn, token, kw, confirmed)
            except UserError as exc:
                response = self._problem(str(exc))
            except (HTTPException, TransactionRollbackError):
                raise
            except Exception as exc:
                # Trace locations are sufficient for diagnosis without recording a submitted value.
                stack = [(f.name, f.lineno) for f in traceback.extract_tb(exc.__traceback__)]
                _logger.warning('Joining page could not finish: %s %s', type(exc).__name__, stack)
                response = self._problem(request.env._('That did not save. Open the link and try again.'))
            response.headers.update(HEADERS)
            return response
        return wrapped
    return decorate


class JoiningPages(http.Controller):
    def _dispatch_joining(self, fn, token, kw, confirmed):
        address = ('address', request.httprequest.remote_addr)
        if limited(address, 10, 600, False):
            return self._render(None, 'inactive')
        j, status = request.env['pb.joining']._for_token(token)
        if status != 'ok':
            limited(address, 10, 600)
            return self._render(None, 'inactive')
        installed = dict(request.env['res.lang'].sudo().get_installed())
        lang = j.lang if j.lang in installed else request.env.context.get('lang', 'en_US')
        request.update_context(lang=lang)
        j = j.with_env(request.env).sudo().with_company(j.company_id)
        if confirmed and not j._remembered(request.session):
            return self._back(j)
        if request.httprequest.method == 'POST':
            j._lock()
            if limited(('save', request.db, j.id), 120, 300):
                return self._problem(request.env._('Please wait a few minutes before trying again.'))
        if confirmed:
            now = fields.Datetime.now()
            if not j.last_seen_at or j.last_seen_at < now - timedelta(minutes=1):
                j.last_seen_at = now
        return fn(self, j, **kw)

    def _problem(self, sentence):
        return self._render(None, 'problem', problem=sentence)

    def _back(self, j, suffix=''):
        return request.redirect('/join/' + j.token + suffix, code=303)

    def _sections(self, j):
        _ = request.env._
        states = j._section_states()
        rows = [('personal', _('About you'), 'user', _('1 minute')),
                ('id_number', _('Your identity card'), 'idCard', _('Take a photo and type the number')),
                ('bank', _('Bank account'), 'landmark', _('Where your pay goes')),
                ('tax', _('Tax and social insurance'), 'receipt', _('Numbers you already have')),
                ('emergency', _('Emergency contact'), 'heart', _('Who to call')),
                ('papers', _('Your papers'), 'layers', _('Papers needed before you start')),
                ('sign', _('Sign your papers'), 'pen', _('Read and sign')),
                ('day', _('Your first day'), 'sun', _('When, where, what to bring'))]
        labels = {'done': _('Done'), 'returned': _('Sent back to fix'), 'later': _('To finish later')}
        out = []
        for key, title, icon, hint in rows:
            if key in states:
                state = states[key]
                out.append(dict(key=key, title=title, icon=icon, state=state, hint=labels.get(state, hint)))
        return out

    def _render(self, j, state, **extra):
        _ = request.env._
        tx = self._words()
        values = dict(state=state, tx=tx, first='', base='', page_lang=request.env.lang or 'en_US',
                      company='', logo='', sections=[], problem='', title=_('Before you join'), saved=False,
                      csrf=request.csrf_token(), languages=[], days=0, hr=_('HR'), masked='', mail_on=False,
                      code_error='', remaining=0, manager=False, note='', back=False)
        if j:
            values.update(first=j._first(), base='/join/' + j.token, company=j.company_id.name,
                          logo=image_data_uri(j.company_id.logo_web) if j.company_id.logo_web and not j.company_id.uses_default_logo else '',
                          masked=j._masked_email(), mail_on=j._can_email(), hr=j._contact().name or _('HR'))
        if j and state != 'code':
            values.update(sections=self._sections(j), job=j.job_title, first_day=j._day_label(),
                          days=(j.first_day - j._today()).days, progress=j.progress,
                          manager=j.manager_id.name, note=j.manager_note, bank_later=j.bank_later,
                          day=[v for v in (j.day_time, j.day_place, j.day_ask_for, j.day_bring) if v],
                          buddy=', '.join(j.offer_id.buddy_employee_ids.mapped('name')),
                          saved=bool(request.session.get('pbj_saved') == j.id),
                          sent_before=bool(j.submitted_at),
                          returns=[r.return_note for r in j.item_ids if r.state == 'returned'],
                          languages=[(k, n) for k, n in [('en_US', 'English'), ('vi_VN', 'Tiếng Việt'),
                                     ('id_ID', 'Bahasa Indonesia')] if k in dict(request.env['res.lang'].sudo().get_installed())])
        values.update(extra)
        response = request.render('pb_joining.phone', values)
        response.flatten()
        return response

    def _words(self):
        _ = request.env._
        return {'inactive': _('This link is not active'), 'new_link': _('Ask the person who sent it for a new one.'),
                'check': _('One quick check'), 'enter': _('Enter your code'), 'continue': _('Continue'),
                'new_code': _('Send me a new code'), 'wait': _('You can ask again in {time}'), 'opened': _('Opened with your code'), 'start': _('Start'),
                'saved': _('Saved'), 'before': _('Before you join'), 'save': _('Save and continue'), 'send': _('Send to HR'),
                'again': _('Send again'), 'done': _('done'), 'missing': _('Still needed'), 'back': _('Back'),
                'later': _('I do not have it with me. Remind me later'), 'none': _('I do not have one yet'),
                'upload': _('Add a paper'), 'replace': _('Replace'), 'change': _('Change'),
                'camera': _('Take a photo of your card'), 'reverse': _('Back of the card'), 'until': _('Valid until'),
                'no_end': _('My card has no end date'), 'issued': _('Issue date'), 'got': _('Got it'),
                'sent': _('Sent to HR'), 'bank_later': _('Bank account still to add'), 'day': _('Your first day'),
                'no_day': _('Your manager will send you the time and place before you start.'),
                'held': _('We already have this from your application.'), 'held_name': _('We already have your name, email and phone from your application. You will not be asked again.'),
                'ten': _('About 10 minutes.'), 'come_back': _('You can stop at any point and come back with the same link. Have your identity card, tax card and bank details nearby.'),
                'check_after': _('HR will check what you sent. If anything needs fixing you will get a message and it will show here.'),
                'optional': _('Only if you already have one'), 'together': _('Saved as you go.'),
                'later_ask': _('Add it before your first pay.'), 'language': _('Language'), 'remove': _('Remove'),
                'fix': _('HR asked you to fix these details.'), 'need_paper': _('Needed when you join'),
                'need_pay': _('Needed before your first pay'), 'if_have': _('If you have it'),
                'update_bank': _('Show fields for this country'), 'saving': _('Uploading…'),
                'fail_file': _('That file did not upload. Try again, or use a smaller photo.')}

    def _code_page(self, j, error=''):
        _ = request.env._
        recent = j.code_issues or []
        wait = max(0, int((fields.Datetime.to_datetime(recent[-1]) + timedelta(minutes=1) - fields.Datetime.now()).total_seconds())) if recent else 0
        if len(recent) >= 5:
            wait = max(wait, int((fields.Datetime.to_datetime(recent[-5]) + timedelta(hours=1) - fields.Datetime.now()).total_seconds()))
        email = j._can_email() and not j.code_by_hr and not j.code_delivery_failed
        return self._render(j, 'code', mail_on=email, remaining=wait, code_error=error,
                            intro=_('We sent a 6-digit code to %(email)s. It works for 10 minutes.', email=j._masked_email()) if email else
                            _('Enter the 6-digit code %(name)s gave you.', name=j._contact().name or _('HR')),
                            no_code=_('No code? Ask %(name)s to show you a new one.', name=j._contact().name or _('HR')),
                            only=_('This page is only for %(name)s. If that is not you, close it.', name=j._first()))

    @http.route('/join/<string:token>', methods=['GET'], **ROUTE)
    @page(confirmed=False)
    def home(self, j, **kw):
        _ = request.env._
        if not j._remembered(request.session):
            j._restore_device(request.session, request.httprequest.cookies.get('pbj_device'))
        if not j._remembered(request.session):
            result = j._issue(automatic=True)
            return self._code_page(j, _('Too many tries. Wait 15 minutes, then ask for a new code.') if result['status'] == 'locked' else '')
        if j.state in ('added', 'to_check'):
            return self._render(j, 'day_one' if j.state == 'added' else 'sent',
                                heading=_('Welcome aboard, %(name)s', name=j._first()) if j.state == 'added' else
                                _('All done, %(name)s. See you on %(date)s.', name=j._first(), date=j._day_label()),
                                signin=_('From today you use My Payobook. %(hr)s will give you your sign-in.', hr=j._contact().name))
        if not j.welcome_started:
            return self._render(j, 'welcome', heading=_('Welcome to %(company)s, %(name)s', company=j.company_id.name, name=j._first()),
                                subtitle=self._welcome_date(j),
                                manager_title=_('%(manager)s, your manager', manager=j.manager_id.name) if j.manager_id else _('Your manager'),
                                initials=''.join(w[0] for w in (j.manager_id.name or '').split()[:2]))
        return self._render(j, 'hub', done_line=_('%(n)s of %(m)s done', n=sum(v in ('done','later') for v in j._section_states().values()), m=len(j._section_states())),
                            timing=_('Saved as you go. You start in %(n)s days.', n=(j.first_day - j._today()).days) if j.first_day > j._today() else _('Saved as you go.'))

    def _welcome_date(self, j):
        days = (j.first_day - j._today()).days
        if days > 0:
            return request.env._('You start as %(job)s on %(date)s, in %(days)s days.', job=j.job_title, date=j._day_label(), days=days)
        if days == 0:
            return request.env._('You start as %(job)s today.', job=j.job_title)
        return request.env._('You start as %(job)s on %(date)s.', job=j.job_title, date=j._day_label())

    @http.route('/join/<string:token>/code', methods=['POST'], csrf=True, **ROUTE)
    @page(confirmed=False)
    def code(self, j, code='', **kw):
        result = j._verify(code)
        if result == 'ok':
            until = j._remember(request.session)
            response = self._back(j)
            response.set_cookie('pbj_device', j._device_cookie(until), max_age=14 * 86400,
                                path='/join/' + j.token, secure=True, httponly=True, samesite='Lax')
            return response
        _ = request.env._
        return self._code_page(j, {'locked': _('Too many tries. Wait 15 minutes, then ask for a new code.'),
                  'expired': _('That code has run out. Ask for a new one.'),
                  'wrong': _('That code is not right. You have %(n)s tries left.', n=5-j.code_tries)}[result])

    @http.route('/join/<string:token>/code/new', methods=['POST'], csrf=True, **ROUTE)
    @page(confirmed=False)
    def new_code(self, j, **kw):
        result = j._issue()
        if result['status'] in ('locked','wait'):
            return self._code_page(j, request.env._('Too many tries. Wait 15 minutes, then ask for a new code.') if result['status']=='locked' else request.env._('Please wait before asking for a new code.'))
        return self._back(j)

    @http.route('/join/<string:token>/start', methods=['POST'], csrf=True, **ROUTE)
    @page()
    def start(self, j, **kw):
        j.welcome_started = True
        return self._back(j)

    @http.route('/join/<string:token>/lang', methods=['POST'], csrf=True, **ROUTE)
    @page()
    def lang(self, j, lang='', **kw):
        if lang in ('en_US', 'vi_VN', 'id_ID') and lang in dict(request.env['res.lang'].sudo().get_installed()):
            j.lang = lang
        return self._back(j)

    def _section(self, j, key, fmt='', error=''):
        _ = request.env._
        section = next((s for s in self._sections(j) if s['key'] == key), None)
        if not section:
            return self._back(j)
        rows = j.item_ids.filtered(lambda r: r.available and r._section_key() == key)
        specs = {s['key']: s for s in j._catalogue()}
        items = []
        for row in rows:
            spec = specs[row.key]
            boxes = spec['fields']
            if key == 'bank':
                fmt = fmt or row._display({'name': 'bank_format'}) or spec['bank']['default']
                boxes = spec['bank']['fields'].get(fmt, boxes)
            inputs = []
            for box in boxes:
                val = row._display(box)
                if box['name'] == 'bank_format':
                    val = fmt
                elif box['name'] == 'private_phone' and not val:
                    val = j.phone or ''
                elif box['name'] == 'account_holder' and not val:
                    val = j.name
                inputs.append(dict(box, value=val, secret=box['name'] in SECRET_FIELDS,
                                   kept=bool(val and box['name'] in SECRET_FIELDS), none=box['name'] in (row.draft or {}).get('none', row.none_fields or [])))
            items.append(dict(spec, fields=inputs, editable=row._editable(), note=row.return_note,
                              issue_date=(row.draft or {}).get('dates', {}).get('issue_date', row.issue_date),
                              expiry_date=(row.draft or {}).get('dates', {}).get('expiry_date', row.expiry_date),
                              no_expiry=(row.draft or {}).get('dates', {}).get('no_expiry', row.no_expiry),
                              files=[{'id': a.id, 'name': a.name, 'size': a.file_size} for a in row.attachment_ids]))
        intro = {'emergency': _('Who should we call if something happens at work?'),
                 'bank': _('Your pay is sent here. The name on the account must match your identity card.'),
                 'tax': _('These are the numbers %(country)s asks for. Leave any you do not have yet; HR will help you get one.', country=j.payroll_country),
                 'id_number': _('Lay your card flat in good light.')}
        return self._render(j, 'section', section=section, key=key, items=items, title=section['title'],
                            laptop=bool(key == 'day' and j.offer_id.prejoin_ids.filtered(lambda r: r.kind == 'laptop' and r.state == 'open')),
                            laptop_tx=laptop_words(request.env) if key == 'day' else {},
                            can_edit_section=any(r._editable() for r in rows) or (key == 'day' and j.state in ('invited','filling') and not j.submitted_at),
                            back=True, problem=error, intro=intro.get(key, ''), fmt=fmt)

    @http.route('/join/<string:token>/s/<string:key>', methods=['GET'], **ROUTE)
    @page()
    def section(self, j, key, fmt='', **kw):
        return self._section(j, key, fmt)

    @http.route('/join/<string:token>/s/<string:key>', methods=['POST'], csrf=True, **ROUTE)
    @page()
    def save(self, j, key, **kw):
        if key == 'day' and kw.get('draft'):
            return self._back(j)
        if key == 'day' and j.state in ('invited', 'filling') and not j.submitted_at:
            if j.offer_id.prejoin_ids.filtered(lambda r: r.kind == 'laptop' and r.state == 'open'):
                self._answer_laptop(j, kw)
            j.day_opened = True
        else:
            specs = {s['key']: s for s in j._catalogue()}
            rows = j.item_ids.filtered(lambda r: r.available and r._section_key() == key and r._editable())
            if not rows:
                return self._back(j)
            if kw.get('format_only'):
                return self._section(j, key, kw.get('bank_format'))
            try:
                with request.env.cr.savepoint():
                    for row in rows:
                        spec = specs[row.key]
                        files = request.httprequest.files.getlist('upload_' + row.key)
                        for f in files:
                            if f and f.filename:
                                row._upload(spec, f.filename, f.read(FILE_MAX + 1), int(kw.get('replace_' + row.key) or 0))
                        values = dict(kw)
                        for field in set(row.values or {}) | set((row.draft or {}).get('fields', {})):
                            if field in SECRET_FIELDS and not values.get(field) and field not in request.httprequest.form.getlist('clear'):
                                values.pop(field, None)
                        for date in ('issue_date', 'expiry_date', 'no_expiry'):
                            values[date] = kw.get(row.key + '_' + date)
                        none = request.httprequest.form.getlist('none')
                        if kw.get('draft'):
                            row._draft(spec, values, none)
                        else:
                            row._save(spec, values, none, later=kw.get('later') == '1')
            except (UserError, ValueError) as exc:
                return self._section(j, key, kw.get('bank_format'), str(exc) if isinstance(exc, UserError) else request.env._('Check the date and try again.'))
        request.session['pbj_saved'] = j.id
        remaining = next((s['key'] for s in self._sections(j) if s['state'] in ('returned', 'empty')), '')
        return self._back(j, '#pbjp-row-' + remaining if remaining else '')

    @http.route(['/join/<string:token>/file', '/join/<string:token>/file/remove'], methods=['POST'], csrf=True, **ROUTE)
    @page()
    def file(self, j, key='', replace=0, **kw):
        row = j.item_ids.filtered(lambda r: r.key == key and r.available)
        if not row:
            return self._back(j)
        row._require_edit()
        if request.httprequest.path.endswith('/remove'):
            row.attachment_ids.filtered(lambda a: a.id == int(replace)).unlink()
            if row.state == 'saved':
                row.state = 'empty'
        else:
            f = request.httprequest.files.get('file')
            spec = next(s for s in j._catalogue() if s['key'] == key)
            if not f:
                raise UserError(request.env._('Choose a file.'))
            att = row._upload(spec, f.filename, f.read(FILE_MAX + 1), int(replace))
            if kw.get('json') == '1':
                return request.make_json_response({'saved': True, 'id': att.id, 'name': att.name, 'size': att.file_size})
        if kw.get('json') == '1':
            return request.make_json_response({'saved': True})
        return self._back(j, '/s/' + row._section_key())

    def _answer_laptop(self, j, kw):
        row = j.offer_id.prejoin_ids.filtered(lambda r: r.kind == 'laptop' and r.state == 'open')[:1]
        if row and not j.submitted_at and j.state in ('invited', 'filling'):
            row.submit_laptop(dict(kind=kw.get('kind'), keyboard=kw.get('keyboard'), screen=kw.get('screen'),
                                   extras=request.httprequest.form.getlist('extras'), note=kw.get('note', '')[:2000]))

    @http.route('/join/<string:token>/laptop', methods=['POST'], csrf=True, **ROUTE)
    @page()
    def laptop(self, j, **kw):
        self._answer_laptop(j, kw)
        return self._back(j, '/s/day')

    @http.route('/join/<string:token>/send', methods=['POST'], csrf=True, **ROUTE)
    @page()
    def send(self, j, **kw):
        j._send_to_hr()
        return self._back(j)
