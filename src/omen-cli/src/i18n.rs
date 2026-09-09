use std::fs;
use std::path::PathBuf;
use serde::Deserialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Language {
    Auto,
    Tr,
    En,
}

#[derive(Debug, Clone, Deserialize)]
struct GuiConfig {
    #[serde(default)]
    language: String,
}

pub fn get_language() -> Language {
    let mut selected = Language::Auto;
    if let Some(home) = std::env::var_os("HOME") {
        let mut p = PathBuf::from(home);
        p.push(".config");
        p.push("omenspace");
        p.push("gui_config.json");
        
        if let Ok(content) = fs::read_to_string(&p) {
            if let Ok(cfg) = serde_json::from_str::<GuiConfig>(&content) {
                selected = match cfg.language.as_str() {
                    "tr" => Language::Tr,
                    "en" => Language::En,
                    _ => Language::Auto,
                };
            }
        }
    }

    if selected == Language::Auto {
        for var in &["LC_MESSAGES", "LC_ALL", "LANG", "LANGUAGE"] {
            if let Ok(val) = std::env::var(var) {
                let lower = val.to_lowercase();
                if lower.starts_with("tr") || lower.contains("tr_tr") || lower.contains("turkish") {
                    return Language::Tr;
                }
            }
        }
        Language::En
    } else {
        selected
    }
}

