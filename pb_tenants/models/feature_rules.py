# -*- coding: utf-8 -*-
"""FLEET P4 — what a customer is actually shown, decided as a pure function.

WHY THIS FILE EXISTS AT ALL (rail R6). The answer to "is Insights switched on
for AB Mauri" is worked out on the platform's database and then WRITTEN to the
customer's. A test cannot follow it across that boundary, so the decision is
lifted out of the write and put here, where a test can ask it a hundred
questions in a millisecond. `sync_rules.py` and `rollout_rules.py` are the same
idea; this is the third of them.

THE WHOLE RULE IS TWO LINES.
  * A feature the customer has no row for is whatever the catalogue says by
    default. Silence means the default, never "off".
  * A feature the customer HAS a row for is whatever that row says.

And then one thing that is not a rule but a rail:

  A SWITCH HIDES DOORS. IT IS NOT A SECURITY CONTROL. Turning Insights off for
  a customer takes the entry off their rail, takes the tiles out of their hubs
  and takes the rows out of their search. It does not add a permission rule to
  the data behind it, and it never has: what somebody may READ is decided by
  the roles they hold, on their own database, exactly as before. The cockpit
  says this in those words, and this comment is the same sentence for the
  person reading the code.
"""

#: The ONE setting on a customer's database that carries all of this. Written
#: by the platform, read by `pb_tenancy` on their side. It lives here, next to
#: the rules, so the writer and the reader cannot drift apart through two
#: separate literals.
T_FEATURES = 'pb_tenancy.features'

#: How an OFF feature shows. `hide` takes the door away; `lock` leaves it on
#: screen with a padlock and one line about how to get it — the teaser the rail
#: has been able to draw since long before this phase.
MODES = ('hide', 'lock')

#: The areas a feature belongs to, only ever used to group the matrix.
AREAS = ('pay', 'people', 'insights', 'compliance', 'workforce', 'learn',
         'platform')

#: The default sentence under a locked door. A customer must never be shown a
#: dead end, so even a feature whose catalogue row forgot its line has one.
DEFAULT_LOCK_TEXT = ("This part of Payobook is not switched on for your "
                     "company. Ask Payobook to switch it on.")

#: Where a switch came from. `manual` is somebody deciding; `plan` is reserved
#: for FLEET P5, which will set switches from what a customer pays for. Nothing
#: in P4 ever writes `plan`; the column exists so P5 does not have to migrate
#: every row it finds.
SOURCES = ('manual', 'plan')


def normal_mode(mode):
    """A mode we are prepared to act on. Anything else is `hide`.

    Damage must fail towards the SAFE answer, and here the safe answer is the
    quiet one: a hand-edited row saying `mode = 'lok'` should take the door
    away, not paint a padlock with no text under it.
    """
    return mode if mode in MODES else 'hide'


def effective_features(catalogue, overrides):
    """What ONE customer is shown, from the catalogue and their own rows.

    `catalogue` is a list of plain dicts — `{key, default_on, mode, lock_text}`
    and whatever else the caller wants to carry — in any order.
    `overrides` is `{key: on}` or `{key: {'on': bool, …}}`; both shapes are
    accepted because the cockpit holds one and the database holds the other.

    Returns `{key: {'on', 'mode', 'lock_text'}}` — exactly what is written to
    the customer and exactly what their browser reads back, so there is one
    shape and not a translation layer between two.

    A key that is not in the catalogue is not in the answer, however loudly an
    override asks for it: a switch for a feature nobody has defined is a switch
    that hides nothing and would sit on the customer's database for ever.
    """
    out = {}
    for row in catalogue or []:
        key = (row.get('key') or '').strip()
        if not key:
            continue
        over = (overrides or {}).get(key)
        if isinstance(over, dict):
            on = over.get('on')
        else:
            on = over
        if on is None:
            on = bool(row.get('default_on', True))
        out[key] = {
            'on': bool(on),
            'mode': normal_mode(row.get('mode')),
            'lock_text': (row.get('lock_text') or '').strip() or DEFAULT_LOCK_TEXT,
        }
    return out


def custom_count(catalogue, overrides):
    """How many of this customer's switches DISAGREE with the catalogue.

    The number on the matrix's row and on the tenant's Overview: "9 of 11 on ·
    2 custom". An override that happens to say the same thing as the default is
    not custom — it changes nothing, and counting it would make a row look
    edited when nobody has decided anything about it.
    """
    defaults = {(r.get('key') or ''): bool(r.get('default_on', True))
                for r in catalogue or []}
    n = 0
    for key, over in (overrides or {}).items():
        if key not in defaults:
            continue
        on = over.get('on') if isinstance(over, dict) else over
        if on is None:
            continue
        if bool(on) != defaults[key]:
            n += 1
    return n


def features_sentence(effective):
    """"9 of 11 switched on" — the one line a row leads with.

    Plain words on purpose: the reader is the person who sells this product,
    not the person who wrote it.
    """
    total = len(effective or {})
    on = sum(1 for v in (effective or {}).values() if v.get('on'))
    if not total:
        return "Nothing is switchable yet."
    if on == total:
        return "Everything is switched on."
    return "%d of %d switched on." % (on, total)
