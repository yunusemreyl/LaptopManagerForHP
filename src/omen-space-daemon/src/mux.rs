#![allow(dead_code)]
#![allow(unused_imports)]
/// MUX (GPU Switch) service - matches Python mux_service.py feature-for-feature.
///
/// D-Bus interface: com.yyl.hpmanager.mux (backward compat) +
///                  org.hp.omen.Mux (new canonical name)
///
/// Methods exposed:
///   SetGpuMode(mode: s)  -> result: s   ("OK_REBOOT_REQUIRED" or "FAIL")
///   GetGpuInfo()         -> j: s        (JSON with mode, backend, displays)
///   SetMuxBackend(backend: s) -> result: s
///   Ping()               -> resp: s
use serde::{Deserialize, Serialize};
use std::path::Path;
use std::sync::Arc;
use tokio::sync::Mutex;
use zbus::interface;
use log::{info, warn};
use glob::glob;

const HP_WMI_GRAPHICS_MODE_PATH: &str = "/sys/devices/platform/hp-wmi/gpu_mux_mode";
const CONFIG_PATH: &str = "/etc/omen-space/mux.json";

#[derive(Serialize, Deserialize, Debug, Clone)]
struct MuxConfig {
    mux_backend: String,
}

impl Default for MuxConfig {
    fn default() -> Self {
        Self { mux_backend: "auto".to_string() }
    }
}

impl MuxConfig {
    fn load() -> Self {
        if let Ok(data) = std::fs::read_to_string(CONFIG_PATH) {
            serde_json::from_str(&data).unwrap_or_default()
        } else {
            Self::default()
        }
    }
    fn save(&self) {
        if let Some(dir) = Path::new(CONFIG_PATH).parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        if let Ok(json) = serde_json::to_string_pretty(self) {
            let _ = std::fs::write(CONFIG_PATH, json);
        }
    }
}

struct MuxInner {
    config: MuxConfig,
    cached_mode: Option<String>,
    displays_cache: Option<Vec<serde_json::Value>>,
}

#[derive(Clone)]
pub struct MuxService {
    inner: Arc<Mutex<MuxInner>>,
}

impl MuxService {
    pub async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let config = MuxConfig::load();
        let inner = Arc::new(Mutex::new(MuxInner {
            config,
            cached_mode: None,
            displays_cache: None,
        }));
        Ok(Self { inner })
    }

    fn wmi_available() -> bool {
        Path::new(HP_WMI_GRAPHICS_MODE_PATH).exists()
    }

    /// Detect GPU mode — mirrors Python NativeWmiMuxController.get_mode().
    ///
    /// Priority:
    ///   1. DRM eDP connector connected to NVIDIA (vendor=0x10de)  → discrete
    ///   2. lspci: NVIDIA without iGPU                             → discrete
    ///   3. lspci: NVIDIA + iGPU                                   → hybrid
    async fn detect_mode() -> String {
        // 1. DRM eDP check
        if let Ok(entries) = glob("/sys/class/drm/card[0-9]*") {
            for entry in entries.filter_map(Result::ok) {
                let name = entry.file_name()
                    .and_then(|n| n.to_str()).unwrap_or("").to_uppercase();
                if !name.contains("EDP") { continue; }
                let status_path = entry.join("status");
                if let Ok(status) = tokio::fs::read_to_string(&status_path).await {
                    if status.trim() != "connected" { continue; }
                    let driver_path = entry.join("device/device/driver");
                    if let Ok(target) = tokio::fs::read_link(&driver_path).await {
                        let target_str = target.to_string_lossy().to_lowercase();
                        if target_str.contains("nvidia") || target_str.contains("nouveau") {
                            return "discrete".to_string();
                        }
                    }
                }
            }
        }

        // 2. Sysfs driver check (replaces lspci -D to prevent waking dGPU from D3cold)
        let mut has_nvidia = false;
        let mut has_igpu = false;
        
        for driver in &["nvidia", "nouveau"] {
            if let Ok(entries) = glob(&format!("/sys/bus/pci/drivers/{}/*", driver)) {
                for entry in entries.filter_map(Result::ok) {
                    if entry.file_name().and_then(|n| n.to_str()).map_or(false, |s| s.contains(':')) {
                        has_nvidia = true;
                    }
                }
            }
        }
        for driver in &["amdgpu", "i915", "xe"] {
            if let Ok(entries) = glob(&format!("/sys/bus/pci/drivers/{}/*", driver)) {
                for entry in entries.filter_map(Result::ok) {
                    if entry.file_name().and_then(|n| n.to_str()).map_or(false, |s| s.contains(':')) {
                        has_igpu = true;
                    }
                }
            }
        }
        
        if has_nvidia && !has_igpu { return "discrete".to_string(); }
        if has_nvidia && has_igpu  { return "hybrid".to_string(); }

        "unknown".to_string()
    }

    /// Enumerate connected displays with GPU vendor — mirrors Python _get_displays().
    async fn get_displays() -> Vec<serde_json::Value> {
        let mut result = Vec::new();

        if let Ok(entries) = glob("/sys/class/drm/card[0-9]*-*") {
            for entry in entries.filter_map(Result::ok) {
                let status_path = entry.join("status");
                if let Ok(status) = tokio::fs::read_to_string(&status_path).await {
                    if status.trim() != "connected" { continue; }
                    let driver_path = entry.join("device/device/driver");
                    let mut gpu_vendor = "Unknown";
                    if let Ok(target) = tokio::fs::read_link(&driver_path).await {
                        let target_str = target.to_string_lossy().to_lowercase();
                        if target_str.contains("nvidia") || target_str.contains("nouveau") {
                            gpu_vendor = "NVIDIA";
                        } else if target_str.contains("i915") || target_str.contains("xe") {
                            gpu_vendor = "Intel";
                        } else if target_str.contains("amdgpu") || target_str.contains("radeon") {
                            gpu_vendor = "AMD";
                        }
                    }

                    if let Some(name) = entry.file_name().and_then(|n| n.to_str()) {
                        let disp_name = name.split('-').skip(1).collect::<Vec<_>>().join("-");
                        result.push(serde_json::json!({
                            "display": disp_name,
                            "gpu": gpu_vendor
                        }));
                    }
                }
            }
        }
        result
    }
}

