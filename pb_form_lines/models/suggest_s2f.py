# -*- coding: utf-8 -*-
"""WDGAP S2-F — wider Suggest words for the Indonesian BPJS sheets and the
monthly tax line.

The Step 2 go-live found that Suggest proposed nothing for the two BPJS
sheets and missed the monthly tax item on a customer's Indonesian scheme.
Two reasons: the scheme names its items in plain English ("Old age employee",
"Pension company", "Accident insurance income", "Life insurance income",
"BPJS health employee", "Payable tax"), and EVERY one of them is a part of
the scheme's own total deduction / total income (`net_role_detail`), which
Suggest skipped. The employer's JKK, JKM and health premiums are carried as
income items (the premium is taxable income of the person) and mirrored as
deductions, so those lines also accept the `earning` role, after
`employer_cost`.

The catalogue is `noupdate="1"`, so a changed XML value never reaches a
database that already has the line. `apply(env)` (run by the 19.0.1.1.1
post-migration) writes the new values ONLY on a line whose Suggest words
still equal the value shipped before; a line somebody changed is left as it
is. Running it again changes nothing. Suggest still never saves.
"""
import logging

_logger = logging.getLogger(__name__)

#: xmlid -> (old words, old roles, new words, new roles). The new values are
#: also the XML's (a test keeps the two equal); suggest_parts = True on each.
S2F_LINES = {
    'pb_form_lines.form_id_bpjs_tk_jht_ee': (
        'jht,jaminan hari tua', 'deduction',
        'jht,jaminan hari tua,old age', 'deduction'),
    'pb_form_lines.form_id_bpjs_tk_jht_er': (
        'jht,jaminan hari tua', 'employer_cost',
        'jht,jaminan hari tua,old age', 'employer_cost'),
    'pb_form_lines.form_id_bpjs_tk_jkk_er': (
        'jkk,kecelakaan kerja', 'employer_cost',
        'jkk,kecelakaan kerja,work accident,accident insurance', 'employer_cost,earning'),
    'pb_form_lines.form_id_bpjs_tk_jkm_er': (
        'jkm,jaminan kematian,kematian', 'employer_cost',
        'jkm,jaminan kematian,kematian,death cover,life insurance', 'employer_cost,earning'),
    'pb_form_lines.form_id_bpjs_tk_jp_ee': (
        'jp,jaminan pensiun', 'deduction',
        'jp,jaminan pensiun,pension', 'deduction'),
    'pb_form_lines.form_id_bpjs_tk_jp_er': (
        'jp,jaminan pensiun', 'employer_cost',
        'jp,jaminan pensiun,pension', 'employer_cost'),
    'pb_form_lines.form_id_bpjs_kes_kes_ee': (
        'bpjs kesehatan,bpjs kes,jkn,health insurance', 'deduction',
        'bpjs kesehatan,bpjs kes,jkn,health insurance,bpjs health employee,bpjs health',
        'deduction'),
    'pb_form_lines.form_id_bpjs_kes_kes_er': (
        'bpjs kesehatan,bpjs kes,jkn,health insurance', 'employer_cost',
        'bpjs kesehatan,bpjs kes,jkn,health insurance,bpjs health company,bpjs health',
        'employer_cost,earning'),
    'pb_form_lines.form_id_bpmp_pph21': (
        'pph 21,pph21,pph pasal 21,pajak penghasilan,income tax,tax', 'deduction',
        'pph 21,pph21,pph pasal 21,pajak penghasilan,income tax,payable tax,tax', 'deduction'),
}

#: Wage lines: words only (the wage base is a whole item, not a part).
S2F_WORDS_ONLY = {
    'pb_form_lines.form_id_bpjs_tk_wage': (
        'upah bpjs,dasar upah bpjs,dasar bpjs,gaji bpjs,upah tk,bpjs wage,bpjs base',
        'upah bpjs,dasar upah bpjs,dasar bpjs,gaji bpjs,upah tk,bpjs wage,bpjs base,'
        'bpjs tk wage'),
    'pb_form_lines.form_id_bpjs_kes_wage': (
        'upah bpjs kesehatan,dasar bpjs kesehatan,gaji bpjs kesehatan,bpjs kes base,'
        'upah bpjs,dasar bpjs',
        'upah bpjs kesehatan,dasar bpjs kesehatan,gaji bpjs kesehatan,bpjs kes base,'
        'upah bpjs,dasar bpjs,bpjs health wage'),
}


def apply(env):
    """Bring the shipped lines to the S2-F words. Returns {xmlid: what was
    done} ('updated', 'already', 'changed by someone - left', 'missing')."""
    done = {}
    for xmlid, (old_w, old_r, new_w, new_r) in S2F_LINES.items():
        line = env.ref(xmlid, raise_if_not_found=False)
        if not line:
            done[xmlid] = 'missing'
            continue
        if line.suggest_words == old_w and line.suggest_roles == old_r:
            line.write({'suggest_words': new_w, 'suggest_roles': new_r,
                        'suggest_parts': True})
            done[xmlid] = 'updated'
        elif line.suggest_words == new_w and line.suggest_roles == new_r:
            if not line.suggest_parts:
                line.write({'suggest_parts': True})
            done[xmlid] = 'already'
        else:
            done[xmlid] = 'changed by someone - left'
    for xmlid, (old_w, new_w) in S2F_WORDS_ONLY.items():
        line = env.ref(xmlid, raise_if_not_found=False)
        if not line:
            done[xmlid] = 'missing'
        elif line.suggest_words == old_w:
            line.write({'suggest_words': new_w})
            done[xmlid] = 'updated'
        elif line.suggest_words == new_w:
            done[xmlid] = 'already'
        else:
            done[xmlid] = 'changed by someone - left'
    _logger.info('pb_form_lines S2-F Suggest words: %s', done)
    return done
