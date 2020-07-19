from datetime import datetime

import dateutil.tz
import dateutil.parser


class SafeLocalTimeZone(dateutil.tz.tzlocal):

    def _isdst(self, dt):
        # This method in tzlocal raises ValueError if dt is out of range (in
        # older versions of dateutil)
        # In such cases, just assume that dt is not DST.
        try:
            return super(SafeLocalTimeZone, self)._isdst(dt)
        except Exception:
            pass
        return False

    def _naive_is_dst(self, dt):
        # This method in tzlocal raises ValueError if dt is out of range (in
        # newer versions of dateutil)
        # In such cases, just assume that dt is not DST.
        try:
            return super(SafeLocalTimeZone, self)._naive_is_dst(dt)
        except Exception:
            pass
        return False


utc_tz = dateutil.tz.tzutc()
local_tz = SafeLocalTimeZone()
UNDEFINED_DATE = datetime(101, 1, 1, tzinfo=utc_tz)


def parse_iso8601(date_string, assume_utc=False, as_utc=True):
    if not date_string:
        return UNDEFINED_DATE
    dt = dateutil.parser.isoparse(date_string)
    tz = utc_tz if assume_utc else local_tz
    if not dt.tzinfo:  # timezone wasn't specified
        dt = dt.replace(tzinfo=tz)
    if as_utc and tz is utc_tz:
        return dt
    return dt.astimezone(utc_tz if as_utc else local_tz)


if __name__ == '__main__':
    import sys
    print(parse_iso8601(sys.argv[-1]))
