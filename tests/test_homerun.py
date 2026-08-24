"""Standalone test suite for Homerunpet API and entity logic."""
from dataclasses import dataclass
import hashlib
import json
import os
import sys
from typing import Any, Optional
from unittest.mock import MagicMock

# Mock homeassistant modules for testing if homeassistant is not in local python env
for mod in [
    "voluptuous",
    "homeassistant",
    "homeassistant.core",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.selector",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.components.binary_sensor",
    "homeassistant.components.switch",
    "homeassistant.components.fan",
    "homeassistant.components.select",
    "homeassistant.components.number",
    "homeassistant.components.button",
    "homeassistant.util",
    "homeassistant.util.percentage",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


@dataclass(frozen=True)
class MockEntityDescription:
    key: str
    name: Optional[str] = None
    translation_key: Optional[str] = None
    icon: Optional[str] = None
    entity_category: Optional[Any] = None
    device_class: Optional[Any] = None
    state_class: Optional[Any] = None
    native_unit_of_measurement: Optional[str] = None
    native_min_value: Optional[float] = None
    native_max_value: Optional[float] = None
    native_step: Optional[float] = None
    mode: Optional[Any] = None


sys.modules["homeassistant.components.sensor"].SensorEntity = type("SensorEntity", (), {})
sys.modules["homeassistant.components.sensor"].SensorEntityDescription = MockEntityDescription
sys.modules["homeassistant.components.sensor"].SensorDeviceClass = MagicMock()
sys.modules["homeassistant.components.sensor"].SensorStateClass = MagicMock()

sys.modules["homeassistant.components.binary_sensor"].BinarySensorEntity = type("BinarySensorEntity", (), {})
sys.modules["homeassistant.components.binary_sensor"].BinarySensorEntityDescription = MockEntityDescription
sys.modules["homeassistant.components.binary_sensor"].BinarySensorDeviceClass = MagicMock()

sys.modules["homeassistant.components.switch"].SwitchEntity = type("SwitchEntity", (), {})
sys.modules["homeassistant.components.switch"].SwitchEntityDescription = MockEntityDescription
sys.modules["homeassistant.components.switch"].SwitchDeviceClass = MagicMock()

sys.modules["homeassistant.components.fan"].FanEntity = type("FanEntity", (), {})
sys.modules["homeassistant.components.fan"].FanEntityFeature = MagicMock()

sys.modules["homeassistant.components.select"].SelectEntity = type("SelectEntity", (), {})

sys.modules["homeassistant.components.number"].NumberEntity = type("NumberEntity", (), {})
sys.modules["homeassistant.components.number"].NumberEntityDescription = MockEntityDescription
sys.modules["homeassistant.components.number"].NumberMode = MagicMock()

sys.modules["homeassistant.components.button"].ButtonEntity = type("ButtonEntity", (), {})
sys.modules["homeassistant.components.button"].ButtonEntityDescription = MockEntityDescription
sys.modules["homeassistant.components.button"].ButtonDeviceClass = MagicMock()


class MockGeneric:
    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, *args, **kwargs):
        self.available = True


sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = MockGeneric
sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = MockGeneric

# Add custom_components to path
sys.path.insert(0, os.path.abspath("/data/clawdata/homeassistant-components/homerun_pat"))
sys.path.insert(0, os.path.abspath("/data/clawdata/homeassistant-components"))

