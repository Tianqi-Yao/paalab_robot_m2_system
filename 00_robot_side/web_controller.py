"""
Web Joystick Controller — HTTP 静态文件 + WebSocket + IMU + 串口速度输出

架构：
  Thread-1: asyncio event loop
    ├─ websockets.serve() :WEB_WS_PORT  → _ws_handler()
    │    接收摇杆命令 → serial.write("V{linear:.2f},{angular:.2f}\n")
    ├─ _imu_broadcast_loop(): 20Hz 推送 IMU + 罗盘
    └─ _watchdog_loop(): 2s 无心跳 → 发送 "V0.00,0.00\n" 急停
  Thread-2: ThreadingHTTPServer :WEB_HTTP_PORT（守护线程，服务静态文件）
  Thread-3: IMUReader（depthai 守护线程，读取 OAK-D IMU）

串口操作直接使用 serial.Serial（不经过 SerialWriter 白名单），
与 robot_receiver.py / local_controller.py 互斥（不可同时持有同一串口）。

Usage:
    cd m2_system/00_robot_side
    python web_controller.py
"""

import asyncio
import json
import logging
import math
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial
import websockets

from config import (
    FEATHER_PORT, SERIAL_BAUD, SERIAL_TIMEOUT,
    WEB_HTTP_PORT, WEB_WS_PORT,
    MAX_LINEAR_VEL, MAX_ANGULAR_VEL,
    WATCHDOG_TIMEOUT,
)

# ── Logging ────────────────────────────────────────────────
_py_name = Path(__file__).stem
Path("log").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"log/{_py_name}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── 静态文件目录 ─────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "web_static"

# ── IMU 数据存储（线程安全用 lock） ──────────────────────
_imu_lock = threading.Lock()
_imu_data: dict = {
    "accel": {"x": 0.0, "y": 0.0, "z": 0.0},
    "gyro":  {"x": 0.0, "y": 0.0, "z": 0.0},
    "compass": {
        "bearing": 0.0, "cardinal": "N",
        "calibrated": False,
        "quat": {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
    },
    "ts": 0.0,
}
_imu_available = False  # 是否成功连接 depthai


# ── 四元数 → 罗盘方位角 ───────────────────────────────────
def quaternion_to_compass(real: float, i: float, j: float, k: float) -> tuple[float, str]:
    """BNO085 ROTATION_VECTOR(NED) → 方位角 [0, 360)，0=磁北，顺时针。
    NED/ENU 坐标系可通过 COORD_SYSTEM 环境变量切换（默认 NED）。
    """
    coord = os.environ.get("COORD_SYSTEM", "NED").upper()
    if coord == "ENU":
        # ENU: yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
        yaw_rad = math.atan2(2 * (real * k + i * j), 1 - 2 * (j * j + k * k))
    else:
        # NED: yaw = atan2(2*(w*k + i*j), 1 - 2*(j^2 + k^2))
        yaw_rad = math.atan2(2 * (real * k + i * j), 1 - 2 * (j * j + k * k))
    bearing = math.degrees(yaw_rad) % 360.0
    cardinals = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    cardinal  = cardinals[int((bearing + 22.5) / 45.0) % 8]
    return bearing, cardinal


# ── IMU 读取线程（depthai OAK-D） ─────────────────────────
class IMUReader(threading.Thread):
    """后台线程：持续从 OAK-D 读取 IMU 数据并更新 _imu_data。"""

    def __init__(self) -> None:
        super().__init__(name="IMUReader", daemon=True)

    def run(self) -> None:
        global _imu_available
        try:
            import depthai as dai
        except ImportError:
            logger.warning("depthai 未安装，IMU 功能不可用，HUD 将显示零值")
            return

        try:
            with dai.Pipeline() as pipeline:
                imu_node = pipeline.create(dai.node.IMU)
                imu_node.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 480)
                imu_node.enableIMUSensor(dai.IMUSensor.GYROSCOPE_RAW, 400)
                imu_node.enableIMUSensor(dai.IMUSensor.ROTATION_VECTOR, 100)
                imu_node.setBatchReportThreshold(1)
                imu_node.setMaxBatchReports(10)

                imu_queue = imu_node.out.createOutputQueue(maxSize=50, blocking=False)
                pipeline.start()
                _imu_available = True
                logger.info("IMUReader: depthai IMU 已启动")

                while pipeline.isRunning():
                    try:
                        imu_data_pkt = imu_queue.get()
                        if imu_data_pkt is None:
                            continue
                        for pkt in imu_data_pkt.packets:
                            self._process_packet(pkt)
                    except Exception as e:
                        logger.error(f"IMUReader: 读取数据包失败: {e}")

        except Exception as e:
            logger.error(f"IMUReader: depthai 管线启动失败: {e}")
            _imu_available = False

    def _process_packet(self, pkt) -> None:
        global _imu_data
        try:
            accel = pkt.acceleroMeter
            gyro  = pkt.gyroscope
            rot   = pkt.rotationVector

            # 检测是否已校准（四元数全零视为未校准）
            w, xi, yj, zk = rot.real, rot.i, rot.j, rot.k
            calibrated = not (w == 0.0 and xi == 0.0 and yj == 0.0 and zk == 0.0)
            bearing, cardinal = quaternion_to_compass(w, xi, yj, zk) if calibrated else (0.0, "N")

            with _imu_lock:
                _imu_data = {
                    "accel": {"x": accel.x, "y": accel.y, "z": accel.z},
                    "gyro":  {"x": gyro.x,  "y": gyro.y,  "z": gyro.z},
                    "compass": {
                        "bearing": bearing,
                        "cardinal": cardinal,
                        "calibrated": calibrated,
                        "quat": {"w": w, "x": xi, "y": yj, "z": zk},
                    },
                    "ts": time.time(),
                }
        except Exception as e:
            logger.error(f"IMUReader: 处理数据包异常: {e}")


