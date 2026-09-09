use gtk::prelude::*;
use libadwaita as adw;
use adw::prelude::*;
use std::cell::RefCell;
use std::rc::Rc;
use std::collections::HashMap;

/* ─────────────────────────────────────────────────────────────
   keyboardrgb.rs — Aydınlatma (Klavye & Lightbar RGB Kontrolü)
   OMEN 4-Zone / Victus 1-Zone + 4-Segment Lightbar Desteği (Ref: OmenCore)
   ───────────────────────────────────────────────────────────── */

#[derive(Clone, Copy, PartialEq, Debug)]
enum KeyboardMode {
    Victus1Zone,
    Omen4Zone,
    #[allow(dead_code)]
    PerKey,
    DesktopRgb,
}

fn get_active_keyboard_mode(detected: KeyboardMode) -> KeyboardMode {
    if let Ok(home) = std::env::var("HOME") {
        let path = format!("{}/.config/omenspace/settings.json", home);
        if let Ok(json_str) = std::fs::read_to_string(&path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&json_str) {
                if let Some(zo) = json.get("zone_override").and_then(|v| v.as_u64()) { 
                    return match zo {
                        1 => KeyboardMode::Omen4Zone,
                        2 => KeyboardMode::Victus1Zone,
                        3 => KeyboardMode::PerKey,
                        4 => KeyboardMode::DesktopRgb,
                        _ => detected,
                    };
                }
            }
        }
    }
    detected
}

fn get_zone_for_key(name: &str) -> i32 {
    match name {
        "W" | "A" | "S" | "D" => 4,
        "Esc" | "F1" | "F2" | "F3" | "F4" | "~" | "1" | "2" | "3" | "4" | 
        "Tab" | "Q" | "E" | "R" | "Caps" | "F" | "Shift" | "Z" | "X" | "C" | "V" | 
        "Ctrl" | "Win" => 1,
        "F5" | "F6" | "F7" | "F8" | "5" | "6" | "7" | "8" | "T" | "Y" | "U" | "I" |
        "G" | "H" | "J" | "K" | "B" | "N" | "M" | "," | "Alt" | "Space" => 2,
        _ => 3,
    }
}

// ── Color Popover Helper ───────────────────────────────────────
#[allow(deprecated)]
pub fn show_color_picker_popover(
    parent: &gtk::Button,
    on_color_selected: Rc<dyn Fn(String)>
) {
    let popover = gtk::Popover::builder().position(gtk::PositionType::Bottom).autohide(true).build();
    popover.set_parent(parent);
    
    let container = gtk::Box::builder().orientation(gtk::Orientation::Horizontal).spacing(6).margin_top(6).margin_bottom(6).margin_start(6).margin_end(6).build();
    
    // Palette: Red, Green, Blue, Purple, Turquoise, Pink, White
    let palette = ["#FF0000", "#00FF00", "#0000FF", "#800080", "#40E0D0", "#FFC0CB", "#FFFFFF"];
    let palette_box = gtk::Box::builder().orientation(gtk::Orientation::Horizontal).spacing(4).build();
    for hex in palette {
        let btn = gtk::Button::builder().width_request(24).height_request(24).build();
        btn.add_css_class("circular");
        let provider = gtk::CssProvider::new();
        provider.load_from_string(&format!("button {{ background: {}; min-width: 24px; min-height: 24px; padding: 0; }}", hex));
        btn.style_context().add_provider(&provider, gtk::STYLE_PROVIDER_PRIORITY_APPLICATION);
        
        let pop_clone = popover.clone();
        let hex_clone = hex.to_string();
        let cb = on_color_selected.clone();
        btn.connect_clicked(move |_| {
            cb(hex_clone.clone());
            pop_clone.popdown();
        });
        palette_box.append(&btn);
    }
    
    let custom_btn = gtk::Button::builder().icon_name("applications-graphics-symbolic").width_request(24).height_request(24).build();
    custom_btn.add_css_class("circular");
    let cb2 = on_color_selected.clone();
    
    let parent_win_ref = parent.root().and_downcast::<gtk::Window>();
    let pop_clone2 = popover.clone();
    
    custom_btn.connect_clicked(move |_| {
        pop_clone2.popdown(); // Hide popover first
        let dialog = gtk::ColorDialog::builder().build();
        let cb_inner = cb2.clone();
        dialog.choose_rgba(parent_win_ref.as_ref(), None::<&gtk::gdk::RGBA>, None::<&gtk::gio::Cancellable>, move |res: Result<gtk::gdk::RGBA, glib::Error>| {
            if let Ok(rgba) = res {
                let hex = format!("#{:02X}{:02X}{:02X}", (rgba.red()*255.) as u8, (rgba.green()*255.) as u8, (rgba.blue()*255.) as u8);
                cb_inner(hex);
            }
        });
    });
    
    container.append(&palette_box);
    container.append(&gtk::Separator::new(gtk::Orientation::Vertical));
    container.append(&custom_btn);
    
    popover.set_child(Some(&container));
    popover.popup();
}

