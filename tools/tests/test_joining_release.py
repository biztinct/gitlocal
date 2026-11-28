"""Release regressions. All transport and service calls in these tests are local fixtures."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('joining_nginx', REPO / 'ops/joining/nginx.py')
nginx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nginx)
log_spec = importlib.util.spec_from_file_location('joining_verify_logs', REPO / 'ops/joining/verify_logs.py')
verify_logs = importlib.util.module_from_spec(log_spec)
log_spec.loader.exec_module(verify_logs)


class JoiningRelease(unittest.TestCase):
    def test_notes_require_completion_and_allow_the_same_failed_operation_to_retry(self):
        runner = (REPO / 'ops/pb_release.sh').read_text()
        function = runner[runner.index('notes_clear()'):runner.index('if ! notes_clear;')]
        start = 'time | Ops | START | install on target | demo |'
        failed = 'time | Ops | FAILED | install | demo |'
        done = 'time | Ops | DONE | install finished | demo |'
        for rows, clear in [
            ([start], False), ([start, failed], False),
            ([start, failed, start, done], True),
            ([start, failed, start.replace('target', 'another job'), done], False),
            ([start, failed, start.replace('demo', 'other'), done.replace('demo', 'other')], False),
            ([start, start, done], False), ([start, done], True),
            (['time | Ops | HOLD | maintenance'], False),
        ]:
            with self.subTest(rows=rows), tempfile.NamedTemporaryFile(mode='w') as notes:
                notes.write('\n'.join(rows))
                notes.flush()
                result = subprocess.run(['bash', '-c', function + 'notes_clear', 'bash'],
                                        env=dict(os.environ, NOTES=notes.name))
                self.assertEqual(result.returncode == 0, clear)

    def test_template_requires_public_404_and_internal_200(self):
        runner = (REPO / 'ops/pb_release.sh').read_text()
        function = runner[runner.index('warm_site()'):runner.index('for db in $DBS; do warm_site')]
        # The internal request must use loopback, the template host and the exact database.
        fixture = """log() { :; }
host_of() { echo "$1.payobook.com"; }
awk() { echo 8069; }
curl() { case "$*" in
    *"Host: payobook_template.payobook.com http://127.0.0.1:8069/web/login?db=payobook_template") echo "$INTERNAL";;
    *"https://"*) echo "$PUBLIC";; *) return 1;; esac; }
