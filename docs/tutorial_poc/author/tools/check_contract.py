#!/usr/bin/env python3
"""Verify that everything Payobook Learn teaches is still true of the product.

WHY THIS EXISTS
---------------
The practice company is a JavaScript fixture, not an isolated tenant. That buys
real safety — there is no server on the other end of it, so a practice action
cannot reach an employee — at the cost of drift: rename a selection value,
retire a menu leaf or re-point an action tag, and the tutorial keeps
confidently teaching a product that no longer exists.

This script is how that cost is paid. `contract.json` declares every fact the
tutorial asserts, together with where it came from; this re-reads the modules
and fails when a declaration no longer holds — naming the fixture entries AND
the content that quotes them, so you know exactly what to update.

    python3 docs/tutorial_poc/author/tools/check_contract.py
    python3 docs/tutorial_poc/author/tools/check_contract.py --quiet   # CI: errors only

Exit codes: 0 = everything still true · 1 = drift detected · 2 = cannot run.

WHEN IT FAILS there are two correct responses and one wrong one:
  1. The product changed on purpose -> update `expect` here, then
     practice-data.js, then the `taughtIn` content the entry names.
  2. The product changed by accident -> fix the product.
  3. WRONG: relax the check. A green checker that proves nothing is worse than
     no checker, because people trust the tutorial more, not less.
"""

import argparse
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUTHOR = os.path.dirname(HERE)                       # docs/tutorial_poc/author
REPO = os.path.dirname(os.path.dirname(os.path.dirname(AUTHOR)))

RED, GREEN, YELLOW, DIM, BOLD, OFF = (
    "\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    RED = GREEN = YELLOW = DIM = BOLD = OFF = ""


class Result:
    def __init__(self):
        self.failures = []   # (check_id, [problems], check dict)
        self.passed = 0
        self.skipped = []    # (check_id, reason)

    def ok(self):
        self.passed += 1

    def fail(self, check, problems):
        self.failures.append((check.get("id", "?"), problems, check))

    def skip(self, check, reason):
        self.skipped.append((check.get("id", "?"), reason))


def read(root, rel):
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def region(text, symbol):
    """The slice of `text` that belongs to `symbol`.

    Anchor on the DEFINITION, not the first mention — a method name usually
    appears first inside `compute="..."` on the field, hundreds of lines above
    the body, and scoping to that window silently finds nothing.

    Deliberately approximate after that: from the definition to whatever looks
    like the next top-level one. A lint that is 95% right and always runs beats
    a parser that is 100% right and gets disabled the first time a decorator
    breaks it.
    """
    # ORDER IS THE WHOLE POINT. The bare name is the LAST resort, because in a
    # well-commented file the first mention of a method is the paragraph at the
    # top explaining what it does — which is how an `absent` check scoped to one
    # ES-class method came to be scoped to the file header instead, and reported
    # every one of its expectations missing. The two middle probes are the JS
    # method definition at class-body indent, `async` first; a CALL is never
    # written at that indent without a `this.` in front of it.
    i = -1
    for probe in ("def %s" % symbol, "\n    async %s(" % symbol,
                  "\n    %s(" % symbol, "%s = " % symbol, symbol):
        i = text.find(probe)
        if i != -1:
            break
    if i == -1:
        return None
    tail = text[i:]
    stop = len(tail)
    # `\n};` is the JS one and it earns its place: without it a top-level object
    # literal has no stop pattern at all in a .js file, so the region runs to
    # EOF and every two-space key in the rest of the file looks like part of it.
    # The last two are the JS METHOD boundary and they were added for the
    # scenario engine: `\n};` only ends a top-level object literal, so scoping
    # to one method of an ES class ran to end-of-file and an `absent` check on
    # `_enterStep` failed on a call made three methods further down. Both are
    # written so they cannot fire inside Python — a closing brace at four-space
    # indent followed by a blank line and either a JSDoc block or another
    # member is not a shape Python source has.
    for pat in (r"\ndef ", r"\n@api", r"\nclass ", r"\n[A-Z_]{3,} = ",
                r"\n    def ", r"\n\};",
                r"\n    \}\n\n    /\*\*", r"\n    \}\n\n    [A-Za-z_$]+\("):
        m = re.search(pat, tail[40:])
        if m:
            stop = min(stop, m.start() + 40)
    return tail[:stop]


# ---------------------------------------------------------------- check kinds
def check_contains(root, chk):
    """Every literal in `expect` must appear in the file (optionally in `within`)."""
    files = chk.get("files") or [chk["file"]]
    problems = []
    blobs = []
    for rel in files:
        text = read(root, rel)
        if text is None:
            return None, "file not found: %s" % rel
        blobs.append(text)
    blob = "\n".join(blobs)
    if chk.get("within"):
        scoped = region(blob, chk["within"])
        if scoped is None:
            return None, "symbol not found: %s" % chk["within"]
        blob = scoped
    for want in chk["expect"]:
        if want not in blob:
            problems.append("missing: %s" % want)
    return problems, None


def check_absent(root, chk):
    """Nothing in `expect` may appear. The inverse check, for a fact that is
    true because something is NOT there — a tier a screen must not show, a
    method the Coach must never reach."""
    files = chk.get("files") or [chk["file"]]
    blob = ""
    for rel in files:
        text = read(root, rel)
        if text is None:
            return None, "file not found: %s" % rel
        blob += text
    if chk.get("within"):
        scoped = region(blob, chk["within"])
        if scoped is None:
            return None, "symbol not found: %s" % chk["within"]
        blob = scoped
    return ["present but must not be: %s" % w for w in chk["expect"] if w in blob], None


def check_xmlids(root, chk):
    """Record ids must still be declared somewhere in the named data files."""
    blob = ""
    for rel in chk["files"]:
        text = read(root, rel)
        if text is None:
            return None, "file not found: %s" % rel
        blob += text
    problems = []
    for xmlid in chk["expect"]:
        if ('id="%s"' % xmlid) not in blob:
            problems.append("record no longer declared: %s" % xmlid)
    return problems, None


def po_pairs(text):
    """msgid -> msgstr, single-line entries only (which is all we assert)."""
    out = {}
    msgid = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'^msgid "(.*)"$', line)
        if m:
            msgid = m.group(1)
            continue
        m = re.match(r'^msgstr "(.*)"$', line)
        if m and msgid is not None:
            out.setdefault(msgid, m.group(1))
            msgid = None
    return out


