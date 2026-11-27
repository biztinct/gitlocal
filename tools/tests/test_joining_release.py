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
    def test_log_checks_cover_active_host_aliases(self):
        with patch.object(Path, 'read_text', return_value='portal.example.test demo\nformer.example.test retired\n'):
            self.assertEqual(verify_logs.hosts_for(['demo']), ['demo.payobook.com', 'portal.example.test'])
            self.assertEqual(
                verify_logs.hosts_for(['payobook']),
                ['payobook.com', 'payobook.payobook.com', 'www.payobook.com'],
            )
            with self.assertRaises(ValueError):
                verify_logs.hosts_for(['abm'])

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
