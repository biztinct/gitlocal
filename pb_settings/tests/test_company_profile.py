# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ACCESS P9 — "Your company", and the wall around it.

The surface is small; the guard is the whole phase. A customer's own
administrator may correct thirteen details on ONE record — their own company —
and nothing else on that record, and the answer to "which record" is decided on
the server from the user account rather than taken from the browser.

So these tests are written the way a tampered client would ask:

  * a plain internal user asking anyway;
  * a payload naming another company's id;
  * a request context claiming another company (`allowed_company_ids`, which is
    what `self.env.company` reads and is exactly why the facade does not);
  * a payload naming `currency_id`, `parent_id`, `partner_id`, `active`.

Every one of them must be refused, in a sentence a person could read, and none
of them may leave a single field written.
"""
import re

from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_settings.models.pb_company_profile import (
    AUDITED_FIELDS, EDITABLE_FIELDS, EDITABLE_KINDS, EDITABLE_WORDS,
    REFUSAL_WORDS,
)

# A 1x1 transparent PNG — a real picture, small enough to live in a test.
_PNG = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk'
        'YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')

# A source gate has to read the CODE, not the file: the paragraph explaining
# why `self.env.company` is the wrong thing to read has to be able to say
# `self.env.company` out loud (W101/W114, and D9's landmine two phases back).
_RE_DOCSTRING = re.compile(r'("""|\'\'\').*?\1', re.S)
_RE_HASH_COMMENT = re.compile(r'(?<!["\'])#[^\n]*')


def _code(src):
    """The Python source with its docstrings and `#` comments removed."""
    return _RE_HASH_COMMENT.sub('', _RE_DOCSTRING.sub('""', src))


