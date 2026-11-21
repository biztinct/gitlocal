# -*- coding: utf-8 -*-
"""WDGAP S2-C test 2 — the general payment list is unchanged, byte for byte.

The golden stamps below were taken by running THIS file on the code of
`origin/19.1` before S2-C (the pristine tree; `S2C_PRINT_GOLDEN=1` logs them),
on the IDB1 fixture (two companies, VND/home money + IDR, every kind of
check). With S2-C code and no bank layout chosen, the Excel and CSV of the
general list must be the same bytes — before and after a bank-layout file was
made for the same run.
"""

import hashlib
import io
import logging
import os
import zipfile

from odoo.tests import tagged

from odoo.addons.pb_pay_delivery.tests import test_wdgap_idb1_payment_list as idb1

_logger = logging.getLogger(__name__)

#: sha256 of the general list for the IDB1 fixture run on origin/19.1
#: (xlsx: every part except docProps/, whose "created" stamp is the build time
#: — ledger IDB1M-3). Recorded 2026-11-18 on origin/19.1 @ 116386329
#: (local copy wdgap_s2c_t).
GOLDEN = {
    'csv': '4b288e23bdbdc112c15322928df04cde1febe6d20d3643b379fc92b924793312',
    'xlsx': 'f6867c5fec724045dd62bb5f811c427352ed274d4643f1d6299a9c87d822bf77',
}


def stable_digest(data, kind):
    if kind != 'xlsx':
        return hashlib.sha256(data).hexdigest()
    digest = hashlib.sha256()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in sorted(zf.namelist()):
            if name.startswith('docProps/'):
                continue
            digest.update(name.encode())
            digest.update(zf.read(name))
    return digest.hexdigest()


@tagged('post_install', '-at_install', 'wdgap_s2c')
class TestS2cGeneralListGolden(idb1._Idb1Fixture):

    def _digests(self):
        out = {}
        for kind in ('csv', 'xlsx'):
            _name, _mime, payload, _data = self.List._pb_build(self.payrun, kind)
            out[kind] = stable_digest(payload, kind)
        return out

    def test_s2c_2_general_list_is_byte_identical(self):
        digests = self._digests()
        if os.environ.get('S2C_PRINT_GOLDEN'):
            _logger.warning('S2C GOLDEN %r', digests)
        for kind, expected in GOLDEN.items():
            self.assertEqual(digests[kind], expected,
                                 'the general %s list changed under S2-C' % kind)
        # a bank-layout file for the same run moves no byte of the general list
        Layout = self.env.get('pb.bank.file.layout')
        if Layout is not None and 'target' in Layout._fields:
            layout = Layout.search([('target', '=', 'payment_list')], limit=1)
            if layout:
                self.List._pb_layout_build(self.payrun, layout)
                self.assertEqual(self._digests(), digests,
                                 'the general list moved after a bank-layout file')
