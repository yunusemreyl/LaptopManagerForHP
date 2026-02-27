// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * hp-omen-core — Companion driver for HP Omen/Victus RGB keyboard backlight.
 *
 * Works alongside the stock hp-wmi driver (which handles fan hwmon,
 * hotkeys, thermal profiles, rfkill).  This module only manages the
 * per-zone RGB colour of the keyboard backlight via WMI.
 *
 * Copyright (C) 2024 Yunus Emre <yunusemreyl>
 *
 * Based on hp-wmi.c by Matthew Garrett and Anssi Hannula, and on
 * hp-omen-rgb by yunusemreyl.
 */

#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/acpi.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/types.h>

MODULE_AUTHOR("Yunus Emre <yunusemreyl>");
MODULE_DESCRIPTION("HP Omen/Victus keyboard RGB companion driver");
MODULE_LICENSE("GPL");
/* NOTE: No MODULE_ALIAS("wmi:...") — we do NOT claim any WMI GUID
 * so we can coexist with the stock hp-wmi driver.                 */

/* ── WMI GUID used by hp_wmi_perform_query (shared, not claimed) ── */
#define HPWMI_BIOS_GUID "5FB7F034-2C63-45E9-BE91-3D44E2C707E4"

/* ── WMI command / query types we need ── */
enum hp_wmi_command {
  HPWMI_READ = 0x01,
  HPWMI_WRITE = 0x02,
  HPWMI_BACKLIGHT = 0x20009,
};

enum hp_wmi_backlight_commandtype {
  HPWMI_COLOR_GET_QUERY = 0x02,
  HPWMI_COLOR_SET_QUERY = 0x03,
  HPWMI_BRIGHTNESS_GET_QUERY = 0x04,
  HPWMI_BRIGHTNESS_SET_QUERY = 0x05,
};

/* ── BIOS communication structures ── */
struct bios_args {
  u32 signature;
  u32 command;
  u32 commandtype;
  u32 datasize;
  u8 data[];
};

struct bios_return {
  u32 sigpass;
  u32 return_code;
};

/* ── WMI query helper ── */
static inline int encode_outsize_for_pvsz(int outsize) {
  if (outsize > 4096)
    return -EINVAL;
  if (outsize > 1024)
    return 5;
  if (outsize > 128)
    return 4;
  if (outsize > 4)
    return 3;
  if (outsize > 0)
    return 2;
  return 1;
}

static int hp_wmi_perform_query(int query, enum hp_wmi_command command,
                                void *buffer, int insize, int outsize) {
  struct acpi_buffer input, output = {ACPI_ALLOCATE_BUFFER, NULL};
  struct bios_return *bios_return;
  union acpi_object *obj = NULL;
  struct bios_args *args = NULL;
  int mid, actual_insize, actual_outsize;
  size_t bios_args_size;
  int ret;

  mid = encode_outsize_for_pvsz(outsize);
  if (WARN_ON(mid < 0))
    return mid;

  actual_insize = max(insize, 128);
  bios_args_size = struct_size(args, data, actual_insize);
  args = kmalloc(bios_args_size, GFP_KERNEL);
  if (!args)
    return -ENOMEM;

  input.length = bios_args_size;
  input.pointer = args;

  args->signature = 0x55434553;
  args->command = command;
  args->commandtype = query;
  args->datasize = insize;
  memcpy(args->data, buffer, flex_array_size(args, data, insize));

  ret = wmi_evaluate_method(HPWMI_BIOS_GUID, 0, mid, &input, &output);
  if (ret)
    goto out_free;

  obj = output.pointer;
  if (!obj || obj->type != ACPI_TYPE_BUFFER) {
    ret = -EINVAL;
    goto out_free;
  }

  bios_return = (struct bios_return *)obj->buffer.pointer;
  ret = bios_return->return_code;
  if (ret)
    goto out_free;

  if (!outsize)
    goto out_free;

  actual_outsize =
      min(outsize, (int)(obj->buffer.length - sizeof(*bios_return)));
  memcpy(buffer, obj->buffer.pointer + sizeof(*bios_return), actual_outsize);
  memset(buffer + actual_outsize, 0, outsize - actual_outsize);

out_free:
  kfree(obj);
  kfree(args);
  return ret;
}

/* ══════════════════════════════════════════════════════════════════
 * RGB ZONE SYSFS  (zone0 … zone3)
 * echo "FF0000" > /sys/devices/platform/hp-omen-core/zone0
 * cat  /sys/devices/platform/hp-omen-core/zone0   → "FF0000"
 * ══════════════════════════════════════════════════════════════════ */
#define RGB_ZONE_COUNT 4
#define COLOR_TABLE_SIZE 128
#define COLOR_OFFSET 25 /* RGB data starts at byte 25 in the table */

static DEFINE_MUTEX(rgb_mutex);

