from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.busminder.const import DOMAIN, CONF_OPERATOR_URL, CONF_ROUTES
from custom_components.busminder.models import Stop, Route, RouteGroup
from custom_components.busminder.exceptions import BusMinderConnectionError

OPERATOR_URL = "https://example-buslines.com.au/live-tracking/springfield-high/"

MOCK_ROUTE_GROUP = RouteGroup(
    uuid="aaaaaaaa-0000-4000-8000-000000000001",
    name="Springfield High - PM",
    routes=[
        Route(
            trip_id=10001,
            name="1001 : Springfield 1 | Springfield High to City - PM",
            route_number="1001",
            colour="#08b8f0",
            stops=[
                Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=1),
                Stop(id=10002, name="Shelbyville Ave", lat=-37.792, lng=145.341, sequence=2),
            ],
        ),
        Route(
            trip_id=10002,
            name="1002 : Springfield 2 | Springfield High to City Station - PM",
            route_number="1002",
            colour="#20e30f",
            stops=[
                Stop(id=10001, name="Springfield High - Main Gate", lat=-37.7877, lng=145.33912, sequence=1),
                Stop(id=10003, name="City Station", lat=-37.860, lng=145.295, sequence=2),
            ],
        ),
    ],
)


@pytest.fixture
def mock_scraper():
    with patch(
        "custom_components.busminder.config_flow.fetch_route_group_from_operator_url",
        return_value=MOCK_ROUTE_GROUP,
    ) as mock:
        yield mock


async def test_step_user_shows_url_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user_success_proceeds_to_pick_routes(hass: HomeAssistant, mock_scraper):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"operator_url": OPERATOR_URL}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_routes"
    schema_keys = list(result["data_schema"].schema.keys())
    assert any("trip_ids" in str(k) for k in schema_keys)


async def test_step_user_cannot_connect(hass: HomeAssistant):
    with patch(
        "custom_components.busminder.config_flow.fetch_route_group_from_operator_url",
        side_effect=BusMinderConnectionError("Cannot connect"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"operator_url": OPERATOR_URL}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_step_pick_routes_proceeds_to_pick_stop(hass: HomeAssistant, mock_scraper):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"operator_url": OPERATOR_URL}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"trip_ids": ["10001", "10002"]}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_stop"


async def test_full_flow_creates_entry(hass: HomeAssistant, mock_scraper):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"operator_url": OPERATOR_URL}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"trip_ids": ["10001", "10002"]}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"stop_id": "10001"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["route_group_uuid"] == "aaaaaaaa-0000-4000-8000-000000000001"
    assert result["data"]["monitored_stop_id"] == 10001
    assert len(result["data"]["routes"]) == 2


async def test_options_flow_shows_url_form(hass: HomeAssistant, mock_config_entry):
    """Options flow opens with the URL form."""
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_options_flow_full_reconfiguration(hass: HomeAssistant, mock_config_entry, mock_scraper):
    """Options flow full 3-step sequence saves new config to entry.options."""
    async def empty_stream():
        return
        yield

    NEW_URL = "https://example-buslines.com.au/live-tracking/springfield-high-revised/"

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"operator_url": NEW_URL}
    )
    assert result["step_id"] == "pick_routes"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"trip_ids": ["10001"]}
    )
    assert result["step_id"] == "pick_stop"

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient2:
        MockClient2.return_value.stream = empty_stream
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"stop_id": "10001"}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_OPERATOR_URL] == NEW_URL
    assert len(mock_config_entry.options[CONF_ROUTES]) == 1


async def test_options_flow_cannot_connect(hass: HomeAssistant, mock_config_entry):
    """Options flow shows cannot_connect error on bad URL."""
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    with patch(
        "custom_components.busminder.config_flow.fetch_route_group_from_operator_url",
        side_effect=BusMinderConnectionError("Cannot connect"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"operator_url": "https://bad-url.example.com/"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_step_user_no_busminder_error(hass: HomeAssistant):
    """Initial flow shows no_busminder error when no iframe found."""
    with patch(
        "custom_components.busminder.config_flow.fetch_route_group_from_operator_url",
        side_effect=BusMinderConnectionError("No BusMinder iframe found"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"operator_url": OPERATOR_URL}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_busminder"}


async def test_step_user_unknown_error(hass: HomeAssistant):
    """Initial flow shows unknown error on unexpected exception."""
    with patch(
        "custom_components.busminder.config_flow.fetch_route_group_from_operator_url",
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"operator_url": OPERATOR_URL}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_step_pick_routes_empty_selection_shows_error(hass: HomeAssistant, mock_scraper):
    """Submitting no routes in pick_routes step shows unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"operator_url": OPERATOR_URL}
    )
    assert result["step_id"] == "pick_routes"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"trip_ids": []}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_routes"
    assert result["errors"] == {"base": "unknown"}


async def test_step_pick_stop_unknown_stop_id(hass: HomeAssistant, mock_scraper):
    """Submitting an invalid stop_id in pick_stop step shows unknown error."""
    from custom_components.busminder.config_flow import BusMinderConfigFlow
    from custom_components.busminder.models import Stop

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"operator_url": OPERATOR_URL}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"trip_ids": ["10001"]}
    )
    assert result["step_id"] == "pick_stop"
    # Bypass schema validation and call async_step_pick_stop directly with an invalid stop_id
    flow_id = result["flow_id"]
    flow = hass.config_entries.flow._progress[flow_id]
    result = await flow.async_step_pick_stop({"stop_id": "99999"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_stop"
    assert result["errors"] == {"base": "unknown"}


async def test_options_flow_unknown_error(hass: HomeAssistant, mock_config_entry):
    """Options flow handles unexpected errors with the 'unknown' error key."""
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    with patch(
        "custom_components.busminder.config_flow.fetch_route_group_from_operator_url",
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"operator_url": "https://example.com/"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_options_flow_no_busminder(hass: HomeAssistant, mock_config_entry):
    """Options flow shows no_busminder error when no iframe found."""
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    with patch(
        "custom_components.busminder.config_flow.fetch_route_group_from_operator_url",
        side_effect=BusMinderConnectionError("No BusMinder iframe found"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"operator_url": "https://example.com/"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_busminder"}


async def test_options_flow_empty_routes_shows_error(hass: HomeAssistant, mock_config_entry, mock_scraper):
    """Options flow shows unknown error when no routes are selected."""
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"operator_url": "https://example.com/"},
    )
    assert result["step_id"] == "pick_routes"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"trip_ids": []},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_routes"
    assert result["errors"] == {"base": "unknown"}


async def test_options_flow_unknown_stop_id(hass: HomeAssistant, mock_config_entry, mock_scraper):
    """Options flow shows unknown error when an invalid stop_id is submitted."""
    async def empty_stream():
        return
        yield

    with patch("custom_components.busminder.coordinator.SignalRClient") as MockClient:
        MockClient.return_value.stream = empty_stream
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"operator_url": "https://example.com/"},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"trip_ids": ["10001"]},
    )
    assert result["step_id"] == "pick_stop"

    # Bypass schema validation and call async_step_pick_stop directly with an invalid stop_id
    flow_id = result["flow_id"]
    flow = hass.config_entries.options._progress[flow_id]
    result = await flow.async_step_pick_stop({"stop_id": "99999"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_stop"
    assert result["errors"] == {"base": "unknown"}
