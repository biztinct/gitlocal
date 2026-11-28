"""Isolated official SDK runner. Tokens arrive on stdin and are never logged.

The SDK dependencies live outside Odoo's Python import path. A short-lived
process avoids changing Odoo's requests/cryptography versions.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.environ.get('PB_HIRING_SDK_DIR', '/odoo/vendor/hiring-calendar-sdk'))


def busy(data):
    if data['provider'] == 'google':
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google_auth_httplib2 import AuthorizedHttp
        import httplib2
        service = build('calendar', 'v3', http=AuthorizedHttp(Credentials(data['token']), http=httplib2.Http(timeout=15)), cache_discovery=False)
        result = service.freebusy().query(body={'timeMin':data['start']+'Z', 'timeMax':data['stop']+'Z',
            'items':[{'id':e} for e in data['emails']]}).execute(num_retries=0)
        calendars = result.get('calendars', {})
        if any(e not in calendars or calendars[e].get('errors') for e in data['emails']):
            raise ValueError('calendar access')
        return [(b['start'],b['end']) for e in data['emails'] for b in calendars[e].get('busy',[])]
    if data['provider'] != 'microsoft':
        raise ValueError('provider')
    from azure.core.credentials import AccessToken
    from msgraph import GraphServiceClient
    from msgraph.generated.users.item.calendar.get_schedule.get_schedule_post_request_body import GetSchedulePostRequestBody
    from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone
    class TokenCredential:
        async def get_token(self,*scopes,**kwargs):
            return AccessToken(data['token'], int(time.time())+120)
    async def fetch():
        client = GraphServiceClient(credentials=TokenCredential(),scopes=['https://graph.microsoft.com/.default'])
        return await asyncio.wait_for(client.me.calendar.get_schedule.post(GetSchedulePostRequestBody(
            schedules=data['emails'], start_time=DateTimeTimeZone(date_time=data['start'],time_zone='UTC'),
            end_time=DateTimeTimeZone(date_time=data['stop'],time_zone='UTC'),availability_view_interval=15)),timeout=20)
    result = asyncio.run(fetch())
    if not result or len(result.value or []) != len(data['emails']) or any(s.error for s in result.value):
        raise ValueError('calendar access')
    return [(i.start.date_time,i.end.date_time) for s in result.value for i in (s.schedule_items or [])
            if str(i.status).lower().split('.')[-1] != 'free']


if __name__ == '__main__':
    try:
        result = busy(json.load(sys.stdin))
        print(json.dumps({'busy':result}))
    except Exception:
        # Do not return provider error bodies, tokens or calendar details.
        print(json.dumps({'error':'Calendar availability could not be read. Check organiser consent, panel sharing and SDK installation.'}))
        sys.exit(1)
