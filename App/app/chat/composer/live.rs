// Добавил полный цикл Live и отдельную кнопку озвучивания готового ответа.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services::{
        self,
        live::{Client, Phase},
    },
};
use dioxus::prelude::*;
use tokio_util::sync::CancellationToken;

struct LiveClient {
    state: Signal<AppState>,
    phase: Signal<u8>,
    store: services::db::Store,
    chat: Option<i64>,
}
impl Client for LiveClient {
    /// Не продолжаю разговор после смены чата или выключения Live.
    fn active(&self) -> bool {
        let state = self.state.read();
        state.live_active
            && state.active == self.chat
            && !state.busy
    }
    /// Только запись и распознавание владеют флагом загрузки аудио.
    fn phase(&mut self, phase: Phase) {
        self.phase.set(match phase {
            Phase::Listening => 1,
            Phase::Recognizing => 2,
            Phase::Answering => 3,
            Phase::Speaking => 4,
        });
        self.state.write().uploading = matches!(
            phase,
            Phase::Listening | Phase::Recognizing
        );
    }
    /// Запись завершается паузой, ограничением времени или отменой.
    async fn listen(
        &mut self,
        token: CancellationToken,
    ) -> anyhow::Result<Vec<u8>> {
        services::voice::record_options(token, true).await
    }
    /// Передаю запись только выбранной модели, текст ещё не является действием агента.
    async fn recognize(
        &mut self,
        audio: Vec<u8>,
        token: CancellationToken,
    ) -> anyhow::Result<String> {
        let config =
            services::generation::audio_configuration(
                &self.store,
            )?;
        services::runtime::background(
            services::voice::transcribe(
                config, audio, token,
            ),
        )
        .await
    }
    /// Обычный обработчик сохраняет историю, выполняет агента и принимает уточнения.
    async fn answer(
        &mut self,
        text: String,
        token: CancellationToken,
    ) -> anyhow::Result<String> {
        let sending = state::send_live(self.state, text);
        tokio::pin!(sending);
        tokio::select! {
            result=&mut sending=>result?,
            _=token.cancelled()=>{
                state::cancel(self.state);
                sending.await?;
            }
        }
        Ok(self
            .state
            .read()
            .messages
            .iter()
            .rev()
            .find(|m| {
                m.role == "ai" || m.role == "assistant"
            })
            .map(|m| m.content.clone())
            .unwrap_or_default())
    }
    /// Отмена сессии закрывает также уже открытый вывод звука.
    async fn speak(
        &mut self,
        text: String,
        token: CancellationToken,
    ) -> anyhow::Result<()> {
        let voice_token = services::speech::begin();
        let speaking = services::speech::speak(
            text,
            voice_token.clone(),
        );
        tokio::pin!(speaking);
        let outcome = tokio::select! {
            result=&mut speaking=>result,
            _=token.cancelled()=>{
                voice_token.cancel();
                let _=speaking.await;
                Ok(())
            }
        };
        if voice_token.is_cancelled() {
            self.state.write().live_active = false;
            return Ok(());
        }
        outcome
    }
}

/// Начало и повторное нажатие управляют всей сессией, а не только иконкой.
fn toggle_live(
    mut state: Signal<AppState>,
    mut phase: Signal<u8>,
    mut cancellation: Signal<Option<CancellationToken>>,
) {
    if let Some(token) = cancellation.read().as_ref() {
        token.cancel();
        if *phase.read() == 3 {
            state::cancel(state);
        }
        services::speech::stop();
        return;
    }
    let result = (|| -> anyhow::Result<_> {
        let value = state.read();
        anyhow::ensure!(
            value.draft.text.trim().is_empty()
                && value.draft.files.is_empty()
                && value.message_queue.is_empty(),
            "Сначала отправьте или сохраните текущий черновик перед Live"
        );
        drop(value);
        let store = state::store(state)?;
        services::generation::audio_configuration(&store)?;
        Ok(store)
    })();
    let store = match result {
        Ok(store) => store,
        Err(error) => {
            state::report(state, Err(error));
            return;
        }
    };
    services::speech::stop();
    let token = CancellationToken::new();
    cancellation.set(Some(token.clone()));
    state.write().live_active = true;
    phase.set(1);
    let mut client = LiveClient {
        state,
        phase,
        store,
        chat: state.read().active,
    };
    spawn(async move {
        let result =
            services::live::run(&mut client, token.clone())
                .await;
        state.write().uploading = false;
        state.write().live_active = false;
        phase.set(0);
        cancellation.set(None);
        if !token.is_cancelled() {
            state::report(state, result);
        }
    });
}