class CompanyProfileCase(TransactionCase):
    """Three personas: a plain user, somebody who may, and the administrator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A database whose administrator account is switched off — the golden
        # template ships that way — refuses to create ANY user, because the
        # constraint that says a database must have an administrator reads the
        # group's user list and archived accounts are not in it (P5's finding).
        if not cls.env.ref('base.group_system').user_ids:
            admin = cls.env.ref('base.user_admin', raise_if_not_found=False)
            if admin:
                admin.sudo().write({'active': True})
        cls.company = cls.env.user.company_id
        cls.editor_group = cls.env.ref('pb_settings.group_company_editor')
        cls.plain = cls.env['res.users'].create({
            'name': 'P9 Plain', 'login': 'pbco_plain',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.editor = cls.env['res.users'].create({
            'name': 'P9 Editor', 'login': 'pbco_editor',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.editor_group.id])],
        })
        cls.boss = cls.env['res.users'].create({
            'name': 'P9 System', 'login': 'pbco_system',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('base.group_system').id])],
        })

    def facade(self, user):
        return self.env['pb.company.profile'].with_user(user)

    def other_company(self):
        """A second company to aim a forged call at."""
        return self.env['res.company'].sudo().create({'name': 'P9 Elsewhere'})


@tagged('post_install', '-at_install')
class TestTheWhitelistIsOneList(CompanyProfileCase):
    """The whitelist is written once; everything else is derived from it."""

    def test_the_whitelist_is_exactly_the_thirteen_agreed_details(self):
        self.assertEqual(
            list(EDITABLE_FIELDS),
            ['name', 'street', 'street2', 'city', 'zip', 'state_id',
             'country_id', 'phone', 'email', 'website', 'vat',
             'company_registry', 'logo'],
            "the owner approved the cosmetic and legal details: the name, the "
            "address, how people reach you, the tax and registration numbers "
            "and the logo. Anything added here widens what a customer's own "
            "administrator may change and needs saying out loud")

    def test_the_structural_fields_are_absent_and_therefore_refused(self):
        """A whitelist refuses by ABSENCE, which is what makes it a whitelist.

        Naming these here is not a second rule — it is a statement that the
        ones that would matter most really are outside the list, so that a
        future contributor adding a field cannot do it accidentally.
        """
        for field in ('currency_id', 'parent_id', 'child_ids', 'partner_id',
                      'user_ids', 'active', 'sequence', 'id',
                      'resource_calendar_id', 'parent_path', 'root_id'):
            self.assertNotIn(field, EDITABLE_KINDS,
                             "%s must not be editable by a tenant" % field)

    def test_every_whitelisted_field_is_really_on_the_company(self):
        Company = self.env['res.company']
        for field in EDITABLE_FIELDS:
            self.assertIn(
                field, Company._fields,
                "the whitelist names %s, which is not a field on a company — "
                "a save would fail with a technical error" % field)

    def test_the_audit_rule_watches_the_whitelist_minus_the_picture(self):
        """The rule is data and the whitelist is code; they must not drift.

        The logo is deliberately outside it: the generic audit writes a field's
        value into a text column, and for a picture that is a megabyte of
        encoded bytes — so the facade writes one readable line for it instead.
        """
        rule = self.env.ref('pb_settings.audit_rule_company_details')
        watched = [f.strip() for f in (rule.field_names or '').split(',')
                   if f.strip()]
        self.assertEqual(watched, list(AUDITED_FIELDS))
        self.assertNotIn('logo', watched)
        self.assertEqual(rule.model_name, 'res.company')
        self.assertTrue(rule.active)

    def test_the_browser_names_the_same_fields(self):
        """The boxes drawn in the browser and the fields the server accepts.

        A box for a field the server refuses is a box that can only produce a
        refusal; a field the server accepts with no box is one nobody can
        reach. Neither is visible at runtime, so it is read out of the source.
        """
        path = get_module_path('pb_settings') + '/static/src/js/company_profile.js'
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        block = src.split('const FIELDS = {', 1)[1].split('\n};', 1)[0]
        keys = re.findall(r'^\s{4}(\w+):\s*\{', block, re.M)
        self.assertEqual(sorted(keys + ['logo']), sorted(EDITABLE_FIELDS))


@tagged('post_install', '-at_install')
class TestWhoMayOpenIt(CompanyProfileCase):
    """Test 1 and test 3 — who gets in, and who is refused."""

    def test_somebody_with_the_company_permission_can_read_it(self):
        res = self.facade(self.editor).profile()
        self.assertEqual(res['company']['name'], self.company.name)
        self.assertFalse(res['is_system'],
                         "holding this permission must not make somebody an "
                         "administrator")
        self.assertTrue(res['countries'])
        self.assertTrue(res['fixed'],
                        "the page must say what it will NOT change")

    def test_a_system_administrator_can_read_it_too(self):
        res = self.facade(self.boss).profile()
        self.assertTrue(res['is_system'])

    def test_a_plain_user_is_refused_reading_it(self):
        with self.assertRaises(AccessError):
            self.facade(self.plain).profile()

    def test_a_plain_user_is_refused_saving_it(self):
        with self.assertRaises(AccessError):
            self.facade(self.plain).save({'name': 'Whatever Ltd'})
        self.assertNotEqual(self.company.name, 'Whatever Ltd')

    def test_a_plain_user_is_refused_the_state_list_too(self):
        """Every method on the facade is guarded, not just the write.

        A read-only helper left open is how the shape of a guarded surface
        leaks out of it.
        """
        with self.assertRaises(AccessError):
            self.facade(self.plain).states(1)

    def test_the_refusal_is_a_sentence_not_a_permission_name(self):
        with self.assertRaises(AccessError) as caught:
            self.facade(self.plain).profile()
        message = str(caught.exception)
        self.assertNotIn('group', message.lower())
        self.assertNotIn('res.company', message)
        self.assertIn('administers this application', message)


@tagged('post_install', '-at_install')
class TestTheWrite(CompanyProfileCase):
    """Test 1's other half — the change lands, and says what it did."""

    def test_it_writes_the_details_and_says_what_changed(self):
        res = self.facade(self.editor).save({
            'name': 'P9 Test Company',
            'street': '12 Test Street',
            'vat': 'P9-TAX-0001',
        })
        self.assertTrue(res['saved'])
        self.assertIn('the company name', res['sentence'])
        self.assertIn('the tax number', res['sentence'])
        self.assertEqual(self.company.name, 'P9 Test Company')
        self.assertEqual(self.company.street, '12 Test Street')
        self.assertEqual(self.company.vat, 'P9-TAX-0001')
        # and the fresh payload comes back with it, so the browser never has to
        # guess what the record now holds
        self.assertEqual(res['profile']['company']['name'], 'P9 Test Company')

    def test_a_picked_country_is_written_by_its_id(self):
        # A country the company is not already in — otherwise the facade
        # correctly answers "nothing had changed" and the test proves the
        # wrong thing (found on the first live run: the company was already
        # in the country the test picked).
        country = self.env['res.country'].search(
            [('id', '!=', self.company.country_id.id)], limit=1)
        if not country:
            self.skipTest('no country data on this database')
        # The province goes with the country, which is what the browser does
        # too: changing the country empties the province rather than leaving a
        # pair the server would then have to refuse.
        self.facade(self.editor).save({'country_id': country.id,
                                       'state_id': False})
        self.assertEqual(self.company.country_id, country)

    def test_the_logo_is_written_and_can_be_taken_off_again(self):
        self.facade(self.editor).save({'logo': _PNG})
        self.assertTrue(self.company.logo)
        self.facade(self.editor).save({'logo': False})
        self.assertFalse(self.company.logo)

    def test_an_unchanged_value_is_not_a_change(self):
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({'name': self.company.name})
        self.assertIn('Nothing had changed', str(caught.exception))

    def test_an_empty_name_is_refused_in_words(self):
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({'name': '   '})
        self.assertIn('has to have a name', str(caught.exception))

    def test_an_email_that_is_not_one_is_refused_in_words(self):
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({'email': 'not an address'})
        self.assertIn('@', str(caught.exception))

    def test_a_state_from_the_wrong_country_is_refused(self):
        state = self.env['res.country.state'].search(
            [('country_id', '!=', False)], limit=1)
        if not state:
            self.skipTest('no state data on this database')
        other = self.env['res.country'].search(
            [('id', '!=', state.country_id.id)], limit=1)
        if not other:
            self.skipTest('only one country on this database')
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({'state_id': state.id,
                                           'country_id': other.id})
        self.assertIn('is not in', str(caught.exception))

    def test_a_picture_that_is_not_one_is_refused(self):
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({'logo': 'this is not base64 !!!'})
        self.assertIn('not a picture', str(caught.exception))

    def test_the_state_list_is_the_country_that_was_asked_for(self):
        state = self.env['res.country.state'].search([], limit=1)
        if not state:
            self.skipTest('no state data on this database')
        rows = self.facade(self.editor).states(state.country_id.id)
        self.assertIn(state.id, [r['id'] for r in rows])


