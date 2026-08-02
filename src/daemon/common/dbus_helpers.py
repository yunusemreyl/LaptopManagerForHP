"""OMEN Command Center for Linux — D-Bus service bootstrap helpers.

Provides ``run_service()`` which handles the repetitive boilerplate that
every microservice needs:

1. Root privilege check
2. D-Bus bus-name ownership + object publishing
3. GLib main-loop
4. Graceful shutdown via SIGTERM / SIGINT
5. Optional sleep/wake event handling via logind
"""

import logging
import os
import signal
import sys
import threading
import time

from gi.repository import GLib
from pydbus import SystemBus

logger = logging.getLogger("hp-manager.dbus")

# Shared flag — services can check this to pause work during sleep
system_sleeping = threading.Event()


def _setup_sleep_handler(service_name: str):
    """Subscribe to logind PrepareForSleep signals."""
    try:
        bus = SystemBus()

        def _on_prepare_for_sleep(sender, obj, iface, signal, params):
            if params:
                sleeping = params[0]
                if sleeping:
                    logger.info("[%s] System preparing for sleep", service_name)
                    system_sleeping.set()
                else:
                    logger.info("[%s] System waking up", service_name)
                    system_sleeping.clear()

        bus.subscribe(
            sender="org.freedesktop.login1",
            iface="org.freedesktop.login1.Manager",
            signal="PrepareForSleep",
            object="/org/freedesktop/login1",
            signal_fired=_on_prepare_for_sleep
        )
        logger.info("[%s] Sleep/wake handler registered", service_name)
    except Exception as exc:
        logger.warning(
            "[%s] Failed to register sleep handler: %s", service_name, exc
        )


def run_service(
    bus_name: str,
    service_instance,
    service_name: str = "unknown",
    handle_sleep: bool = True,
):
    """Publish *service_instance* on the system D-Bus and run the main-loop.

    Parameters
    ----------
    bus_name : str
        The well-known D-Bus bus name, e.g. ``"com.yyl.hpmanager.fan"``.
    service_instance : object
        A pydbus-compatible service object with an introspection docstring.
    service_name : str
        Human-readable name used in log messages.
    handle_sleep : bool
        If True, register logind sleep/wake handler.
    """
    if os.geteuid() != 0:
        print(f"[{service_name}] Root privileges required.")
        sys.exit(1)

    loop = GLib.MainLoop()

    def _shutdown(*_args):
        logger.info("[%s] Shutting down…", service_name)
        loop.quit()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    if handle_sleep:
        _setup_sleep_handler(service_name)

    try:
        bus = SystemBus()
        bus.publish(bus_name, service_instance)
        logger.info("[%s] Ready on D-Bus (%s)", service_name, bus_name)
        loop.run()
    except Exception as exc:
        logger.critical("[%s] Service error: %s", service_name, exc)
        sys.exit(1)
