# -*- coding: utf-8 -*-
"""A small stand-in for the parts of Odoo the ONECHAT router touches, so the
routing rules can be EXECUTED on a machine with no odoo-bin (PA10).

WHAT THIS IS
------------
* fake `odoo`, `odoo.api`, `odoo.models`, `odoo.fields`, `odoo.exceptions`,
  `odoo.tools`, `odoo.tools.translate` modules (plus `pytz`);
* a miniature model registry: every class that names `_name` / `_inherit` is
  collected, and `Env[model]` composes them in load order, so `super()` runs
  through the three modules' `learn.helper` layers exactly as the ORM chains
  them (base pb_learn → pb_payroll_ai_insights → pb_payai_actions);
* a `LazyTranslate` that reads each addon's own `i18n/vi_VN.po`, so the
  router's Vietnamese wording (and the runner's reused msgids) is checked
  against the shipped catalogue rather than against a copy.

WHAT IT CANNOT SEE — the list is the point (precedent: replay_tests.py):
records, access rules, record rules, the conversation / task tables. Every
method that reads a table is REPLACED by the test (`patch`) with the state it
would read, and the same assertions run for real on the clone (PA10, PA50) in
`pb_payai_actions/tests/test_onechat_router.py` and its siblings.

The real source files are loaded — never copies of them.
"""
import importlib.util
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
assert os.path.isdir(os.path.join(REPO, 'pb_learn')), 'repo root not found: %s' % REPO


def _mk(name, path=None):
    mod = types.ModuleType(name)
    if path is not None:
        mod.__path__ = [path]
    sys.modules[name] = mod
    parent, _sep, leaf = name.rpartition('.')
    if parent and parent in sys.modules:
        setattr(sys.modules[parent], leaf, mod)
    return mod


# ------------------------------------------------------------ translations
_PO_CACHE = {}


def _po_unescape(s):
    return s.encode('utf-8').decode('unicode_escape').encode('latin-1').decode('utf-8')


def po_map(addon, lang='vi_VN'):
    """{msgid: msgstr} of one addon's catalogue (one line per entry, PA51)."""
    key = (addon, lang)
    if key in _PO_CACHE:
        return _PO_CACHE[key]
    out = {}
    path = os.path.join(REPO, addon, 'i18n', '%s.po' % lang)
    if os.path.exists(path):
        msgid = None
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.rstrip('\n')
                m = re.match(r'^msgid "(.*)"$', line)
                if m:
                    msgid = _po_unescape(m.group(1))
                    continue
                m = re.match(r'^msgstr "(.*)"$', line)
                if m and msgid:
                    val = _po_unescape(m.group(1))
                    if val:
                        out[msgid] = val
                    msgid = None
    _PO_CACHE[key] = out
    return out


def _addon_of(module_name):
    parts = (module_name or '').split('.')
    if len(parts) > 2 and parts[0] == 'odoo' and parts[1] == 'addons':
        return parts[2]
    return ''


class _Lazy(str):
    """A str that also answers `_translate(lang)` like Odoo's LazyGettext."""

    def __new__(cls, msg, addon):
        obj = super().__new__(cls, msg)
        obj._msg = msg
        obj._addon = addon
        return obj

    def _translate(self, lang=None):
        if str(lang or '').startswith('vi'):
            return po_map(self._addon).get(self._msg, self._msg)
        return self._msg


class LazyTranslate:
    def __init__(self, module, default_lang=''):
        self._addon = _addon_of(module)

    def __call__(self, msg, *args, **kw):
        return _Lazy(msg, self._addon)


CURRENT_LANG = {'lang': 'en_US'}


def _gettext(msg, *args, **kw):
    """`_()` in the request's language (the harness sets CURRENT_LANG)."""
    import inspect
    frame = inspect.currentframe().f_back
    addon = _addon_of(frame.f_globals.get('__name__', ''))
    text = msg
    if CURRENT_LANG['lang'].startswith('vi'):
        text = po_map(addon).get(msg, msg)
    if args:
        text = text % args
    elif kw:
        text = text % kw
    return text


# ------------------------------------------------------------ the registry
REGISTRY = {}           # model name -> [classes in load order]


