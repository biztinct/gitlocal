# -*- coding: utf-8 -*-
"""The ONECHAT router, loaded out of its three real source files over the
`odoo_stub` stand-in, with two database shapes:

  P — payobook: pb_learn + pb_payroll_ai_insights + pb_payai_actions, an
      assistant that is set up, "PayAI may look" on;
  B — base / rize-like: the three hook layers replaced by pb_learn's own
      base behaviour (no assistant, no command path) — exactly what the
      server test does with `patch.object` (handover test 1.1).

Everything that would read a table is a hook the test sets: a plan waiting,
a question open, the voice switch, the Access reach.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import odoo_stub as S  # noqa: E402

S.install()
PAYAI = S.load_payai_package()
LEARN = S.load_addon_models('pb_learn', [
    'learn_content', 'learn_live', 'learn_progress', 'learn_question',
    'learn_runtime', 'learn_intent', 'learn_helper'])
INSIGHTS = S.load_addon_models('pb_payroll_ai_insights', ['learn_helper'])
ACTIONS = S.load_addon_models('pb_payai_actions', ['learn_helper'])

BASE = LEARN['learn_helper'].LearnHelper
HELPER_HOOKS = ('_payai_available', '_voice_offered', '_can_act', '_looks_like_question',
                '_command_key', '_go_ahead_words', '_route_payai_state', '_waiting_plan',
                '_route_command', '_capability_route', '_tap_note')


class FakeCompany:
    def __init__(self, look=True, prepare=True, decide=True, voice_go_ahead=False):
        self.id = 1
        self.payai_tier_look = look
        self.payai_tier_prepare = prepare
        self.payai_tier_decide = decide
        self.payai_voice_go_ahead = voice_go_ahead
        self._fields = {'payai_tier_look': 1, 'payai_tier_prepare': 1,
                        'payai_tier_decide': 1, 'payai_voice_go_ahead': 1}

    def __getitem__(self, name):
        return getattr(self, name)

    def __bool__(self):
        return True


class FakeUser:
    id = 2
    name = 'Harness'
    lang = 'en_US'

    def __init__(self, groups=None):
        self.groups = groups

    def has_group(self, xmlid):
        return True if self.groups is None else xmlid in self.groups


class FakeRuntime:
    """learn.runtime: the Access reach and the live next step."""

    def __init__(self, access_visible=True):
        self.access_visible = access_visible
        self.reach_calls = []

    def _station_reach(self, sidebar_key, visible_ids=None, index=None):
        self.reach_calls.append(sidebar_key)
        if sidebar_key == 'pb_settings.item_settings':
            return self.access_visible, False, None
        return True, False, None

    def next_step_live(self, screen):
        return screen.get('next_step') or ''

    def features(self):
        return {}


class FakeLive:
    def render(self, text, fallback=''):
        return text

    def with_context(self, **kw):
        return self


class FakeProvider:
    def __init__(self, available=True):
        self.available = available
        self.calls = []

    def is_available(self):
        return self.available

    def _boom(self, *a, **k):
        self.calls.append(a)
        raise AssertionError('the router called the model')

    generate_text = generate_chat = generate_tools = _boom


class FakeConfig:
    def __init__(self, provider):
        self.provider = provider

    def __bool__(self):
        return self.provider is not None

    def get_active_config(self):
        return self

    def get_provider(self):
        return self.provider

    def sudo(self):
        return self


class FakeParams:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def sudo(self):
        return self

    def get_param(self, key, default=None):
        return self.values.get(key, default)

    def set_param(self, key, value):
        if value is False or value is None:
            self.values.pop(key, None)
        else:
            self.values[key] = value


class FakeConversation:
    def __init__(self, voice=False):
        self.voice = voice

    def rpc_voice_status(self):
        return {'available': self.voice}


def make_env(mode='P', look=True, access_visible=True, voice=False, voice_go_ahead=False,
             provider_available=True, compose=False, lang='en_US'):
    provider = FakeProvider(provider_available) if mode == 'P' else None
    extra = {
        'learn.runtime': FakeRuntime(access_visible),
        'learn.live': FakeLive(),
        'payroll.ai.config': FakeConfig(provider),
        'payroll.ai.conversation': FakeConversation(voice),
        'ir.config_parameter': FakeParams(
            {'pb_learn.compose_enabled': 'True'} if compose else {}),
    }
    env = S.Env(user=FakeUser(), company=FakeCompany(look=look, voice_go_ahead=voice_go_ahead),
                lang=lang, extra=extra)
    env.provider = provider
    return env


class Patch:
    """Temporarily replace attributes on the composed helper class."""

    def __init__(self, helper, **attrs):
        self.cls = type(helper)
        self.attrs = attrs
        self.saved = {}

    def __enter__(self):
        for name, value in self.attrs.items():
            self.saved[name] = self.cls.__dict__.get(name, None)
            setattr(self.cls, name, value)
        return self

    def __exit__(self, *exc):
        for name in self.attrs:
            if self.saved[name] is None:
                delattr(self.cls, name)
            else:
                setattr(self.cls, name, self.saved[name])
        return False


def base_hooks():
    """Every hook as pb_learn alone defines it (the B column)."""
    return {name: BASE.__dict__[name] for name in HELPER_HOOKS}


def helper(env):
    return env['learn.helper']
