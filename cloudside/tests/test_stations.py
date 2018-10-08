from datetime import datetime
import os
from pkg_resources import resource_filename
import tempfile
import urllib
import warnings

import numpy
import pandas
import matplotlib.dates as mdates

from unittest import mock
import pytest
import numpy.testing as nptest
import pandas.util.testing as pdtest

from cloudside import station
from .helpers import get_test_file, raises


class FakeClass(object):
    def value(self):
        return 'item2'


@pytest.fixture
def basic_metar():
    teststring = (
        'METAR KPDX 010855Z 00000KT 10SM FEW010 OVC200 04/03 A3031 P0005 '
        'RMK AO2 SLP262 T00390028 53010 $'
    )
    return station.MetarParser(teststring, strict=False)


@pytest.fixture
def asos_metar():
    teststring = (
        '24229KPDX PDX20170108090014901/08/17 09:00:31  5-MIN KPDX 081700Z '
        '10023G35KT 7SM -FZRA OVC065 00/M01 A2968 250 96 -1400 080/23G35 RMK '
        'AO2 PK WND 10035/1654 P0005 I1000 T00001006'
    )
    return station.MetarParser(teststring, strict=False)


@pytest.fixture
def ts():
    return pandas.DatetimeIndex(start='2012-01-01', end='2012-02-28', freq='D')


@pytest.fixture
def fake_rain_data():
    tdelta = datetime(2001, 1, 1, 1, 5) - datetime(2001, 1, 1, 1, 0)
    start = datetime(2001, 1, 1, 12, 0)
    end = datetime(2001, 1, 1, 16, 0)
    daterange_num = mdates.drange(start, end, tdelta)
    daterange = mdates.num2date(daterange_num)

    rain_raw = [
        0.,  1.,  2.,  3.,  4.,  4.,  4.,  4.,  4.,  4.,  4.,  4.,
        0.,  0.,  0.,  0.,  0.,  5.,  5.,  5.,  5.,  5.,  5.,  5.,
        0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,
        1.,  2.,  3.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.,  0.
    ]

    return daterange, rain_raw


@pytest.fixture(params=['KPDX'])
def sta(request):
    with warnings.catch_warnings(), tempfile.TemporaryDirectory() as datadir:
        warnings.simplefilter('ignore')
        yield station.WeatherStation(request.param, city='Portland', state='OR',
                                     country='Cascadia', lat=999, lon=999,
                                     max_attempts=3, datadir=os.path.join(datadir, 'testtree'))


@pytest.fixture()
def known_statuses():
    return ['ok', 'bad', 'not there']


@pytest.fixture
def start():
    return datetime(2012, 1, 1)


@pytest.fixture
def end():
    return datetime(2012, 2, 28)


def test_MetarParser_datetime(asos_metar):
    assert asos_metar.datetime == datetime(2017, 1, 8, 9)


def test_MetarParser_asos_dict(asos_metar):
    result = asos_metar.asos_dict()
    expected = {
        'datetime': datetime(2017, 1, 8, 9),
        'raw_precipitation': 0.05,
        'temperature': 0.0,
        'dew_point': -0.6,
        'wind_speed': 23.0,
        'wind_direction': 100,
        'air_pressure': 250.0,
        'sky_cover': 1.0,
    }
    assert result == expected


@pytest.mark.parametrize(('datestring', 'expected'), [
    ('2012-6-4', datetime(2012, 6, 4)),
    ('September 23, 1982', datetime(1982, 9, 23)),
])
def test_parse_dates(datestring, expected):
    result = station._parse_date(datestring)
    assert result == expected


def test_date_asos():
    metarstring = '24229KPDX PDX20010101000010001/01/01 00:00:31 5-MIN KPDX'
    expected = datetime(2001, 1, 1, 0, 0)
    assert station._date_ASOS(metarstring) == expected


def test_append_val():
    x = FakeClass()
    expected = ['item1', 'item2', 'NA']
    testlist = ['item1']
    testlist = station._append_val(x, testlist)
    testlist = station._append_val(None, testlist)
    assert testlist == expected


