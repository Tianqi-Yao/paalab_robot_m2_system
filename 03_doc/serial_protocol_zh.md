# 串口通信协议

**连接参数**：115200 baud, 8N1

---

## 主机 → Feather M4 CAN（发送）

### 新协议：速度命令（web_controller.py 使用）

```
V{linear:.2f},{angular:.2f}\n
```

示例：
```
V0.50,-0.30\n   # 前进 0.5 m/s，右转 0.3 rad/s
V0.00,0.00\n    # 急停
```

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| linear | float（2位小数） | [-MAX_LINEAR_VEL, +MAX_LINEAR_VEL] | 正值前进，负值后退 |
| angular | float（2位小数） | [-MAX_ANGULAR_VEL, +MAX_ANGULAR_VEL] | 正值左转，负值右转 |

### 状态切换命令

| 字节 | 说明 |
|------|------|
| `\r` (0x0D) | 切换 READY ↔ ACTIVE 状态 |

### 旧协议：WASD 单字节（robot_receiver.py / local_controller.py 使用）

| 字符 | 说明 |
|------|------|
| `w` | 前进 |
| `s` | 后退 |
| `a` | 左转 |
| `d` | 右转 |
| ` ` (空格) | 停止 |
| `H` | 心跳（不驱动电机） |

---

## Feather M4 CAN → 主机（接收）

Feather 定期输出当前状态行（换行符结尾）：

| 报文 | 说明 |
|------|------|
| `S:READY\n` | 固件处于 READY 状态（电机使能锁定） |
| `S:ACTIVE\n` | 固件处于 ACTIVE 状态（电机正常响应命令） |

主机的 `SerialReader` 线程监听这些报文，驱动 Web UI 的状态按钮更新。