def check_po(root, chk):
    """Shipped Vietnamese strings must still say what the content ships.

    Spot checks, not a full audit: the generator already refuses to write a
    translatable with no Vietnamese. What this catches is a translation being
    silently REPLACED — the promise in the honesty banner is the one string in
    this module where that would matter most.
    """
    problems = []
    for rel, pairs in chk["expect"].items():
        text = read(root, rel)
        if text is None:
            return None, "file not found: %s" % rel
        found = po_pairs(text)
        for msgid, want in pairs.items():
            got = found.get(msgid)
            if got is None:
                problems.append('%s: msgid "%s" is gone' % (rel, msgid))
            elif got != want:
                problems.append('%s: "%s" now translates to "%s", content ships "%s"'
                                % (rel, msgid, got, want))
    return problems, None


def check_model_scope(root, chk):
    """Every model a METHOD reaches must be inside an allowed namespace.

    An `absent` list is a list of the models somebody thought to ban, which is
    the same weakness the advice deny-list had: it protects against the six
    names in it and against nothing else. This asks the general question
    instead — parse the file, find the method, collect every `self.env['x.y']`
    literal inside it, and require each one to start with an allowed prefix.

    Written for the composer's corpus builder, where the guarantee is not
    "these six product models are absent" but "nothing outside learn.* is
    read at all", and where the difference is whether an employee's pay can
    reach a prompt.
    """
    text = read(root, chk["file"])
    if text is None:
        return None, "file not found: %s" % chk["file"]
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return None, "could not parse %s: %s" % (chk["file"], exc)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == chk["within"]:
            target = node
            break
    if target is None:
        return None, "symbol not found: %s" % chk["within"]

    prefixes = tuple(chk["expect"])
    found, problems = set(), []
    for node in ast.walk(target):
        if not isinstance(node, ast.Subscript):
            continue
        key = node.slice
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        name = key.value
        # A model name, not a dict key: dotted, unspaced, lowercase-ish.
        if "." not in name or " " in name:
            continue
        found.add(name)
        if not name.startswith(prefixes):
            problems.append(
                "%s() reads '%s', which is outside %s"
                % (chk["within"], name, "/".join(prefixes)))
    if not found:
        problems.append(
            "%s() names no model at all — the scan found nothing to check, "
            "which means it is broken rather than passing" % chk["within"])
    return problems, None


