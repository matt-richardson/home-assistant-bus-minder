import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
from aioresponses import aioresponses as aioresponses_ctx

from custom_components.busminder.signalr import SignalRClient
from custom_components.busminder.models import BusPosition

ROUTE_UUID = "aaaaaaaa-0000-4000-8000-000000000001"
TOKEN = "abc123token=="
ENCODED_TOKEN = "abc123token%3D%3D"

NEGOTIATE_RESP = {"ConnectionToken": TOKEN, "ProtocolVersion": "2.0"}
START_RESP = '{ "Response": "started" }'
REGISTER_RESP = '{"I":"0"}'

GPS_MSG = json.dumps({
    "M": [{
        "M": "gps",
        "A": [json.dumps({
            "TripId": 10001,
            "BusId": 11528,
            "Route": "nuseFuyavZHAJ?H@L?HBJ@J@",
            "Reg": "1528",
            "Poll": 0,
            "LSID": 906802,
            "LSDT": 1774845511180,
        })]
    }]
})


@pytest.fixture
def mock_aiohttp():
    with aioresponses_ctx() as m:
        yield m


async def test_negotiate(mock_aiohttp):
    import urllib.parse
    qs = urllib.parse.urlencode({"clientProtocol": "2.0", "connectionData": '[{"name":"broadcasthub"}]'})
    mock_aiohttp.get(
        f"https://live.busminder.com.au/signalr/negotiate?{qs}",
        payload=NEGOTIATE_RESP,
    )
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        token = await client._negotiate()
    assert token == TOKEN


async def test_parse_gps_event():
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        positions = client._parse_sse_payload(GPS_MSG)
    assert len(positions) == 1
    assert positions[0].trip_id == 10001
    assert positions[0].bus_reg == "1528"
    assert positions[0].last_stop_id == 906802


async def test_parse_empty_payload():
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        assert client._parse_sse_payload("{}") == []
        assert client._parse_sse_payload("") == []


async def test_parse_non_gps_method_ignored():
    msg = json.dumps({"M": [{"M": "someOtherMethod", "A": []}]})
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        assert client._parse_sse_payload(msg) == []
