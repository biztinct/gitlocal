# Payobook Zoho SSO

Secure Zoho Accounts single sign-on for Odoo 19 CE using Authorization Code +
PKCE. The module does not reuse or persist payroll-import access tokens.

## Zoho API Console

Create a **Server-based Application** and register the exact callback shown in
Payobook's General Settings. For the main database it is normally:

```text
https://payobook.com/auth/zoho/callback
```

Configure these values under **Settings → General Settings → Zoho single
sign-on**:

- enable Zoho single sign-on;
- client ID and client secret;
- the Zoho Accounts data centre used by the organisation;
- optional exact-email auto-linking and its allowed company domains;
- the default logical destination, such as `action-1156`.

The login-only OAuth scope is fixed to:

```text
AaaServer.profile.READ,email
```

## Zoho People button

Copy the generated button URL from General Settings, or use:

```text
https://payobook.com/auth/zoho/start?target=action-1156
```

The `target` is a same-origin logical destination. External redirect URLs are
not accepted.

## First login

When auto-linking is disabled, the first verified attempt creates a pending
identity without creating an Odoo user. An administrator approves it at
**Settings → Zoho SSO → Identity approvals** by selecting an existing active
Payobook user and changing the state to **Linked**.

When auto-linking is enabled, it only operates for explicitly allowed email
domains and only when exactly one active existing Payobook user matches the
verified Zoho email/login.