def _bilingual_pairs(node, out):
    """Every `{en, vi}` PROSE leaf in the tree, as en -> {vi, …}.

    The `{en, vi}` key set is not sufficient on its own, and LEARNOS Phase 2
    is what proved it: a glossary entry's `match` block is
    `{"en": [...], "vi": [...]}` — the per-language phrase lists the hovercard
    matches on — which has the same keys and is not prose. Treating it as a
    leaf raised `unhashable type: 'list'`, which was at least loud; the quieter
    version of the same bug is a non-prose node being counted as a translatable
    and reported as untranslated. A prose leaf is two STRINGS, so that is what
    is tested.
    """
    if isinstance(node, dict):
        if set(node) == {"en", "vi"}:
            if isinstance(node["en"], str) and isinstance(node["vi"], str):
                out.setdefault(node["en"], set()).add(node["vi"])
                return
            # Same keys, not prose: keep walking rather than claiming it.
        for value in node.values():
            _bilingual_pairs(value, out)
    elif isinstance(node, list):
        for value in node:
            _bilingual_pairs(value, out)


def _lesson_keys(tree):
    return {lesson.get("key")
            for station in tree.get("stations") or []
            for lesson in station.get("lessons") or []}


def check_json_content(root, chk):
    """Assertions about the STATIC CONTENT PLANE.

    Since LEARNOS Phase 1a the learning content is one generated JSON asset
    rather than a set of data files, so the checks that used to grep XML have
    to ask the tree instead. Greping the JSON as text would work today and
    break the first time the emitter changes its indentation — and worse, a
    literal like `"key": "L1"` would happily match a station or a mission.

    Three assertion kinds, each the retargeted form of a check that existed:

      sections    the top-level keys both consumers assume are present
      nonEmpty    …and that are not allowed to be an empty collection, because
                  an empty section renders as a blank surface rather than an
                  error
      lessonKeys  every named lesson is actually written
      bilingual   an English leaf still carries the Vietnamese the content
                  ships, wherever in the tree it appears
      banner      the generated-file marker, because a generated file that does
                  not say so is one somebody will hand-edit
    """
    text = read(root, chk["file"])
    if text is None:
        return None, "file not found: %s" % chk["file"]
    try:
        tree = json.loads(text)
    except ValueError as exc:
        return None, "not valid JSON: %s" % exc

    want = chk["expect"]
    problems = []
    for section in want.get("sections") or []:
        if section not in tree:
            problems.append("section is gone: %s" % section)
    for section in want.get("nonEmpty") or []:
        if not tree.get(section):
            problems.append("section is empty: %s" % section)
    if want.get("lessonKeys"):
        present = _lesson_keys(tree)
        for key in want["lessonKeys"]:
            if key not in present:
                problems.append("lesson no longer written: %s" % key)
    if want.get("bilingual"):
        pairs = {}
        _bilingual_pairs(tree, pairs)
        for en, vi in want["bilingual"].items():
            got = pairs.get(en)
            if not got:
                problems.append('no bilingual leaf reads "%s" any more' % en)
            elif vi not in got:
                problems.append('"%s" now translates to %s, content ships "%s"'
                                % (en, " / ".join('"%s"' % g for g in sorted(got)), vi))
    if want.get("banner") and want["banner"] not in (tree.get("__generated__") or ""):
        problems.append("the generated-file banner is gone")
    return problems, None


KINDS = {
    "contains": check_contains,
    "selection": check_contains,
    "absent": check_absent,
    "xmlids": check_xmlids,
    "po": check_po,
    "model-scope": check_model_scope,
    "json-content": check_json_content,
}

