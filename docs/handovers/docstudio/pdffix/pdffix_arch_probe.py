# DOCSTUDIO PDFFIX phase 2: render payslips with CHANGED report templates WITHOUT deploying them:
# the template arch is swapped in this shell's transaction only (rolled back at the end, nothing
# stored), with whichever PDF engine this process finds on PATH.
# Env: OUT, SLIPS (ids, comma), REFS (report action xmlids, comma),
#      ARCH (";"-separated "module.template_id=/path/to/file.xml"; empty = live templates).
import os
from lxml import etree
from odoo.addons.base.models import ir_actions_report as IAR

OUT = os.environ['OUT']; os.makedirs(OUT, exist_ok=True)


def p(*a):
    print('PROBE', *a, flush=True)


try:
    w = IAR._wkhtml(); p('engine', w.bin, w.version, 'patched' if w.is_patched_qt else 'UNPATCHED')
    for item in filter(None, (os.environ.get('ARCH') or '').split(';')):
        xmlid, path = item.split('=', 1)
        tid = xmlid.split('.', 1)[1]
        node = next(t for t in etree.parse(path).getroot().iter('template') if t.get('id') == tid)
        arch = etree.Element('t', {'t-name': xmlid})
        arch.text = node.text
        for child in node:
            arch.append(child)
        view = env.ref(xmlid)
        view.sudo().with_context(lang=None).write({'arch_db': etree.tostring(arch, encoding='unicode')})
        p('arch swapped', xmlid)
    env.registry.clear_cache('templates')
    Report = env['ir.actions.report'].sudo()
    ids = [int(x) for x in os.environ['SLIPS'].split(',') if x]
    for ref in os.environ['REFS'].split(','):
        rep = env.ref(ref, raise_if_not_found=False)
        if not rep:
            p(ref, 'absent'); continue
        for tag, res in (('one', ids[:1]), ('run', ids)):
            if tag == 'run' and len(ids) < 2:
                continue
            pdf, _x = Report.with_context(pb_payrun_print=True)._render_qweb_pdf(rep, res_ids=res)
            name = '%s_%s.pdf' % (ref.split('.')[-1], tag)
            open(os.path.join(OUT, name), 'wb').write(pdf)
            p(name, len(pdf))
except Exception as e:                                       # noqa: BLE001
    import traceback; traceback.print_exc(); p('ERROR', type(e).__name__, str(e)[:300])
finally:
    env.cr.rollback(); p('rolled back')
