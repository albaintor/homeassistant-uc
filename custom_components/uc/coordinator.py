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
    client_id: str
    subscription_id: int
    cancel_subscription_callback: ()
    notification_callback: Callable[[dict[any, any]], None]
    entity_ids: [str]


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "uc/info"
    }
)
@callback
def ws_get_info(
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

    coordinator.subscribe_entities_events(connection, msg)
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
        self._subscriptions: list[SubscriptionEvent] = []

        websocket_api.async_register_command(hass, ws_get_info)
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

    def subscribe_entities_events(self, connection: websocket_api.ActiveConnection,
                                  msg: dict):
        """Adds and handle subscribed event"""
        subscription: SubscriptionEvent | None = None
        cancel_callback: Callable[[], None] | None = None

        @callback
        def forward_event(data: dict[any, any]) -> None:
            """Forward telegram to websocket subscription."""
            connection.send_event(
                msg["id"],
                data,
            )

        def entities_state_change_event(event: Event[EventStateChangedData]) -> Any:
            """Method called by HA when one of the subscribed entities have changed state."""
            # Note that this method as to be encapsulated in the subscribe_entities_events method in order to keep
            # a trace of the subscription variable because no context can be passed to the subscription registry
            entity_id = event.data["entity_id"]
            old_state = event.data["old_state"]
            new_state = event.data["new_state"]
            _LOGGER.debug("Received notification to send to UC remote %s", event)
            subscription.notification_callback({
                "data": {
                    "entity_id": entity_id,
                    "new_state": new_state,
                    "old_state": old_state  # TODO : old state useful ?
                }
            })

        def remove_listener() -> None:
            """Remove the listener."""
            try:
                _LOGGER.debug("Unfolded Circle unregister event %s for remote %s",
                              subscription_id, client_id)
                cancel_callback()
            except Exception:
                pass
            self._subscriptions.remove(subscription)

        # Create the new events subscription
        subscription_id = msg["id"]
        data = msg["data"]
        entities = data.get("entities", [])
        client_id = data.get("client_id", "")

        cancel_callback = async_track_state_change_event(self.hass, entities, entities_state_change_event)
        subscription = SubscriptionEvent(client_id=client_id,
                                         cancel_subscription_callback=cancel_callback,
                                         subscription_id=subscription_id,
                                         notification_callback=forward_event,
                                         entity_ids=entities)
        self._subscriptions.append(subscription)
        _LOGGER.debug("UC added subscription from remote %s for entity ids %s", client_id, entities)

        connection.subscriptions[subscription_id] = remove_listener

        return remove_listener

    def update(self) -> dict[str, any]:
        """Update the internal state by querying the device."""
        data = {}

        return data