from custom_components.homerunpet.const import (
    APP_ID,
    APP_KEY,
    APP_SECRET,
    CAMERA_CATEGORIES,
    DOMAIN,
    MD5_SALT,
    EZ_TOKEN_IV,
    CATEGORY_CAT_LITTER_BOX,
    CATEGORY_FEEDER,
    CATEGORY_AIR_PURIFIER,
    CATEGORY_CAMERA,
    SERVICE_GET_YS7_CREDENTIALS,
)
from custom_components.homerunpet.homerun_api import (
    HomerunApiClient,
    build_ys7_credentials,
    camera_serial_from_device,
    decrypt_ezviz_token,
    hash_password,
    is_camera_device,
    param_sign,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
import base64
from custom_components.homerunpet.switch import SWITCH_DESCRIPTIONS
from custom_components.homerunpet.sensor import SENSOR_DESCRIPTIONS
from custom_components.homerunpet.binary_sensor import BINARY_SENSOR_DESCRIPTIONS
from custom_components.homerunpet.number import NUMBER_DESCRIPTIONS
from custom_components.homerunpet.button import BUTTON_DESCRIPTIONS


def test_crypto_algorithms():
    """Verify password MD5 salt and param signing."""
    print("[1] Testing Password Hashing...")
    pwd = "MySecretPassword123"
    hashed = hash_password(pwd)
    assert len(hashed) == 20, f"Expected 20 chars, got {len(hashed)} ({hashed})"
    print(f"  Password '{pwd}' -> MD5 hash: {hashed}")

    print("[2] Testing Parameter Signature...")
    params = {
        "phone": "13800138000",
        "appId": APP_ID,
        "region": "Asia",
        "countryCode": "CN",
    }
    ts = "1700000000"
    sig = param_sign(params, ts)
    assert len(sig) == 64, f"Expected 64-char SHA256 hex, got {len(sig)}"
    print(f"  Generated signature: {sig}")

    token = "at.home-run-ezviz-test-token"
    padder = PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(token.encode()) + padder.finalize()
    encryptor = Cipher(
        algorithms.AES(APP_KEY.encode()), modes.CBC(EZ_TOKEN_IV.encode())
    ).encryptor()
    encrypted = base64.b64encode(
        encryptor.update(padded) + encryptor.finalize()
    ).decode()
    assert decrypt_ezviz_token(encrypted) == token
    assert decrypt_ezviz_token(token) == token


def test_thing_models_loading():
    """Verify thing models load from json."""
    print("[3] Testing Thing Models loading...")
    client = HomerunApiClient()
    models = client.thing_models
    assert len(models) > 0, "Thing models should be loaded from thing_models.json"
    print(f"  Loaded {len(models)} device product models successfully.")


def test_entity_descriptions():
    """Verify entity descriptions coverage."""
    print("[4] Testing Entity Descriptions...")

    test_props = {
        "switch": True,
        "child_lock": 1,
        "night_mode": False,
        "pm25": 18,
        "tvoc": 0.05,
        "air_quality": 0,
        "current_temp": 24.5,
        "current_humidity": 55,
        "filter_life": 92,
        "battery_percentage": 100,
        "toilet_remain_percentage": 85,
        "cat_nearby": True,
        "waste_bin_status": 1,
        "food_remain_status": 0,
        "lamp_brightness": 75,
        "portion": 3,
    }

    # Verify switches
    power_switch = next(d for d in SWITCH_DESCRIPTIONS if d.key == "power")
    assert power_switch.is_on_fn(test_props) is True

    child_lock_switch = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
    assert child_lock_switch.is_on_fn(test_props) is True

    # Verify sensors
    pm25_sensor = next(d for d in SENSOR_DESCRIPTIONS if d.key == "pm25")
    assert pm25_sensor.value_fn(test_props) == 18

    tvoc_sensor = next(d for d in SENSOR_DESCRIPTIONS if d.key == "tvoc")
    assert tvoc_sensor.value_fn(test_props) == 0.05

    filter_sensor = next(d for d in SENSOR_DESCRIPTIONS if d.key == "filter_life")
    assert filter_sensor.value_fn(test_props) == 92

    exception_sensor = next(d for d in SENSOR_DESCRIPTIONS if d.key == "exception_messages")
    assert exception_sensor.value_fn({"exception_messages": [{"detailsTopDes": "缺粮"}]}) == 1

    # Verify binary sensors
    cat_nearby = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "cat_nearby")
    assert cat_nearby.is_on_fn(test_props) is True

    waste_bin = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "waste_bin_full")
    assert waste_bin.is_on_fn(test_props) is True

    food_empty = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "food_empty")
    assert food_empty.is_on_fn(test_props) is False
    assert food_empty.is_on_fn({"food_remain_status": 1}) is True
    assert food_empty.is_on_fn({"food_remain_status": True}) is True

    # Verify numbers
    lamp_b = next(d for d in NUMBER_DESCRIPTIONS if d.key == "lamp_brightness")
    assert lamp_b.value_fn(test_props) == 75

    portion = next(d for d in NUMBER_DESCRIPTIONS if d.key == "portion")
    assert portion.value_fn(test_props) == 3

    # Verify buttons
    feed_btn = next(d for d in BUTTON_DESCRIPTIONS if d.key == "remote_feed")
    assert feed_btn.service_id == "remote_feed"

    clean_btn = next(d for d in BUTTON_DESCRIPTIONS if d.key == "remote_clean")
    assert clean_btn.service_id == "remote_clean"

    print("  All entity mapping checks passed!")


def test_ys7_credentials_helpers():
    """Verify Ezviz child serial extraction and on-demand credential payload."""
    print("[5] Testing YS7 credential helpers...")
    parent = "HRPARENT123"
    child = "C98765432"
    row = {
        "serial": parent,
        "device": {
            "deviceSerial": parent,
            "categ": CATEGORY_CAMERA,
            "cameraList": [{"deviceSerial": child, "channelNo": 1}],
        },
        "properties": {"camera_switch": True},
    }

    assert camera_serial_from_device(row, parent) == child
    assert camera_serial_from_device(row["device"], parent) == child
    assert camera_serial_from_device({"deviceSerial": parent}, parent) == parent
    assert is_camera_device(row["device"], row["properties"], camera_categories=CAMERA_CATEGORIES)

    payload = build_ys7_credentials(
        {
            "ysAppKey": "ys-app-key",
            "accessToken": "at.fresh-token",
            "ysDomain": "https://open.ys7.com",
        },
        device_serial=parent,
        device=row,
    )
    assert payload["ys_app_key"] == "ys-app-key"
    assert payload["access_token"] == "at.fresh-token"
    assert payload["camera_serial"] == child
    assert payload["ys_domain"] == "https://open.ys7.com"
    assert payload["device_serial"] == parent
    assert SERVICE_GET_YS7_CREDENTIALS == "get_ys7_credentials"
    print("  YS7 credential helper checks passed!")


if __name__ == "__main__":
    test_crypto_algorithms()
    test_thing_models_loading()
    test_entity_descriptions()
    test_ys7_credentials_helpers()
    print("\n🎉 ALL 5 TEST SUITES PASSED SUCCESSFULLY!")
