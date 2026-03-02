# hp-wmi — Manual Fan Control & Keyboard RGB for HP Laptops

A Linux kernel module that adds manual fan speed control and keyboard RGB backlight support for HP Omen, Victus, and similar laptops.

> Based on the upstream [hp-wmi driver](https://github.com/TUXOV/hp-wmi-fan-and-backlight-control) by [TUXOV](https://github.com/TUXOV). All credit for the original implementation goes to the upstream maintainer.

**Please ⭐ star the repo if this driver works for you!**

## Features

- 🌀 **Manual fan speed control** — set custom RPM via hwmon interface
- 🔄 **Fan mode switching** — Automatic / Manual / Max via `pwm1_enable`
- 🎨 **Keyboard RGB backlight** — single-zone & 4-zone via LED multicolor interface
- 📊 **Performance profiles** — `performance` / `balanced` / `low-power` integrated with `power-profiles-daemon` (GNOME/KDE)
- ⌨️ **Fn+P hotkey** — cycle performance profiles from the keyboard

> [!NOTE]
> **HP Victus 15:** HP didn't mark manual fan control as supported on these laptops, even though the hardware supports it. Load the module with:
> ```bash
> sudo insmod hp-wmi.ko force_fan_control_support=true
> ```

## Installation

### Quick Install (All Distros)

The included `install.sh` script auto-detects your distro, installs dependencies, and sets up DKMS:

```bash
git clone https://github.com/yunusemreyl/hp-wmi-fan-and-backlight-control
cd hp-wmi-fan-and-backlight-control
sudo ./install.sh
```

Supported distros: **Ubuntu/Debian**, **Fedora/RHEL**, **Arch/Manjaro**, **openSUSE**, **Void**, **Gentoo**, and derivatives.

To uninstall:
```bash
sudo ./install.sh uninstall
```

### Optimized Kernels (CachyOS, Arch Clang, etc.)

If your kernel was compiled with Clang/LLVM (e.g., CachyOS), the build process needs to use the same toolchain. The `install.sh` and `Makefile` now automatically detect this by checking `/proc/version`.

If the detection fails, you can force it manually with:
```bash
sudo LLVM=1 ./install.sh
```

### Manual DKMS Install

```bash
git clone https://github.com/yunusemreyl/hp-wmi-fan-and-backlight-control
cd hp-wmi-fan-and-backlight-control
make
sudo make install-dkms
```

### Arch Linux (AUR)

```bash
git clone https://github.com/yunusemreyl/hp-wmi-fan-and-backlight-control
cd hp-wmi-fan-and-backlight-control
make install-arch
```

### NixOS

Add the repo as a flake input:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    hp_wmi_control.url = "github:yunusemreyl/hp-wmi-fan-and-backlight-control";
  };
  outputs = { self, nixpkgs, hp_wmi_control, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        ./configuration.nix
        hp_wmi_control.nixosModules.default
        {
          hardware.hp-wmi-control = {
            enable = true;
            # victus-15-support.enable = true;
          };
        }
      ];
    };
  };
}
```

### Temporary Install (Testing Only)

```bash
git clone https://github.com/yunusemreyl/hp-wmi-fan-and-backlight-control
cd hp-wmi-fan-and-backlight-control
make
sudo rmmod hp-wmi
sudo modprobe led_class_multicolor
sudo insmod hp-wmi.ko
```

## Usage

### Fan Control

Fan mode is controlled via `pwm1_enable`:

| Value | Mode | Description |
|-------|------|-------------|
| `0` | **Max** | All fans at maximum speed |
| `1` | **Manual** | Set custom RPM targets |
| `2` | **Auto** | BIOS controls fans based on temperature |

```bash
# Switch to manual mode
echo 1 | sudo tee /sys/devices/platform/hp-wmi/hwmon/hwmon*/pwm1_enable

# Set fan speeds (check fan*_max for limits)
echo 5500 | sudo tee /sys/devices/platform/hp-wmi/hwmon/hwmon*/fan1_target
echo 5200 | sudo tee /sys/devices/platform/hp-wmi/hwmon/hwmon*/fan2_target

# Return to automatic mode
echo 2 | sudo tee /sys/devices/platform/hp-wmi/hwmon/hwmon*/pwm1_enable
```

> [!TIP]
> Check `fan*_max` for maximum allowed RPM values. Values exceeding the limit return `-EINVAL`.

### Keyboard Backlight (RGB)

```bash
# Set color (R G B, 0-255 each)
echo "255 0 0" | sudo tee /sys/class/leds/hp::kbd_backlight/multi_intensity

# Set brightness (0-255)
echo 128 | sudo tee /sys/class/leds/hp::kbd_backlight/brightness
```

### Performance Profiles

Integrated with `power-profiles-daemon` — change profiles from GNOME/KDE power settings or via command line:

```bash
cat /sys/firmware/acpi/platform_profile              # Current profile
cat /sys/firmware/acpi/platform_profile_choices       # Available profiles

echo performance | sudo tee /sys/firmware/acpi/platform_profile
echo balanced    | sudo tee /sys/firmware/acpi/platform_profile
echo low-power   | sudo tee /sys/firmware/acpi/platform_profile
```

**Fn+P** keyboard shortcut also cycles through profiles.

## Tested On

- Victus 16‑s1 (9Z791EA)
- Victus 16‑r0053nt (i5‑13500H, RTX 4050) — *Tested by yunusemreyl*
- More testers needed! See [#1](https://github.com/TUXOV/hp-wmi-fan-and-backlight-control/issues/1)

## GUI

A new GUI for this driver is coming soon! Stay tuned.

## License

GPL-2.0-or-later — see [LICENSE](LICENSE)

## Disclaimer

**USE AT YOUR OWN RISK. THE AUTHORS ACCEPT NO RESPONSIBILITY FOR ANY DAMAGES.**
