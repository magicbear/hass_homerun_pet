"""Fan platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

import logging
import math
from typing import Any, List, Optional

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import CATEGORY_AIR_PURIFIER, DOMAIN
from .coordinator import HomerunDataUpdateCoordinator
from .entity import HomerunBaseEntity

_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (1, 5)  # Speeds 1 through 5
PRESET_MODES = ["auto", "manual", "sleep", "comfort", "strong"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homerun fan entities."""
    coordinator: HomerunDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[HomerunAirPurifierFan] = []
    if coordinator.data:
        for serial, dev_data in coordinator.data.items():
            dev = dev_data.get("device", {})
            props = dev_data.get("properties", {})
            categ = dev.get("categ", "")
            thing_model = coordinator.client.get_device_thing_model(dev)
            model_props = {
                p.get("identifier")
                for p in thing_model.get("properties", [])
                if isinstance(p, dict)
            }
            # Add fan entity only if device is an AirPurifier or has fan_speed in properties/model
            if categ == CATEGORY_AIR_PURIFIER or "fan_speed" in props or "fan_speed" in model_props:
                entities.append(HomerunAirPurifierFan(coordinator, serial))

    async_add_entities(entities)


class HomerunAirPurifierFan(HomerunBaseEntity, FanEntity):
    """Representation of a Homerun Air Purifier fan entity."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_preset_modes = PRESET_MODES
    _attr_speed_count = int_states_in_range(SPEED_RANGE)

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, serial, "fan")
        self._attr_name = "风机"
        self._attr_icon = "mdi:air-purifier"

    @property
    def is_on(self) -> Optional[bool]:
        """Return True if fan is on."""
        return bool(self.get_property("switch", False))

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        speed = self.get_property("fan_speed", 1)
        if not self.is_on or not speed:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, speed)

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode."""
        mode = self.get_property("mode")
        if isinstance(mode, int):
            mode_map = {0: "auto", 1: "manual", 2: "sleep", 3: "comfort", 4: "strong"}
            return mode_map.get(mode, "auto")
        if isinstance(mode, str):
            return mode.lower()
        return "auto"

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self.coordinator.client.async_set_device_properties(
            self.serial, {"switch": True, "fan_speed": speed}
        )
        self.properties["switch"] = True
        self.properties["fan_speed"] = speed
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        mode_val: Any = preset_mode
        mode_rev_map = {"auto": 0, "manual": 1, "sleep": 2, "comfort": 3, "strong": 4}
        if preset_mode in mode_rev_map:
            mode_val = mode_rev_map[preset_mode]

        await self.coordinator.client.async_set_device_properties(
            self.serial, {"switch": True, "mode": mode_val}
        )
        self.properties["switch"] = True
        self.properties["mode"] = mode_val
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        updates: dict[str, Any] = {"switch": True}
        if percentage is not None:
            updates["fan_speed"] = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        if preset_mode is not None:
            mode_rev_map = {"auto": 0, "manual": 1, "sleep": 2, "comfort": 3, "strong": 4}
            updates["mode"] = mode_rev_map.get(preset_mode, preset_mode)

        await self.coordinator.client.async_set_device_properties(self.serial, updates)
        self.properties.update(updates)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.client.async_set_device_properties(
            self.serial, {"switch": False}
        )
        self.properties["switch"] = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
