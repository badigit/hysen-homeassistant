"""Floureon thermostat integration."""

from __future__ import annotations

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_TIMEOUT,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .api import FloureonApiClient
from .const import DOMAIN, SERVICE_SET_TIME
from .coordinator import FloureonConfigEntry, FloureonDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-level services."""

    async def _async_set_time(call: ServiceCall) -> None:
        ent_reg = er.async_get(hass)
        entry_ids = {
            entity.config_entry_id
            for entity_id in call.data.get(ATTR_ENTITY_ID, [])
            if (entity := ent_reg.async_get(entity_id)) is not None
            and entity.config_entry_id is not None
        }
        for entry_id in entry_ids:
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is not None
                and entry.domain == DOMAIN
                and getattr(entry, "runtime_data", None) is not None
            ):
                await entry.runtime_data.async_set_time()

    hass.services.async_register(DOMAIN, SERVICE_SET_TIME, _async_set_time)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FloureonConfigEntry) -> bool:
    """Set up a thermostat from a config entry."""
    client = FloureonApiClient.from_config(
        host=entry.data[CONF_HOST],
        mac=entry.data[CONF_MAC],
        dev_type=entry.data[CONF_TYPE],
        timeout=entry.data[CONF_TIMEOUT],
    )
    coordinator = FloureonDataUpdateCoordinator(hass, entry, client)
    try:
        await coordinator.async_authenticate()
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await coordinator.async_set_time()
    except BaseException:
        await client.close()
        raise
    return True


async def async_reload_entry(hass: HomeAssistant, entry: FloureonConfigEntry) -> None:
    """Reload an entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FloureonConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.client.close()
    return True
