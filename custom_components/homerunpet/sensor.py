"""Sensor platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HomerunDataUpdateCoordinator
from .entity import HomerunBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HomerunSensorEntityDescription(SensorEntityDescription):
    """Description for Homerun sensor entities."""

    property_key: str = ""
    value_fn: Callable[[Dict[str, Any]], Any] = lambda p: None


AIR_QUALITY_MAP = {
    0: "优 (Excellent)",
    1: "良 (Good)",
    2: "中 (Moderate)",
    3: "差 (Poor)",
}

SENSOR_DESCRIPTIONS: List[HomerunSensorEntityDescription] = [
    HomerunSensorEntityDescription(
        key="pm25",
        name="PM2.5 颗粒物",
        property_key="pm25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda p: p.get("pm25"),
    ),
    HomerunSensorEntityDescription(
        key="tvoc",
        name="TVOC 有机挥发物",
        property_key="tvoc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        value_fn=lambda p: p.get("tvoc"),
    ),
    HomerunSensorEntityDescription(
        key="air_quality",
        name="空气质量",
        property_key="air_quality",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda p: AIR_QUALITY_MAP.get(p.get("air_quality"), p.get("air_quality")),
    ),
    HomerunSensorEntityDescription(
        key="current_temp",
        name="当前温度",
        property_key="current_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda p: p.get("current_temp"),
    ),
    HomerunSensorEntityDescription(
        key="current_humidity",
        name="当前湿度",
        property_key="current_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda p: p.get("current_humidity"),
    ),
    HomerunSensorEntityDescription(
        key="filter_life",
        name="滤芯剩余寿命",
        property_key="filter_life",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:air-filter",
        value_fn=lambda p: p.get("filter_life"),
    ),
    HomerunSensorEntityDescription(
        key="battery_percentage",
        name="电池电量",
        property_key="battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda p: p.get("battery_percentage"),
    ),
    HomerunSensorEntityDescription(
        key="toilet_remain_percentage",
        name="猫砂余量",
        property_key="toilet_remain_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:chart-donut",
        value_fn=lambda p: p.get("toilet_remain_percentage") or p.get("toilet_litter_percent"),
    ),
    HomerunSensorEntityDescription(
        key="countdown_left",
        name="倒计时剩余时间",
        property_key="countdown_left",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-sand",
        value_fn=lambda p: p.get("countdown_left"),
    ),
    HomerunSensorEntityDescription(
        key="status",
        name="工作状态",
        property_key="status",
        icon="mdi:state-machine",
        value_fn=lambda p: str(p.get("status", "idle")),
    ),
    HomerunSensorEntityDescription(
        key="current_task",
        name="当前任务",
        property_key="current_task",
        icon="mdi:clipboard-list",
        value_fn=lambda p: str(p.get("current_task", "")),
    ),
    HomerunSensorEntityDescription(
        key="motor_duration",
        name="电机运行时长",
        property_key="motor_duration",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:engine",
        value_fn=lambda p: p.get("motor_duration"),
    ),
    HomerunSensorEntityDescription(
        key="desiccant_info",
        name="干燥剂剩余天数",
        property_key="desiccant_info",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar-clock",
        value_fn=lambda p: (
            p["desiccant_info"].get("left_days")
            if isinstance(p.get("desiccant_info"), dict)
            else p.get("desiccant_info")
        ),
    ),
    HomerunSensorEntityDescription(
        key="exception_messages",
        name="异常报警",
        property_key="exception_messages",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement="条",
        icon="mdi:alert-circle",
        value_fn=lambda p: len(p.get("exception_messages") or []),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homerun sensor entities."""
    coordinator: HomerunDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[HomerunSensor] = []
    if coordinator.data:
        for serial, dev_data in coordinator.data.items():
            dev = dev_data.get("device", {})
            props = dev_data.get("properties", {})
            thing_model = coordinator.client.get_device_thing_model(dev)
            model_props = {
                p.get("identifier")
                for p in thing_model.get("properties", [])
                if isinstance(p, dict)
            }
            for desc in SENSOR_DESCRIPTIONS:
                # Strictly check if property is supported by device
                if desc.property_key in props or desc.property_key in model_props:
                    entities.append(HomerunSensor(coordinator, serial, desc))

    async_add_entities(entities)


class HomerunSensor(HomerunBaseEntity, SensorEntity):
    """Representation of a Homerun sensor."""

    entity_description: HomerunSensorEntityDescription

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
        description: HomerunSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.properties)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Expose the full active warning list for the exception sensor."""
        if self.entity_description.key != "exception_messages":
            return {}

        items = self.properties.get("exception_messages") or []
        messages = [
            str(item.get("detailsTopDes"))
            for item in items
            if isinstance(item, dict) and item.get("detailsTopDes")
        ]
        return {
            "messages": messages,
            "warnings": items,
        }
