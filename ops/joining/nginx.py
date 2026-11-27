"""Apply the Joining log format to the active Payobook sites and their redirects."""

from fnmatch import fnmatchcase
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

FORMAT = '''# Joining links contain private credentials. Keep the method, status and timing.
map $request_uri $pb_join_request {
    default $request;
    ~*/join(?:/|%2f) "$request_method /join/[private] $server_protocol";
}
map $http_referer $pb_join_referer {
    default $http_referer;
    ~*/join(?:/|%2f) "/join/[private]";
}
log_format pb_joining '$remote_addr - $remote_user [$time_local] "$pb_join_request" '
                      '$status $body_bytes_sent "$pb_join_referer" "$http_user_agent"';
'''


def closing_brace(text, start):
    depth = 0
    for token in re.finditer(r"""\#[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[{}]""", text[start:]):
        if token[0] == '{':
            depth += 1
        elif token[0] == '}':
            depth -= 1
            if depth == 0:
                return start + token.end()
    raise ValueError('Unclosed nginx block')


def listeners(configs, hosts):
    """Find the HTTP and HTTPS ports actually served for each active hostname."""
    ports = {host: set() for host in hosts}
    for config in configs:
        for server in re.finditer(r'(?m)^\s*server\s*\{', config):
            block = config[server.start():closing_brace(config, server.end() - 1)]
            names = re.findall(r'(?m)^\s*server_name\s+([^;]+);', block)
            sockets = re.findall(r'(?m)^\s*listen\s+([^;\s]+)', block) or ['80']
            enabled = {p for p in (80, 443) if any(s.split(':')[-1] == str(p) for s in sockets)}
            for host in hosts:
                if any(fnmatchcase(host, name) for group in names for name in group.split()):
                    ports[host].update(enabled)
    if any(not port for port in ports.values()):
        raise ValueError('Missing active site listener')
    return ports


def rewrite(text, active_hosts):
    sites = set()
    chunks = []
    end = 0
    for match in re.finditer(r'(?m)^\s*server\s*\{', text):
        stop = closing_brace(text, match.end() - 1)
        block = text[match.start() : stop]
        hosts = {
            host for names in re.findall(r'(?m)^\s*server_name\s+([^;]+);', block) for host in names.split()
        }
        if not hosts & active_hosts:
            continue
        if hosts - active_hosts:
            raise ValueError('An active server block also serves an unexpected hostname')
        sites.update(hosts)
        logs = list(re.finditer(r'(?m)^(\s*access_log\s+)([^;\s]+)(?:\s+([^;]+))?;', block))
        if logs:
            for log in reversed(logs):
                if log[3] not in (None, 'combined', 'pb_joining'):
                    raise ValueError('Unexpected access log format')
                block = block[: log.start()] + log[1] + log[2] + ' pb_joining;' + block[log.end() :]
        else:
            index = block.index('{') + 1
            block = block[:index] + '\n    access_log /var/log/nginx/access.log pb_joining;' + block[index:]
        # nginx cannot format its diagnostic error log. For Joining alone, the
        # redacted access entry still records upstream failures and their status.
        root = re.search(r'(?m)^([ \t]*)location\s+/\s*\{', block)
        if root and 'location ^~ /join/' not in block:
            last = closing_brace(block, root.end() - 1)
            original = block[root.start() : last]
            if 'proxy_pass ' in original:
                private = original.replace('location /', 'location ^~ /join/', 1)
                point = private.index('{') + 1
                private = (
                    private[:point] + '\n' + root[1] + '    error_log /dev/null emerg;' + private[point:]
                )
                block = block[: root.start()] + private + '\n' + block[root.start() :]
        chunks.extend([text[end : match.start()], block])
        end = stop
    return ''.join(chunks) + text[end:], sites


def replace(path, content):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
        tmp = Path(out.name)
        out.write(content.encode())
    try:
        if path.exists():
            shutil.copystat(path, tmp)
            os.chown(tmp, path.stat().st_uid, path.stat().st_gid)
        else:
            tmp.chmod(0o644)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def changes_for(root, databases):
    names = set(databases)
    if not names or 'abm' in names:
        raise ValueError('Expected only the active databases')
    canonical = {('payobook.com' if db == 'payobook' else db + '.payobook.com') for db in names}
    aliases = set()
    for line in Path('/etc/odoo-host-db.map').read_text().splitlines():
        parts = line.partition('#')[0].split()
        if len(parts) == 2 and parts[1] in names:
            aliases.add(parts[0])
    active_hosts = canonical | aliases | {'*.payobook.com'}
    changes = {}
    seen = set()
    for entry in sorted((root / 'sites-enabled').iterdir()):
        if not entry.is_file() or 'abm' in entry.name.lower():
            continue
        path = entry.resolve()
        original = path.read_text()
        revised, sites = rewrite(original, active_hosts)
        seen.update(sites)
        if original != revised:
            changes[path] = revised
    required = aliases | {'*.payobook.com'} | ({'payobook.com'} & canonical)
    if required - seen:
        raise ValueError('Missing active sites: ' + ', '.join(sorted(required - seen)))
    conf = root / 'conf.d' / 'pb-joining-log.conf'
    if not conf.exists() or conf.read_text() != FORMAT:
        changes[conf] = FORMAT
    return changes, seen


def preview(root, databases):
    changes, seen = changes_for(root, databases)
    with tempfile.TemporaryDirectory(prefix='pb-joining-nginx-') as folder:
        scratch = Path(folder)
        for directory in ('conf.d', 'sites-enabled'):
            target = scratch / directory
            target.mkdir()
            for entry in (root / directory).iterdir():
                if entry.is_file():
                    source = entry.resolve()
                    if source in changes:
                        (target / entry.name).write_text(changes[source])
                    else:
                        (target / entry.name).symlink_to(source)
        (scratch / 'conf.d/pb-joining-log.conf').unlink(missing_ok=True)
        (scratch / 'conf.d/pb-joining-log.conf').write_text(FORMAT)
        config = (root / 'nginx.conf').read_text()
        for directory in ('conf.d', 'sites-enabled'):
            config = config.replace(str(root / directory) + '/', str(scratch / directory) + '/')
        (scratch / 'nginx.conf').write_text(config)
        subprocess.run(['nginx', '-t', '-c', str(scratch / 'nginx.conf')], check=True)
    print('Verified the candidate configuration for ' + ', '.join(sorted(seen)))


def apply(root, backup, databases):
    changes, seen = changes_for(root, databases)
    backup.mkdir(mode=0o700, parents=True, exist_ok=True)
    previous = {}
    try:
        for i, (path, content) in enumerate(changes.items()):
            previous[path] = path.read_text() if path.exists() else None
            if path.exists():
                shutil.copy2(path, backup / f'{i}-{path.name}')
            replace(path, content)
        subprocess.run(['nginx', '-t'], check=True)
        if changes:
            subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
    except BaseException:
        for path, original in reversed(list(previous.items())):
            if original is None:
                path.unlink(missing_ok=True)
            else:
                replace(path, original)
        raise
    print('Joining log redaction configured on ' + ', '.join(sorted(seen)))


if __name__ == '__main__':
    if sys.argv[1] == '--check':
        preview(Path('/etc/nginx'), sys.argv[2:])
    else:
        apply(Path('/etc/nginx'), Path(sys.argv[1]), sys.argv[2:])
