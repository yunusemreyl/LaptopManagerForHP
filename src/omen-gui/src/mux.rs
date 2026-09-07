use gtk::prelude::*;
use libadwaita as adw;
use adw::prelude::*;
use std::fs;
use crate::i18n;

/* ─────────────────────────────────────────────────────────────
   mux.rs — GPU MUX Switch Page
   ───────────────────────────────────────────────────────────── */

fn get_nvidia_driver_version() -> String {
    if let Ok(content) = fs::read_to_string("/proc/driver/nvidia/version") {
        for line in content.lines() {
            if line.contains("NVRM version:") {
                let parts: Vec<&str> = line.split_whitespace().collect();
                for part in parts {
                    if part.contains('.') && part.chars().next().map_or(false, |c| c.is_ascii_digit()) {
                        return format!("{} (NVIDIA Open Kernel)", part);
                    }
                }
            }
        }
    }
    "Unknown".to_string()
}

fn detect_active_display_gpu() -> (String, bool, String, String) {
    let specs = crate::daemon_client::get_hardware_specs_sync();
    let gpu_name = specs.gpu_spec.split("  ·  ").next().unwrap_or("NVIDIA GPU").to_string();
    let is_amd = specs.cpu_spec.to_lowercase().contains("ryzen") || specs.cpu_spec.to_lowercase().contains("amd");
    let igpu_name = if is_amd { "AMD Radeon Graphics".to_string() } else { "Intel Integrated Graphics".to_string() };

    if let Ok(entries) = glob::glob("/sys/class/drm/card[0-9]*-*eDP-1*/device/vendor") {
        for entry in entries.filter_map(Result::ok) {
            if let Ok(vendor) = fs::read_to_string(entry) {
                if vendor.trim().to_lowercase() == "0x10de" {
                    return (format!("eDP-1 → {} (Discrete)", gpu_name), true, gpu_name, igpu_name);
                }
            }
        }
    }
    if let Ok(entries) = glob::glob("/sys/class/drm/card[0-9]*-*eDP-1*/device/device/vendor") {
        for entry in entries.filter_map(Result::ok) {
            if let Ok(vendor) = fs::read_to_string(entry) {
                if vendor.trim().to_lowercase() == "0x10de" {
                    return (format!("eDP-1 → {} (Discrete)", gpu_name), true, gpu_name, igpu_name);
                }
            }
        }
    }
    (format!("eDP-1 → {} (Hybrid)", igpu_name), false, gpu_name, igpu_name)
}

