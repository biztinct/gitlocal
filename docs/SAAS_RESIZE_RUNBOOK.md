# Resizing the Payobook platform machine — one page

Written 2026-09-03 (FLEET P3). Read this the day Mission Control says **"No room
for another customer"**, or the day you sell one more customer than the gauge
says will fit.

**This is the only step of the capacity story that is not automated, on purpose.**
The platform measures the room it has left and refuses to create a customer past
it; growing the machine costs money and downtime, so it stays a decision a person
makes.

---

## What you are changing

| | Today (measured 2026-09-03) | After |
|---|---|---|
| Memory | 1.9 GB (`MemTotal` 1907 MB) | 4 GB or 8 GB |
| Processor | 2 cores | 2 cores (4 GB plan) |
| Disk | 58 GB, 50 % used | 80 GB (4 GB plan) / 160 GB (8 GB plan) |
| Customers it holds | see the gauge on the Tenants screen | roughly `(new free memory − 400 MB) ÷ per-customer cost` |
| Cost | the current plan | about twice / four times it |

The per-customer memory cost is the setting `pb_tenants.tenant_cost_mb`, measured
on this machine (see the FLEET ledger, entry F34). **It does not change when you
resize** — the same customer costs the same memory on a bigger machine — so leave
the setting alone afterwards. What changes is how much free memory there is.

**Expected downtime: 30 to 60 minutes**, most of it the snapshot and the first
boot. Every customer is signed out and every site is unreachable for the whole of
it. Do it on a Sunday, and put a notice on the customers' screens the day before
(Mission Control → **Send a notice** → tick **Also show this on the public status
page**).

---

## Before you start

1. **Tell everybody.** Send the notice, public, with the window in it. It stays on
   payobook.com/status while the machine is down, because that page is a file the
   web server hands out without the application being up — but only if the new
   machine is the one serving it, so also expect the status page to be down during
   the move. Say the window in the notice itself.
2. **Take a backup of every customer**: Mission Control → each customer →
   **Back up now**. The snapshot below covers everything, but a snapshot is a
   whole machine and a per-customer backup is the thing you can actually restore
   one customer from.
3. **Write down the current address**: `3.25.57.42` (this is what
   `payobook.com` and every `*.payobook.com` resolves to today).
4. **OWNER TO CONFIRM before anything else — is that address a Lightsail *static
   IP*?** In the Lightsail console → **Networking** → the address should be listed
   under *Static IPs* and attached to this instance. This machine's own credentials
   are not allowed to ask, so it could not be checked from here.
   * **If it IS static** — good. You detach it from the old instance and attach it
     to the new one, and no DNS changes at all.
   * **If it is NOT static** — the address is released the moment the instance
     stops, and every name breaks. In that case: create a static IP first, attach
     it to the CURRENT instance (this changes the public address), update the DNS
     records at Mat Bao (`@`, `*`, and every customer's own name), wait for them to
     take, and only then do the resize. Add a day for that.

---

## The move

The instance is a **Lightsail** instance (`i-08fe6d2b46a0d7520`, plan 2 GB / 2
cores / 60 GB, zone `ap-southeast-2a`). Lightsail cannot change an instance's plan
in place: you take a snapshot and build a bigger instance from it.

1. **Stop the application cleanly** (so the snapshot is not of a half-written
   database):
   ```bash
   ssh Payobook19v2
   sudo systemctl stop odoo-server
   sudo systemctl stop nginx
   sync
   ```
2. **Snapshot.** Lightsail console → the instance → **Snapshots** → *Create
   snapshot*. Name it `payobook-before-resize-YYYY-MM-DD`. Wait for it to say
   *Available* (typically 10–20 minutes for this disk).
3. **Create the new instance from the snapshot.** Snapshots tab → the snapshot →
   *Create new instance*. Pick:
   * the same region and zone (`ap-southeast-2a`);
   * the plan you want — **4 GB / 2 cores / 80 GB** is the next size up and roughly
     doubles the number of customers this platform can hold; 8 GB if you are
     buying room for a year;
   * name it `payobook-4gb-YYYY-MM-DD`.
4. **Move the address.** Networking → the static IP → *Detach* from the old
   instance → *Attach* to the new one. Nothing at the registrar changes.
5. **Open the firewall the same way.** New instances get the default firewall.
   Under the new instance → Networking → IPv4 firewall, allow **22 (SSH), 80
   (HTTP), 443 (HTTPS)** — copy exactly what the old instance has.
6. **Boot and check it came up:**
   ```bash
   ssh ubuntu@3.25.57.42          # the same key as before
   free -m                        # MemTotal should now be ~3900 or ~7900
   sudo systemctl status odoo-server nginx
   sudo journalctl -u odoo-server -n 40 | grep -i "registry loaded"
   ss -ltnp | grep 8069
   ```
   If the application did not start on its own: `sudo systemctl start odoo-server`.
7. **Let the database server use the new memory.** PostgreSQL's settings were
   tuned for a 2 GB box and will not use more on their own. **OWNER TO CONFIRM
   with whoever tuned it** — on a 4 GB machine the usual step is
   `shared_buffers = 1GB` and `effective_cache_size = 2GB` in
   `/etc/postgresql/16/main/postgresql.conf`, then
   `sudo systemctl restart postgresql`. Skipping this is not dangerous; it simply
   leaves some of the new machine unused.

---

## Verify before you tell anybody it is done

Work down this list. Every item is something a customer would notice.

| # | Check | How |
|---|---|---|
| 1 | The application is running | `sudo systemctl is-active odoo-server` → `active` |
| 2 | It finished loading | `sudo journalctl -u odoo-server \| grep -i "Registry loaded"` |
| 3 | The platform answers | open `https://payobook.com` and sign in |
| 4 | Every customer answers | open each customer's own address (`abm.payobook.com`, …) and check the sign-in page appears |
| 5 | Certificates are still trusted | no browser warning on the platform and on a customer address; then Mission Control → **Platform checks** → the two certificate rows are green |
| 6 | The public page is served | `curl -sI https://payobook.com/status` → `200`, and the body is the status page |
| 7 | Alerts still reach you | Mission Control → **Alert settings** → **Send a test email**, and look in your inbox |
| 8 | Scheduled jobs are running | Mission Control → the fleet health numbers refresh within the hour; the morning summary arrives the next day |
| 9 | The gauge has moved | the Tenants screen now says room for more customers |
| 10 | Backups still work | Mission Control → a customer → **Back up now** |

Then take the maintenance notice down (Mission Control → **Take it down**).

---

## Afterwards

* **Leave `pb_tenants.tenant_cost_mb` alone.** It is what one customer costs, not
  what the machine has.
* **Keep the old instance stopped, not deleted, for 48 hours.** It is the only way
  back if something on the new one turns out to be missing. After 48 hours delete
  the old instance AND the snapshot (Lightsail charges for both).
* **Write down what the new machine measured** — `free -m`, and the room the gauge
  now reports — in the FLEET ledger, so the next person knows what changed.

## If it goes wrong

Attach the static IP back to the OLD instance and start it. That is the whole
rollback, it takes about five minutes, and it is the reason the old instance is
kept for two days.
