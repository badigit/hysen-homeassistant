"""Temperature sensors for Floureon/Hysen thermostats."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FloureonConfigEntry, FloureonDataUpdateCoordinator
from .entity import FloureonEntity

PARALLEL_UPDATES = 1

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="floor_temperature",
        translation_key="floor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FloureonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose both probe readings for automations."""
    coordinator = entry.runtime_data
    async_add_entities(
        FloureonSensor(coordinator, description) for description in SENSORS
    )


class FloureonSensor(FloureonEntity, SensorEntity):
    """A single probe reading from the thermostat."""

    def __init__(
        self,
        coordinator: FloureonDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.mac}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the probe temperature."""
        data = self.coordinator.data
        if self.entity_description.key == "room_temperature":
            return data.room_temp
        return data.external_temp
