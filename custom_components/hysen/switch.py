"""Switch entities for Floureon thermostats."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.climate.const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)

from .const import (
    CONF_ENTITY_TYPE,
    CONF_TURN_OFF_MODE,
    CONF_TURN_ON_MODE,
    CONF_USE_EXTERNAL_TEMP,
    DEFAULT_ENTITY_TYPE,
    DEFAULT_TIMEOUT,
    DEFAULT_TURN_OFF_MODE,
    DEFAULT_TURN_ON_MODE,
    DEFAULT_USE_EXTERNAL_TEMP,
    DOMAIN,
    ENTITY_TYPE_SWITCH,
    MAX_TEMP,
    MIN_TEMP,
    POWER_OFF,
    POWER_ON,
    SENSOR_EXTERNAL,
    SENSOR_INTERNAL,
    TURN_OFF,
)
from .coordinator import FloureonConfigEntry, FloureonDataUpdateCoordinator
from .entity import FloureonEntity

PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=30)
        ),
        vol.Optional(
            CONF_USE_EXTERNAL_TEMP, default=DEFAULT_USE_EXTERNAL_TEMP
        ): cv.boolean,
        vol.Optional(CONF_TURN_OFF_MODE, default=DEFAULT_TURN_OFF_MODE): vol.Any(
            vol.In([MIN_TEMP, TURN_OFF]),
            vol.All(vol.Coerce(float), vol.Range(min=5, max=99)),
        ),
        vol.Optional(CONF_TURN_ON_MODE, default=DEFAULT_TURN_ON_MODE): vol.Any(
            vol.In([MAX_TEMP]),
            vol.All(vol.Coerce(float), vol.Range(min=5, max=99)),
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Import a legacy YAML switch platform."""
    data = dict(config)
    data[CONF_ENTITY_TYPE] = ENTITY_TYPE_SWITCH
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=data,
    )


@dataclass(frozen=True, kw_only=True)
class FloureonSwitchDescription(SwitchEntityDescription):
    """Describe a writable boolean flag on the thermostat."""

    status_field: str
    advanced: bool = True


CONFIG_SWITCHES: tuple[FloureonSwitchDescription, ...] = (
    FloureonSwitchDescription(
        key="child_lock",
        translation_key="child_lock",
        status_field="remote_lock",
        advanced=False,
    ),
    FloureonSwitchDescription(
        key="anti_freeze",
        translation_key="anti_freeze",
        status_field="anti_freeze",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FloureonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up config switches plus the optional legacy switch entity."""
    coordinator = entry.runtime_data
    entities: list = [
        FloureonConfigSwitch(coordinator, description)
        for description in CONFIG_SWITCHES
    ]
    if entry.options.get(CONF_ENTITY_TYPE, DEFAULT_ENTITY_TYPE) == ENTITY_TYPE_SWITCH:
        entities.append(FloureonSwitch(coordinator))
    async_add_entities(entities)


class FloureonConfigSwitch(FloureonEntity, SwitchEntity):
    """A writable boolean device setting."""

    entity_description: FloureonSwitchDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: FloureonDataUpdateCoordinator,
        description: FloureonSwitchDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.mac}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the last reported flag state."""
        value = getattr(self.coordinator.data, self.entity_description.status_field)
        return None if value is None else bool(value)

    async def _async_set(self, on: bool) -> None:
        client = self.coordinator.client
        if self.entity_description.advanced:
            call = partial(
                client.set_advanced,
                **{self.entity_description.status_field: on},
            )
        else:
            call = partial(client.set_remote_lock, on)
        await self.coordinator.async_command_with_status(call)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the flag."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the flag."""
        await self._async_set(False)


class FloureonSwitch(FloureonEntity, SwitchEntity):
    """Expose active heating as a simple on/off switch."""

    def __init__(self, coordinator: FloureonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = None
        options = coordinator.config_entry.options
        self._use_external_temp = options.get(
            CONF_USE_EXTERNAL_TEMP, DEFAULT_USE_EXTERNAL_TEMP
        )
        self._turn_off_mode = options.get(CONF_TURN_OFF_MODE, DEFAULT_TURN_OFF_MODE)
        self._turn_on_mode = options.get(CONF_TURN_ON_MODE, DEFAULT_TURN_ON_MODE)

    @property
    def is_on(self) -> bool:
        """Return whether the thermostat is actively heating/cooling."""
        data = self.coordinator.data
        return data.power and data.active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose temperatures relevant to switch automations."""
        data = self.coordinator.data
        return {
            "room_temperature": data.room_temp,
            "external_temperature": data.external_temp,
            "current_temperature": (
                data.external_temp if self._use_external_temp else data.room_temp
            ),
            "target_temperature": data.target_temp,
        }

    @property
    def _sensor(self) -> int:
        return SENSOR_EXTERNAL if self._use_external_temp else SENSOR_INTERNAL

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Power on and apply the configured on temperature."""
        await self.coordinator.async_command_with_status(
            lambda status: self.coordinator.client.set_switch_state(
                status,
                power=POWER_ON,
                temperature=(
                    status.max_temp or DEFAULT_MAX_TEMP
                    if self._turn_on_mode == MAX_TEMP
                    else float(self._turn_on_mode)
                ),
                schedule=status.loop_mode or 0,
                sensor=self._sensor,
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Power off or lower the set point, matching legacy semantics."""

        def command(status):
            if self._turn_off_mode == TURN_OFF:
                power = POWER_OFF
                temperature = None
            else:
                power = POWER_ON
                temperature = (
                    status.min_temp or DEFAULT_MIN_TEMP
                    if self._turn_off_mode == MIN_TEMP
                    else float(self._turn_off_mode)
                )
            return self.coordinator.client.set_switch_state(
                status,
                power=power,
                temperature=temperature,
                schedule=status.loop_mode or 0,
                sensor=self._sensor,
            )

        await self.coordinator.async_command_with_status(command)
