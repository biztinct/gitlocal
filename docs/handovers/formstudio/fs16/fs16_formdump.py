# FS-16 investigation (odoo-bin shell, a COPY): write the employee form as HR sees it — normalised the
# same way as fs16_probe.py — to FORM_OUT (en only), and list the newest chatter messages by kind
# (model, type, subtype, author is the system or not; never bodies or names) after MSG_AFTER.
import os

from lxml import etree

DELETED = ('vn_foreign_insurance_exempt', 'vn_si_number', 'vn_si_effective_date', 'vn_hi_number',
           'vn_hi_effective_date', 'vn_ui_number', 'vn_ui_effective_date', 'vn_tax_table_id',
           'vn_tax_effective_date', 'vn_employer_insurance_cost', 'vn_employee_insurance_cost',
           'vn_total_insurance_contribution', 'vn_personal_tax_rate', 'vn_monthly_tax_allowance',
           'vn_dependent_tax_allowance')


def normalised(arch_text):
    root = etree.fromstring(arch_text.encode())
    for node in list(root.iter('field')):
        if node.get('name') in DELETED and not any(a.tag == 'field' for a in node.iterancestors()):
            node.getparent().remove(node)
    for grp in list(root.iter('group')):
        if 'o_label_nowrap' in (grp.get('class') or '') and not list(grp.iter('field')):
            grp.getparent().remove(grp)
    for div in list(root.iter('div')):
        if len(div) == 1 and div[0].tag == 'strong' and not list(div.iter('field')):
            div.getparent().remove(div)
    for el in root.iter():
        el.text = (el.text or '').strip() or None
        el.tail = (el.tail or '').strip() or None
    return etree.tostring(root, pretty_print=True)


env.registry.clear_cache('templates')
view = env.ref('hr.view_employee_form')
arch = env['hr.employee'].sudo().with_context(lang='en_US').get_view(view.id, 'form')['arch']
open(os.environ['FORM_OUT'], 'wb').write(normalised(arch))
after = int(os.environ.get('MSG_AFTER') or 0)
env.cr.execute("""select m.model, m.message_type, coalesce(s.name->>'en_US', ''), (m.author_id is null)::text, count(*)
                    from mail_message m left join mail_message_subtype s on s.id = m.subtype_id
                   where m.id > %s group by 1, 2, 3, 4 order by 5 desc""", [after])
for row in env.cr.fetchall():
    print('MSG %s' % ' | '.join(str(x) for x in row))
env.cr.execute("select max(id) from mail_message")
print('MSGMAX %s' % env.cr.fetchone()[0])
env.cr.rollback()
