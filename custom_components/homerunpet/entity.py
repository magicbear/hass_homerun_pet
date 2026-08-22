"""Base entity for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_CATEGORIES_NAMES, DOMAIN
from .coordinator import HomerunDataUpdateCoordinator


class HomerunBaseEntity(CoordinatorEntity[HomerunDataUpdateCoordinator]):
    """Defines a base Homerun entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.serial = serial
        self.entity_key = entity_key
        self._attr_unique_id = f"{serial}_{entity_key}"

    @property
    def device_raw_data(self) -> Dict[str, Any]:
        """Get the full device raw data dict from coordinator."""
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get(self.serial, {})

    @property
    def device_info_dict(self) -> Dict[str, Any]:
        """Get device list metadata."""
        return self.device_raw_data.get("device", {})

    @property
    def properties(self) -> Dict[str, Any]:
        """Get telemetry properties."""
        return self.device_raw_data.get("properties", {})

    def get_property(self, key: str, default: Any = None) -> Any:
        """Get a specific property value."""
        return self.properties.get(key, default)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available or not self.device_raw_data:
            return False

        # In dev_info, status or online field may represent connection
        dev = self.device_info_dict
        if "online" in dev:
            return bool(dev["online"])
        if "status" in dev and dev["status"] == 0:
            # 0 might mean offline in some models, or online in others
            pass
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        dev = self.device_info_dict
        device_name = dev.get("deviceName") or dev.get("deviceNickName") or f"霍曼设备 {self.serial[-6:]}"
        categ = dev.get("categ", "")
        model_name = DEVICE_CATEGORIES_NAMES.get(categ, categ or "霍曼智能设备")
        mac = dev.get("mac")
        sw_version = dev.get("firmwareVersion") or dev.get("version")

        connections = set()
        if mac:
            connections.add(("mac", mac))

        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            connections=connections,
            name=device_name,
            manufacturer="Homerunpet (霍曼)",
            model=model_name,
            sw_version=sw_version,
        )
