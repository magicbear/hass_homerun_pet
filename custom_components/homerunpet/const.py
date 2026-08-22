"""Constants for the Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "homerunpet"
PLATFORMS: Final = [
    "sensor",
    "binary_sensor",
    "switch",
    "fan",
    "select",
    "button",
    "number",
    "camera",
]

# Cloud API constants extracted from APK
APP_ID: Final = "ddf3f28b7bda47bf83aafba9faf611bc"
APP_KEY: Final = "akbumgokcupum36vh0okfp7hkfz4m2m5"
APP_SECRET: Final = "8946644a4eb35e50f83f96dbb6403dab"
X_APPLICATION_ID: Final = "f73b2c3ca9031565e6d6b9337d762bd9"
MD5_SALT: Final = "#q&8UT6eRV79ol4*"
EZ_TOKEN_IV: Final = "sD1N5TCa9BOYywAp"

# Server hosts by region
REGION_CN: Final = "CN"
REGION_US: Final = "US"
REGION_EU: Final = "EU"

API_HOSTS: Final = {
    REGION_CN: "https://api.homerunsmart.com",
    REGION_US: "https://usapi.homerunsmart.com",
    REGION_EU: "https://euapi.homerunsmart.com",
}

DEFAULT_REGION: Final = REGION_CN
DEFAULT_SCAN_INTERVAL_SEC: Final = 30

# Configuration keys
CONF_ACCOUNT_TYPE: Final = "account_type"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_REGION: Final = "region"
CONF_AREA_CODE: Final = "area_code"
CONF_FAMILY_ID: Final = "family_id"
CONF_TOKEN: Final = "token"
CONF_USER_ID: Final = "user_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"

ACCOUNT_TYPE_PHONE: Final = "phone"
ACCOUNT_TYPE_EMAIL: Final = "email"

# Common Area Codes
AREA_CODES: Final = {
    "+86": "中国大陆 (+86)",
    "+1": "United States / Canada (+1)",
    "+44": "United Kingdom (+44)",
    "+81": "Japan (+81)",
    "+82": "South Korea (+82)",
    "+49": "Germany (+49)",
    "+33": "France (+33)",
    "+61": "Australia (+61)",
    "+852": "Hong Kong (+852)",
    "+886": "Taiwan (+886)",
    "+65": "Singapore (+65)",
    "+60": "Malaysia (+60)",
    "+66": "Thailand (+66)",
}

# Known Device Categories
CATEGORY_CAT_LITTER_BOX: Final = "CatLitterBox"
CATEGORY_FEEDER: Final = "FeedingTrough"
CATEGORY_FEEDER_ALT: Final = "Feeder"
CATEGORY_AIR_PURIFIER: Final = "AirPurifier"
CATEGORY_PET_DRYER: Final = "PetDryer"
CATEGORY_PET_HEATER: Final = "PetHeater"
CATEGORY_WATER_FOUNTAIN: Final = "WaterCamera"
CATEGORY_CAMERA: Final = "C01_Camera"
CATEGORY_FEED_RACK_CAMERA: Final = "FeedRackCamera"

# Known device model names
DEVICE_CATEGORIES_NAMES: Final = {
    CATEGORY_CAT_LITTER_BOX: "智能猫砂盆",
    CATEGORY_FEEDER: "智能喂食器",
    CATEGORY_FEEDER_ALT: "智能喂食器",
    CATEGORY_AIR_PURIFIER: "智能净味器/净化器",
    CATEGORY_PET_DRYER: "智能宠物烘干箱",
    CATEGORY_PET_HEATER: "智能电热窝/电热毯",
    CATEGORY_WATER_FOUNTAIN: "智能饮水机",
    CATEGORY_CAMERA: "宠物智能摄像机",
    CATEGORY_FEED_RACK_CAMERA: "智能粮架摄像机",
}
