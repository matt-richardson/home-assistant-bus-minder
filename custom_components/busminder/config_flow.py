from __future__ import annotations

from typing import Any, Optional

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_OPERATOR_URL, CONF_ROUTE_GROUP_NAME, CONF_ROUTE_GROUP_UUID, CONF_ROUTES, DOMAIN
from .exceptions import BusMinderConnectionError
from .models import Route, RouteGroup
from .scraper import fetch_route_group_from_operator_url


class BusMinderConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]  # pylint: disable=abstract-method
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: "ConfigEntry") -> "BusMinderOptionsFlow":
        return BusMinderOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._operator_url: str = ""
        self._route_group: Optional[RouteGroup] = None
        self._selected_trip_ids: list[int] = []
        self._route_queue: list[Route] = []
        self._confirmed_routes: list[dict] = []
        self._last_confirmed_stop_id: Optional[int] = None

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_OPERATOR_URL].strip()
            try:
                session = async_get_clientsession(self.hass)
                group = await fetch_route_group_from_operator_url(session, url)
            except BusMinderConnectionError as exc:
                msg = str(exc)
                if "Cannot connect" in msg:
                    errors["base"] = "cannot_connect"
                elif "No BusMinder" in msg:
                    errors["base"] = "no_busminder"
                else:
                    errors["base"] = "unknown"
            except Exception:  # pylint: disable=broad-exception-caught
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(group.uuid)
                self._abort_if_unique_id_configured()

                self._operator_url = url
                self._route_group = group
                return await self.async_step_pick_routes()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OPERATOR_URL): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_routes(self, user_input: Optional[dict[str, Any]] = None) -> ConfigFlowResult:
        assert self._route_group is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get("trip_ids", [])
            if not selected:
                errors["base"] = "unknown"
            else:
                self._selected_trip_ids = [int(t) for t in selected]
                self._route_queue = sorted(
                    [r for r in self._route_group.routes if r.trip_id in self._selected_trip_ids],
                    key=lambda r: r.route_number,
                )
                self._confirmed_routes = []
                self._last_confirmed_stop_id = None
                return await self.async_step_pick_stop()

        route_options = [
            selector.SelectOptionDict(value=str(r.trip_id), label=r.name)
            for r in sorted(self._route_group.routes, key=lambda r: r.route_number)
        ]

        return self.async_show_form(
            step_id="pick_routes",
            data_schema=vol.Schema(
                {
                    vol.Required("trip_ids"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=route_options, multiple=True)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_pick_stop(self, user_input: Optional[dict[str, Any]] = None) -> ConfigFlowResult:
        assert self._route_group is not None
        assert self._route_queue

        current_route = self._route_queue[0]

        if user_input is not None:
            stop_id = int(user_input["stop_id"])
            stop = next((s for s in current_route.stops if s.id == stop_id), None)
            if stop is None:
                return self.async_show_form(
                    step_id="pick_stop",
                    data_schema=self._stop_schema(current_route),
                    description_placeholders={"route_name": current_route.name},
                    errors={"base": "unknown"},
                )

            self._confirmed_routes.append(
                {
                    "trip_id": current_route.trip_id,
                    "name": current_route.name,
                    "route_number": current_route.route_number,
                    "uuid": current_route.uuid,
                    "stop_id": stop.id,
                    "stop_name": stop.name,
                    "stop_lat": stop.lat,
                    "stop_lng": stop.lng,
                }
            )
            self._last_confirmed_stop_id = stop.id
            self._route_queue.pop(0)

            if self._route_queue:
                return await self.async_step_pick_stop()

            return self.async_create_entry(
                title=f"{self._route_group.name} ({', '.join(r['route_number'] for r in self._confirmed_routes)})",
                data={
                    CONF_OPERATOR_URL: self._operator_url,
                    CONF_ROUTE_GROUP_UUID: self._route_group.uuid,
                    CONF_ROUTE_GROUP_NAME: self._route_group.name,
                    CONF_ROUTES: self._confirmed_routes,
                },
            )

        return self.async_show_form(
            step_id="pick_stop",
            data_schema=self._stop_schema(current_route),
            description_placeholders={"route_name": current_route.name},
        )

    def _stop_schema(self, route: Route) -> vol.Schema:
        stop_options = sorted(
            [selector.SelectOptionDict(value=str(s.id), label=s.name) for s in route.stops],
            key=lambda o: o["label"],
        )
        stop_ids_in_route = {s.id for s in route.stops}
        default = (
            str(self._last_confirmed_stop_id) if self._last_confirmed_stop_id in stop_ids_in_route else vol.UNDEFINED
        )
        return vol.Schema(
            {
                vol.Required("stop_id", default=default): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=stop_options, multiple=False)
                ),
            }
        )


class BusMinderOptionsFlow(OptionsFlow):
    """Options flow — re-run the full config sequence to reconfigure."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        current = {**entry.data, **entry.options}
        self._operator_url: str = current.get(CONF_OPERATOR_URL, "")
        self._route_group: Optional[RouteGroup] = None
        self._selected_trip_ids: list[int] = [r["trip_id"] for r in current.get(CONF_ROUTES, [])]
        self._route_queue: list[Route] = []
        self._confirmed_routes: list[dict] = []
        # Per-route saved stops so each route defaults to its own previously chosen stop on re-open
        self._saved_stops: dict[int, int] = {r["trip_id"]: r["stop_id"] for r in current.get(CONF_ROUTES, [])}
        self._last_confirmed_stop_id: Optional[int] = None

    async def async_step_init(self, _user_input: Optional[dict[str, Any]] = None) -> ConfigFlowResult:
        return await self.async_step_user()

    async def async_step_user(self, user_input: Optional[dict[str, Any]] = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_OPERATOR_URL].strip()
            try:
                session = async_get_clientsession(self.hass)
                group = await fetch_route_group_from_operator_url(session, url)
            except BusMinderConnectionError as exc:
                msg = str(exc)
                if "Cannot connect" in msg:
                    errors["base"] = "cannot_connect"
                elif "No BusMinder" in msg:
                    errors["base"] = "no_busminder"
                else:
                    errors["base"] = "unknown"
            except Exception:  # pylint: disable=broad-exception-caught
                errors["base"] = "unknown"
            else:
                self._operator_url = url
                self._route_group = group
                return await self.async_step_pick_routes()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OPERATOR_URL, default=self._operator_url): str,
                }
            ),
            errors=errors,
        )

    async def async_step_pick_routes(self, user_input: Optional[dict[str, Any]] = None) -> ConfigFlowResult:
        assert self._route_group is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get("trip_ids", [])
            if not selected:
                errors["base"] = "unknown"
            else:
                self._selected_trip_ids = [int(t) for t in selected]
                self._route_queue = sorted(
                    [r for r in self._route_group.routes if r.trip_id in self._selected_trip_ids],
                    key=lambda r: r.route_number,
                )
                self._confirmed_routes = []
                return await self.async_step_pick_stop()

        route_options = [
            selector.SelectOptionDict(value=str(r.trip_id), label=r.name)
            for r in sorted(self._route_group.routes, key=lambda r: r.route_number)
        ]
        current_selection = [str(t) for t in self._selected_trip_ids]

        return self.async_show_form(
            step_id="pick_routes",
            data_schema=vol.Schema(
                {
                    vol.Required("trip_ids", default=current_selection): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=route_options, multiple=True)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_pick_stop(self, user_input: Optional[dict[str, Any]] = None) -> ConfigFlowResult:
        assert self._route_group is not None
        assert self._route_queue

        current_route = self._route_queue[0]

        if user_input is not None:
            stop_id = int(user_input["stop_id"])
            stop = next((s for s in current_route.stops if s.id == stop_id), None)
            if stop is None:
                return self.async_show_form(
                    step_id="pick_stop",
                    data_schema=self._stop_schema(current_route),
                    description_placeholders={"route_name": current_route.name},
                    errors={"base": "unknown"},
                )

            self._confirmed_routes.append(
                {
                    "trip_id": current_route.trip_id,
                    "name": current_route.name,
                    "route_number": current_route.route_number,
                    "uuid": current_route.uuid,
                    "stop_id": stop.id,
                    "stop_name": stop.name,
                    "stop_lat": stop.lat,
                    "stop_lng": stop.lng,
                }
            )
            self._last_confirmed_stop_id = stop.id
            self._route_queue.pop(0)

            if self._route_queue:
                return await self.async_step_pick_stop()

            return self.async_create_entry(
                title="",
                data={
                    CONF_OPERATOR_URL: self._operator_url,
                    CONF_ROUTE_GROUP_UUID: self._route_group.uuid,
                    CONF_ROUTE_GROUP_NAME: self._route_group.name,
                    CONF_ROUTES: self._confirmed_routes,
                },
            )

        return self.async_show_form(
            step_id="pick_stop",
            data_schema=self._stop_schema(current_route),
            description_placeholders={"route_name": current_route.name},
        )

    def _stop_schema(self, route: Route) -> vol.Schema:
        stop_options = sorted(
            [selector.SelectOptionDict(value=str(s.id), label=s.name) for s in route.stops],
            key=lambda o: o["label"],
        )
        stop_ids_in_route = {s.id for s in route.stops}
        # Prefer the previously saved stop for this specific route; fall back to last confirmed
        default_id = self._saved_stops.get(route.trip_id, self._last_confirmed_stop_id)
        default = str(default_id) if default_id in stop_ids_in_route else vol.UNDEFINED
        return vol.Schema(
            {
                vol.Required("stop_id", default=default): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=stop_options, multiple=False)
                ),
            }
        )
