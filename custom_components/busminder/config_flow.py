from __future__ import annotations

from typing import Any, Optional

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_OPERATOR_URL,
    CONF_ROUTE_GROUP_UUID,
    CONF_ROUTE_GROUP_NAME,
    CONF_ROUTES,
    CONF_MONITORED_STOP_ID,
    CONF_MONITORED_STOP_NAME,
    CONF_MONITORED_STOP_LAT,
    CONF_MONITORED_STOP_LNG,
)
from .models import RouteGroup
from .scraper import ScraperError, fetch_route_group_from_operator_url


class BusMinderConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._operator_url: str = ""
        self._route_group: Optional[RouteGroup] = None
        self._selected_trip_ids: list[int] = []

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_OPERATOR_URL].strip()
            try:
                async with aiohttp.ClientSession() as session:
                    group = await fetch_route_group_from_operator_url(session, url)
            except ScraperError as exc:
                msg = str(exc)
                if "Cannot connect" in msg:
                    errors["base"] = "cannot_connect"
                elif "No BusMinder" in msg:
                    errors["base"] = "no_busminder"
                else:
                    errors["base"] = "unknown"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(group.uuid)
                self._abort_if_unique_id_configured()

                self._operator_url = url
                self._route_group = group
                return await self.async_step_pick_routes()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_OPERATOR_URL): str,
            }),
            errors=errors,
        )

    async def async_step_pick_routes(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        assert self._route_group is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = user_input.get("trip_ids", [])
            if not selected:
                errors["base"] = "unknown"
            else:
                self._selected_trip_ids = [int(t) for t in selected]
                return await self.async_step_pick_stop()

        route_options = [
            selector.SelectOptionDict(
                value=str(r.trip_id),
                label=r.name,
            )
            for r in self._route_group.routes
        ]

        return self.async_show_form(
            step_id="pick_routes",
            data_schema=vol.Schema({
                vol.Required("trip_ids"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=route_options,
                        multiple=True,
                    )
                ),
            }),
            errors=errors,
        )

    async def async_step_pick_stop(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        assert self._route_group is not None
        assert self._selected_trip_ids

        if user_input is not None:
            stop_id = int(user_input["stop_id"])
            all_stops = self._route_group.all_stops()
            stop = next((s for s in all_stops if s.id == stop_id), None)
            if stop is None:
                return self.async_show_form(
                    step_id="pick_stop",
                    data_schema=self._stop_schema(),
                    errors={"base": "unknown"},
                )

            selected_routes = [
                {"trip_id": r.trip_id, "name": r.name, "route_number": r.route_number}
                for r in self._route_group.routes
                if r.trip_id in self._selected_trip_ids
            ]

            return self.async_create_entry(
                title=f"{self._route_group.name} ({', '.join(r['route_number'] for r in selected_routes)})",
                data={
                    CONF_OPERATOR_URL: self._operator_url,
                    CONF_ROUTE_GROUP_UUID: self._route_group.uuid,
                    CONF_ROUTE_GROUP_NAME: self._route_group.name,
                    CONF_ROUTES: selected_routes,
                    CONF_MONITORED_STOP_ID: stop.id,
                    CONF_MONITORED_STOP_NAME: stop.name,
                    CONF_MONITORED_STOP_LAT: stop.lat,
                    CONF_MONITORED_STOP_LNG: stop.lng,
                },
            )

        return self.async_show_form(
            step_id="pick_stop",
            data_schema=self._stop_schema(),
        )

    def _stop_schema(self) -> vol.Schema:
        assert self._route_group is not None
        selected_routes = [
            r for r in self._route_group.routes
            if r.trip_id in self._selected_trip_ids
        ]
        seen_ids: set[int] = set()
        stop_options = []
        for route in selected_routes:
            for stop in route.stops:
                if stop.id not in seen_ids:
                    seen_ids.add(stop.id)
                    stop_options.append(
                        selector.SelectOptionDict(
                            value=str(stop.id),
                            label=stop.name,
                        )
                    )
        stop_options.sort(key=lambda o: o["label"])

        return vol.Schema({
            vol.Required("stop_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=stop_options,
                    multiple=False,
                )
            ),
        })
