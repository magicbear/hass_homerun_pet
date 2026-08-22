"""Select platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

import logging
from typing import Any, List

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HomerunDataUpdateCoordinator
from .entity import HomerunBaseEntity

_LOGGER = logging.getLogger(__name__)

# Modes for Pet Dryer and other appliances
DRYER_MODES = ["comfort", "quick", "summer", "winter", "ozone", "airbath"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homerun select entities."""
    coordinator: HomerunDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[HomerunModeSelect] = []
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

            # Only add mode select if device actually has operating mode support
            if categ in ("PetDryer",) or "mode" in props or "mode" in model_props or "comfort_mode_params" in model_props:
                entities.append(HomerunModeSelect(coordinator, serial))

    async_add_entities(entities)


class HomerunModeSelect(HomerunBaseEntity, SelectEntity):
    """Select entity for device operating mode."""

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, serial, "mode_select")
        self._attr_name = "工作模式"
        self._attr_icon = "mdi:tune"
        self._attr_options = DRYER_MODES

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option."""
        val = self.get_property("mode")
        if isinstance(val, int):
            if 0 <= val < len(DRYER_MODES):
                return DRYER_MODES[val]
            return str(val)
        if isinstance(val, str):
            return val.lower() if val.lower() in DRYER_MODES else val
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        val: Any = option
        if option in DRYER_MODES:
            # Check if device prefers integer index or string
            val = option

        await self.coordinator.client.async_set_device_properties(
            self.serial, {"mode": val}
        )
        self.properties["mode"] = val
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
