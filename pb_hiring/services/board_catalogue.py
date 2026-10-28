"""Reviewed destinations and onboarding instructions, not claims of API access.

`route` describes implemented delivery, while `evidence` describes the provider's
documented offer. A saved onboarding note can never activate a connector.
"""

COUNTRIES = {'IN': 'India', 'VN': 'Vietnam', 'ID': 'Indonesia'}


def board(key, name, countries, audience, route, url, evidence, customer, platform):
    return dict(key=key, name=name, countries=list(countries), audience=audience,
                route=route, url=url, evidence=evidence, customer=customer,
                platform=platform)


PARTNER_TASK = ('Payobook must obtain the current integration specification, partner permission, '
                'test resources and production approval, then build and test the connector.')
ACCOUNT_TASK = ('The employer supplies a verified employer account, any required subscription '
                'and authorization to connect. Do not put passwords or API keys in setup notes.')
FEED_TASK = ('Payobook provides the feed and tracked application links. Arrange feed acceptance '
             'and market coverage with the provider; a feed fetch does not confirm publication.')

BOARDS = [
    board('linkedin', 'LinkedIn', (), 'Professional hiring', 'api',
          'https://business.linkedin.com/hire/hiring-integrations',
          'Publishing and native application connector implemented; partner approval and tenant activation required.',
          'Supply your LinkedIn company ID, eligible contract and employer authorization.',
          'Payobook owns partner onboarding, customer-app provisioning and certification.'),
    board('jobstreet', 'JobStreet by SEEK', ('ID',), 'General recruitment', 'api',
          'https://developer.seek.com/',
          'SEEK publishing and application connector implemented; approved hirer binding required.',
          'Supply your SEEK hirer identifier, posting contact and eligible advertising products.',
          'Payobook owns the shared SEEK partner app, tenant bindings and certification.'),
    board('naukri', 'Naukri', ('IN',), 'Professional hiring', 'partner',
          'https://help.zoho.com/portal/en/kb/recruit/talent-sourcing/job-boards/premium-job-boards/articles/post-jobs-on-naukri-through-zoho-recruit',
          'Zoho documents Naukri publishing through Zwayam Amplify. Payobook connector awaits the approved contract.',
          'Ask your Naukri account manager for Zwayam Amplify access for Payobook and confirm your subscription.', PARTNER_TASK),
    board('foundit', 'foundit India', ('IN',), 'Professional hiring', 'partner',
          'https://help.zoho.com/portal/en/kb/recruit/talent-sourcing/job-boards/premium-job-boards/articles/post-your-jobs-on-foundit-india-from-zoho-recruit-4-6-2026',
          'Zoho documents account identifiers and an API key. Payobook requires its own approved integration.',
          'Request corporation/login identifiers and API entitlement from your foundit account manager.', PARTNER_TASK),
    board('foundit_id', 'foundit Indonesia', ('ID',), 'Professional hiring', 'partner',
          'https://recruiter.foundit.id/',
          'Indonesia employer posting is available. API eligibility and market-specific partner terms must be confirmed with foundit.',
          'Use your Indonesia employer account and ask foundit Indonesia to confirm ATS integration access.', PARTNER_TASK),
    board('apna', 'Apna', ('IN',), 'Frontline and volume hiring', 'partner',
          'https://help.zoho.com/portal/en/kb/recruit/talent-sourcing/job-boards/premium-job-boards/articles/post-and-manage-your-jobs-on-apna',
          'Zoho documents client credentials, job management and applicant capture.', ACCOUNT_TASK, PARTNER_TASK),
    board('shine', 'Shine', ('IN',), 'General recruitment', 'partner',
          'https://help.zoho.com/portal/en/kb/recruit/talent-sourcing/job-boards/premium-job-boards/articles/integrate-shine-with-zoho-recruit',
          'Zoho documents an account-based integration. Current Payobook partner access is unconfirmed.', ACCOUNT_TASK, PARTNER_TASK),
    board('hirist', 'hirist', ('IN',), 'Technology hiring', 'partner',
          'https://www.hirist.tech/', 'An ATS integration is documented by Zoho; Payobook access must be agreed.', ACCOUNT_TASK, PARTNER_TASK),
    board('iimjobs', 'iimjobs', ('IN',), 'Management and specialist hiring', 'partner',
          'https://www.iimjobs.com/', 'An ATS integration is documented by Zoho; use a separate employer entitlement.', ACCOUNT_TASK, PARTNER_TASK),
    board('instahyre', 'Instahyre', ('IN',), 'Professional hiring', 'partner',
          'https://help.instahyre.com/en/article/get-started-with-ats-integration-14s0ijg/',
          'ATS partnerships and candidate export are documented. Ask the account manager to add Payobook.',
          'Confirm ATS entitlement on your subscription and authorize Payobook once available.', PARTNER_TASK),
    board('timesjobs', 'TimesJobs', ('IN',), 'General recruitment', 'partner',
          'https://hire.timesjobs.com/', 'Listed in Zoho’s catalogue; the current technical route needs confirmation.', ACCOUNT_TASK, PARTNER_TASK),
    board('internshala', 'Internshala', ('IN',), 'Internships and graduates', 'partner',
          'https://internshala.com/', 'Employer posting is available; an external ATS posting/intake contract is unverified.', ACCOUNT_TASK, PARTNER_TASK),
    board('vietnamworks', 'VietnamWorks', ('VN',), 'Professional hiring', 'partner',
          'https://www.vietnamworks.com/', 'Existing Payobook setup awaits a current API contract and staging access.',
          'Confirm employer API entitlement and the privacy information required for candidate delivery.', PARTNER_TASK),
    board('topcv', 'TopCV', ('VN',), 'General recruitment', 'partner',
          'https://tuyendung.topcv.vn/help/huong-dan-su-dung/ket-noi-he-thong/',
          'Partner APIs, sandbox access and CV webhooks are documented. One employer account connects to one ATS at a time.',
          'Confirm the API/CV-sync service and plan migration if another ATS is connected.', PARTNER_TASK),
    board('itviec', 'ITviec', ('VN',), 'Technology hiring', 'partner',
          'https://itviec.com/blog/ket-noi-he-thong-quan-tri-tuyen-dung/',
          'Officially supports ATS posting, editing, hiding/reopening jobs and CV delivery.', ACCOUNT_TASK, PARTNER_TASK),
    board('careerviet', 'CareerViet', ('VN',), 'Professional hiring', 'partner',
          'https://careerviet.vn/', 'Formerly CareerBuilder Vietnam; confirm the local contract rather than a global CareerBuilder API.', ACCOUNT_TASK, PARTNER_TASK),
    board('vieclam24h', 'Vieclam24h', ('VN',), 'General and volume hiring', 'partner',
          'https://promotion.vieclam24h.vn/',
          'Confirm current CV delivery. MISA reported restrictions on its API retrieval in September 2026.', ACCOUNT_TASK, PARTNER_TASK),
    board('topdev', 'TopDev', ('VN',), 'Technology hiring', 'partner',
          'https://topdev.vn/page/products', 'Employer services are documented; an external integration specification is unverified.', ACCOUNT_TASK, PARTNER_TASK),
    board('glints', 'Glints', ('VN', 'ID'), 'Regional recruitment', 'partner',
          'https://glints.com/', 'Local employer services are available; partner publishing and applicant delivery need confirmation.', ACCOUNT_TASK, PARTNER_TASK),
    board('kalibrr', 'Kalibrr', ('ID',), 'Professional hiring', 'partner',
          'https://kalibrr-support.zendesk.com/hc/en-us/articles/21664815834905-Do-Kalibrr-offer-integration-with-other-platforms',
          'Public documentation describes exporting Kalibrr jobs to a careers site, not full ATS publishing and intake.', ACCOUNT_TASK, PARTNER_TASK),
    board('dealls', 'Dealls', ('ID',), 'Professional and early-career hiring', 'partner',
          'https://dealls.com/en/about', 'Employer posting is available; an external ATS integration contract is unverified.', ACCOUNT_TASK, PARTNER_TASK),
    board('kitalulus', 'KitaLulus', ('ID',), 'Local and volume hiring', 'partner',
          'https://id.kitalulus.com/en', 'Confirm posting and applicant delivery, including messaging-based applications.', ACCOUNT_TASK, PARTNER_TASK),
    board('karir', 'Karir.com', ('ID',), 'General recruitment', 'partner',
          'https://karir.com/', 'Local employer coverage is available; current partner access needs confirmation.', ACCOUNT_TASK, PARTNER_TASK),
    board('indeed', 'Indeed', ('IN', 'VN', 'ID'), 'General recruitment', 'partner',
          'https://docs.indeed.com/', 'Partner approval is required for Job Sync, Indeed Apply and disposition synchronization.', ACCOUNT_TASK, PARTNER_TASK),
    board('careerjet', 'Careerjet', ('IN', 'VN', 'ID'), 'Job search distribution', 'feed',
          'https://www.careerjet.co.in/docs/feeds/xml', 'Documented XML feed implemented. Applicants use your tracked careers-page link.',
          'Confirm feed acceptance, country coverage and any advertising charges with Careerjet.', FEED_TASK),
    board('jooble', 'Jooble', ('IN', 'VN', 'ID'), 'Job search distribution', 'feed',
          'https://jooble.org/files/xml_feed_specifications.pdf', 'Documented XML feed implemented. Applicants use your tracked careers-page link.',
          'Confirm feed acceptance, country coverage and any advertising charges with Jooble.', FEED_TASK),
    board('google_jobs', 'Google job search', ('IN', 'VN', 'ID'), 'Careers-page discovery', 'discovery',
          'https://developers.google.com/search/docs/appearance/structured-data/job-posting',
          'Career pages already carry JobPosting markup. Search visibility is decided by Google; no listing confirmation is implied.',
          'Verify the careers domain in Search Console and review individual job URLs.',
          'Payobook maintains public job-page markup. Indexing API activation needs a verified project and service account.'),
    board('logicmelon', 'LogicMelon', ('IN', 'VN', 'ID'), 'Multiple job boards', 'partner',
          'https://logicmelon.com/', 'Distribution partner; confirm each target board and applicant return path before subscribing.', ACCOUNT_TASK, PARTNER_TASK),
    board('broadbean', 'Broadbean', ('IN', 'VN', 'ID'), 'Multiple job boards', 'partner',
          'https://integrations.broadbean.com/', 'Distribution partner with integration documentation; target-board coverage and commercial access need confirmation.', ACCOUNT_TASK, PARTNER_TASK),
]
CATALOGUE = {b['key']: b for b in BOARDS}
FEED_KEYS = frozenset(b['key'] for b in BOARDS if b['route'] == 'feed')


def onboarding_request(spec, company):
    return (
        'Subject: Payobook ATS integration with ' + spec['name'] + '\n\n'
        'Hello,\n\nPayobook is an applicant tracking and hiring platform. We would like to '
        'integrate ' + spec['name'] + ' for employer ' + company + '.\n\n'
        'Please confirm:\n'
        '1. Your ATS partner onboarding process and supported countries.\n'
        '2. The current technical documentation and authentication requirements.\n'
        '3. Support for publishing, updating and closing jobs, receiving applications and CVs, '
        'screening answers and application-status feedback.\n'
        '4. Sandbox/test-employer access and certification requirements.\n'
        '5. Partner fees, employer subscriptions and advertising charges.\n'
        '6. Employer authorization, data-handling requirements and production activation steps.\n\n'
        'Payobook will build, host and maintain the connector. Employers will authorize their '
        'own accounts. Please advise the appropriate technical partner contact.\n\n'
        'Thank you.\nPayobook\nhttps://payobook.com\n'
    )
