// Описание: Именованные символы из локального шрифта Material Icons.
// Codepoints: flutter/flutter, packages/flutter/lib/src/material/icons.dart.
use dioxus::prelude::*;

pub const FONT: Asset = asset!("/assets/fonts/material/MaterialIcons-Regular.otf");

pub fn glyph(name: &str) -> &'static str {
    match name {
        "add" => "\u{e047}",
        "add_comment" => "\u{e051}",
        "add_comment_outlined" => "\u{ee41}",
        "api" => "\u{e08a}",
        "arrow_back" => "\u{e092}",
        "arrow_downward" => "\u{e097}",
        "auto_awesome" => "\u{e0b7}",
        "bookmark_border" => "\u{e0f4}",
        "check" => "\u{e156}",
        "storage" => "\u{e609}",
        "palette_outlined" => "\u{f24f}",
        "expand_less" => "\u{e245}",
        "chat_bubble_outline" => "\u{e155}",
        "chevron_right" => "\u{e15f}",
        "close" => "\u{e16a}",
        "code" => "\u{e176}",
        "construction" => "\u{e189}",
        "content_copy" => "\u{e190}",
        "delete_outline" => "\u{e1bb}",
        "description" => "\u{e1bf}",
        "download" => "\u{e201}",
        "download_outlined" => "\u{eff2}",
        "draw" => "\u{f04f3}",
        "draw_outlined" => "\u{f05ed}",
        "edit" => "\u{e21a}",
        "expand_more" => "\u{e246}",
        "fact_check" => "\u{e256}",
        "fact_check_outlined" => "\u{f045}",
        "folder_open" => "\u{e2a4}",
        "format_quote" => "\u{e2bc}",
        "forum" => "\u{e2c3}",
        "forum_outlined" => "\u{f0b0}",
        "graphic_eq" => "\u{e2e3}",
        "history" => "\u{e314}",
        "hourglass_empty" => "\u{e325}",
        "info_outline" => "\u{e33d}",
        "language" => "\u{e366}",
        "library_books" => "\u{e377}",
        "library_books_outlined" => "\u{f160}",
        "lock_outline" => "\u{e3b1}",
        "lock_outlined" => "\u{f197}",
        "menu" => "\u{e3dc}",
        "mic" => "\u{e3e1}",
        "more_horiz" => "\u{e402}",
        "person" => "\u{e491}",
        "person_outline" => "\u{e497}",
        "search" => "\u{e567}",
        "send" => "\u{e571}",
        "send_rounded" => "\u{f0147}",
        "settings" => "\u{e57f}",
        "smart_toy" => "\u{e5c5}",
        "smart_toy_outlined" => "\u{f3a8}",
        "stop" => "\u{e606}",
        "system_update" => "\u{e636}",
        "system_update_outlined" => "\u{f41a}",
        "text_snippet" => "\u{e651}",
        "tune" => "\u{e683}",
        "workspaces" => "\u{e6f5}",
        "dark_mode_outlined" => "\u{ef9f}",
        "psychology_outlined" => "\u{f2d2}",
        "memory" => "\u{e3db}",
        "record_voice_over" => "\u{e510}",
        _ => "\u{e88e}",
    }
}

#[component]
pub fn build_icon(name: String) -> Element {
    rsx! { span { class: "material-icons", "aria-hidden": "true", {glyph(&name)} } }
}
