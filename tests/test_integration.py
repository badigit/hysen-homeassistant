"""End-to-end Home Assistant lifecycle tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.climate.const import PRESET_AWAY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from custom_components.hysen.const import DOMAIN, SERVICE_SET_TIME


async def test_setup_commands_reload_and_unload(
    hass: HomeAssistant,
    entry,
    client,
    device: MagicMock,
) -> None:
    """A config entry creates a working climate entity and unloads cleanly."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hysen.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.hall_thermostat")
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes["current_temperature"] == 25.0
    assert state.attributes["temperature"] == 23.0
    assert device.auth.await_count == 1
    assert device.get_full_status.await_count >= 2
    device.set_time.assert_awaited_once()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )
    device.set_mode.assert_any_await(0, 0, 1)
    device.set_temp.assert_any_await(22.5)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    device.set_power.assert_any_await(0, heating_cooling=0)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get(state.entity_id).state == "unavailable"
    device.aclose.assert_awaited_once()


async def test_reload_listener(hass: HomeAssistant, entry, client) -> None:
    """Changing options reloads the entry through the registered listener."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hysen.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "scan_interval": 60}
        )
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_climate_converts_native_celsius_to_fahrenheit(
    hass: HomeAssistant,
    entry,
    client,
) -> None:
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hysen.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.hall_thermostat")
    assert state is not None
    assert state.attributes["temperature_unit"] == "°F"
    assert abs(state.attributes["current_temperature"] - 77.0) < 0.6
    assert abs(state.attributes["temperature"] - 73.4) < 0.6
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_preset_mode_is_published_after_command(
    hass: HomeAssistant,
    entry,
    client,
) -> None:
    """The post-command refresh must not freeze a stale preset in the state."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hysen.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.hall_thermostat")
    assert state is not None

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(state.entity_id)
    assert state.attributes["preset_mode"] == PRESET_AWAY
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_set_time_service_targets_entry_entities(
    hass: HomeAssistant,
    entry,
    client,
    device: MagicMock,
) -> None:
    """The set_time service syncs the clock of the targeted entry."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hysen.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device.set_time.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TIME,
        {ATTR_ENTITY_ID: "climate.hall_thermostat"},
        blocking=True,
    )
    device.set_time.assert_awaited_once()


async def test_auxiliary_entities_read_and_write(
    hass: HomeAssistant,
    entry,
    client,
    device: MagicMock,
) -> None:
    """Probes, flags and advanced settings are exposed as entities."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hysen.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.hall_thermostat_room_temperature").state == "21.5"
    assert hass.states.get("sensor.hall_thermostat_floor_temperature").state == "25.0"
    assert hass.states.get("number.hall_thermostat_hysteresis").state == "2.0"
    assert hass.states.get("switch.hall_thermostat_child_lock").state == "off"
    assert hass.states.get("switch.hall_thermostat_anti_freeze").state == "on"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: "switch.hall_thermostat_child_lock"},
        blocking=True,
    )
    device.set_power.assert_any_await(1, remote_lock=1, heating_cooling=0)

    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: "number.hall_thermostat_hysteresis", "value": 3},
        blocking=True,
    )
    device.set_advanced.assert_awaited_once()
    assert device.set_advanced.await_args.args[3] == 3

    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: "switch.hall_thermostat_anti_freeze"},
        blocking=True,
    )
    assert device.set_advanced.await_count == 2
    assert device.set_advanced.await_args.args[7] == 0

    device.set_time.reset_mock()
    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.hall_thermostat_sync_clock"},
        blocking=True,
    )
    device.set_time.assert_awaited_once()