@tagged('post_install', '-at_install')
class TestTheForgedCall(CompanyProfileCase):
    """Test 2 — the whole point of the phase.

    Everything here is a call that could only come from an edited client.
    """

    def test_a_blocked_field_is_refused_and_nothing_at_all_is_written(self):
        """One blocked field poisons the WHOLE call, on purpose.

        A save that applied the twelve good fields and dropped the blocked one
        would be indistinguishable, to the person who sent it, from one that
        did what they asked.
        """
        before = self.company.name
        other = self.env['res.currency'].search(
            [('id', '!=', self.company.currency_id.id)], limit=1)
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({
                'name': 'Forged Ltd',
                'currency_id': other.id if other else 1,
            })
        message = str(caught.exception)
        self.assertIn('the currency this company keeps its books in', message)
        self.assertEqual(self.company.name, before,
                         "a refused call must write nothing at all")

    def test_the_hierarchy_is_refused(self):
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({'parent_id': self.company.id})
        self.assertIn('which company this one sits under',
                      str(caught.exception))
        self.assertFalse(self.company.parent_id)

    def test_a_company_id_in_the_payload_is_refused(self):
        other = self.other_company()
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({'id': other.id, 'name': 'Forged'})
        self.assertIn('which company this page is about', str(caught.exception))
        self.assertEqual(other.name, 'P9 Elsewhere')

    def test_re_pointing_the_contact_record_is_refused(self):
        with self.assertRaises(UserError):
            self.facade(self.editor).save({'partner_id': 1})

    def test_switching_the_company_off_is_refused(self):
        with self.assertRaises(UserError):
            self.facade(self.editor).save({'active': False})
        self.assertTrue(self.company.active)

    def test_an_invented_field_is_refused_without_being_echoed_back(self):
        """A name the server has never heard of gets the general sentence.

        Echoing an arbitrary string from a payload back into a message is a
        string from a payload rendered on a page, and it tells the person
        reading it nothing they did not already know.
        """
        with self.assertRaises(UserError) as caught:
            self.facade(self.editor).save({'<script>x</script>': 'x'})
        message = str(caught.exception)
        self.assertNotIn('script', message)
        self.assertIn('It changes nothing else about your company.', message)

    def test_a_context_naming_another_company_cannot_redirect_the_write(self):
        """THE ONE THAT MATTERS MOST.

        `self.env.company` reads `allowed_company_ids` out of the request
        context, which the browser sends. The facade reads the USER record's
        own company instead, so a call that claims to be "in" another company
        still writes to the caller's own — there is nowhere for the claim to
        land.
        """
        other = self.other_company()
        self.editor.sudo().write({'company_ids': [(4, other.id)]})
        forged = self.env['pb.company.profile'].with_user(self.editor)\
            .with_context(allowed_company_ids=[other.id, self.company.id])
        forged.save({'name': 'Aimed Elsewhere Ltd'})
        self.assertEqual(other.name, 'P9 Elsewhere',
                         "the other company must be untouched")
        self.assertEqual(self.company.name, 'Aimed Elsewhere Ltd',
                         "the write belongs to the caller's own company")

    def test_with_company_cannot_redirect_the_write_either(self):
        other = self.other_company()
        self.editor.sudo().write({'company_ids': [(4, other.id)]})
        self.env['pb.company.profile'].with_user(self.editor)\
            .with_company(other).save({'city': 'Aimed Elsewhere'})
        self.assertFalse(other.city)
        self.assertEqual(self.company.city, 'Aimed Elsewhere')

    def test_the_facade_takes_no_company_argument_at_all(self):
        """Read out of the source, because it is a property of the SHAPE.

        A behaviour test can only prove that today's arguments are ignored; the
        thing to defend is that a company argument is never added.
        """
        path = get_module_path('pb_settings') + '/models/pb_company_profile.py'
        with open(path, encoding='utf-8') as fh:
            src = _code(fh.read())
        for signature in re.findall(r'^\s+def (profile|save|states)\(([^)]*)\)',
                                    src, re.M):
            args = [a.strip() for a in signature[1].split(',')]
            for arg in args:
                self.assertNotIn(
                    'company', arg,
                    "%s takes %s — the caller's company is resolved on the "
                    "server and must never be accepted from the browser"
                    % (signature[0], arg))
        self.assertIn('self.env.user.company_id', src)
        self.assertNotIn('self.env.company', src,
                         "self.env.company reads allowed_company_ids out of "
                         "the request context, which the browser controls")


