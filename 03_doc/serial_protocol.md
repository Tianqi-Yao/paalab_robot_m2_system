# Serial Communication Protocol

**Connection**: 115200 baud, 8N1

---

## Host → Feather M4 CAN (Outgoing)

### Current Protocol: Velocity Command (used by web_controller.py)

```
V{linear:.2f},{angular:.2f}\n
```

Examples:
```
V0.50,-0.30\n   # Forward 0.5 m/s, turn right 0.3 rad/s
V0.00,0.00\n    # Emergency stop
```

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| linear | float (2 decimal places) | [-MAX_LINEAR_VEL, +MAX_LINEAR_VEL] | Positive = forward, negative = reverse |
| angular | float (2 decimal places) | [-MAX_ANGULAR_VEL, +MAX_ANGULAR_VEL] | Positive = turn left, negative = turn right |

### State Toggle Command

| Byte | Description |
|------|-------------|
| `\r` (0x0D) | Toggle READY ↔ ACTIVE state |

### Legacy Protocol: Single-byte WASD (used by robot_receiver.py / local_controller.py)

| Character | Description |
|-----------|-------------|
| `w` | Forward |
| `s` | Reverse |
| `a` | Turn left |
| `d` | Turn right |
| ` ` (space) | Stop |
| `H` | Heartbeat (no motor output) |

---

## Feather M4 CAN → Host (Incoming)

The Feather periodically outputs status lines (newline-terminated):

| Message | Description |
|---------|-------------|
| `S:READY\n` | Firmware in READY state (motor enable locked) |
| `S:ACTIVE\n` | Firmware in ACTIVE state (motor responds to commands normally) |

The host's `SerialReader` thread listens for these messages and drives the Web UI state button.
