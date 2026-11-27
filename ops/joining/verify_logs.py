"""Confirm Joining access-log redaction and keep ordinary request logging on every active hostname."""

from pathlib import Path
import secrets
import subprocess
import sys
import time


def hosts_for(databases):
    names = set(databases)
    if not names or 'abm' in names:
        raise ValueError('Expected only the active databases')
    hosts = {('payobook.com' if db == 'payobook' else db + '.payobook.com') for db in names}
    if 'payobook' in names:
        hosts.update({'www.payobook.com', 'payobook.payobook.com'})
    for line in Path('/etc/odoo-host-db.map').read_text().splitlines():
        parts = line.partition('#')[0].split()
        if len(parts) == 2 and parts[1] in names:
            hosts.add(parts[0])
    return sorted(hosts)


def check(databases):
    from nginx import listeners

    hosts = hosts_for(databases)
    configs = (p.read_text() for p in Path('/etc/nginx/sites-enabled').iterdir() if p.is_file())
    ports = listeners(configs, hosts)
    streams = (
        'access.log',
        'error.log',
        'odoo-access.log',
        'odoo-error.log',
        'tenants-access.log',
        'tenants-error.log',
    )
    paths = [Path('/var/log/nginx') / name for name in streams if (Path('/var/log/nginx') / name).is_file()]
    offsets = {p: p.stat().st_size for p in paths}
    probe = secrets.token_hex(18)
    agent = 'Payobook-Joining-check-' + secrets.token_hex(6)
    expected = {}
    for index, host in enumerate(hosts):
        for port in sorted(ports[host]):
            scheme = 'https' if port == 443 else 'http'
            for path, label in [('/join/' + probe, 'request'), ('/web/login', 'referer')]:
                marker = f'{agent}-{index}-{port}-{label}'
                headers = ['--referer', 'https://' + host + '/join/' + probe] if label == 'referer' else []
                subprocess.run(
                    [
                        'curl',
                        '-sS',
                        '-I',
                        '-o',
                        '/dev/null',
                        '--max-time',
                        '25',
                        '--resolve',
                        f'{host}:{port}:127.0.0.1',
                        '-A',
                        marker,
                        *headers,
                        f'{scheme}://{host}{path}',
                    ],
                    check=True,
                )
                expected[marker] = (
                    'HEAD /join/[private] HTTP/' if label == 'request' else 'HEAD /web/login HTTP/'
                )
    seen = set()
    for attempt in range(10):
        for path in paths:
            with path.open('rb') as log:
                log.seek(offsets[path])
                for raw in log:
                    if probe.encode() in raw:
                        raise RuntimeError('Unredacted Joining probe in ' + path.name)
                    line = raw.decode(errors='replace')
                    for marker, request in expected.items():
                        if (
                            marker + '"' in line
                            and request in line
                            and (not marker.endswith('-referer') or '"/join/[private]"' in line)
                        ):
                            seen.add(marker)
                offsets[path] = log.tell()
        if len(seen) == len(expected):
            print(
                f'Verified {len(seen)} redacted request/referer records across {len(hosts)} active hostnames'
            )
            return
        time.sleep(1)
    raise RuntimeError(f'Only {len(seen)} of {len(expected)} expected log records appeared')


if __name__ == '__main__':
    check(sys.argv[1:])
