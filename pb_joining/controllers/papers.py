from time import time

from odoo import http
from odoo.http import request, content_disposition
from odoo.tools.misc import format_datetime

from .joining import JoiningPages, page, ROUTE


class JoiningPapers(JoiningPages):
    def _paper(self, j, paper):
        return j.sign_ids.filtered(lambda s: s.paper_id.id == paper and s.original_id)[:1]

    def _section(self, j, key, fmt='', error=''):
        if key != 'sign':
            return super()._section(j, key, fmt, error)
        if not j.sign_ids:
            return self._back(j)
        rows = [
            {
                'id': s.paper_id.id,
                'name': s.paper_name,
                'signed': bool(s.signed_on),
                'when': format_datetime(request.env, s.signed_on) if s.signed_on else '',
                'note': s.return_note,
            }
            for s in j.sign_ids
        ]
        return self._render(j, 'sign_list', title=request.env._('Sign your papers'), papers=rows, back=True)

    @http.route('/join/<string:token>/paper/<int:paper>', methods=['GET'], **ROUTE)
    @page()
    def read_paper(self, j, paper, **kw):
        s = self._paper(j, paper)
        if not s or s.signed_on or j.state not in ('invited', 'filling'):
            return self._back(j, '/s/sign')
        previous = request.session.get('pbj_last_signature') or {}
        recent = (
            j.sign_ids.filtered(lambda row: row.id == previous.get('id') and row.signed_on)
            if previous.get('until', 0) > time()
            else j.sign_ids.browse()
        )
        reuse_ink = (
            'data:image/png;base64,' + recent.signature.decode() if recent and recent.signature else ''
        )
        return self._render(
            j,
            'sign_paper',
            title=s.paper_name,
            back=True,
            signer=j.name,
            paper=s.paper_id.id,
            paper_open=bool(s.opened_at),
            reuse_ink=reuse_ink,
            agree=request.env._('I have read %(paper)s and I agree to it.', paper=s.paper_name),
        )

    @http.route('/join/<string:token>/paper/<int:paper>/pdf', methods=['GET'], **ROUTE)
    @page()
    def original(self, j, paper, **kw):
        s = self._paper(j, paper)
        if not s:
            return self._back(j, '/s/sign')
        s._record_open()
        return request.make_response(
            s.original_id.raw,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', content_disposition(s.original_id.name, disposition_type='inline')),
                ('X-Content-Type-Options', 'nosniff'),
            ],
        )

    @http.route('/join/<string:token>/paper/<int:paper>/sign', methods=['POST'], csrf=True, **ROUTE)
    @page()
    def sign_paper(self, j, paper, signature='', signer='', agree='', **kw):
        s = self._paper(j, paper)
        if not s:
            return self._back(j, '/s/sign')
        req = request.httprequest
        s._sign(signature, signer, agree, req.remote_addr, req.user_agent.string)
        request.session['pbj_last_signature'] = {'id': s.id, 'until': int(time()) + 1800}
        return self._back(j, '/s/sign')

    def _render(self, j, state, **extra):
        if j and state == 'hub':
            extra['returns'] = [r.return_note for r in j.item_ids if r.state == 'returned'] + [
                s.return_note for s in j.sign_ids if s.return_note
            ]
        return super()._render(j, state, **extra)

    def _words(self):
        _ = request.env._
        return dict(
            super()._words(),
            read_sign=_('Read and sign'),
            signed=_('Signed'),
            open_paper=_('Open the paper'),
            draw=_('Sign here with your finger'),
            clear=_('Clear'),
            signer=_('Your name as you sign it'),
            sign=_('Sign'),
            reuse=_('Use the signature I just drew'),
            no_script=_("Open this page in your phone's browser to sign."),
            next=_('Continue'),
        )
