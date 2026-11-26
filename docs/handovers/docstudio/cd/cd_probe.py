# DOCSTUDIO close-out D probe (odoo-bin shell; everything is rolled back). As the administrator
# (or PROBE_UID). Prints PROBE lines (counts, languages, yes/no; never names, values or pay).
#  Z1  an untouched built-in offer letter written in Indonesian / Vietnamese / with no choice:
#      the pay table's "how often" words (letter text and, with PROBE_PDF=1, the real PDF text)
#  Z2  the three analytics PDFs that never had a page design: on no Print menu
#  Z3  names of the two built-in offer letters + the Vietnam contract in en / vi / id, the designer's
#      name box (open) = the gallery card in that language
#  Z4  the designer previews the Vietnam contract, for a person whose own language differs, in the
#      language the contract panel picks; with PROBE_PDF=1 the sample PDF in that language
#  L   the six new lessons are in the shipped lesson file; Learn's vi_VN.po present
import base64, io, json, os, re, unicodedata
from odoo.tools import file_open


def p(*a):
    print('PROBE', *a)


def pdf_text(raw):
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        from PyPDF2 import PdfFileReader as PdfReader
    r = PdfReader(io.BytesIO(raw))
    return len(r.pages), ' '.join(re.sub(r'\s+', ' ', (pg.extract_text() or '')) for pg in r.pages)


def has(word, txt):
    # PDF text layers may hold decomposed accents and odd spacing: compare NFC, spaces removed
    n = lambda x: re.sub(r'\s+', '', unicodedata.normalize('NFC', x))
    return n(word) in n(txt)


PDF = os.environ.get('PROBE_PDF') == '1'
WORDS = {'en_US': ('Every month', 'One-off'), 'vi_VN': ('Hằng tháng', 'Một lần'),
         'id_ID': ('Setiap bulan', 'Sekali saja')}
