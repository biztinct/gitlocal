# -*- coding: utf-8 -*-
"""CLEANMAP P2 — the Journey shows only what is mapped, and its cards open.

The phase inverts the payload: v1 took a CENSUS of the database and then drew
edges between whichever nodes happened to be wired, so a connector nobody uses
and seven feeds that never synced were on the picture (ledger CM4). v2 builds
the field-level LINKS first and derives the cards from them, so a card exists
only because something on this scheme reads through it.

Every test below is written against that inversion, and each one fails
SILENTLY without it — an extra card is not an exception, it is a picture that
quietly describes the wrong thing.

The numbering follows `CLEANMAP_P2_JOURNEY_HANDOVER.md` §5.
"""
import json
import re

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCleanmapJourney(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FieldMapping = cls.env['hr.integration.field.mapping']
        cls.PeopleMap = cls.env['hr.payslip.import.mapping']
        cls.TRule = cls.env['hr.api.transformation.rule']
        cls.Endpoint = cls.env['hr.integration.endpoint']

    # ------------------------------------------------------------- fixtures
    def _config(self, name, **extra):
        vals = {'name': name, 'code': re.sub(r'\W', '', name.upper())[:32],
                'country_code': 'VN', 'state': 'active'}
        vals.update(extra)
        return self.Config.create(vals)

    def _input(self, cfg, code, name=None, seq=1, **extra):
        vals = {'config_id': cfg.id, 'name': name or code, 'code': code,
                'column_type': 'input', 'sequence': seq}
        vals.update(extra)
        return self.Rule.create(vals)

    def _connector(self, name='P2 Conn'):
        conn = self.Connector.create({'name': name, 'connector_type': 'demo'})
        # SC-1 — a mapping is refused to a field the system has never sent, so
        # the keys these tests wire must have ARRIVED.
        self.env['hr.api.data.store'].create({
            'connector_id': conn.id, 'data_type': 'employee',
            'raw_payload': {'base': 1, 'ot': 2, 'deps': 3, 'hours': 4}})
        return conn

    def _endpoint(self, conn, name='Employees', data_type='employee'):
        return self.Endpoint.create({
            'connector_id': conn.id, 'name': name,
            'code': re.sub(r'\W', '', name.lower())[:16],
            'data_type': data_type, 'operation': data_type,
            'path': 'forms/%s/getRecords' % data_type})

    def _wire(self, conn, rule, key, endpoint=None):
        vals = {'connector_id': conn.id, 'target_rule_id': rule.id,
                'source_field': key, 'active_state': 'active'}
        if endpoint:
            vals['endpoint_id'] = endpoint.id
        return self.FieldMapping.create(vals)

    def _trule(self, conn, key, name=None, **extra):
        # `value_steps` is what `_consumed_field_names()` reads — NOT
        # `aggregate_field`, which is the aggregation target and is not a
        # lineage statement. A rule fixture without a DERIVE step reads
        # nothing, which is a perfectly valid rule and a useless fixture for a
        # test about what a rule reads.
        vals = {'connector_id': conn.id, 'name': name or ('Rule %s' % key),
                'output_key': key, 'rule_type': 'sum',
                'builder_mode': 'guided', 'source_data_type': 'employee',
                'aggregate_field': 'hours',
                'value_steps': [{'field': 'hours'}]}
        vals.update(extra)
        return self.TRule.create(vals)

    def _file(self, cfg, columns, filename='P2.xlsx'):
        """Put a stored spreadsheet on the scheme, in `peek_source_columns`'
        own shape: `{key, sheet, header, letter, sample, preferred}`."""
        cfg.sudo().write({
            'import_sample_filename': filename,
            'import_sample_columns_json': json.dumps(columns),
        })

    def _sheet_file(self, cfg, headings, sheet='Salary'):
        """The MERGE shape rize's workbook has: one preferred sheet-qualified
        card per column, plus its bare twin and its letter."""
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        cols = []
        for n, head in enumerate(headings):
            cols.append({'key': '%s|%s' % (sheet, head), 'sheet': sheet,
                         'header': head, 'letter': letters[n], 'sample': '',
                         'preferred': True})
        for n, head in enumerate(headings):
            cols.append({'key': head, 'sheet': '', 'header': head,
                         'letter': letters[n], 'sample': '', 'preferred': False})
            cols.append({'key': letters[n], 'sheet': '', 'header': letters[n],
                         'letter': letters[n], 'sample': '', 'preferred': False})
        self._file(cfg, cols)
        return cols

    def _cards(self, d, lane):
        return d['lanes'][lane]

    def _card(self, d, cid):
        for lane in d['lanes'].values():
            for c in lane:
                if c['id'] == cid:
                    return c
        return None

    def _rows(self, d, cid):
        c = self._card(d, cid)
        return (c or {}).get('rows') or []

    # =====================================================================
    # 1 — the payload's shape
    # =====================================================================
    def test_01_payload_is_v2_with_five_named_lanes_and_no_run(self):
        cfg = self._config('P2 Shape')
        self._input(cfg, 'BASIC')
        d = self.Studio.journey_data(cfg.id)
        self.assertTrue(d['ok'])
        self.assertEqual(d['v'], 2)
        self.assertEqual(sorted(d['lanes']),
                         ['feeds', 'scheme', 'source', 'systems', 'transforms'])
        self.assertNotIn('run', d['lanes'],
                         "the owner removed the pay-run lane (ruling 3)")
        self.assertIn('links', d)
        self.assertIn('contains', d)
        for key in ('inputs', 'fed', 'unfed', 'attention'):
            self.assertIn(key, d['header'])
        self.assertTrue(d['lanes']['scheme'], "the scheme lane is never empty")

    # =====================================================================
    # 2 — the Zoho case: a connector nothing reads is not on the board
    # =====================================================================
    def test_02_an_unused_connector_draws_nothing_at_all(self):
        """The defect this phase exists for.

        v1 iterated `Conn.search([])` and drew every connector on the database,
        every feed of every connector and every transformation rule anywhere.
        rize's Journey therefore showed a "Zoho People — inbound" nothing uses,
        seven feeds that have never synced and a ghost transformations lane, on
        a scheme fed entirely by one spreadsheet.
        """
        cfg = self._config('P2 Unused')
        self._input(cfg, 'BASIC')
        conn = self._connector('P2 Unused Conn')
        self._endpoint(conn)
        self._trule(conn, 'UNUSEDKEY')
        d = self.Studio.journey_data(cfg.id)
        self.assertEqual(d['lanes']['systems'], [],
                         "a connector with no wire into this scheme has no card")
        self.assertEqual(d['lanes']['feeds'], [],
                         "…and neither do its feeds")
        self.assertEqual(d['lanes']['transforms'], [],
                         "…and neither do its transformation rules")

    # =====================================================================
    # 3 — one wire, one system card, one feed card, one row
    # =====================================================================
    def test_03_one_wire_draws_exactly_one_of_each(self):
        cfg = self._config('P2 OneWire')
        basic = self._input(cfg, 'BASIC')
        conn = self._connector('P2 One')
        cfg.sudo().write({'connector_id': conn.id})
        ep = self._endpoint(conn)
        self._endpoint(conn, 'Leave records', 'leave')     # never read: no card
        self._wire(conn, basic, 'base', endpoint=ep)
        d = self.Studio.journey_data(cfg.id)
        self.assertEqual([c['id'] for c in d['lanes']['systems']],
                         ['c:%s' % conn.id])
        self.assertEqual([c['id'] for c in d['lanes']['feeds']],
                         ['e:%s' % ep.id])
        rows = self._rows(d, 'e:%s' % ep.id)
        self.assertEqual([r['id'] for r in rows], ['e:%s:base' % ep.id])
        self.assertEqual(d['contains'],
                         [{'from': 'c:%s' % conn.id, 'to': 'e:%s' % ep.id}])

    # =====================================================================
    # 4 — a consumed transformation, and the feed rows it reads
    # =====================================================================
    def test_04_a_consumed_transformation_brings_its_reads_with_it(self):
        cfg = self._config('P2 Tf')
        hours = self._input(cfg, 'WORKED')
        conn = self._connector('P2 Tf Conn')
        cfg.sudo().write({'connector_id': conn.id})
        ep = self._endpoint(conn)
        tf = self._trule(conn, 'WORKEDHRS', name='Actual working hours')
        self._wire(conn, hours, 'WORKEDHRS')
        d = self.Studio.journey_data(cfg.id)
        self.assertEqual([c['id'] for c in d['lanes']['transforms']],
                         ['t:%s' % conn.id])
        trows = self._rows(d, 't:%s' % conn.id)
        self.assertEqual([r['id'] for r in trows], ['r:%s' % tf.id])
        reads = [l for l in d['links'] if l['kind'] == 'reads']
        self.assertTrue(reads, "the rule's inputs are on the picture")
        for l in reads:
            self.assertEqual(l['b'], 'r:%s' % tf.id)
        # …and the feed rows those reads name exist, although no component
        # reads them directly.
        ids = {r['id'] for r in self._rows(d, 'e:%s' % ep.id)}
        self.assertEqual({l['a'] for l in reads}, ids)
        self.assertIn({'from': 'c:%s' % conn.id, 'to': 't:%s' % conn.id},
                      d['contains'])

    # =====================================================================
    # 5 — an unconsumed transformation rule is simply not there
    # =====================================================================
    def test_05_an_unconsumed_rule_is_absent(self):
        cfg = self._config('P2 TfUnread')
        hours = self._input(cfg, 'WORKED')
        conn = self._connector('P2 TfUnread Conn')
        cfg.sudo().write({'connector_id': conn.id})
        tf = self._trule(conn, 'WORKEDHRS')
        self._trule(conn, 'NOBODYREADS')
        self._wire(conn, hours, 'WORKEDHRS')
        d = self.Studio.journey_data(cfg.id)
        rows = [r['id'] for r in self._rows(d, 't:%s' % conn.id)]
        self.assertEqual(rows, ['r:%s' % tf.id],
                         "a rule nothing on this scheme consumes has no row")

    # =====================================================================
    # 6 — the file rows ARE the Spreadsheet board's accepted wires
    # =====================================================================
    def test_06_file_rows_match_the_spreadsheet_boards_wires(self):
        """The `data_source_field` question, settled in both directions.

        `hr.formula.rule.declared_sources()` does NOT carry the legacy
        `data_source_field` — it is not a `source_ids` row and never was — but
        the Spreadsheet board still draws a wire for it. So the Journey applies
        the same fallback, and this test compares the two SETS of component
        ids. It fails whichever way the answer goes wrong: a Journey that
        forgot the legacy column would call a pre-binding scheme unfed, and a
        Journey that drew one the board does not would be a second opinion.
        """
        cfg = self._config('P2 Legacy')
        bound = self._input(cfg, 'BOUND', seq=1)
        legacy = self._input(cfg, 'LEGACY', seq=2,
                             data_source_field='Old Column')
        self._input(cfg, 'NEITHER', seq=3)
        self._sheet_file(cfg, ['Basic Salary', 'Old Column'])
        bound.set_source_binding('excel', 'Salary|Basic Salary', origin='user')
        d = self.Studio.journey_data(cfg.id)
        journey_ids = set()
        rows = {r['id'] for r in self._rows(d, 'file')}
        for l in d['links']:
            if l['kind'] == 'excel' and l['a'] in rows:
                journey_ids.add(int(l['b'].split(':')[1]))
        board = self.Studio.import_mapping_data(cfg.id, 'sample')
        board_ids = {w['rightId'] for w in board['wires']
                     if w['kind'] == 'mapping'
                     and str(w.get('leftId', '')).startswith('c:')}
        self.assertEqual(journey_ids, board_ids,
                         "the two boards disagree about which components read "
                         "a spreadsheet column")
        self.assertIn(legacy.id, journey_ids,
                      "the legacy data_source_field draws a wire on the "
                      "Spreadsheet board and must draw a link here")

    # =====================================================================
    # 7 — a letter alias lands on the heading's row; a missing key is `gone`
    # =====================================================================
    def test_07_an_alias_lands_on_the_column_and_a_stranger_is_gone(self):
        cfg = self._config('P2 Alias')
        by_letter = self._input(cfg, 'BYLETTER', seq=1)
        by_bare = self._input(cfg, 'BYBARE', seq=2)
        stranger = self._input(cfg, 'STRANGER', seq=3)
        self._sheet_file(cfg, ['Basic Salary', 'Overtime hours'])
        by_letter.set_source_binding('excel', 'B', origin='user')
        by_bare.set_source_binding('excel', 'Basic Salary', origin='user')
        stranger.set_source_binding('excel', 'Ghost Column', origin='user')
        d = self.Studio.journey_data(cfg.id)
        rows = {r['id']: r for r in self._rows(d, 'file')}
        self.assertIn('f:Salary|Overtime hours', rows,
                      "the letter B is the SECOND column of this sheet")
        self.assertIn('f:Salary|Basic Salary', rows,
                      "a bare heading is that column's other spelling")
        self.assertEqual(rows['f:Salary|Basic Salary']['label'], 'Basic Salary')
        self.assertEqual(rows['f:Salary|Basic Salary']['tag'], 'A')
        self.assertIn('f:Ghost Column', rows)
        self.assertEqual(rows['f:Ghost Column']['state'], 'gone',
                         "a key this file does not have says so on the row — "
                         "a wire drawn to nothing crashed a canvas once")
        self.assertEqual(len(rows), 3)

    # =====================================================================
    # 8 — the direction of every record link
    # =====================================================================
    def test_08_record_links_run_the_way_the_resolver_reads_them(self):
        cfg = self._config('P2 Dir')
        emp = self._input(cfg, 'EMPCODE', seq=1)
        con = self._input(cfg, 'JOBTITLE', seq=2)
        bank = self._input(cfg, 'BANKNUM', seq=3, column_role='bank')
        comp = self._input(cfg, 'ALLOWANCE', seq=4, is_contract_component=True)
        period = self._input(cfg, 'STDDAYS', seq=5, period_key='STDDAYS')
        self._people(cfg, emp, 'hr.employee', 'employee_id')
        self._people(cfg, con, 'hr.contract', 'job_id')
        self.PeopleMap.create({
            'salary_structure_id': cfg.id, 'component_id': bank.id,
            'destination_type': 'bank_account', 'bank_role': 'acc_number'})
        d = self.Studio.journey_data(cfg.id)
        by = {}
        for l in d['links']:
            by.setdefault(l['kind'], []).append(l)
        record = {l['b']: l for l in by.get('record', [])}
        self.assertEqual(record['p:emp:employee_id']['dir'], 'both')
        self.assertEqual(record['p:con:job_id']['dir'], 'both')
        self.assertEqual(record['p:bank:acc_number']['dir'], 'fwd',
                         "J3 S1 — a bank row is the import half only; the "
                         "resolver never reads a bank part back")
        self.assertEqual(by['component'][0]['dir'], 'back')
        self.assertEqual(by['component'][0]['b'], 's:%s' % comp.id)
        self.assertEqual(by['period'][0]['dir'], 'back')
        self.assertEqual(by['period'][0]['b'], 's:%s' % period.id)

    def _people(self, cfg, rule, model_name, field_name):
        model = self.env['ir.model']._get(model_name)
        field = self.env['ir.model.fields'].search(
            [('model', '=', model_name), ('name', '=', field_name)], limit=1)
        if not field:
            self.skipTest('%s.%s is not in this build' % (model_name, field_name))
        return self.PeopleMap.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': model.id, 'target_field_id': field.id})

    # =====================================================================
    # 9 — the scheme card IS the input list, and the fold is the rest
    # =====================================================================
    def test_09_scheme_rows_are_the_inputs_in_sequence_and_the_fold_is_the_rest(self):
        cfg = self._config('P2 Scheme')
        a = self._input(cfg, 'AAA', seq=3)
        b = self._input(cfg, 'BBB', seq=1)
        c = self._input(cfg, 'CCC', seq=2)
        self.Rule.create({'config_id': cfg.id, 'name': 'Gross', 'code': 'GROSS',
                          'column_type': 'formula', 'sequence': 9,
                          'excel_formula': '=AAA+BBB'})
        self.Rule.create({'config_id': cfg.id, 'name': 'Rate', 'code': 'RATE',
                          'column_type': 'constant', 'sequence': 10,
                          'constant_value': 1.5})
        d = self.Studio.journey_data(cfg.id)
        card = self._card(d, 'scheme')
        self.assertEqual([r['id'] for r in card['rows']],
                         ['s:%s' % b.id, 's:%s' % c.id, 's:%s' % a.id],
                         "the scheme card is the inputs, in sequence order")
        self.assertEqual(card['folded']['n'], 2)
        self.assertEqual(len(card['folded']['rows']), 2)
        self.assertEqual(d['header']['fed'] + d['header']['unfed'],
                         d['header']['inputs'])
        self.assertEqual(d['header']['inputs'], 3)

    # =====================================================================
    # 10 — two sources, two links, fed once
    # =====================================================================
    def test_10_two_declared_sources_are_two_links_and_one_fed(self):
        cfg = self._config('P2 Two')
        rule = self._input(cfg, 'BASIC')
        conn = self._connector('P2 Two Conn')
        cfg.sudo().write({'connector_id': conn.id})
        ep = self._endpoint(conn)
        self._sheet_file(cfg, ['Basic Salary'])
        rule.set_source_binding('excel', 'Salary|Basic Salary', origin='user')
        self._wire(conn, rule, 'base', endpoint=ep)
        d = self.Studio.journey_data(cfg.id)
        into = [l for l in d['links'] if l['b'] == 's:%s' % rule.id]
        self.assertEqual(len(into), 2, "J9 — a component may declare two")
        self.assertEqual({l['kind'] for l in into}, {'excel', 'feed'})
        self.assertEqual(d['header']['fed'], 1, "it is ONE fed component")
        self.assertEqual(d['header']['unfed'], 0)

    # =====================================================================
    # 11 — a wire on a connection this scheme does not read
    # =====================================================================
    def test_11_a_non_primary_wire_is_dimmed_and_does_not_feed(self):
        cfg = self._config('P2 Dim')
        rule = self._input(cfg, 'BASIC')
        mine = self._connector('P2 Dim Primary')
        other = self._connector('P2 Dim Other')
        cfg.sudo().write({'connector_id': mine.id})
        ep = self._endpoint(other)
        self._wire(other, rule, 'base', endpoint=ep)
        d = self.Studio.journey_data(cfg.id)
        into = [l for l in d['links'] if l['b'] == 's:%s' % rule.id]
        self.assertEqual(len(into), 1)
        self.assertTrue(into[0]['dimmed'])
        self.assertEqual(d['header']['fed'], 0,
                         "a pay run reads only the connection the scheme is "
                         "set to, so this component is NOT fed")
        card = self._card(d, 'c:%s' % other.id)
        self.assertTrue(card['chips'], "…and the card says why")
        self.assertEqual(card['chips'][0]['tone'], 'muted')

    # =====================================================================
    # 12 — every card's rows follow the scheme
    # =====================================================================
    def test_12_rows_are_sorted_by_the_scheme_row_they_reach(self):
        """The WOW detail: forty near-parallel lines instead of a web.

        The file's own column order is deliberately the REVERSE of the
        scheme's here, so a card that kept the file's order fails.
        """
        cfg = self._config('P2 Order')
        first = self._input(cfg, 'FIRST', seq=1)
        second = self._input(cfg, 'SECOND', seq=2)
        third = self._input(cfg, 'THIRD', seq=3)
        self._sheet_file(cfg, ['Col Third', 'Col Second', 'Col First'])
        first.set_source_binding('excel', 'Salary|Col First', origin='user')
        second.set_source_binding('excel', 'Salary|Col Second', origin='user')
        third.set_source_binding('excel', 'Salary|Col Third', origin='user')
        d = self.Studio.journey_data(cfg.id)
        self.assertEqual([r['label'] for r in self._rows(d, 'file')],
                         ['Col First', 'Col Second', 'Col Third'])
        self.assertEqual([r['tag'] for r in self._rows(d, 'file')],
                         ['C', 'B', 'A'],
                         "the column letter stays in the gutter, so the "
                         "file's own order is not lost — only not obeyed")

    # =====================================================================
    # 12b — the tag gutter carries the column's REAL letter
    # =====================================================================
    def test_12b_the_row_tag_is_the_columns_position_in_its_own_sheet(self):
        """CLEANMAP P2 defect 1, pinned in both directions.

        `peek_source_columns` stores a `letter` per column and on a MERGED
        workbook it is not the column's position in its sheet — rize's first
        Salary column came back `AP`, the second `AD`, the third `FG`. The
        Journey showed those and the Spreadsheet board's pay-run lane showed
        A, B, C for the same file, so one board described one workbook two
        ways.

        This asserts the truth (first heading = A, second = B…) AND that the
        two lanes of the Spreadsheet board now agree with each other and with
        the Journey.
        """
        cfg = self._config('P2 Letters')
        a = self._input(cfg, 'AAA', seq=1)
        b = self._input(cfg, 'BBB', seq=2)
        c = self._input(cfg, 'CCC', seq=3)
        cols = self._sheet_file(cfg, ['First col', 'Second col', 'Third col'])
        # Bend the STORED letters the way rize's are bent, so the fixture
        # fails against the stored value and passes only against the walk.
        for col in cols:
            col['letter'] = 'ZZ'
        self._file(cfg, cols)
        a.set_source_binding('excel', 'Salary|First col', origin='user')
        b.set_source_binding('excel', 'Salary|Second col', origin='user')
        c.set_source_binding('excel', 'Salary|Third col', origin='user')

        d = self.Studio.journey_data(cfg.id)
        rows = {r['label']: r['tag'] for r in self._rows(d, 'file')}
        self.assertEqual(rows, {'First col': 'A', 'Second col': 'B',
                                'Third col': 'C'},
                         "the gutter is the column's position in its sheet, "
                         "never the stored letter")

        # …and the Spreadsheet board's template-file lane says the same
        board = self.Studio.import_mapping_data(cfg.id, 'sample')
        letters = {card['label']: (card.get('meta') or {}).get('letter')
                   for card in board['left']
                   if card['id'].startswith('c:')}
        for label, tag in rows.items():
            self.assertEqual(letters.get(label), tag,
                             "the Journey and the Spreadsheet board must give "
                             "%s the same column letter" % label)

    def test_12c_a_second_sheet_starts_its_letters_again_at_A(self):
        """The letter is a position IN A SHEET, so two sheets both have an A."""
        cfg = self._config('P2 Letters2')
        cols = []
        for sheet, heads in (('Salary', ['Pay A', 'Pay B']),
                             ('Hours', ['Hour A'])):
            for n, head in enumerate(heads):
                cols.append({'key': '%s|%s' % (sheet, head), 'sheet': sheet,
                             'header': head, 'letter': 'ZZ', 'sample': '',
                             'preferred': True})
        self._file(cfg, cols)
        letters = self.Studio._sample_column_letters(cfg)
        self.assertEqual(letters, {'Salary|Pay A': 'A', 'Salary|Pay B': 'B',
                                   'Hours|Hour A': 'A'})

    # =====================================================================
    # 13 — the zero state is an invitation, not five ghosts
    # =====================================================================
    def test_13_a_scheme_with_no_links_offers_three_doors(self):
        cfg = self._config('P2 Zero')
        self._input(cfg, 'BASIC')
        d = self.Studio.journey_data(cfg.id)
        self.assertEqual(d['lanes']['systems'], [])
        self.assertEqual(d['lanes']['feeds'], [])
        self.assertEqual(d['lanes']['transforms'], [])
        self.assertEqual(d['lanes']['source'], [])
        self.assertEqual(len(d['lanes']['scheme']), 1)
        self.assertTrue(d['invite'])
        self.assertEqual([door['door']['mode'] for door in d['invite']['doors']],
                         ['import', 'api', 'employee'])
        for door in d['invite']['doors']:
            self.assertTrue(door['label'])

    def test_13b_a_disabled_lane_takes_its_door_with_it(self):
        """SC-4 — an invitation onto a tab this scheme does not have is a door
        onto a door that is not there."""
        if 'source_excel_enabled' not in self.Config._fields:
            self.skipTest('this build has no per-scheme lane flags')
        cfg = self._config('P2 ZeroLanes')
        self._input(cfg, 'BASIC')
        cfg.sudo().write({'source_excel_enabled': False})
        d = self.Studio.journey_data(cfg.id)
        self.assertNotIn('import',
                         [door['door']['mode'] for door in d['invite']['doors']])

    # =====================================================================
    # 14 — no orphan ends
    # =====================================================================
    def test_14_every_link_end_is_a_row_that_exists(self):
        """MAPFIX-D's rule, restated for rows: a link to an id no row carries
        draws nothing and is invisible, so the picture silently understates
        the wiring — the worst possible failure on this tab."""
        cfg = self._config('P2 Ends')
        a = self._input(cfg, 'AAA', seq=1)
        b = self._input(cfg, 'BBB', seq=2)
        conn = self._connector('P2 Ends Conn')
        cfg.sudo().write({'connector_id': conn.id})
        ep = self._endpoint(conn)
        tf = self._trule(conn, 'WORKEDHRS')
        self._wire(conn, a, 'WORKEDHRS')
        self._sheet_file(cfg, ['Basic Salary'])
        b.set_source_binding('excel', 'Salary|Basic Salary', origin='user')
        self._people(cfg, b, 'hr.employee', 'employee_id')
        d = self.Studio.journey_data(cfg.id)
        rows = set()
        cards = set()
        for lane, nodes in d['lanes'].items():
            for c in nodes:
                cards.add(c['id'])
                self.assertEqual(c['lane'], lane)
                for r in c['rows']:
                    self.assertNotIn(r['id'], rows, "row ids are globally unique")
                    rows.add(r['id'])
                    self.assertEqual(r['card'], c['id'])
        for l in d['links']:
            self.assertIn(l['a'], rows, "link %s starts nowhere" % l['id'])
            self.assertIn(l['b'], rows, "link %s ends nowhere" % l['id'])
        for c in d['contains']:
            self.assertIn(c['from'], cards)
            self.assertIn(c['to'], cards)
        self.assertIn('r:%s' % tf.id, rows)
        self.assertIn('e:%s' % ep.id, {c['id'] for c in d['lanes']['feeds']})

    # =====================================================================
    # 15 — the Journey writes NOTHING
    # =====================================================================
    def test_15_journey_data_writes_nothing(self):
        """MF37's diff, not a promise. A source grep cannot see a write behind
        a helper; a row count around the call can."""
        cfg = self._config('P2 RO')
        rule = self._input(cfg, 'BASIC')
        conn = self._connector('P2 RO Conn')
        cfg.sudo().write({'connector_id': conn.id})
        ep = self._endpoint(conn)
        self._wire(conn, rule, 'base', endpoint=ep)
        self._sheet_file(cfg, ['Basic Salary'])
        tables = ['hr_formula_rule', 'hr_formula_config',
                  'hr_integration_field_mapping', 'hr_integration_connector',
                  'hr_integration_endpoint', 'hr_api_transformation_rule',
                  'hr_payslip_import_mapping', 'hr_formula_rule_source']

        def snapshot():
            out = {}
            for table in tables:
                self.env.cr.execute(
                    'SELECT count(*), coalesce(sum(id), 0) FROM %s'
                    % table)          # noqa: S608 — a fixed literal list
                out[table] = self.env.cr.fetchone()
            return out

        before = snapshot()
        self.Studio.journey_data(cfg.id)
        self.Studio.journey_data(cfg.id)
        self.env.flush_all()
        self.assertEqual(snapshot(), before,
                         "journey_data changed the database")

    # =====================================================================
    # 16 — the catalogue discovery is gone
    # =====================================================================
    def test_16_the_field_catalogue_is_never_asked(self):
        """`get_available_source_fields` is a data-store search PER CONNECTOR.
        v1 ran it on every connector on the database to print field counts on
        feeds this phase no longer draws."""
        cfg = self._config('P2 NoCat')
        rule = self._input(cfg, 'BASIC')
        gone = self._input(cfg, 'GONE', seq=2)
        conn = self._connector('P2 NoCat Conn')
        cfg.sudo().write({'connector_id': conn.id})
        ep = self._endpoint(conn)
        self._wire(conn, rule, 'base', endpoint=ep)
        # A DECLARED feed source, which is the shape that used to reach the
        # catalogue the long way round: `binding_dangling` computes
        # `dangling` per source row and that compute calls
        # `get_available_source_fields`. On abm it was 470 of the payload's
        # 492 queries — the call this method had just promised not to make.
        gone.set_source_binding('feed', 'no_such_key', origin='user')
        with patch.object(type(self.FieldMapping), 'get_available_source_fields',
                          autospec=True) as spy:
            spy.return_value = []
            d = self.Studio.journey_data(cfg.id)
        self.assertTrue(d['ok'])
        spy.assert_not_called()
        # …and the chip it answers is still answered, from the links.
        self.assertIn('dangling', d['counts'])

    # =====================================================================
    # 17 — what one read costs
    # =====================================================================
    def test_17_the_read_stays_inside_its_query_budget(self):
        """A landing tab is the screen people open by accident. v1 charged one
        catalogue discovery per connector plus one rule census of the whole
        database for a picture of one scheme; this is the ceiling that keeps
        that from coming back."""
        cfg = self._config('P2 Cost')
        for n in range(12):
            self._input(cfg, 'C%02d' % n, seq=n)
        conn = self._connector('P2 Cost Conn')
        cfg.sudo().write({'connector_id': conn.id})
        ep = self._endpoint(conn)
        for n, rule in enumerate(cfg.rule_ids):
            if n < 6:
                self._wire(conn, rule, 'base%s' % n, endpoint=ep)
        self.env.flush_all()
        self.env.invalidate_all()
        self.Studio.journey_data(cfg.id)        # warm the registry caches
        self.env.invalidate_all()
        before = self.env.cr.sql_log_count
        self.Studio.journey_data(cfg.id)
        cost = self.env.cr.sql_log_count - before
        self.assertLessEqual(
            cost, 80,
            "journey_data took %s queries for one scheme — the v1 shape "
            "(one catalogue discovery per connector, one rule census of the "
            "database) is back." % cost)
