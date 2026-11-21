"""Advanced settings exposed as number entities."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FloureonConfigEntry, FloureonDataUpdateCoordinator
from .entity import FloureonEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class FloureonNumberDescription(NumberEntityDescription):
    """Describe a writable advanced field."""

    status_field: str


NUMBERS: tuple[FloureonNumberDescription, ...] = (
    FloureonNumberDescription(
        key="hysteresis",
        translation_key="hysteresis",
        status_field="hysteresis",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=1,
        native_max_value=9,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    FloureonNumberDescription(
        key="sensor_calibration",
        translation_key="sensor_calibration",
        status_field="room_temp_adjustment",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=-9.9,
        native_max_value=9.9,
        native_step=0.1,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FloureonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose writable advanced settings."""
    coordinator = entry.runtime_data
    async_add_entities(
        FloureonNumber(coordinator, description) for description in NUMBERS
    )


class FloureonNumber(FloureonEntity, NumberEntity):
    """One writable field of the device advanced block."""

    entity_description: FloureonNumberDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: FloureonDataUpdateCoordinator,
        description: FloureonNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.mac}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the last reported value."""
        return getattr(self.coordinator.data, self.entity_description.status_field)

    async def async_set_native_value(self, value: float) -> None:
        """Merge the new value into the advanced block."""
        await self.coordinator.async_command(
            partial(
                self.coordinator.client.set_advanced,
                self.coordinator.data,
                **{self.entity_description.status_field: value},
            )
        )
