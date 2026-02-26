# M2 System — Farm Robot LAN Control

Remote keyboard control and live video streaming for the farm-ng Amiga agricultural robot over a local area network (LAN).

> Chinese documentation: [README_zh.md](README_zh.md)

---

## Architecture

```
Remote PC (01_remote_side/)
├── Main thread  : cv2.imshow video display
├── Thread A     : VideoCapture pulls frames from HTTP:8080
├── Thread B     : pynput keyboard listener
└── Thread C     : TCP:9000 command sender + heartbeat
        │
        │  TCP :9000 (control)   HTTP :8080 (video)
        ▼
Robot side (00_robot_side/)
├── robot_receiver.py  → serial → Feather M4 CAN → CAN bus → Amiga Dashboard
└── camera_streamer.py ← FrameSource (swappable pipeline)
```

---

## Repository Layout

```
m2_system/
├── 00_robot_side/                  # Robot PC (Mac Mini / Linux)
│   ├── config.py                   # Serial / TCP / watchdog / camera params (env-overridable)
│   ├── serial_writer.py            # Thread-safe serial wrapper with command whitelist
│   ├── watchdog.py                 # Watchdog timer — triggers emergency stop on timeout
│   ├── robot_receiver.py           # TCP server + watchdog + serial forwarding
│   ├── local_controller.py         # Local keyboard → serial (no TCP required)
│   ├── frame_source.py             # FrameSource ABC + SimpleColorSource (OAK-D)
│   ├── camera_streamer.py          # MJPEGServer: streams any FrameSource over HTTP
│   ├── main.py                     # Interactive launcher menu (recommended entry point)
│   ├── log/                        # Runtime logs (auto-created)
│   └── cam_demo/                   # OAK-D camera demo scripts
│       ├── camera_viewer.py        # OAK-D local viewer (single-machine debug)
│       ├── Camera_output.py
│       ├── Camera_multiple_outputs.py
│       ├── Display_all_cameras.py
│       ├── Depth_Align.py
│       ├── Detection_network.py
│       ├── Detection_network_Remap.py
│       ├── Feature_Tracker.py
│       └── IMU.py
├── 01_remote_side/                 # Operator PC
│   ├── config.py                   # ROBOT_HOST, TCP/stream ports, reconnect delays
│   ├── remote_sender.py            # pynput + TCP client + heartbeat (standalone-capable)
│   ├── remote_viewer.py            # MJPEG pull + cv2.imshow + auto-reconnect (standalone-capable)
│   ├── main.py                     # One-shot launcher: sender (daemon thread) + viewer (main thread)
│   └── log/                        # Runtime logs (auto-created)
├── CIRCUITPY/                      # Feather M4 CAN firmware (CircuitPython)
│   ├── code.py                     # Parses serial commands → CAN frames
│   └── lib/farm_ng/                # farm-ng Amiga protocol library
├── CLAUDE.md
├── README.md                       # This file (English)
└── README_zh.md                    # Chinese documentation
```

---

## Operating Modes

### Mode A — Local control

Operator sits at the robot PC and controls it directly via keyboard.

```
Local PC (pynput) ──► local_controller.py ──serial──► Feather M4 CAN
```

- No TCP required; serial port is held directly.
- No watchdog (operator is physically present).
- **Cannot run simultaneously with `robot_receiver.py` (serial port conflict).**

### Mode B — Remote TCP control

Operator controls the robot from a separate machine over LAN.

```
Remote PC (pynput) ──TCP:9000──► robot_receiver.py ──serial──► Feather M4 CAN
```

- Remote side sends motion commands + periodic heartbeats.
- Robot-side watchdog triggers an emergency stop if no message is received within 2 s.

### Mode C — Remote TCP control + camera stream (recommended)

Full remote operation: keyboard control and live video in a single command.

```
Remote PC ──TCP:9000──► robot_receiver.py ──serial──► Feather M4 CAN
          ◄─HTTP:8080── camera_streamer.py ◄── FrameSource (OAK-D / YOLO / …)
```

---

## Key Bindings

| Key     | Action                                             |
|---------|----------------------------------------------------|
| `W`     | Forward (+0.1 m/s)                                 |
| `S`     | Backward (−0.1 m/s)                                |
| `A`     | Turn left (+0.1 rad/s)                             |
| `D`     | Turn right (−0.1 rad/s)                            |
| `Space` | Emergency stop (also sent automatically on key release) |
| `Enter` | Toggle state: AUTO_READY ↔ AUTO_ACTIVE             |
| `Q`     | Quit                                               |

> Direction keys are sent repeatedly at 10 Hz. Releasing all direction keys immediately sends an emergency stop.

---

## Installation

```bash
# Robot side (Mac Mini / Linux)
pip install pyserial pynput depthai opencv-python

# Remote side (operator PC)
pip install pynput opencv-python
```

---

## Configuration

### Robot side (`00_robot_side/config.py`)

| Parameter             | Default (macOS)            | Default (Linux)    | Description                      |
|-----------------------|----------------------------|--------------------|----------------------------------|
| `FEATHER_PORT`        | `/dev/cu.usbmodem2301`     | `/dev/ttyACM0`     | Feather M4 CAN serial port       |
| `SERIAL_BAUD`         | `115200`                   | same               | Serial baud rate                 |
| `TCP_PORT`            | `9000`                     | same               | TCP listening port               |
| `WATCHDOG_TIMEOUT`    | `2.0` s                    | same               | Watchdog timeout                 |
| `KEY_REPEAT_INTERVAL` | `0.1` s (10 Hz)            | same               | Key repeat interval              |
| `CAM1_IP`             | `10.95.76.10`              | same               | OAK-D PoE camera 1 IP            |
| `CAM2_IP`             | `10.95.76.11`              | same               | OAK-D PoE camera 2 IP            |
| `CAM1_STREAM_PORT`    | `8080`                     | same               | Camera 1 MJPEG stream port       |
| `CAM2_STREAM_PORT`    | `8081`                     | same               | Camera 2 MJPEG stream port       |
| `MJPEG_QUALITY`       | `80`                       | same               | JPEG encoding quality (1–100)    |
| `LOCAL_DISPLAY`       | `0` (off)                  | same               | Set `1` for local preview window |
| `CAM2_ENABLED`        | `0` (off)                  | same               | Set `1` to stream a second camera |

