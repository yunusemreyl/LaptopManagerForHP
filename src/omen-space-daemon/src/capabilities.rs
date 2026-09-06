#![allow(dead_code)]
#![allow(unused_imports)]
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub enum LinuxCapabilityClass {
    FullControl,
    ProfileOnly,
    TelemetryOnly,
    UnsupportedControl,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct LinuxCapabilityAssessment {
    pub capability_class: LinuxCapabilityClass,
    pub supports_manual_fan_control: bool,
    pub supports_profile_control: bool,
    pub supports_telemetry: bool,
    pub reason: String,
}

impl LinuxCapabilityAssessment {
    pub fn capability_key(&self) -> &str {
        match self.capability_class {
            LinuxCapabilityClass::FullControl => "full-control",
            LinuxCapabilityClass::ProfileOnly => "profile-only",
            LinuxCapabilityClass::TelemetryOnly => "telemetry-only",
            LinuxCapabilityClass::UnsupportedControl => "unsupported-control",
        }
    }
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ModelCapabilities {
    pub product_id: String,
    pub model_name: String,
    pub model_year: u32,
    pub family: String,
    
    // Fan Control
    pub supports_fan_control_wmi: bool,
    pub supports_fan_control_ec: bool,
    pub supports_fan_curves: bool,
    pub supports_independent_fan_curves: bool,
    pub supports_rpm_readback: bool,
    pub fan_zone_count: u32,
    pub max_fan_speed_percent: u32,
    pub min_fan_speed_percent: u32,
    
    // Performance Modes
    pub supports_performance_modes: bool,
    pub performance_modes: Vec<String>,
    pub allow_decoupled_wmi_thermal_policy_fallback: bool,
    
    // GPU
    pub has_mux_switch: bool,
    pub supports_gpu_power_boost: bool,
    pub supports_advanced_optimus: bool,
    
    // Lighting
    pub has_keyboard_backlight: bool,
    pub has_four_zone_rgb: bool,
    pub has_per_key_rgb: bool,
    pub has_light_bar: bool,
    
    // Power / Undervolt
    pub supports_undervolt: bool,
    pub supports_tcc_offset: bool,
    pub supports_power_limits: bool,
    pub supports_battery_care: bool,
    
    // Low-level OS Assessment
    pub linux_assessment: Option<LinuxCapabilityAssessment>,
    
    pub notes: String,
}

impl Default for ModelCapabilities {
    fn default() -> Self {
        Self {
            product_id: "DEFAULT".to_string(),
            model_name: "Unknown HP System".to_string(),
            model_year: 2023,
            family: "HP".to_string(),
            
            supports_fan_control_wmi: true,
            supports_fan_control_ec: false,
            supports_fan_curves: true,
            supports_independent_fan_curves: true,
            supports_rpm_readback: true,
            fan_zone_count: 2,
            max_fan_speed_percent: 100,
            min_fan_speed_percent: 0,
            
            supports_performance_modes: true,
            performance_modes: vec!["Default".to_string(), "Performance".to_string(), "Cool".to_string()],
            allow_decoupled_wmi_thermal_policy_fallback: false,
            
            has_mux_switch: false,
            supports_gpu_power_boost: true,
            supports_advanced_optimus: false,
            
            has_keyboard_backlight: true,
            has_four_zone_rgb: true,
            has_per_key_rgb: false,
            has_light_bar: false,
            
            supports_undervolt: true,
            supports_tcc_offset: true,
            supports_power_limits: true,
            supports_battery_care: true,
            linux_assessment: None,
            
            notes: "".to_string(),
        }
    }
}

pub struct LinuxCapabilityClassifier;

impl LinuxCapabilityClassifier {
    pub fn assess(is_root: bool, board_id: &str, _model: &str) -> LinuxCapabilityAssessment {
        let is_wmaa_abort_prone = Self::is_wmaa_abort_prone_board(board_id);
        
        let has_ec_access = Path::new("/sys/kernel/debug/ec/ec0/io").exists();
        let has_hp_wmi_path = Path::new("/sys/devices/platform/hp-wmi").exists();
        // Check both underscore and hyphen naming (kernel version dependent)
        let has_thermal_profile =
            Path::new("/sys/devices/platform/hp-wmi/thermal_profile").exists() ||
            Path::new("/sys/devices/platform/hp-wmi/thermal-profile").exists();
        let has_platform_profile =
            Path::new("/sys/devices/platform/hp-wmi/platform_profile").exists() ||
            Path::new("/sys/devices/platform/hp-wmi/platform-profile").exists();
        let has_acpi_platform_profile = Path::new("/sys/firmware/acpi/platform_profile").exists();
        let has_fan1_output = Path::new("/sys/devices/platform/hp-wmi/fan1_output").exists();
        let has_fan2_output = Path::new("/sys/devices/platform/hp-wmi/fan2_output").exists();
        
        // Basic hwmon checks
        let mut has_hwmon_fan_access = false;
        if let Ok(entries) = std::fs::read_dir("/sys/class/hwmon") {
            for entry in entries.filter_map(Result::ok) {
                if entry.path().join("pwm1_enable").exists() {
                    has_hwmon_fan_access = true;
                }
            }
        }
        
        let has_manual_fan_control = has_ec_access || has_fan1_output || has_fan2_output;
        let has_profile_control = has_thermal_profile || has_platform_profile || has_acpi_platform_profile || has_hwmon_fan_access;
        let has_telemetry = has_hp_wmi_path || has_manual_fan_control || has_profile_control;
        
        if is_wmaa_abort_prone && has_manual_fan_control {
            let mut reason = "Board 8BCD has field reports of ACPI WMAA/WHCM aborts where WMI-backed fan, RGB, and battery paths can report success without hardware effect. Treat visible manual/profile fan paths as degraded until an effective write/readback check proves control.".to_string();
            if !is_root {
                reason.push_str(" Run with sudo for write/readback validation.");
            }
            return LinuxCapabilityAssessment {
                capability_class: if has_profile_control { LinuxCapabilityClass::ProfileOnly } else { LinuxCapabilityClass::TelemetryOnly },
                supports_manual_fan_control: false,
                supports_profile_control: has_profile_control,
                supports_telemetry: true,
                reason,
            };
        }

        if has_manual_fan_control {
            let mut reason = if has_hwmon_fan_access {
                "Manual fan control is available through hwmon pwm/fan targets."
            } else if has_fan1_output {
                "Manual fan control is available through hp-wmi fan output files."
            } else {
                "Manual fan control is available through legacy EC access."
            }.to_string();
            
            if !is_root {
                reason.push_str(" Run with sudo to use write-capable controls.");
            }
            
            return LinuxCapabilityAssessment {
                capability_class: LinuxCapabilityClass::FullControl,
                supports_manual_fan_control: true,
                supports_profile_control: has_profile_control,
                supports_telemetry: true,
                reason,
            };
        }

        if has_profile_control {
            let mut reason = "Thermal/platform profile control is available, but firmware does not expose manual fan target/output interfaces on this board.".to_string();
            if !is_root {
                reason.push_str(" Run with sudo to apply profile changes.");
            }
            if is_wmaa_abort_prone {
                reason.push_str(" Board 8BCD is currently treated as degraded profile control because field diagnostics show ACPI WMAA/WHCM aborts.");
            }
            
            return LinuxCapabilityAssessment {
                capability_class: LinuxCapabilityClass::ProfileOnly,
                supports_manual_fan_control: false,
                supports_profile_control: true,
                supports_telemetry: true,
                reason,
            };
        }

        if has_telemetry {
            return LinuxCapabilityAssessment {
                capability_class: LinuxCapabilityClass::TelemetryOnly,
                supports_manual_fan_control: false,
                supports_profile_control: false,
                supports_telemetry: true,
                reason: "Telemetry paths are present, but no writable EC, hp-wmi, hwmon target, or platform profile control interface is exposed.".to_string(),
            };
        }

        LinuxCapabilityAssessment {
            capability_class: LinuxCapabilityClass::UnsupportedControl,
            supports_manual_fan_control: false,
            supports_profile_control: false,
            supports_telemetry: false,
            reason: "No supported Linux control interface was detected. This is usually a kernel exposure gap or missing hp-wmi/ec_sys support.".to_string(),
        }
    }

    fn is_wmaa_abort_prone_board(board_id: &str) -> bool {
		// 8BCD: ACPI WMAA/WHCM aborts (field-reported)
		// 8C75: broken GETB zero-length CreateField → AE_AML_BUFFER_LIMIT on all WMID methods
		matches!(board_id.trim().to_uppercase().as_str(), "8BCD" | "8C75")
	}
}

pub fn detect(board_id: &str, product_name: &str, cpu_model: &str) -> ModelCapabilities {
    let mut cap = get_known_model(board_id).or_else(|| {
        let prod_lower = product_name.to_lowercase();
        // Fallback by product name if exact board_id is not found
        get_all_models().iter().find(|m| prod_lower.contains(&m.model_name.to_lowercase())).cloned()
    }).unwrap_or_default();
    
    let cpu_upper = cpu_model.to_uppercase();
    let is_hx = cpu_upper.contains("HX");
    let is_amd = cpu_upper.contains("AMD") || cpu_upper.contains("RYZEN");
    
    if cap.family.to_uppercase().contains("VICTUS") {
        if !is_hx && !is_amd {
            cap.supports_undervolt = false;
            cap.supports_tcc_offset = false;
            cap.supports_power_limits = false;
        }
    }
    cap
}

macro_rules! model {
    ($id:expr, $name:expr, $year:expr, $family:expr, { $($field:ident : $val:expr),* $(,)? }) => {
        {
            let mut m = ModelCapabilities {
                product_id: $id.to_string(),
                model_name: $name.to_string(),
                model_year: $year,
                family: $family.to_string(),
                ..Default::default()
            };
            $(
                m.$field = $val;
            )*
            m
        }
    };
}

fn get_all_models() -> &'static [ModelCapabilities] {
    static MODELS: std::sync::OnceLock<Vec<ModelCapabilities>> = std::sync::OnceLock::new();
    MODELS.get_or_init(|| vec![
        // OMEN 15 Series (2020-2021)
        model!("8A14", "OMEN 15 (2020) Intel", 2020, "OMEN", { has_mux_switch: false, supports_fan_control_ec: true }),
        model!("878C", "OMEN Laptop 15-ek0xxx", 2020, "OMEN", { has_mux_switch: false, supports_fan_control_ec: true, notes: "Direct EC fan control highly recommended when hp-wmi fails".to_string() }),
        model!("878A", "OMEN 15 (2020) AMD", 2020, "OMEN", { has_mux_switch: false, supports_fan_control_ec: true }),
        model!("878A", "OMEN Laptop 15-ek0xxx", 2020, "OMEN", { has_mux_switch: true, supports_fan_control_wmi: true, has_four_zone_rgb: true }),

        // OMEN 16 Series
        model!("8A43", "OMEN by HP Gaming Laptop 16-n0xxx", 2022, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8BAA", "OMEN by HP Gaming Laptop 16-wf0xxx", 2023, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true, supports_fan_control_ec: false }),
        model!("8BAB", "OMEN by HP Gaming Laptop 16-wf0xxx", 2023, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true, supports_fan_control_ec: false }),
        model!("8BAD", "OMEN 16 (2023) Intel", 2023, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8CD1", "OMEN 16 (2023) AMD", 2023, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8C58", "OMEN 16 Transcend", 2024, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8D24", "OMEN 16 (2024)", 2024, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8D26", "OMEN 16 (2024) AMD", 2024, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8BCD", "OMEN by HP Gaming Laptop 16-xd0xxx", 2023, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8E35", "OMEN MAX 16t-ah000", 2025, "OMEN", { has_mux_switch: true, supports_fan_control_ec: true, has_per_key_rgb: true }),
        model!("8E41", "OMEN MAX 16-ah0xxx", 2025, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false, has_per_key_rgb: true }),
        model!("8D88", "OMEN MAX Gaming Laptop 16-ak0xxx", 2025, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false, supports_fan_control_wmi: true, has_per_key_rgb: true }),
        model!("8D87", "OMEN MAX Gaming Laptop 16-ak0xxx", 2025, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false, supports_fan_control_wmi: true, has_per_key_rgb: true, notes: "Ryzen AI 9 HX 375 / RTX 5080. RTX 5080 sibling of 8D88. Requires patched hp-wmi for gpu_tgp/gpu_ppab.".to_string() }),
        model!("8C77", "OMEN by HP Gaming Laptop 16-wf1xxx", 2024, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8C78", "OMEN by HP Gaming Laptop 16-wf1xxx", 2024, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        // Issue #169: 8D41 had no entry — zones are inverted, per-key is present via HID
        model!("8D41", "OMEN MAX Gaming Laptop 16-ah0xxx", 2025, "OMEN", {
            has_mux_switch: true,
            supports_fan_control_ec: false,
            has_per_key_rgb: true,
            notes: "RGB zone order is inverted (Zone 1 is right-most). Per-key RGB via HID.".to_string()
        }),
        
        // OMEN 17 Series
        model!("8BB1", "OMEN 17 / Victus 15", 2023, "OMEN/Victus", { has_mux_switch: true, supports_fan_control_ec: false }),
        // Issue #175: 8C75 has a broken GETB ACPI helper (same as 8BAC) that causes
        // AE_AML_BUFFER_LIMIT on all WMID writes — fans silently stuck at 0 RPM.
        model!("8C75", "OMEN 17-db0xxx", 2024, "OMEN", {
            has_mux_switch: true,
            supports_fan_control_ec: false,
            notes: "Broken GETB ACPI helper (AE_AML_BUFFER_LIMIT on WMID WMBX/WMBA). \
                    Fan writes abort silently; no-EC params applied. Fan may stick at 0 RPM \
                    after an overheat EC reset until driver re-applies thermal profile.".to_string()
        }),
        
        // Victus Series
        model!("88EC", "Victus by HP 16-e0xxx", 2021, "Victus", { has_mux_switch: false, supports_fan_control_ec: true }),
        model!("8934", "Victus by HP 16-e0xxx", 2021, "Victus", { has_mux_switch: false, supports_fan_control_ec: true }),
        model!("8912", "OMEN by HP Laptop 16-c0xxx", 2021, "OMEN", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8A25", "Victus by HP 15-fb0xxx", 2022, "Victus", { has_mux_switch: false, supports_fan_control_ec: true }),
        model!("8A97", "Victus by HP 16-d1xxx", 2022, "Victus", { has_mux_switch: false, supports_fan_control_ec: true }),
        model!("8B19", "Victus by HP 16-r0xxx", 2023, "Victus", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8B1A", "Victus by HP 16-s0xxx", 2023, "Victus", { has_mux_switch: true, supports_fan_control_ec: false }),
        model!("8BBE", "Victus by HP 16-r0xxx", 2023, "Victus", { has_mux_switch: true, supports_fan_control_ec: true }),
        model!("88F8", "Victus by HP Laptop 16-d0xxx", 2023, "Victus", { has_mux_switch: false, supports_fan_control_ec: true }),
        model!("8C9C", "Victus by HP Gaming Laptop 16-s1xxx", 2024, "Victus", { has_mux_switch: true, supports_fan_control_ec: false }),
        
        // Legacy Migrations
        model!("8A15", "OMEN 15 (2020) AMD", 2020, "Legacy", { has_mux_switch: false, supports_fan_control_ec: true, supports_undervolt: false }),
        model!("8574", "OMEN 15-dc1xxx (2019) Intel", 2019, "Legacy", { has_mux_switch: false, supports_fan_control_wmi: false, supports_fan_control_ec: true, supports_gpu_power_boost: true, has_four_zone_rgb: false }),
        model!("8600", "OMEN 15-dh0xxx (2019) Intel", 2019, "Legacy", { has_mux_switch: false, supports_fan_control_wmi: false, supports_fan_control_ec: true, supports_gpu_power_boost: true, has_four_zone_rgb: false }),
        model!("8787", "OMEN 15-en0038ur (2020) AMD", 2020, "Legacy", { has_mux_switch: true, supports_gpu_power_boost: true, supports_undervolt: false }),
        model!("88D2", "OMEN by HP Laptop 15z-en100 (2021) AMD", 2021, "Legacy", { has_mux_switch: false, supports_undervolt: false }),
        model!("8BAF", "OMEN 16 (2021) Intel", 2021, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true }),
        model!("8BB0", "OMEN 16 (2021) AMD", 2021, "OMEN", { has_mux_switch: true, supports_undervolt: false }),
        model!("8CD0", "OMEN 16 (2022) Intel", 2022, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true }),
        model!("8A43", "OMEN 16 (2022) n0xxx AMD", 2022, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true, supports_undervolt: false }),
        model!("8A44", "OMEN 16 (2022) n0xxx AMD", 2022, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true, supports_undervolt: false }),
        model!("8BCA", "OMEN 16 (2023) wf0xxx Intel", 2023, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true }),
        model!("8C76", "OMEN 16 (2024) wf1xxx Intel", 2024, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true }),
        model!("8B2J", "OMEN 16 (2024) xf0xxx Intel", 2024, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true }),
        model!("8D2F", "OMEN 16-am0xxx (8D2F)", 2025, "OMEN", {
            has_mux_switch: true,
            supports_gpu_power_boost: true,
            supports_undervolt: false,
            notes: "thermal_profile sysfs node absent on this board; fan mode uses pwm1 duty only".to_string()
        }),
        model!("8D40", "OMEN Slim 16 (2025) an0xxx", 2025, "OMEN", { has_mux_switch: false, supports_gpu_power_boost: true, has_four_zone_rgb: false, supports_undervolt: false }),
        model!("8A18", "OMEN 17-ck1xxx (2022)", 2022, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true }),
        model!("8C3F", "HP Victus 15-fa1xxx (2022)", 2022, "Victus", { has_mux_switch: false, has_four_zone_rgb: false, supports_undervolt: false }),
        model!("8BB1-VICTUS15", "HP Victus 15-fa1xxx (2022)", 2022, "Victus", { has_mux_switch: false, has_four_zone_rgb: false, supports_undervolt: false }),
        model!("8B9D", "OMEN 17 (2023) Intel", 2023, "OMEN", { has_mux_switch: true, supports_gpu_power_boost: true }),
        model!("17CK2", "OMEN 17-ck2xxx (2023)", 2023, "OMEN", { has_mux_switch: true, supports_fan_control_wmi: false, supports_fan_control_ec: true, supports_gpu_power_boost: true }),
        model!("8B9E", "OMEN 17 (2023) AMD", 2023, "OMEN", { has_mux_switch: true, supports_undervolt: false }),
        model!("8C3A", "OMEN Transcend 14 (2023)", 2023, "Transcend", { has_mux_switch: true, supports_fan_control_wmi: false, supports_fan_control_ec: true, supports_gpu_power_boost: true, has_four_zone_rgb: false }),
        model!("8C3B", "OMEN Transcend 16 (2023)", 2023, "Transcend", { has_mux_switch: true, supports_fan_control_wmi: false, supports_fan_control_ec: true, has_four_zone_rgb: false }),
        // Issue #168: 88F7 had no entry
        model!("88F7", "OMEN by HP Laptop 17-ck0xxx", 2021, "OMEN", {
            has_mux_switch: true,
            supports_fan_control_ec: false,
            has_four_zone_rgb: true,
            notes: "RGB power-off state must persist across reboots; startup applies saved config".to_string()
        }),
        model!("88D9", "HP Victus 15 (2022) Intel", 2022, "Victus", { has_mux_switch: false, has_four_zone_rgb: false }),
        model!("88DA", "HP Victus 15 (2022) AMD", 2022, "Victus", { has_mux_switch: false, has_four_zone_rgb: false, supports_undervolt: false }),
        model!("8A3E", "HP Victus 15 (2022) fb0xxx AMD", 2022, "Victus", { has_mux_switch: false, has_four_zone_rgb: false, supports_undervolt: false }),
        model!("8DCD", "HP Victus 15 (8DCD)", 2024, "Victus", { has_mux_switch: false, has_four_zone_rgb: false, supports_undervolt: false }),
        model!("8A26", "HP Victus 16 (2023/2024) d1xxx", 2023, "Victus", { has_mux_switch: false, supports_undervolt: false }),
        model!("8BD4", "HP Victus 16-s0xxx AMD", 2023, "Victus", { has_mux_switch: false, supports_undervolt: false }),
        model!("8C2F", "HP Victus 15/16 (2024+) Ryzen (shared board)", 2024, "Victus", { has_mux_switch: false, supports_undervolt: false }),
        model!("88DB", "HP Victus 16 (2022)", 2022, "Victus", { has_mux_switch: false, supports_undervolt: false }),
        model!("88EE", "HP Victus 16-e0194nw", 2022, "Victus", { has_mux_switch: false, has_four_zone_rgb: false, supports_undervolt: false }),
        model!("DESKTOP-25L", "OMEN 25L Desktop", 2021, "Desktop", { has_mux_switch: false, supports_fan_control_wmi: false, has_four_zone_rgb: false }),
        model!("DESKTOP-30L", "OMEN 30L Desktop", 2022, "Desktop", { has_mux_switch: false, supports_fan_control_wmi: false, has_four_zone_rgb: false }),
        model!("DESKTOP-35L", "OMEN 35L Desktop", 2023, "Desktop", { has_mux_switch: false, supports_fan_control_wmi: false, has_four_zone_rgb: false }),
        model!("DESKTOP-40L", "OMEN 40L Desktop", 2023, "Desktop", { has_mux_switch: false, supports_fan_control_wmi: false, has_four_zone_rgb: false }),
        model!("DESKTOP-45L", "OMEN 45L Desktop", 2023, "Desktop", { has_mux_switch: false, supports_fan_control_wmi: false, has_four_zone_rgb: false }),
    ])
}

fn get_known_model(board_id: &str) -> Option<ModelCapabilities> {
    let id_upper = board_id.to_uppercase();
    get_all_models().iter().find(|m| m.product_id == id_upper).cloned()
}