def test_determine_reset_time(fake_rain_data):
    dates, precip = fake_rain_data
    result = station._determine_reset_time(dates, precip)
    expected = 0
    assert result == expected


def test_process_precip(fake_rain_data):
    dates, precip = fake_rain_data
    result = station._process_precip(dates, precip, 0)
    expected = numpy.array([
        0., 1., 1., 1., 1., 0., 0., 0., 0., 0., 0., 0., 0.,
        0., 0., 0., 0., 5., 0., 0., 0., 0., 0., 0., 0., 0.,
        0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 1., 1., 1.,
        0., 0., 0., 0., 0., 0., 0., 0., 0.
    ])
    nptest.assert_array_almost_equal(result, expected)


def test_process_sky_cover(basic_metar):
    testval = station._process_sky_cover(basic_metar)
    assert testval == 1.0000


def test_getAllStations():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        stations = station.getAllStations()
        assert isinstance(stations, dict)
        known_vals = ('BIST', 'Stykkisholmur', '', 'Iceland', '65-05N', '022-44W')
        assert stations['BIST'] == known_vals


def test_getStationByID():
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        sta = station.getStationByID('KPDX')
        assert sta.sta_id == 'KPDX'
        assert sta.city == 'Portland, Portland International Airport'
        assert sta.state == 'OR'
        assert sta.country == 'United States'
        assert sta.lat == '45-35-27N'
        assert sta.lon == '122-36-01W'


@pytest.mark.parametrize('attribute', [
    'sta_id', 'city', 'state', 'country', 'position',
    'name', 'wunderground', 'asos',
])
def test_WS_attributes(sta, attribute):
    assert hasattr(sta, attribute)


def test_WS_find_dir(sta):
    result = sta._find_dir('asos', 'raw')
    expected = os.path.join(sta.datadir, sta.sta_id, 'asos', 'raw')
    assert result == expected


@pytest.mark.xfail
def test_WS_find_file_wunder(sta, ts):
    wunder_result = sta._find_file(ts[0], 'wunderground', 'flat')
    wunder_expected = '{}_20120101.csv'.format(sta.sta_id)
    assert wunder_result == wunder_expected


def test_WS_find_file_asos(sta, ts):
    asos_result = sta._find_file(ts[0], 'asos', 'raw')
    asos_expected = '{}_201201.dat'.format(sta.sta_id)
    assert asos_result == asos_expected


def test_WS_set_cookies(sta):
    assert isinstance(sta.asos, urllib.request.OpenerDirector)
    assert isinstance(sta.wunderground, urllib.request.OpenerDirector)


@pytest.mark.xfail
def test_WS_url_by_date_wunder(sta, ts):
    wunder_result = sta._url_by_date(ts[0], src='wunderground')
    wunder_expected = (
        "http://www.wunderground.com/history/airport/{}"
        "/2012/01/01/DailyHistory.html?&&theprefset=SHOWMETAR"
        "&theprefvalue=1&format=1"
    ).format(sta.sta_id)
    assert wunder_result == wunder_expected


def test_WS_url_by_date_asos(sta, ts):
    asos_result = sta._url_by_date(ts[0], src='asos')
    asos_expected = (
        "ftp://ftp.ncdc.noaa.gov/pub/data/asos-fivemin"
        "/6401-2012/64010{}201201.dat"
    ).format(sta.sta_id)
    assert asos_result == asos_expected


@pytest.mark.xfail
def test_WS_make_data_file_wunder(sta, ts):
    wunder_result = sta._make_data_file(ts[0], 'wunderground', 'flat')
    wunder_expected = os.path.join(sta.datadir, sta.sta_id, 'wunderground',
                                   'flat', '{}_20120101.csv'.format(sta.sta_id))

    assert wunder_result == wunder_expected


def test_WS_make_data_file_asos(sta, ts):
    asos_result = sta._make_data_file(ts[0], 'asos', 'raw')
    asos_expected = os.path.join(sta.datadir, sta.sta_id, 'asos',
                                 'raw', '{}_201201.dat'.format(sta.sta_id))
    assert asos_result == asos_expected


