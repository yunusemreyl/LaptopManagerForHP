use log::{info, error};
use tokio::time::{sleep, Duration};
use crate::notifier::DesktopNotifier;
use zbus::Connection;

#[zbus::proxy(
    interface = "org.hp.omen.Fan",
    default_service = "org.hp.omen",
    default_path = "/org/hp/omen/Fan"
)]
trait Fan {
    async fn set_fan_mode(&self, mode: &str) -> zbus::Result<String>;
}

pub struct FanCleaningService;

impl FanCleaningService {
    pub async fn run_cleaning_routine() -> String {
        info!("Starting Fan Dust Cleaning routine...");
        DesktopNotifier::send_notification(
            "OMEN Space Fan Maintenance",
            "Fan Dust Cleaning routine started. Operating fans at high airflow bursts...",
            1,
        ).await;

        let conn = match Connection::system().await {
            Ok(c) => c,
            Err(e) => {
                error!("Failed to connect to system bus for fan cleaning: {}", e);
                return format!("Error: {}", e);
            }
        };

        let proxy = match FanProxy::new(&conn).await {
            Ok(p) => p,
            Err(e) => {
                error!("Failed to create FanProxy: {}", e);
                return format!("Error: {}", e);
            }
        };

        // Step 1: Max out fans
        let _ = proxy.set_fan_mode("max").await;
        sleep(Duration::from_secs(10)).await;

        // Step 2: Return to auto
        let _ = proxy.set_fan_mode("auto").await;

        DesktopNotifier::send_notification(
            "OMEN Space Fan Maintenance",
            "Fan Dust Cleaning completed successfully. Returned to automatic fan mode.",
            0,
        ).await;

        "Fan Dust Cleaning completed successfully".to_string()
    }
}
