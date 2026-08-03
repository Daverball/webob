import calendar
import datetime
from email.utils import formatdate, parsedate
import time

import pytest

from webob import datetime_utils


def test_UTC():
    """Test missing function in _UTC"""
    x = datetime_utils.UTC
    assert x.tzname(datetime.datetime.now()) == "UTC"
    assert x.dst(datetime.datetime.now()) == datetime.timedelta(0)
    assert x.utcoffset(datetime.datetime.now()) == datetime.timedelta(0)
    assert repr(x) == "UTC"


# Testing datetime_utils.parse_date.
# We need to verify the following scenarios:
#     * a nil submitted value
#     * a submitted value that cannot be parse into a date
#     * a valid RFC2822 date with and without timezone


class Uncooperative:
    def __str__(self):
        raise NotImplementedError


@pytest.mark.parametrize("invalid_date", [None, "Hi there", 1, "\xc3", Uncooperative()])
def test_parse_date_invalid(invalid_date):
    assert datetime_utils.parse_date(invalid_date) is None


@pytest.mark.parametrize(
    "valid_date, parsed_datetime",
    [
        (
            "Mon, 20 Nov 1995 19:12:08 -0500",
            datetime.datetime(1995, 11, 21, 0, 12, 8, tzinfo=datetime_utils.UTC),
        ),
        (
            "Mon, 20 Nov 1995 19:12:08",
            datetime.datetime(1995, 11, 20, 19, 12, 8, tzinfo=datetime_utils.UTC),
        ),
    ],
)
def test_parse_date_valid(valid_date, parsed_datetime):
    assert datetime_utils.parse_date(valid_date) == parsed_datetime


def test_serialize_date():
    """Testing datetime_utils.serialize_date
    We need to verify the following scenarios:
        * on py3, passing an binary date, return the same date but str
        * on py2, passing an unicode date, return the same date but str
        * passing a timedelta, return now plus the delta
        * passing an invalid object, should raise ValueError
    """
    from webob.util import text_

    ret = datetime_utils.serialize_date("Mon, 20 Nov 1995 19:12:08 GMT")
    assert isinstance(ret, str)
    assert ret == "Mon, 20 Nov 1995 19:12:08 GMT"
    ret = datetime_utils.serialize_date(text_("Mon, 20 Nov 1995 19:12:08 GMT"))
    assert isinstance(ret, str)
    assert ret == "Mon, 20 Nov 1995 19:12:08 GMT"
    dt = formatdate(
        calendar.timegm((datetime_utils.utcnow() + datetime.timedelta(1)).timetuple()),
        usegmt=True,
    )
    assert dt == datetime_utils.serialize_date(datetime.timedelta(1))
    with pytest.raises(ValueError):
        datetime_utils.serialize_date(None)


@pytest.mark.skipif(
    not hasattr(time, "tzset"),
    reason="time.tzset() (setting the process timezone) is not available",
)
def test_serialize_date_timedelta_is_utc_based(local_timezone):
    """A timedelta must be added to *UTC* now, not naive local time.

    ``serialize_date`` labels its output as GMT (``usegmt=True``) and builds the
    epoch with ``calendar.timegm`` (which treats the time tuple as UTC).  If the
    "now" the delta is added to is naive local time, the resulting header ends
    up off by the local UTC offset.  See
    https://github.com/Pylons/webob/issues/430.

    Running under a non-UTC timezone, the serialized zero-delta header must
    still match the current UTC time (within a small tolerance for the second
    boundary), regardless of the local offset.
    """
    # "America/New_York" is a non-UTC, DST-having offset
    with local_timezone("America/New_York"):
        before = datetime_utils.utcnow()
        header = datetime_utils.serialize_date(datetime.timedelta(seconds=0))
        after = datetime_utils.utcnow()

    header_ts = calendar.timegm(parsedate(header))
    assert header_ts is not None, header
    lower = calendar.timegm(before.timetuple()) - 1
    upper = calendar.timegm(after.timetuple()) + 1
    assert lower <= header_ts <= upper, (
        "Expires header %r (%d) is not within [%d, %d] of UTC now; "
        "it appears to use naive local time" % (header, header_ts, lower, upper)
    )


def test_parse_date_delta():
    """Testing datetime_utils.parse_date_delta
    We need to verify the following scenarios:
        * passing a nil value, should return nil
        * passing a value that fails the conversion to int, should call
          parse_date
    """
    assert datetime_utils.parse_date_delta(None) is None, (
        "Passing none value," "should return None"
    )
    ret = datetime_utils.parse_date_delta("Mon, 20 Nov 1995 19:12:08 -0500")
    assert ret == datetime.datetime(1995, 11, 21, 0, 12, 8, tzinfo=datetime_utils.UTC)
    WHEN = datetime.datetime(2011, 3, 16, 10, 10, 37, tzinfo=datetime_utils.UTC)
    with _NowRestorer(WHEN):
        ret = datetime_utils.parse_date_delta(1)
        assert ret == WHEN + datetime.timedelta(0, 1)


@pytest.mark.skipif(
    not hasattr(time, "tzset"),
    reason="time.tzset() (setting the process timezone) is not available",
)
def test_parse_date_delta_is_utc_based(local_timezone):
    """
    Delta seconds are resolved against UTC now, not naive local time. Reading
    back a delta-seconds header (such as ``Response.retry_after``) otherwise
    returns an instant off by the local UTC offset. See
    https://github.com/Pylons/webob/issues/430
    """
    # "America/New_York" is a non-UTC, DST-having offset
    with local_timezone("America/New_York"):
        # Note: a falsy value returns None, so the delta must be non-zero.
        delta = datetime.timedelta(seconds=1)
        before = datetime_utils.utcnow() + delta
        ret = datetime_utils.parse_date_delta(1)
        after = datetime_utils.utcnow() + delta

    assert before <= ret <= after, (
        "parse_date_delta(1) returned %r, outside [%r, %r]; it appears to use "
        "naive local time" % (ret, before, after)
    )


def test_serialize_date_delta():
    """Testing datetime_utils.serialize_date_delta
    We need to verify the following scenarios:
        * if we pass something that's not an int or float, it should delegate
          the task to serialize_date
    """
    assert datetime_utils.serialize_date_delta(1) == "1"
    assert datetime_utils.serialize_date_delta(1.5) == "1"
    ret = datetime_utils.serialize_date_delta("Mon, 20 Nov 1995 19:12:08 GMT")
    assert type(ret) is (str)
    assert ret == "Mon, 20 Nov 1995 19:12:08 GMT"


def test_timedelta_to_seconds():
    val = datetime.timedelta(86400)
    result = datetime_utils.timedelta_to_seconds(val)
    assert result == 7464960000


def test_utcnow():
    """utcnow() is a drop-in for the deprecated datetime.utcnow()."""
    before = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    result = datetime_utils.utcnow()
    after = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    assert result.tzinfo is None
    assert before <= result <= after


class _NowRestorer:
    def __init__(self, new_now):
        self._new_now = new_now
        self._old_now = None

    def __enter__(self):
        import webob.datetime_utils

        self._old_now = webob.datetime_utils._now
        webob.datetime_utils._now = lambda: self._new_now

    def __exit__(self, exc_type, exc_value, traceback):
        import webob.datetime_utils

        webob.datetime_utils._now = self._old_now