/// Live включается явно и прекращает захват звука при уходе приложения в фон.
#[component]
pub fn build_live_button() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let phase = use_signal(|| 0_u8);
    let cancellation =
        use_signal(|| None::<CancellationToken>);
    use_drop(move || {
        if let Some(token) = cancellation.read().as_ref() {
            token.cancel();
        }
        if let Ok(mut value) = state.try_write()
            && value.live_active
        {
            value.live_active = false;
            value.uploading = false;
            if *phase.read() == 3
                && let Some(token) =
                    value.cancelled.as_ref()
            {
                token.cancel();
            }
            services::speech::stop();
        }
    });
    use_future(move || async move {
        let mut bridge = document::eval(
            r#"
            const hidden=()=>{if(document.hidden)dioxus.send(true);};
            document.addEventListener('visibilitychange',hidden);
            try{await dioxus.recv();}finally{document.removeEventListener('visibilitychange',hidden);}
        "#,
        );
        while bridge.recv::<bool>().await.is_ok() {
            services::speech::stop_hidden();
            if let Some(token) =
                cancellation.read().as_ref()
            {
                token.cancel();
                if *phase.read() == 3 {
                    state::cancel(state);
                }
            }
        }
    });
    let label = if *phase.read() == 0 {
        "Live — голосовой разговор"
    } else {
        "Остановить Live"
    };
    rsx! {
        button {
            class: "brand-button tone-ai",
            style: "--button-size:40px",
            title: label,
            "aria-label": label,
            "aria-pressed": *phase.read()!=0,
            disabled: *phase.read()==0 && (state.read().busy||state.read().uploading),
            onclick: move |_| toggle_live(state,phase,cancellation),
            icons::build_icon {
                name: if *phase.read()==0 {"graphic_eq"}else{"stop"},
            }
        }
        if *phase.read()!=0 {
            span {
                class: "notice live-phase",
                role: "status",
                {match *phase.read(){1=>"Слушаю…",2=>"Распознаю речь…",3=>"ИИ отвечает…",_=>"Озвучиваю…"}}
            }
        }
    }
}

/// Готовый ответ можно прослушать отдельно от Live и остановить повторным нажатием.
fn toggle_speech(
    state: Signal<AppState>,
    text: String,
    mut active: Signal<bool>,
    mut cancellation: Signal<Option<CancellationToken>>,
) {
    if let Some(token) = cancellation.read().as_ref() {
        token.cancel();
        return;
    }
    let token = services::speech::begin();
    cancellation.set(Some(token.clone()));
    active.set(true);
    spawn(async move {
        let result =
            services::speech::speak(text, token.clone())
                .await;
        active.set(false);
        cancellation.set(None);
        if !token.is_cancelled() {
            state::report(state, result);
        }
    });
}

/// Отдельный компонент владеет только своим воспроизведением, не чужой задачей чата.
#[component]
pub fn build_speech_button(text: String) -> Element {
    let state = use_context::<Signal<AppState>>();
    let active = use_signal(|| false);
    let cancellation =
        use_signal(|| None::<CancellationToken>);
    use_drop(move || {
        if let Some(token) = cancellation.read().as_ref() {
            token.cancel();
        }
    });
    let label = if *active.read() {
        "Остановить озвучивание"
    } else {
        "Озвучить ответ"
    };
    rsx! {
        button {
            class: "message-action",
            title: label,
            "aria-label": label,
            disabled: state.read().live_active,
            onclick: move |_| toggle_speech(state,text.clone(),active,cancellation),
            icons::build_icon {
                name: if *active.read(){"stop"}else{"volume_up"},
            }
        }
    }
}
