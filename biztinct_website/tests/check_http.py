"""Black-box HTTP checks. Writes are permitted only to the local QA tunnel."""
import argparse
import html
import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('base_url')
    parser.add_argument('--qa-writes', action='store_true')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    if args.qa_writes and base != 'http://localhost:18069':
        raise SystemExit('Write tests are restricted to http://localhost:18069 (QA tunnel).')
    opener = urllib.request.build_opener(NoRedirect(),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    passed = []

    def fetch(path, data=None):
        request = urllib.request.Request(base + path,
            data=urllib.parse.urlencode(data).encode() if data is not None else None)
        try:
            response = opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        return response.code, response.read().decode(), response.headers

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        passed.append(name)
        print('PASS:', name)

    for path in ['/', '/solutions', '/approach', '/contactus', '/privacy', '/contactus/thanks']:
        status, body, headers = fetch(path)
        check('page ' + path, status == 200 and '<!DOCTYPE html>' in body and '| Biztinct</title>' in body)
        check('page security ' + path, headers.get('X-Content-Type-Options') == 'nosniff')
    status, body, _ = fetch('/sitemap.xml')
    check('clean sitemap', status == 200 and body.count('<url>') == 5 and '/operations' not in body)
    for path, target in [('/operations', '/solutions#operations'), ('/sales', '/solutions#sales'),
                         ('/productivity', '/solutions#automation'),
                         ('/website-design-e-commerce', '/solutions#digital'),
                         ('/restaurant-and-cafe', '/solutions#industries'),
                         ('/education-and-coaching', '/solutions#industries'),
                         ('/transport-and-fleet', '/solutions#industries'),
                         ('/clinic-and-hospital', '/solutions#industries'),
                         ('/hotel-management', '/solutions#industries'),
                         ('/building-and-construction', '/solutions#industries'),
                         ('/event-management', '/solutions#industries')]:
        status, _, headers = fetch(path)
        check('legacy ' + path, status == 301 and headers.get('Location', '').endswith(target))
    for path in ['/biztinct/mail-setup', '/biztinct/enquiries']:
        status, _, headers = fetch(path)
        check('administrator login required ' + path,
              status in (302, 303) and '/web/login' in headers.get('Location', ''))
    status, contact, _ = fetch('/contactus')
    check('correct email link', 'href="mailto:ash@biztinct.com"' in contact
          and 'yourcompany.example.com' not in contact)
    if args.qa_writes:
        token = html.unescape(re.search(r'name="csrf_token" value="([^"]+)"', contact).group(1))
        values = dict(csrf_token=token, name='Website QA HTTP', email='website-qa@example.invalid',
                      company='Test-only enquiry', phone='', interest='Custom software',
                      message='QA only. No delivery expected.', consent='yes', website_url='')
        invalid = dict(values); invalid.pop('csrf_token')
        status, _, _ = fetch('/contactus', invalid)
        check('CSRF rejection', status in (400, 403))
        for key, value, expected in [
                ('name', '', 'Please enter your name.'),
                ('email', 'bad\r\nBcc: injection@example.invalid', 'Please enter a valid email address.'),
                ('message', '', 'Tell us a little about what you have in mind.'),
                ('interest', 'untrusted-option', 'Please choose an option.'),
                ('consent', 'no', 'Please confirm'),
                ('message', 'x' * 6001, 'under 6000 characters')]:
            status, body, _ = fetch('/contactus', dict(values, **{key: value}))
            check('server validation ' + key + ':' + value[:15], status == 400 and expected in body)
        status, _, headers = fetch('/contactus', dict(values, website_url='bot-filled'))
        check('honeypot handled', status == 303)
        for number in range(5):
            status, _, headers = fetch('/contactus', dict(values, name='Website QA HTTP %s' % number))
            check('enquiry saved %s' % number, status == 303 and '/contactus/thanks' in headers.get('Location', ''))
        status, body, _ = fetch('/contactus', values)
        check('sixth enquiry is rate limited', status == 400 and 'Please wait a few minutes' in body)
    print('%s HTTP checks passed.' % len(passed))


if __name__ == '__main__':
    main()
