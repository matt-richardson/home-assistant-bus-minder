DOMAIN = "busminder"

# Config entry keys
CONF_OPERATOR_URL = "operator_url"
CONF_ROUTE_GROUP_UUID = "route_group_uuid"
CONF_ROUTE_GROUP_NAME = "route_group_name"
CONF_ROUTES = "routes"            # list of {trip_id, name, route_number}
CONF_MONITORED_STOP_ID = "monitored_stop_id"
CONF_MONITORED_STOP_NAME = "monitored_stop_name"
CONF_MONITORED_STOP_LAT = "monitored_stop_lat"
CONF_MONITORED_STOP_LNG = "monitored_stop_lng"

# API
MAPS_BASE_URL = "https://maps.busminder.com.au"
LIVE_BASE_URL = "https://live.busminder.com.au/signalr"
SIGNALR_HEADERS = {
    "Origin": "https://maps.busminder.com.au",
    "Referer": "https://maps.busminder.com.au/",
    "User-Agent": "Mozilla/5.0 (HomeAssistant BusMinder Integration)",
}
CONNECTION_DATA_ENC = "%5B%7B%22name%22%3A%22broadcasthub%22%7D%5D"