class _MetaModel(type):
    def __init__(cls, name, bases, ns):
        super().__init__(name, bases, ns)
        model = ns.get('_name') or ns.get('_inherit')
        if isinstance(model, (list, tuple)):
            model = model[0] if model else None
        if model and ns.get('_harness_base') is None:
            REGISTRY.setdefault(model, []).append(cls)


class BaseModel(metaclass=_MetaModel):
    _harness_base = True
    _name = None
    _inherit = None

    def __init__(self, env):
        self.env = env

    # Recordset-ish conveniences the router layers may call.
    def with_context(self, *a, **kw):
        ctx = dict(self.env.context)
        if a and isinstance(a[0], dict):
            ctx.update(a[0])
        ctx.update(kw)
        return self.env.with_context(ctx)[self._model_name]

    def with_user(self, user):
        return self

    def sudo(self, flag=True):
        return self

    def search_count(self, domain=None, **kw):
        """No table offline: nothing is ever written, so nothing is counted."""
        return 0

    def __bool__(self):
        return True


def _compose(model):
    classes = REGISTRY.get(model)
    if not classes:
        raise KeyError(model)
    # Last loaded first in the MRO, exactly as `_inherit` chains them.
    bases = tuple(reversed(classes))
    return type('Composed_%s' % model.replace('.', '_'), bases,
                {'_harness_base': True, '_model_name': model})


