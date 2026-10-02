# -*- coding: utf-8 -*-
"""A Zoho refusal must never read as an empty result set.

The incident this file exists for: a user pressed Sync on the ABM connector's
Employees feed, got no error, and got no data. The feed card said
`Synced <1h ago · 0 staged · 0 pulled` and the connector header said
`Connected`. Every one of those statements was produced by a failure.

The chain was four links long, and each link was individually defensible:

  1. the seeded path `forms/P_Employee/records` is not one Zoho serves;
  2. Zoho refused it with **HTTP 200** and the body
     `[{"message":"Invalid View Name","errorcode":7012,"Response status":2}]`,
     so `if response.status_code != 200` saw success;
  3. `data.get('response', {})` on that list raised `AttributeError: 'list'
     object has no attribute 'get'`, and `fetch_employees` wrapped its whole
     body in `except Exception: return []`;
  4. an empty list is a legal pull, so the feed stamped `success` — and since
     every other Zoho feed is a per-employee lookup driven by the stored
     employee list, an empty employee store made all seven feeds read empty.

These tests are payload-level and make no network call. The payloads are
verbatim from a live Zoho People tenant on 2026-08-26.
"""
from unittest.mock import Mock

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.integrations.zoho_connector import (
    ZohoApiError, ZohoConnector,
)

# ------------------------------------------------------- observed refusals
INVALID_VIEW = [{"message": "Invalid View Name", "errorcode": 7012,
                 "Response status": 2}]                       # HTTP 200
INCORRECT_URL = {"response": {"message": "Error occurred",
                              "uri": "/api/leave/getLeaveDetails",
                              "errors": {"code": 7201,
                                         "message": "Incorrect URL. Also "
                                                    "check for spelling errors"},
                              "status": 1}}                    # HTTP 404
MISSING_PARAM = {"response": {"message": "Error in fetching data",
                              "uri": "/api/timetracker/gettimesheet",
                              "errors": [{"code": 9002,
                                          "message": "No user parameter "
                                                     "specified."}],
                              "status": 1}}                    # HTTP 200
INVALID_USER = {"error": "Invalid User."}                      # HTTP 200

# ------------------------------------------------------- observed emptiness
# Zoho reports "nothing here" as an ERROR too, with the same `status: 1`
# envelope as a real refusal and the same HTTP 200. On the live ABM connector
# 98 of 152 employees had no overtime this month and answered with this.
NO_RECORDS = {"response": {"message": "Error occurred",
                           "uri": "/api/forms/overtime_request/getRecords",
                           "errors": {"code": 7024,
                                      "message": "No records found"},
                           "status": 1}}                       # HTTP 200

# ---------------------------------------------------------- observed data
EMPLOYEE_PAGE = {"response": {
    "result": [{"811648000007178001": [{"EmployeeID": "11708",
                                        "FirstName": "Thuy",
                                        "LastName": "Bui",
                                        "EmailID": "thuy.bui@abmauri.vn",
                                        "Department": "Finance",
                                        "Zoho_ID": 811648000007178001}]}],
    "message": "Data fetched successfully", "status": 0}}
SUMMARY_REPORT = {"summaryReport": [{"emailId": "chi.nguyen@abmauri.vn",
                                     "totalWorkedHours": 572400,
                                     "totalWorkedDays": 18}]}
USER_REPORT = {"2026-08-17": {"FirstIn": "17/08/2026 07:03 AM",
                              "TotalHours": "10:16"}}
EMPTY_TIMESHEET = {"response": {"result": [], "status": 0,
                                "message": "Data fetched successfully"}}


def _response(payload, status=200):
    """A `requests.Response` stand-in that answers `.json()` and `.status_code`."""
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    return response


