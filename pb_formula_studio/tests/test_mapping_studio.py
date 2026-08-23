# -*- coding: utf-8 -*-
"""Integrations Cycle 2 — the Mapping Studio's server contract.

The cockpit is OWL and its own correctness only shows at runtime (C18.71/W10),
so what is gated here is the six properties underneath it that fail SILENTLY:

  * a picker that lists a connector the caller cannot read, or resolves an
    arrival context onto a different scheme without saying so. A deep link that
    lands wrong looks exactly like a deep link that landed right — this
    codebase's worst bug class (W76.3/W117), and the reason `mapping_pickers`
    reports `fell_back` at all (tests 1, 1b, 4b);
  * a feed filter that quietly drops the mappings drawn before feeds existed.
    Those wires have no `endpoint_id`, and hiding them would look like an
    operator's work had been deleted (test 2);
  * `endpoint_id` accepted from the browser without being checked against the
    connector it was drawn on — every count on two screens then disagrees and
    nothing errors (test 2b);
  * a sample line that crashes on a feed with no stored payload, or that
    invents the `hr.employee` schema as if it were the leave API's shape
    (test 3);
  * a board that leaks wires between configurations (test 4);
  * `python` reaching `api_transform_save` from a client path. The whitelist is
    W12 and the only proof is asking for one (test 5).

And test 6 re-asserts the never-overwrite shape of a template apply on the new
surface's path, because the studio calls it with a connector the overlay never
passed.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMappingStudio(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Conn = cls.env['hr.integration.connector']
        cls.EP = cls.env['hr.integration.endpoint']
        cls.Store = cls.env['hr.api.data.store']
        cls.FM = cls.env['hr.integration.field.mapping']
        cls.Config = cls.env['hr.formula.config']

    # ------------------------------------------------------------- fixtures
    def _config(self, name, codes):
        cfg = self.Config.create({
            'name': name, 'code': name.replace(' ', '_').upper(),
            'country_code': 'VN', 'state': 'active',
        })
        for i, code in enumerate(codes):
            # MAPFIX A: hr.formula.rule.code is shape-constrained (uppercase
            # alphanumeric). The fixture spells its columns in lowercase for
            # readability; the model is handed the code it will actually enforce.
            self.env['hr.formula.rule'].create({
                'config_id': cfg.id, 'name': code.title(), 'code': code.upper(),
                'column_type': 'input', 'sequence': (i + 1) * 10,
            })
        return cfg

    def _connector(self, name='IG-C2 probe'):
        return self.Conn.create({'name': name, 'connector_type': 'demo'})

    def _store(self, conn, data_type, payload):
        return self.Store.create({
            'connector_id': conn.id, 'data_type': data_type,
            'raw_payload': payload,
        })

    def _endpoint(self, conn, code, data_type):
        return self.EP.create({
            'connector_id': conn.id, 'code': code,
            'name': code.replace('_', ' ').title(), 'data_type': data_type,
        })

    # --------------------------------------------------------------- test 1
    def test_01_the_pickers_offer_what_the_caller_may_read(self):
        conn = self._connector('IG-C2 pickers')
        ep = self._endpoint(conn, 'c2_employees', 'employee')
        cfg = self._config('IG-C2 scheme', ['basic', 'allowance'])

        d = self.Studio.mapping_pickers()
        self.assertTrue(d['ok'])

        # the connector scope IS `search([])` — the same answer
        # `pb.integrations._readable_connectors` settles on, and for the same
        # reason: the record rules already made the decision.
        listed = {c['id'] for c in d['connectors']}
        self.assertEqual(listed, set(self.Conn.search([]).ids),
                         "the pickers must offer exactly the connectors the "
                         "caller's own record rules allow")
        row = next(c for c in d['connectors'] if c['id'] == conn.id)
        self.assertEqual([e['id'] for e in row['endpoints']], [ep.id])
        self.assertEqual(row['endpoints'][0]['data_type'], 'employee')
        self.assertTrue(row['endpoints'][0]['data_type_label'],
                        "a feed option needs a human label, not a key")

        cfg_row = next(c for c in d['configs'] if c['id'] == cfg.id)
        self.assertEqual(cfg_row['column_count'], 2)
        self.assertEqual(cfg_row['input_count'], 2)
        self.assertEqual(cfg_row['country'], 'VN')

    def test_01b_an_unresolvable_arrival_falls_back_and_says_so(self):
        """The whole reason `fell_back` exists.

        Silence here is the failure mode: the studio would render a perfectly
        confident header naming a scheme the link did not ask for, and the only
        way to notice would be to already know the answer.
        """
        d = self.Studio.mapping_pickers({'config_id': 99999999,
                                         'connector_id': 99999998})
        self.assertIn('config', d['defaults']['fell_back'])
        self.assertIn('connector', d['defaults']['fell_back'])
        self.assertNotEqual(d['defaults']['config_id'], 99999999)

        # …and an arrival it CAN honour is honoured, silently.
        cfg = self._config('IG-C2 arrival', ['basic'])
        conn = self._connector('IG-C2 arrival conn')
        ep = self._endpoint(conn, 'c2_arrival', 'employee')
        d = self.Studio.mapping_pickers({'config_id': cfg.id,
                                         'connector_id': conn.id,
                                         'endpoint_id': ep.id})
        self.assertEqual(d['defaults']['config_id'], cfg.id)
        self.assertEqual(d['defaults']['connector_id'], conn.id)
        self.assertEqual(d['defaults']['endpoint_id'], ep.id)
        self.assertEqual(d['defaults']['fell_back'], [])

    def test_01d_a_junk_arrival_context_is_answered_not_raised(self):
        """A context key is written by whoever built the link and read back out
        of the browser, so it is not guaranteed to be a number. `int()` on a
        stale or hand-built value is a 500 on the screen whose entire job is to
        be the friendly front door."""
        for junk in ('', None, 'zoho', [], {'a': 1}, '12abc'):
            d = self.Studio.mapping_pickers({'config_id': junk,
                                             'connector_id': junk,
                                             'endpoint_id': junk})
            self.assertTrue(d['ok'])
            self.assertIsInstance(d['defaults']['config_id'], int)

    def test_01e_a_connector_link_lands_on_the_scheme_it_actually_feeds(self):
        """The board's "N mappings" is a door, and it must not contradict the
        number it was printed on.

        Found live: clicking "6 mappings" on a connector card opened the studio
        on the DEFAULT scheme, which that connector feeds not at all, so the
        story bar answered "0 mapped" to a user who had just clicked six.
        """
        conn = self._connector('IG-C2 resolver')
        self._store(conn, 'employee', {'basic': 1, 'bonus': 2})
        quiet = self._config('IG-C2 resolver quiet', ['basic'])
        loud = self._config('IG-C2 resolver loud', ['basic', 'bonus'])
        for path, rule in (('f:basic', loud.rule_ids.filtered(lambda r: r.code == 'BASIC')),
                           ('f:bonus', loud.rule_ids.filtered(lambda r: r.code == 'BONUS'))):
            self.Studio.api_mapping_create(loud.id, conn.id, path, rule.id)

        d = self.Studio.mapping_pickers({'connector_id': conn.id})
        self.assertEqual(d['defaults']['connector_id'], conn.id)
        self.assertEqual(d['defaults']['config_id'], loud.id,
                         "a connector-only link must land on the scheme that "
                         "connector actually feeds, not on the default")
        self.assertEqual(d['defaults']['fell_back'], [])
        self.assertNotEqual(loud.id, quiet.id)

        # an EXPLICIT config still wins over the resolver — precedence is
        # explicit > derived > default, and it must not be quietly reordered.
        d2 = self.Studio.mapping_pickers({'connector_id': conn.id,
                                          'config_id': quiet.id})
        self.assertEqual(d2['defaults']['config_id'], quiet.id)

    def test_01c_a_feed_from_another_connector_is_refused_not_shown(self):
        a = self._connector('IG-C2 A')
        b = self._connector('IG-C2 B')
        ep_b = self._endpoint(b, 'c2_b_feed', 'employee')
        d = self.Studio.mapping_pickers({'connector_id': a.id,
                                         'endpoint_id': ep_b.id})
        self.assertEqual(d['defaults']['connector_id'], a.id)
        self.assertEqual(d['defaults']['endpoint_id'], 0)
        self.assertIn('endpoint', d['defaults']['fell_back'])

    # --------------------------------------------------------------- test 2
    def test_02_a_feed_narrows_the_board_without_losing_legacy_wires(self):
        conn = self._connector('IG-C2 feeds')
        cfg = self._config('IG-C2 feed scheme', ['basic', 'leavedays'])
        emp_ep = self._endpoint(conn, 'c2_emp', 'employee')
        self._endpoint(conn, 'c2_leave', 'leave')
        self._store(conn, 'employee', {'employee_id': 'E1', 'basic': 100})
        self._store(conn, 'leave', {'leave_days': 3, 'leave_type': 'AL'})

        basic = cfg.rule_ids.filtered(lambda r: r.code == 'BASIC')
        leavedays = cfg.rule_ids.filtered(lambda r: r.code == 'LEAVEDAYS')

        # a mapping drawn BEFORE feeds existed — no endpoint_id
        legacy = self.FM.create({
            'connector_id': conn.id, 'source_field': 'leave_days',
            'target_rule_id': leavedays.id, 'source_field_label': 'Leave Days'})
        self.assertFalse(legacy.endpoint_id)

        d = self.Studio.api_mapping_data(cfg.id, conn.id, emp_ep.id)
        self.assertTrue(d['ok'])
        paths = {i['id'] for i in d['left']}
        self.assertIn('f:basic', paths, "the employee feed's own fields")
        self.assertIn('f:employee_id', paths)
        self.assertNotIn('f:leave_type', paths,
                         "an unmapped field of ANOTHER feed must not be here")

        # the legacy wire survives, and its source is on the board, grouped
        legacy_wire = [w for w in d['wires'] if w['ref'] == legacy.id]
        self.assertEqual(len(legacy_wire), 1,
                         "a mapping with no feed must not vanish when a feed "
                         "is picked — that reads as deleted work")
        item = next(i for i in d['left'] if i['id'] == 'f:leave_days')
        self.assertEqual(item['group'], 'Unassigned')
        self.assertEqual(
            next(i for i in d['left'] if i['id'] == 'f:basic')['group'],
            emp_ep.name, "this feed's own fields are grouped under its name")

        # and the unfiltered board is unchanged for the overlay
        allb = self.Studio.api_mapping_data(cfg.id, conn.id)
        self.assertIn('f:leave_type', {i['id'] for i in allb['left']})
        self.assertFalse(allb['endpoint_id'])

    def test_02b_a_created_wire_is_stamped_with_the_feed_it_was_drawn_on(self):
        conn = self._connector('IG-C2 stamp')
        other = self._connector('IG-C2 stamp other')
        cfg = self._config('IG-C2 stamp scheme', ['basic'])
        ep = self._endpoint(conn, 'c2_stamp', 'employee')
        foreign = self._endpoint(other, 'c2_foreign', 'employee')
        basic = cfg.rule_ids[0]

        self.Studio.api_mapping_create(cfg.id, conn.id, 'f:basic', basic.id, ep.id)
        m = self.FM.search([('connector_id', '=', conn.id),
                            ('target_rule_id', '=', basic.id)])
        self.assertEqual(m.endpoint_id, ep)

        # an id from the browser naming ANOTHER connector's feed is dropped,
        # not filed — a mapping under a feed that cannot produce it makes every
        # count on both screens wrong, quietly.
        self.Studio.api_mapping_create(cfg.id, conn.id, 'f:basic', basic.id,
                                       foreign.id)
        m = self.FM.search([('connector_id', '=', conn.id),
                            ('target_rule_id', '=', basic.id)])
        self.assertFalse(m.endpoint_id)

        # no feed given → no stamp, and the wire still works (the overlay path)
        self.Studio.api_mapping_create(cfg.id, conn.id, 'f:basic', basic.id)
        m = self.FM.search([('connector_id', '=', conn.id),
                            ('target_rule_id', '=', basic.id)])
        self.assertTrue(m)
        self.assertFalse(m.endpoint_id)

    # --------------------------------------------------------------- test 3
    def test_03_left_items_carry_a_sample_and_do_not_crash_without_one(self):
        conn = self._connector('IG-C2 samples')
        cfg = self._config('IG-C2 sample scheme', ['basic'])
        ep = self._endpoint(conn, 'c2_sample', 'employee')
        self._store(conn, 'employee',
                    {'basic': 12345.67, 'name': 'Nguyen Van A', 'nested': {'x': 1}})

        d = self.Studio.api_mapping_data(cfg.id, conn.id, ep.id)
        by_id = {i['id']: i for i in d['left']}
        self.assertEqual(by_id['f:name']['sample'], 'Nguyen Van A')
        self.assertTrue(by_id['f:basic']['sample'])

        # a feed with NO rows on a connector that has rows: an empty field list
        # and an empty board, never the hr.employee schema dressed up as this
        # API's shape.
        empty_ep = self._endpoint(conn, 'c2_empty', 'attendance')
        d2 = self.Studio.api_mapping_data(cfg.id, conn.id, empty_ep.id)
        self.assertTrue(d2['ok'])
        self.assertEqual(d2['left'], [])

        # a connector with no store rows at all still offers something to map
        bare = self._connector('IG-C2 bare')
        d3 = self.Studio.api_mapping_data(cfg.id, bare.id)
        self.assertTrue(d3['left'], "a brand-new connector must still offer the "
                                    "employee schema as a starting point")
        self.assertTrue(all('sample' in i for i in d3['left']))

    def test_03b_a_long_or_structured_sample_is_trimmed_not_dropped(self):
        self.assertEqual(self.Studio._sample_text(None), '')
        self.assertEqual(self.Studio._sample_text(False), '')
        self.assertEqual(self.Studio._sample_text('short'), 'short')
        long_ = self.Studio._sample_text('x' * 200)
        self.assertEqual(len(long_), 46)
        self.assertTrue(long_.endswith('…'))
        self.assertIn('a', self.Studio._sample_text({'a': 1}))
        # 0 is a VALUE, not an absence. The tidy `if not value: return ''`
        # would eat every zero — the same `0 == False` trap `_section` was
        # written around in pb_integrations.
        self.assertEqual(self.Studio._sample_text(0), '0')

    def test_03c_a_wire_remembers_the_sample_the_board_showed(self):
        """Found on the live pass, and the reason the preview was empty.

        Every left card prints its sample; `api_mapping_create` dropped it, so
        the transform popover — the very next click — answered "No sample value
        stored" about a field whose sample was on screen beside it.
        """
        conn = self._connector('IG-C2 create sample')
        cfg = self._config('IG-C2 create sample scheme', ['hours'])
        ep = self._endpoint(conn, 'c2_cs', 'employee')
        self._store(conn, 'employee', {'seconds_worked': 7200, 'name': 'A'})
        rule = cfg.rule_ids[0]

        self.Studio.api_mapping_create(cfg.id, conn.id, 'f:seconds_worked',
                                       rule.id, ep.id)
        m = self.FM.search([('connector_id', '=', conn.id),
                            ('target_rule_id', '=', rule.id)])
        self.assertEqual(m.source_sample_value, '7200')
        self.assertEqual(m.source_data_type, 'integer')

        # …and the preview the user opens next actually previews something
        prev = self.Studio.api_transform_preview(
            m.id, {'transformation_type': 'divide', 'transformation_value': 3600})
        self.assertTrue(prev.get('ok'), prev)
        self.assertFalse(prev.get('no_sample'),
                         "the popover must not say 'no sample stored' about a "
                         "field the board is printing a sample for")
        self.assertEqual(float(prev['result']), 2.0)

        # a path the connector has never delivered stays honestly blank
        self.Studio.api_mapping_create(cfg.id, conn.id, 'f:not_a_field',
                                       rule.id, ep.id)
        m2 = self.FM.search([('connector_id', '=', conn.id),
                             ('source_field', '=', 'not_a_field')])
        self.assertFalse(m2.source_sample_value)

    # --------------------------------------------------------------- test 4
    def test_04_two_configs_on_one_connector_never_share_wires(self):
        conn = self._connector('IG-C2 two configs')
        self._store(conn, 'employee', {'basic': 1, 'bonus': 2})
        a = self._config('IG-C2 cfg A', ['basic'])
        b = self._config('IG-C2 cfg B', ['basic'])

        self.Studio.api_mapping_create(a.id, conn.id, 'f:basic', a.rule_ids[0].id)
        da = self.Studio.api_mapping_data(a.id, conn.id)
        db = self.Studio.api_mapping_data(b.id, conn.id)
        self.assertEqual(len([w for w in da['wires'] if w['state'] == 'accepted']), 1)
        self.assertEqual(len([w for w in db['wires'] if w['state'] == 'accepted']), 0,
                         "a wire drawn on one scheme must not appear on another")

        self.Studio.api_mapping_create(b.id, conn.id, 'f:bonus', b.rule_ids[0].id)
        da = self.Studio.api_mapping_data(a.id, conn.id)
        self.assertEqual(
            {w['leftId'] for w in da['wires'] if w['state'] == 'accepted'},
            {'f:basic'},
            "creating on B must not touch A — the boards are per configuration")

    # --------------------------------------------------------------- test 5
    def test_05_a_transform_round_trips_and_python_is_refused(self):
        conn = self._connector('IG-C2 transform')
        cfg = self._config('IG-C2 transform scheme', ['hours'])
        self._store(conn, 'employee', {'seconds_worked': 7200})
        rule = cfg.rule_ids[0]
        self.Studio.api_mapping_create(cfg.id, conn.id, 'f:seconds_worked', rule.id)
        m = self.FM.search([('connector_id', '=', conn.id),
                            ('target_rule_id', '=', rule.id)])

        prev = self.Studio.api_transform_preview(
            m.id, {'transformation_type': 'divide', 'transformation_value': 3600})
        self.assertTrue(prev.get('ok'), prev)
        self.assertIn('result', prev)
        # the preview must not have written anything
        self.assertEqual(m.transformation_type, 'direct')

        res = self.Studio.api_transform_save(
            m.id, {'transformation_type': 'divide', 'transformation_value': 3600,
                   'transformation_decimals': 2})
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(m.transformation_type, 'divide')
        self.assertEqual(m.transformation_value, 3600)
        self.assertEqual(res['transform']['type'], 'divide')

        # W12 — the canvas is not a code-authoring surface and no client path
        # may make it one.
        bad = self.Studio.api_transform_save(
            m.id, {'transformation_type': 'python',
                   'transformation_code': 'result = 1'})
        self.assertFalse(bad.get('ok'))
        self.assertEqual(m.transformation_type, 'divide',
                         "a refused save must change nothing")
        self.assertNotIn('transformation_code', str(bad))

    # --------------------------------------------------------------- test 6
    def test_06_a_template_apply_never_overwrites_an_existing_wire(self):
        conn = self._connector('IG-C2 template')
        cfg = self._config('IG-C2 template scheme', ['basic', 'bonus'])
        self._store(conn, 'employee', {'basic': 1, 'bonus': 2})
        basic = cfg.rule_ids.filtered(lambda r: r.code == 'BASIC')

        tpl = self.env['hr.formula.mapping.template'].create({
            'name': 'IG-C2 vendor', 'adapter': 'api',
            'line_ids': [
                (0, 0, {'source_key': 'basic', 'target_code': 'BASIC'}),
                (0, 0, {'source_key': 'bonus', 'target_code': 'BONUS'}),
                (0, 0, {'source_key': 'nowhere', 'target_code': 'nosuchcode'}),
            ],
        })
        # one wire already drawn by hand, with a transform on it
        self.Studio.api_mapping_create(cfg.id, conn.id, 'f:basic', basic.id)
        mine = self.FM.search([('connector_id', '=', conn.id),
                               ('target_rule_id', '=', basic.id)])
        self.Studio.api_transform_save(
            mine.id, {'transformation_type': 'multiply', 'transformation_value': 2})

        res = self.Studio.mapping_template_apply(tpl.id, cfg.id, conn.id)
        self.assertTrue(res['ok'], res)
        for key in ('applied', 'skipped_existing', 'unmatched_sources',
                    'unmatched_targets'):
            self.assertIn(key, res)
        self.assertEqual([a['target'] for a in res['applied']], ['BONUS'])
        self.assertEqual([s['target'] for s in res['skipped_existing']], ['BASIC'])
        self.assertIn('nowhere', res['unmatched_sources'])
        self.assertIn('nosuchcode', res['unmatched_targets'])
        # the hand-drawn transform survived untouched
        self.assertEqual(mine.transformation_type, 'multiply')
        self.assertEqual(mine.transformation_value, 2)

    # ------------------------------------------------------- the five adapters
    def test_07_every_adapter_still_answers_the_shape_the_canvas_needs(self):
        """The studio and the overlay call the SAME five adapters.

        Cycle 2 changed one of them (`api_mapping_data` grew an argument) and
        the binding non-goal was that the other four are untouched. The cheap
        proof is that all five still return the keys the canvas mounts on: a
        missing `wires` is an OWL crash at mount, which no python test above
        would ever see.
        """
        cfg = self._config('IG-C2 adapters', ['basic'])
        for payload in (
            self.Studio.api_mapping_data(cfg.id),
            self.Studio.import_mapping_data(cfg.id),
            self.Studio.employee_mapping_data(cfg.id),
            self.Studio.scheme_mapping_data(cfg.id),
            self.Studio.mapping_canvas_data(cfg.id),
        ):
            self.assertIn('ok', payload)
            if not payload['ok']:
                # a refusal must say WHY, or the studio has nothing to print
                self.assertIn('reason', payload)
                continue
            for key in ('left', 'right', 'wires', 'can_edit'):
                self.assertIn(key, payload)


# ============================================ Integrations Cycle 7 — WP-4
#
# The floating launchers are offset off the TO column on this board and nowhere
# else. Cycle 6 wrote that offset as `right: 380px`, a number measured at the
# 1900px viewport it was tested on; at the owner's 1450px the FAB lands at
# x 968-1070 against a column starting at 1110 — correct by 40px of luck rather
# than by construction, and silently wrong the day the column width changes.
#
# The offset is now stated as what it is: one column, plus a gutter. Both files
# read the column width from the same custom property, and this asserts they
# still do — a CSS mismatch renders, so nothing else would ever notice.
@tagged('post_install', '-at_install')
class TestLauncherOffsetFollowsTheColumn(TransactionCase):

    def _scss(self, name):
        import os
        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('pb_formula_studio'),
                            'static', 'src', 'scss', name)
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_50_the_launcher_offset_is_one_column_not_a_measured_number(self):
        studio = self._scss('mapping_studio.scss')
        block = studio.split('.o_web_client:has(.pbim.pbms .pbms-wrap)', 1)
        self.assertEqual(len(block), 2, 'the launcher-offset rule has gone')
        rule = block[1].split('\n}', 1)[0]
        for sel in ('.lrn-fab', '.payai-floating-pill'):
            self.assertIn(sel, rule, '%s is no longer moved off the column' % sel)
        self.assertIn('var(--mc-col-w)', rule,
                      'the offset is a magic number again; it has to be '
                      'derived from the column it is avoiding')
        self.assertIn('--mc-col-w:', rule,
                      'the property the offset reads must be set on the same '
                      'host, or it resolves to nothing on a sibling')

    def test_51_the_column_reads_the_same_property_the_offset_does(self):
        canvas = self._scss('mapping.scss')
        self.assertIn('.mapping-canvas .mc-col { width: var(--mc-col-w,', canvas,
                      'the column stopped consuming the property the launcher '
                      'offset is computed from — the two can now disagree '
                      'without either file changing')
