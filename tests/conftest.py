import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.busminder.const import (
    DOMAIN,
    CONF_ROUTE_GROUP_UUID,
    CONF_ROUTE_GROUP_NAME,
    CONF_ROUTES,
    CONF_MONITORED_STOP_ID,
    CONF_MONITORED_STOP_NAME,
    CONF_MONITORED_STOP_LAT,
    CONF_MONITORED_STOP_LNG,
    CONF_OPERATOR_URL,
)

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def config_entry_data():
    return {
        CONF_OPERATOR_URL: "https://your-operator.com.au/live-tracking/your-school/",
        CONF_ROUTE_GROUP_UUID: "ba62fb89-d818-481c-8a95-08f48e331aa1",
        CONF_ROUTE_GROUP_NAME: "Springfield High - PM",
        CONF_ROUTES: [
            {"trip_id": 62869, "name": "3428 : Springfield High 3 | Springfield High to Dawson St/Burwood Hwy - PM", "route_number": "3428"},
            {"trip_id": 62867, "name": "3430 : Springfield High 2 | Springfield High to Boronia Station - PM", "route_number": "3430"},
        ],
        CONF_MONITORED_STOP_ID: 905346,
        CONF_MONITORED_STOP_NAME: "Springfield High - Bottom Area",
        CONF_MONITORED_STOP_LAT: -37.7877,
        CONF_MONITORED_STOP_LNG: 145.33912,
    }


@pytest.fixture
def mock_config_entry(config_entry_data):
    return MockConfigEntry(domain=DOMAIN, data=config_entry_data)
