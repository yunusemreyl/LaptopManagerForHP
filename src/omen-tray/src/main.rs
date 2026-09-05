use ksni::menu::{CheckmarkItem, StandardItem, SubMenu};
use ksni::MenuItem;
use log::{error, info, warn};
use std::fs::OpenOptions;
use std::os::unix::io::AsRawFd;
use std::process::Command;
use std::sync::OnceLock;
use zbus::{Connection, Result as ZbusResult};

static RUNTIME: OnceLock<tokio::runtime::Handle> = OnceLock::new();

fn acquire_single_instance_lock() -> Option<std::fs::File> {
    let runtime_dir = std::env::var("XDG_RUNTIME_DIR")
        .unwrap_or_else(|_| format!("/tmp/user-{}", unsafe { libc::getuid() }));
    let _ = std::fs::create_dir_all(&runtime_dir);
    let lock_path = format!("{}/omen-tray.lock", runtime_dir);

    let file = match OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(&lock_path)
    {
        Ok(f) => f,
        Err(e) => {
            warn!("Kilit dosyası açılamadı ({}): {}, tekillik kontrolü atlanıyor.", lock_path, e);
            return None;
        }
    };

    let fd = file.as_raw_fd();
    let res = unsafe { libc::flock(fd, libc::LOCK_EX | libc::LOCK_NB) };
    if res != 0 {
        return None;
    }

    Some(file)
}

fn spawn_task<F>(f: F)
where
    F: std::future::Future<Output = ()> + Send + 'static,
{
    if let Some(handle) = RUNTIME.get() {
        handle.spawn(f);
    } else {
        error!("Tokio runtime handle is not initialized");
    }
}

#[derive(Debug, Clone)]
struct Tray {
    power_profile: String,
    fan_mode: String,
}

impl ksni::Tray for Tray {
    fn id(&self) -> String {
        "omenspace_tray".into()
    }

    fn category(&self) -> ksni::Category {
        ksni::Category::Hardware
    }

    fn status(&self) -> ksni::Status {
        ksni::Status::Active
    }

    fn icon_name(&self) -> String {
        "omenspace".into()
    }

    fn icon_theme_path(&self) -> String {
        "/usr/share/omen-space/assets".into()
    }

    fn title(&self) -> String {
        "OMEN SPACE".into()
    }

    fn tool_tip(&self) -> ksni::ToolTip {
        let p_label = match self.power_profile.as_str() {
            "performance" => "Performans",
            "power-saver" | "eco" => "Eko",
            _ => "Dengeli",
        };
        let f_label = match self.fan_mode.as_str() {
            "max" => "Maksimum",
            "ec" => "EC (Donanım)",
            "custom" => "Özel",
            _ => "Otomatik",
        };
        ksni::ToolTip {
            title: "OMEN Space".into(),
            description: format!("Güç: {}\nFan: {}", p_label, f_label),
            icon_name: "omenspace".into(),
            ..Default::default()
        }
    }

    fn activate(&mut self, _x: i32, _y: i32) {
        let _ = Command::new("omen-gui").spawn();
    }

    fn menu(&self) -> Vec<ksni::MenuItem<Self>> {
        let cur_power = self.power_profile.as_str();
        let cur_fan = self.fan_mode.as_str();

        vec![
            StandardItem {
                label: "OMENSpace'i Aç".into(),
                icon_name: "omenspace".into(),
                activate: Box::new(|_| {
                    let _ = Command::new("omen-gui").spawn();
                }),
                ..Default::default()
            }
            .into(),
            MenuItem::Separator,
            SubMenu {
                label: "⚡ Güç Profili".into(),
                submenu: vec![
                    CheckmarkItem {
                        label: "🔥 Performans".into(),
                        checked: cur_power == "performance",
                        activate: Box::new(|tray: &mut Self| {
                            tray.power_profile = "performance".into();
                            spawn_task(async {
                                set_power_profile("performance").await;
                            });
                        }),
                        ..Default::default()
                    }
                    .into(),
                    CheckmarkItem {
                        label: "⚖️ Dengeli".into(),
                        checked: cur_power == "balanced",
                        activate: Box::new(|tray: &mut Self| {
                            tray.power_profile = "balanced".into();
                            spawn_task(async {
                                set_power_profile("balanced").await;
                            });
                        }),
                        ..Default::default()
                    }
                    .into(),
                    CheckmarkItem {
                        label: "🍃 Eko".into(),
                        checked: cur_power == "power-saver" || cur_power == "eco",
                        activate: Box::new(|tray: &mut Self| {
                            tray.power_profile = "power-saver".into();
                            spawn_task(async {
                                set_power_profile("power-saver").await;
                            });
                        }),
                        ..Default::default()
                    }
                    .into(),
                ],
                ..Default::default()
            }
            .into(),
            SubMenu {
                label: "❄️ Fan Modu".into(),
                submenu: vec![
                    CheckmarkItem {
                        label: "🤖 Otomatik".into(),
                        checked: cur_fan == "auto",
                        activate: Box::new(|tray: &mut Self| {
                            tray.fan_mode = "auto".into();
                            spawn_task(async {
                                set_fan_mode("auto").await;
                            });
                        }),
                        ..Default::default()
                    }
                    .into(),
                    CheckmarkItem {
                        label: "🌪️ Maksimum".into(),
                        checked: cur_fan == "max",
                        activate: Box::new(|tray: &mut Self| {
                            tray.fan_mode = "max".into();
                            spawn_task(async {
                                set_fan_mode("max").await;
                            });
                        }),
                        ..Default::default()
                    }
                    .into(),
                    CheckmarkItem {
                        label: "⚙️ EC (Donanım)".into(),
                        checked: cur_fan == "ec",
                        activate: Box::new(|tray: &mut Self| {
                            tray.fan_mode = "ec".into();
                            spawn_task(async {
                                set_fan_mode("ec").await;
                            });
                        }),
                        ..Default::default()
                    }
                    .into(),
                ],
                ..Default::default()
            }
            .into(),
            MenuItem::Separator,
            StandardItem {
                label: "❌ Çıkış".into(),
                icon_name: "application-exit".into(),
                activate: Box::new(|_| {
                    let _ = Command::new("pkill")
                        .arg("-TERM")
                        .arg("-x")
                        .arg("omen-gui")
                        .output();
                    std::process::exit(0);
                }),
                ..Default::default()
            }
            .into(),
        ]
    }
}

