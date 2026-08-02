# OmenCtl Documentation

Welcome to the internal documentation for **OmenCtl**. This directory contains comprehensive details about the software architecture, hardware manipulation via EC (Embedded Controller) and WMI (Windows Management Instrumentation) in Linux, and guidelines for development.

## Table of Contents

1. [Architecture & Execution Flow](ARCHITECTURE.md)
   Learn how a command flows from the User Interface (GTK4), through the D-Bus IPC, into the Python Daemon, and finally down to the hardware WMI/EC level.

2. [Hardware Offsets & Registers](HARDWARE_OFFSETS.md)
   A deep dive into the Embedded Controller (EC) registers, memory offsets, and ACPI paths used to control Fan Speeds, RGB Lighting, and Power Profiles. Covers HP V1 vs V2 architectures.

3. [Developer's Guide (Where to Edit)](DEVELOPERS_GUIDE.md)
   A step-by-step guide explaining which files to modify if you want to change the GUI, update the background daemon, or add support for a new laptop model.

4. [Source Code & Method Reference](CODE_REFERENCE.md)
   A deep dive into the actual codebase. Explains what specific methods do (like `_monitor_loop` or `_curve_fan_pct`), why they were written, and their expected behaviors.