### Remote side (`01_remote_side/config.py`)

| Parameter               | Default      | Description                                   |
|-------------------------|--------------|-----------------------------------------------|
| `ROBOT_HOST`            | **required** | Robot IP address                              |
| `TCP_PORT`              | `9000`       | Control channel port                          |
| `STREAM_PORT`           | `8080`       | Video stream port                             |
| `HEARTBEAT_INTERVAL`    | `0.5` s      | Heartbeat send interval                       |
| `KEY_REPEAT_INTERVAL`   | `0.1` s      | Key repeat interval                           |
| `TCP_RECONNECT_DELAY`   | `2.0` s      | Wait time before retrying TCP connection      |
| `STREAM_RECONNECT_DELAY`| `3.0` s      | Wait time before retrying stream connection   |
| `STREAM_STALE_TIMEOUT`  | `3.0` s      | No-new-frame threshold for stale detection    |

---

## Quick Start

### Robot side

```bash
cd m2_system/00_robot_side
python main.py
```

```
========================================
   Farm Robot — Robot-side Launcher
========================================
  1. Local control
  2. Local control + camera
  3. Remote TCP control
  4. Remote TCP control + camera stream
  5. Local camera test

  q. Quit
========================================
```

Option **4** starts `robot_receiver.py` and `camera_streamer.py` in parallel.
Press `Ctrl+C` to stop both at once.

### Remote side — all-in-one

```bash
export ROBOT_HOST=192.168.x.x    # robot IP
cd m2_system/01_remote_side
python main.py
```

- The cv2 window shows the live camera feed.
- With keyboard focus on the terminal, use `wasd` to drive the robot.
- Press `q` in the terminal, or close the video window, to quit everything.

### Remote side — individual components

```bash
export ROBOT_HOST=192.168.x.x

# Control only
python remote_sender.py

# Video only
python remote_viewer.py
```

---

## Extending the Video Pipeline (FrameSource)

`camera_streamer.py` decouples *frame content* from *transport*.
Swap in a new pipeline by subclassing `FrameSource` — the `MJPEGServer` and all remote-side code stay unchanged.

```python
# 00_robot_side/frame_source.py
class FrameSource(ABC):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def get_frame(self) -> Optional[np.ndarray]: ...  # returns BGR frame

# Built-in implementation
class SimpleColorSource(FrameSource): ...   # raw OAK-D colour frame (default)

# Example future sources
class YOLODetectionSource(FrameSource): ... # colour frame + bounding-box overlay
class DepthAlignSource(FrameSource): ...    # colour + depth side-by-side
```

---

## Local Camera Tests (menu option 5)

| Option | Function                                    |
|--------|---------------------------------------------|
| 1      | Simple viewer (300×300, CAM_A)              |
| 2      | All cameras, full resolution                |
| 3      | Multi-output (300×300, CAM_A / B / C)       |
| 4      | Depth Align demo                            |
| 5      | YOLO object detection demo                  |

Additional demo scripts are in the `cam_demo/` directory (IMU, feature tracking, etc.).

---

## Feather M4 CAN Firmware

- **Path**: `CIRCUITPY/code.py`
- **Runtime**: CircuitPython 7.3.2
- **Protocol library**: `lib/farm_ng/` (farm-ng Amiga Dev Kit)

Workflow:

1. Listen on USB serial (115200 baud).
2. Parse single-byte commands (`w` / `s` / `a` / `d` / `space` / `\r`).
3. Update velocity and angular velocity (±0.1 increments); send CAN RPDO1 frame at 20 Hz.
4. Receive TPDO1 status frames from the Amiga Dashboard to sync control state.

---

## Safety

| Mechanism            | Description                                                     |
|----------------------|-----------------------------------------------------------------|
| Watchdog timer       | No command (including heartbeat) for 2 s → automatic emergency stop |
| Command whitelist    | `SerialWriter` only passes `w/s/a/d/space/\r`                  |
| Key-release stop     | All direction keys released → emergency stop sent immediately   |
| TCP disconnect stop  | `robot_receiver.py` sends emergency stop when client disconnects |
| Exception logging    | All exceptions are logged; silent swallowing is forbidden       |

---

## Logs

| Script                   | Log file                                  |
|--------------------------|-------------------------------------------|
| `main.py` (robot side)   | `00_robot_side/log/robot_main.log`        |
| `local_controller.py`    | `00_robot_side/log/local_controller.log`  |
| `robot_receiver.py`      | `00_robot_side/log/robot_receiver.log`    |
| `camera_streamer.py`     | `00_robot_side/log/camera_streamer.log`   |
| `main.py` (remote side)  | `01_remote_side/log/main.log`             |
| `remote_sender.py`       | `01_remote_side/log/remote_sender.log`    |
| `remote_viewer.py`       | `01_remote_side/log/remote_viewer.log`    |

Log format:

```
2025-01-01 12:00:00,000 [INFO] TCP server listening on 0.0.0.0:9000
2025-01-01 12:00:01,500 [INFO] Remote client connected: ('192.168.1.50', 54321)
2025-01-01 12:00:01,600 [INFO] MJPEG server started → http://0.0.0.0:8080/
```
