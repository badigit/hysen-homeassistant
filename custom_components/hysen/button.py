"""Button entities for Floureon/Hysen thermostats."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FloureonConfigEntry, FloureonDataUpdateCoordinator
from .entity import FloureonEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FloureonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose the clock-synchronisation action."""
    async_add_entities([FloureonSyncTimeButton(entry.runtime_data)])


class FloureonSyncTimeButton(FloureonEntity, ButtonEntity):
    """Push the current Home Assistant time to the thermostat."""

    _attr_translation_key = "sync_time"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FloureonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.mac}_sync_time"

    async def async_press(self) -> None:
        """Synchronise the device clock; failures surface to the caller."""
        await self.coordinator.async_sync_time()
