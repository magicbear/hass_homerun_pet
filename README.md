# Homerunpet (霍曼宠物) Home Assistant Integration

[English](README.md) | [中文说明](README_zh.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, full-featured Home Assistant custom component for **Homerunpet (霍曼宠物)** smart pet devices. Developed through reverse engineering of the official Homerunpet Android application protocol.

---

## 🌟 Supported Devices & Entity Features

| Device Category | Models | Supported Entities & Controls |
| :--- | :--- | :--- |
| **Smart Feeding Trough & Camera<br>(智能猫食盘 / 智能粮架摄像机)** | `FeedRackCamera`, `FeedingTrough`, `a90111a1`, `a90112a1`, etc. | - **Camera**: Real-time HLS HD live stream (`m3u8`), WebRTC support, on/off control<br>- **Switches**: Microphone pickup, OSD timestamp, AI pet bounding box, motion/presence detection, feed behavior recording<br>- **Numbers**: Speaker volume slider (0–100%) |
| **Smart Cat Litter Box<br>(智能猫砂盆)** | `A9015201`, `A9015202`, `B9015201`, `B9015202`, `a90128a1`, etc. | - **Camera**: Live stream support for camera-equipped models<br>- **Sensors**: Litter level percentage, work status, task duration<br>- **Binary Sensors**: Cat nearby motion, cat inside occupancy, waste bin full alert, litter low alert<br>- **Switches**: Auto clean, auto refill, auto deodorizer cover, kitten mode, child lock, night mode<br>- **Buttons**: Instant scoop / clean, sand leveling, instant sand refill, waste bin reset |
| **Smart Pet Feeder<br>(智能喂食器)** | `A9016101`, `A9016102`, `B9016101`, `B9016102`, `9015601`, etc. | - **Sensors**: Battery percentage, next feed plan<br>- **Binary Sensors**: Food empty warning, outlet blockage warning, power connected, battery present<br>- **Numbers**: Portion size setting (1–10 portions)<br>- **Buttons**: Instant remote feed<br>- **Switches**: Child lock, night mode, feed detection radar |
| **Smart Air Purifier / Deodorizer<br>(智能净味器 / 净化器)** | `A9014901`, `B9014901`, `D0773AD2`, etc. | - **Fan**: Power, speed percentage (1–5 gears), preset modes (`auto`, `manual`, `sleep`, `comfort`, `strong`)<br>- **Sensors**: PM2.5 (`µg/m³`), TVOC (`mg/m³`), Air Quality Level, Filter Life Percentage<br>- **Switches**: Child lock, mute mode<br>- **Buttons**: Reset filter life |
| **Smart Pet Dryer Box<br>(智能宠物烘干箱)** | `9016401`, `9016402`, etc. | - **Sensors**: Real-time chamber temperature (°C), humidity (%), countdown remaining (min)<br>- **Select**: Operating mode (`comfort`, `quick`, `summer`, `winter`, `ozone`, `airbath`)<br>- **Numbers**: Countdown duration setting, lamp brightness (1–100%)<br>- **Switches**: Power, lamp switch, child lock |
| **Smart Pet Water Fountain<br>(智能饮水机)** | `WaterCamera`, etc. | - **Sensors**: Status, filter life<br>- **Binary Sensors**: Low water alert, water pump alert<br>- **Switches**: Power, night mode |
| **Smart Pet Camera<br>(宠物智能摄像机)** | `C01_Camera`, `FeedRackCamera`, etc. | - **Switches**: Camera power, microphone, IR night vision, status LED |

---

## 🚀 Installation

### Option 1: Via HACS (Recommended)
1. In Home Assistant, navigate to **HACS -> Integrations**.
2. Click the top right **three dots menu** -> **Custom repositories**.
3. Add this repository URL, select category **Integration**, and click **Add**.
4. Search for **Homerunpet (霍曼宠物)** in HACS and click **Download**.
5. Restart Home Assistant.

### Option 2: Manual Installation
1. Copy the `custom_components/homerunpet` directory from this repository into your Home Assistant `<config>/custom_components/` directory.
2. Restart Home Assistant.

---

## ⚙️ Configuration (Config Flow)

1. In Home Assistant, go to **Settings -> Devices & Services -> Add Integration**.
2. Search for **Homerunpet** (or **霍曼宠物**).
3. Fill in your login credentials:
   - **Account Type**: Mobile Phone (`phone`) or Email (`email`).
   - **Server Region**:
     - `China Mainland (中国大陆)`: for `+86` accounts (`https://api.homerunsmart.com`)
     - `North America (北美)`: for US/Canada accounts (`https://usapi.homerunsmart.com`)
     - `Europe / Global (欧洲及其他)`: for EU accounts (`https://euapi.homerunsmart.com`)
   - **Area Code**: Country / Dialing code (default `+86`).
   - **Username**: Your registered phone number or email address.
   - **Password**: Your Homerunpet account password.
4. If your account contains multiple family homes, select the family you wish to import.
5. Click **Submit**. All smart devices bound to that home will be automatically discovered and configured!

---

## 🔧 Options Flow

Click **Configure / Options** on the integration page to adjust the background cloud polling interval (default: `30 seconds`, adjustable between `10` and `300` seconds).

---

## Camera playback and HomeKit

Live video and snapshots require a working HA `go2rtc` integration; other device functions remain available without it. HomeKit requires **HA-managed go2rtc** (HA OS / Container); external go2rtc supports HA playback only. For non-Docker installations, configure an external URL in HA's go2rtc integration.

---

## 🛠️ Architecture & Protocol Details

- **Authentication**: Uses salted MD5 password hashing with client-side SHA256 parameter signature generation replicating Homerunpet APK version 1.3.1+.
- **Device Communication**: Direct HTTPS cloud polling and REST command dispatching (`/v1/devices/{serial}/properties` and `/v1/devices/{serial}/service/{id}`).
- **Coordinator**: Robust `DataUpdateCoordinator` with automatic token refresh, re-auth handling, and graceful offline detection.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
