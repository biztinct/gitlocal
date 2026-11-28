# DOCSTUDIO W2: the two font / long-PDF findings, checked on live payobook as the QA login through the
# designer's own "Download a sample PDF" (sample_pdf: no letter made, nothing filed), plus a contract
# document PDF and an offer letter sample PDF for the "same page design" check. Rolled back.
# Writes the PDFs to $PDF_OUT (default /tmp/w2-fontcheck); prints PROBE lines (sizes, pages, words).
import base64, io, os, re
OUT = os.environ.get('PDF_OUT', '/tmp/w2-fontcheck')
os.makedirs(OUT, exist_ok=True)


def p(*a):
    print('PROBE', *a)


def save(name, b64):
    raw = base64.b64decode(b64)
    with open(os.path.join(OUT, name), 'wb') as f:
        f.write(raw)
    return raw


try:
    qa = env['res.users'].browse(int(os.environ.get('PROBE_UID') or 6672))
    cids = [qa.company_id.id] + [c for c in qa.company_ids.ids if c != qa.company_id.id]
    q = env(user=qa.id, context=dict(env.context, allowed_company_ids=cids))
    DS = q['pb.doc.studio']
    cert = env.ref('pb_me_letters.letter_template_employment_cert')
    exp = env.ref('pb_lifecycle.letter_template_experience')
    people = DS.people('')
    vn = env['hr.employee'].sudo().browse([x['id'] for x in people]).filtered(
        lambda e: e.company_id.country_id.code == 'VN')[:1] or env['hr.employee'].browse(people[0]['id'])
    p('person', vn.id, 'company country', vn.company_id.country_id.code)
    # 1. Vietnamese employment certificate, shipped Vietnamese wording, "Clean" (default) twice, then serif
    for tag, page in (('clean1', {}), ('clean2', {}), ('serif', {'font': 'classic'})):
        dr = {'page': dict(cert.pbds_page or {}, **page)} if page else {}
        r = DS.sample_pdf(cert.id, dr, vn.id, 'vi_VN')
        if r.get('ok'):
            raw = save('cert_vi_%s.pdf' % tag, r['data'])
            p('cert vi', tag, 'bytes', len(raw), 'pdf', raw[:5] == b'%PDF-', 'vendor in name', 'odoo' in r['name'].lower())
        else:
            p('cert vi', tag, 'FAILED', r.get('msg'))
    # 2. a LONG letter (2+ pages) from the designer, "Clean", twice: the shipped wording + 30 numbered paragraphs
    base = str(exp.with_context(lang='en_US').body_html or '')
    extra = ''.join('<p><strong>Paragraph %d.</strong> This sentence checks that every word of a long '
                    'letter reaches the page, with <strong>bold words</strong> in the middle and a '
                    'plain ending word number %d.</p>' % (i, i) for i in range(1, 31))
    for tag in ('clean1', 'clean2', 'serif'):
        dr = {'body': base + extra}
        if tag == 'serif':
            dr['page'] = dict(exp.pbds_page or {}, font='classic')
        r = DS.sample_pdf(exp.id, dr, vn.id, 'en_US')
        if r.get('ok'):
            raw = save('long_en_%s.pdf' % tag, r['data'])
            p('long letter', tag, 'bytes', len(raw))
        else:
            p('long letter', tag, 'FAILED', r.get('msg'))
    # 3. same page design: contract document PDF + offer letter sample PDF
    if 'pb.contracts' in env and hasattr(env['pb.contracts'], 'contract_document_pdf'):
        k = env['hr.contract'].sudo().search([('state', '=', 'open'), ('employee_id', '!=', False),
                                               ('company_id', '=', qa.company_id.id)], order='id', limit=1)
        if k:
            r = q['pb.contracts'].contract_document_pdf(k.id)
            if r.get('ok'):
                raw = save('contract.pdf', r['data'])
                p('contract pdf', 'bytes', len(raw), 'vendor in name', 'odoo' in r['name'].lower())
            else:
                p('contract pdf FAILED', r.get('msg'))
    offs = DS.offers('') if hasattr(DS, 'offers') else []
    oc = env.ref('pb_hiring.letter_template_offer_generic', raise_if_not_found=False)
    if offs and oc:
        r = DS.sample_pdf(oc.id, {}, offs[0]['id'])
        if r.get('ok'):
            raw = save('offer.pdf', r['data'])
            p('offer pdf', 'bytes', len(raw), 'vendor in name', 'odoo' in r['name'].lower())
        else:
            p('offer pdf FAILED', r.get('msg'))
    p('letters', env['pb.hr.letter'].sudo().search_count([]), 'documents', env['pb.employee.document'].sudo().search_count([]))
except Exception as e:
    import traceback; traceback.print_exc()
    p('ERROR', type(e).__name__, str(e)[:300])
finally:
    env.cr.rollback()
    p('rolled back')
