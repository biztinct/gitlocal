#!/bin/bash
# DOCSTUDIO W1A: signed-in requests on rize/payobook/sudima in the last N minutes (default 15). Read-only.
MIN=${1:-15}
SINCE=$(date -u -d "$MIN minutes ago" '+%Y-%m-%d %H:%M:%S')
sudo awk -v s="$SINCE" '($1" "substr($2,1,8)) >= s' /var/log/odoo/odoo-server.log \
  | grep -E ' INFO (rize|payobook|sudima) werkzeug: ' \
  | grep -E '"(POST|GET) /(web/dataset/|web/action|json/|mail/|web/webclient/load|bizapp|odoo/|web/session/get|my/|my |report/)' \
  | grep -vE 'websocket|/bus/|longpolling' | grep -E 'HTTP/1.[01]" 200 '
