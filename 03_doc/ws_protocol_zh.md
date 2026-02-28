# WebSocket 通信协议

**服务端地址**：`ws://<robot_ip>:8889/`

---

## 客户端 → 服务端（指令）

| type | 字段 | 说明 |
|------|------|------|
| `heartbeat` | — | 保持连接、重置看门狗（500ms 发一次） |
| `joystick` | `linear: float`, `angular: float`, `force: float` | 摇杆速度命令，10Hz 发送；导航中忽略 |
| `toggle_state` | — | 切换 READY ↔ ACTIVE 状态（发送 `\r` 到 Feather） |
| `toggle_record` | — | 开始 / 停止 CSV 数据录制 |
| `upload_waypoints` | `csv: str` | 上传 CSV 格式航点文本 |
| `nav_start` | — | 启动自主导航 |
| `nav_stop` | — | 停止自主导航 |
| `nav_mode` | `mode: "p2p" \| "pure_pursuit"` | 切换导航算法 |
| `filter_mode` | `mode: "moving_avg" \| "kalman"` | 切换 GPS 滤波器 |

---

## 服务端 → 客户端（数据推送）

### `imu`（20 Hz）
```json
{
  "type": "imu",
  "ts": 1234567890.123,
  "accel": { "x": 0.0, "y": 0.0, "z": 9.8 },
  "gyro":  { "x": 0.0, "y": 0.0, "z": 0.0 },
  "compass": {
    "bearing": 45.0,
    "cardinal": "NE",
    "calibrated": true,
    "accuracy": 3,
    "quat": { "w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0 }
  }
}
```

### `rtk`（1 Hz）
```json
{
  "type": "rtk",
  "available": true,
  "lat": 31.1234567,
  "lon": 121.1234567,
  "alt": 10.5,
  "fix_quality": 4,
  "num_sats": 12,
  "hdop": 0.8,
  "speed_knots": 0.02,
  "track_deg": 90.0
}
```
`fix_quality`: 0=无信号, 1=GPS, 2=DGPS, 4=RTK FIX, 5=RTK FLOAT

### `state_status`（状态变化时 + 客户端连接时推送）
```json
{ "type": "state_status", "active": false }
```
`active`: false = READY, true = ACTIVE

### `record_status`（录制状态变化时）
```json
{ "type": "record_status", "recording": true, "filename": "robot_data_20240101_120000.csv" }
```

### `status`（2 Hz，系统健康状态）
```json
{
  "type": "status",
  "serial_ok": true,
  "imu_ok": true,
  "rtk_ok": true,
  "recording": false,
  "message": "OK"
}
```

### `waypoints_loaded`（上传航点后）
```json
{ "type": "waypoints_loaded", "count": 5 }
// 或失败时：
{ "type": "waypoints_loaded", "count": 0, "error": "empty CSV" }
```

### `nav_status`（导航状态变化时）
```json
{
  "type": "nav_status",
  "state": "navigating",
  "progress": [2, 5],
  "distance_m": 3.2,
  "target_bearing": 45.0,
  "nav_mode": "p2p",
  "filter_mode": "moving_avg",
  "tolerance_m": 1.5
}
```
`state`: `"idle"` | `"navigating"` | `"finished"`

### `nav_complete`（导航完成时）
```json
{ "type": "nav_complete", "total_wp": 5 }
```

### `nav_warning`（导航告警，如 GPS 超时）
```json
{ "type": "nav_warning", "msg": "GPS timeout — stopping" }
```