# ── HTTP 静态文件服务 ─────────────────────────────────────
class StaticFileHandler(SimpleHTTPRequestHandler):
    """从 STATIC_DIR 提供静态文件，注入 MAX_LINEAR/MAX_ANGULAR 到 HTML meta。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        # 对 index.html 注入速度配置
        if self.path in ('/', '/index.html'):
            self._serve_index()
        else:
            super().do_GET()

    def _serve_index(self):
        index_path = STATIC_DIR / "index.html"
        try:
            content = index_path.read_text(encoding="utf-8")
            # 在 <html> 标签注入 data 属性，供 JS 读取
            content = content.replace(
                '<html lang="en">',
                f'<html lang="en" data-max-linear="{MAX_LINEAR_VEL}" data-max-angular="{MAX_ANGULAR_VEL}">'
            )
            encoded = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except Exception as e:
            logger.error(f"HTTP: 服务 index.html 失败: {e}")
            self.send_error(500)

    def log_message(self, fmt, *args):
        logger.debug(f"HTTP: {fmt % args}")


def _start_http_server() -> None:
    """在守护线程中启动 ThreadingHTTPServer。"""
    server = ThreadingHTTPServer(("0.0.0.0", WEB_HTTP_PORT), StaticFileHandler)
    t = threading.Thread(target=server.serve_forever, name="HTTPServer", daemon=True)
    t.start()
    logger.info(f"HTTP 静态文件服务已启动：http://0.0.0.0:{WEB_HTTP_PORT}/")


# ── WebSocket 服务 ────────────────────────────────────────
class WebController:
    """管理 WebSocket 连接、串口输出和看门狗。"""

    def __init__(self) -> None:
        self._ser: serial.Serial | None = None
        self._ser_lock = threading.Lock()
        self._clients: set = set()
        self._clients_lock = asyncio.Lock()
        self._last_heartbeat: float = time.time()
        self._serial_ok = False
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Serial ────────────────────────────────────────────
    def open_serial(self) -> None:
        try:
            self._ser = serial.Serial(FEATHER_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
            self._serial_ok = True
            logger.info(f"串口已打开: {FEATHER_PORT} @ {SERIAL_BAUD} baud")
        except serial.SerialException as e:
            logger.error(f"串口打开失败 [{FEATHER_PORT}]: {e}")
            self._serial_ok = False

    def close_serial(self) -> None:
        with self._ser_lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
                logger.info("串口已关闭")

    def _send_velocity(self, linear: float, angular: float) -> None:
        """向 Feather M4 发送直接速度命令 V{linear:.2f},{angular:.2f}\n"""
        cmd = f"V{linear:.2f},{angular:.2f}\n".encode()
        with self._ser_lock:
            if self._ser is None or not self._ser.is_open:
                logger.warning("串口未打开，无法发送速度命令")
                return
            try:
                self._ser.write(cmd)
                logger.debug(f"串口发送: {cmd!r}")
            except serial.SerialException as e:
                logger.error(f"串口写入失败: {e}")
                self._serial_ok = False

    # ── WebSocket 处理器 ──────────────────────────────────
    async def _ws_handler(self, websocket) -> None:
        async with self._clients_lock:
            self._clients.add(websocket)
        logger.info(f"WebSocket 客户端已连接: {websocket.remote_address}")
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(f"WebSocket: 无效 JSON: {raw!r}")
                    continue

                msg_type = msg.get("type")

                if msg_type == "heartbeat":
                    self._last_heartbeat = time.time()

                elif msg_type == "joystick":
                    self._last_heartbeat = time.time()  # 摇杆消息也刷新心跳
                    try:
                        linear  = float(msg.get("linear",  0.0))
                        angular = float(msg.get("angular", 0.0))
                        # 钳位到速度限制
                        linear  = max(-MAX_LINEAR_VEL,  min(MAX_LINEAR_VEL,  linear))
                        angular = max(-MAX_ANGULAR_VEL, min(MAX_ANGULAR_VEL, angular))
                        self._send_velocity(linear, angular)
                    except (TypeError, ValueError) as e:
                        logger.warning(f"WebSocket: 摇杆消息格式错误: {e}")

        except websockets.exceptions.ConnectionClosedError:
            pass
        except Exception as e:
            logger.error(f"WebSocket 处理器异常: {e}")
        finally:
            async with self._clients_lock:
                self._clients.discard(websocket)
            logger.info(f"WebSocket 客户端已断开: {websocket.remote_address}")
            # 客户端断开时立即发送急停
            self._send_velocity(0.0, 0.0)

    # ── IMU 广播循环（20Hz） ──────────────────────────────
    async def _imu_broadcast_loop(self) -> None:
        while True:
            await asyncio.sleep(0.05)  # 20Hz
            with _imu_lock:
                data = dict(_imu_data)
            msg = json.dumps({
                "type": "imu",
                "ts":    data["ts"],
                "accel": data["accel"],
                "gyro":  data["gyro"],
                "compass": data["compass"],
            })
            async with self._clients_lock:
                clients = set(self._clients)
            if not clients:
                continue
            dead = set()
            for ws in clients:
                try:
                    await ws.send(msg)
                except Exception:
                    dead.add(ws)
            if dead:
                async with self._clients_lock:
                    self._clients -= dead

    # ── 看门狗循环 ────────────────────────────────────────
    async def _watchdog_loop(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            elapsed = time.time() - self._last_heartbeat
            if elapsed > WATCHDOG_TIMEOUT:
                logger.warning(f"看门狗触发！{elapsed:.1f}s 未收到心跳，发送急停")
                self._send_velocity(0.0, 0.0)
                # 重置计时，避免连续急停刷屏
                self._last_heartbeat = time.time()

    # ── 状态广播（低频） ──────────────────────────────────
    async def _status_broadcast_loop(self) -> None:
        while True:
            await asyncio.sleep(2.0)
            msg = json.dumps({
                "type": "status",
                "serial_ok": self._serial_ok,
                "imu_ok": _imu_available,
                "message": "OK" if (self._serial_ok and _imu_available) else "DEGRADED",
            })
            async with self._clients_lock:
                clients = set(self._clients)
            for ws in clients:
                try:
                    await ws.send(msg)
                except Exception:
                    pass

    # ── 主入口 ────────────────────────────────────────────
    async def serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._last_heartbeat = time.time()

        async with websockets.serve(
            self._ws_handler,
            "0.0.0.0",
            WEB_WS_PORT,
            ping_interval=20,
            ping_timeout=10,
        ):
            logger.info(f"WebSocket 服务已启动：ws://0.0.0.0:{WEB_WS_PORT}/")
            await asyncio.gather(
                self._imu_broadcast_loop(),
                self._watchdog_loop(),
                self._status_broadcast_loop(),
            )


# ── 主程序入口 ────────────────────────────────────────────
def main() -> None:
    logger.info("=" * 50)
    logger.info("Web Joystick Controller 启动中...")
    logger.info(f"  HTTP 端口: {WEB_HTTP_PORT}")
    logger.info(f"  WS   端口: {WEB_WS_PORT}")
    logger.info(f"  串口设备: {FEATHER_PORT}")
    logger.info(f"  速度上限: linear={MAX_LINEAR_VEL} m/s, angular={MAX_ANGULAR_VEL} rad/s")
    logger.info(f"  看门狗:   {WATCHDOG_TIMEOUT}s")
    logger.info("=" * 50)

    controller = WebController()
    controller.open_serial()

    # 启动 HTTP 静态文件服务（守护线程）
    _start_http_server()

    # 启动 IMU 读取线程（守护线程）
    imu_reader = IMUReader()
    imu_reader.start()

    # 获取本机 IP 供用户访问提示
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "localhost"

    logger.info(f"手机访问：http://{local_ip}:{WEB_HTTP_PORT}/")

    try:
        asyncio.run(controller.serve())
    except KeyboardInterrupt:
        logger.info("用户中断，正在关闭...")
    finally:
        controller.close_serial()
        logger.info("Web Controller 已停止")


if __name__ == "__main__":
    main()