@tagged('post_install', '-at_install')
class TestZohoResponseContract(TransactionCase):

    def setUp(self):
        super().setUp()
        connector = self.env['hr.integration.connector'].create({
            'name': 'Zoho response contract',
            'connector_type': 'zoho',
            'api_endpoint': 'https://people.zoho.com/people/api',
        })
        self.zoho = ZohoConnector(connector)

    # =================================================== a refusal is an error
    def test_http_200_refusals_raise_instead_of_reading_as_data(self):
        """The four shapes Zoho refuses with, three of them carrying 200 OK."""
        for label, payload, status in (
                ('invalid view (the incident)', INVALID_VIEW, 200),
                ('incorrect url', INCORRECT_URL, 404),
                ('missing parameter', MISSING_PARAM, 200),
                ('invalid user', INVALID_USER, 200)):
            with self.subTest(refusal=label):
                with self.assertRaises(ZohoApiError):
                    self.zoho._payload(_response(payload, status), 'the feed')

    def test_the_refusal_sentence_reaches_the_message(self):
        """A user who is told nothing goes looking in the server log.

        The point of raising is not the traceback, it is that the vendor's own
        words end up on the feed card.
        """
        for payload, expected in (
                (INVALID_VIEW, 'Invalid View Name'),
                (INCORRECT_URL, 'Incorrect URL'),
                (MISSING_PARAM, 'No user parameter specified.'),
                (INVALID_USER, 'Invalid User.')):
            with self.subTest(expected=expected):
                with self.assertRaises(ZohoApiError) as caught:
                    self.zoho._payload(_response(payload), 'the employee form')
                self.assertIn(expected, str(caught.exception))
                self.assertIn('the employee form', str(caught.exception))

    def test_success_is_not_mistaken_for_a_refusal(self):
        """`status: 0` and an empty result are data, and must pass through.

        The mirror risk of this fix: an over-eager error detector that turns
        every quiet period into a failure would be the same defect wearing the
        opposite sign.
        """
        for label, payload in (('employee page', EMPLOYEE_PAGE),
                               ('summary report', SUMMARY_REPORT),
                               ('user report', USER_REPORT),
                               ('empty but successful', EMPTY_TIMESHEET)):
            with self.subTest(payload=label):
                self.assertEqual(self.zoho._zoho_error(payload), '')
                self.zoho._payload(_response(payload), 'the feed')

    def test_no_records_found_is_emptiness_and_not_a_refusal(self):
        """Code 7024 is Zoho saying "nothing here", in a refusal's envelope.

        Caught on the live ABM run of this very fix: the overtime feed reported
        `98 of 152 employees failed` for 98 employees who simply had no
        overtime. It is also the answer to the page AFTER the last page of any
        paginated feed, so reading it as a refusal breaks pagination as well.
        """
        self.assertTrue(self.zoho._zoho_is_empty(NO_RECORDS))
        self.assertEqual(self.zoho._zoho_error(NO_RECORDS), '')
        payload = self.zoho._payload(_response(NO_RECORDS), 'the overtime form')
        # Normalised, so the leftover `errors` key cannot become a row.
        self.assertEqual(self.zoho._result_rows(payload), [])

    def test_a_real_refusal_alongside_emptiness_is_still_a_refusal(self):
        mixed = {"response": {"errors": [{"code": 7024, "message": "No records found"},
                                         {"code": 7201, "message": "Incorrect URL"}],
                              "status": 1}}
        self.assertFalse(self.zoho._zoho_is_empty(mixed))
        with self.assertRaises(ZohoApiError):
            self.zoho._payload(_response(mixed), 'the feed')

    def test_a_non_json_body_is_a_named_failure(self):
        response = Mock()
        response.status_code = 502
        response.json.side_effect = ValueError('no json')
        with self.assertRaises(ZohoApiError):
            self.zoho._payload(response, 'the feed')

    # ================================================== the shapes of the data
    def test_employee_rows_are_unwrapped_out_of_their_record_id_envelope(self):
        """`result: [{"<recordId>": [ {…fields…} ]}]` — one level deeper.

        Even with the path corrected, reading the OUTER dict would have given
        one employee per page whose every field was blank.
        """
        rows = self.zoho._result_rows(EMPLOYEE_PAGE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['EmployeeID'], '11708')

        parsed = self.zoho._parse_employee_record(rows[0])
        self.assertEqual(parsed['email'], 'thuy.bui@abmauri.vn')
        self.assertEqual(parsed['employee_id'], '11708')
        # A JSON number becomes a string here, not at each comparison site.
        self.assertEqual(parsed['id'], '811648000007178001')
        self.assertEqual(parsed['name'], 'Thuy Bui')

    def test_the_date_keyed_attendance_report_keeps_its_dates(self):
        rows = self.zoho._result_rows(USER_REPORT)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['_result_key'], '2026-08-17')
        self.assertEqual(rows[0]['TotalHours'], '10:16')

    # ============================================= the window Zoho will not do
    def test_leave_is_windowed_here_because_zoho_ignores_the_filter(self):
        """Zoho's form search accepts `From Between …` and then ignores it."""
        self.assertTrue(self.zoho._overlaps(
            '2026-08-28', '2026-08-29', '2026-08-01', '2026-08-31'))
        self.assertFalse(self.zoho._overlaps(
            '2026-09-02', '2026-09-03', '2026-08-01', '2026-08-31'))
        # Straddling the boundary counts: a leave that starts in July and ends
        # in August is an August payroll input.
        self.assertTrue(self.zoho._overlaps(
            '2026-07-28', '2026-08-02', '2026-08-01', '2026-08-31'))
        # An unreadable date is KEPT. Dropping it would silently shorten a
        # payroll input, which is the failure class this file guards.
        self.assertTrue(self.zoho._overlaps(
            '', '', '2026-08-01', '2026-08-31'))

    # ================================================ nobody to ask is an error
    def test_a_per_employee_feed_with_no_employees_says_so(self):
        """Six of the seven feeds are per-employee lookups.

        With an empty employee store each of them returns a clean, wordless
        zero — which is precisely the screen the user reported. It has to name
        its cause instead.
        """
        endpoint = Mock(name='Salary form', code='zohosalary')
        endpoint.name = 'Salary form'
        with self.assertRaises(ZohoApiError) as caught:
            self.zoho._require_employee_refs([], endpoint)
        self.assertIn('Employees feed', str(caught.exception))
        # A populated roster passes silently.
        self.zoho._require_employee_refs([{'id': '1'}], endpoint)

    def test_a_sweep_that_read_nobody_raises_rather_than_returning_zero(self):
        refs = [{'id': '1'}, {'id': '2'}]
        with self.assertRaises(ZohoApiError) as caught:
            self.zoho._report_failures(['Invalid User.', 'Invalid User.'],
                                       refs, [])
        self.assertIn('Invalid User.', str(caught.exception))
        # A PARTIAL failure keeps the rows it did read; only the log is told.
        self.zoho._report_failures(['Invalid User.'], refs, [{'payload': {}}])
        # And a clean sweep says nothing at all.
        self.zoho._report_failures([], refs, [{'payload': {}}])

    # ================================================ field discovery casing
    def test_form_components_are_read_with_zohos_own_lowercase_keys(self):
        """`labelname`/`displayname`/`comptype`, not `compLinkName`/`labelName`.

        The camelCase spellings this connector used matched nothing, so every
        discovered field was nameless and dropped, and "Fetch fields" reported
        that the vendor had returned none — of sixty it had just described.
        """
        components = {"response": {"result": [
            {"comptype": "Text", "ismandatory": True,
             "displayname": "Employee ID", "labelname": "EmployeeID"},
            {"comptype": "Email", "ismandatory": False,
             "displayname": "Email address", "labelname": "EmailID"},
        ]}}
        self.zoho.access_token = 'test'
        with self.patch_get(components):
            fields = self.zoho._get_form_fields('employee')
        self.assertEqual([f['name'] for f in fields],
                         ['EmployeeID', 'EmailID'])
        self.assertEqual(fields[0]['label'], 'Employee ID')
        self.assertTrue(fields[0]['required'])
        self.assertEqual(fields[0]['form'], 'employee')

    def patch_get(self, payload):
        from unittest.mock import patch
        return patch(
            'odoo.addons.pb_hr_payroll_formula.integrations.zoho_connector'
            '.requests.get', return_value=_response(payload))
