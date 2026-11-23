//! Maplewing desktop (MIT). A native window around the same website and configurator that GitHub
//! Pages serves (docs/), bundled so it works offline. It has no backend and no commands: links to
//! other sites open in the system browser, everything else stays in the app.
use tauri::webview::{NewWindowResponse, WebviewWindowBuilder};
use tauri::{WebviewUrl, Url};
use tauri_plugin_opener::OpenerExt;

fn is_external(url: &Url) -> bool {
    matches!(url.scheme(), "http" | "https") && !matches!(url.host_str(), Some("tauri.localhost") | Some("localhost"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let handle = app.handle().clone();
            let handle2 = app.handle().clone();
            WebviewWindowBuilder::new(app, "main", WebviewUrl::App("app/index.html".into()))
                .title("Maplewing")
                .inner_size(1280.0, 860.0)
                .min_inner_size(380.0, 600.0)
                .on_navigation(move |url| {
                    if is_external(url) {
                        let _ = handle.opener().open_url(url.as_str(), None::<&str>);
                        return false;
                    }
                    true
                })
                .on_new_window(move |url, _features| {
                    let _ = handle2.opener().open_url(url.as_str(), None::<&str>);
                    NewWindowResponse::Deny
                })
                .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running the Maplewing app");
}
