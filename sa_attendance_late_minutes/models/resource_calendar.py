from    datetime    import datetime, timedelta
from    odoo        import _, api, fields, models
from    odoo.tools  import date_utils
import  logging

_logger = logging.getLogger(__name__)

class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'
    
    next_dayofweek      = fields.Char(compute='_compute_next_dayofweek', store=True)

    @api.depends('dayofweek', 'calendar_id')
    def _compute_next_dayofweek(self):
        for r in self:
            ndow = (int(r.dayofweek) + 1) % 7
            r.next_dayofweek = ndow

class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'
    
    overnight_shift     = fields.Boolean(default=False)

    def _get_next_day(self, dayofweek):
        ndow = (int(dayofweek) + 1) % 7
        next_dayofweek_id = None
        if self.overnight_shift == True:
            line = self.attendance_ids.search([('calendar_id.id','=',self.id), ('dayofweek','=',ndow), ('day_period','=','morning')])
            next_dayofweek_id = line
        return next_dayofweek_id        

    def _softatt_get_shift_start_and_end_bot(self, dayofweek, time):
        line = None
        str_time = time.strftime("%H:%M")
        time_float = date_utils._softatt_time_to_float(str_time)
        afm = False
        if not self.overnight_shift:
            line = self.attendance_ids.search([('hour_from','<',time_float), ('hour_to','>',time_float), ('dayofweek','=',dayofweek), ('calendar_id.id','=',self.id), ('day_period','!=','break')])
        else:
            line = self.attendance_ids.search([('hour_from','<',time_float), ('hour_to','>',time_float), ('dayofweek','=',dayofweek), ('day_period','=','afternoon'), ('calendar_id.id','=',self.id)])            
            if not line:
                previous_day = self.attendance_ids.search([('hour_to','>',time_float), ('next_dayofweek','=',dayofweek), ('day_period','=','afternoon'),('calendar_id.id','=',self.id)], limit=1)
                if previous_day:
                    next_day = self._get_next_day(previous_day.dayofweek)
                    if next_day and time_float < next_day.hour_to:
                        line = previous_day
                    if line:
                        afm = True
        if not line:
            _logger.info("--------No matching records-------")
            return None
        if not self.overnight_shift:
            shift_start_time    = line.hour_from
            shift_end_time      = line.hour_to 
            s, e = datetime.combine(time.date(), datetime.min.time()) + timedelta(hours=shift_start_time), datetime.combine(time.date(), datetime.min.time()) + timedelta(hours=shift_end_time)
        else:
            shift_start_time    = line.hour_from
            shift_end_time      = self._get_next_day(line.dayofweek).hour_to + 24
            if not afm:
                s, e = datetime.combine(time.date(), datetime.min.time()) + timedelta(hours=shift_start_time), datetime.combine(time.date(), datetime.min.time()) + timedelta(hours=shift_end_time)            
            else:
                s, e = datetime.combine(time.date(), datetime.min.time()) + timedelta(hours=shift_start_time), datetime.combine(time.date(), datetime.min.time()) + timedelta(hours=shift_end_time)            
                s, e = s - timedelta(days=1), e - timedelta(days=1)
        return [s, e, line]