@tagged('post_install', '-at_install')
class TestTheAuditLine(CompanyProfileCase):
    """Test 5 — who changed what, and when."""

    def _entries(self, field=None):
        domain = [('model_name', '=', 'res.company'),
                  ('res_id', '=', self.company.id)]
        if field:
            domain.append(('field_name', '=', field))
        return self.env['biz.audit.entry'].sudo().search(domain)

    def test_a_change_writes_one_line_naming_who_what_and_when(self):
        before = self._entries('vat')
        self.facade(self.editor).save({'vat': 'P9-AUDIT-42'})
        new = self._entries('vat') - before
        self.assertEqual(len(new), 1)
        self.assertEqual(new.user_id, self.editor,
                         "the actor is forced server-side, never sent")
        self.assertEqual(new.new_value, 'P9-AUDIT-42')
        self.assertTrue(new.stamp)
        self.assertEqual(new.company_id, self.company,
                         "an entry about a company belongs to that company")

    def test_the_surface_reads_its_own_history_back(self):
        self.facade(self.editor).save({'city': 'P9 Audit City'})
        history = self.facade(self.editor).profile()['history']
        self.assertTrue(history)
        top = history[0]
        self.assertEqual(top['who'], self.editor.name)
        self.assertEqual(top['what'], EDITABLE_WORDS['city'])
        self.assertEqual(top['to'], 'P9 Audit City')
        self.assertTrue(top['when'])

    def test_the_logo_is_logged_in_words_not_in_bytes(self):
        self.facade(self.editor).save({'logo': _PNG})
        entry = self._entries('logo')[:1]
        self.assertTrue(entry)
        self.assertLess(len(entry.new_value or ''), 40,
                        "a picture must never be written into the trail as "
                        "its own bytes")
        self.assertIn('picture', entry.new_value)

    def test_a_change_made_anywhere_else_is_recorded_too(self):
        """The mixin is on the MODEL, so the platform's own Companies screen
        is audited by the same rule — a trail that only knows about one of two
        doors is a trail that says a change was never made."""
        before = self._entries('name')
        self.company.sudo().write({'name': 'Written From Elsewhere'})
        self.assertEqual(len(self._entries('name') - before), 1)