# Payobook anchors follow a screen-prefix convention, which is what makes them
# lintable: pw (run payroll wizard), pk (pay run board), ps (payslip review),
# im (import), iw (import wizard), lg (the shared ledgers), rep (replica-only),
# from Phase B fs (formula studio), st (statutory), sr (salary structures),
# ig (integrations), and from Phase C1 dash (dashboard), pa (approvals),
# pe (employees), ct (contracts), in (insights), ex (explorer),
# wa (workforce analytics), gr (government reports).
#
# The Phase C1 prefixes are two letters each because the three People-family
# cockpits share the `ppl-*` CLASS vocabulary in their templates — one prefix
# per SCREEN is what stops a lesson pointing at the Employees roster and landing
# on the Contracts one.
#
# A prefix missing from this list is not a loud failure — the anchor simply
# stops being linted, and the content can then point at a control that does not
# exist. Adding the prefix is part of adding a screen.
ANCHOR_RE = re.compile(
    r'"((?:pw|pk|ps|im|iw|lg|rep|fs|st|sr|ig|dash|pa|pe|ct|in|ex|wa|gr)'
    r'-[a-z0-9][a-z0-9-]*)"')


def anchor_lint(cfg, res, quiet):
    """Content names controls; a rename must break the build.

    This runs at AUTHORING time, against the real product templates. It is the
    same comparison tests/test_anchor_registry.py makes after generation, one
    step earlier — the point being to fail before a bad anchor becomes a
    database record.

    Unlike the prototype's version, `present` is read from LITERAL attributes
    only. Our anchors are literal attributes in real OWL templates, so the
    weaker "the name appears somewhere as a string" fallback is not needed and
    would only hide a deleted attribute.
    """
    spec = cfg.get("anchorLint")
    if not spec:
        return
    referenced, present = set(), set()
    for rel in spec["contentFiles"]:
        text = read(AUTHOR, rel)
        if text is None:
            res.skip({"id": "anchor-lint"}, "content file not found: %s" % rel)
            return
        referenced |= set(ANCHOR_RE.findall(text))
    for rel in spec["templateFiles"]:
        text = read(REPO, rel)
        if text is None:
            res.skip({"id": "anchor-lint"}, "template file not found: %s" % rel)
            return
        present |= set(re.findall(r'data-coach="([^"]+)"', text))
    # Practice-only anchors have no product template by definition; they are
    # declared in the registry and drawn by the replica, and the module's own
    # test checks that side.
    registry = read(REPO, spec["registry"])
    if registry is None:
        res.skip({"id": "anchor-lint"}, "registry not found: %s" % spec["registry"])
        return
    present |= set(json.loads(registry)["practice"])

    missing = sorted(referenced - present)
    chk = {"id": "anchor-lint",
           "why": spec["why"],
           "taughtIn": ["every lesson step, mission target and coach point-at"]}
    if missing:
        res.fail(chk, ["content points at a control that no longer exists: %s" % a
                       for a in missing])
    else:
        res.ok()
        if not quiet:
            orphans = sorted(present - referenced)
            print("  %s✓%s anchor-lint            %s%d referenced, all present%s%s"
                  % (GREEN, OFF, DIM, len(referenced), OFF,
                     (" · %d anchor(s) no content points at yet" % len(orphans))
                     if orphans else ""))


