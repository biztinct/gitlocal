# Part of biz_host_db — portable Odoo 19 platform layer. License LGPL-3.
{
    'name': 'Biz Host Database Map',
    'summary': 'Serve a database on any hostname (custom domains) via a server-side host map',
    'description': """
SERVER-WIDE module — load it with `server_wide_modules = base,rpc,web,biz_host_db`
in the server config. It is never installed in a database.

`dbfilter = ^%d$` routes by the FIRST label of the hostname, so a customer's own
domain (jobs.customer.com) asks for a database called "jobs" and gets none.
This module puts an exact hostname -> database map in front of that rule:

    /etc/odoo-host-db.map          (one "hostname database" pair per line)

A host listed there is served from its database; every other host falls through
to the configured dbfilter unchanged. The file is re-read when its mtime
changes, so adding a domain needs no restart.

Why a file and not an nginx header: a header is client-supplied unless every
proxy block strips it, and one forgotten block would let a visitor pick another
tenant's database. The map is on disk, root-owned, and keyed on the host the
request was actually routed by.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'author': 'Biztinct',
    'license': 'LGPL-3',
    'depends': ['base'],
    'installable': True,
    'auto_install': False,
}
