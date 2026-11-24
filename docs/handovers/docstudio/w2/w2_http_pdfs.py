# DOCSTUDIO W2: the same PDFs the browser gets, through the running site (HTTP, as the QA login):
# the long built report, a contract document, the Vietnamese certificate and the long letter in "Clean".
# Nothing is saved (download / sample PDF only). Password read from a root-only file, never printed.
import base64, json, os, sys, requests
OUT = sys.argv[1]; RID = int(sys.argv[2])
pw = open(sys.argv[3]).read().strip()
s = requests.Session(); H = {'Host': 'payobook.com'}; B = 'http://127.0.0.1:8069'
def rpc(path, params):
    r = s.post(B + path, json={'jsonrpc': '2.0', 'method': 'call', 'params': params}, headers=H, timeout=600)
    j = r.json()
    if 'error' in j:
        raise SystemExit('RPC ERROR %s %s' % (path, j['error'].get('data', {}).get('message')))
    return j['result']
def kw(model, method, *args):
    return rpc('/web/dataset/call_kw/%s/%s' % (model, method), {'model': model, 'method': method, 'args': list(args), 'kwargs': {}})
u = rpc('/web/session/authenticate', {'db': 'payobook', 'login': 'qa.test@payobook.com', 'password': pw})
print('uid', u['uid'])
def save(name, res):
    if not res.get('ok'):
        print(name, 'FAILED', res.get('msg')); return
    open(os.path.join(OUT, name), 'wb').write(base64.b64decode(res['data'])); print(name, 'saved')
o = kw('pb.report.pdf', 'open', 'pb.report.definition', RID)
save('http_long_report.pdf', kw('pb.report.pdf', 'download', 'pb.report.definition', RID, o['look']))
k = kw('hr.contract', 'search', [['state', '=', 'open'], ['company_id', '=', 5]], 0, 1)
save('http_contract.pdf', kw('pb.contracts', 'contract_document_pdf', k[0]))
cert = kw('ir.model.data', 'search_read', [['module', '=', 'pb_me_letters'], ['name', '=', 'letter_template_employment_cert']], ['res_id'])[0]['res_id']
exp = kw('ir.model.data', 'search_read', [['module', '=', 'pb_lifecycle'], ['name', '=', 'letter_template_experience']], ['res_id'])[0]['res_id']
people = kw('pb.doc.studio', 'people', '')
pid = people[0]['id']
save('http_cert_vi_clean.pdf', kw('pb.doc.studio', 'sample_pdf', cert, {}, pid, 'vi_VN'))
body = kw('pb.doc.studio', 'open', exp).get('body') or ''
extra = ''.join('<p><strong>Paragraph %d.</strong> This sentence checks that every word of a long letter reaches the page, with <strong>bold words</strong> in the middle and a plain ending word number %d.</p>' % (i, i) for i in range(1, 31))
save('http_long_letter_clean.pdf', kw('pb.doc.studio', 'sample_pdf', exp, {'body': (body if isinstance(body, str) else '') + extra}, pid, 'en_US'))
rpc('/web/session/destroy', {})
print('signed out')
