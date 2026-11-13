/* Standalone setup surface: shared by signed-in managers and invited IT. */
(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const manager = document.body.dataset.manager;
    const token = location.hash.slice(1);
    const base = manager ? `/clock-bridge/manage/${manager}/` : '/clock-bridge/setup/';
    let busy = false;
    let loaded = false;
    let refreshing = false;
    let invitation = '';
    function show(id, yes = true) { $(id).hidden = !yes; }
    function message(text, error = false) {
        $('message').textContent = text;
        $('message').className = error ? 'message error' : 'message';
        show('message');
    }
    async function call(operation, download = false) {
        const headers = manager ? {} : {Authorization: `Bearer ${token}`};
        const body = new URLSearchParams();
        if (manager) body.set('csrf_token', document.body.dataset.csrf);
        const abort = new AbortController();
        const deadline = setTimeout(() => abort.abort(), download ? 120000 : 20000);
        try {
            const result = await fetch(base + operation, {method: 'POST', headers, body,
                credentials: manager ? 'same-origin' : 'omit', cache: 'no-store', redirect: 'error', signal: abort.signal});
            if (!result.ok) {
                let detail;
                try { detail = (await result.json()).error; } catch (_) { /* login/session/proxy error */ }
                const error = new Error(detail || (manager ? 'Your session may have expired. Return to Payobook and reopen Guided setup.' : 'Could not reach Payobook. Check your connection and try again.'));
                error.status = result.status;
                throw error;
            }
            return await (download ? result.blob() : result.json());
        } catch (error) {
            if (error.name === 'AbortError') throw new Error('The request timed out. Check your connection and try again.');
            throw error;
        } finally { clearTimeout(deadline); }
    }
    function time(value) {
        if (!value) return 'Not yet';
        const date = new Date(value.replace(' ', 'T') + 'Z');
        return date.toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', timeZoneName:'short'});
    }
    function render(data) {
        $('company').textContent = data.company;
        $('connector-name').textContent = data.name;
        $('history').textContent = data.history_from;
        $('timezone').textContent = data.timezone;
        $('schedule-label').textContent = `Configured sync interval: ${data.interval_minutes} minutes`;
        const paired = data.state === 'connected';
        const read = paired && Boolean(data.last_read);
        const stale = paired && data.last_contact && Date.now() - new Date(data.last_contact.replace(' ', 'T') + 'Z').getTime() > Math.max(60, data.interval_minutes * 3) * 60000;
        const complete = read && data.pending === 0 && !data.needs_attention && !stale;
        $('status-pill').textContent = complete ? 'Sync received' : stale ? 'Contact overdue' : paired ? 'Paired' : data.state === 'revoked' ? 'Access revoked' : 'Awaiting setup';
        $('status-pill').className = 'pill ' + (complete ? 'good' : '');
        $('paired').textContent = paired ? 'Yes' : 'Not yet';
        $('contact').textContent = time(data.last_contact);
        $('read').textContent = read ? time(data.last_read) : 'Not yet';
        $('pending').textContent = read ? data.pending.toLocaleString() + ' records' : 'Awaiting first read';
        $('health-summary').textContent = data.needs_attention ? 'The PC reported a collection issue. Check Show diagnostics on Windows; queued records can continue uploading.' : complete ? 'The database was read and the PC reported an empty upload queue. Confirm the scheduled task on Windows.' : stale ? 'No recent contact. Check that the PC is awake, online and its scheduled task is running.' : paired ? 'The PC is paired. Run Sync now on Windows to verify the database read and upload.' : 'Install and pair the Windows connector to start the connection check.';
        $('code').disabled = paired;
        show('paired-note', paired);
        if (paired) { show('code-result', false); $('pairing-code').value = ''; }
        show('attention', data.needs_attention);
        $('status-updated').textContent = `Checked ${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})}. Contact and read times use your browser’s time zone.`;
        $('check-result').className = 'check-result' + (complete ? ' good' : '');
        $('check-summary').textContent = $('status-pill').textContent + '. ' + $('health-summary').textContent;
        $('check-details').textContent = `Last contact: ${time(data.last_contact)}. Last database read: ${read ? time(data.last_read) : 'Not yet'}. Queue: ${read ? data.pending.toLocaleString() + ' records' : 'Awaiting first read'}.`;
        $('check-time').textContent = $('status-updated').textContent;
        if (manager) {
            $('invite-expiry').textContent = data.invitation_until ? `Current invitation expires ${time(data.invitation_until)}.` : 'No active IT invitation.';
            show('revoke', !!data.invitation_until);
            $('invite').textContent = data.invitation_until ? 'Replace IT invitation' : 'Create IT invitation';
        } else {
            $('access-label').textContent = 'IT invitation · expires ' + time(data.invitation_until);
        }
        loaded = true;
        show('loading', false); show('fatal', false); show('app');
    }
    async function refresh() {
        if (busy || refreshing) return;
        refreshing = true;
        const button = $('refresh');
        button.disabled = true; button.setAttribute('aria-busy', 'true');
        button.textContent = 'Checking...';
        $('check-result').setAttribute('aria-busy', 'true');
        $('check-summary').textContent = 'Checking the latest status received by Payobook...';
        try { render(await call('status')); }
        catch (error) {
            $('check-result').className = 'check-result error';
            $('check-summary').textContent = error.message;
            $('check-time').textContent = 'Check failed. Any contact and read times above are from the previous successful check.';
            if (!loaded || error.status === 401 || error.status === 403) {
                show('app', false); show('loading', false); show('fatal');
                $('fatal-message').textContent = error.message;
            }
        } finally {
            refreshing = false; button.disabled = false;
            button.removeAttribute('aria-busy'); button.textContent = 'Check connection';
            $('check-result').removeAttribute('aria-busy');
        }
    }
    async function action(id, work) {
        if (busy || refreshing) return;
        busy = true;
        const button = $(id); button.disabled = true; button.setAttribute('aria-busy', 'true');
        try { await work(); }
        catch (error) { message(error.message, true); }
        finally { busy = false; button.disabled = false; button.removeAttribute('aria-busy'); }
    }
    $('server-address').value = location.origin;
    if (manager) {
        show('manager-nav'); show('invite-panel');
        $('access-label').textContent = 'Signed-in administrator';
        $('back-link').href = document.body.dataset.backUrl;
    }
    show('platform-note', !/Windows/i.test(navigator.userAgent));
    $('download').addEventListener('click', () => action('download', async () => {
        const blob = await call('download', true);
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url; anchor.download = 'PayobookAttendanceConnector.zip'; anchor.click();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
        message('Package downloaded. On the Windows PC, extract the ZIP and open Install.cmd.');
    }));
    $('code').addEventListener('click', () => action('code', async () => {
        const data = await call('code');
        $('pairing-code').value = data.code; show('code-result');
        message('Pairing code ready. Paste it into the Windows connector within 30 minutes.');
    }));
    $('invite').addEventListener('click', () => action('invite', async () => {
        if ($('revoke').hidden === false && !confirm('Replace the existing invitation? Its unused pairing code will also stop working. A paired PC keeps syncing.')) return;
        const data = await call('invite');
        invitation = location.origin + '/clock-bridge/setup#' + data.invitation;
        $('invitation').value = invitation; show('invite-result'); render(data);
        message('Invitation created. Share this private link directly with IT.');
    }));
    $('revoke').addEventListener('click', () => action('revoke', async () => {
        if (!confirm('Revoke this invitation and any unused code issued through it? A paired PC keeps syncing.')) return;
        render(await call('revoke-invite'));
        invitation = ''; $('invitation').value = ''; show('invite-result', false);
        message('Invitation revoked. Existing installation access is unchanged.');
    }));
    $('refresh').addEventListener('click', refresh); $('retry').addEventListener('click', refresh);
    document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
        const input = $(button.dataset.copy);
        try { await navigator.clipboard.writeText(input.value); message('Copied.'); }
        catch (_) { input.focus(); input.select(); message('Select and copy the highlighted text.'); }
    }));
    refresh();
    setInterval(() => { if (!document.hidden && !busy && !$('app').hidden) refresh(); }, 20000);
})();