"""
        for db, public, internal, clear in [
            ('payobook_template', '404', '200', True), ('payobook_template', '200', '200', False),
            ('payobook_template', '404', '404', False), ('payobook', '200', '', True),
            ('payobook', '404', '', False),
        ]:
            with self.subTest(db=db, public=public, internal=internal):
                result = subprocess.run(['bash', '-c', fixture + function + 'warm_site "$1"', 'bash', db],
                                        env=dict(os.environ, PUBLIC=public, INTERNAL=internal))
                self.assertEqual(result.returncode == 0, clear)

    def test_log_checks_cover_active_host_aliases(self):
        with patch.object(Path, 'read_text', return_value='portal.example.test demo\nformer.example.test retired\n'):
            self.assertEqual(verify_logs.hosts_for(['demo']), ['demo.payobook.com', 'portal.example.test'])
            self.assertEqual(
                verify_logs.hosts_for(['payobook']),
                ['payobook.com', 'payobook.payobook.com', 'www.payobook.com'],
            )
            with self.assertRaises(ValueError):
                verify_logs.hosts_for(['abm'])

    def test_redaction_checks_every_configured_listener(self):
        sites = [
            'server {\n listen 80;\n server_name *.example.test;\n}',
            'server {\n listen 443 ssl;\n server_name *.example.test;\n}',
            'server {\n listen 80;\n server_name edge.example.org;\n}',
        ]
        self.assertEqual(nginx.listeners(sites, ['one.example.test', 'edge.example.org']),
                         {'one.example.test': {80, 443}, 'edge.example.org': {80}})
        with self.assertRaises(ValueError):
            nginx.listeners(sites, ['unknown.example.org'])

    def test_nginx_preserves_routes_and_is_idempotent(self):
        site = """server {
 server_name *.example.test;
 access_log /tmp/tenant.log;
 location / {
   if ($workspace = 0) { return 404; }
   proxy_pass http://127.0.0.1:8069;
 }
}
server {
 server_name *.example.test;
 return 301 https://$host$request_uri;
}
server {
 server_name retired.example.test;
 access_log /tmp/retired.log;
 return 410;
}
"""
        active = {'*.example.test'}
        revised, hosts = nginx.rewrite(site, active)
        self.assertEqual(hosts, active)
        self.assertEqual(nginx.rewrite(revised, active)[0], revised)
        self.assertEqual(revised.count('if ($workspace = 0)'), 2)
        self.assertEqual(revised.count('proxy_pass http://127.0.0.1:8069'), 2)
        self.assertIn('location ^~ /join/', revised)
        self.assertIn('access_log /tmp/tenant.log pb_joining;', revised)
        self.assertIn('access_log /var/log/nginx/access.log pb_joining;', revised)
        self.assertTrue(revised.endswith(site[site.rindex('server {') :]))
        self.assertIn('$pb_join_request', nginx.FORMAT)
        self.assertIn('$pb_join_referer', nginx.FORMAT)

    def test_configuration_failure_restores_prior_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            current = root / 'current'
            created = root / 'new'
            current.write_text('existing config')
            with (
                patch.object(
                    nginx, 'changes_for', return_value=({current: 'changed', created: 'new'}, set())
                ),
                patch.object(
                    nginx.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'nginx')
                ) as run,
            ):
                with self.assertRaises(subprocess.CalledProcessError):
                    nginx.apply(root, root / 'backup', ['demo'])
            self.assertEqual(current.read_text(), 'existing config')
            self.assertFalse(created.exists())
            self.assertEqual(run.call_count, 1)

    def test_wrapper_stages_committed_modules_and_quotes_author(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bindir = root / 'bin'
            bindir.mkdir()
            repo = root / 'repo'
            repo.mkdir()
            for file in [
                'tools/release.sh',
                'ops/pb_release.sh',
                'ops/joining/nginx.py',
                'ops/joining/verify_logs.py',
                'ops/joining/restore-cron.sql',
            ]:
                dest = repo / file
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((REPO / file).read_bytes())
            for name in ('demo_top', 'addons', 'addons/demo_nested', 'web'):
                dest = repo / name
                dest.mkdir(exist_ok=True)
                (dest / '__manifest__.py').write_text("{'version':'19.0.1.0.0'}")

            def command(*args, **kwargs):
                return subprocess.run(args, cwd=repo, text=True, capture_output=True, **kwargs)

            command('git', 'init', '-q', check=True)
            command('git', 'add', '--', 'tools', 'ops', 'demo_top', 'addons', 'web', check=True)
            command(
                'git',
                '-c',
                'user.name=DEMO',
                '-c',
                'user.email=demo@example.invalid',
                'commit',
                '-qm',
                'fixture',
                check=True,
            )
            (repo / 'demo_top' / 'untracked').write_text('fixture')
            (bindir / 'ssh').write_text("""#!/bin/bash
set -eu
case "$2" in
  *ls-tree*) printf 'web\nbase\n';;
  *systemd-run*) printf '%s' "$2" > "$TEST_ROOT/launch";;
esac
""")
            (bindir / 'rsync').write_text("""#!/bin/bash
set -eu
test -f "$2/demo_top/__manifest__.py"
test -f "$2/demo_nested/__manifest__.py"
test -f "$2/.release/pb_release.sh"
test -f "$2/.release/joining/verify_logs.py"
test ! -e "$2/demo_top/untracked"
touch "$TEST_ROOT/staged"
""")
            for file in bindir.iterdir():
                file.chmod(0o755)
            env = dict(
                os.environ,
                PATH=str(bindir) + ':' + os.environ['PATH'],
                HOST='local-fixture',
                WHO='Codex JOINING',
                TEST_ROOT=str(root),
            )

            def release(mods, upgrade):
                return command('bash', 'tools/release.sh', 'risky', mods, upgrade, env=env)

            self.assertEqual(release('demo_top,demo_nested', '+demo_top,demo_nested').returncode, 0)
            self.assertTrue((root / 'staged').exists())
            self.assertIn(r'--setenv=WHO=Codex\ JOINING', (root / 'launch').read_text())
            self.assertNotEqual(release('web', '+web').returncode, 0)
            self.assertNotEqual(release('demo_top', '+demo_nested').returncode, 0)
            (repo / 'demo_top/__manifest__.py').write_text('{}')
            self.assertNotEqual(release('demo_top', '+demo_top').returncode, 0)


if __name__ == '__main__':
    unittest.main()