try:
    uid = int(os.environ.get('PROBE_UID') or env.ref('base.user_admin').id)
    user = env['res.users'].browse(uid)
    cids = [user.company_id.id] + [c for c in user.company_ids.ids if c != user.company_id.id]
    uenv = env(user=uid, context=dict(env.context, allowed_company_ids=cids))
    names = ['pb_learn', 'pb_payroll_ai_insights', 'pb_report_builder', 'pb_excel_layout', 'pb_report_pdf',
             'pb_report_pdf_send', 'pb_doc_studio', 'pb_doc_studio_hiring', 'pb_doc_studio_me',
             'pb_doc_contracts', 'pb_hiring', 'pb_hr_payroll_analytics']
    mods = {m.name: m for m in env['ir.module.module'].search([('name', 'in', names)])}
    p('modules', ' '.join('%s=%s:%s' % (n, mods[n].state, mods[n].latest_version) if n in mods else n + '=absent'
                          for n in names))
    langs = [l for l in ('en_US', 'vi_VN', 'id_ID') if env['res.lang']._lang_get(l)]
    p('languages active', ' '.join(langs))

    # ---- Z2
    reps = env['ir.actions.report'].sudo().search([('report_name', 'like', 'pb_hr_payroll_analytics.report_%')])
    p('Z2 analytics PDFs', len(reps), 'on a Print menu', sum(1 for r in reps if r.binding_model_id))

    # ---- Z3
    DS = uenv['pb.doc.studio']
    for xmlid in ('pb_hiring.letter_template_offer_generic', 'pb_hiring.letter_template_offer_vietnam',
                  'pb_doc_contracts.contract_template_vn'):
        t = env.ref(xmlid, raise_if_not_found=False)
        if not t:
            p('Z3', xmlid, 'absent'); continue
        row = []
        for lang in langs:
            nm = t.with_context(lang=lang).name or ''
            o = DS.with_context(lang=lang).open(t.id)
            card = next((c for c in DS.with_context(lang=lang).board()['cards'] if c['id'] == t.id), {})
            row.append('%s name=%s box=card %s' % (lang, nm, o.get('name') == card.get('name')))
        p('Z3', xmlid.split('.')[1], '; '.join(row))

    # ---- Z1
    Offer = env['pb.hiring.offer'] if 'pb.hiring.offer' in env else None
    generic = env.ref('pb_hiring.letter_template_offer_generic', raise_if_not_found=False)
    if Offer is not None and generic:
        p('Z1 generic offer letter edited in the designer', bool(generic.pbds_edited) if 'pbds_edited' in generic._fields else '-')
        cands = Offer.sudo().search([('line_ids', '!=', False)], order='id')
        offer = next((o for o in cands if set(o.line_ids.mapped('period')) >= {'monthly', 'one_time'}), None) \
            or (cands[:1] or None)
        if not offer:
            p('Z1 no offer with pay lines on this database')
        else:
            p('Z1 offer with periods', ' '.join(sorted(set(offer.line_ids.mapped('period')))))
            for chosen in (False, 'id_ID', 'vi_VN'):
                env.cr.execute('SAVEPOINT z1')
                try:
                    o = offer.with_user(uid).with_context(allowed_company_ids=cids)
                    o.sudo().write({'letter_template_id': generic.id, 'pbds_letter_lang': chosen})
                    o.action_prepare_letter()
                    html = str(o.rendered_html or '')
                    found = {k: [w in html for w in v] for k, v in WORDS.items()}
                    line = ['letter', chosen or 'no choice', 'written in', o.pbds_lang or '-',
                            'words in the letter', ' '.join('%s=%s' % (k, '/'.join('y' if x else 'n' for x in v)) for k, v in found.items())]
                    if PDF and o.attachment_id:
                        raw = o.attachment_id.raw or b''
                        if raw[:5] == b'%PDF-':
                            n, txt = pdf_text(raw)
                            line += ['| pdf pages', n, 'text chars', len(txt), 'words in the PDF',
                                     ' '.join('%s=%s' % (k, '/'.join('y' if has(w, txt) else 'n' for w in v)) for k, v in WORDS.items()),
                                     'vendor word', 'odoo' in txt.lower()]
                        else:
                            line += ['| attachment is not a PDF']
                    p('Z1', *line)
                except Exception as e:
                    p('Z1', chosen or 'no choice', 'ERROR', type(e).__name__, str(e)[:200])
                finally:
                    try:
                        env.flush_all()
                    except Exception:
                        pass
                    env.cr.execute('ROLLBACK TO SAVEPOINT z1')
                    env.invalidate_all(flush=False)

    # ---- Z4
    tvn = env.ref('pb_doc_contracts.contract_template_vn', raise_if_not_found=False)
    if tvn:
        Panel = uenv['pb.contracts']
        vn = env.ref('base.vn')
        emps = env['hr.employee'].sudo().search([('company_id', 'in', cids), ('company_id.partner_id.country_id', '=', vn.id)], order='id')
        emp = next((e for e in emps if (e.lang or '') != 'vi_VN'), None)
        if not emp:
            p('Z4 no person in a Vietnam company whose own language is not Vietnamese')
        else:
            codes = [r['code'] for r in Panel._pbdc_langs(tvn)]
            panel = Panel._pbdc_pick_lang(tvn, emp, False, [{'code': c} for c in codes])
            try:
                plain = DS.preview(tvn.id, {}, emp.id)
                auto = DS.with_context(pbds_preview_auto=True).preview(tvn.id, {}, emp.id)
                hand = DS.preview(tvn.id, {}, emp.id, lang='en_US')
                p('Z4 person lang', emp.lang, 'wording langs', '/'.join(codes), 'panel picks', panel,
                  '| designer (auto)', auto.get('lang'), 'same as panel', auto.get('lang') == panel,
                  '| without the flag', plain.get('lang'), '| English picked by hand', hand.get('lang'))
                if PDF:
                    s = DS.with_context(pbds_preview_auto=True).sample_pdf(tvn.id, {}, emp.id)
                    raw = base64.b64decode(s['data']) if s.get('ok') else b''
                    if raw[:5] == b'%PDF-':
                        n, txt = pdf_text(raw)
                        p('Z4 sample pdf pages', n, 'text chars', len(txt), 'Vietnamese wording',
                          bool(re.search(r'HỢP ĐỒNG|Hợp đồng|hợp đồng', txt)),
                          '"No wording" line', 'No wording' in txt or 'Chưa có nội dung' in txt,
                          'sample note', any(w in txt for w in ('Sample wording', 'Nội dung mẫu', 'lawyer', 'luật sư')))
                    else:
                        p('Z4 sample pdf FAILED', s.get('msg'))
            except Exception as e:
                p('Z4 ERROR', type(e).__name__, str(e)[:200])

    # ---- L
    with file_open('pb_learn/static/content/learn_content.json', 'r') as fh:
        raw = fh.read()
    keys = ['L43', 'L44', 'L45', 'L46', 'L47', 'L48']
    p('L lessons in the shipped file', ' '.join('%s=%s' % (k, ('"%s"' % k) in raw) for k in keys),
      'vendor word in file', len(re.findall(r'\bOdoo\b', raw)))
    with file_open('pb_learn/i18n/vi_VN.po', 'rb') as fh:
        po = fh.read()
    p('L pb_learn vi_VN.po bytes', len(po), 'entries', po.count(b'\nmsgid '))
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:300])
finally:
    env.cr.rollback()
    p('rolled back')