@pytest.mark.parametrize(('fetcher_name', 'fetcher_key'), [
    ('getASOSData', 'asos'),
    ('getWundergroundData', 'wunderground'),
    ('getWunderground_NonAirportData', 'wunder_nonairport')
])
def test_WS_get_data_APIs(sta, fetcher_name, fetcher_key):
    startdate = '2011-03-01'
    enddate = '2012-01-01'
    filename = 'mock.csv'
    fetcher = getattr(sta, fetcher_name)
    with mock.patch.object(sta, '_get_data') as gd:
        fetcher(startdate, enddate, filename)
        gd.assert_called_once_with(startdate, enddate, fetcher_key, filename)


@pytest.mark.slow
@pytest.mark.parametrize('tstamp', ['2012-01-01', '1999-01-01'])
def test_fetch_data(sta, tstamp, known_statuses):
    tstamp = pandas.Timestamp(tstamp)
    status_asos = sta._fetch_data(tstamp, 1, src='asos')
    assert status_asos in known_statuses
    with raises(NotImplementedError):
        status_wund = sta._fetch_data(tstamp, 1, src='wunderground')


@pytest.mark.slow
def test_attempt_download(sta, known_statuses):
    good_ts = pandas.Timestamp('2012-01-01')
    bad_ts = pandas.Timestamp('1999-01-01')
    status_asos, attempt1 = sta._attempt_download(good_ts, src='asos')

    assert status_asos in known_statuses

    status_fail, attempt3 = sta._attempt_download(bad_ts, src='asos')
    assert status_fail == 'not there'

    assert attempt1 <= sta.max_attempts
    assert attempt3 == sta.max_attempts


@pytest.mark.slow
@pytest.mark.parametrize('src, datestr', [
    ('asos', '201201'),
    pytest.param('wunderground', '20120101', marks=pytest.mark.xfail),
])
def test_process_file(sta, src, datestr, known_statuses):
    tstamp = pandas.Timestamp('2012-01-01')
    filename, status = sta._process_file(tstamp, src)
    knownpath = os.path.join(sta.datadir, sta.sta_id, src, 'flat',
                             '{}_{}.csv'.format(sta.sta_id, datestr))

    assert filename == knownpath
    assert status in known_statuses


@pytest.mark.slow
@pytest.mark.parametrize('src, has_dwpt', [
    pytest.param('wunderground', True, marks=pytest.mark.xfail),
    ('asos', True),
])
def test_read_csv_XXXX(sta, ts, src, has_dwpt):
    data, status = sta._read_csv(ts[0], src)
    known_columns = ['DewPnt', 'Sta', 'Date', 'Precip', 'Temp',
                     'WindSpd', 'WindDir', 'AtmPress', 'SkyCover']
    if not has_dwpt:
        known_columns = known_columns[1:]
    assert sorted(data.reset_index().columns.tolist()) == sorted(known_columns)


@pytest.mark.slow
@pytest.mark.parametrize('gettername, has_dwpt', [
    pytest.param('getWundergroundData', True, marks=pytest.mark.xfail),
    ('getASOSData', True),
])
def test_getXXXData(sta, gettername, has_dwpt, start, end):
    known_columns = ['DewPnt', 'Sta', 'Date', 'Precip',
                     'Temp', 'WindSpd', 'WindDir',
                     'AtmPress', 'SkyCover']
    if not has_dwpt:
        known_columns = known_columns[1:]

    getter = getattr(sta, gettername)
    df = getter(start, end)
    assert sorted(df.reset_index().columns.tolist()) == sorted(known_columns)
    assert df.index.is_unique


@pytest.mark.slow
def test_getDataSaveFile(sta, start, end):
    sta._get_data(start, end, 'asos', 'testfile.csv')


@pytest.mark.parametrize(('src', 'error'), [
    ('asos', None),
    ('wunderground', NotImplementedError),
    ('wunder_nonairport', NotImplementedError),
])
@pytest.mark.parametrize('kwds', [
    {'filename': 'testfile.csv'},
    {'filenum': 1}
])
def test_loadCompData_asos(sta, src, kwds, error):
    with raises(error):
        sta.loadCompiledFile(src, **kwds)
