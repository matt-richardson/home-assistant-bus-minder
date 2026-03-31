import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.busminder.const import (
    DOMAIN,
    CONF_ROUTE_GROUP_UUID,
    CONF_ROUTE_GROUP_NAME,
    CONF_ROUTES,
    CONF_OPERATOR_URL,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def config_entry_data():
    return {
        CONF_OPERATOR_URL: "https://example-buslines.com.au/live-tracking/springfield-high/",
        CONF_ROUTE_GROUP_UUID: "aaaaaaaa-0000-4000-8000-000000000001",
        CONF_ROUTE_GROUP_NAME: "Springfield High - PM",
        CONF_ROUTES: [
            {
                "trip_id": 10001,
                "name": "1001 : Springfield 1 | Springfield High to City - PM",
                "route_number": "1001",
                "uuid": "aaaaaaaa-0000-4000-8000-000000000001",
                "stop_id": 10001,
                "stop_name": "Springfield High - Main Gate",
                "stop_lat": -37.7877,
                "stop_lng": 145.33912,
            },
            {
                "trip_id": 10002,
                "name": "1002 : Springfield 2 | Springfield High to City Station - PM",
                "route_number": "1002",
                "uuid": "aaaaaaaa-0000-4000-8000-000000000001",
                "stop_id": 10003,
                "stop_name": "City Station",
                "stop_lat": -37.860,
                "stop_lng": 145.295,
            },
        ],
    }


@pytest.fixture
def mock_config_entry(config_entry_data):
    return MockConfigEntry(domain=DOMAIN, data=config_entry_data)