@tagged('post_install', '-at_install')
class TestTheCopy(CompanyProfileCase):
    """Test 8 — plain English, and never the product this is built on."""

    FILES = ('models/pb_company_profile.py',
             'static/src/js/company_profile.js',
             'static/src/xml/company_profile.xml')

    def _sentences(self):
        """Every user-visible string this phase adds."""
        out = []
        path = get_module_path('pb_settings')
        with open(path + '/models/pb_company_profile.py', encoding='utf-8') as fh:
            src = fh.read()
        out += re.findall(r'_\(\s*"([^"]+)"', src)
        out += list(EDITABLE_WORDS.values()) + list(REFUSAL_WORDS.values())
        with open(path + '/static/src/js/company_profile.js', encoding='utf-8') as fh:
            out += re.findall(r'_t\(\s*"([^"]+)"', fh.read())
        return out

    def test_no_technical_field_or_model_name_is_ever_shown(self):
        for sentence in self._sentences():
            for technical in ('res.company', 'res.partner', 'currency_id',
                              'parent_id', 'company_id', 'vat',
                              'company_registry', 'ir.model', 'group_'):
                self.assertNotIn(
                    technical, sentence,
                    "a person is shown %r, which is what the database calls "
                    "it, not what the screen does: %r" % (technical, sentence))

    def test_the_product_this_is_built_on_is_never_named(self):
        for name in self.FILES:
            path = get_module_path('pb_settings') + '/' + name
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            # The engineering comments may (and do) name it — an engineer
            # reading this needs the real name. Only the strings a USER sees
            # are read: the translated ones everywhere, plus the plain text
            # nodes of the template.
            strings = re.findall(r'_t?\(\s*"([^"]+)"', src)
            if name.endswith('.xml'):
                strings += re.findall(r'>([^<>{]{4,})<', src)
            for sentence in strings:
                self.assertNotIn(
                    'Odoo', sentence,
                    "%s shows a user the word Odoo: %r" % (name, sentence))
