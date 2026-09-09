use evdev::{Device, Key};
use futures::StreamExt;
use log::info;
use zbus::Connection;

pub struct HotkeyMonitor;

impl HotkeyMonitor {
    pub fn start(connection: Connection) {
        tokio::spawn(async move {
            Self::monitor_loop(connection).await;
        });
    }

    async fn monitor_loop(connection: Connection) {
        loop {
            let mut streams = Vec::new();
            if let Ok(mut dir) = tokio::fs::read_dir("/dev/input").await {
                while let Ok(Some(entry)) = dir.next_entry().await {
                    let path = entry.path();
                    if path.to_string_lossy().contains("event") {
                        if let Ok(dev) = Device::open(&path) {
                            let name = dev.name().unwrap_or("").to_lowercase();
                            let has_target_keys = dev.supported_keys().map_or(false, |k| k.contains(Key::KEY_PROG1) || k.contains(Key::KEY_PROG2) || k.contains(Key::KEY_CALC));
                            let is_likely_hp = name.contains("hp") || name.contains("omen") || name.contains("keyboard");
                            if has_target_keys && is_likely_hp {
                                if let Ok(stream) = dev.into_event_stream() {
                                    info!("HotkeyMonitor: listening to {:?}", path);
                                    streams.push(stream);
                                }
                            }
                        }
                    }
                }
            }

            if streams.is_empty() {
                tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
                continue;
            }

            let mut select_all = futures::stream::select_all(streams);

            while let Some(Ok(event)) = select_all.next().await {
                if let evdev::InputEventKind::Key(key) = event.kind() {
                    if event.value() == 1 { // Key press
                        let key_code = key.code();
                        // 148 = KEY_PROG1 (Omen Key mapped by hwdb)
                        // 149 = KEY_PROG2 (P1/P2/Macro)
                        // 140 = KEY_CALC (Calculator)
                        let key_name = match key_code {
                            148 => Some("omen"),
                            149 => Some("prog2"),
                            140 => Some("calc"),
                            256 => Some("prog3"),
                            _ => None,
                        };

                        if let Some(name) = key_name {
                            info!("HotkeyMonitor: Detected Macro Key Press: {}", name);
                            // We can emit a DBus signal directly using zbus connection
                            // but PlatformService is the interface. We must call PlatformService::macro_key_pressed
                            // Wait, the easiest way to emit a signal on an object path without an interface wrapper 
                            // is to use Connection::emit_signal.
                            let _ = connection.emit_signal(
                                None::<&str>, // destination
                                "/org/hp/omen/Platform",
                                "org.hp.omen.Platform",
                                "MacroKeyPressed",
                                &(name),
                            ).await;
                        }
                    }
                }
            }

            // If we break out (e.g. devices disconnected), wait and restart
            tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
        }
    }
}
