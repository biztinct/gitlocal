from odoo.tools import date_utils
from datetime import datetime
import pytz


def _softatt_localize(utc_time, timezone):
    old_tz  = pytz.timezone('UTC')
    new_tz  = pytz.timezone(timezone)
    dt      = old_tz.localize(utc_time).astimezone(new_tz).replace(tzinfo=None)
    return dt

def _softatt_get_span_dates(s, e, timezone):
    old_tz  = pytz.timezone(timezone)
    new_tz  = pytz.timezone('UTC')
    s       = datetime.combine(s, datetime.min.time())
    e       = datetime.combine(e, datetime.max.time())
    s, e    = old_tz.localize(s).astimezone(new_tz).replace(tzinfo=None), old_tz.localize(e).astimezone(new_tz).replace(tzinfo=None)
    return (s,e)

def _softatt_time_to_float(time_str):
    if ':' in time_str:
        hours, minutes = map(int, time_str.split(':'))
        return hours + (minutes / 60)
    return 0.0


setattr(date_utils, '_softatt_localize',        _softatt_localize)
setattr(date_utils, '_softatt_get_span_dates',  _softatt_get_span_dates)
setattr(date_utils, '_softatt_time_to_float',   _softatt_time_to_float)