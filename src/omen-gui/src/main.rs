use libadwaita as adw;
use gtk::prelude::*;
use libadwaita::prelude::AdwApplicationWindowExt;
use std::rc::Rc;

mod i18n;
mod monitoring;
mod performance_control;
mod appprofiles;
mod fan_presets;
mod fan_curve_editor;
mod undervolt;
mod mux;
mod keyboardrgb;
mod settings;
mod updater;
mod daemon_client;
mod asset_resolver;

const APP_ID: &str = "org.hp.OmenSpace";

fn main() {
    let app = adw::Application::builder().application_id(APP_ID).build();
    app.connect_startup(|_| {
        adw::init().expect("Failed to initialize libadwaita");
        i18n::init();
        ensure_tray_running();
        
        let display = gtk::gdk::Display::default().unwrap();
        let icon_theme = gtk::IconTheme::for_display(&display);
        icon_theme.add_search_path("assets");
        icon_theme.add_search_path("/usr/share/omen-space/assets");
        
        let provider = gtk::CssProvider::new();
        provider.load_from_string(include_str!("style.css"));
        let custom_provider = gtk::CssProvider::new();
        custom_provider.load_from_string(
            "navigation-split-view separator, flap separator { min-width: 0px; background: transparent; }"
        );
        gtk::style_context_add_provider_for_display(
            &gtk::gdk::Display::default().unwrap(),
            &provider,
            gtk::STYLE_PROVIDER_PRIORITY_APPLICATION,
        );
        gtk::style_context_add_provider_for_display(
            &gtk::gdk::Display::default().unwrap(),
            &custom_provider,
            gtk::STYLE_PROVIDER_PRIORITY_APPLICATION,
        );
    });
    app.connect_activate(build_ui);
    app.run();
}

fn apply_startup_profile() {
    if let Ok(home) = std::env::var("HOME") {
        let path = format!("{}/.config/omenspace/settings.json", home);
        if let Ok(json_str) = std::fs::read_to_string(&path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&json_str) {
                if let Some(sp) = json.get("startup_profile").and_then(|v| v.as_u64()) {
                    let profile_name = match sp {
                        1 => "Quiet",
                        2 => "Default",
                        3 => "Performance",
                        _ => return, // 0 = Last used, do nothing
                    };
                    crate::daemon_client::set_power_profile_sync(profile_name.to_string());
                }
            }
        }
    }
}

fn apply_appearance_mode() {
    if let Ok(home) = std::env::var("HOME") {
        let path = format!("{}/.config/omenspace/settings.json", home);
        if let Ok(json_str) = std::fs::read_to_string(&path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&json_str) {
                if let Some(am) = json.get("appearance_mode").and_then(|v| v.as_u64()) {
                    let scheme = match am {
                        1 => adw::ColorScheme::ForceLight,
                        2 => adw::ColorScheme::ForceDark,
                        _ => adw::ColorScheme::Default,
                    };
                    adw::StyleManager::default().set_color_scheme(scheme);
                }
            }
        }
    }
}

fn ensure_tray_running() {
    std::thread::spawn(|| {
        let spawned = std::process::Command::new("omen-tray")
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .spawn();

        if spawned.is_err() {
            let _ = std::process::Command::new("/usr/bin/omen-tray")
                .stdin(std::process::Stdio::null())
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .spawn();
        }
    });
}

fn build_ui(app: &adw::Application) {
    ensure_tray_running();
    apply_startup_profile();
    apply_appearance_mode();

    if let Some(window) = app.active_window().or_else(|| app.windows().first().cloned()) {
        window.set_visible(true);
        window.present();
        return;
    }

    let window = adw::ApplicationWindow::builder()
        .application(app)
        .title(i18n::t("app_title"))
        .default_width(1150)
        .default_height(820)
        .build();

    // Close button hides the window instead of killing the process (Minimize to Tray)
    window.connect_close_request(move |win| {
        win.set_visible(false);
        gtk::glib::Propagation::Stop
    });

    render_ui(&window, "performance");
    window.present();
}