// ── Interactive Keyboard Builder ─────────────────────────────
fn build_interactive_keyboard(
    detected_mode: KeyboardMode,
    zone_colors: Rc<RefCell<Vec<String>>>,
    per_key_colors: Rc<RefCell<Vec<String>>>
) -> (gtk::Box, Rc<dyn Fn(&str, f64)>, gtk::Box) {
    let kb_card = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .css_classes(["os-card"])
        .spacing(6)
        .halign(gtk::Align::Center)
        .build();

    let layout = vec![
        vec![("Esc", 1.0), ("F1", 1.0), ("F2", 1.0), ("F3", 1.0), ("F4", 1.0), ("F5", 1.0), ("F6", 1.0), ("F7", 1.0), ("F8", 1.0), ("F9", 1.0), ("F10", 1.0), ("F11", 1.0), ("F12", 1.0), ("PrtSc", 1.0), ("ScrLk", 1.0), ("Pause", 1.0)],
        vec![("~", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("4", 1.0), ("5", 1.0), ("6", 1.0), ("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0), ("=", 1.0), ("Backspace", 2.0), ("Ins", 1.0), ("Home", 1.0), ("PgUp", 1.0), ("Num", 1.0), ("/", 1.0), ("*", 1.0), ("-", 1.0)],
        vec![("Tab", 1.5), ("Q", 1.0), ("W", 1.0), ("E", 1.0), ("R", 1.0), ("T", 1.0), ("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("[", 1.0), ("]", 1.0), ("\\", 1.5), ("Del", 1.0), ("End", 1.0), ("PgDn", 1.0), ("7", 1.0), ("8", 1.0), ("9", 1.0), ("+", 1.0)],
        vec![("Caps", 1.8), ("A", 1.0), ("S", 1.0), ("D", 1.0), ("F", 1.0), ("G", 1.0), ("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), (";", 1.0), ("'", 1.0), ("Enter", 2.2), ("4", 1.0), ("5", 1.0), ("6", 1.0)],
        vec![("Shift", 2.4), ("Z", 1.0), ("X", 1.0), ("C", 1.0), ("V", 1.0), ("B", 1.0), ("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0), ("/", 1.0), ("Shift_R", 2.6), ("Up", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("Ent", 1.0)],
        vec![("Ctrl", 1.5), ("Win", 1.2), ("Alt", 1.2), ("Space", 6.0), ("Alt_R", 1.2), ("Fn", 1.2), ("Menu", 1.2), ("Ctrl_R", 1.5), ("Left", 1.0), ("Down", 1.0), ("Right", 1.0), ("0", 2.0), (".", 1.0)]
    ];
    let base_width = 38;
    let height = 36;
    
    let buttons_map: Rc<RefCell<HashMap<String, gtk::Button>>> = Rc::new(RefCell::new(HashMap::new()));
    
    let mut key_x_pos = HashMap::new();
    let mut global_idx = 0;
    for row_keys in &layout {
        let row_box = gtk::Box::builder().orientation(gtk::Orientation::Horizontal).spacing(4).build();
        let mut x_idx = 0;
        for (name, size_mult) in row_keys {
            let width = (base_width as f32 * size_mult) as i32;
            let display_name = if name.ends_with("_R") { &name[..name.len()-2] } else { name };
            let key_btn = gtk::Button::builder().label(display_name).build();
            key_btn.set_size_request(width, height);
            key_btn.set_widget_name(&format!("key_{}", global_idx));
            key_btn.add_css_class("kb-key");
            
            buttons_map.borrow_mut().insert(name.to_string(), key_btn.clone());
            key_x_pos.insert(name.to_string(), x_idx);
            row_box.append(&key_btn);
            global_idx += 1;
            x_idx += 1;
        }
        kb_card.append(&row_box);
    }
    
    let b_map_clone = buttons_map.clone();
    let dyn_provider = Rc::new(gtk::CssProvider::new());
    if let Some(display) = gtk::gdk::Display::default() {
        gtk::style_context_add_provider_for_display(&display, &*dyn_provider, gtk::STYLE_PROVIDER_PRIORITY_APPLICATION);
    }
    let key_colors = Rc::new(RefCell::new(HashMap::<String, String>::new()));
    
    let global_color_box = gtk::Box::builder().orientation(gtk::Orientation::Horizontal).spacing(12).margin_top(8).margin_bottom(12).halign(gtk::Align::Center).build();
    let global_color_label = gtk::Label::builder().label(i18n::t("kb_global_color")).css_classes(["dim-label"]).build();
    if global_color_label.label().is_empty() || global_color_label.label() == "kb_global_color" {
        global_color_label.set_label(i18n::t("kb_global_color"));
    }
    let global_color_btn = gtk::Button::builder().width_request(40).height_request(24).build();
    global_color_btn.add_css_class("circular");
    global_color_btn.set_widget_name("global_color_btn");
    
    let c1_label = gtk::Label::builder().label(i18n::t("kb_color_1")).css_classes(["dim-label"]).build();
    let c1_btn = gtk::Button::builder().width_request(40).height_request(24).build();
    c1_btn.add_css_class("circular");
    c1_btn.set_widget_name("c1_btn");

    let c2_label = gtk::Label::builder().label(i18n::t("kb_color_2")).css_classes(["dim-label"]).build();
    let c2_btn = gtk::Button::builder().width_request(40).height_request(24).build();
    c2_btn.add_css_class("circular");
    c2_btn.set_widget_name("c2_btn");

    let c3_label = gtk::Label::builder().label(i18n::t("kb_color_3")).css_classes(["dim-label"]).build();
    let c3_btn = gtk::Button::builder().width_request(40).height_request(24).build();
    c3_btn.add_css_class("circular");
    c3_btn.set_widget_name("c3_btn");

    let c4_label = gtk::Label::builder().label(i18n::t("kb_color_4")).css_classes(["dim-label"]).build();
    let c4_btn = gtk::Button::builder().width_request(40).height_request(24).build();
    c4_btn.add_css_class("circular");
    c4_btn.set_widget_name("c4_btn");

    global_color_box.append(&global_color_label);
    global_color_box.append(&global_color_btn);
    
    if detected_mode == KeyboardMode::Omen4Zone || detected_mode == KeyboardMode::PerKey {
        global_color_box.append(&gtk::Separator::new(gtk::Orientation::Vertical));
        global_color_box.append(&c1_label);
        global_color_box.append(&c1_btn);
        global_color_box.append(&c2_label);
        global_color_box.append(&c2_btn);
        global_color_box.append(&c3_label);
        global_color_box.append(&c3_btn);
        global_color_box.append(&c4_label);
        global_color_box.append(&c4_btn);
    }
    
    if detected_mode == KeyboardMode::PerKey {
        let per_key_hint = gtk::Label::builder()
            .label(i18n::t("per_key_hint"))
            .css_classes(["os-section-desc"])
            .margin_bottom(8)
            .build();
        kb_card.prepend(&per_key_hint);
    }
    
    kb_card.prepend(&global_color_box);
    
    let b_map_global = buttons_map.clone();
    let dyn_prov_global = dyn_provider.clone();
    let kc_global = key_colors.clone();
    let zc_global = zone_colors.clone();
    let pk_global = per_key_colors.clone();
    
    global_color_btn.connect_clicked(move |btn_ref| {
        let b_map_local = b_map_global.clone();
        let kc_local = kc_global.clone();
        let dyn_local = dyn_prov_global.clone();
        let zc_local = zc_global.clone();
        let pk_local = pk_global.clone();
        let current_mode = crate::keyboardrgb::get_active_keyboard_mode(detected_mode);
        
        show_color_picker_popover(btn_ref, Rc::new(move |hex| {
            let mut css_str = String::new();
            css_str.push_str(&format!("#global_color_btn {{ background: {}; background-image: none; border: 1px solid rgba(255,255,255,0.4); }}\n", hex));

            match current_mode {
                KeyboardMode::Victus1Zone => {
                    zc_local.borrow_mut()[0] = hex.clone();
                    for (k, _) in b_map_local.borrow().iter() { kc_local.borrow_mut().insert(k.clone(), hex.clone()); }
                    crate::daemon_client::set_color_sync(8, hex.clone());
                }
                KeyboardMode::Omen4Zone => {
                    for i in 0..4 {
                        if i < zc_local.borrow().len() { zc_local.borrow_mut()[i] = hex.clone(); }
                        crate::daemon_client::set_color_sync(i as i32, hex.clone());
                    }
                    for (k, _) in b_map_local.borrow().iter() { kc_local.borrow_mut().insert(k.clone(), hex.clone()); }
                }
                KeyboardMode::PerKey => {
                    let len = pk_local.borrow().len();
                    for i in 0..len { pk_local.borrow_mut()[i] = hex.clone(); }
                    for (k, _) in b_map_local.borrow().iter() { kc_local.borrow_mut().insert(k.clone(), hex.clone()); }
                    crate::daemon_client::set_per_key_colors_sync(pk_local.borrow().clone());
                }
                KeyboardMode::DesktopRgb => {}
            }
            
            for (k, c) in kc_local.borrow().iter() {
                if let Some(target_btn) = b_map_local.borrow().get(k) {
                    let wname = target_btn.widget_name();
                    css_str.push_str(&format!("#{} {{ background: {}; background-image: none; }}\n", wname.as_str(), c));
                }
            }
            dyn_local.load_from_string(&css_str);
        }));
    });

    let dyn_prov_c1 = dyn_provider.clone();
    c1_btn.connect_clicked(move |btn_ref| {
        let dyn_local = dyn_prov_c1.clone();
        show_color_picker_popover(btn_ref, Rc::new(move |hex| {
            let css_str = format!("#c1_btn {{ background: {}; background-image: none; border: 1px solid rgba(255,255,255,0.4); }}\n", hex);
            crate::daemon_client::set_color_sync(0, hex.clone());
            dyn_local.load_from_string(&css_str);
        }));
    });

    let dyn_prov_c2 = dyn_provider.clone();
    c2_btn.connect_clicked(move |btn_ref| {
        let dyn_local = dyn_prov_c2.clone();
        show_color_picker_popover(btn_ref, Rc::new(move |hex| {
            let css_str = format!("#c2_btn {{ background: {}; background-image: none; border: 1px solid rgba(255,255,255,0.4); }}\n", hex);
            crate::daemon_client::set_color_sync(1, hex.clone());
            dyn_local.load_from_string(&css_str);
        }));
    });
    let dyn_prov_c3 = dyn_provider.clone();
    c3_btn.connect_clicked(move |btn_ref| {
        let dyn_local = dyn_prov_c3.clone();
        show_color_picker_popover(btn_ref, Rc::new(move |hex| {
            let css_str = format!("#c3_btn {{ background: {}; background-image: none; border: 1px solid rgba(255,255,255,0.4); }}\n", hex);
            crate::daemon_client::set_color_sync(2, hex.clone());
            dyn_local.load_from_string(&css_str);
        }));
    });

    let dyn_prov_c4 = dyn_provider.clone();
    c4_btn.connect_clicked(move |btn_ref| {
        let dyn_local = dyn_prov_c4.clone();
        show_color_picker_popover(btn_ref, Rc::new(move |hex| {
            let css_str = format!("#c4_btn {{ background: {}; background-image: none; border: 1px solid rgba(255,255,255,0.4); }}\n", hex);
            crate::daemon_client::set_color_sync(3, hex.clone());
            dyn_local.load_from_string(&css_str);
        }));
    });
    // ------------------------
    
    for (name, btn) in buttons_map.borrow().iter() {
        let b_map_inner = b_map_clone.clone();
        let name_inner = name.clone();
        let zc_inner = zone_colors.clone();
        let pk_inner = per_key_colors.clone();
        
        let mut key_index = 0;
        let mut found = false;
        for row in &layout {
            for (n, _) in row {
                if *n == name.as_str() { found = true; break; }
                key_index += 1;
            }
            if found { break; }
        }
        
        let dyn_prov_inner = dyn_provider.clone();
        let kc_inner = key_colors.clone();
        
        btn.connect_clicked(move |btn_ref| {
            let current_mode = crate::keyboardrgb::get_active_keyboard_mode(detected_mode);
            let b_map_local = b_map_inner.clone();
            let name_local = name_inner.clone();
            let pk_local = pk_inner.clone();
            let zc_local = zc_inner.clone();
            let kc_local = kc_inner.clone();
            let dyn_local = dyn_prov_inner.clone();
            
            show_color_picker_popover(btn_ref, Rc::new(move |hex| {
                match current_mode {
                    KeyboardMode::PerKey => {
                        if key_index < pk_local.borrow().len() {
                            pk_local.borrow_mut()[key_index] = hex.clone();
                        }
                        kc_local.borrow_mut().insert(name_local.clone(), hex.clone());
                        crate::daemon_client::set_per_key_colors_sync(pk_local.borrow().clone());
                    }
                    KeyboardMode::Victus1Zone => {
                        zc_local.borrow_mut()[0] = hex.clone();
                        let map = b_map_local.borrow();
                        for (k, _) in map.iter() {
                            kc_local.borrow_mut().insert(k.clone(), hex.clone());
                        }
                        crate::daemon_client::set_color_sync(8, hex.clone());
                    }
                    KeyboardMode::Omen4Zone => {
                        let target_zone = get_zone_for_key(&name_local);
                        let zone_idx = (target_zone - 1) as usize;
                        if zone_idx < zc_local.borrow().len() {
                            zc_local.borrow_mut()[zone_idx] = hex.clone();
                        }
                        let map = b_map_local.borrow();
                        for (k, _) in map.iter() {
                            if get_zone_for_key(k) == target_zone {
                                kc_local.borrow_mut().insert(k.clone(), hex.clone());
                            }
                        }
                        crate::daemon_client::set_color_sync(zone_idx as i32, hex.clone());
                    }
                    KeyboardMode::DesktopRgb => {}
                }
                
                // Build dynamic CSS
                let mut css_str = String::new();
                for (k, c) in kc_local.borrow().iter() {
                    if let Some(target_btn) = b_map_local.borrow().get(k) {
                        let wname = target_btn.widget_name();
                        css_str.push_str(&format!("#{} {{ background: {}; background-image: none; }}\n", wname.as_str(), c));
                    }
                }
                dyn_local.load_from_string(&css_str);
            }));
        });
    }
    
    let dyn_anim = dyn_provider.clone();
    let b_map_anim = buttons_map.clone();
    let kc_anim = key_colors.clone();
    
    let apply_anim = Rc::new(move |mode: &str, speed: f64| {
        let duration = if speed <= 0.0 { 10.0 } else { 10.0 - (speed / 100.0) * 8.0 }; // 2s to 10s
        let mut css = String::new();
        
        match mode {
            "static" => {
                for (k, c) in kc_anim.borrow().iter() {
                    if let Some(btn) = b_map_anim.borrow().get(k) {
                        css.push_str(&format!("#{} {{ background: {}; animation: none; opacity: 1.0; }}\n", btn.widget_name(), c));
                    }
                }
            },
            "cycle" => {
                css.push_str("@keyframes kb_cycle { 0% { background: #ff0000; } 16% { background: #ffff00; } 33% { background: #00ff00; } 50% { background: #00ffff; } 66% { background: #0000ff; } 83% { background: #ff00ff; } 100% { background: #ff0000; } }\n");
                for (_, btn) in b_map_anim.borrow().iter() {
                    css.push_str(&format!("#{} {{ animation: kb_cycle {:.1}s infinite linear; opacity: 1.0; }}\n", btn.widget_name(), duration));
                }
            },
            "breathing" => {
                css.push_str("@keyframes kb_breathe { 0%, 100% { opacity: 0.1; } 50% { opacity: 1.0; } }\n");
                for (k, c) in kc_anim.borrow().iter() {
                    if let Some(btn) = b_map_anim.borrow().get(k) {
                        css.push_str(&format!("#{} {{ background: {}; animation: kb_breathe {:.1}s infinite ease-in-out; }}\n", btn.widget_name(), c, duration));
                    }
                }
            },
            "wave" => {
                css.push_str("@keyframes kb_wave { 0% { background: #ff0000; } 16% { background: #ffff00; } 33% { background: #00ff00; } 50% { background: #00ffff; } 66% { background: #0000ff; } 83% { background: #ff00ff; } 100% { background: #ff0000; } }\n");
                for (k, btn) in b_map_anim.borrow().iter() {
                    let x_pos = *key_x_pos.get(k).unwrap_or(&0);
                    let delay = (x_pos as f64) * 0.15 * (duration / 5.0);
                    css.push_str(&format!("#{} {{ animation: kb_wave {:.1}s infinite linear -{:.2}s; opacity: 1.0; }}\n", btn.widget_name(), duration, delay));
                }
            },
            "audio" => {
                css.push_str("@keyframes kb_audio { 0%, 100% { opacity: 0.1; } 10%, 30%, 70% { opacity: 1.0; } 20%, 50%, 80% { opacity: 0.4; } }\n");
                for (k, c) in kc_anim.borrow().iter() {
                    if let Some(btn) = b_map_anim.borrow().get(k) {
                        css.push_str(&format!("#{} {{ background: {}; animation: kb_audio {:.1}s infinite linear; }}\n", btn.widget_name(), c, duration));
                    }
                }
            }
            _ => {}
        }
        dyn_anim.load_from_string(&css);
    });
    
    (kb_card, apply_anim, global_color_box)
}

// ── OmenCore 4-Segment Lightbar Widget Builder ───────────────
fn build_interactive_lightbar(state_json_opt: &Option<serde_json::Value>) -> gtk::Box {
    let bar_card = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .css_classes(["os-card"])
        .spacing(12)
        .build();

    let title_row = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .spacing(8)
        .build();
    title_row.append(&gtk::Label::builder()
        .label(i18n::t("lightbar_title"))
        .css_classes(["chip-title"])
        .hexpand(true)
        .halign(gtk::Align::Start)
        .build());

    let sync_btn = gtk::Button::builder()
        .label(i18n::t("lightbar_sync_btn"))
        .css_classes(["ec-btn"])
        .build();
    title_row.append(&sync_btn);
    bar_card.append(&title_row);

    // 4 Segment Light Bar Strip
    let strip_box = gtk::Box::builder()
        .orientation(gtk::Orientation::Horizontal)
        .spacing(6)
        .homogeneous(true)
        .margin_top(4)
        .margin_bottom(4)
        .build();

    let segment_names = [i18n::t("lb_seg_1"), i18n::t("lb_seg_2"), i18n::t("lb_seg_3"), i18n::t("lb_seg_4")];
    let default_colors = ["#E03454", "#0099EE", "#0099EE", "#E03454"]; // OMEN gradient
    let mut segment_buttons = Vec::new();

    let dyn_provider = Rc::new(gtk::CssProvider::new());
    if let Some(display) = gtk::gdk::Display::default() {
        gtk::style_context_add_provider_for_display(&display, &*dyn_provider, gtk::STYLE_PROVIDER_PRIORITY_APPLICATION);
    }
    let mut initial_colors = default_colors.iter().map(|s| s.to_string()).collect::<Vec<_>>();
    if let Some(state) = state_json_opt {
        if let Some(zones) = state.get("zones").and_then(|z| z.as_object()) {
            for i in 0..4 {
                let key = format!("{}", i + 4); // Lightbar zones are 4, 5, 6, 7
                if let Some(hex) = zones.get(&key).and_then(|h| h.as_str()) {
                    initial_colors[i] = hex.to_string();
                }
            }
        }
    }
    let colors_map = Rc::new(RefCell::new(initial_colors));

    for (i, name) in segment_names.iter().enumerate() {
        let seg_btn = gtk::Button::builder()
            .label(*name)
            .height_request(46)
            .build();
        
        seg_btn.set_widget_name(&format!("lightbar_seg_{}", i));
        
        let dyn_prov_inner = dyn_provider.clone();
        let colors_inner = colors_map.clone();
        
        seg_btn.connect_clicked(move |btn_ref| {
            let colors_local = colors_inner.clone();
            let dyn_local = dyn_prov_inner.clone();
            
            show_color_picker_popover(btn_ref, Rc::new(move |hex| {
                colors_local.borrow_mut()[i] = hex.clone();
                
                let mut css_str = String::new();
                for (idx, c) in colors_local.borrow().iter().enumerate() {
                    css_str.push_str(&format!(
                        "#lightbar_seg_{} {{ background: {}; background-image: none; color: #fff; border-radius: 6px; font-size: 11px; font-weight: bold; border: 1px solid rgba(255,255,255,0.25); box-shadow: 0 0 14px {}60; transition: all 0.25s ease; }}\n",
                        idx, c, c
                    ));
                }
                dyn_local.load_from_string(&css_str);
                
                // Assuming lightbar uses zones 4, 5, 6, 7
                let zone_id = 4 + i as i32;
                crate::daemon_client::set_color_sync(zone_id, hex.clone());
            }));
        });

        strip_box.append(&seg_btn);
        segment_buttons.push(seg_btn);
    }
    bar_card.append(&strip_box);

    let dyn_prov_inner_sync = dyn_provider.clone();
    let colors_inner_sync = colors_map.clone();
    
    sync_btn.connect_clicked(move |btn_ref| {
        let colors_local = colors_inner_sync.clone();
        let dyn_local = dyn_prov_inner_sync.clone();
        
        show_color_picker_popover(btn_ref, Rc::new(move |hex| {
            let mut css_str = String::new();
            for i in 0..4 {
                colors_local.borrow_mut()[i] = hex.clone();
                css_str.push_str(&format!(
                    "#lightbar_seg_{} {{ background: {}; background-image: none; color: #fff; border-radius: 6px; font-size: 11px; font-weight: bold; border: 1px solid rgba(255,255,255,0.25); box-shadow: 0 0 14px {}60; transition: all 0.25s ease; }}\n",
                    i, hex, hex
                ));
                crate::daemon_client::set_color_sync((4 + i) as i32, hex.clone());
            }
            dyn_local.load_from_string(&css_str);
        }));
    });

    // Initialize initial colors
    let mut init_css = String::new();
    for (idx, c) in colors_map.borrow().iter().enumerate() {
        init_css.push_str(&format!(
            "#lightbar_seg_{} {{ background: {}; background-image: none; color: #fff; border-radius: 6px; font-size: 11px; font-weight: bold; border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 0 10px {}40; transition: all 0.25s ease; }}\n",
            idx, c, c
        ));
    }
    dyn_provider.load_from_string(&init_css);

    bar_card
}

use crate::i18n;

pub fn build_page() -> (adw::PreferencesPage, Option<adw::PreferencesGroup>, Option<adw::PreferencesGroup>) {
    let page = adw::PreferencesPage::builder().build();
    let specs = crate::daemon_client::get_hardware_specs_sync();

    // ── Device Type Auto-Detection ────────────────────────────
    let prod_lower = specs.product_name.to_lowercase();
    let is_omen = prod_lower.contains("omen");

    // Sync initial state from daemon early to detect per-key
    let current_state_str = crate::daemon_client::get_rgb_state_sync();
    let mut is_per_key = false;
    let mut state_json_opt: Option<serde_json::Value> = None;
    if let Ok(state_json) = serde_json::from_str::<serde_json::Value>(&current_state_str) {
        if state_json["per_key_available"].as_bool().unwrap_or(false) {
            is_per_key = true;
        }
        state_json_opt = Some(state_json);
    }

    let mut zone_override = 0;
    if let Ok(home) = std::env::var("HOME") {
        let path = format!("{}/.config/omenspace/settings.json", home);
        if let Ok(json_str) = std::fs::read_to_string(&path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&json_str) {
                if let Some(zo) = json.get("zone_override").and_then(|v| v.as_u64()) {
                    zone_override = zo;
                }
            }
        }
    }

    let detected_mode = match zone_override {
        4 => KeyboardMode::DesktopRgb,
        3 => KeyboardMode::PerKey,
        2 => KeyboardMode::Victus1Zone, // Single zone override
        1 => KeyboardMode::Omen4Zone,   // 4-zone override
        _ => {
            // Auto detection (0 or unknown)
            if specs.product_name.to_lowercase().contains("desktop") || specs.product_name.to_lowercase().contains("tower") {
                KeyboardMode::DesktopRgb
            } else if is_per_key {
                KeyboardMode::PerKey
            } else if is_omen {
                KeyboardMode::Omen4Zone
            } else {
                KeyboardMode::Victus1Zone
            }
        }
    };

    // ── 1. Keyboard Lighting Group ────────────────────────────
    let std_group = adw::PreferencesGroup::builder()
        .title(i18n::t("kb_lighting_group"))
        .description(if detected_mode == KeyboardMode::DesktopRgb {
            i18n::t("desktop_rgb_desc")
        } else if is_per_key {
            i18n::t("omen_per_key_desc")
        } else if is_omen {
            i18n::t("omen_4zone_desc")
        } else {
            i18n::t("victus_1zone_desc")
        })
        .build();

    let detected_row = adw::ActionRow::builder()
        .title(i18n::t("hw_arch"))
        .subtitle(if detected_mode == KeyboardMode::DesktopRgb {
            "OMEN Desktop RGB"
        } else if is_per_key {
            "Omen Per-Key RGB"
        } else if is_omen {
            i18n::t("hw_arch_omen")
        } else {
            i18n::t("hw_arch_victus")
        })
        .build();
    let badge = gtk::Label::builder()
        .label(if detected_mode == KeyboardMode::DesktopRgb { "Desktop" } else if is_per_key { "Per-Key" } else if is_omen { i18n::t("badge_4zone") } else { i18n::t("badge_1zone") })
        .css_classes(["badge-ok"])
        .valign(gtk::Align::Center)
        .build();
    detected_row.add_suffix(&badge);
    std_group.add(&detected_row);

    // Animation Effect Combo
    // Animation Effect Combo
    let (effect_labels, mode_str_list) = match detected_mode {
        KeyboardMode::Victus1Zone => (
            vec![i18n::t("effect_static"), i18n::t("effect_breathing"), i18n::t("effect_cycle")],
            vec!["static", "breathing", "cycle"]
        ),
        KeyboardMode::Omen4Zone => (
            vec![
                i18n::t("effect_static"), 
                i18n::t("effect_breathing"), 
                i18n::t("effect_blinking"), 
                i18n::t("effect_cycle"), 
                i18n::t("effect_wave_custom"), 
                i18n::t("effect_wave_rainbow")
            ],
            vec!["static", "breathing", "blinking", "cycle", "wave", "wave_rainbow"]
        ),
        KeyboardMode::PerKey => (
            vec![
                i18n::t("effect_static"),
                "Per-Key Custom",
                i18n::t("effect_breathing"),
                i18n::t("effect_blinking"),
                i18n::t("effect_cycle"),
                i18n::t("effect_wave_custom"),
                i18n::t("effect_wave_rainbow"),
                i18n::t("effect_starlight"),
                i18n::t("effect_marquee"),
                i18n::t("effect_reactive"),
                i18n::t("effect_ripple"),
                i18n::t("effect_raindrop")
            ],
            vec!["static", "per_key_custom", "breathing", "blinking", "cycle", "wave", "wave_rainbow", "starlight", "marquee", "reactive", "ripple", "raindrop"]
        ),
        KeyboardMode::DesktopRgb => (
            vec![
                i18n::t("effect_static"),
                i18n::t("effect_breathing"),
                i18n::t("effect_cycle"),
                i18n::t("effect_blinking"),
                i18n::t("effect_wave"),
            ],
            vec!["static", "breathing", "cycle", "blinking", "wave"]
        ),
    };
    
    let mode_model = gtk::StringList::new(&effect_labels);
    let mode_row = adw::ComboRow::builder()
        .title(i18n::t("kb_effect"))
        .model(&mode_model)
        .build();
    std_group.add(&mode_row);

    let effect_speed_row = adw::ActionRow::builder().title(i18n::t("kb_effect_speed")).build();
    let speed_scale = gtk::Scale::with_range(gtk::Orientation::Horizontal, 0.0, 100.0, 1.0);
    speed_scale.set_value(50.0);
    speed_scale.set_draw_value(true);
    speed_scale.set_hexpand(false);
    speed_scale.set_size_request(250, -1);
    speed_scale.set_margin_start(12);
    speed_scale.set_margin_end(12);
    speed_scale.set_valign(gtk::Align::Center);
    effect_speed_row.add_suffix(&speed_scale);
    std_group.add(&effect_speed_row);
    
    // Sync initial state from daemon (parsed early)
    if let Some(state_json) = &state_json_opt {
        if let Some(mode_str) = state_json["mode"].as_str() {
            if let Some(idx) = mode_str_list.iter().position(|&m| m == mode_str) {
                mode_row.set_selected(idx as u32);
            }
        }
        if let Some(speed) = state_json["speed"].as_f64() {
            speed_scale.set_value(speed);
        }
    }

    let mode_row_clone = mode_row.clone();
    let speed_scale_clone = speed_scale.clone();
    
    // We will hook up the animation after we define it below, but we need a cell to hold it
    let apply_anim_rc: Rc<RefCell<Option<Rc<dyn Fn(&str, f64)>>>> = Rc::new(RefCell::new(None));
    let aa_hook = apply_anim_rc.clone();
    
    let msl_c: Vec<String> = mode_str_list.iter().map(|s| s.to_string()).collect();
    let msl_for_ae = mode_str_list.clone();
    
    let apply_effect = move || {
        let idx = mode_row_clone.selected() as usize;
        let speed = speed_scale_clone.value();
        if idx < msl_for_ae.len() {
            let m = msl_for_ae[idx];
            if m == "wave_ltr" {
                crate::daemon_client::set_mode_sync("wave", speed as i32);
                crate::daemon_client::set_global_sync(true, 100, "ltr");
            } else if m == "wave_rtl" {
                crate::daemon_client::set_mode_sync("wave", speed as i32);
                crate::daemon_client::set_global_sync(true, 100, "rtl");
            } else {
                crate::daemon_client::set_mode_sync(m, speed as i32);
            }
            if let Some(anim_func) = &*aa_hook.borrow() {
                let anim_m = if m.starts_with("wave_") { "wave" } else { m };
                anim_func(anim_m, speed);
            }
        }
    };
    
    let ae_rc = Rc::new(apply_effect);
    let ae1 = ae_rc.clone();
    mode_row.connect_selected_notify(move |_| ae1());
    
    let ae2 = ae_rc.clone();
    speed_scale.connect_value_changed(move |_| ae2());

    // Brightness
    let bright_row = adw::ActionRow::builder().title(i18n::t("kb_brightness")).build();
    let bright_scale = gtk::Scale::with_range(gtk::Orientation::Horizontal, 0.0, 100.0, 1.0);
    bright_scale.set_value(100.0);
    if let Some(state_json) = &state_json_opt {
        if let Some(brightness) = state_json["brightness"].as_f64() {
            bright_scale.set_value(brightness);
        }
    }
    bright_scale.set_draw_value(true);
    bright_scale.set_hexpand(false);
    bright_scale.set_size_request(250, -1);
    bright_scale.set_margin_start(12);
    bright_scale.set_margin_end(12);
    bright_scale.set_valign(gtk::Align::Center);
    bright_row.add_suffix(&bright_scale);
    std_group.add(&bright_row);
    
    bright_scale.connect_value_changed(move |scale| {
        let val = scale.value() as i32;
        let pwr = val > 0;
        crate::daemon_client::set_global_sync(pwr, val, "ltr");
    });


    page.add(&std_group);

    // ── Interactive Keyboard Layout & Palette ─────────────────
    let std_kb_group = adw::PreferencesGroup::builder()
        .title(i18n::t("kb_color_map"))
        .description(i18n::t("kb_color_map_desc"))
        .build();

    let zone_colors = Rc::new(RefCell::new(vec!["#0099ED".to_string(); 7]));
    let per_key_colors = Rc::new(RefCell::new(vec!["#0099ED".to_string(); 104]));

    let (std_kb_grid, apply_anim, global_color_box_ref) = if detected_mode == KeyboardMode::DesktopRgb {
        crate::desktop_rgb_gui::build_desktop_rgb_card(zone_colors.clone())
    } else {
        build_interactive_keyboard(detected_mode, zone_colors.clone(), per_key_colors.clone())
    };
    std_kb_group.add(&std_kb_grid);
    page.add(&std_kb_group);
    
    let mr_c = mode_row.clone();
    let update_color_box_vis = move || {
        let idx = mr_c.selected() as usize;
        if idx < msl_c.len() {
            let m = &msl_c[idx];
            let show = m == "static" || m == "per_key_custom";
            global_color_box_ref.set_visible(show);
        }
    };
    let ucbv_rc = Rc::new(update_color_box_vis);
    let u1 = ucbv_rc.clone();
    mode_row.connect_selected_notify(move |_| u1());
    ucbv_rc();
    
    *apply_anim_rc.borrow_mut() = Some(apply_anim.clone());
    
    // Call it initially so it starts animating at launch
    if let Some(state_json) = &state_json_opt {
        if let Some(mode_str) = state_json["mode"].as_str() {
            let speed = state_json["speed"].as_f64().unwrap_or(50.0);
            apply_anim(mode_str, speed);
        } else {
            apply_anim("static", 50.0);
        }
    } else {
        apply_anim("static", 50.0);
    }

    // ── Load RGB Initial State ───────────────────────────────
    let zc_load = zone_colors.clone();
    glib::spawn_future_local(async move {
        if let Ok(json) = crate::daemon_client::get_rgb_state_async().await {
            if let Ok(state) = serde_json::from_str::<serde_json::Value>(&json) {
                // E.g. assume state has "zone_colors": ["#112233", "#445566", ...]
                // Or maybe just a global color. 
                // Let's just try to parse a global color or zones.
                // Just loading into zone_colors/per_key_colors
                if let Some(zones) = state.get("zones").and_then(|z| z.as_object()) {
                    let mut loaded_colors = zc_load.borrow_mut();
                    for (i, v) in zones.iter() {
                        if let Ok(idx) = i.parse::<usize>() {
                            if let Some(hex) = v.as_str() {
                                if idx < loaded_colors.len() {
                                    loaded_colors[idx] = hex.to_string();
                                }
                            }
                        }
                    }
                }
            }
        }
    });

    let mut lb_group_ret = None;
    let mut lb_preview_group_ret = None;

    let is_omen_brand = is_omen || detected_mode == KeyboardMode::DesktopRgb;
    if is_omen_brand {
        let lb_group = adw::PreferencesGroup::builder()
            .title(i18n::t("lightbar_group"))
            .description(i18n::t("lightbar_desc"))
            .build();

        let lb_enable_row = adw::SwitchRow::builder()
            .title(i18n::t("lightbar_enable"))
            .subtitle(i18n::t("lightbar_enable_sub"))
            .build();
        lb_enable_row.set_active(true);
        lb_group.add(&lb_enable_row);

        let lb_effect_model = gtk::StringList::new(&[
            i18n::t("effect_static"),
            i18n::t("effect_wave"),
            i18n::t("effect_breathing"),
            i18n::t("effect_cycle"),
        ]);
        let lb_effect_row = adw::ComboRow::builder()
            .title(i18n::t("lightbar_effect"))
            .model(&lb_effect_model)
            .build();
        lb_effect_row.connect_selected_notify(move |row| {
            let mode = match row.selected() {
                1 => "wave",
                2 => "breathing",
                3 => "cycle",
                _ => "static",
            };
            crate::daemon_client::set_mode_sync(mode, 50);
        });
        lb_group.add(&lb_effect_row);

        let lb_bright_row = adw::ActionRow::builder().title(i18n::t("lightbar_brightness")).build();
        let lb_bright_scale = gtk::Scale::with_range(gtk::Orientation::Horizontal, 0.0, 100.0, 1.0);
        lb_bright_scale.set_value(80.0);
        lb_bright_scale.set_draw_value(true);
        lb_bright_scale.set_hexpand(false);
        lb_bright_scale.set_size_request(250, -1);
        lb_bright_scale.set_margin_start(12);
        lb_bright_scale.set_margin_end(12);
        lb_bright_scale.set_valign(gtk::Align::Center);
        lb_bright_row.add_suffix(&lb_bright_scale);
        lb_group.add(&lb_bright_row);
        
        lb_bright_scale.connect_value_changed(move |scale| {
            // Note: the backend currently uses set_global for all brightness. 
            // In the future, this can be separated if hardware supports it.
            let val = scale.value() as i32;
            crate::daemon_client::set_global_sync(val > 0, val, "ltr");
        });

        page.add(&lb_group);

        // Lightbar Interactive 4-Segment Strip
        let lb_preview_group = adw::PreferencesGroup::builder()
            .title(i18n::t("lightbar_segments"))
            .build();
        let lb_widget = build_interactive_lightbar(&state_json_opt);
        lb_preview_group.add(&lb_widget);
        page.add(&lb_preview_group);

        let lb_effect_row_c = lb_effect_row.clone();
        let lb_bright_row_c = lb_bright_row.clone();
        let lb_preview_group_c = lb_preview_group.clone();

        lb_enable_row.connect_active_notify(move |row| {
            let is_active = row.is_active();
            lb_effect_row_c.set_visible(is_active);
            lb_bright_row_c.set_visible(is_active);
            lb_preview_group_c.set_visible(is_active);
        });
        let lb_prod_lower = specs.product_name.to_lowercase();
        let mut show_lightbar = detected_mode == KeyboardMode::DesktopRgb || lb_prod_lower.contains("desktop") || lb_prod_lower.contains("transcend") || lb_prod_lower.contains("max");
        if let Ok(home) = std::env::var("HOME") {
            let path = format!("{}/.config/omenspace/settings.json", home);
            if let Ok(json_str) = std::fs::read_to_string(&path) {
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&json_str) {
                    if let Some(lb) = json.get("lightbar_enabled").and_then(|v| v.as_bool()) {
                        show_lightbar = lb;
                    }
                }
            }
        }
        lb_group.set_visible(show_lightbar);
        lb_preview_group.set_visible(show_lightbar);

        lb_group_ret = Some(lb_group);
        lb_preview_group_ret = Some(lb_preview_group);
    }

    (page, lb_group_ret, lb_preview_group_ret)
}
