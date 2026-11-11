// Описание: Регистрация, вход и управление профилями полностью на этом устройстве.
use crate::{
    app::{
        shared::icons,
        state::{self, AppState},
    },
    services::{
        self,
        local_accounts::{self, Account, Usage},
    },
};
use dioxus::prelude::*;
use zeroize::Zeroizing;
#[component]
pub fn build_local_accounts() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut accounts = use_signal(Vec::<Account>::new);
    let mut current = use_signal(|| None::<Account>);
    let mut usage = use_signal(Usage::default);
    let mut selected = use_signal(String::new);
    let mut login = use_signal(String::new);
    let mut name = use_signal(String::new);
    let mut password = use_signal(String::new);
    let mut new_password = use_signal(String::new);
    let mut confirmation = use_signal(String::new);
    let mut mode = use_signal(|| "login".to_string());
    let mut working = use_signal(|| false);
    use_future(move || async move {
        let result = async {
            let store = state::store(state)?;
            let root = services::paths::app_data_dir()?;
            let (list, active, stats) = services::runtime::blocking(move || {
                Ok((
                    local_accounts::list()?,
                    local_accounts::current(&store)?,
                    local_accounts::usage(&store, &root)?,
                ))
            })
            .await?;
            if let Some(first) = list.first() {
                selected.set(first.id.clone());
            }
            accounts.set(list);
            current.set(active);
            usage.set(stats);
            Ok(())
        }
        .await;
        state::report(state, result);
    });
    let active = current.read().clone();
    let used = usage.read().bytes as f64 / 1048576.0;
    rsx! {
        section{class:"section local-account-panel",
            h2{class:"section-title","Аккаунты на устройстве"}
            p{class:"notice","Сервер отключён. Регистрация, пароль и история работают локально; вход в облако и синхронизация не выполняются."}
            div{class:"account-statistics",
                span{"Чатов: {usage.read().chats}"}span{"Сообщений: {usage.read().messages}"}span{"Данные профиля: {used:.1} МиБ"}
            }
            if usage.read().cached_cloud{p{class:"notice","Сохранённое облачное подключение оставлено в базе. Сетевых запросов нет."}}
            if let Some(account)=active.clone(){
                div{class:"settings-card",icons::build_icon{name:"person"}span{class:"catalog-copy",strong{"{account.login}"}small{"Локальный аккаунт · облачный тариф не используется"}}}
                div{class:"row",
                    button{class:"button",disabled:*working.read()||state.read().unsaved,onclick:move|_|{spawn(async move{
                        working.set(true);let result=async{state::ensure_session_change(state)?;state::persist_draft(state).await?;let session=services::runtime::blocking(local_accounts::guest).await?;state::activate_session(state,session).await}.await;working.set(false);state::report(state,result);
                    });},"Выйти в профиль устройства"}
                    button{class:"button",disabled:*working.read(),onclick:move|_|{password.set(String::new());new_password.set(String::new());confirmation.set(String::new());mode.set("password".into());},"Изменить пароль"}
                    button{class:"button danger",disabled:*working.read(),onclick:move|_|{password.set(String::new());mode.set("delete".into());},"Удалить локальный аккаунт"}
                }
            }else{p{class:"notice","Сейчас открыт профиль устройства. Его прежняя история сохранится при входе в другой аккаунт."}}
            if mode.read().as_str()=="password"{
                label{class:"field","Текущий пароль",input{r#type:"password",autocomplete:"current-password",value:"{password}",oninput:move|e|password.set(e.value())}}
                label{class:"field","Новый пароль",input{r#type:"password",autocomplete:"new-password",value:"{new_password}",oninput:move|e|new_password.set(e.value())}}
                label{class:"field","Повторите новый пароль",input{r#type:"password",autocomplete:"new-password",value:"{confirmation}",oninput:move|e|confirmation.set(e.value())}}
                button{class:"button primary",disabled:*working.read()||state.read().unsaved,onclick:move|_|{spawn(async move{
                    working.set(true);let result=async{
                        state::ensure_session_change(state)?;state::persist_draft(state).await?;
                        let id=current.peek().as_ref().ok_or_else(||anyhow::anyhow!("Войдите в аккаунт"))?.id.clone();
                        anyhow::ensure!(*new_password.peek()==*confirmation.peek(),"Пароли не совпадают");
                        let old=Zeroizing::new(password.peek().clone());let new=Zeroizing::new(new_password.peek().clone());
                        password.set(String::new());new_password.set(String::new());confirmation.set(String::new());
                        let store=state::store(state)?;
                        let session=services::runtime::blocking(move||local_accounts::change_password(&store,&id,&old,&new)).await?;state::activate_session(state,session).await
                    }.await;working.set(false);state::report(state,result);
                });},"Сохранить новый пароль"}
                button{class:"button",onclick:move|_|{mode.set("login".into());password.set(String::new());new_password.set(String::new());confirmation.set(String::new());},"Отмена смены пароля"}
            }else if mode.read().as_str()=="delete"{
                p{class:"notice","Будут удалены история и материалы только этого локального аккаунта. Другие профили, внешние папки проектов и модели сохранятся."}
                label{class:"field","Пароль для удаления",input{r#type:"password",value:"{password}",oninput:move|e|password.set(e.value())}}
                button{class:"button danger",disabled:*working.read()||state.read().unsaved,onclick:move|_|{spawn(async move{
                    working.set(true);let result=async{
                        state::ensure_session_change(state)?;state::persist_draft(state).await?;
                        let id=current.peek().as_ref().ok_or_else(||anyhow::anyhow!("Войдите в аккаунт"))?.id.clone();let password_value=Zeroizing::new(password.peek().clone());password.set(String::new());
                        let store=state::store(state)?;
                        let session=services::runtime::blocking(move||{let guest=local_accounts::guest()?;local_accounts::delete(&store,&id,&password_value)?;Ok(guest)}).await?;state::activate_session(state,session).await
                    }.await;working.set(false);state::report(state,result);
                });},"Подтвердить удаление аккаунта"}
                button{class:"button",onclick:move|_|{mode.set("login".into());password.set(String::new());},"Отмена удаления аккаунта"}
            }else{
                div{class:"row",button{class:"button",onclick:move|_|mode.set("login".into()),"Войти локально"}button{class:"button",onclick:move|_|mode.set("register".into()),"Создать локальный аккаунт"}}
                if mode.read().as_str()=="register"{
                    label{class:"field","Локальный логин",input{value:"{login}",autocomplete:"username",maxlength:80,oninput:move|e|login.set(e.value())}}
                    label{class:"field","Имя нового профиля",input{value:"{name}",maxlength:50,oninput:move|e|name.set(e.value())}}
                }else{
                    label{class:"field","Выберите аккаунт",crate::app::shared::select::build_select{id:"local-account-choice",label:"Выберите аккаунт",value:selected.read().clone(),options:accounts.read().iter().map(|account|(account.id.clone(),account.login.clone())).collect::<Vec<_>>(),onchange:move|id:String|selected.set(id)}}
                }
                label{class:"field","Пароль локального аккаунта",input{r#type:"password",autocomplete:if mode.read().as_str()=="register"{"new-password"}else{"current-password"},value:"{password}",oninput:move|e|password.set(e.value())}}
                if mode.read().as_str()=="register"{label{class:"field","Повторите пароль",input{r#type:"password",autocomplete:"new-password",value:"{confirmation}",oninput:move|e|confirmation.set(e.value())}}}
                button{class:"button primary",disabled:*working.read()||state.read().unsaved,onclick:move|_|{spawn(async move{
                    working.set(true);let result=async{
                        state::ensure_session_change(state)?;state::persist_draft(state).await?;
                        let register=mode.peek().as_str()=="register";
                        if register{anyhow::ensure!(*password.peek()==*confirmation.peek(),"Пароли не совпадают");}
                        let login=login.peek().clone();let name=name.peek().clone();let id=selected.peek().clone();
                        let secret=Zeroizing::new(password.peek().clone());password.set(String::new());confirmation.set(String::new());
                        let session=services::runtime::blocking(move||if register{local_accounts::register(&login,&name,&secret)}else{local_accounts::login(&id,&secret)}).await?;
                        state::activate_session(state,session).await
                    }.await;working.set(false);state::report(state,result);
                });},if *working.read(){"Подождите…"}else if mode.read().as_str()=="register"{"Зарегистрировать на устройстве"}else{"Открыть аккаунт"}}
                p{class:"notice","Пароль защищает отдельную зашифрованную историю. Сервер не получает логин или пароль; восстановление через почту сейчас недоступно."}
            }
        }
    }
}