fn render_ui(window: &adw::ApplicationWindow, initial_page: &str) {
    window.set_title(Some(i18n::t("app_title")));

    let stack = gtk::Stack::builder()
        .vexpand(true)
        .hexpand(true)
        .hhomogeneous(false)
        .vhomogeneous(false)
        .transition_type(gtk::StackTransitionType::Crossfade)
        .build();

    // Title label for the content page
    let content_title = gtk::Label::builder()
        .label(match initial_page {
            "undervolt" => i18n::t("title_undervolt"),
            "mux" => i18n::t("title_mux"),
            "monitoring" => i18n::t("title_monitoring"),
            "rgb" => i18n::t("title_lighting"),
            "appprof" => i18n::t("title_app_profiles"),
            "updater" => i18n::t("title_updater"),
            "settings" => i18n::t("title_settings"),
            _ => i18n::t("title_performance"),
        })
        .css_classes(["title"])
        .build();

    // Sidebar list
    let sidebar_list = gtk::ListBox::builder()
        .css_classes(["navigation-sidebar"])
        .selection_mode(gtk::SelectionMode::Single)
        .build();

    let spec_header = monitoring::build_spec_header();
    let page_perf = performance_control::build_page();
    let page_mon = monitoring::build_page(true);
    let gen_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .valign(gtk::Align::Start)
        .spacing(10)
        .margin_top(14)
        .margin_start(18)
        .margin_end(18)
        .margin_bottom(14)
        .build();
    gen_box.append(&spec_header);
    gen_box.append(&page_perf);
    gen_box.append(&page_mon);

    let m = 20;
    let page_undervolt = undervolt::build_page();
    page_undervolt.set_margin_top(m);
    page_undervolt.set_margin_start(m);
    page_undervolt.set_margin_end(m);
    page_undervolt.set_margin_bottom(m);

    let page_mux = mux::build_page();
    page_mux.set_margin_top(m);
    page_mux.set_margin_start(m);
    page_mux.set_margin_end(m);
    page_mux.set_margin_bottom(m);

    let mon_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .spacing(10)
        .margin_top(20)
        .margin_start(20)
        .margin_end(20)
        .margin_bottom(20)
        .build();
    mon_box.append(&monitoring::build_page(false));

    let page_rgb = keyboardrgb::build_page();
    page_rgb.set_margin_top(m);
    page_rgb.set_margin_start(m);
    page_rgb.set_margin_end(m);
    page_rgb.set_margin_bottom(m);

    // Setup dynamic on_lang_changed callback that re-renders the UI instantly
    let win_clone = window.clone();
    let on_lang_changed = Rc::new(move || {
        render_ui(&win_clone, "settings");
    });

    let page_settings = settings::build_page(&window, Some(on_lang_changed));
    page_settings.set_margin_top(m);
    page_settings.set_margin_start(m);
    page_settings.set_margin_end(m);
    page_settings.set_margin_bottom(m);

    let page_updater = updater::build_page(window);
    page_updater.set_margin_top(m);
    page_updater.set_margin_start(m);
    page_updater.set_margin_end(m);
    page_updater.set_margin_bottom(m);

    let page_app_profiles = appprofiles::build_page(window);
    page_app_profiles.set_margin_top(m);
    page_app_profiles.set_margin_start(m);
    page_app_profiles.set_margin_end(m);
    page_app_profiles.set_margin_bottom(m);

    stack.add_named(&gen_box, Some("performance"));
    stack.add_named(&page_undervolt, Some("undervolt"));
    stack.add_named(&page_mux, Some("mux"));
    stack.add_named(&mon_box, Some("monitoring"));
    stack.add_named(&page_rgb, Some("rgb"));
    stack.add_named(&page_app_profiles, Some("appprof"));
    stack.add_named(&page_updater, Some("updater"));
    stack.add_named(&page_settings, Some("settings"));

    stack.set_visible_child_name(initial_page);

    let toggle_sidebar_btn = gtk::ToggleButton::builder()
        .icon_name("sidebar-show-symbolic")
        .active(true)
        .build();

    let content_header = adw::HeaderBar::builder()
        .title_widget(&content_title)
        .build();
    content_header.pack_start(&toggle_sidebar_btn);

    let content_box = gtk::Box::builder().orientation(gtk::Orientation::Vertical).build();
    content_box.append(&content_header);
    let scroll = gtk::ScrolledWindow::builder()
        .vexpand(true)
        .hscrollbar_policy(gtk::PolicyType::Never)
        .child(&stack)
        .build();
    content_box.append(&scroll);

    let content_page = adw::NavigationPage::builder()
        .title(i18n::t("app_title"))
        .child(&content_box)
        .build();

    let tabs = [
        ("omen-performance-symbolic", i18n::t("nav_performance"), "performance"),
        ("omen-power-symbolic", i18n::t("nav_undervolt"), "undervolt"),
        ("omen-gpu-symbolic", i18n::t("nav_mux"), "mux"),
        ("omen-monitor-symbolic", i18n::t("nav_monitoring"), "monitoring"),
        ("omen-lighting-symbolic", i18n::t("nav_lighting"), "rgb"),
        ("omen-profiles-symbolic", i18n::t("nav_app_profiles"), "appprof"),
        ("omen-updater-symbolic", i18n::t("nav_updater"), "updater"),
    ];

    for (icon_name, tab_name, page_name) in tabs.iter() {
        let row = gtk::ListBoxRow::builder().build();
        let box_ = gtk::Box::builder()
            .orientation(gtk::Orientation::Horizontal)
            .spacing(12)
            .margin_start(12)
            .margin_end(12)
            .margin_top(11)
            .margin_bottom(11)
            .build();
        box_.append(&gtk::Image::builder().icon_name(*icon_name).pixel_size(18).build());
        box_.append(&gtk::Label::builder().label(*tab_name).build());
        row.set_child(Some(&box_));
        row.set_widget_name(*page_name);
        sidebar_list.append(&row);
    }

    let bottom_list = gtk::ListBox::builder()
        .css_classes(["navigation-sidebar"])
        .selection_mode(gtk::SelectionMode::Single)
        .margin_bottom(8)
        .build();
    let settings_row = gtk::ListBoxRow::builder().name("settings").build();
    let s_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .spacing(12)
        .margin_start(12)
        .margin_end(12)
        .margin_top(11)
        .margin_bottom(11)
        .build();
    s_box.append(&gtk::Image::builder().icon_name("omen-settings-symbolic").pixel_size(18).build());
    s_box.append(&gtk::Label::builder().label(i18n::t("nav_settings")).build());
    settings_row.set_child(Some(&s_box));
    bottom_list.append(&settings_row);

    if initial_page == "settings" {
        bottom_list.select_row(Some(&settings_row));
    } else {
        let mut selected = false;
        let mut idx = 0;
        while let Some(row) = sidebar_list.row_at_index(idx) {
            if row.widget_name().as_str() == initial_page {
                sidebar_list.select_row(Some(&row));
                selected = true;
                break;
            }
            idx += 1;
        }
        if !selected {
            if let Some(first_row) = sidebar_list.row_at_index(0) {
                sidebar_list.select_row(Some(&first_row));
            }
        }
    }

    let stack_clone = stack.clone();
    let title_clone = content_title.clone();
    let bottom_list_clone = bottom_list.clone();
    sidebar_list.connect_row_selected(move |_list, row_opt| {
        if let Some(row) = row_opt {
            bottom_list_clone.unselect_all(); // Mutual exclusion
            let page_name = row.widget_name().to_string();
            stack_clone.set_visible_child_name(&page_name);
            match page_name.as_str() {
                "performance" => title_clone.set_label(i18n::t("title_performance")),
                "undervolt" => title_clone.set_label(i18n::t("title_undervolt")),
                "mux" => title_clone.set_label(i18n::t("title_mux")),
                "monitoring" => title_clone.set_label(i18n::t("title_monitoring")),
                "rgb" => title_clone.set_label(i18n::t("title_lighting")),
                "appprof" => title_clone.set_label(i18n::t("title_app_profiles")),
                "updater" => title_clone.set_label(i18n::t("title_updater")),
                _ => {}
            }
        }
    });

    let stack_clone2 = stack.clone();
    let title_clone2 = content_title.clone();
    let sidebar_list_clone2 = sidebar_list.clone();
    bottom_list.connect_row_selected(move |_list, row_opt| {
        if let Some(row) = row_opt {
            sidebar_list_clone2.unselect_all(); // Mutual exclusion
            let page_name = row.widget_name().to_string();
            stack_clone2.set_visible_child_name(&page_name);
            if page_name == "settings" {
                title_clone2.set_label(i18n::t("title_settings"));
            }
        }
    });

    let header_logo_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .halign(gtk::Align::Center)
        .valign(gtk::Align::Center)
        .spacing(8)
        .build();
    window.set_icon_name(Some("omenspace"));
    header_logo_box.append(&gtk::Image::builder().icon_name("omenspace").pixel_size(24).build());
    header_logo_box.append(&gtk::Label::builder().label(i18n::t("app_title")).css_classes(["title"]).build());

    let sidebar_header = adw::HeaderBar::builder().title_widget(&header_logo_box).build();
    let sidebar_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .css_classes(["os-sidebar-box"])
        .width_request(220)
        .build();
    sidebar_box.append(&sidebar_header);
    sidebar_box.append(&sidebar_list);
    
    let spacer = gtk::Box::builder().vexpand(true).build();
    sidebar_box.append(&spacer);
    sidebar_box.append(&bottom_list);

    let sidebar_page = adw::NavigationPage::builder()
        .title(i18n::t("menu"))
        .child(&sidebar_box)
        .width_request(220)
        .build();

    let split_view = adw::OverlaySplitView::builder()
        .sidebar(&sidebar_page)
        .content(&content_page)
        .min_sidebar_width(220.0)
        .max_sidebar_width(220.0)
        .sidebar_width_fraction(0.0)
        .pin_sidebar(true)
        .build();

    toggle_sidebar_btn.connect_toggled({
        let split_view = split_view.clone();
        move |btn| {
            split_view.set_property("show-sidebar", btn.is_active());
        }
    });

    window.set_content(Some(&split_view));
}
