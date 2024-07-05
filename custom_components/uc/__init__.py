"""The panasonic_bluray remote and media player component."""
from __future__ import absolute_import

from .const import DOMAIN, SUBSCRIBED_ENTITIES_ENTRY, COORDINATOR_ENTRY
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .coordinator import UCCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)

# TODO add necessary entity types
PLATFORMS: list[Platform] = [

]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Unfolded Circle from a config entry."""

    entities_list: list[any] | None = entry.data.get(SUBSCRIBED_ENTITIES_ENTRY, None)

    _LOGGER.debug("Unfolded Circle initialization")
    coordinator = UCCoordinator(hass, entities_list)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR_ENTRY: coordinator
    }

    # Retrieve info from Remote
    # Get Basic Device Information
    # await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    # await zeroconf.async_get_async_instance(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        coordinator: UCCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR_ENTRY]
        # coordinator.api.?
    except Exception as ex:
        _LOGGER.error("Unfolded Circle async_unload_entry error", ex)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update Listener."""
    #TODO Should be ?
    #await async_unload_entry(hass, entry)
    #await async_setup_entry(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        coordinator: UCCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR_ENTRY]
        # coordinator.api.?
    except Exception as ex:
        _LOGGER.error("Panasonic device async_unload_entry error", ex)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update Listener."""
    # TODO Should be ?
    # await async_unload_entry(hass, entry)
    # await async_setup_entry(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)
