# WF2 P6e check on payobook.com (demo site), odoo-bin shell: the QA login's language goes
# en -> vi -> en; after each change a fresh page load (a new session takes the user's language, as
# a normal reload after the preference change does) asks the Workflow Studio for its words. The
# words must follow the language at once, and the address must not be cached for days.
# Prints the session ids so the shell script can also ask THROUGH the web server (nginx) with curl;
# the sessions are deleted at the end and the language is put back as it was.
import os

from werkzeug.test import Client
from werkzeug.wrappers import Response

from odoo import http
from odoo.service import security

host = os.environ.get('PROBE_HOST') or 'payobook.com'
qa = env['res.users'].sudo().search([('login', '=', 'qa.test@payobook.com')], limit=1)
if not qa:
    print('WORDS no QA login on this site')
else:
    before = qa.lang
    out, sids = [], []
    for lang in ('en_US', 'vi_VN', 'en_US'):
        qa.lang = lang
        env.cr.commit()
        s = http.root.session_store.new()
        s.update(http.get_default_session(), db=env.cr.dbname, _trace_disable=True)
        s.uid, s.login = qa.id, qa.login
        s.context = {'lang': lang}
        s.session_token = security.compute_session_token(s, env(user=qa.id))
        http.root.session_store.save(s)
        c = Client(http.root, Response)
        c.set_cookie('session_id', s.sid, domain=host)
        r = c.get('/pb_lifecycle/workflow/words', headers={'Host': host})
        body = r.get_data(as_text=True)
        out.append('%s %s etag=%s vi-words=%s' % (lang, r.status_code, (r.headers.get('ETag') or '')[-10:],
                                                   'Quy trình' in body))
        sids.append(s.sid)
        print('SID %s %s' % (lang, s.sid))
    qa.lang = before
    env.cr.commit()
    print('WORDS %s; language put back: %s' % (' | '.join(out), qa.lang == before))