#[zbus::proxy(
    interface = "org.hp.omen.Power",
    default_service = "org.hp.omen",
    default_path = "/org/hp/omen/Power"
)]
trait Power {
    async fn set_power_profile(&self, profile: &str) -> zbus::Result<String>;
    async fn get_power_profile(&self) -> zbus::Result<String>;
}

#[zbus::proxy(
    interface = "org.hp.omen.Fan",
    default_service = "org.hp.omen",
    default_path = "/org/hp/omen/Fan"
)]
trait Fan {
    async fn set_fan_mode(&self, mode: &str) -> zbus::Result<String>;
    async fn get_fan_mode(&self) -> zbus::Result<String>;
}

async fn get_conn() -> ZbusResult<Connection> {
    Connection::system().await
}

async fn fetch_power_profile() -> Option<String> {
    if let Ok(conn) = get_conn().await {
        if let Ok(proxy) = PowerProxy::new(&conn).await {
            if let Ok(json_str) = proxy.get_power_profile().await {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&json_str) {
                    if let Some(active) = val.get("active").and_then(|v| v.as_str()) {
                        return Some(active.to_string());
                    }
                }
            }
        }
    }
    None
}

async fn fetch_fan_mode() -> Option<String> {
    if let Ok(conn) = get_conn().await {
        if let Ok(proxy) = FanProxy::new(&conn).await {
            if let Ok(mode) = proxy.get_fan_mode().await {
                return Some(mode.trim().to_string());
            }
        }
    }
    None
}

async fn set_power_profile(profile: &str) {
    if let Ok(conn) = get_conn().await {
        if let Ok(proxy) = PowerProxy::new(&conn).await {
            match proxy.set_power_profile(profile).await {
                Ok(resp) => info!("Güç profili ayarlandı ({}) -> {}", profile, resp),
                Err(e) => error!("Güç profili değiştirilemedi: {}", e),
            }
        }
    }
}

async fn set_fan_mode(mode: &str) {
    if let Ok(conn) = get_conn().await {
        if let Ok(proxy) = FanProxy::new(&conn).await {
            match proxy.set_fan_mode(mode).await {
                Ok(resp) => info!("Fan modu ayarlandı ({}) -> {}", mode, resp),
                Err(e) => error!("Fan modu değiştirilemedi: {}", e),
            }
        }
    }
}

#[tokio::main]
async fn main() {
    env_logger::init();
    info!("omen-tray başlatılıyor...");

    let _lock = match acquire_single_instance_lock() {
        Some(lock) => lock,
        None => {
            info!("omen-tray zaten çalışıyor. İkinci kopya sonlandırılıyor.");
            return;
        }
    };

    RUNTIME
        .set(tokio::runtime::Handle::current())
        .expect("Failed to initialize runtime handle");

    let initial_power = fetch_power_profile().await.unwrap_or_else(|| "balanced".into());
    let initial_fan = fetch_fan_mode().await.unwrap_or_else(|| "auto".into());

    let tray = Tray {
        power_profile: initial_power,
        fan_mode: initial_fan,
    };

    let service = ksni::TrayService::new(tray);
    let handle = service.handle();
    service.spawn();

    loop {
        tokio::time::sleep(std::time::Duration::from_secs(3)).await;
        let p = fetch_power_profile().await;
        let f = fetch_fan_mode().await;
        if p.is_some() || f.is_some() {
            handle.update(|tray| {
                if let Some(new_p) = p {
                    tray.power_profile = new_p;
                }
                if let Some(new_f) = f {
                    tray.fan_mode = new_f;
                }
            });
        }
    }
}
