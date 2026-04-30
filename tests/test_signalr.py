import json
from unittest.mock import patch

import aiohttp
import pytest
from aioresponses import aioresponses as aioresponses_ctx

from custom_components.busminder.signalr import SignalRClient

ROUTE_UUID = "aaaaaaaa-0000-4000-8000-000000000001"
TOKEN = "abc123token=="
ENCODED_TOKEN = "abc123token%3D%3D"

NEGOTIATE_RESP = {"ConnectionToken": TOKEN, "ProtocolVersion": "2.0", "KeepAliveTimeout": 20.0}
START_RESP = '{ "Response": "started" }'
REGISTER_RESP = '{"I":"0"}'

GPS_MSG = json.dumps(
    {
        "M": [
            {
                "M": "gps",
                "A": [
                    json.dumps(
                        {
                            "TripId": 10001,
                            "BusId": 10042,
                            "Route": "nuseFuyavZHAJ?H@L?HBJ@J@",
                            "Reg": "0042",
                            "Poll": 0,
                            "LSID": 906802,
                            "LSDT": 1774845511180,
                        }
                    )
                ],
            }
        ]
    }
)


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
        token, keepalive_s = await client._negotiate()
    assert token == TOKEN
    assert keepalive_s == 20.0


async def test_parse_gps_event():
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        positions = client._parse_sse_payload(GPS_MSG)
    assert len(positions) == 1
    assert positions[0].trip_id == 10001
    assert positions[0].bus_reg == "0042"
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


async def test_start(mock_aiohttp):
    """_start() calls /start endpoint with the connection token."""
    import urllib.parse

    token = TOKEN
    qs = urllib.parse.urlencode(
        {
            "transport": "serverSentEvents",
            "clientProtocol": "2.0",
            "connectionToken": token,
            "connectionData": '[{"name":"broadcasthub"}]',
        }
    )
    mock_aiohttp.get(
        f"https://live.busminder.com.au/signalr/start?{qs}",
        payload={"Response": "started"},
    )
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        await client._start(token)  # should not raise


async def test_register(mock_aiohttp):
    """_register() POSTs to /send endpoint."""
    import urllib.parse

    token = TOKEN
    qs = urllib.parse.urlencode(
        {
            "transport": "serverSentEvents",
            "clientProtocol": "2.0",
            "connectionToken": token,
            "connectionData": '[{"name":"broadcasthub"}]',
        }
    )
    mock_aiohttp.post(
        f"https://live.busminder.com.au/signalr/send?{qs}",
        payload={"I": "0"},
    )
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        await client._register(token)  # should not raise


async def test_parse_invalid_json_returns_empty():
    """_parse_sse_payload returns empty list for invalid JSON."""
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        result = client._parse_sse_payload("not valid json{{")
    assert result == []


async def test_parse_gps_with_empty_args_ignored():
    """GPS messages with empty A array are skipped."""
    msg = json.dumps({"M": [{"M": "gps", "A": []}]})
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        result = client._parse_sse_payload(msg)
    assert result == []


async def test_parse_gps_bad_args_returns_empty():
    """GPS messages with malformed args (KeyError, TypeError) are skipped."""
    msg = json.dumps({"M": [{"M": "gps", "A": ["not_json_at_all"]}]})
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        result = client._parse_sse_payload(msg)
    assert result == []


async def test_stream_yields_positions(mock_aiohttp):
    """stream() negotiates, connects, and yields BusPosition objects."""
    import urllib.parse

    token = TOKEN

    # Negotiate
    neg_qs = urllib.parse.urlencode({"clientProtocol": "2.0", "connectionData": '[{"name":"broadcasthub"}]'})
    mock_aiohttp.get(
        f"https://live.busminder.com.au/signalr/negotiate?{neg_qs}",
        payload=NEGOTIATE_RESP,
    )

    # Connect — SSE stream: send "initialized" then a GPS message
    sse_lines = (f"data: initialized\n\n" f"data: {GPS_MSG}\n\n").encode()

    connect_qs = urllib.parse.urlencode(
        {
            "transport": "serverSentEvents",
            "clientProtocol": "2.0",
            "connectionToken": token,
            "connectionData": '[{"name":"broadcasthub"}]',
        }
    )
    mock_aiohttp.get(
        f"https://live.busminder.com.au/signalr/connect?{connect_qs}",
        body=sse_lines,
        content_type="text/event-stream",
    )

    # Start
    start_qs = connect_qs  # same params
    mock_aiohttp.get(
        f"https://live.busminder.com.au/signalr/start?{start_qs}",
        payload={"Response": "started"},
    )

    # Register (POST to /send)
    mock_aiohttp.post(
        f"https://live.busminder.com.au/signalr/send?{connect_qs}",
        payload={"I": "0"},
    )

    positions = []
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        with patch("custom_components.busminder.signalr.asyncio.sleep"):
            async for pos in client.stream():
                positions.append(pos)
                break  # only need one

    assert len(positions) == 1
    assert positions[0].trip_id == 10001


async def test_stream_calls_on_connected_after_init(mock_aiohttp):
    """stream() calls on_connected after the initialized handshake completes."""
    import urllib.parse

    token = TOKEN

    neg_qs = urllib.parse.urlencode({"clientProtocol": "2.0", "connectionData": '[{"name":"broadcasthub"}]'})
    mock_aiohttp.get(f"https://live.busminder.com.au/signalr/negotiate?{neg_qs}", payload=NEGOTIATE_RESP)

    sse_lines = (f"data: initialized\n\n" f"data: {GPS_MSG}\n\n").encode()
    connect_qs = urllib.parse.urlencode(
        {
            "transport": "serverSentEvents",
            "clientProtocol": "2.0",
            "connectionToken": token,
            "connectionData": '[{"name":"broadcasthub"}]',
        }
    )
    mock_aiohttp.get(
        f"https://live.busminder.com.au/signalr/connect?{connect_qs}",
        body=sse_lines,
        content_type="text/event-stream",
    )
    mock_aiohttp.get(f"https://live.busminder.com.au/signalr/start?{connect_qs}", payload={"Response": "started"})
    mock_aiohttp.post(f"https://live.busminder.com.au/signalr/send?{connect_qs}", payload={"I": "0"})

    connected_calls = []
    async with aiohttp.ClientSession() as session:
        client = SignalRClient(session, ROUTE_UUID)
        with patch("custom_components.busminder.signalr.asyncio.sleep"):
            async for _ in client.stream(on_connected=lambda: connected_calls.append(1)):
                break

    assert len(connected_calls) == 1
