# DOCSTUDIO W2 probe (odoo-bin shell; read-only in effect: everything is rolled back).
# As the administrator (or PROBE_UID): the wave-2 screens answer —
#  * document designer: "Hiring" and "Employment contracts" groups, offers to preview with, an
#    offer letter previewed with a real offer, a certificate previewed with a person;
#  * contract panel: the contract document of a real contract (sample-wording flag on screen),
#    and with PROBE_PDF=1 the real PDF, whose text must NOT carry the sample-wording note;
#  * report PDF: a saved built report and a saved Explorer view open in the PDF designer
#    (fonts offered), and with PROBE_PDF=1 a real PDF (pages, "Printed on" / page numbers);
#  * the "Send regularly" PDF choice field.
# Prints PROBE lines (counts and yes/no only, never names or values).
import base64, io, os, re
from odoo.exceptions import AccessError, UserError


def p(*a):
    print('PROBE', *a)


def pdf_text(raw):
    try:
        from PyPDF2 import PdfReader
    except ImportError:                 # older PyPDF2
        from PyPDF2 import PdfFileReader as PdfReader
    r = PdfReader(io.BytesIO(raw))
    pages = list(r.pages)
    return len(pages), [re.sub(r'\s+', ' ', (pg.extract_text() or '')) for pg in pages]


