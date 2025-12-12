#!/usr/bin/env python3
import RPi.GPIO as GPIO
import os
import time
import threading
import logging

# --- Logging configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

log = logging.getLogger("NESPiSafeShutdown")

# --- GPIO pins for NESPi 4 ---
POWER_PIN   = 3   # Power button
RESET_PIN   = 2   # Reset button
LED_PIN     = 14  # LED (TXD)
POWEREN_PIN = 4   # Power enable / fan / power latch

# --- Health thresholds ---
LOW_TEMP_C    = 60.0
MEDIUM_TEMP_C = 67.0
HIGH_TEMP_C   = 75.0

LOW_LOAD1     = 1.1
MEDIUM_LOAD1  = 2.2
HIGH_LOAD1    = 3.3

# --- Time base for LED worker ---
TICK = 0.2  # seconds per step

# --- Global state ---
shutting_down = False
lock = threading.Lock()


def init_gpio():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    # Buttons with pull-up
    GPIO.setup(POWER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(RESET_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # LED
    GPIO.setup(LED_PIN, GPIO.OUT)
    GPIO.output(LED_PIN, GPIO.HIGH)  # LED on = system on

    # Power enable: keep HIGH so that the case keeps the Pi powered
    GPIO.setup(POWEREN_PIN, GPIO.OUT)
    GPIO.output(POWEREN_PIN, GPIO.HIGH)

    log.info(
        "GPIO initialized (Power=%d, Reset=%d, LED=%d, PowerEn=%d)",
        POWER_PIN, RESET_PIN, LED_PIN, POWEREN_PIN
    )


def get_load_and_temp():
    """Read 1-minute load average and CPU temperature."""
    load1 = 0.0
    temp_c = 0.0

    # CPU load
    try:
        with open("/proc/loadavg", "r") as f:
            load1 = float(f.read().split()[0])
    except Exception as e:
        log.debug("Could not read /proc/loadavg: %s", e)

    # CPU temperature
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_c = int(f.read().strip()) / 1000.0
    except Exception as e:
        log.debug("Could not read CPU temperature: %s", e)

    return load1, temp_c


def led_worker():
    """
    Drive the NESPi 4 front LED depending on system state.

    States:
      - shutting_down:
          fast blinking (0.2s on / 0.2s off), pattern: ON,OFF,ON,OFF,...
      - pattern == "high":
          high load, pattern (4 ticks = 0.8s): ON,ON,OFF,OFF
      - pattern == "medium":
          medium load, pattern (8 ticks = 1.6s): ON,ON,ON,ON,OFF,OFF,OFF,OFF
      - pattern == "low":
          slight load, pattern (14 ticks = 2.8s): 7x ON, 7x OFF
      - pattern == "idle":
          steady ON

    The loop never sleeps longer than TICK (0.2s) so the transition to
    shutdown blinking is visible quickly after the power button is pressed.
    """
    log.info("LED worker started")

    phase = 0  # global phase counter for blink patterns

    while True:
        with lock:
            sd = shutting_down

        if sd:
            # Shutdown mode: fast, even blinking (strobe-like)
            GPIO.output(LED_PIN, GPIO.HIGH if phase % 2 == 0 else GPIO.LOW)
            phase = (phase + 1) % 2
            time.sleep(TICK)
            continue

        # Health mode
        load1, temp_c = get_load_and_temp()

        # Default: idle = steady light
        pattern = "idle"

        # Thresholds - check from high to low
        if temp_c >= HIGH_TEMP_C or load1 >= HIGH_LOAD1:
            pattern = "high"
        elif temp_c >= MEDIUM_TEMP_C or load1 >= MEDIUM_LOAD1:
            pattern = "medium"
        elif temp_c >= LOW_TEMP_C or load1 >= LOW_LOAD1:
            pattern = "low"

        if pattern == "idle":
            # Steady ON; short sleep so we still react quickly to shutdown
            GPIO.output(LED_PIN, GPIO.HIGH)
            phase = 0
            time.sleep(TICK)

        elif pattern == "low":
            # Slow blinking:
            # Period ~2.8s (14 * 0.2s): 7 ticks ON, 7 ticks OFF
            if phase < 7:
                GPIO.output(LED_PIN, GPIO.HIGH)
            else:
                GPIO.output(LED_PIN, GPIO.LOW)
            phase = (phase + 1) % 14
            time.sleep(TICK)

        elif pattern == "medium":
            # Medium blinking:
            # Period ~1.6s (8 * 0.2s): 4 ticks ON, 4 ticks OFF
            if phase < 4:
                GPIO.output(LED_PIN, GPIO.HIGH)
            else:
                GPIO.output(LED_PIN, GPIO.LOW)
            phase = (phase + 1) % 8
            time.sleep(TICK)

        elif pattern == "high":
            # High blinking:
            # Period ~0.8s (4 * 0.2s): 2 ticks ON, 2 ticks OFF
            if phase < 2:
                GPIO.output(LED_PIN, GPIO.HIGH)
            else:
                GPIO.output(LED_PIN, GPIO.LOW)
            phase = (phase + 1) % 4
            time.sleep(TICK)


def stop_docker_containers():
    """
    Stop all running Docker containers cleanly.
    If Docker is not installed or no containers are running, this is a no-op.
    """
    log.info("Stopping Docker containers (if any)...")
    rc = os.system("docker ps -q | xargs -r docker stop")
    if rc != 0:
        log.warning("docker stop command returned exit code %d", rc)
    else:
        log.info("Docker containers stopped (or none were running).")


def handle_power(channel):
    """
    Callback for the NESPi 4 power button.

    - Debounces the button
    - Sets the global shutting_down flag (LED worker switches to shutdown pattern)
    - Waits 3 seconds to provide visible feedback
    - Stops Docker containers
    - Initiates a reboot via `shutdown -r now` (NESPi 4 then cuts power)
    """
    global shutting_down

    # Debounce
    time.sleep(0.2)
    if GPIO.input(POWER_PIN) == GPIO.HIGH:
        return  # Button was released again

    with lock:
        if shutting_down:
            log.info("Power button pressed again, shutdown already in progress - ignoring.")
            return
        shutting_down = True

    log.info("Power button pressed - starting shutdown sequence.")

    # Wait 3 seconds so the user can clearly see the shutdown LED pattern
    time.sleep(3.0)

    # Cleanly stop docker containers before reboot
    stop_docker_containers()

    # Reboot (NESPi 4 case will cut power after the reboot sequence)
    log.info("Triggering reboot via 'shutdown -r now'...")
    os.system("shutdown -r now")


def handle_reset(channel):
    """
    Callback for the NESPi 4 reset button.

    Triggers a direct reboot without stopping Docker first.
    """
    # Debounce
    time.sleep(0.2)
    if GPIO.input(RESET_PIN) == GPIO.HIGH:
        return

    log.info("Reset button pressed - triggering reboot.")
    os.system("shutdown -r now")


def main():
    log.info("NESPi SafeShutdown service starting...")
    init_gpio()

    # Start LED worker as a daemon thread
    t_led = threading.Thread(target=led_worker, daemon=True)
    t_led.start()

    # Register button events
    GPIO.add_event_detect(POWER_PIN, GPIO.FALLING,
                          callback=handle_power, bouncetime=200)
    GPIO.add_event_detect(RESET_PIN, GPIO.FALLING,
                          callback=handle_reset, bouncetime=200)

    log.info("Event handlers registered. Waiting for button events...")

    try:
        # Main loop keeps the script alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt - exiting.")
    finally:
        GPIO.cleanup()
        log.info("GPIO cleaned up. Service exiting.")


if __name__ == "__main__":
    main()
