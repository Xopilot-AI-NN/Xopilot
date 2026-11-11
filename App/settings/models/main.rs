// Описание: Каталог и общий фоновый загрузчик; закрытие окна не останавливает скачивание.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState, Screen},
    },
    services::{
        self,
        model_installer::{self, MODELS},
    },
};
use dioxus::prelude::*;

#[component]
pub fn build_model_catalog() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut statuses = use_signal(|| {
        MODELS
            .iter()
            .map(|m| model_installer::progress(m.id))
            .collect::<Vec<_>>()
    });
    let mut import_path = use_signal(String::new);
    let mut importing = use_signal(|| false);
    let mut import_open = use_signal(|| false);
    use_future(move || async move {
        loop {
            let next = MODELS
                .iter()
                .map(|m| model_installer::progress(m.id))
                .collect::<Vec<_>>();
            if *statuses.peek() != next {
                statuses.set(next);
            }
            services::runtime::background(async {
                tokio::time::sleep(std::time::Duration::from_millis(250)).await
            })
            .await;
        }
    });
    rsx! {
        div { class:"model-catalog",
            for (index,spec) in MODELS.iter().copied().enumerate() {
                crate::app::models::model_download::build_model_row { key:"{spec.id}",id:spec.id.to_string(),progress:statuses.read().get(index).cloned().unwrap_or_default() }
            }
            button{class:"model-import-trigger",onclick:move|_|{let next=!*import_open.peek();import_open.set(next);},icons::build_icon{name:"folder_open"}span{"Установить модель из файла"}icons::build_icon{name:if *import_open.read(){"expand_less"}else{"expand_more"}}}
            if *import_open.read(){section { class:"model-import-panel",
                label {class:"field","Импорт скачанного файла",input {value:"{import_path}",placeholder:"Путь к оригинальному .litertlm",oninput:move|e|import_path.set(e.value())}}
                div {class:"row",for spec in MODELS.iter().copied(){button {class:"button",disabled:*importing.read(),onclick:move|_|{spawn(async move{
                    importing.set(true);
                    let path=std::path::PathBuf::from(import_path.peek().clone());
                    let result=services::runtime::blocking(move||model_installer::import(spec,&path)).await;
                    importing.set(false);
                    if result.is_ok(){state.write().notice=Some("Модель импортирована; выберите её в каталоге".into());}
                    state::report(state,result);
                });},"Импорт {spec.name}"}} }
                p {class:"notice","Модель проверяется по SHA-256. Загрузка и импорт не отправляют переписку в сеть."}
                if *importing.read(){p{class:"notice",role:"status","Копируем файл и проверяем целостность…"}}
            }}
            button {class:"settings-navigation-row model-api-row",onclick:move|_|state::navigate(state,Screen::Api),span{class:"preference-icon tone-ai",icons::build_icon{name:"api"}}span{class:"catalog-copy",strong{"Подключить API"}small{"Google AI Studio, OpenRouter или свой сервер"}}icons::build_icon{name:"chevron_right"}}
            div{class:"model-catalog-footer",p{class:"notice","Файлы хранятся на устройстве. Во время скачивания можно закрыть это окно."}
                button {class:"text-button",disabled:state.read().busy,onclick:move|_|{spawn(async move{state::report(state,services::runtime::blocking(services::litert::unload).await);});},"Освободить память"}
            }
            if !services::litert::available(){p{class:"notice","В этой сборке отсутствует библиотека LiteRT. Нужна сборка со встроенным runtime."}}
        }
    }
}