#[interface(name = "org.hp.omen.Mux")]
impl MuxService {
    /// SetGpuMode — mirrors Python MUXService.SetGpuMode().
    async fn set_gpu_mode(&self, mode: String) -> String {
        let valid = ["hybrid", "discrete", "advanced"];
        if !valid.contains(&mode.as_str()) {
            return "FAIL".to_string();
        }

        if !Self::wmi_available() {
            warn!("SetGpuMode: WMI MUX interface not found at {}", HP_WMI_GRAPHICS_MODE_PATH);
            return "Error: WMI MUX interface not found".to_string();
        }

        let val = if mode == "discrete" { "1" } else if mode == "advanced" { "2" } else { "0" };
        if tokio::fs::write(HP_WMI_GRAPHICS_MODE_PATH, val).await.is_ok() {
            {
                let mut g = self.inner.lock().await;
                g.cached_mode = Some(mode.clone());
            }
            info!("SetGpuMode: '{}' written to WMI sysfs", mode);
            "OK_REBOOT_REQUIRED".to_string()
        } else {
            warn!("SetGpuMode: Failed to write to {}", HP_WMI_GRAPHICS_MODE_PATH);
            "Error: Failed to write to WMI sysfs".to_string()
        }
    }

    /// GetGpuInfo — mirrors Python MUXService.GetGpuInfo().
    async fn get_gpu_info(&self) -> String {
        let g = self.inner.lock().await;
        let available = Self::wmi_available();
        let backend = if available { "wmi-native" } else { "none" };
        let available_backends: Vec<&str> = if available { vec!["wmi-native"] } else { vec![] };
        let forced_backend = g.config.mux_backend.clone();
        drop(g);

        let mode = Self::detect_mode().await;
        let displays = Self::get_displays().await;

        let json = serde_json::json!({
            "available": available,
            "backend": backend,
            "available_backends": available_backends,
            "forced_backend": forced_backend,
            "mode": mode,
            "displays": displays,
        });
        json.to_string()
    }

    /// SetMuxBackend — mirrors Python MUXService.SetMuxBackend().
    async fn set_mux_backend(&self, backend: String) -> String {
        if backend != "auto" && backend != "wmi-native" {
            return "FAIL".to_string();
        }
        let mut g = self.inner.lock().await;
        g.config.mux_backend = backend.clone();
        g.config.save();
        info!("SetMuxBackend: '{}'", backend);
        "OK".to_string()
    }

    async fn ping(&self) -> String {
        "OK".to_string()
    }
}