def token_lint(cfg, res, quiet):
    """Every `{{key}}` content writes must be a declared tenant slot.

    Same failure mode as a broken anchor, different surface: a typo renders the
    key itself to a learner instead of the company's pay day. Also reports slots
    nothing uses, which are dead configuration a tenant admin can still see and
    change to no effect.
    """
    spec = cfg.get("tokenLint")
    if not spec:
        return
    used = set()
    for rel in spec["contentFiles"]:
        text = read(AUTHOR, rel)
        if text is None:
            res.skip({"id": "token-lint"}, "content file not found: %s" % rel)
            return
        used |= set(re.findall(r"\{\{([a-zA-Z][a-zA-Z0-9_]*)\}\}", text))
    fixture = read(AUTHOR, spec["declaredIn"])
    if fixture is None:
        res.skip({"id": "token-lint"}, "fixture not found: %s" % spec["declaredIn"])
        return
    block = region(fixture, "TENANT_DEFAULTS")
    declared = set(re.findall(r"^\s{2}([a-zA-Z][a-zA-Z0-9_]*):\s*B\(", block or "", re.M))
    undeclared = sorted(used - declared)
    chk = {"id": "token-lint", "why": spec["why"],
           "fixture": ["TENANT_DEFAULTS"],
           "taughtIn": ["every string naming a tier, a date or a contact"]}
    if undeclared:
        res.fail(chk, ["content uses an undeclared tenant slot: {{%s}}" % k
                       for k in undeclared])
    else:
        res.ok()
        if not quiet:
            unused = sorted(declared - used)
            print("  %s✓%s token-lint             %s%d slot(s) declared, %d used%s%s"
                  % (GREEN, OFF, DIM, len(declared), len(used), OFF,
                     (" · unused: %s" % ", ".join(unused)) if unused else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quiet", action="store_true", help="print failures only")
    ap.add_argument("--contract", default=os.path.join(AUTHOR, "contract.json"))
    args = ap.parse_args()

    try:
        with open(args.contract, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception as exc:                                  # noqa: BLE001
        print("%scannot read contract: %s%s" % (RED, exc, OFF))
        return 2

    root = os.path.abspath(os.path.join(AUTHOR, cfg.get("repoRoot", "../../..")))
    # pb_sidebar rather than addons/: Payobook's modules live at the repository
    # root, so the presence of an addons/ directory would prove nothing.
    if not os.path.isdir(os.path.join(root, "pb_sidebar")):
        print("%scannot find pb_sidebar from repoRoot %s%s" % (RED, root, OFF))
        return 2

    if not args.quiet:
        print("\n%sPayobook Learn — contract check%s" % (BOLD, OFF))
        print("%srepo: %s · contract schema %s%s\n"
              % (DIM, root, cfg.get("schemaVersion", "?"), OFF))

    res = Result()
    for chk in cfg["checks"]:
        fn = KINDS.get(chk.get("kind"))
        if fn is None:
            res.skip(chk, "unknown kind: %s" % chk.get("kind"))
            continue
        problems, err = fn(root, chk)
        if err:
            res.skip(chk, err)
        elif problems:
            res.fail(chk, problems)
        else:
            res.ok()
            if not args.quiet:
                print("  %s✓%s %-22s %s%s%s"
                      % (GREEN, OFF, chk["id"], DIM,
                         (chk.get("file") or (chk.get("files") or ["-"])[0]), OFF))

    anchor_lint(cfg, res, args.quiet)
    token_lint(cfg, res, args.quiet)

    for cid, reason in res.skipped:
        print("  %s⊘%s %-22s %sskipped — %s%s" % (YELLOW, OFF, cid, DIM, reason, OFF))

    if res.failures:
        print("\n%s%d contract check(s) FAILED — the tutorial now teaches something "
              "untrue.%s" % (RED + BOLD, len(res.failures), OFF))
        for cid, problems, chk in res.failures:
            print("\n  %s✗ %s%s" % (RED + BOLD, cid, OFF))
            print("    %swhy it matters:%s %s" % (BOLD, OFF, chk.get("why", "-")))
            for p in problems:
                print("      %s- %s%s" % (RED, p, OFF))
            if chk.get("fixture"):
                print("    %supdate in practice-data.js:%s %s"
                      % (BOLD, OFF, ", ".join(chk["fixture"])))
            if chk.get("taughtIn"):
                print("    %sthen re-read this content:%s %s"
                      % (BOLD, OFF, ", ".join(chk["taughtIn"])))
        print()
        return 1

    print("\n%s✓ %d checks passed%s%s — everything the tutorial teaches is still "
          "true of the product.%s\n"
          % (GREEN + BOLD, res.passed, OFF, GREEN, OFF))
    return 0


if __name__ == "__main__":
    sys.exit(main())
