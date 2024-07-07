"""The IntelliFire integration."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import voluptuous as vol
from typing import Any, Callable

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.helpers.event import async_track_state_change_event, EventStateChangedData
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, COORDINATOR_ENTRY

_LOGGER = logging.getLogger(__name__)


@dataclass
class SubscriptionEvent:
    remote_id: str
    cancel_subscription: ()
    action: Callable[[dict[any, any]], None]
    entities: [str]


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "uc/info"
    }
)
@callback
def ws_connect(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
) -> None:
    """Handle get info command."""

    _LOGGER.debug("Unfolded Circle connect request %s", msg)
    connection.send_message({
        "id": msg["id"],
        "type": "result",
        "success": True,
        "result": {
            "state": "CONNECTED",
            "cat": "DEVICE",
            "version": "1.0.0"
        }
    })


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "uc/event/unsubscribe",
    }
)
@callback
def ws_unsubscribe_event(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
) -> None:
    """Subscribe to incoming and outgoing events."""
    if hass.data[DOMAIN] is None:
        _LOGGER.error("Unfolded Circle integration not configured")
        connection.send_result(msg["id"])
        return

    coordinator: UCCoordinator = (next(iter(hass.data[DOMAIN].values()))).get(COORDINATOR_ENTRY, None)
    if coordinator is None:
        _LOGGER.error("Unfolded Circle coordinator not initialized")
        connection.send_result(msg["id"])
        return

    cancel_callback = connection.subscriptions.get(msg["id"], None)
    if cancel_callback is not None:
        cancel_callback()
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "uc/event/subscribed_entities",
        vol.Optional("data"): dict[any, any]
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

    connection.subscriptions[msg["id"]] = coordinator.subscribed_entities(
        action=forward_event,
        data=msg["data"]
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
        self._jobs: list[SubscriptionEvent] = []

        websocket_api.async_register_command(hass, ws_connect)
        websocket_api.async_register_command(hass, ws_subscribe_event)
        websocket_api.async_register_command(hass, ws_unsubscribe_event)
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

    def entities_state_change_event(self, event: Event[EventStateChangedData]) -> Any:
        entity_id = event.data["entity_id"]
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        _LOGGER.debug("Received notification to send to UC remote %s", event)
        for job in self._jobs:
            if entity_id in job.entities:
                job.action({
                    "data": {
                        "entity_id": entity_id,
                        "new_state": new_state,
                        "old_state": old_state #TODO : old state useful ?
                    }
                })



    def subscribed_entities(self, action: Callable[[dict[any, any]], None], data: dict[any, any]) -> Callable:
        """Adds and handle subscribed event"""
        entities = data.get("entities", [])
        #TODO handle remote instance to be able to handle subscriptions per device: self._jobs should be hashmap
        #TODO 2 : if multiple remotes subscribe to the same entity ids, we will have multiple jobs that will
        # receive the same notifications to send to the remote so the remote will receive them multiple times
        # => regroup all jobs into one and manage the full (unique) list of entities whatever the remote is
        # and send the notif to the right remote(s)
        task = async_track_state_change_event(self.hass, entities, self.entities_state_change_event)
        job: SubscriptionEvent = SubscriptionEvent(cancel_subscription=task, remote_id="",
                                                   action=action, entities=entities)
        self._jobs.append(job)

        def remove_listener() -> None:
            """Remove the listener."""
            try:
                _LOGGER.debug("Unfolded Circle unregister event")
                task()
            except Exception:
                pass
            self._jobs.remove(job)

        return remove_listener

    async def test_action_event(self, action: Callable[[dict[any, any]], None], entities: list[str]):
        while True:
            await asyncio.sleep(10)
            _LOGGER.debug("Unfolded Circle send event")
            action({"test": "send entities event", "event": entities})

    def update(self) -> dict[str, any]:
        """Update the internal state by querying the device."""
        data = {}

        return data
