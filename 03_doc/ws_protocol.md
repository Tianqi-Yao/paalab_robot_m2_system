# WebSocket Protocol

**Server address**: `ws://<robot_ip>:8889/`

---

## Client → Server (Commands)

| type | Fields | Description |
|------|--------|-------------|
| `heartbeat` | — | Keep-alive, resets watchdog timer (sent every 500 ms) |
| `joystick` | `linear: float`, `angular: float`, `force: float` | Joystick velocity command, sent at 10 Hz; ignored during autonomous navigation |
| `toggle_state` | — | Toggle READY ↔ ACTIVE state (sends `\r` to Feather) |
| `toggle_record` | — | Start / stop CSV data recording |
| `upload_waypoints` | `csv: str` | Upload waypoint list as CSV text |
| `nav_start` | — | Start autonomous navigation |
| `nav_stop` | — | Stop autonomous navigation |
| `nav_mode` | `mode: "p2p" \| "pure_pursuit"` | Switch navigation algorithm |
| `filter_mode` | `mode: "moving_avg" \| "kalman"` | Switch GPS filter mode |

---

## Server → Client (Push Messages)

### `imu` (20 Hz)
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

### `rtk` (1 Hz)
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
`fix_quality`: 0=No fix, 1=GPS, 2=DGPS, 4=RTK FIX, 5=RTK FLOAT

### `state_status` (on state change + on client connect)
```json
{ "type": "state_status", "active": false }
```
`active`: false = READY, true = ACTIVE

### `record_status` (on recording state change)
```json
{ "type": "record_status", "recording": true, "filename": "robot_data_20240101_120000.csv" }
```

### `status` (2 Hz, system health)
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

### `waypoints_loaded` (after waypoint upload)
```json
{ "type": "waypoints_loaded", "count": 5 }
// on failure:
{ "type": "waypoints_loaded", "count": 0, "error": "empty CSV" }
```

### `nav_status` (on navigation state change)
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

### `nav_complete` (on navigation complete)
```json
{ "type": "nav_complete", "total_wp": 5 }
```

### `nav_warning` (on navigation warning, e.g. GPS timeout)
```json
{ "type": "nav_warning", "msg": "GPS timeout — stopping" }
```
