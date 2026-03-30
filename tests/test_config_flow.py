from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.busminder.const import DOMAIN
from custom_components.busminder.models import Stop, Route, RouteGroup
from custom_components.busminder.scraper import ScraperError

OPERATOR_URL = "https://your-operator.com.au/live-tracking/your-school/"

MOCK_ROUTE_GROUP = RouteGroup(
    uuid="ba62fb89-d818-481c-8a95-08f48e331aa1",
    name="Springfield High - PM",
    routes=[
        Route(
            trip_id=62869,
            name="3428 : Springfield High 3 | Springfield High to Dawson St/Burwood Hwy - PM",
            route_number="3428",
            colour="#08b8f0",
            stops=[
                Stop(id=905346, name="Springfield High - Bottom Area", lat=-37.7877, lng=145.33912, sequence=1),
                Stop(id=905347, name="St Peter Julian Eymard PS", lat=-37.792, lng=145.341, sequence=2),
            ],
        ),
        Route(
            trip_id=62867,
            name="3430 : Springfield High 2 | Springfield High to Boronia Station - PM",
            route_number="3430",
            colour="#20e30f",
            stops=[
                Stop(id=905346, name="Springfield High - Bottom Area", lat=-37.7877, lng=145.33912, sequence=1),
                Stop(id=905888, name="Boronia Station", lat=-37.860, lng=145.295, sequence=2),
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
        side_effect=ScraperError("Cannot connect"),
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
        result["flow_id"], user_input={"trip_ids": ["62869", "62867"]}
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
        result["flow_id"], user_input={"trip_ids": ["62869", "62867"]}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"stop_id": "905346"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["route_group_uuid"] == "ba62fb89-d818-481c-8a95-08f48e331aa1"
    assert result["data"]["monitored_stop_id"] == 905346
    assert len(result["data"]["routes"]) == 2
