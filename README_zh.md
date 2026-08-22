# 霍曼宠物 (Homerunpet) Home Assistant 自定义集成插件

[English](README.md) | [中文说明](README_zh.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

通过对霍曼宠物（Homerunpet）官方 Android App 客户端通讯协议进行逆向反编译分析而开发的 Home Assistant 自定义集成插件。支持通过原生 UI Config Flow 直接登录官方账号，自动发现、监控与控制全系列宠物智能硬件。

---

## 🌟 支持的设备品类与实体功能

| 设备品类 | 适用型号 | 实体功能与控制能力 |
| :--- | :--- | :--- |
| **智能食盆 / 智能粮架摄像机<br>(Feeding Trough & Feed Rack Camera)** | `FeedRackCamera`, `FeedingTrough`, `a90111a1`, `a90112a1` 等 | - **摄像头 (Camera)**: 实时 HLS 高清视频流直播、WebRTC 支持、摄像头软开关<br>- **开关 (Switch)**: 麦克风拾音、画面时间水印、AI 宠物目标框选、靠近感应检测、进食行为录像<br>- **数值调节 (Number)**: 摄像机扬声器音量 (0~100%) |
| **智能猫砂盆 (Cat Litter Box)** | `A9015201`, `A9015202`, `B9015201`, `B9015202`, `a90128a1` 等 | - **摄像头 (Camera)**: 带摄像头款支持实时视频流<br>- **传感器 (Sensor)**: 猫砂余量百分比、设备工作状态、任务运行时长<br>- **二值传感器 (Binary Sensor)**: 猫咪靠近感应、猫咪入仓感应、集便仓满告警、猫砂过低预警<br>- **开关 (Switch)**: 自动清理、自动补砂、自动除臭仓盖、幼猫模式、童锁、夜间免打扰<br>- **动作按钮 (Button)**: 立即清理/铲屎、平整猫砂、立即补砂、重置集便盒满状态 |
| **智能喂食器 (Feeder)** | `A9016101`, `A9016102`, `B9016101`, `B9016102`, `9015601` 等 | - **传感器 (Sensor)**: 备用电池电量、下次计划喂食信息<br>- **二值传感器 (Binary Sensor)**: 粮桶缺粮预警、出粮口堵粮异常、市电连接状态、备用电池在位<br>- **数值调节 (Number)**: 单次出粮份数设定（1~10 份）<br>- **动作按钮 (Button)**: 远程手动立即出粮<br>- **开关 (Switch)**: 童锁、夜间模式、出粮雷达检测开关 |
| **智能净味器 / 空气净化器 (Air Purifier)** | `A9014901`, `B9014901`, `D0773AD2` 等 | - **风扇 (Fan)**: 电源开关、1~5 挡风速百分比调节、预设工作模式 (`auto`, `manual`, `sleep`, `comfort`, `strong`)<br>- **传感器 (Sensor)**: PM2.5 (`µg/m³`)、TVOC (`mg/m³`)、空气质量等级、滤芯剩余寿命百分比<br>- **开关 (Switch)**: 童锁、静音模式<br>- **动作按钮 (Button)**: 滤芯寿命重置 |
| **智能宠物烘干箱 (Pet Dryer)** | `9016401`, `9016402` 等 | - **传感器 (Sensor)**: 实时箱内温度 (°C)、湿度 (%)、倒计时剩余时间 (分钟)<br>- **下拉选择 (Select)**: 模式切换（舒适、快速、夏季、冬季、臭氧消毒、新风等）<br>- **数值调节 (Number)**: 倒计时时长设定、照明灯亮度设定 (1~100%)<br>- **开关 (Switch)**: 电源、照明灯/氛围灯、童锁 |
| **智能饮水机 (Water Fountain)** | `WaterCamera` 等 | - **传感器 (Sensor)**: 运行状态、滤芯寿命<br>- **二值传感器 (Binary Sensor)**: 缺水预警、水泵异常告警<br>- **开关 (Switch)**: 电源开关、夜间模式 |
| **智能宠物摄像机 (Pet Camera)** | `C01_Camera`, `FeedRackCamera` 等 | - **开关 (Switch)**: 摄像机电源、麦克风拾音、红外夜视、指示灯 |

---

## 🚀 安装指南

### 方式 1: 通过 HACS 安装（推荐）
1. 在 Home Assistant 中进入 **HACS -> Integrations**。
2. 点击右上角 **三个点菜单 -> 自定义存储库 (Custom repositories)**。
3. 输入本仓库地址，类别选择 **Integration (集成)** 并点击添加。
4. 在 HACS 集成列表中找到 **霍曼宠物 (Homerunpet)** 并点击 **下载**。
5. 重启 Home Assistant。

### 方式 2: 手动安装
1. 将本项目中的 `custom_components/homerunpet` 目录复制到您 Home Assistant 配置目录的 `custom_components/` 文件夹下（例如 `/config/custom_components/homerunpet`）。
2. 重启 Home Assistant。

---

## ⚙️ 账号配置 (Config Flow)

1. 进入 Home Assistant **设置 -> 设备与服务 -> 添加集成**。
2. 搜索并选择 **霍曼宠物** 或 `homerunpet`。
3. 填入登录信息：
   - **账号类型**：手机号码 (`phone`) 或 电子邮箱 (`email`)。
   - **服务器区域**：
     - `中国大陆`: 针对国内 `+86` 账号 (`https://api.homerunsmart.com`)
     - `北美地区`: 针对美加账号 (`https://usapi.homerunsmart.com`)
     - `欧洲及其他`: 针对海外/欧盟账号 (`https://euapi.homerunsmart.com`)
   - **国家/地区区号**：默认 `+86`。
   - **账号**：绑定的手机号或注册邮箱。
   - **登录密码**：霍曼 App 登录密码。
4. 若账号下存在多个家庭，系统将弹出选择框供您选择导入的家庭。
5. 点击提交，即可全自动发现该家庭名下的所有智能设备并生成实体。

---

## 🔧 选项配置 (Options)

在集成管理页面点击 **选项 (Configure / Options)**，可自由调整设备状态的云端轮询刷新周期（默认 30 秒，支持 10 ~ 300 秒）。

---

## 🛠️ 逆向协议与技术原理

- **密码哈希算法**：`MD5(appKey + password + "#q&8UT6eRV79ol4*")[7:27]`
- **请求参数签名**：请求参数 TreeMap 降序序列化 + AppKey + Timestamp 经 SHA256 运算生成签名。
- **状态同步机制**：基于 `DataUpdateCoordinator` 统一管理设备并发请求，支持 Token 过期自动静默重新登录。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。仅供智能家居爱好者学习交流与个人非商业使用。