pub fn build_page() -> gtk::Box {
    let page = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .spacing(18)
        .build();

    let drv_version = get_nvidia_driver_version();
    let (disp_info, is_discrete_active, gpu_name, igpu_name) = detect_active_display_gpu();

    // ── Header ───────────────────────────────────────────────
    let hdr = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .spacing(4)
        .margin_bottom(4)
        .build();
    hdr.append(&gtk::Label::builder()
        .label(i18n::t("title_mux"))
        .css_classes(["page-title"])
        .halign(gtk::Align::Start)
        .build());
    hdr.append(&gtk::Label::builder()
        .label(i18n::t("mux_desc"))
        .css_classes(["os-section-desc"])
        .halign(gtk::Align::Start)
        .build());
    page.append(&hdr);

    // ── 2 Main Selection Cards ────────────────────────────────
    let modes_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .spacing(16)
        .homogeneous(true)
        .build();

    // 1. Hybrid Card
    let (btn_hybrid, wrap_hybrid) = build_simple_mux_card(
        &crate::asset_resolver::get_asset_path("balanced.svg"),
        i18n::t("hybrid_title"),
        i18n::t("hybrid_mode"),
        i18n::t("hybrid_desc"),
    );

    // 2. Discrete Card
    let (btn_discrete, wrap_discrete) = build_simple_mux_card(
        &crate::asset_resolver::get_asset_path("performance.svg"),
        i18n::t("discrete_title"),
        i18n::t("discrete_mode"),
        i18n::t("discrete_desc"),
    );

    btn_discrete.set_group(Some(&btn_hybrid));
    if is_discrete_active {
        btn_discrete.set_active(true);
    } else {
        btn_hybrid.set_active(true);
    }

    modes_box.append(&wrap_hybrid);
    modes_box.append(&wrap_discrete);
    page.append(&modes_box);

    // ── Reboot Warning Card ───────────────────────────────────
    let warn_card = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .spacing(12)
        .css_classes(["os-card"])
        .margin_top(4)
        .visible(false)
        .build();

    let warn_icon = gtk::Image::builder()
        .icon_name("dialog-warning-symbolic")
        .pixel_size(20)
        .valign(gtk::Align::Center)
        .build();
    warn_card.append(&warn_icon);

    let warn_txt = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .spacing(2)
        .hexpand(true)
        .build();
    warn_txt.append(&gtk::Label::builder()
        .label(i18n::t("restart_required"))
        .css_classes(["chip-title"])
        .halign(gtk::Align::Start)
        .build());
    warn_txt.append(&gtk::Label::builder()
        .label(i18n::t("restart_desc"))
        .css_classes(["os-section-desc"])
        .halign(gtk::Align::Start)
        .build());
    warn_card.append(&warn_txt);

    let reboot_btn = gtk::Button::builder()
        .label(i18n::t("restart_now"))
        .css_classes(["suggested-action"])
        .valign(gtk::Align::Center)
        .build();
    warn_card.append(&reboot_btn);
    page.append(&warn_card);

    // ── GPU & Display Details ─────────────────────────────────
    let info_group = adw::PreferencesGroup::builder()
        .title(i18n::t("gpu_details_group"))
        .build();

    let disp_row = adw::ActionRow::builder()
        .title(i18n::t("disp_out_row"))
        .subtitle(i18n::t("disp_out_sub"))
        .build();
    let disp_val = gtk::Label::builder()
        .label(&disp_info)
        .css_classes(if is_discrete_active { ["badge-warn"] } else { ["badge-ok"] })
        .valign(gtk::Align::Center)
        .build();
    disp_row.add_suffix(&disp_val);
    info_group.add(&disp_row);

    let specs = crate::daemon_client::get_hardware_specs_sync();

    let gpu_row = adw::ActionRow::builder()
        .title(i18n::t("active_gpu"))
        .subtitle(i18n::t("dgpu_sub"))
        .build();
    let gpu_val = gtk::Label::builder()
        .label(&specs.gpu_spec)
        .css_classes(["os-section-desc"])
        .valign(gtk::Align::Center)
        .build();
    gpu_row.add_suffix(&gpu_val);
    info_group.add(&gpu_row);

    let drv_row = adw::ActionRow::builder()
        .title(i18n::t("driver_ver"))
        .subtitle(i18n::t("driver_sub"))
        .build();
    let drv_val = gtk::Label::builder()
        .label(&drv_version)
        .css_classes(["os-section-desc"])
        .valign(gtk::Align::Center)
        .build();
    drv_row.add_suffix(&drv_val);
    info_group.add(&drv_row);

    page.append(&info_group);

    // Wire MUX toggles to daemon
    let w_c = warn_card.clone();
    let d_val = disp_val.clone();
    let gpu_n1 = gpu_name.clone();
    btn_discrete.connect_toggled(move |btn| {
        if btn.is_active() {
            crate::daemon_client::set_gpu_mode_sync("discrete".to_string());
            if !is_discrete_active {
                w_c.set_visible(true);
            }
            d_val.set_label(&format!("eDP-1 → {} (Discrete)", gpu_n1));
            d_val.set_css_classes(&["badge-warn"]);
        }
    });

    let w_c2 = warn_card.clone();
    let d_val2 = disp_val.clone();
    let igpu_n1 = igpu_name.clone();
    btn_hybrid.connect_toggled(move |btn| {
        if btn.is_active() {
            crate::daemon_client::set_gpu_mode_sync("hybrid".to_string());
            if is_discrete_active {
                w_c2.set_visible(true);
            }
            d_val2.set_label(&format!("eDP-1 → {} (Hybrid)", igpu_n1));
            d_val2.set_css_classes(&["badge-ok"]);
        }
    });

    let bd_load = btn_discrete.clone();
    let bh_load = btn_hybrid.clone();
    glib::spawn_future_local(async move {
        if let Ok(json) = crate::daemon_client::get_gpu_info_async().await {
            if let Ok(info) = serde_json::from_str::<serde_json::Value>(&json) {
                if let Some(mode) = info.get("mode").and_then(|v| v.as_str()) {
                    if mode == "discrete" {
                        bd_load.set_active(true);
                    } else if mode == "hybrid" {
                        bh_load.set_active(true);
                    }
                }
            }
        }
    });

    page
}

/// Simple, modern rectangular MUX card.
fn build_simple_mux_card(
    icon_path: &str,
    title: &str,
    subtitle: &str,
    desc: &str,
) -> (gtk::ToggleButton, gtk::Box) {
    let btn = gtk::ToggleButton::builder()
        .css_classes(["chip-card"])
        .build();

    let inner = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .spacing(10)
        .halign(gtk::Align::Fill)
        .valign(gtk::Align::Center)
        .build();

    let top_row = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .spacing(12)
        .build();

    top_row.append(&gtk::Image::builder().file(icon_path).pixel_size(28).build());

    let text_col = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .spacing(2)
        .hexpand(true)
        .valign(gtk::Align::Center)
        .build();
    text_col.append(&gtk::Label::builder()
        .label(title)
        .css_classes(["chip-title"])
        .halign(gtk::Align::Start)
        .build());
    text_col.append(&gtk::Label::builder()
        .label(subtitle)
        .css_classes(["chip-sub"])
        .halign(gtk::Align::Start)
        .build());
    top_row.append(&text_col);
    inner.append(&top_row);

    inner.append(&gtk::Label::builder()
        .label(desc)
        .css_classes(["os-section-desc"])
        .halign(gtk::Align::Start)
        .wrap(true)
        .build());

    btn.set_child(Some(&inner));

    let wrap = gtk::Box::builder().orientation(gtk::Orientation::Vertical).build();
    wrap.append(&btn);
    (btn, wrap)
}