class Fake:
    """An object that answers any attribute with a value given at build."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class Env:
    def __init__(self, user=None, company=None, lang='en_US', context=None,
                 extra=None, dbname='harness'):
        self.user = user or Fake(id=2, name='Harness', has_group=lambda x: True,
                                 lang=lang)
        self.company = company or Fake(id=1, payai_tier_look=True,
                                       payai_tier_prepare=True,
                                       payai_tier_decide=True,
                                       payai_voice_go_ahead=False)
        self.lang = lang
        self.context = dict(context or {})
        self.extra = dict(extra or {})          # fake models: name -> object
        self.cr = Fake(dbname=dbname)
        self.su = False
        self._cache = {}

    def with_context(self, ctx=None, **kw):
        new = Env(self.user, self.company, self.lang,
                  dict(self.context, **(ctx or {}), **kw), self.extra, self.cr.dbname)
        return new

    def __contains__(self, model):
        return model in self.extra or model in REGISTRY

    def __getitem__(self, model):
        if model in self.extra:
            return self.extra[model]
        if model not in self._cache:
            self._cache[model] = _compose(model)(self)
        return self._cache[model]

    def ref(self, xmlid, raise_if_not_found=True):
        # Records a test names by xml id live in `extra['__refs__']`.
        return (self.extra.get('__refs__') or {}).get(xmlid)

    def _(self, msg, *a, **kw):
        return _gettext(msg, *a, **kw)


# --------------------------------------------------------------- the stubs
def install():
    if 'odoo' in sys.modules and getattr(sys.modules['odoo'], '_harness', False):
        return
    odoo = _mk('odoo')
    odoo._harness = True
    odoo.SUPERUSER_ID = 1

    api = _mk('odoo.api')
    ident = lambda f=None, *a, **k: (f if callable(f) else (lambda g: g))  # noqa: E731
    for name in ('model', 'model_create_multi', 'private', 'readonly', 'autovacuum'):
        setattr(api, name, lambda f: f)
    for name in ('depends', 'constrains', 'onchange', 'depends_context', 'returns'):
        setattr(api, name, lambda *a, **k: (lambda f: f))
    api.ident = ident
    odoo.api = api

    models = _mk('odoo.models')
    models.Model = BaseModel
    models.AbstractModel = BaseModel
    models.TransientModel = BaseModel
    odoo.models = models

    fields = _mk('odoo.fields')

    class _Field:
        def __init__(self, *a, **k):
            pass

    for name in ('Char', 'Text', 'Html', 'Integer', 'Float', 'Boolean', 'Date',
                 'Datetime', 'Selection', 'Many2one', 'One2many', 'Many2many',
                 'Binary', 'Json', 'Monetary', 'Reference', 'Image', 'Properties'):
        setattr(fields, name, type(name, (_Field,), {}))
    import datetime as _dt
    fields.Datetime.now = staticmethod(lambda: _dt.datetime(2031, 6, 15, 9, 0))
    fields.Datetime.to_string = staticmethod(lambda d: d.strftime('%Y-%m-%d %H:%M:%S'))
    fields.Date.today = staticmethod(lambda *a: _dt.date(2031, 6, 15))
    fields.Date.context_today = staticmethod(lambda *a: _dt.date(2031, 6, 15))
    odoo.fields = fields

    exceptions = _mk('odoo.exceptions')
    for name in ('UserError', 'AccessError', 'ValidationError', 'MissingError',
                 'RedirectWarning', 'AccessDenied'):
        setattr(exceptions, name, type(name, (Exception,), {}))
    odoo.exceptions = exceptions

    tools = _mk('odoo.tools')

    def file_open(path, mode='r', **kw):
        return open(os.path.join(REPO, path), mode, encoding='utf-8')

    tools.file_open = file_open
    tools.config = {}
    translate = _mk('odoo.tools.translate')
    translate.LazyTranslate = LazyTranslate
    translate._ = _gettext
    tools.translate = translate
    odoo.tools = tools
    odoo._ = _gettext

    osv = _mk('odoo.osv')
    expression = _mk('odoo.osv.expression')
    expression.AND = lambda doms: [x for d in doms for x in d]
    expression.OR = lambda doms: [x for d in doms for x in d]
    osv.expression = expression

    http = _mk('odoo.http')
    http.request = None

    pytz = _mk('pytz')
    pytz.timezone = lambda name: _dt.timezone.utc
    pytz.utc = _dt.timezone.utc
    pytz.UTC = _dt.timezone.utc

    _mk('odoo.addons', path=os.path.join(REPO))


def load_file(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    parent, _sep, leaf = modname.rpartition('.')
    if parent in sys.modules:
        setattr(sys.modules[parent], leaf, mod)
    spec.loader.exec_module(mod)
    return mod


def package(modname, path):
    """An addon package (or sub-package) WITHOUT running its __init__."""
    if modname in sys.modules:
        return sys.modules[modname]
    return _mk(modname, path=path)


def load_addon_models(addon, files):
    """Load named model files of an addon, in the order given."""
    base = 'odoo.addons.%s' % addon
    package(base, os.path.join(REPO, addon))
    package(base + '.models', os.path.join(REPO, addon, 'models'))
    out = {}
    for name in files:
        full = '%s.models.%s' % (base, name)
        if full in sys.modules:
            out[name] = sys.modules[full]
            continue
        out[name] = load_file(full, os.path.join(REPO, addon, 'models', name + '.py'))
    return out


def load_payai_package():
    """pb_payai_actions/payai — the real catalogue, runner and gate."""
    package('odoo.addons.pb_payroll_ai_insights', os.path.join(REPO, 'pb_payroll_ai_insights'))
    package('odoo.addons.pb_payroll_ai_insights.models',
            os.path.join(REPO, 'pb_payroll_ai_insights', 'models'))
    if 'odoo.addons.pb_payroll_ai_insights.models.ai_redaction' not in sys.modules:
        load_file('odoo.addons.pb_payroll_ai_insights.models.ai_redaction',
                  os.path.join(REPO, 'pb_payroll_ai_insights', 'models', 'ai_redaction.py'))
    package('odoo.addons.pb_payai_actions', os.path.join(REPO, 'pb_payai_actions'))
    if 'odoo.addons.pb_payai_actions.payai' not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            'odoo.addons.pb_payai_actions.payai',
            os.path.join(REPO, 'pb_payai_actions', 'payai', '__init__.py'),
            submodule_search_locations=[os.path.join(REPO, 'pb_payai_actions', 'payai')])
        mod = importlib.util.module_from_spec(spec)
        sys.modules['odoo.addons.pb_payai_actions.payai'] = mod
        setattr(sys.modules['odoo.addons.pb_payai_actions'], 'payai', mod)
        spec.loader.exec_module(mod)
    return sys.modules['odoo.addons.pb_payai_actions.payai']
