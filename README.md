# NESPi 4 Safe Shutdown & Health-LED (Raspberry Pi 4, Bookworm/Trixie)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.x-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%204-red.svg)
![OS](https://img.shields.io/badge/Raspberry%20Pi%20OS-Bookworm%2FTrixie-orange.svg)

This repository provides a modern safe-shutdown setup for the  
**RetroFlag NESPi 4 case** with a **Raspberry Pi 4**, focused on running the Pi as a **home server with Docker containers**.

It is based on — and inspired by — the original Safe Shutdown work from the  
**RetroFlag team**:  
https://github.com/RetroFlag/retroflag-picase  
A big shout‑out to RetroFlag for providing the foundation that made this improved and updated version possible.

---

## Main Features

- Safe shutdown via the NESPi 4 **power switch**
- Reboot via the NESPi 4 **reset button**
- Automatic power cut by the NESPi 4 case after reboot
- Health LED on the NESPi 4 front panel:
  - **Idle**: steady ON  
  - **Low load**: slow blinking  
  - **Medium load**: medium-speed blinking  
  - **High load**: fast blinking  
  - **Shutdown in progress**: strobe-like blinking
- **Designed by default to stop all Docker containers before reboot**  
  (ideal for a Raspberry Pi Home Server running Pi-hole, Unbound, Home Assistant, etc.)
- The Docker-stop behavior can be replaced by any custom shutdown actions  
  (EmulationStation, RetroArch, other services)

This setup is intended for **Raspberry Pi OS Bookworm/Trixie** using **systemd**.

---

## Installation

You can install everything using a single command:

```bash
wget -O - "https://raw.githubusercontent.com/fry747/nespi4-safe-shutdown/main/install.sh" | sudo bash
```

The installer will:

1. Install `python3-rpi-lgpio`
2. Download `SafeShutdown.py` → `/opt/RetroFlag/`
3. Install overlay → `/boot/firmware/overlays/`
4. Modify `config.txt`
5. Install the systemd service
6. Enable + start the service

Check service status:

```bash
systemctl status nespi-safe-shutdown.service
```

Reboot afterward:

```bash
sudo reboot
```

---

## Repository Contents

- `SafeShutdown.py`  
  Main Python script handling:
  - GPIO initialization  
  - Power/Reset button handling  
  - LED worker thread (health indicator + shutdown feedback)  
  - Docker container shutdown logic  
  - Reboot initiation

- `nespi-safe-shutdown.service`  
  A systemd service that starts the SafeShutdown script at boot.

- `RetroFlag_pw_io.dtbo`  
  Device Tree overlay used to configure GPIO pins for the NESPi 4 case.

- `install.sh`  
  Automated installer script that:
  - installs required dependencies  
  - places all files in their correct locations  
  - enables the device-tree overlay  
  - installs and starts the systemd service  

---

## Hardware & OS Requirements

- Raspberry Pi 4  
- RetroFlag **NESPi 4 case**  
  - internal **Safe Shutdown switch set to ON**
- Raspberry Pi OS:
  - **Bookworm** or **Trixie**
- Optional: Docker (if you want graceful container shutdown)

---

## How It Works

### GPIO & Device Tree Overlay

The NESPi 4 case uses the following Raspberry Pi pins:

- GPIO 3  → Power button  
- GPIO 2  → Reset button  
- GPIO 14 → LED output (TXD)  
- GPIO 4  → Power enable / latch  

The included overlay (`RetroFlag_pw_io.dtbo`) configures these pins at boot.

On modern Raspberry Pi OS versions, the config file is:

```
/boot/firmware/config.txt
```

The installer adds:

```
dtoverlay=RetroFlag_pw_io.dtbo
enable_uart=1
```

### SafeShutdown.py Overview

The script:

1. Initializes relevant GPIO pins  
2. Spawns an LED worker thread that:
   - reads load average & CPU temperature (every 0.2s)
   - displays the corresponding blink pattern  
3. Handles button events:
   - **Power switch**:
     - Debounce  
     - Set a shutdown flag  
     - Show shutdown LED pattern  
     - Stop Docker containers (if installed)  
     - Reboot (`shutdown -r now`)  
     - NESPi case cuts power automatically  
   - **Reset button**:
     - Immediate reboot (no Docker stop)

### LED Indicator Patterns

| State                | Behavior                               |
|----------------------|----------------------------------------|
| Idle                 | LED steady ON                          |
| Low load             | 7 ticks ON, 7 ticks OFF                |
| Medium load          | 4 ticks ON, 4 ticks OFF                |
| High load            | 2 ticks ON, 2 ticks OFF                |
| Shutdown in progress | Fast ON/OFF strobe (0.2s / 0.2s)       |

Thresholds are configurable in `SafeShutdown.py`:

```python
LOW_TEMP_C, MEDIUM_TEMP_C, HIGH_TEMP_C
LOW_LOAD1, MEDIUM_LOAD1, HIGH_LOAD1
```

---

## Customizing the Shutdown Routine

If you do not use Docker, modify:

```python
def stop_docker_containers():
    # replace with your own logic
```

Examples:

- Stop EmulationStation  
- Stop RetroArch  
- Stop a custom systemd service  

---

## Testing Load-Based LED Behavior

Install stress-ng:

```bash
sudo apt install -y stress-ng
```

Simulate medium load:

```bash
stress-ng --cpu 2 --cpu-load 50 --timeout 120s
```

Simulate high load:

```bash
stress-ng --cpu 4 --cpu-load 100 --timeout 120s
```

Monitor thresholds:

```bash
watch -n 1 "cat /proc/loadavg; cat /sys/class/thermal/thermal_zone0/temp"
```

---

## Notes about newer Raspberry Pi OS versions

On newer Raspberry Pi OS versions (Bookworm and later), the legacy
`python3-rpi.gpio` library can have issues with edge detection and the
old `/sys/class/gpio` interface.

This project therefore uses:

- `python3-rpi-lgpio`

which provides the same `RPi.GPIO` API, but internally uses the newer
GPIO character-device interface. This makes it compatible with current
kernels and Raspberry Pi OS releases.

The `install.sh` script will:

- remove `python3-rpi.gpio` if present,
- install `python3-rpi-lgpio`.

---

## License

This project is licensed under the **MIT License**.  
See the **LICENSE** file for full details.

---

## Credits

- **RetroFlag** for the original Safe Shutdown design and their public scripts  
  https://github.com/RetroFlag/retroflag-picase  

This project builds upon their work and extends it for  
modern Raspberry Pi OS versions and home server use cases (Docker).
