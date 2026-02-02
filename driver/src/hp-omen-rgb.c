// SPDX-License-Identifier: GPL-2.0-or-later
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/init.h>
#include <linux/slab.h>
#include <linux/types.h>
#include <linux/platform_device.h>
#include <linux/acpi.h>
#include <linux/wmi.h>
#include <linux/mutex.h>
#include <linux/jiffies.h>

#define HPWMI_BIOS_GUID "5FB7F034-2C63-45e9-BE91-3D44E2C707E4"
#define DRIVER_NAME "hp-omen-rgb"
#define HPWMI_FOURZONE 131081
#define HPWMI_FOURZONE_COLOR_GET 2
#define HPWMI_FOURZONE_COLOR_SET 3
#define ZONE_COUNT 4

struct color_platform { u8 red; u8 green; u8 blue; };
struct platform_zone { u8 offset; struct color_platform colors; };

static struct platform_zone zone_data[ZONE_COUNT];
static struct platform_device *hp_omen_platform_dev;
static DEFINE_MUTEX(rgb_mutex);
static unsigned long last_update;

static int hp_perform_query(int query, int command, void *buffer, int insize, int outsize)
{
    struct bios_args {
        u32 signature; u32 command; u32 commandtype; u32 datasize; u8 data[128];
    } args = { .signature = 0x55434553, .command = command, .commandtype = query, .datasize = insize };
    struct acpi_buffer input = { sizeof(struct bios_args), &args };
    struct acpi_buffer output = { ACPI_ALLOCATE_BUFFER, NULL };
    union acpi_object *obj;
    acpi_status status;
    int ret = 0;

    if (insize > sizeof(args.data)) return -EINVAL;
    memcpy(&args.data[0], buffer, insize);
    status = wmi_evaluate_method(HPWMI_BIOS_GUID, 0, 3, &input, &output);
    if (ACPI_FAILURE(status)) return -ENODEV;
    obj = output.pointer;
    if (!obj) return -EINVAL;
    if (obj->type == ACPI_TYPE_BUFFER && obj->buffer.length >= 8) {
        ret = *(u32 *)(obj->buffer.pointer + 4);
        if (!ret && outsize && buffer) {
            size_t copy_len = min_t(size_t, outsize, obj->buffer.length - 8);
            memcpy(buffer, obj->buffer.pointer + 8, copy_len);
        }
    } else { ret = -EINVAL; }
    ACPI_FREE(obj);
    return ret;
}

static int update_led(int zone_idx, bool write)
{
    int ret; u8 state[128];
    if (zone_idx < 0 || zone_idx >= ZONE_COUNT) return -EINVAL;
    if (!write && time_before(jiffies, last_update + HZ / 5)) return 0;
    mutex_lock(&rgb_mutex);
    ret = hp_perform_query(HPWMI_FOURZONE_COLOR_GET, HPWMI_FOURZONE, &state, 128, 128);
    if (ret) { mutex_unlock(&rgb_mutex); return ret; }
    if (write) {
        state[zone_data[zone_idx].offset + 0] = zone_data[zone_idx].colors.red;
        state[zone_data[zone_idx].offset + 1] = zone_data[zone_idx].colors.green;
        state[zone_data[zone_idx].offset + 2] = zone_data[zone_idx].colors.blue;
        ret = hp_perform_query(HPWMI_FOURZONE_COLOR_SET, HPWMI_FOURZONE, &state, 128, 128);
    } else {
        zone_data[zone_idx].colors.red = state[zone_data[zone_idx].offset + 0];
        zone_data[zone_idx].colors.green = state[zone_data[zone_idx].offset + 1];
        zone_data[zone_idx].colors.blue = state[zone_data[zone_idx].offset + 2];
        last_update = jiffies;
    }
    mutex_unlock(&rgb_mutex);
    return ret;
}

static ssize_t zone_show(struct device *dev, struct device_attribute *attr, char *buf)
{
    int i; if (kstrtoint(attr->attr.name + 4, 10, &i)) return -EINVAL;
    update_led(i, false);
    return sprintf(buf, "%02X%02X%02X\n", zone_data[i].colors.red, zone_data[i].colors.green, zone_data[i].colors.blue);
}

static ssize_t zone_store(struct device *dev, struct device_attribute *attr, const char *buf, size_t count)
{
    int i; u32 rgb; if (kstrtoint(attr->attr.name + 4, 10, &i)) return -EINVAL;
    if (kstrtou32(buf, 16, &rgb)) return -EINVAL;
    zone_data[i].colors.red = (rgb >> 16) & 0xFF;
    zone_data[i].colors.green = (rgb >> 8) & 0xFF;
    zone_data[i].colors.blue = rgb & 0xFF;
    update_led(i, true);
    return count;
}

static DEVICE_ATTR(zone0, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone1, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone2, 0644, zone_show, zone_store);
static DEVICE_ATTR(zone3, 0644, zone_show, zone_store);
static struct attribute *hp_attrs[] = { &dev_attr_zone0.attr, &dev_attr_zone1.attr, &dev_attr_zone2.attr, &dev_attr_zone3.attr, NULL };
ATTRIBUTE_GROUPS(hp);
static struct platform_driver hp_omen_driver = { .driver = { .name = DRIVER_NAME, .dev_groups = hp_groups, }, };

static int __init hp_omen_init(void)
{
    int i, ret; for (i = 0; i < ZONE_COUNT; i++) zone_data[i].offset = 25 + (i * 3);
    ret = platform_driver_register(&hp_omen_driver);
    if (ret) return ret;
    hp_omen_platform_dev = platform_device_register_simple(DRIVER_NAME, -1, NULL, 0);
    if (IS_ERR(hp_omen_platform_dev)) { platform_driver_unregister(&hp_omen_driver); return PTR_ERR(hp_omen_platform_dev); }
    return 0;
}

static void __exit hp_omen_exit(void)
{
    platform_device_unregister(hp_omen_platform_dev);
    platform_driver_unregister(&hp_omen_driver);
}

module_init(hp_omen_init);
module_exit(hp_omen_exit);
MODULE_LICENSE("GPL");
MODULE_AUTHOR("Yunus Emre");
MODULE_DESCRIPTION("HP Omen/Victus RGB Driver");
