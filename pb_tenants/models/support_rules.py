# -*- coding: utf-8 -*-
"""FLEET P6 — what the platform is allowed to ask for, decided in pure functions.

RAIL R6. Every judgement here is about ANOTHER database — is that customer
reachable, has that customer switched us off — so none of it can be tested
where it is used. So it is not decided where it is used: the facts are gathered
in `support_service.py` and handed to these functions, which are ordinary
Python and have their own tests.
"""

#: The three lengths the cockpit offers, in minutes, with the words on the
#: buttons. Not free text: "how long do you need" is a question somebody answers
#: with a shrug, and a shrug becomes eight hours. Three deliberate choices makes
#: the two-hour default a decision rather than a habit.
DURATIONS = (
    (30, "30 minutes", "A quick look at one screen."),
    (120, "2 hours", "Working through something with them."),
    (480, "8 hours", "A whole day on a migration or a pay run."),
)
DEFAULT_MINUTES = 120
ALLOWED_MINUTES = tuple(m for m, _l, _b in DURATIONS)

#: A customer we may never open. `decommissioned` has no database left at all;
#: `pending_deletion` still has one, and helping somebody through their last
#: month is a real thing to need, so it is NOT on this list.
CLOSED_STATES = ('decommissioned', 'draft', 'provisioning', 'error')


def customer_blocker(state, linked, allowed):
    """Why this CUSTOMER cannot be opened at all, or None. PURE.

    Asked by the screen before anybody has typed anything, so the button can be
    disabled with the reason written beside it rather than offering a dialog
    that ends in a refusal.
    """
    if state in CLOSED_STATES:
        return "This customer has no live database to open."
    if not linked:
        return ("This customer's database has not been brought in step yet, so "
                "there is nowhere to record a support session. Bring them in "
                "step first — the button is on the \"In step with master\" "
                "screen.")
    if not allowed:
        return ("This customer has switched support access off. Nobody here "
                "can turn it back on: ask them to switch it on under "
                "Settings → About Payobook → Support access, and it takes "
                "effect at once.")
    return None


def support_refusal(state, linked, allowed, reason, minutes):
    """Why the platform may not open this customer NOW, or None. PURE.

    The reason is asked about first because it is the thing the person pressing
    the button controls: telling them "this customer is closed" when they simply
    have not typed anything yet is answering a question they did not ask.

    Returns the sentence to show, which is the whole answer — the caller never
    composes one of its own, so the screen and the server say the same thing.
    """
    if not (reason or '').strip():
        return ("Say what you need to look at first. The reason is written on "
                "the customer's own screen, so write it for them.")
    if len((reason or '').strip()) < 6:
        return ("That reason is too short to mean anything to the customer "
                "reading it later. A few words about what you are looking at.")
    blocker = customer_blocker(state, linked, allowed)
    if blocker:
        return blocker
    if minutes not in ALLOWED_MINUTES:
        return "Pick one of the three lengths."
    return None


def session_sentence(name, company, minutes):
    """The line written into the customer's log and into the alert. PURE."""
    label = dict((m, l) for m, l, _b in DURATIONS).get(minutes,
                                                       "%d minutes" % minutes)
    return ("%s opened a support session on %s for %s."
            % (name or "Payobook support", company, label))
