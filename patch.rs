    // Read current setting
    let mut init_auto = true;
    if let Ok(home) = std::env::var("HOME") {
        let path = format!("{}/.config/omenspace/settings.json", home);
        if let Ok(content) = std::fs::read_to_string(&path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(auto) = json.get("auto_update").and_then(|v| v.as_bool()) {
                    init_auto = auto;
                }
            }
        }
    }
