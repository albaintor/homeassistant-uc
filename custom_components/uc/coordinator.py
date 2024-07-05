"""The IntelliFire integration."""
from __future__ import annotations

import asyncio
import logging
import voluptuous as vol
from typing import Any, Callable

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, COORDINATOR_ENTRY

_LOGGER = logging.getLogger(__name__)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "uc/info",
    }
)
@callback
def ws_info(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
) -> None:
    """Handle get info command."""
    if hass.data[DOMAIN] is None:
        _LOGGER.error("Unfolded Circle integration not configured")
        return

    coordinator: UCCoordinator = (next(iter(hass.data[DOMAIN].values()))).get(COORDINATOR_ENTRY, None)
    if coordinator is None:
        _LOGGER.error("Unfolded Circle coordinator not initialized")

    connection.send_result(
        msg["id"],
        {
            "config": hass.config.as_dict()
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "uc/subscribe_entities",
    }
)
@callback
def ws_subscribe_event(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
) -> None:
    """Subscribe to incoming and outgoing events."""
    if hass.data[DOMAIN] is None:
        _LOGGER.error("Unfolded Circle integration not configured")
        return

    coordinator: UCCoordinator = (next(iter(hass.data[DOMAIN].values()))).get(COORDINATOR_ENTRY, None)
    if coordinator is None:
        _LOGGER.error("Unfolded Circle coordinator not initialized")

    @callback
    def forward_event(data: dict[any, any]) -> None:
        """Forward telegram to websocket subscription."""
        connection.send_event(
            msg["id"],
            data,
        )

    connection.subscriptions[msg["id"]] = coordinator.listen_event(
        action=forward_event,
        name="Entity update",
    )
    connection.send_result(msg["id"])


class UCCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for an Unfolded Circle Remote device."""
    # List of events to subscribe to the websocket
    subscribe_events: dict[str, bool]

    def __init__(self, hass: HomeAssistant, subscribed_entities: list[any] | None) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER
        )
        self.hass = hass
        self._entities = subscribed_entities
        self.data = {}
        self._jobs = []

        websocket_api.async_register_command(hass, ws_info)
        websocket_api.async_register_command(hass, ws_subscribe_event)
        _LOGGER.debug("Unfolded Circle websocket APIs registered")

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the latest data from the Unfolded Circle Remote."""
        _LOGGER.debug("Unfolded Circle coordinator update")
        try:
            self.data = await self.hass.async_add_executor_job(self.update)
            return self.data
        except Exception as ex:
            _LOGGER.error("Unfolded Circle coordinator error during update", ex)
            raise UpdateFailed(
                f"Error communicating with Unfolded Circle API {ex}"
            ) from ex

    def listen_event(self, action: Callable[[dict[any, any]], None], name: str) -> Callable:
        """Adds and handle subscribed event"""
        task = asyncio.create_task(self.test_action_event(action, name))
        self._jobs.append(task)

        def remove_listener() -> None:
            """Remove the listener."""
            try:
                _LOGGER.debug("Unfolded Circle unregister event")
                task.cancel()
            except Exception:
                pass
            self._jobs.remove(task)

        return remove_listener

    async def test_action_event(self, action: Callable[[dict[any, any]], None], name: str):
        while True:
            await asyncio.sleep(10)
            _LOGGER.debug("Unfolded Circle send event")
            action({"test": "test data", "event": name})

    def update(self) -> dict[str, any]:
        """Update the internal state by querying the device."""
        data = {}

        return data