static ssize_t zone_show(struct device *dev, struct device_attribute *attr,
                         char *buf) {
  int zone;
  u8 tbl[COLOR_TABLE_SIZE];
  int ret;

  if (kstrtoint(attr->attr.name + 4, 10, &zone) || zone < 0 ||
      zone >= RGB_ZONE_COUNT)
    return -EINVAL;

  mutex_lock(&rgb_mutex);
  memset(tbl, 0, sizeof(tbl));
  ret = hp_wmi_perform_query(HPWMI_COLOR_GET_QUERY, HPWMI_BACKLIGHT, tbl,
                             sizeof(tbl), sizeof(tbl));
  mutex_unlock(&rgb_mutex);

  if (ret)
    return -EIO;

  return sysfs_emit(buf, "%02X%02X%02X\n", tbl[COLOR_OFFSET + zone * 3 + 0],
                    tbl[COLOR_OFFSET + zone * 3 + 1],
                    tbl[COLOR_OFFSET + zone * 3 + 2]);
}

static ssize_t zone_store(struct device *dev, struct device_attribute *attr,
                          const char *buf, size_t count) {
  int zone;
  u32 rgb;
  u8 tbl[COLOR_TABLE_SIZE];
  int ret;

  if (kstrtoint(attr->attr.name + 4, 10, &zone) || zone < 0 ||
      zone >= RGB_ZONE_COUNT)
    return -EINVAL;
  if (kstrtou32(buf, 16, &rgb))
    return -EINVAL;

  mutex_lock(&rgb_mutex);
  memset(tbl, 0, sizeof(tbl));
  ret = hp_wmi_perform_query(HPWMI_COLOR_GET_QUERY, HPWMI_BACKLIGHT, tbl,
                             sizeof(tbl), sizeof(tbl));
  if (ret) {
    mutex_unlock(&rgb_mutex);
    return -EIO;
  }

  tbl[COLOR_OFFSET + zone * 3 + 0] = (rgb >> 16) & 0xFF;
  tbl[COLOR_OFFSET + zone * 3 + 1] = (rgb >> 8) & 0xFF;
  tbl[COLOR_OFFSET + zone * 3 + 2] = rgb & 0xFF;

  ret = hp_wmi_perform_query(HPWMI_COLOR_SET_QUERY, HPWMI_BACKLIGHT, tbl,
                             sizeof(tbl), sizeof(tbl));
  mutex_unlock(&rgb_mutex);

  return ret ? -EIO : count;
}

/* ── brightness on/off ── */
static ssize_t brightness_show(struct device *dev,
                               struct device_attribute *attr, char *buf) {
  u8 data = 0;

  hp_wmi_perform_query(HPWMI_BRIGHTNESS_GET_QUERY, HPWMI_BACKLIGHT, &data,
                       sizeof(data), sizeof(data));
  /* 0xE4 = on, 0x64 = off */
  return sysfs_emit(buf, "%d\n", data == 0xE4 ? 1 : 0);
}

static ssize_t brightness_store(struct device *dev,
                                struct device_attribute *attr, const char *buf,
                                size_t count) {
  unsigned int val;
  u8 data;

  if (kstrtouint(buf, 10, &val))
    return -EINVAL;

  data = val ? 0xE4 : 0x64;
  hp_wmi_perform_query(HPWMI_BRIGHTNESS_SET_QUERY, HPWMI_BACKLIGHT, &data,
                       sizeof(data), sizeof(data));
  return count;
}

/* ── sysfs attributes ── */
static DEVICE_ATTR(zone0, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone1, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone2, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone3, 0644, zone_show, zone_store);
static DEVICE_ATTR_RW(brightness);

static struct attribute *hp_omen_attrs[] = {
    &dev_attr_zone0.attr, &dev_attr_zone1.attr,      &dev_attr_zone2.attr,
    &dev_attr_zone3.attr, &dev_attr_brightness.attr, NULL,
};
ATTRIBUTE_GROUPS(hp_omen);

/* ══════════════════════════════════════════════════════════════════
 * PLATFORM DEVICE
 * ══════════════════════════════════════════════════════════════════ */
static struct platform_device *hp_omen_pdev;

static int __init hp_omen_core_init(void) {
  int ret;

  if (!wmi_has_guid(HPWMI_BIOS_GUID)) {
    pr_info("HP WMI BIOS GUID not found — not an HP system?\n");
    return -ENODEV;
  }

  hp_omen_pdev = platform_device_register_simple("hp-omen-core",
                                                 PLATFORM_DEVID_NONE, NULL, 0);
  if (IS_ERR(hp_omen_pdev))
    return PTR_ERR(hp_omen_pdev);

  ret = sysfs_create_groups(&hp_omen_pdev->dev.kobj, hp_omen_groups);
  if (ret) {
    platform_device_unregister(hp_omen_pdev);
    return ret;
  }

  pr_info("HP Omen/Victus RGB companion driver loaded\n");
  return 0;
}

static void __exit hp_omen_core_exit(void) {
  sysfs_remove_groups(&hp_omen_pdev->dev.kobj, hp_omen_groups);
  platform_device_unregister(hp_omen_pdev);
  pr_info("HP Omen/Victus RGB companion driver unloaded\n");
}

module_init(hp_omen_core_init);
module_exit(hp_omen_core_exit);