PDF = os.environ.get('PROBE_PDF') == '1'
NOTE_WORDS = ('Sample wording', 'lawyer', 'Nội dung mẫu', 'luật sư', 'Contoh', 'pengacara')
try:
    uid = int(os.environ.get('PROBE_UID') or env.ref('base.user_admin').id)
    user = env['res.users'].browse(uid)
    cids = [user.company_id.id] + [c for c in user.company_ids.ids if c != user.company_id.id]
    uenv = env(user=uid, context=dict(env.context, allowed_company_ids=cids))
    names = ['pb_doc_studio', 'pb_doc_studio_hiring', 'pb_doc_studio_me', 'pb_doc_contracts',
             'pb_report_pdf', 'pb_report_pdf_send', 'pb_report_builder', 'pb_explorer']
    mods = {m.name: m for m in env['ir.module.module'].search([('name', 'in', names)])}
    p('modules', ' '.join('%s=%s:%s' % (n, mods[n].state, mods[n].latest_version) if n in mods else n + '=absent'
                          for n in names))
    inst = {n for n, m in mods.items() if m.state == 'installed'}
    T = env['pb.letter.template'].sudo().with_context(active_test=False)
    p('templates', T.search_count([]), 'letters', env['pb.hr.letter'].sudo().search_count([]),
      'offers', env['pb.hiring.offer'].sudo().search_count([]) if 'pb.hiring.offer' in env else '-',
      'documents', env['pb.employee.document'].sudo().search_count([]))
    DS = uenv['pb.doc.studio']
    b = DS.board()
    cards = b['cards']
    per = {}
    for c in cards:
        per[c['kind']] = per.get(c['kind'], 0) + 1
    p('board cards', len(cards), 'per kind', ' '.join('%s=%s' % kv for kv in sorted(per.items())),
      'first kind', cards[0]['kind'] if cards else '-', 'edited', sum(1 for c in cards if c['edited']))
    if 'pb_doc_contracts' in inst:
        p('shipped contract wordings with the sample note', T.search_count([('pbdc_sample', '=', True)]),
          'with studio data', T.search_count([('pbdc_sample', '=', True), ('pbds_edited', '=', True)]))
    if 'pb_doc_studio_hiring' in inst:
        offs = DS.offers('')
        p('offers offered to preview', len(offs))
        oc = next((c for c in cards if c['kind'] == 'hiring'), None)
        if oc and offs:
            o = DS.open(oc['id'])
            pv = DS.preview(oc['id'], {}, offs[0]['id'])
            p('offer preview', 'kind', o.get('preview_kind'), 'access', o.get('offer_access'),
              'html chars', len(pv['html']), 'lang', pv['lang'], 'vendor word', 'odoo' in pv['html'].lower())
            if PDF:
                s = DS.sample_pdf(oc['id'], {}, offs[0]['id'])
                raw = base64.b64decode(s['data']) if s.get('ok') else b''
                p('offer sample pdf', 'ok' if raw[:5] == b'%PDF-' else 'FAILED %s' % s.get('msg'), 'bytes', len(raw))
    if 'pb_doc_studio_me' in inst:
        cc = next((c for c in cards if 'ertificat' in (c.get('name') or '') or c.get('key') == 'employment_cert'), None)
        people = DS.people('')
        if cc and people:
            pv = DS.preview(cc['id'], {}, people[0]['id'])
            p('certificate preview', 'html chars', len(pv['html']), 'lang', pv['lang'])
    if 'pb_doc_contracts' in inst:
        C = uenv['pb.contracts']
        k = env['hr.contract'].sudo().search([('state', '=', 'open'), ('employee_id', '!=', False),
                                               ('company_id', 'in', cids)], order='id', limit=1)
        if not k:
            p('contract document', 'no running contract')
        else:
            av = C.contract_document_available(k.id)
            d = C.contract_document(k.id)
            if d.get('ok'):
                p('contract document', 'ok', 'langs', len(d['langs']), 'documents', len(d['documents']),
                  'sample note on screen', d['sample_wording'], 'missing', len(d['missing']),
                  'left out', len(d['left_out']), 'can file', d['can_file'], 'pay blocked', d['pay_blocked'],
                  'note words in the paper', any(w in d['html'] for w in NOTE_WORDS),
                  'vendor word', 'odoo' in d['html'].lower())
                if PDF:
                    for lang in (d['langs'] or [{'code': None}])[:2]:
                        code = lang.get('code') if isinstance(lang, dict) else lang
                        r = C.contract_document_pdf(k.id, code)
                        if r.get('ok'):
                            raw = base64.b64decode(r['data'])
                            n, texts = pdf_text(raw)
                            body = ' '.join(texts)
                            p('contract pdf', code, 'pages', n, 'bytes', len(raw),
                              'note in the PDF', any(w in body for w in NOTE_WORDS),
                              'vendor in name', 'odoo' in r['name'].lower())
                        else:
                            p('contract pdf FAILED', code, r.get('msg'))
            else:
                p('contract document refused', d.get('msg'), 'available', av)
    if 'pb_report_pdf' in inst:
        P = uenv['pb.report.pdf']
        srcs = []
        if 'pb.report.builder' in env:
            RB = uenv['pb.report.builder']
            ex = RB.examples()
            if ex:
                pick = next((e for e in ex if e['spec'].get('subject') == 'people'), ex[0])
                card = RB.save_report('W2 probe', pick['spec'], False)
                srcs.append(('built report', 'pb.report.definition', card['id']))
        if 'pb.explorer.view' in env:
            v = uenv['pb.explorer.view'].pbx_save('W2 probe view', {'measure': 'net', 'dimension': 'department_id'}, False)
            srcs.append(('explorer view', 'pb.explorer.view', v['id']))
        for label, model, rid in srcs:
            o = P.open(model, rid)
            if not o.get('ok'):
                p('pdf designer', label, 'refused', o.get('msg'))
                continue
            p('pdf designer', label, 'ok', 'columns', len(o['columns']), 'fonts', '/'.join(f['label'] for f in o['options']['fonts']),
              'origin', o['origin'], 'preview chars', len((o.get('preview') or {}).get('html') or ''))
            if PDF:
                r = P.download(model, rid, o['look'])
                if r.get('ok'):
                    raw = base64.b64decode(r['data'])
                    n, texts = pdf_text(raw)
                    p('pdf download', label, 'rows', r['rows'], 'pages', n, 'seconds', r['seconds'],
                      'pages with a printed-on line', sum(1 for t in texts if re.search(r'Printed on|In lúc|In ngày|Dicetak', t)),
                      'pages with a page number', sum(1 for t in texts if re.search(r'(Page|Trang|Halaman)\s*\d+', t)),
                      'reader lang', uenv.user.lang,
                      'empty pages', sum(1 for t in texts if len(t.strip()) < 20),
                      'vendor in name', 'odoo' in r['name'].lower())
                else:
                    p('pdf download FAILED', label, r.get('msg'))
        p('looks stored', env['pb.report.pdf.look'].sudo().search_count([]))
    if 'pb.explorer.schedule' in env:
        p('schedule pdf field', 'pbrp_pdf' in env['pb.explorer.schedule']._fields)
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:300])
finally:
    env.cr.rollback()
    p('rolled back')