pub fn t(key: &'static str) -> &'static str {
    let lang = get_language();
    match lang {
        Language::Tr => translate_tr(key),
        _ => translate_en(key),
    }
}

fn translate_tr(key: &'static str) -> &'static str {
    match key {
        "ready" => "Hazır. Aşağıya bir komut yazın (örn: 'fan max', 'perf eco')",
        "os" => "İşletim Sistemi",
        "kernel" => "Çekirdek",
        "host" => "Cihaz",
        "power_profile" => "Güç Modu",
        "thermal_fans" => "Sıcaklık/Fanlar",
        "gpu_mux" => "Ekran Kartı MUX",
        "battery_care" => "Pil Sınırı",
        "limit" => "Sınır",
        "conflicts" => "Çakışmalar",
        "clean" => "Temiz",
        "warning" => "Uyarı",
        "usage_fan" => "Kullanım: fan auto | ec | max | <0-100>",
        "usage_perf" => "Kullanım: perf performance | balanced | eco | <pl1 pl2>",
        "usage_mux" => "Kullanım: mux hybrid | discrete | advanced",
        "usage_rgb" => "Kullanım: rgb red | blue | off | <hex>",
        "usage_bat" => "Kullanım: bat <50-100>",
        "usage_uv" => "Kullanım: uv <-100 - 0>",
        
        "fan_changed" => "Fan modu '{}' olarak değiştirildi",
        "fan_error" => "Fan hatası:",
        "fan_set" => "Fan hızı %{} olarak ayarlandı (Hedef: {} RPM)",
        "fan_set_failed" => "Fan hızı ayarlanamadı",
        "fan_invalid" => "Geçersiz fan modu:",
        "fan_no_service" => "Fan D-Bus servisi kullanılamıyor",

        "perf_perf" => "Güç profili PERFORMANS olarak ayarlandı",
        "perf_bal" => "Güç profili DENGELİ olarak ayarlandı",
        "perf_eco" => "Güç profili TASARRUF olarak ayarlandı",
        "perf_limits" => "CPU Güç Sınırları ayarlandı: PL1={}W / PL2={}W",
        "perf_error" => "Güç profili hatası:",
        "perf_invalid" => "Geçersiz güç profili:",
        "perf_no_service" => "Güç D-Bus servisi kullanılamıyor",

        "bat_set" => "Pil Şarj Sınırı %{} olarak ayarlandı",
        "bat_error" => "Pil sınırı hatası:",
        "bat_no_service" => "Platform D-Bus servisi kullanılamıyor",

        "mux_set" => "GPU MUX Modu '{}' olarak ayarlandı [{}]",
        "mux_error" => "MUX hatası:",
        "mux_invalid" => "Geçersiz MUX modu:",
        "mux_no_service" => "MUX D-Bus servisi kullanılamıyor",
        
        "uv_set" => "CPU Undervolt Ofseti {}mV olarak ayarlandı",
        "uv_error" => "Undervolt hatası:",
        "uv_invalid" => "Geçersiz voltaj ofseti:",

        "rgb_off" => "Klavye RGB aydınlatması KAPATILDI",
        "rgb_on" => "Klavye RGB aydınlatması AÇILDI",
        "rgb_color" => "Klavye RGB rengi #{} olarak ayarlandı",
        "rgb_error" => "RGB hatası:",
        "rgb_invalid" => "Geçersiz RGB komutu veya renk:",
        "rgb_no_service" => "RGB D-Bus servisi kullanılamıyor",

        "cache_cleared" => "Bellek (Page Cache) temizlendi",
        "cache_error" => "Temizleme hatası:",

        "diag_initiated" => "WMI Teşhisi başlatıldı",
        "diag_error" => "Teşhis hatası:",
        "diag_bundle" => "Teşhis paketi oluşturuldu: {}",
        "diag_no_service" => "SysMon D-Bus servisi kullanılamıyor",
        
        "executed" => "'{}' çalıştırıldı",
        "unknown_cmd" => "Bilinmeyen komut:",
        
        _ => key,
    }
}

fn translate_en(key: &'static str) -> &'static str {
    match key {
        "ready" => "Ready. Type command below (e.g. 'fan max', 'perf eco')",
        "os" => "OS",
        "kernel" => "Kernel",
        "host" => "Host",
        "power_profile" => "Power Profile",
        "thermal_fans" => "Thermal/Fans",
        "gpu_mux" => "GPU MUX",
        "battery_care" => "Battery Care",
        "limit" => "Limit",
        "conflicts" => "Conflicts",
        "clean" => "Clean",
        "warning" => "Warning",
        "usage_fan" => "Usage: fan auto | ec | max | <0-100>",
        "usage_perf" => "Usage: perf performance | balanced | eco | <pl1 pl2>",
        "usage_mux" => "Usage: mux hybrid | discrete | advanced",
        "usage_rgb" => "Usage: rgb red | blue | off | <hex>",
        "usage_bat" => "Usage: bat <50-100>",
        "usage_uv" => "Usage: uv <-100 - 0>",
        
        "fan_changed" => "Fan mode changed to '{}'",
        "fan_error" => "Fan error:",
        "fan_set" => "Fan speed set to {}% (Target: {} RPM)",
        "fan_set_failed" => "Fan speed set failed",
        "fan_invalid" => "Invalid fan mode:",
        "fan_no_service" => "Fan D-Bus service unavailable",

        "perf_perf" => "Power profile set to PERFORMANCE",
        "perf_bal" => "Power profile set to BALANCED",
        "perf_eco" => "Power profile set to ECO / POWER SAVER",
        "perf_limits" => "CPU Power Limits set to PL1={}W / PL2={}W",
        "perf_error" => "Power error:",
        "perf_invalid" => "Invalid power profile:",
        "perf_no_service" => "Power D-Bus service unavailable",

        "bat_set" => "Battery Charge Limit set to {}%",
        "bat_error" => "Battery limit error:",
        "bat_no_service" => "Platform D-Bus service unavailable",

        "mux_set" => "GPU MUX Mode set to '{}' [{}]",
        "mux_error" => "MUX error:",
        "mux_invalid" => "Invalid MUX mode:",
        "mux_no_service" => "MUX D-Bus service unavailable",
        
        "uv_set" => "CPU Undervolt Offset set to {}mV",
        "uv_error" => "Undervolt error:",
        "uv_invalid" => "Invalid voltage offset:",

        "rgb_off" => "Keyboard RGB turned OFF",
        "rgb_on" => "Keyboard RGB turned ON",
        "rgb_color" => "Keyboard RGB Color set to #{}",
        "rgb_error" => "RGB error:",
        "rgb_invalid" => "Invalid RGB command or color:",
        "rgb_no_service" => "RGB D-Bus service unavailable",

        "cache_cleared" => "Memory page cache cleared",
        "cache_error" => "Cache clear error:",

        "diag_initiated" => "WMI Diagnostics initiated",
        "diag_error" => "Diagnostic error:",
        "diag_bundle" => "Triage bundle created: {}",
        "diag_no_service" => "SysMon D-Bus service unavailable",
        
        "executed" => "Executed '{}'",
        "unknown_cmd" => "Unknown command:",
        
        _ => key,
    }
}
