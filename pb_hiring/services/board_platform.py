"""Server-owned partner credentials shared across databases; never tenant-editable."""

import json
import os
import stat

CONFIG_FILE = "/etc/payobook/job-board-apps.json"


def read_platform(provider, environment, tenant_key):
    # Configuration is provisioned by the platform operator, not a tenant RPC.
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o027
                or info.st_uid not in (0, os.getuid())
            ):
                raise ValueError("Partner configuration permissions are not private")
            data = json.load(stream)
        app = data[provider][environment]
        tenant = app["tenants"][tenant_key]
        if (
            not app.get("client_id")
            or not app.get("client_secret")
            or not tenant.get("enabled")
        ):
            raise ValueError(
                "Partner application or tenant authorization is incomplete"
            )
        return {k: app[k] for k in ("client_id", "client_secret")} | {
            "tenant": dict(tenant),
            "certified": app.get("certified") is True,
        }
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError(
            "Payobook must configure its approved partner app and authorize this tenant for the selected environment."
        ) from None
