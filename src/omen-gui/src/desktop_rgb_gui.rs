use gtk::prelude::*;
use std::rc::Rc;
use std::cell::RefCell;

pub fn build_desktop_rgb_card(
    zone_colors: Rc<RefCell<Vec<String>>>,
) -> (gtk::Box, Rc<dyn Fn(&str, f64)>, gtk::Box) {
    let card = gtk::Box::builder()
        .orientation(gtk::Orientation::Vertical)
        .css_classes(["os-card"])
        .spacing(16)
        .halign(gtk::Align::Center)
        .build();

    let css = "
    .desktop-case {
        background: rgba(30,30,30,0.8);
        border: 2px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    }
    .desktop-glass {
        background: rgba(10,10,10,0.9);
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 8px;
        margin: 12px;
    }
    .desktop-fan {
        border-radius: 50%;
        background: rgba(255,255,255,0.05);
        border: 2px solid rgba(255,255,255,0.1);
    }
    .desktop-logo {
        
        background: rgba(255,255,255,0.1);
    }
    .desktop-strip {
        border-radius: 4px;
        background: rgba(255,255,255,0.1);
    }
    ";
    let provider = gtk::CssProvider::new();
    provider.load_from_string(css);
    if let Some(display) = gtk::gdk::Display::default() {
        gtk::style_context_add_provider_for_display(&display, &provider, gtk::STYLE_PROVIDER_PRIORITY_APPLICATION);
    }

    let dyn_provider = Rc::new(gtk::CssProvider::new());
    if let Some(display) = gtk::gdk::Display::default() {
        gtk::style_context_add_provider_for_display(&display, &*dyn_provider, gtk::STYLE_PROVIDER_PRIORITY_APPLICATION);
    }

    let case_outer = gtk::Box::builder().orientation(gtk::Orientation::Vertical).css_classes(["desktop-case"]).width_request(180).height_request(320).build();
    let glass_panel = gtk::Box::builder().orientation(gtk::Orientation::Vertical).css_classes(["desktop-glass"]).vexpand(true).spacing(12).build();
    
    // Fake internal components
    let top_fan = gtk::Box::builder().css_classes(["desktop-fan"]).width_request(60).height_request(60).halign(gtk::Align::Center).margin_top(12).build();
    let cpu_cooler = gtk::Box::builder().css_classes(["desktop-fan"]).width_request(80).height_request(80).halign(gtk::Align::Center).build();
    let bottom_logo = gtk::Box::builder().css_classes(["desktop-logo"]).width_request(40).height_request(45).halign(gtk::Align::Center).vexpand(true).valign(gtk::Align::End).margin_bottom(20).build();
    let ram_strip = gtk::Box::builder().css_classes(["desktop-strip"]).width_request(12).height_request(60).halign(gtk::Align::End).margin_end(20).build();

    top_fan.set_widget_name("desktop_zone_2");
    cpu_cooler.set_widget_name("desktop_zone_1");
    bottom_logo.set_widget_name("desktop_zone_0");
    ram_strip.set_widget_name("desktop_zone_3");

    glass_panel.append(&top_fan);
    glass_panel.append(&cpu_cooler);
    glass_panel.append(&ram_strip);
    glass_panel.append(&bottom_logo);
    case_outer.append(&glass_panel);

    card.append(&case_outer);

    let global_color_box = gtk::Box::builder().orientation(gtk::Orientation::Horizontal).spacing(12).margin_top(8).margin_bottom(12).halign(gtk::Align::Center).build();
    
    let dyn_prov_global = dyn_provider.clone();
    let zc_global = zone_colors.clone();

    // Create 7 zone buttons
    let mut zone_buttons = Vec::new();
    for i in 0..7 {
        let btn = gtk::Button::builder().width_request(32).height_request(32).build();
        btn.add_css_class("circular");
        btn.set_widget_name(&format!("btn_zone_{}", i));
        
        let label = gtk::Label::builder().label(&format!("Z{}", i+1)).css_classes(["dim-label"]).build();
        let vbox = gtk::Box::builder().orientation(gtk::Orientation::Vertical).spacing(4).build();
        vbox.append(&btn);
        vbox.append(&label);
        global_color_box.append(&vbox);
        zone_buttons.push(btn);
    }

    let zc_clone = zc_global.clone();
    let dyn_clone = dyn_prov_global.clone();
    
    let update_css = Rc::new(move || {
        let mut css_str = String::new();
        let zc = zc_clone.borrow();
        for i in 0..7 {
            let color = zc.get(i).unwrap_or(&"#FF0000".to_string()).clone();
            css_str.push_str(&format!("#btn_zone_{} {{ background: {}; background-image: none; border: 1px solid rgba(255,255,255,0.4); }}\n", i, color));
            css_str.push_str(&format!("#desktop_zone_{} {{ background: {}; background-image: none; box-shadow: 0 0 15px {}; }}\n", i, color, color));
        }
        dyn_clone.load_from_string(&css_str);
    });

    for i in 0..7 {
        let btn = &zone_buttons[i];
        let zc_local = zc_global.clone();
        let update_css_local = update_css.clone();
        let idx = i;
        
        btn.connect_clicked(move |btn_ref| {
            let zc_inner = zc_local.clone();
            let up_inner = update_css_local.clone();
            crate::keyboardrgb::show_color_picker_popover(btn_ref, Rc::new(move |hex| {
                if idx < zc_inner.borrow().len() {
                    zc_inner.borrow_mut()[idx] = hex.clone();
                } else {
                    while zc_inner.borrow().len() <= idx {
                        zc_inner.borrow_mut().push("#FF0000".to_string());
                    }
                    zc_inner.borrow_mut()[idx] = hex.clone();
                }
                crate::daemon_client::set_color_sync((idx + 10) as i32, hex.clone());
                up_inner();
            }));
        });
    }

    // Call initially
    update_css();

    let apply_anim = Rc::new(move |_mode: &str, _speed: f64| {
        // Desktop handles animation in hardware, we don't need CSS animations here!
        // The daemon handles mode changing via set_mode_sync
    });

    (card, apply_anim, global_color_box)
}
