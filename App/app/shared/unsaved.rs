// Описание: Единая защита форм, которые сохраняются явной кнопкой.
use crate::app::state::AppState;
use dioxus::prelude::*;

/// Связывает изменённую форму с общей защитой переходов.
pub fn use_unsaved(dirty: Signal<bool>) {
    let mut state = use_context::<Signal<AppState>>();
    use_effect(move || {
        state.write().unsaved = *dirty.read()
    });
    use_drop(move || {
        if let Ok(mut value) = state.try_write() {
            value.unsaved = false;
        }
    });
}
