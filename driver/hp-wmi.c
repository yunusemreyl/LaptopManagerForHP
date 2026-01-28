// SPDX-License-Identifier: GPL-2.0-or-later
#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/init.h>
#include <linux/slab.h>
#include <linux/types.h>
#include <linux/platform_device.h>
#include <linux/acpi.h>
#include <linux/wmi.h>

#define HPWMI_BIOS_GUID "5FB7F034-2C63-45e9-BE91-3D44E2C707E4"
#define HPWMI_FOURZONE 131081
#define HPWMI_FOURZONE_COLOR_GET 2
#define HPWMI_FOURZONE_COLOR_SET 3

struct color_platform {
    u8 blue; u8 green; u8 red;
} __packed;

struct platform_zone {
    u8 offset;
    struct color_platform colors;
};

static struct platform_zone zone_data[4];
static struct platform_device *hp_wmi_platform_dev;

static int hp_wmi_perform_query(int query, int command, void *buffer, int insize, int outsize)
{
    struct bios_args {
        u32 signature; u32 command; u32 commandtype; u32 datasize; u8 data[128];
    } args = { .signature = 0x55434553, .command = command, .commandtype = query, .datasize = insize };
    
    struct acpi_buffer input = { sizeof(struct bios_args), &args };
    struct acpi_buffer output = { ACPI_ALLOCATE_BUFFER, NULL };
    union acpi_object *obj;
    acpi_status status;
    int ret = 0;

    if (insize > 128) return -EINVAL;
    memcpy(&args.data[0], buffer, insize);

    status = wmi_evaluate_method(HPWMI_BIOS_GUID, 0, 3, &input, &output);
    if (ACPI_FAILURE(status)) return -ENODEV;

    obj = output.pointer;
    if (!obj) return -EINVAL;

    if (obj->type == ACPI_TYPE_BUFFER && obj->buffer.length >= 8) {
        ret = *(u32 *)(obj->buffer.pointer + 4);
        if (!ret && outsize)
            memcpy(buffer, obj->buffer.pointer + 8, min(outsize, (int)obj->buffer.length - 8));
    } else {
        ret = -EINVAL;
    }
    kfree(obj);
    return ret;
}

static int fourzone_update_led(int zone_idx, bool write)
{
    u8 state[128];
    int ret = hp_wmi_perform_query(HPWMI_FOURZONE_COLOR_GET, HPWMI_FOURZONE, &state, 128, 128);
    if (ret) return ret;

    if (write) {
        state[zone_data[zone_idx].offset + 0] = zone_data[zone_idx].colors.red;
        state[zone_data[zone_idx].offset + 1] = zone_data[zone_idx].colors.green;
        state[zone_data[zone_idx].offset + 2] = zone_data[zone_idx].colors.blue;
        return hp_wmi_perform_query(HPWMI_FOURZONE_COLOR_SET, HPWMI_FOURZONE, &state, 128, 128);
    } else {
        zone_data[zone_idx].colors.red = state[zone_data[zone_idx].offset + 0];
        zone_data[zone_idx].colors.green = state[zone_data[zone_idx].offset + 1];
        zone_data[zone_idx].colors.blue = state[zone_data[zone_idx].offset + 2];
    }
    return 0;
}

static ssize_t zone_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    int i = attr->attr.name[4] - '0';
    fourzone_update_led(i, false);
    return sprintf(buf, "%02X%02X%02X\n", zone_data[i].colors.red, zone_data[i].colors.green, zone_data[i].colors.blue);
}

static ssize_t zone_store(struct device *dev, struct device_attribute *attr, const char *buf, size_t count)
{
    int i = attr->attr.name[4] - '0';
    u32 rgb;
    if (kstrtou32(buf, 16, &rgb)) return -EINVAL;
    zone_data[i].colors.red = (rgb >> 16) & 0xFF;
    zone_data[i].colors.green = (rgb >> 8) & 0xFF;
    zone_data[i].colors.blue = rgb & 0xFF;
    fourzone_update_led(i, true);
    return count;
}

static DEVICE_ATTR(zone0, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone1, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone2, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone3, 0644, zone_show, zone_store);

static struct attribute *hp_wmi_attrs[] = {
    &dev_attr_zone0.attr, &dev_attr_zone1.attr, &dev_attr_zone2.attr, &dev_attr_zone3.attr, NULL
};
ATTRIBUTE_GROUPS(hp_wmi);

static int hp_wmi_bios_setup(struct platform_device *device)
{
    return 0;
}

static void hp_wmi_bios_remove(struct platform_device *device)
{
}

static struct platform_driver hp_wmi_driver = {
    .driver = { 
        .name = "hp-wmi", 
        .dev_groups = hp_wmi_groups,
    },
    .probe = hp_wmi_bios_setup,
    .remove = hp_wmi_bios_remove, /* DÜZELTİLDİ: .remove_new -> .remove */
};

static int __init hp_wmi_init(void)
{
    int i;
    for (i = 0; i < 4; i++) zone_data[i].offset = 25 + (i * 3);

    hp_wmi_platform_dev = platform_device_register_simple("hp-wmi", -1, NULL, 0);
    if (IS_ERR(hp_wmi_platform_dev)) return PTR_ERR(hp_wmi_platform_dev);

    return platform_driver_register(&hp_wmi_driver);
}

static void __exit hp_wmi_exit(void)
{
    platform_driver_unregister(&hp_wmi_driver);
    platform_device_unregister(hp_wmi_platform_dev);
}

module_init(hp_wmi_init);
module_exit(hp_wmi_exit);
MODULE_LICENSE("GPL");
