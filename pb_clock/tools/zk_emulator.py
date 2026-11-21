#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A pretend ZK attendance machine that speaks PUSH / ADMS ("iclock").

Standard library only, so it runs on any box with python3:

    python3 zk_emulator.py --base https://rize.payobook.com --sn TST-0002 --tz 7 \\
        --punch '885,2026-11-05 07:31:00,0,1' --punch '227,2026-11-05 07:40:12,0,1' \\
        --poll 60

What it does, in the order a real 2.x terminal does it:

  1. handshake  GET  /iclock/cdata?SN=…&options=all&pushver=…   prints the options
     (403 `pending` → it keeps asking every --retry seconds when --wait is given,
     like a machine that is waiting to be let in)
  2. punches    POST /iclock/cdata?SN=…&table=ATTLOG&Stamp=…     the --punch lines,
     the --file lines, or --now PIN (a punch at the emulated clock's time)
  3. poll       GET  /iclock/getrequest?SN=…&INFO=…              every --delay s for
     --poll s; executes what it is told:
        SET OPTIONS DateTime=<n>  → decodes and prints it, sets the emulated clock
        DATA QUERY ATTLOG …       → re-posts the punches it holds in that range
        CHECK                     → handshakes again
     and answers POST /iclock/devicecmd  ID=…&Return=0  (or -1 with --fail-commands).

`--clock-offset 300` makes the emulated clock 5 minutes fast (the "set the
clock 5 min off" browser check); `--v3` does the 3.x ping / registry / push
dance first. `--machine-number` adds the extra third column some firmware sends.

The class `ZkEmulator` is used by the automated tests with their own HTTP
transport (`http=`), so the same code drives both.
"""

import argparse
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


def zk_encode(dt):
    return ((((dt.year - 2000) * 12 * 31) + ((dt.month - 1) * 31) + (dt.day - 1)) * 86400
            + dt.hour * 3600 + dt.minute * 60 + dt.second)


def zk_decode(value):
    value = int(value)
    s = value % 60
    value //= 60
    m = value % 60
    value //= 60
    h = value % 24
    value //= 24
    d = value % 31 + 1
    value //= 31
    mo = value % 12 + 1
    value //= 12
    return datetime(value + 2000, mo, d, h, m, s)


def _urllib_http(insecure=False, extra_headers=None):
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    def call(method, url, data=None, headers=None):
        hdrs = {'User-Agent': 'iClock Proxy/1.09', 'Content-Type': 'text/plain'}
        hdrs.update(extra_headers or {})
        hdrs.update(headers or {})
        body = data.encode('utf-8') if isinstance(data, str) else data
        req = urllib.request.Request(url, data=body if method == 'POST' else None,
                                     headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return resp.status, resp.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode('utf-8', 'replace')
    return call


class ZkEmulator:
    def __init__(self, base, sn, tz_hours=7, pushver='2.4.1', http=None,
                 clock_offset_s=0, machine_number=False, fail_commands=False,
                 out=None, firmware='Ver 6.60 Apr 28 2017'):
        self.base = base.rstrip('/')
        self.sn = sn
        self.tz = timezone(timedelta(hours=tz_hours))
        self.pushver = pushver
        self.http = http or _urllib_http()
        self.clock_offset = timedelta(seconds=clock_offset_s)
        self.machine_number = machine_number
        self.fail_commands = fail_commands
        self.out = out if out is not None else sys.stdout
        self.firmware = firmware
        self.options = {}
        self.held = []              # punches this machine holds: (pin, local, status, verify)
        self.stamp = 0
        self.log = []

    # ------------------------------------------------------------ helpers
    def say(self, *parts):
        line = ' '.join(str(p) for p in parts)
        self.log.append(line)
        if self.out:
            print(line, file=self.out)

    def url(self, path, **params):
        q = {'SN': self.sn}
        q.update({k: v for k, v in params.items() if v is not None})
        return '%s/iclock/%s?%s' % (self.base, path, urllib.parse.urlencode(q))

    def now_local(self):
        return (datetime.now(timezone.utc).astimezone(self.tz).replace(tzinfo=None)
                + self.clock_offset).replace(microsecond=0)

    def line(self, pin, local, status='0', verify='1'):
        stamp = local.strftime('%Y-%m-%d %H:%M:%S') if isinstance(local, datetime) else local
        cols = [str(pin), stamp]
        if self.machine_number:
            cols.append('101')
        cols += [str(status), str(verify), '0', '0']
        return '\t'.join(cols)

    # ------------------------------------------------------------ protocol
    def handshake(self):
        status, body = self.http('GET', self.url('cdata', options='all',
                                                 pushver=self.pushver, language='69'))
        self.say('handshake ->', status, body.strip().replace('\r\n', ' | '))
        if status == 200:
            self.options = dict(
                ln.split('=', 1) for ln in body.replace('\r\n', '\n').split('\n')
                if '=' in ln)
        return status, body

    def v3_dance(self):
        s1, b1 = self.http('GET', '%s/iclock/ping?SN=%s' % (self.base, self.sn))
        self.say('ping ->', s1, b1.strip())
        s2, b2 = self.http('POST', self.url('registry', pushver='3.0.1', DeviceType='att'),
                           data='DeviceType=att,~DeviceName=TST')
        self.say('registry ->', s2, b2.strip())
        s3, b3 = self.http('POST', self.url('push', pushver='3.0.1'), data='')
        self.say('push ->', s3, b3.strip().replace('\r\n', ' | '))
        return (s1, b1), (s2, b2), (s3, b3)

    def add(self, pin, local, status='0', verify='1'):
        if isinstance(local, str):
            local = datetime.strptime(local.strip()[:19], '%Y-%m-%d %H:%M:%S')
        self.held.append((str(pin), local, str(status), str(verify)))

    def post_lines(self, lines, table='ATTLOG'):
        self.stamp += len(lines)
        body = '\n'.join(lines) + '\n'
        status, text = self.http('POST', self.url('cdata', table=table, Stamp=str(self.stamp)),
                                 data=body)
        self.say('post %s x%s ->' % (table, len(lines)), status, text.strip())
        return status, text

    def post_held(self, rows=None):
        rows = self.held if rows is None else rows
        if not rows:
            return None
        return self.post_lines([self.line(*r[:1], r[1], r[2], r[3]) for r in rows])

    def info(self):
        return '%s,%s,%s,%s,%s,10,7,15,0,111' % (
            self.firmware, 2, 2, len(self.held), '192.168.1.201')

    def getrequest(self, with_info=True):
        status, text = self.http('GET', self.url('getrequest',
                                                 INFO=self.info() if with_info else None))
        cmds = [ln for ln in text.replace('\r\n', '\n').split('\n') if ln.startswith('C:')]
        self.say('getrequest ->', status, text.strip().replace('\r\n', ' | ') or '(empty)')
        results = []
        for ln in cmds:
            _c, cid, cmd = ln.split(':', 2)
            rc = self.run_command(cmd)
            results.append((cid, rc, cmd))
        if results:
            body = '\n'.join('ID=%s&Return=%s&CMD=%s' % (cid, rc, cmd.split(' ')[0])
                             for cid, rc, cmd in results)
            s2, t2 = self.http('POST', self.url('devicecmd'), data=body)
            self.say('devicecmd ->', s2, t2.strip())
        return status, text, results

    def run_command(self, cmd):
        if self.fail_commands:
            self.say('  (refusing)', cmd)
            return -1
        if cmd.startswith('SET OPTIONS DateTime='):
            told = zk_decode(cmd.split('=', 1)[1])
            before = self.now_local()
            real = before - self.clock_offset
            self.clock_offset = told - real
            self.say('  clock set to', told.strftime('%Y-%m-%d %H:%M:%S'),
                     '(was', before.strftime('%H:%M:%S') + ')')
            return 0
        if cmd.startswith('DATA QUERY ATTLOG'):
            spec = cmd.split('ATTLOG', 1)[1]
            parts = dict(p.strip().split('=', 1) for p in spec.split('\t') if '=' in p)
            lo = datetime.strptime(parts.get('StartTime', '2000-01-01 00:00:00')[:19],
                                   '%Y-%m-%d %H:%M:%S')
            hi = datetime.strptime(parts.get('EndTime', '2099-01-01 00:00:00')[:19],
                                   '%Y-%m-%d %H:%M:%S')
            rows = [r for r in self.held if lo <= r[1] <= hi]
            self.say('  resending', len(rows), 'punch(es) from', lo.date())
            if rows:
                self.post_held(rows)
            return 0
        if cmd.strip() == 'CHECK':
            self.stamp = 0
            self.handshake()
            self.post_held()
            return 0
        self.say('  unknown command', cmd)
        return 0

    def poll(self, seconds, delay=10):
        end = time.time() + seconds
        while time.time() < end:
            self.getrequest()
            time.sleep(delay)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--base', required=True, help='http(s)://host[:port]')
    ap.add_argument('--sn', required=True)
    ap.add_argument('--tz', type=float, default=7)
    ap.add_argument('--pushver', default='2.4.1')
    ap.add_argument('--punch', action='append', default=[],
                    help='PIN,YYYY-MM-DD HH:MM:SS,status,verify (repeatable)')
    ap.add_argument('--now', action='append', default=[], help='PIN: a punch at the clock now')
    ap.add_argument('--file', help='a file of tab-separated ATTLOG lines')
    ap.add_argument('--table', default='ATTLOG', help='post the punches as this table')
    ap.add_argument('--clock-offset', type=int, default=0, help='seconds the clock is fast (+) / slow (-)')
    ap.add_argument('--machine-number', action='store_true')
    ap.add_argument('--fail-commands', action='store_true')
    ap.add_argument('--v3', action='store_true')
    ap.add_argument('--wait', type=int, default=0, help='keep asking this many seconds while pending')
    ap.add_argument('--retry', type=int, default=15)
    ap.add_argument('--poll', type=int, default=0, help='poll for commands this many seconds')
    ap.add_argument('--delay', type=int, default=10)
    ap.add_argument('--insecure', action='store_true')
    ap.add_argument('--header', action='append', default=[], help='Name: value (repeatable)')
    a = ap.parse_args(argv)

    headers = dict(h.split(':', 1) for h in a.header)
    headers = {k.strip(): v.strip() for k, v in headers.items()}
    emu = ZkEmulator(a.base, a.sn, tz_hours=a.tz, pushver=a.pushver,
                     http=_urllib_http(a.insecure, headers),
                     clock_offset_s=a.clock_offset, machine_number=a.machine_number,
                     fail_commands=a.fail_commands)
    if a.v3:
        emu.v3_dance()
    status, _body = emu.handshake()
    end = time.time() + a.wait
    while status == 403 and time.time() < end:
        time.sleep(a.retry)
        status, _body = emu.handshake()
    if status != 200:
        print('not let in (%s); stopping' % status)
        return 1
    print('options:', ', '.join('%s=%s' % kv for kv in emu.options.items()))
    for spec in a.punch:
        bits = [b.strip() for b in spec.split(',')]
        emu.add(bits[0], bits[1], *(bits[2:4] + ['0', '1'][len(bits[2:4]):]))
    for pin in a.now:
        emu.add(pin, emu.now_local(), '0', '1')
    lines = []
    if a.file:
        with open(a.file, encoding='utf-8') as fh:
            lines = [ln.rstrip('\n') for ln in fh if ln.strip()]
    if emu.held:
        emu.post_lines([emu.line(r[0], r[1], r[2], r[3]) for r in emu.held], table=a.table)
    if lines:
        emu.post_lines(lines, table=a.table)
    if a.poll:
        emu.poll(a.poll, a.delay)
    return 0


if __name__ == '__main__':
    sys.exit(main())
