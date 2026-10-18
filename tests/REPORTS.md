# Отчёт о проверках Xopilot

Дата: 13 октября 2026 года, Europe/Minsk.
Исполнитель всех отмеченных как проведённые проверок: **я, Codex, ИИ-ассистент**. Я запускал автоматические тесты и управлял настоящим интерфейсом POCO через ADB. Авторство исходных тестов этим не присваивается. Статус «не выполнен» означает отсутствие проверки, а не успешный результат.

## Итог и границы

- Полный набор Python-тестов: **356 выполнены успешно, 0 ошибок, 0 провалов, 0 пропусков**, 203,729 секунды. После добавления запрета очистки при активном превью повторно выполнены 12 проверок жизненного цикла памяти (0,545 с); все прошли. В таблице ниже **357 разных Python-тестов**: 356 полного запуска и одна новая проверка превью.
- Настоящий PostgreSQL/API использовался только в отдельной базе `xopilot_test`; пользовательская база не очищалась. Часть остальных тестов использует временные файлы, настоящую SQLCipher и тестовые замены сети/модели/интерфейса. Успех таких тестов не означает проверку всех функций на настоящем устройстве.
- Rust: `cargo test --manifest-path Services/Cargo.toml --offline --lib` — **4 выполнены успешно**, 0 провалов. Проверены повреждённая соль, отсутствие замены потерянного ключа существующей базы и переход между keyring/резервным способом. Это локальные тесты, не аудит сервера.
- Настоящие ручные проверки проводились на POCO X5 5G и профиле ПК. После просьбы пользователя Live, микрофон и воспроизведение звука не запускались. Результаты Live ниже относятся к более ранней разрешённой проверке 12 октября.
- Цель **не более 140 МБ ОЗУ вне работы модели пока не достигнута**. Использование памяти модели/GPU, весь процесс приложения и размер APK — разные показатели. Ни один из них не подменяет другой.
- Это функциональная проверка и отдельные проверки защитных свойств, **не сертификат безопасности и не завершённый независимый аудит приложения/сервера**.

## Настоящие сценарии и нерешённые вопросы

| Проверка | Состояние | Что проверено / что не так |
| --- | --- | --- |
| Установка APK поверх существующей базы POCO | Выполнен, успешно (4046 и 4048) | Вход и история сохранены. Финальная 4048 установлена поверх существующих данных; вход и история сохранены. |
| Ответы через настроенный API | Выполнен | Получены настоящие ответы на телефоне. Это не оценка качества всех моделей. |
| Агент создаёт и изменяет Canvas | Выполнен, успешно | Настоящий API создал файл с `print(42)`, затем изменил на `print(43)`; правка с ПК `print(44)` появилась на телефоне. |
| Рисование Canvas | Выполнен, успешно | Штрихи сохраняются, повторно открываются и экспортируются в PNG. |
| Удаление последнего Canvas | Выполнен, успешно | Исправлено повторное создание пустого документа; редактор закрывается. |
| Папка проекта на телефоне | Выполнен, успешно | Создание/чтение файла, добавление копии в библиотеку; системные команды на Android запрещены. |
| Файлы и команды проекта на ПК | Выполнен, успешно на уровне сервисов Linux | Реально записан/прочитан временный файл и запущен Python, вывод `42`. Отклонённое действие не выполняется; выход за папку, ссылки и изменение файла после просмотра отклоняются. База и подтверждение в этом тесте заменены тестовыми объектами. |
| Полный диалог агента → подтверждение команды пользователем на ПК | Не выполнен | Инструмент и окно подключены в коде; настоящий сквозной сценарий запуска команды через интерфейс ПК ещё не проверен. |
| Доступ ИИ «к чему угодно в системе» | Не предоставлен автоматически | Файловые инструменты работают в выбранной папке. Подтверждённые команды имеют права пользователя ОС и могут влиять за пределами папки; это не системная песочница. |
| Синхронизация чатов/материалов/пространств/Canvas телефон ↔ ПК | Выполнен, успешно | Проверены настоящие изменения и совпадение содержимого материалов. Это не проверка всех возможных сетевых сбоев на телефоне. |
| Конфликт профиля, фото и памяти | Выполнен, успешно | Проверено сравнение двух версий; сохранена память телефона и резервная версия облака. После синхронизации факт пришёл на ПК, конфликтов нет. Устаревший выбор проверен отдельными тестами. |
| Удалённая неиспользуемая копия не возвращается | Выполнен, успешно | На APK 4046 удалена только собственная тестовая копия `qa-4042.txt`; после двух ручных синхронизаций она не вернулась ни в материалы, ни в корзину. |
| Действующее вложение восстанавливается из облака | Выполнен, успешно | Проверено с настоящим API и двумя временными SQLCipher-профилями. |
| Просмотр/экспорт материала и Android SAF | Выполнен, успешно | Настоящее текстовое вложение просмотрено и сохранено; сохранение PNG тоже проверено. |
| Корзина, восстановление, локальная копия, загрузка из облака | Выполнен, успешно | Проверено через интерфейс и отдельные автоматические тесты; исходный файл вне управляемого хранилища сохраняется. |
| Память обо мне | Выполнен | Вопрос об имени не записывается как факт, сохранённое имя используется в ответе. Семантическое качество извлечения всех видов фактов полностью не оценено. |
| Имена устройств | Выполнен, успешно | Телефон отображается как POCO X5 5G, вместо localhost. |
| Native Live/JNI после исправления R8 | Выполнен 12 октября | Причина SIGABRT установлена по журналу: удалённые R8 JNI-геттеры. После исправления три последовательных текстовых запроса завершились без падения. В текущей тихой проверке Live не запускался. |
| Качество локальной Gemma4-e2b | Проблема обнаружена | Первый математический ответ был неверным; последующие два правильными. Общую точность модели не объявляю проверенной. |
| Русский офлайн-голос Android | Не готов | На телефоне не установлен подходящий офлайн-голос `ru`. Тихая проверка не включает воспроизведение. |
| Распознавание настоящей речи | Не выполнен полностью | Нет подтверждённого полного сценария речь → ответ → звук в этой проверке. |
| Камера и демонстрация экрана | Частично выполнен 12 октября | Разрешения/активный захват/отключение проверены. Ответ модели по настоящему кадру и внешний вид защищённого плавающего превью полностью не проверены. |
| Плавающее превью поверх других приложений | Частично выполнен | Запуск оверлея проверен; FLAG_SECURE не позволил оценить содержимое по снимку. Защита не обходилась. |
| Google вход | Выполнен ранее | Настоящий OAuth-возврат проверен ранее. Новый вход сейчас повторно не выполнялся. |
| SMTP регистрации | Не готов | Провайдер/отправка настоящего письма ещё не настроены; тестовый почтовый транспорт не подтверждает доставку реального SMTP. |
| DonationAlerts, выдача тарифа после настоящей оплаты | Не выполнен | Настройки OAuth владельца отсутствуют. Тарифы/интеграционные проверки не являются настоящей покупкой. Деньги не списывались. |
| Перенос серверных файлов на /data_2 | Выполнен ранее, успешно | Проверены количество/хеши 41 зашифрованного файла и собственная тестовая загрузка через API. В текущем запуске серверный перенос не повторялся. |
| Windows: сборка и реальный запуск | Не выполнен здесь | Исправления CI в коде не являются подтверждённой Windows-сборкой. |
| ChromeOS/x86_64 на настоящем устройстве | Не выполнен | Устройство отсутствует. Проверка пакета не заменяет проверку системы. |
| POCO: лимит 140 МБ | Не достигнут | До изменения: PSS 236259 КиБ после обычного запуска; после длительного использования было 300883 КиБ. Однократный предварительный замер 188409 КиБ не воспроизведён на том же открытом экране и не считается устойчивым результатом оптимизации. На промежуточной APK 4047: PSS 253582 КиБ через 20 с, 252621 КиБ через 80 с; вызов очистки подтверждён журналом. После системного memory-pressure уведомления: 247895 КиБ. Окончательная 4048: PSS 243586 КиБ через 20 с и 242641 КиБ (236,95 МиБ) через 80 с. RSS 364724 и 364684 КиБ. Очистка сработала по таймеру, подтверждена журналом; базовый расход почти не уменьшился, GPU/ИИ при этом не запускался. |
| Linux: лимит 140 МБ, чистый профиль, без модели | Не достигнут | Python + Flet и их дочерние процессы: PSS 190404 КиБ через 20 с; PSS 195891 КиБ через 65 с. Это суммарный расход, а не только Python. RSS соответственно 282360 и 265052 КиБ. |
| Освобождение памяти после простоя | Выполнен, эффект ограничен | Очистка временных миниатюр/Python и графических кэшей после 60 с; активный запрос/Live/превью камеры или экрана/открытое окно блокируют очистку. Закрытые окна учитываются слабыми ссылками. На телефоне вызов подтверждён, но цель 140 МБ не выполнена; нельзя считать один вызов очистки доказательством существенного уменьшения ОЗУ. |

## Как запускалось

Полный набор загружен стандартным `unittest.defaultTestLoader.discover("tests")`. В `sys.path` добавлены корень репозитория и `tests`, поскольку некоторые существующие тесты импортируют общие фикстуры по короткому имени. SSH-туннель использовался для базы `xopilot_test`; секреты не записаны в этот отчёт. Новый тестовый аккаунт и временные профили создавались самим тестом.

Полный запуск: `/tmp/xopilot-fulltests-20261013.log`; машинные результаты каждого теста: `/tmp/xopilot-fulltest-results-20261013.json`. Файлы `/tmp` временные; таблица результатов ниже сохранена в репозитории. Более подробные телефонные наблюдения находятся в локальных `docs/PHONE_QA_20261012.md` и `docs/PHONE_QA_20261013.md`.

При первом точечном запуске произошла ошибка загрузчика из-за отсутствующего `tests` в пути импортов; после корректировки пути 47 точечных тестов прошли. Это ошибка команды проверки, не результат тестируемой функции. Первая сборка оптимизации не прошла из-за обращения к защищённому `getFlutterEngine()`; обращение заменено публичным Android callback `onTrimMemory`, промежуточная APK 4047 собрана успешно; окончательные ARM64 4048 и x86_64 6048 с запретом очистки при превью успешно собраны. Ошибки расшифровки в журнале отрицательных тестов SQLCipher ожидаемы: тест намеренно использует неверный ключ.

## Автоматические тесты по модулям

| Модуль | Выполнено успешно | Не выполнено / провалено |
| --- | ---: | ---: |
| `test_acceleration_runtime.py` | 10 | 0 |
| `test_canvas_library_agent.py` | 12 | 0 |
| `test_catalog_api_titles.py` | 14 | 0 |
| `test_cloud_account.py` | 18 | 0 |
| `test_cloud_storage_and_billing.py` | 4 | 0 |
| `test_cloud_sync_integration.py` | 8 | 0 |
| `test_dictation.py` | 21 | 0 |
| `test_donationalerts.py` | 13 | 0 |
| `test_donationalerts_setup.py` | 3 | 0 |
| `test_exports.py` | 3 | 0 |
| `test_final_workflows.py` | 10 | 0 |
| `test_finishing_features.py` | 10 | 0 |
| `test_live.py` | 29 | 0 |
| `test_live_vision_markdown.py` | 10 | 0 |
| `test_local_workflows.py` | 13 | 0 |
| `test_memory_lifecycle.py` | 12 | 0 |
| `test_miku_voice.py` | 12 | 0 |
| `test_mobile.py` | 19 | 0 |
| `test_mobile_documents.py` | 8 | 0 |
| `test_model_downloads.py` | 5 | 0 |
| `test_model_paths.py` | 3 | 0 |
| `test_native_db.py` | 9 | 0 |
| `test_personal_memory_storage.py` | 12 | 0 |
| `test_piper_voice.py` | 6 | 0 |
| `test_private_chats.py` | 22 | 0 |
| `test_profile.py` | 7 | 0 |
| `test_profile_conflict_preview.py` | 5 | 0 |
| `test_real_answers.py` | 18 | 0 |
| `test_sidebar_chats.py` | 3 | 0 |
| `test_sync_crypto.py` | 2 | 0 |
| `test_sync_recovery.py` | 2 | 0 |
| `test_sync_transport.py` | 4 | 0 |
| `test_ui_improvements.py` | 5 | 0 |
| `test_updates.py` | 4 | 0 |
| `test_voice_selection.py` | 21 | 0 |

## Результат каждого автоматического теста

### test_acceleration_runtime.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `AccelerationTests.test_auto_retries_a_previously_busy_gpu_on_a_later_request` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccelerationTests.test_container_size_and_moderate_display_activity_do_not_reject_gpu` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccelerationTests.test_device_preference_change_reloads_before_next_request` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccelerationTests.test_full_or_sustained_busy_gpu_defers_to_cpu_but_explicit_gpu_is_honored` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccelerationTests.test_gpu_init_failure_falls_back_only_in_auto` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccelerationTests.test_model_button_reports_actual_backend_and_fallback_then_clears_on_unload` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccelerationTests.test_transient_utilization_spike_does_not_force_cpu` | Выполнен, успешно | Замечаний в этой проверке нет |
| `FileSelectionTests.test_cancel_returns_no_files_and_does_not_write_materials` | Выполнен, успешно | Замечаний в этой проверке нет |
| `FileSelectionTests.test_native_path_and_browser_bytes_produce_independent_copies` | Выполнен, успешно | Замечаний в этой проверке нет |
| `RuntimeTests.test_cli_temp_and_working_directory_move_out_of_watched_sources` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_canvas_library_agent.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `DocumentWorkflowTests.test_agent_cannot_read_other_workspaces_canvas` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_agent_executes_multiple_tools_and_saves_actual_document` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_agent_level_stops_tool_loop_and_preserves_created_document` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_cancelled_agent_cannot_write_canvas` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_disabled_material_is_not_given_to_chat_or_agent` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_folder_copies_keep_structure_and_skip_symlinks_hidden_build` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_missing_cloud_copies_have_distinct_library_actions_and_are_not_directories` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_retry_of_same_agent_request_does_not_duplicate_canvas` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_search_phrase_finds_facts_spread_between_documents` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentWorkflowTests.test_text_and_drawing_survive_database_reopen_and_export` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ThemeRoundtripTests.test_all_seven_palettes_restore_shared_styles_and_text` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ThemeRoundtripTests.test_code_blocks_follow_all_dark_and_light_palettes` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_catalog_api_titles.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `ApiTransportTests.test_api_http_transmits_full_history_and_attachments` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ApiTransportTests.test_api_validation_and_pre_cancel` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ApiTransportTests.test_cancel_interrupts_waiting_http_body` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ApiTransportTests.test_dropdown_uses_input_surface_and_rounded_menu` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ApiTransportTests.test_google_ai_studio_preset_uses_compatible_endpoint_and_separates_provider_keys` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ApiTransportTests.test_text_and_custom_models_do_not_fetch_catalog` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ApiTransportTests.test_text_only_model_rejects_images_before_sending_chat` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ApiTransportTests.test_unavailable_catalog_is_unknown_and_does_not_leak_key` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CatalogPersistenceTests.test_agent_resolves_canvas_title_but_rejects_ambiguous_names` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CatalogPersistenceTests.test_api_configuration_reopens_without_plaintext_key_on_disk` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CatalogPersistenceTests.test_auto_agent_extends_steps_only_when_needed` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CatalogPersistenceTests.test_chat_title_uses_first_question_and_keeps_manual_names` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CatalogPersistenceTests.test_existing_unnamed_chats_are_named_from_history` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CatalogPersistenceTests.test_project_icon_survives_edit_and_reopen` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_cloud_account.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `AccountTests.test_confirmation_rejects_incorrect_code_before_network` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_credentials_are_hidden_from_ui_and_chat_content_not_read` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_endpoint_cannot_downgrade_or_embed_credentials` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_failed_storage_is_not_reported_as_successful_signin` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_google_avatar_download_never_sends_credentials_and_is_bounded` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_google_does_not_overwrite_another_login` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_google_login_imports_profile_and_photo_failure_keeps_session` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_google_login_persists_only_own_session` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_google_pending_and_failure_never_save_account` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_google_profile_refresh_retains_rotated_credentials` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_google_proof_stays_ephemeral_and_outside_browser_url` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_google_rejects_foreign_browser_urls_before_launch` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_network_failure_does_not_silently_leave_server_session_active` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_redirect_never_receives_password_or_token` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_registration_does_not_store_session_password_or_code` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_registration_rejects_mismatched_password_and_bad_email_before_network` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_revoked_refresh_removes_saved_session` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AccountTests.test_verified_confirmation_persists_only_server_identity` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_cloud_storage_and_billing.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `CloudStorageBilling.test_corrupted_exchange_rate_cache_does_not_break_plan_list` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CloudStorageBilling.test_currency_region_override_and_decimal_prices` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CloudStorageBilling.test_rolling_budget_owner_isolation_and_failed_attempts` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CloudStorageBilling.test_trash_restore_and_permanent_delete_only_managed_copy` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_cloud_sync_integration.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `SyncIntegration.test_cloud_material_exclusion_reinclude_and_private_conflict_recovery` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncIntegration.test_deferred_categories_and_conflicts_keep_both` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncIntegration.test_library_names_notes_and_later_material_enable_converge_after_reopen` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncIntegration.test_new_device_first_pull_after_linked_chat_was_already_deleted` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncIntegration.test_profile_avatar_name_are_encrypted_and_conflicts_preserve_versions` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncIntegration.test_protected_vault_transfers_only_after_close_temporary_never_transfers` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncIntegration.test_two_profiles_files_projects_edits_deletes_and_retry_budget` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncIntegration.test_unused_purged_copy_is_not_redownloaded_but_live_attachment_is` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_dictation.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `MicrophoneTests.test_cancel_discards_audio_and_allows_new_recording` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MicrophoneTests.test_capture_limit_trims_last_block` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MicrophoneTests.test_device_error_does_not_leave_stream_open` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MicrophoneTests.test_empty_short_and_silent_recordings_are_rejected` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MicrophoneTests.test_missing_portaudio_is_a_recoverable_error` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MicrophoneTests.test_overflow_is_reported_instead_of_transcribing_incomplete_audio` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MicrophoneTests.test_stop_returns_valid_wav_and_releases_microphone` | Выполнен, успешно | Замечаний в этой проверке нет |
| `TranscriptionTests.test_audio_uses_separate_conversation_and_no_chat_statistics` | Выполнен, успешно | Замечаний в этой проверке нет |
| `TranscriptionTests.test_cancellation_stops_native_inference_before_closing_conversation` | Выполнен, успешно | Замечаний в этой проверке нет |
| `TranscriptionTests.test_cancelled_job_does_not_load_or_use_model` | Выполнен, успешно | Замечаний в этой проверке нет |
| `TranscriptionTests.test_missing_audio_support_and_empty_transcript_are_reported` | Выполнен, успешно | Замечаний в этой проверке нет |
| `TranscriptionTests.test_missing_model_is_reported_without_downloading` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_busy_chat_and_browser_do_not_open_microphone` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_cancel_inference_discards_late_result` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_cancel_preserves_draft_and_does_not_transcribe` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_close_during_microphone_start_releases_device` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_error_preserves_draft_and_restores_button` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_limit_automatically_stops_and_transcribes` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_repeated_clicks_do_not_start_multiple_recordings` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_stop_appends_to_current_draft_without_sending` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceInputTests.test_transcription_error_keeps_draft_and_allows_retry` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_donationalerts.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `AndroidBrowserTests.test_android_refuses_non_https_credentials_or_javascript` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AndroidBrowserTests.test_android_uses_native_browser_not_unmounted_url_launcher` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AndroidBrowserTests.test_google_button_launches_browser_and_recovers_transient_poll_failure` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CheckoutTests.test_checkout_sends_only_plan_and_uses_server_quote` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CheckoutTests.test_order_check_and_cancel_do_not_allow_arbitrary_paths` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CheckoutTests.test_payment_status_must_belong_to_the_requested_order` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CheckoutTests.test_signed_out_never_queries_or_opens_payment` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CheckoutTests.test_untrusted_payment_links_and_amounts_are_rejected` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PaymentInterfaceTests.test_account_failure_is_not_presented_as_a_free_subscription` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PaymentInterfaceTests.test_active_plan_prevents_accidental_second_plan_order` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PaymentInterfaceTests.test_automatic_confirmation_refreshes_without_cancelling_itself` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PaymentInterfaceTests.test_closed_dialog_never_reappears_when_order_request_finishes` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PaymentInterfaceTests.test_order_dialog_keeps_pending_payment_and_refreshes_after_server_confirmation` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_donationalerts_setup.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `OwnerOAuthTests.test_exchange_verifies_recipient_and_donation_scope_before_saving` | Выполнен, успешно | Замечаний в этой проверке нет |
| `OwnerOAuthTests.test_request_and_callback_require_exact_state_and_one_code` | Выполнен, успешно | Замечаний в этой проверке нет |
| `OwnerOAuthTests.test_token_file_is_private_and_cannot_replace_an_existing_file_or_symlink` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_exports.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `ExportTests.test_drawing_export_preserves_canvas_proportions` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ExportTests.test_exports_preserve_bytes_and_never_overwrite_or_escape_folder` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ExportTests.test_failed_export_removes_its_partial_file` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_final_workflows.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `EmptyChatTests.test_real_database_drafts_messages_canvas_and_deleted_chat` | Выполнен, успешно | Замечаний в этой проверке нет |
| `FinalComposerTests.test_rejected_live_question_keeps_draft_and_shows_error` | Выполнен, успешно | Замечаний в этой проверке нет |
| `FinalComposerTests.test_typed_live_question_uses_main_composer_without_ordinary_generation` | Выполнен, успешно | Замечаний в этой проверке нет |
| `FinalComposerTests.test_unused_current_chat_is_reused_and_draft_forces_new_chat` | Выполнен, успешно | Замечаний в этой проверке нет |
| `HistoryTests.test_history_delete_persists_only_selected_chat_and_keeps_other_messages` | Выполнен, успешно | Замечаний в этой проверке нет |
| `HistoryTests.test_individual_delete_removes_selected_row_only` | Выполнен, успешно | Замечаний в этой проверке нет |
| `InlineCallTests.test_open_and_close_use_inline_controls_no_live_dialog` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncToggleTests.test_enable_guides_setup_then_persists_enabled_only_after_success` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncToggleTests.test_enable_with_saved_key_starts_transfer_and_busy_does_not_refresh_chat` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SyncToggleTests.test_failed_password_keeps_sync_disabled_and_dialog_open` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_finishing_features.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `ChatPreviewTests.test_chat_material_click_uses_shared_viewer` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DeviceAndMemoryTests.test_android_uses_actual_model_not_localhost` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DeviceAndMemoryTests.test_memory_does_not_call_model_for_name_questions_or_one_off_requests` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProjectTests.test_agent_creates_and_updates_persisted_canvas_for_explicit_request` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProjectTests.test_deduplicated_materials_and_cleanup_never_remove_referenced_files` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProjectTests.test_delete_last_canvas_closes_editor_without_recreating_document` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProjectTests.test_drawing_surface_has_no_scroll_parent_and_saved_strokes_export` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProjectTests.test_file_changed_while_reviewing_is_not_overwritten` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProjectTests.test_no_write_or_execution_without_approval_or_outside_folder` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProjectTests.test_reviewed_write_read_compile_and_process_output_are_real` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_live.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `LiveControllerTests.test_android_screen_denial_preserves_existing_camera_selection` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_android_screen_denial_shows_message_without_platform_exception_wrapper` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_android_screen_requires_consent_and_closes_native_capture` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_busy_mode_and_browser_do_not_start_live` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_close_prevents_later_ui_updates` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_floating_mute_cancels_real_recorder_before_publishing_state` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_floating_stop_reaches_capture_cleanup_and_closes_panel` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_interrupt_speech_resumes_listening` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_landscape_keyboard_hides_panel_but_preserves_capture_and_restores_it` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_live_attachments_are_saved_and_passed_to_model_once` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_main_composer_files_are_consumed_once_after_message_save` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_missing_voice_preserves_answer_and_keeps_call_open` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_portrait_keyboard_leaves_chat_space_without_stopping_camera` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_repeated_clicks_cancel_start_without_second_session` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_second_queued_question_does_not_replace_first` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_short_viewport_bounds_live_panel_without_replacing_controls` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_stop_discards_late_model_reply` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_stop_during_listening_does_not_send_audio` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_successful_source_change_clears_old_permission_error_but_keeps_busy_status` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_two_turns_share_history_and_return_to_listening` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveControllerTests.test_typed_question_starts_without_camera_or_microphone` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveModelTests.test_reply_uses_fresh_context_and_keeps_chat_conversation_untouched` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveModelTests.test_text_followup_receives_previous_live_messages` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SegmentationTests.test_cancel_while_waiting_for_speech_releases_microphone` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SegmentationTests.test_idle_silence_keeps_only_preroll_and_does_not_trigger` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SegmentationTests.test_long_utterance_is_bounded_by_model_limit` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SegmentationTests.test_short_noise_does_not_become_a_question` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SegmentationTests.test_short_pause_does_not_split_utterance` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SegmentationTests.test_speech_ends_after_pause_preserving_onset` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_live_vision_markdown.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `LiveVisionNoteTests.test_capture_error_prevents_reply_without_requested_image` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveVisionNoteTests.test_no_vision_button_means_no_capture` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LiveVisionNoteTests.test_screen_frame_is_returned_and_note_is_cleared` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MarkdownMessageTests.test_ai_reply_is_rendered_as_markdown` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MarkdownMessageTests.test_author_prefix_stays_bold` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MarkdownMessageTests.test_copy_action_gets_raw_markdown` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ScreenCaptureTests.test_black_frame_is_reported_instead_of_sent_to_model` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ScreenCaptureTests.test_black_mss_frame_falls_back_to_compositor_tool` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ScreenCaptureTests.test_missing_tools_are_reported_with_reason` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ScreenCaptureTests.test_wayland_uses_compositor_tool_before_mss` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_local_workflows.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `CameraLifetimeTests.test_closed_camera_cannot_reopen_after_late_capture` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LivePreviewTests.test_controller_can_restart_after_browser_reconnect` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LivePreviewTests.test_idle_preview_is_released_by_stop` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LivePreviewTests.test_stale_frame_is_not_sent` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LocalWorkflowTests.test_failed_import_leaves_no_partial_file` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LocalWorkflowTests.test_shared_files_and_instructions_survive_restart_and_original_move` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LocalWorkflowTests.test_web_material_bytes_are_saved_without_client_path` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PaletteTests.test_dark_theme_changes_surfaces_and_new_dialogs_then_restores_light` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PaletteTests.test_settings_sections_construct_with_readable_dark_text` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PaletteTests.test_theme_replaces_shared_border_styles_without_changing_shape` | Выполнен, успешно | Замечаний в этой проверке нет |
| `RetryUITests.test_retry_preserves_new_draft_and_does_not_repeat_user_message` | Выполнен, успешно | Замечаний в этой проверке нет |
| `RetryUITests.test_retry_uses_edited_question` | Выполнен, успешно | Замечаний в этой проверке нет |
| `RetryUITests.test_worker_cancellation_offers_retry_without_duplicate_question` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_memory_lifecycle.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `DialogRetentionTests.test_theme_registry_does_not_retain_closed_editor_or_payload` | Выполнен, успешно | Замечаний в этой проверке нет |
| `EncoderLifecycleTests.test_idle_cleanup_waits_for_quiet_period_and_next_request_can_reload` | Выполнен, успешно | Замечаний в этой проверке нет |
| `EncoderLifecycleTests.test_muted_live_and_cancelled_voice_start_do_not_load_audio_encoder` | Выполнен, успешно | Замечаний в этой проверке нет |
| `EncoderLifecycleTests.test_text_image_audio_text_switches_have_one_engine_and_keep_capabilities` | Выполнен, успешно | Замечаний в этой проверке нет |
| `EncoderLifecycleTests.test_timer_cannot_interrupt_an_active_native_operation` | Выполнен, успешно | Замечаний в этой проверке нет |
| `IdleUICleanupTests.test_busy_request_and_open_dialog_block_even_model_release_cleanup` | Выполнен, успешно | Замечаний в этой проверке нет |
| `IdleUICleanupTests.test_model_release_notifies_android_and_discards_only_thumbnail_cache` | Выполнен, успешно | Замечаний в этой проверке нет |
| `IdleUICleanupTests.test_quiet_period_and_user_activity_delay_cache_release` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LazyMediaTests.test_app_import_does_not_import_media_or_load_native_model_library` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LazyMediaTests.test_live_button_label_does_not_inspect_model_capabilities` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LazyMediaTests.test_optional_library_is_loaded_once_and_missing_dependency_stays_optional` | Выполнен, успешно | Замечаний в этой проверке нет |
| `IdleUICleanupTests.test_camera_preview_blocks_ui_cleanup_even_without_generation` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_miku_voice.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `MikuInstallationTests.test_bad_download_preserves_previous_model_and_removes_partial` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuInstallationTests.test_embedded_launcher_is_not_executed_as_a_python_venv` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuInstallationTests.test_export_interpreter_keeps_virtual_environment_symlink` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuInstallationTests.test_invalid_metadata_and_corrupted_encoder_are_rejected` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuInstallationTests.test_matching_download_does_not_use_network` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuInstallationTests.test_piper_files_alone_never_mark_miku_installed` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuSignalTests.test_cancellation_while_waiting_for_converter_does_not_leak_lock` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuSignalTests.test_converted_chunk_replaces_cached_pcm_and_preserves_source_on_error` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuSignalTests.test_english_miku_name_changes_only_spoken_pronunciation` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuSignalTests.test_pending_conversion_cancels_without_loading_models` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuSignalTests.test_pitch_is_a_local_weighted_average_and_silence_is_unvoiced` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MikuSignalTests.test_silent_mel_is_finite_with_ten_ms_frames` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_mobile.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `AndroidDocumentTests.test_android_cached_document_is_copied_by_path_without_loading_bytes` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AndroidDocumentTests.test_bridge_never_blocks_the_ui_loop_but_worker_can_call_it` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AndroidDocumentTests.test_content_uri_uses_bytes_and_persists_managed_copy` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AndroidDocumentTests.test_inaccessible_uri_reports_failure_without_creating_empty_material` | Выполнен, успешно | Замечаний в этой проверке нет |
| `AndroidPackagingTests.test_cli_exclusions_preserve_private_data_and_expand_host_native_globs` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LazyMobileCapabilitiesTests.test_home_restores_cache_without_loading_native_model_library` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileKeyDatabaseTests.test_android_does_not_open_database_before_keystore_ready` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileKeyDatabaseTests.test_explicit_random_key_survives_reopen_wrong_key_cannot_read_history` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileKeyDatabaseTests.test_reconnect_accepts_same_key_but_cannot_replace_open_database_key` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileLayoutTests.test_android_canvas_exports_through_saf_without_writing_content_uri` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileLayoutTests.test_android_storage_never_moves_to_shared_or_runtime_folder` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileLayoutTests.test_android_tls_has_real_trusted_ca_certificates_without_disabling_validation` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileLayoutTests.test_composer_resize_keeps_draft_recording_and_action_callbacks` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileLayoutTests.test_model_name_is_short_only_on_narrow_phones_and_restores_on_desktop` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileLayoutTests.test_nested_account_form_fits_phone_then_restores_desktop_width` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileLayoutTests.test_portrait_landscape_and_chromebook_resize_restore_menu` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobileLayoutTests.test_settings_shell_uses_phone_width_without_double_dialog_gutters` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobilePageTests.test_complete_page_start_rotate_and_send_first_message_to_empty_chat` | Выполнен, успешно | Замечаний в этой проверке нет |
| `MobilePageTests.test_sync_refresh_updates_chat_and_remote_deletion_preserves_typed_draft` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_mobile_documents.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `DocumentRecoveryTests.test_avatar_write_failure_retains_native_image_for_retry` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentRecoveryTests.test_deleted_or_private_destination_is_discarded_without_redirect` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentRecoveryTests.test_export_bytes_are_staged_before_opening_picker_and_recovered_after_restart` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentRecoveryTests.test_failed_db_write_keeps_native_result_for_retry` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentRecoveryTests.test_invalid_avatar_does_not_block_future_file_selection` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentRecoveryTests.test_result_after_process_death_is_saved_once_and_acknowledged_after_db` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentRecoveryTests.test_startup_waits_for_native_copy_result` | Выполнен, успешно | Замечаний в этой проверке нет |
| `DocumentRecoveryTests.test_workspace_selection_survives_restart_and_keeps_logical_names` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_model_downloads.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `ModelDownloadTests.test_disconnect_preserves_partial_and_server_ignoring_range_restarts_safely` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelDownloadTests.test_hash_failure_preserves_installed_model_and_removes_corrupt_partial` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelDownloadTests.test_job_automatically_resumes_after_network_returns` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelDownloadTests.test_network_job_wait_can_be_paused_and_resumed` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelDownloadTests.test_pause_retains_bytes_then_new_job_continues_range_and_verifies` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_model_paths.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `ModelPathTests.test_python_database_wrapper_uses_user_directory` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelPathTests.test_user_models_override_legacy_and_list_both` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelPathTests.test_windows_and_linux_data_directories` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_native_db.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `NativeDatabaseTests.test_clear_preserves_other_chat_and_settings` | Выполнен, успешно | Замечаний в этой проверке нет |
| `NativeDatabaseTests.test_edit_delete_and_chat_cascade_persist` | Выполнен, успешно | Замечаний в этой проверке нет |
| `NativeDatabaseTests.test_editing_text_and_attachments_is_persistent` | Выполнен, успешно | Замечаний в этой проверке нет |
| `NativeDatabaseTests.test_invalid_chat_does_not_create_partial_message` | Выполнен, успешно | Замечаний в этой проверке нет |
| `NativeDatabaseTests.test_renaming_and_aggregate_counts_survive_reopen` | Выполнен, успешно | Замечаний в этой проверке нет |
| `NativeDatabaseTests.test_reopen_keeps_settings_messages_and_attachments` | Выполнен, успешно | Замечаний в этой проверке нет |
| `NativeDatabaseTests.test_selected_chat_survives_reset_of_python_cache` | Выполнен, успешно | Замечаний в этой проверке нет |
| `NativeDatabaseTests.test_sync_import_cas_receipt_and_new_id_are_atomic` | Выполнен, успешно | Замечаний в этой проверке нет |
| `NativeDatabaseTests.test_sync_settings_cas_never_overwrites_concurrent_project_edit` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_personal_memory_storage.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `MemoryCaptureLifecycleTests.test_private_transition_cancels_capture_and_releases_busy_state` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_bounded_preview_real_streamed_export_and_trash_preview` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_clear_all_history_deletes_chats_and_drafts_but_keeps_project_memory_and_canvas` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_exact_user_quotes_only_and_no_credentials_attachments_or_private_reads` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_explicit_capture_no_extra_inference_and_disable_clear_wins_over_pending_extraction` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_memory_interface_uses_real_edit_delete_search` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_name_assertion_replaces_old_name_and_questions_never_become_memory` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_profile_cloud_import_keeps_memory_and_google_refresh_preserves_it` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_saved_edited_deleted_notes_survive_reopen_without_plaintext_database` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersonalMemoryTests.test_two_encrypted_databases_transfer_and_delete_memory_with_real_e2ee_codec` | Выполнен, успешно | Замечаний в этой проверке нет |
| `StorageInterfaceTests.test_storage_menu_preview_export_and_search_use_real_material_identifiers` | Выполнен, успешно | Замечаний в этой проверке нет |
| `StreamedAndroidExportTests.test_export_existing_file_passes_only_path_to_native_service` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_piper_voice.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `PiperVoiceTests.test_cancel_before_synthesis_does_not_run_model` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PiperVoiceTests.test_cancel_during_playback_stops_at_next_small_block_and_closes_audio` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PiperVoiceTests.test_cancel_interrupts_native_inference_and_next_turn_can_run` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PiperVoiceTests.test_inference_error_restores_session_and_releases_lock` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PiperVoiceTests.test_normal_playback_writes_all_audio_and_drains_output` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PiperVoiceTests.test_output_start_failure_closes_generator_and_device` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_private_chats.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `PrivateChatTests.test_attachment_failure_removes_all_decrypted_scratch_files` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_authenticated_ciphertext_rejects_tampering` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_crashed_scratch_is_reclaimed_but_live_session_is_preserved` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_failed_write_rolls_back_visible_state_and_partial_attachment` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_lease_releases_when_ui_thread_differs_from_unlock_thread` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_malformed_directory_does_not_break_chat_listing` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_other_window_cannot_overwrite_unlocked_chat` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_password_isolates_transcript_draft_canvas_and_attachment` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_regular_material_cannot_be_attached_without_private_copy` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateChatTests.test_temporary_state_disappears_on_close_without_persistent_files` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateGenerationTests.test_private_reply_forces_fresh_context_and_does_not_record_profile_stats` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_api_camera_question_sends_and_saves_frame_without_loading_live_model` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_api_retry_reuses_saved_screen_frame_instead_of_recapturing` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_api_screen_capture_failure_preserves_question_without_sending_blindly` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_failed_delete_keeps_message_visible` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_failed_edit_preserves_original_and_draft` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_failed_save_preserves_draft_and_does_not_generate` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_late_answer_after_disconnect_cannot_leak_into_normal_retry` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_leaving_private_chat_erases_temporary_and_locks_saved` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_new_chat_is_blocked_while_generation_runs` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_private_request_ignores_api_workspace_and_global_agent` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PrivateUITests.test_unsaved_reply_can_be_retried_without_duplicate_generation` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_profile.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `AndroidAvatarTests.test_android_avatar_uses_restart_safe_native_picker` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfileTests.test_avatar_is_bounded_reencoded_and_metadata_removed` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfileTests.test_concurrent_name_edit_wins_over_google_import` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfileTests.test_explicit_default_name_and_removed_avatar_are_preserved` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfileTests.test_google_does_not_replace_existing_local_or_synced_profile` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfileTests.test_google_seeds_blank_profile_and_preserves_manual_fields` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfileTests.test_monthly_catalog_and_discounts_require_verification` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_profile_conflict_preview.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `ProfilePreviewTests.test_authenticated_remote_update_also_invalidates_the_previous_preview` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfilePreviewTests.test_change_after_preview_is_not_overwritten_and_no_recovery_is_written` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfilePreviewTests.test_edit_between_preview_validation_and_import_is_preserved` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfilePreviewTests.test_preview_authenticates_both_profiles_without_resolving_or_mutating_them` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ProfilePreviewTests.test_tampered_envelope_cannot_be_shown_as_a_valid_choice` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_real_answers.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `LegacyCleanupTests.test_edited_demo_and_quoted_or_attached_messages_are_preserved` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LegacyCleanupTests.test_exact_demo_and_ai_templates_are_removed_but_real_messages_remain` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LegacyCleanupTests.test_future_real_replies_with_same_words_are_not_deleted_again` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LegacyCleanupTests.test_interrupted_cleanup_resumes_without_removing_edited_remaining_row` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelLimitsTests.test_empty_model_response_is_an_error` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelLimitsTests.test_history_keeps_more_than_twelve_messages_and_six_thousand_characters` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelLimitsTests.test_live_reply_does_not_set_a_token_budget` | Выполнен, успешно | Замечаний в этой проверке нет |
| `ModelLimitsTests.test_text_reply_is_not_limited_or_truncated` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersistenceUITests.test_api_camera_question_sends_and_saves_frame_without_loading_live_model` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersistenceUITests.test_api_retry_reuses_saved_screen_frame_instead_of_recapturing` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersistenceUITests.test_api_screen_capture_failure_preserves_question_without_sending_blindly` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersistenceUITests.test_failed_delete_keeps_message_visible` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersistenceUITests.test_failed_edit_preserves_original_and_draft` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersistenceUITests.test_failed_save_preserves_draft_and_does_not_generate` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersistenceUITests.test_new_chat_is_blocked_while_generation_runs` | Выполнен, успешно | Замечаний в этой проверке нет |
| `PersistenceUITests.test_unsaved_reply_can_be_retried_without_duplicate_generation` | Выполнен, успешно | Замечаний в этой проверке нет |
| `RealReplyUITests.test_absent_model_is_reported_without_generation` | Выполнен, успешно | Замечаний в этой проверке нет |
| `RealReplyUITests.test_generation_failure_is_shown_without_saving_a_fake_ai_reply` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_sidebar_chats.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `SidebarTests.test_open_sidebar_refreshes_titles_when_generation_finishes` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SidebarTests.test_sidebar_refetches_filters_and_selects_correct_chat` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SidebarTests.test_storage_error_has_visible_feedback` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_sync_crypto.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `CryptoTests.test_compress_encrypt_roundtrip_and_owner_binding` | Выполнен, успешно | Замечаний в этой проверке нет |
| `CryptoTests.test_key_password_account_binding_and_bounded_decompression` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_sync_recovery.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `LegacyConflictRecoveryTests.test_changed_project_is_not_auto_replaced_after_chat_deletion` | Выполнен, успешно | Замечаний в этой проверке нет |
| `LegacyConflictRecoveryTests.test_first_pull_can_collapse_unknown_entity_to_its_deletion` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_sync_transport.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `TransportRetryTests.test_network_retries_are_bounded` | Выполнен, успешно | Замечаний в этой проверке нет |
| `TransportRetryTests.test_non_network_and_budget_errors_are_not_retried` | Выполнен, успешно | Замечаний в этой проверке нет |
| `TransportRetryTests.test_retry_preserves_operation_identity_and_encrypted_bytes` | Выполнен, успешно | Замечаний в этой проверке нет |
| `TransportRetryTests.test_retry_rechecks_account_switch_disable_and_scope` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_ui_improvements.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `DraftTests.test_switch_restores_each_chat_draft` | Выполнен, успешно | Замечаний в этой проверке нет |
| `WorkspaceTests.test_create_select_rename_and_delete_preserve_chats` | Выполнен, успешно | Замечаний в этой проверке нет |
| `WorkspaceTests.test_creation_saves_instructions_and_materials_in_one_write` | Выполнен, успешно | Замечаний в этой проверке нет |
| `WorkspaceTests.test_failed_write_does_not_change_saved_workspace` | Выполнен, успешно | Замечаний в этой проверке нет |
| `WorkspaceTests.test_invalid_workspace_and_empty_name_are_rejected` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_updates.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `HistoryTests.test_database_error_preserves_visible_messages` | Выполнен, успешно | Замечаний в этой проверке нет |
| `UpdateTests.test_new_and_current_versions` | Выполнен, успешно | Замечаний в этой проверке нет |
| `UpdateTests.test_offline_does_not_report_success` | Выполнен, успешно | Замечаний в этой проверке нет |
| `UpdateTests.test_unpublished_releases_are_not_reported_as_latest` | Выполнен, успешно | Замечаний в этой проверке нет |

### test_voice_selection.py

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `SpeechRoutingTests.test_cancellation_between_languages_does_not_load_next_model` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_cancelled_or_empty_reply_does_not_load_model` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_change_during_reply_does_not_mix_profiles` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_each_profile_routes_russian_and_english_to_its_variants` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_fixed_voice_can_be_used_without_changing_saved_selection` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_markup_is_suitable_for_reading_aloud` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_miku_uses_one_converter_for_both_languages_and_releases_on_voice_change` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_missing_selected_voice_is_not_replaced_with_another_voice` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_model_is_reused_between_replies_in_same_language` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_names_do_not_switch_language_inside_russian_sentence` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_numbers_keep_previous_language` | Выполнен, успешно | Замечаний в этой проверке нет |
| `SpeechRoutingTests.test_voice_change_applies_on_next_reply_without_restarting_live` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoicePageTests.test_android_settings_opens_native_settings_and_download_only_on_click` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoicePageTests.test_android_without_engine_does_not_start_synthesis_or_change_desktop_voice` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoicePageTests.test_failed_save_restores_previous_choice_and_reports_error` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoicePageTests.test_missing_saved_voice_uses_default_choice` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoicePageTests.test_selector_has_three_voices_and_saves_choice` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceSettingsTests.test_database_failure_is_reported` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceSettingsTests.test_missing_or_invalid_saved_voice_defaults_to_cove` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceSettingsTests.test_unavailable_or_unknown_voice_does_not_change_saved_selection` | Выполнен, успешно | Замечаний в этой проверке нет |
| `VoiceSettingsTests.test_voice_selection_survives_a_new_reader` | Выполнен, успешно | Замечаний в этой проверке нет |


## Rust-тесты защиты локального ключа

Исполнитель: Codex. Запуск: `cargo test --manifest-path Services/Cargo.toml --offline --lib`. Журнал: `/tmp/xopilot-rust-tests-20261013.log`.

| Тест | Состояние | Что не так |
| --- | --- | --- |
| `security::tests::existing_keyring_key_remains_an_option_with_a_corrupt_salt` | Выполнен, успешно | Замечаний в этой проверке нет |
| `security::tests::corrupt_salt_is_preserved_instead_of_replaced` | Выполнен, успешно | Замечаний в этой проверке нет |
| `security::tests::missing_key_never_creates_a_replacement_for_existing_history` | Выполнен, успешно | Замечаний в этой проверке нет |
| `security::tests::fallback_survives_keyring_becoming_available` | Выполнен, успешно | Замечаний в этой проверке нет |

## Окончательные APK и замер памяти

Исполнитель: Codex. Собраны 13 октября 2026 года командой `./python/linux/bin/python scripts/build_android.py --skip-native --jdk build/android-jdk/jdk-21.0.12.1+1 --build-number 2048`.

| Пакет / проверка | Состояние | Результат |
| --- | --- | --- |
| ARM64 `build/apk/Xopilot-arm64-v8a.apk` | Выполнен, успешно | 4048; 102,3 МиБ; SHA256 `323d05606c48401b28d5909ad206b7de1caa62d525aa83a13ff1eff9cd3f2bdd` |
| x86_64 `build/apk/Xopilot-x86_64.apk` | Выполнен, успешно | 6048; 109,4 МиБ; SHA256 `6cde4257c0f06c61c5ede772f2d652fb56bf4b2bf85bd6bddea3135ab946836e` |
| ABI, определения JNI в DEX, ELF 16 КиБ, манифест, иконка | Выполнен, успешно | Проверены оба пакета, журнал `/tmp/xopilot-memory-final-apk2048-20261013.log` |
| Совпадение Python-кода с источниками | Выполнен, успешно | Сопоставлен байткод `App`, `app/main`, `app/palette`, `services/runtime` в обеих APK. Проверка читает `assets/app.zip`, а не только файлы на диске |
| Установка ARM64 и запуск на POCO | Выполнен, успешно | Android сообщает versionCode 4048; существующий чат и аккаунт сохранены |
| Меню → аккаунт → хранилище → обычный чат после очистки | Выполнен, успешно | Проверено реальными нажатиями на POCO 4048 после срабатывания таймера: меню показывает чаты, аккаунт и хранилище открываются; 16 материалов и 4 другие неиспользуемые копии сохранены. Пользовательские материалы не удалялись, Live и звук не запускались |
| Память на том же открытом чате, модель не запущена | Выполнен, цель провалена | 20 с: PSS 243586 КиБ; 80 с: PSS 242641 КиБ. **140 МБ не достигнуты**. Отдельно указаны RSS и графика; они не заменяют PSS |
| x86_64: настоящий запуск на ChromeOS | Не выполнен | Нет устройства; успешная упаковка не подтверждает запуск |

На APK 4048 через 80 с графика занимала 83352 КиБ, native heap — 37404 КиБ, Private Other — 56548 КиБ. Это показывает, почему одного закрытия модели и сбора Python-мусора недостаточно для заданного предела. Сравнение старой холодной 4046 (236259 КиБ) и новой 4048 не доказывает снижение базового расхода; нынешние изменения исправляют удержание закрытых редакторов и освобождают заменяемые кэши, но не завершают задачу оптимизации. Размер APK тоже не используется как доказательство расхода ОЗУ.

Журнал вызова очистки: `/tmp/xopilot-idle-cleanup-final-phone-20261013.log`. Полные снимки памяти: `/tmp/xopilot-memory-final4048-20s-20261013.txt`, `/tmp/xopilot-memory-final4048-80s-20261013.txt`. Исходная холодная версия: `/tmp/xopilot-memory-baseline4046-20261013.txt`. Замер Linux: `/tmp/xopilot-desktop-memory-results-20261013.jsonl`.

## Подготовка GitHub Actions для dev-v2.0.7

Исполнитель: Codex. После назначения версии 2.0.7 выполнены 35 проверок обновлений, Android и жизненного цикла памяти: все прошли, 1,705 с. Workflow проверен `actionlint 1.7.12` без замечаний. Встроенный OpenSSL устраняет зависимость Windows-сборки SQLCipher от `OPENSSL_DIR`; настроены Perl и Visual Studio. CI закреплён на Python 3.14.7 и проверенном локально Flutter 3.44.8. Android job собирает ARM64/x86_64 и проверяет APK, выравнивание и подпись. Версия и увеличенный build-number передаются обеим платформенным сборкам. Кэши IDE/Gradle, базы, приватные ключи и keystore не включены в отправку.

На момент этого коммита запуск GitHub Actions **ещё не выполнен**: локальные проверки и APK 4048 не объявляются результатом серверной CI-сборки dev-2.0.7. Установленная APK 4048 относится к предыдущему локальному этапу и имеет версию 2.0.0; новая версия 2.0.7 будет подтверждена отдельным запуском Actions. Функции не скрывались и не удалялись для отправки.

### Первый запуск CI и переименование тега

Исполнитель: Codex. В запуске Actions `38367037837` Android job не дошёл до компиляции: SDK Manager сообщил `Failed to find package 'platforms;android-37'`. В актуальном официальном каталоге Google имя пакета — `platforms;android-37.0`; именно этот пакет установлен и в локальном SDK, на котором ранее собрались обе APK. Workflow исправлен на точное имя, `setup-android@v4` и Command-line Tools 22 (архив 15859902), существующий в официальном каталоге. Старый тег `dev-2.0.7` заменяется по просьбе пользователя на `dev-v2.0.7`. Исправление параметров SDK не объявляется доказательством успешной компиляции: новый запуск требуется проверить отдельно.

Linux job первого запуска прошёл нативную сборку и тесты, затем упал в Dart-компиляции: свежий `jni_flutter 1.0.4+1` требует `jni ^1.1.0`, а шаблон Flet 1.0.3 принудительно выбирает `jni 1.0.0`. В pyproject зафиксирована совместимая пара `jni 1.0.0` / `jni_flutter 1.0.2`, использованная в ранее проверенных локальных пакетах. Это исправление несовместимости зависимостей, а не удаление функции JNI или платформы Android.

### Навигация проектов, контекст и Windows CI — 13 октября 2026

Исполнитель всех проверок этого этапа: Codex. Запуск Actions `38368872476` успешно собрал Linux и обе Android APK. Windows успешно собрал SQLCipher и прошёл четыре Rust-теста, затем остановился: 4 ошибки утверждений и 7 ошибок исполнения Python-тестов. Release job был пропущен; опубликованного релиза `dev-v2.0.7` нет.

Устранены удерживаемые соединения с временной БД (добавлено явное закрытие, сохраняющее безопасную ошибку при последующих обращениях), сравнения коротких/полных Windows-путей, разделители имён материалов и чтение эксклюзивно заблокированных служебных lease-файлов в проверке шифрования. Для отмены HTTP сохранён отдельный дескриптор транспорта, включая TLS; подтверждение поведения на Windows ожидает нового CI. Rust-тесты выполняются в release-профиле, чтобы не компилировать все зависимости повторно в debug.

| Проверка | Состояние | Результат / ограничение |
| --- | --- | --- |
| Полный Python-набор на отдельном локальном профиле | Выполнен, успешно | 363 проверки: 355 прошли, 8 интеграционных пропущены без URL тестового backend. Пропуски не объявляются успешным исполнением |
| Rust — переходы ключей | Выполнен, успешно | 4 теста в release-профиле |
| Контекст принадлежит чату, а не выбранному соседнему проекту | Выполнен, успешно | Имя пространства и включённые материалы передаются отдельно; чужое пространство и отключённые материалы отсутствуют |
| Агент после преждевременного final / исправления JSON | Выполнен, успешно | Сохраняет исходный запрос, историю и вложения на следующих шагах; реально создаёт Canvas в изолированной БД. Генератор модели в этом тесте имитирован |
| Новый чат проекта / обычный чат / повторный пустой чат | Выполнен, успешно | Обработчики интерфейса и настоящая SQLCipher БД: история проекта остаётся на месте, обычный чат изолирован, пустой не дублируется |
| Drawer: обновления и повторное открытие | Выполнен, успешно | Нет анимации ширины, blur и обновлений всей страницы; неизменные строки сохраняют объекты. Тест не измеряет FPS телефона |
| Цвета кнопок и контраст | Выполнен, успешно | Четыре смысловые группы; контраст белой иконки со всеми цветами градиентов >= 4.5:1 |
| Настоящий Google API, материалы `Test` | Не завершён | Google вернул HTTP 503. Корректность передачи контекста проверена; качество ответа модели этим запросом не подтверждено |
| ARM64 APK 4049, версия 2.0.7 | Выполнен, успешно | 102,3 МиБ; JNI, ELF 16 КиБ, манифест проверены; SHA256 `0c1a304cd9f9ef7d05c5e2754586f859ba8ff8faca336bbfb1b5c807636ed653`. Обновление установленной APK на POCO выполнено без удаления данных |
| Windows-пакет после исправлений | Не выполнен на этом этапе | Требуется повторный запуск Actions; локальные Linux-тесты не подтверждают готовность Windows |

Первый локальный прогон во время редактирования выявил 11 сбоев. Два относились к ещё не исправленным новым тестам; остальные обнаружили зависимость тестов от выбранного в личном профиле API и ошибку первой реализации dup для SSLSocket. Исправлены код транспорта, тестовые обработчики и изоляция выбора API; повторный полный прогон на отдельном профиле прошёл. Успешный повтор не скрывает эти первоначальные результаты.

#### Итог повторной проверки этого этапа

Исполнитель: Codex. После восстановления соединения повторно выполнены все **8** сценариев API/SQLCipher/двух профилей на отдельной PostgreSQL `xopilot_test`: **8 прошли**, 212,386 с. Предыдущий повтор завершился 7 ошибками после потери соединения с тестовой БД; ошибки записаны как ошибки, а не пропуски. Производственная БД не использовалась. В сумме на актуальном коде выполнены **363 Python-проверки успешно**: 355 в локальном изолированном прогоне и 8 в отдельном интеграционном; дополнительно прошли **4 Rust-теста**.

Настоящий Google API после временного HTTP 503 ответил по материалам `Test`: правильно назвал пространство, `Cargo.toml`, `src/main.rs` и их назначение. Отдельно настоящий агент через Google создал в изолированной БД Canvas `summary.md` с именем тестового пространства, языком Rust и точным фактом `ORBIT-716` из файла. Создание и содержимое проверены чтением сохранённого документа; генератор модели в этом сценарии не имитировался. Никакие команды ОС не запускались.

На POCO проверены реальные нажатия: меню с общим списком и подписью проекта; `Test → Новый чат → В проекте «Test»`; повторный выбор `Обычный чат`; два повторных нажатия `Новый чат`. В меню остался один пустой обычный чат, исходная история `Test → привет` сохранена. APK: версия 2.0.7, versionCode 4049. Live, микрофон, воспроизведение звука и звонки не запускались. Drawer использует фиксированную ширину и перевод по offset, обновления ограничены меню; количественный FPS на устройстве не измерялся, поэтому гарантии постоянных 60/120 FPS нет.

Код отправлен в `main`, коммит `81c640e228ece02297462afd700a1a46e202483b`. Неудавшийся и ещё не опубликованный тег `dev-v2.0.7` обновлён; повторный Actions — `38425992596`. Результат Windows/Android этого запуска фиксируется отдельно после завершения.

Созданный на POCO пустой QA-чат удалён через подтверждение `Новый чат — чат и его сообщения будут удалены`. Повторное открытие меню показало прежние чаты (`кто я`, `Test → сколько времени`, `Test → привет`); пустого тестового чата нет. Материалы и сообщения пользователя не удалялись.

#### Оставшиеся Windows-проверки и отмена TLS

Запуск `38425992596`: Linux и обе Android APK собраны успешно. Windows сократил сбои с 11 до 2: оставшееся сравнение короткого имени каталога `runtime` и отмена зависшего HTTP body. Путь `runtime` и путь cache в тесте теперь сравниваются после resolve. Для чтения HTTP введён RawIOBase с проверкой отмены внутри recv-цикла: короткие тайм-ауты не выходят в HTTP BufferedReader и не повреждают частично прочитанные заголовки/чанки. SocketIO lease удерживает дескриптор до окончания ответа. TLS-проверка использует настоящие локальные TLS-сокеты, временный сертификат и проверку его доверия, а не отключение проверки сертификатов.

Исполнитель: Codex. Ранние проверки пути/HTTP/TLS прошли локально (3 проверки). Полный изолированный Python-прогон: **364 проверки, 356 прошли, 8 серверных пропущены без URL**, 29,550 с. Восемь серверных сценариев успешно выполнены отдельным прогоном, описанным выше. Новый `ApiTransportTests.test_cancel_interrupts_waiting_tls_body` — выполнен, успешно. Windows-подтверждение новой реализации остаётся ожидающим; предыдущий Windows-запуск не объявляется успешным. Проверки отмены и пути вынесены перед дорогой компиляцией в Actions.

Ранние проверки пути, HTTP и TLS **прошли на Windows и Linux в Actions `38429077254`**, коммит `3daae9737f93f70d22046e140838e865a543cf0e`. Полная сборка пакетов на момент записи продолжалась. APK ARM64 с новым транспортом: версия 2.0.7, versionCode 4050, 102,3 МиБ, SHA256 `82d3ac2f783047e3c9b6858ebb9ff62863aea5a5c01a83159b273cfdb894c7d6`; содержимое/JNI/ELF 16 КиБ/манифест проверены. Установлена на POCO обновлением без удаления данных. Сопоставление code objects восьми основных модулей APK с текущими источниками успешно. Меню и создание/удаление QA-чата проверялись на 4049; UI-код 4050 идентичен. Повторная проверка UI 4050 остановилась на блокировке экрана; этот шаг не объявляется выполненным. Настоящий HTTPS-запрос к Google с новым транспортом успешно прочитал материалы `Test` и вернул корректный ответ на ПК. Звук не запускался.

### Окончательный результат Actions

Исполнитель проверки результата: Codex. Запуск **38429077254 завершился успешно**: Linux — success, Windows — success, Android (ARM64 и x86_64) — success, release — success. Устранённые Windows-ошибки подтверждены успешным полным job, включая нативную БД, Rust-тесты, Python-тесты и упаковку приложения. Предварительный релиз **dev-v2.0.7 опубликован**. Ранее ожидающие статусы выше относятся к моменту записи и заменены этим окончательным результатом. Физический запуск Windows/ChromeOS этим не подтверждается; количественный FPS на POCO не измерялся.

### Холодная палитра кнопок Material You — 13 октября 2026

Исполнитель: Codex. После замечания пользователя о бронзовом оттенке заменены тёплые зелёные заливки на холодные голубые/сине-серые тональные градиенты. Белые обводки толщиной 2 заменены тонкими рамками, у стандартных кнопок убрано возвышение; иконки/подписи и заливки обновляются вместе со светлой/тёмной темой. Используется Material 3 и палитра приложения; системные цвета обоев Android не подключались.

| Проверка | Состояние | Результат |
| --- | --- | --- |
| Контраст и переключение всех 7 тем | Выполнен, успешно | Обновлён существующий тест цветов: контраст иконки с обоими концами градиента >= 4.5:1 |
| Полный локальный набор на изолированном профиле | Выполнен, успешно | 364 проверки: 356 прошли, 8 серверных пропущены без URL; 26,835 с. Серверные проверки в этом косметическом этапе не запускались |
| Сборка ARM64 и проверка пакета | Выполнен, успешно | 2.0.7 / 4052, 102,3 МиБ; JNI/ELF 16 КиБ/манифест OK; SHA256 `7566eee5afa7147773679fa9e139c31a3c55318a972b807fe2df89a8a0d0a0ac` |
| Установка и чат на POCO | Выполнен, успешно | Данные сохранены, видны прежняя переписка и новые холодные кнопки. Начальный пустой кадр был фазой запуска; повторная проверка показала интерфейс |
| Соответствие функционального оформления APK | Выполнен, успешно | Цвета, рендер кнопок, тема, меню и аккаунт совпадают с источниками. APK содержит предыдущую строку описания модуля цветов и неиспользуемый import outline_color в выборе модели; эти отличия не меняют оформление и функции |

Live, микрофон и воспроизведение звука на телефоне не запускались. Опубликованный dev-v2.0.7 не перезаписывался этим косметическим этапом.

### Более светлые кнопки — 13 октября 2026

Исполнитель: Codex. По замечанию пользователя «мрачно» тёмные заливки кнопок заменены светлыми пастельными голубыми, лавандовыми и розовыми градиентами с тёмными иконками. В светлых темах немного усилены голубой и лавандовый оттенки. Геометрия и поведение кнопок сохранены.

- Выполнен, успешно: 4 проверки `test_project_context_navigation.py`, включая контраст >= 4.5:1 с обоими концами градиента во всех 7 темах.
- Выполнен, успешно: `git diff --check`.
- Выполнен, успешно: сборка ARM64 2.0.7 / 4053, 102,3 МиБ; проверка JNI/ELF 16 КиБ/манифеста. SHA256 `a3af4b93cc56ed8f9951f60fcc516ddad575c5018e6bb64483ba90f02e4790b2`.
- Выполнен, успешно: установка обновлением на POCO, просмотр чата и открытие меню через реальные нажатия ADB. Светлые голубые и лавандовые кнопки видны в теме Forest, подписи читаемы. Данные пользователя сохранены; Live, микрофон и звук не запускались.

### Настройки и всплывающие списки — 13 октября 2026

Исполнитель: Codex. Открытые пользователем настройки просмотрены на POCO: в них оставались отдельные старые значки и зелёно-синяя шапка. Шапка стала компактнее с голубым градиентом; значки разделов, карточек персонализации и моделей используют общую пастельную палитру. Выпадающие списки и меню действий получили нейтральную поверхность, радиус 20, тонкую рамку и мягкую тень; выбранные пункты подсвечиваются лавандовым оттенком. Существующие обработчики сохранены.

- Выполнен, успешно: полный локальный прогон на изолированном профиле — 364 проверки, 356 успешно и 8 серверных пропущены, 26,573 с.
- Выполнен, успешно: после последних изменений значков повторно выполнены 13 проверок локальных сценариев и страниц настроек.
- Выполнен, успешно: `git diff --check`.
- Сборка 4054 прошла проверку пакета, но не установлена: при сравнении упакованных code objects обнаружено отсутствие двух последних изменений значков. Назначена пересборка; эта промежуточная APK не объявляется окончательной.
- Выполнен, успешно: окончательная ARM64 APK 2.0.7 / 4055, 102,3 МиБ; JNI/ELF 16 КиБ/манифест OK, SHA256 `e27d7590fe3e9db78df9f55af1d8e1d3c0d824fbcf657b79f882f937ddf94109`. Code objects всех семи изменённых модулей оформления/настроек совпадают с текущими источниками.
- Выполнен, успешно: обновление установлено на POCO без удаления данных. Через реальные нажатия проверены персонализация, раскрытие списка тем с подсветкой текущей темы Forest и всплывающее меню действий чата. Тема пользователя не изменялась, удаление не запускалось. Live/микрофон/звук не запускались.
- Выполнен, успешно: повторно открыта главная страница настроек; проверены новая шапка, рамки карточек и голубые значки. Телефон оставлен на этой странице.

### Подготовка dev-v2.0.8 — 13 октября 2026

Исполнитель: Codex. По запросу пользователя подготовлены все текущие изменения оформления к отправке в main с новым тегом dev-v2.0.8. Версия обновлена в pyproject.toml, заголовке приложения и проверке обновлений. Workflow тега собирает Linux, Windows, Android ARM64/x86_64 и публикует предварительный релиз после успешного завершения сборок. Локально проверенная и установленная на POCO косметическая APK имеет версию 2.0.7 / 4055; это не подтверждение сборки 2.0.8 в Actions. Результат нового CI на момент подготовки ожидается.

### Контраст кнопки «Закрыть» — 13 октября 2026

Исполнитель: Codex. На присланном снимке обнаружена тёмная подпись прозрачной кнопки на тёмном фоне. Причина: цвет текста тональной заливки применялся и к прозрачным TextButton/OutlinedButton. «Закрыть» теперь имеет светлую тональную заливку, рамку и тёмный текст; остальные прозрачные действия получают светлый текст в тёмных темах. Обработчики закрытия сохранены.

Выполнен, успешно: 4 проверки `test_project_context_navigation.py`; существующая проверка контраста расширена на кнопку «Закрыть» и прозрачную «Отмена» во всех 7 темах (>= 4.5:1). `git diff --check` прошёл. Эта правка выполнена после тега dev-v2.0.8 и в его исходную сборку не входит. Новая APK и визуальная проверка на телефоне в этом этапе не выполнялись.

### Файлы Office и поиск истории — 14 октября 2026

Исполнитель: Codex. Сервис создаёт настоящие DOCX/PDF/XLSX/CSV и текстовые файлы; поддерживает кириллицу и таблицы. Строки XLSX сохраняются как данные, а не исполняемые формулы/внешние ссылки. Поиск и чтение обычных чатов исключают отрицательные идентификаторы защищённого хранилища, поддерживают курсоры продолжения.

Выполнен, успешно: две проверки `test_office_documents.py` — созданные DOCX прочитаны python-docx, PDF прочитан pypdf с проверкой кириллицы, XLSX прочитан openpyxl с проверкой данных; поиск/чтение обычного чата и отказ приватному ID проверены. Интеграция инструментов в UI/агента находится в следующем отдельном этапе, этот коммит не объявляется полной готовностью всех новых функций.

### Обработка недоверенных изображений и Rust-зависимость — 14 октября 2026

Исполнитель: Codex. По предупреждениям Dependabot проверены аватарки, вложения, просмотр и миниатюры материалов. Выбор декодера ограничен до вызова парсера: JPEG/PNG/WebP/BMP/GIF; сохранённые аватарки — только JPEG, снимки CLI — PNG. Ошибочные байты вложения больше не передаются модели. Это дополнительная защита приложения, а не объявление всех библиотечных предупреждений закрытыми.

- Выполнен: безопасный маркер вместо опасных парсеров на исходном коде выбран во всех пяти вариантах сигнатур EPS/JP2/McIdas; проверка ожидаемо не прошла. Реальный зависающий/повреждающий память PoC не запускался.
- Выполнен, успешно: 5 регрессионных проверок после исправления. Опасные парсеры не вызываются в миниатюрах, просмотре, нормализации/проверке аватарки и анализе вложений. Все пять обычных растровых форматов работают, повреждённые изображения отклоняются.
- Выполнен, успешно: 35 ближайших проверок аватарки, её конфликтов, документов Android и подменённого захвата изображения; реальные камера, микрофон и звук не запускались.
- Выполнен: независимый просмотр нашёл пропущенную миниатюру App/app/material.py; путь исправлен и добавлен в регрессионную проверку.
- Выполнен, успешно: Cargo check и Cargo build --locked с tract 0.22.4 / time 0.3.47. Обновление tract необходимо: прежняя версия запрещала time >=0.3.42.
- Выполнен, успешно: полный Python-прогон на изолированной копии с новой нативной библиотекой — 375 проверок, 367 успешно, 8 серверных пропущены. Первый прогон случайно импортировал старую установленную нативную библиотеку и дал 45 ошибок несовместимости API; повторный прогон использовал свежую библиотеку и прошёл.
- Не выполнен: проверка на физическом телефоне — ADB не видит устройств. Исправленные Android-библиотеки и сборка APK проверяются следующим отдельным этапом.

### Исправленные Android-зависимости — 14 октября 2026

Исполнитель: Codex. Из первоначальных 35 предупреждений Dependabot 18 различающихся advisory: 13 Pillow, 4 cryptography и 1 time; повторения относятся к двум Python-манифестам. Android использовал Pillow 12.2.0 / cryptography 48.0.0, готовых исправленных колёс в индексе Flet не было. Теперь Android и ПК используют Pillow 12.3.0 / cryptography 50.0.2. Для Android добавлена сборка из закреплённого Flet Mobile Forge, с закреплённым crossenv и SHA256 трёх исходных архивов. CI кеширует колёса; верификатор проверяет реальные метаданные APK и OpenSSL 3.5.7 в его libcrypto_python.so. Проверки не означают полного аудита всего приложения/сервера.

- Выполнен, успешно: исходный Forge и затем новый scripts/build_android_wheels.py собрали исправленные Pillow/cryptography для ARM64 и x86_64; для нового скрипта использовались свежие виртуальные окружения и результаты компиляции.
- Выполнен, успешно: 4 проверки против старых/подменённых метаданных, старого OpenSSL и изменённого кешированного архива. Повторно проверен синтаксис всех трёх скриптов сборки.
- Выполнен, успешно: финальный полный Python-прогон — 379 проверок, 371 успешно, 8 серверных пропущены; 4 Rust-теста прошли. После обновления tract также вручную проверены positive/negative/neutral результаты существующего ONNX-классификатора.
- Выполнен, успешно: ARM64 APK 2.0.8 / 4057, 107,1 МиБ; x86_64 APK — 114,3 МиБ. Состав, JNI, ELF 16 КиБ, манифест, наличие image_safety, метаданные Pillow 12.3.0 / cryptography 50.0.2 и бинарная версия OpenSSL 3.5.7 проверены. Использована прежняя нативная Android-БД: её исходники не менялись; sentiment/time в Android не включается.
- SHA256 ARM64: 5e6f4ec8099ae5ff92945423432181f17aa4f9dcc98a1f64ec4f4aedcf6e00cb. SHA256 x86_64: bac22358c1180cd5064660d633e85a026aa7d37afe72f05736ad01b5f5aeb77d.
- Выполнен, успешно: Android 37 x86_64 эмулятор, самостоятельный Python 3.14.6 с собранными колёсами: пять растровых форматов, отказ выбирать EPS/JP2/McIdas, Scrypt/AES-GCM и отклонение подменённого шифротекста.
- Выполнен, успешно: готовая x86_64 APK с Python 3.14.7 установлена на чистый эмулятор. Через реальные нажатия открыты приложение и системный выбор файла; PNG добавлен в чат, показана миниатюра и открыт встроенный просмотр. Traceback/ImportError/ошибок запуска не обнаружено в проверенном журнале. Live/микрофон/звук не запускались; эмулятор запущен с -no-audio.
- Не выполнен: физический ARM64 телефон отсутствует в ADB. Ответ ИИ/платежи/производственная серверная синхронизация этим этапом не проверялись. GitHub Actions и пересчёт оставшихся предупреждений выполняются после отправки коммита; опубликованный dev-v2.0.8 не перезаписывается.

### Android: восстановление выбора файлов — 14 октября 2026

Исполнитель всех перечисленных проверок: Codex. На физическом POCO обнаружен зависший выбор документов. Новая операция сначала восстанавливает завершённый импорт; нативный код освобождает только оставленный waiting без живого callback. Поздний результат старого окна не попадёт в новый запрос.

- Выполнен, успешно: 22 проверки документов и памяти. Полный прогон изолированной сборочной копии — 377 проверок, 369 успешно, 8 серверных пропущены.
- Выполнен, успешно: ARM64 APK 2.0.8 / 4058, 107,1 МиБ, SHA256 1aa6f7cd9b379ab3b7cb85e0a633c9747f375b098e56ea20f8df7c6014758160. Состав и подпись проверены; обновление установлено на POCO с сохранением настроек.
- Выполнен через настоящие нажатия на POCO: добавление собственного PNG, миниатюра, просмотр, закрытие; принудительный перезапуск при открытом выборе файла, повторный выбор, отмена с сохранением предыдущего вложения. Live, микрофон и звук не запускались.
- Не завершена очистка: тестовое вложение снято с черновика, собственный материал Xopilot-security-20261014.png ещё находится в хранилище; телефон отключился перед переносом в корзину. Материалы пользователя не удалялись.
- Выполнен замер памяти в хранилище/API-режиме: PSS 263066 КиБ (около 257 МиБ), RSS 386692 КиБ. Цель 140 МиБ не достигнута.
- Выполнен, успешно: GitHub Actions 38526731998 для 68b1ca6 — Linux, Windows, Android. Dependabot: 35 fixed, 0 open. Новая версия тега не создавалась.
- Не завершена проверка расширенного Canvas: в отдельном прогоне незакоммиченных функций Playwright один раз не смог получить screenshot; это не входит в подтверждённые результаты сборочной копии.

### Интерактивный Canvas — 14 октября 2026

Исполнитель: Codex. Canvas получил тип «Сайт»: настоящий изолированный браузер исполняет встроенные HTML/CSS/JS; поддерживаются DOM, ввод, клики, прокрутка и снимок просмотра. На Android используется отдельный WebView без сетевого/файлового моста. На ПК компонент Chromium устанавливается по отдельной кнопке и запускается только для просмотра. Добавлен выбор DOCX/PDF/XLSX/CSV при экспорте, прикреплении и сохранении локальной копии.

- Выполнен: реальный тест Chromium — JavaScript изменил кнопку после ввода в поле и клика; PNG получен; неоднозначный CSS selector отклонён; браузер и временная папка закрыты. В одном прежнем прогоне была временная ошибка захвата screenshot; добавлено одно повторение только этой ошибки.
- Выполнен: полный прогон текущей изолированной копии — 390 тестов, 382 успешно, 8 серверных пропущены. Для этого прогона использована свежая нативная библиотека. Новые задачи проверяются отдельным этапом.
- Не выполнен: визуальная проверка нового Canvas на телефоне; пользователь выбрал подготовку APK без установки. Нативная сборка APK выполняется, реальный ответ внешней ИИ-модели в этом этапе не проверялся.

### Управление генерацией и процессами — 14 октября 2026

Исполнитель: Codex. Добавлено прерывание незавершённого шага генерации для паузы, продолжение этого шага после возобновления, отдельная остановка задачи и фоновые процессы с PID/выводом. Обрыв сети приостанавливает модель; уже запущенный локальный процесс продолжает работать. После успешной проверки связи запрос ИИ повторяется автоматически. Ошибки авторизации не повторяются как сетевые.

- Выполнен, успешно: реальное прерывание тестового генератора по сигналу, ожидание на паузе и продолжение; искусственный ConnectionResetError остановил генерацию, реальный Python-процесс продолжил работать, восстановление связи возобновило генерацию; HTTP 401 не повторялся.
- Ограничение: пауза прерывает текущую генерацию и повторяет незавершённый шаг, а не сохраняет внутреннее состояние модели/провайдера. Внешний API может тарифицировать отменённый запрос. Задачи живут до выхода приложения.
- Этот коммит содержит основу выполнения. Кнопки и пакетный агент добавляются отдельными проверенными частями.

### Инструменты агента и параллельные действия — 14 октября 2026

Исполнитель: Codex. Автоматический уровень больше не ограничен 16 действиями; завершение выбирает модель, пользователь может отменить задачу. Независимые действия можно передать в одном JSON-пакете; выполняются до четырёх инструментов одновременно, изменения общего Canvas/библиотеки сериализованы. До восьми OS-процессов могут работать одновременно. Ограничение одновременных процессов не является лимитом общего количества действий. Есть запуск долгого процесса, список/PID, чтение вывода и остановка.

- Выполнен, успешно: 20 действий в автоматическом режиме и итог; три настоящие Python-команды со sleep(1) завершились параллельно менее чем за 2,5 с; отдельный фоновый процесс оставался активным и отдавал stdout; доступ из другого чата отклонён.
- Выполнен, успешно: ручной режим является исходным; отклонение не запускает процесс, автоматическое подтверждение применяется только к выбранному проекту. Действия Android продолжают требовать отдельного подтверждения.
- Выполнен: реальное чтение https://example.com. DuckDuckGo не вернул результаты, резервный Bing RSS вернул реальные ссылки по запросу Python official documentation. Скрипты удаляются из читаемого текста; TLS проверяется, DNS закреплён после проверки, локальные/служебные адреса и перенаправления к ним запрещены. Динамические страницы могут отдавать неполный текст.
- Выполнен: настоящие DOCX создаются агентом и возвращаются как вложения. Поиск обычных чатов исключает защищённые/временные чаты.
- Не выполнен: реальный запуск стороннего приложения/медиаплеера Android; звук не проверялся. Реальный ответ API-модели на пакет команд в этом этапе не проверялся — модель заменена генератором протокола, команды и файлы настоящие.

### Единая панель и кнопки задачи — 14 октября 2026

Исполнитель: Codex. Настройки пространства и библиотека объединены: название/иконка, инструкции, режим подтверждения, поиск, просмотр, скачивание, файлы/папки/заметки. Библиотека сохраняется сразу; сохранение формы не затирает новые материалы старым снимком. Автоматический режим включается только после явного выбора и объяснения системных прав команд.

- Выполнен, успешно: две проверки формы — общий вход из библиотеки, сохранение актуальных материалов и явное включение/отключение автоматического подтверждения; пять проверок навигации, включая удаление активного чата с открытием нового пустого, а не старой истории.
- Выполнен: браузер на отдельной тестовой БД показал объединённую панель с инструкциями, режимом, библиотекой и двумя тестовыми HTML-файлами в дереве доступности. Снимок браузера оказался белым; визуальную красоту этим не подтверждаю. Исправлена потенциальная раскладка Expanded внутри Wrap.
- Добавлены «Пауза / Продолжить» и «Команды» с PID, stdout, состоянием и остановкой процесса. Для закрытия окна ПК при активной задаче/процессах добавлено предупреждение и остановка. Принудительное завершение ОС не позволяет показывать подтверждение.
- Не выполнены: физическая проверка новых кнопок на телефоне и реальное закрытие окна ПК во время настоящего API-ответа. Пользователь выбрал подготовку APK без установки.

Итоговая проверка части с меню и задачами: 392 теста, 384 успешно, 8 серверных пропущены. Дополнительно проверена остановка повторяющегося неправильного JSON после трёх одинаковых ответов: это защита от бесконечного расходования API, не ограничение успешных действий. Коммит проверялся с подготовленной версией main.py без незавершённого удалённого подключения.

Визуальная проверка панели дополнена: переход тестовой страницы на CanvasKit устранил белый снимок. Получен настоящий снимок объединённого меню в теме Forest с названием, иконкой, инструкциями, режимом и двумя файлами. По результату поля инструкций и поиска растянуты по ширине панели. Это проверка в браузере, не на физическом телефоне.

### Уточнение подтверждений и пустых папок — 14 октября 2026

Исполнитель: Codex. По уточнению пользователя режим подтверждения перенесён из настроек пространства на кнопку прямо в чате, рядом с моделью. Ручной/автоматический выбор хранится отдельно для каждого обычного чата только на этом устройстве; приватные чаты не получают эту кнопку. Режим выбирается до запуска задачи. При удалении чата старое разрешение сбрасывается.

Добавление папки теперь явно различает живую папку проекта (допускается пустая, ИИ может создавать в ней файлы) и копии материалов библиотеки. Отсутствие файлов при копировании больше не является ошибкой. Подключённая папка отображается в общей панели, её путь не переносится в облако.

- Выполнен, успешно: выбор автоматического режима требует явного подтверждения; другой чат остаётся ручным; возврат к ручному и скрытие кнопки в приватном чате проверены.
- Выполнен, успешно: через обработчик настоящей формы подключена реальная пустая временная папка; список файлов пуст; импорт копий вернул пустой результат без ошибки.

Итог этого уточнения: полный прогон изолированной копии — 393 теста, 385 успешно, 8 серверных пропущены. Последняя проверенная APK 4061 относится к предыдущей раскладке; для кнопки в чате и пустой папки собирается новая APK, старый пакет не выдаётся за обновлённый.

По дополнительному уточнению кнопка подтверждения стала прямым переключателем без выпадающего списка. Первое включение автоматического режима требует предупреждения; после разрешения следующие переключения в этом чате происходят одним нажатием. Согласие сбрасывается при удалении чата. Проверка дополнена прямыми нажатиями и отсутствием повторного диалога после первого разрешения.

### Итоговые артефакты этой части — 14 октября 2026

Исполнитель: Codex. ARM64 APK 2.0.8 / 4063 собрана из коммита 4061198, 107,1 МиБ. Состав, JNI, ELF 16 КиБ, манифест и зависимости проверены; SHA256 de0c0e8de36767794091cd9aeb8613ef23bbe86eaaeb3fb46eaf907107119999. Копия: build/apk/Xopilot-2.0.8-4063-arm64-v8a.apk. Физически не установлена: пользователь выбрал подготовку без проверки телефона.

Браузерная проверка на отдельной БД: настоящая кнопка «Вручную» находится рядом с моделью, выпадающий список отсутствует; первое нажатие показало предупреждение, отмена оставила ручной режим. Снимок сохранён в build/ui/chat-confirmation.jpg. После последней правки прошли 3 проверки панели/переключателя и 5 навигации; предшествующий полный прогон — 393 теста, 8 серверных пропущены.

GitHub Actions 38557737064 для d47f817 успешно собрал Linux, Windows и Android, release пропущен. Это проверка основной функциональности до последних правок расположения/переключателя, не подтверждение всех последующих коммитов в CI. Последние коммиты проверены локально и ARM64-сборкой. На текущей проверке Dependabot — 0 открытых предупреждений. Удалённое подключение к ПК и серверная админ-панель остаются отдельной незавершённой частью и в эту APK не включены.


### Очередь сообщений, инструменты и POCO — 14 октября 2026

Все перечисленные проверки выполнил Codex. Полный прогон изолированной копии с актуальным нативным модулем: 410 тестов, 402 успешно, 8 серверных пропущены. Выполнено: порядок очереди без прерывания текущего запроса; сохранение набранного черновика; уточнение на паузе и продолжение; структурированный API-ответ и адресный fallback; компактный сохранённый журнал инструментов; поиск последних чатов; разрешение Canvas по ID или однозначному названию с проверкой области доступа.

Физически проверено на POCO X5 (Android 17): ответ API 42; создание HTML Canvas и PDF, просмотр PDF, JavaScript-счётчик Canvas 0→1; чтение заметки проекта MOONSTONE42; переключатель ручного/автоматического подтверждения; удаление собственного тестового чата с переходом в пустой; аккаунт; сохранение обеих версий конфликта по разрешению пользователя и последующая синхронизация двух изменений без нового конфликта. Последнее не доказывает полную сходимость двух устройств. Экспорт собственного PNG через системный выбор файла: SHA256 исходника и экспорта совпадают ff498c40d4b86358baabbe76cde333cac80977c1964107b23c435b9b4b6416c8; собственный PNG и экспорт удалены. Live, камера, микрофон и звук не запускались по просьбе пользователя.

Не выполнено: цель холодного запуска за 1 секунду. На установленной APK с фактическим versionCode 6067 полный чат стал виден за 4,384 / 3,859 / 4,133 секунды; Activity стартует за 1,070 / 0,962 / 0,924 секунды. Экран загрузки не считается готовым приложением. После использования функций на предыдущей сборке PSS 228038 КиБ: цель 140 МБ не достигнута. Физический повтор проверки обновлённой очереди и компактного журнала — ожидает установки новой APK.

Уточнение номеров: базовый номер сборки Flet 4067 даёт versionCode 6067 для split ARM64; названия старых APK с 4063/4064 обозначают базовый номер, а не фактический код Android.


APK очереди собрана и установлена через `adb install -r` с сохранением данных: 2.0.8, базовый номер 4069, фактический versionCode 6069, ARM64, 107,1 МиБ. Состав, JNI, ELF 16 КиБ, манифест и зависимости проверены. SHA256 2559a62645b0965de070d62ac4835bc69217444057b1e1fdc141bc19c46186de. Файл: build/apk/Xopilot-2.0.8-4069-arm64-v8a.apk. Физическая проверка очереди пока НЕ выполнена: телефон заблокирован, отправлен запрос открыть Xopilot. Успех unit-теста не выдаётся за проверку через телефон.


Дополнение после разблокировки POCO: физическая проверка очереди ВЫПОЛНЕНА на APK 6069. Во время настоящего длинного API-ответа отправлен второй вопрос; интерфейс показал «В очереди · после текущей задачи» и счётчик 1, кнопка оставалась «Приостановить задачу». Первый ответ завершился, затем пришёл отдельный ответ QUEUE_OK; очередь исчезла. Первый короткий проход не засчитан: ответ успел завершиться до отправки второго вопроса. Собственный чат QA-4069 после проверки удалён с подтверждением через интерфейс, приложение вернулось в новый пустой чат.


### Исправление видимой иконки паузы — 14 октября 2026

Исполнитель Codex. Найдена ошибка API Flet 1.0.3: у ft.Icon меняли произвольное Python-свойство name вместо сериализуемого icon. Поэтому действия и tooltip менялись, но изображение оставалось стрелкой; аналогичная ошибка была у ручного/автоматического подтверждения. Исправлены оба места. Предыдущая проверка очереди подтверждает поведение, а НЕ корректную видимую иконку. Исправлены тестовые утверждения: проверяется настоящее icon; 15 проверок локальных сценариев и 3 панели пространства успешно. Новая APK собирается для визуального повторения на POCO.


### Иконка паузы и независимое управление Linux — 14 октября 2026

Исполнитель всех проверок: Codex. Состояние последнего прогона: ВЫПОЛНЕНО, 418 тестов, 410 успешно, 8 серверных пропущены. Включает отсутствие разрешения, отказ действия, старый/непросмотренный target, запрет сырых move/type/key, удаление временных кадров, закрытие при ошибке модели и запуск помощника из ресурсов при отсутствии исходных Python-модулей.

POCO: ВЫПОЛНЕНО визуально, APK 2.0.8, базовый номер 4070, фактический versionCode 6070. Во время настоящего API-ответа на снимке видны две полоски паузы. SHA256 feb785476a853a910b2df9c607e541fba8a9aade3a2e7690e894534bdc780c1e; JNI/ELF 16 КиБ/манифест и состав проверены, размер 107,1 МиБ. Собственный чат QA-4070 удалён с подтверждением, возврат в пустой чат выполнен. Во время проверки по координатам ответ успел закончиться и открылась панель Live; разговор/микрофон/звук не запускались, панель сразу закрыта. Не выдаём открытие панели за проверку Live. Эта APK собрана до добавления Linux-инструментов, они проверялись из исходников и сервисной копии.

Linux-приложения: ВЫПОЛНЕНО, настоящий Gio-каталог и запуск собственного тестового .desktop; появление нового процесса подтверждено. Первый прототип использовал виртуальную мышь/клавиатуру; после уточнения пользователя этот подход прекращён и удалён из итогового кода. Не утверждаем, что его Ctrl+A работал: проверка не прошла.

Текущий режим работает с основными окнами через AT-SPI. Реально на Niri проверено: кадр 1920×1200, замена русского/английского текста в GTK-поле, действие кнопки, сохранение активного окна. Отдельный отражённый SVG-указатель через layer-shell показан на настоящем экране; поверхность не принимает ввод и не меняет фокус. Системные устройства ввода не создаются. Поля пароля скрываются по числовому AT-SPI role 40, а не только по локализованному названию.

Настоящая модель через настроенный Google API: ВЫПОЛНЕНО в контролируемом сервисном сценарии. Агент сам вызвал computer_start → computer_view → два computer_input, поле действительно содержит QA_AGENT_INDEPENDENT_OK, новый клик подтверждён обновлением файла кнопки, получен итоговый ответ. В API уходило только дерево собственного QA-окна; снимки и содержимое Discord/остальных приложений не отправлялись. Первый проход выполнил действия, но итоговый запрос оборвался на TLS-таймауте — НЕ полный успех. Повтор с TaskControl завершился полностью.

Упаковка: ВЫПОЛНЕНО, системный Python получает помощник из plain-source ресурсов, независимо от pyc встроенного Python; проверены существование приватных восстановленных модулей и удаление каталога после закрытия. Подготовка ресурсов добавлена перед Flet-сборкой в GitHub Actions. Новая компиляция Linux/Windows после этих изменений ещё НЕ проверена.

Браузерный сценарий через чат: НЕ ВЫПОЛНЕН, доступ к локальной странице отклонён политикой браузерного инструмента; обход не использовался. Локальный процесс интерфейса запущен на 8567. Не заявляем универсальное управление любыми приложениями: нужны доступные AT-SPI элементы. Произвольные пиксельные клики/игры/собственная отрисовка недоступны независимому режиму. GNOME/KDE, несколько мониторов и Windows физически не проверены. Удалённое подключение телефона к ПК и серверная админ-панель остаются прежней отдельной незавершённой частью.


## 15 октября 2026 — инструменты, контекст других чатов, браузер и подключение к ПК

Исполнитель всех проверок этого раздела: **Codex**. Пользователь эти тесты не выполнял.

| Проверка | Состояние | Фактический результат |
| --- | --- | --- |
| Формат управления Linux | Выполнен | `Click` нормализуется в `click`; пустой вызов отклоняется до выполнения и возвращается модели на исправление с примером. Сохраняется проверка ID последнего кадра; координатный ввод не добавлялся. |
| Автоматические подтверждения | Выполнен | В автоматическом режиме `computer_session` не создаёт отдельного подтверждения в чате. Ручной режим и разрешение Linux на экран сохраняются. |
| Контекст других чатов | Выполнен | Выдаются короткие исходные выдержки с ID сообщений и продолжением, поиск учитывает query; длинное первое сообщение также ограничено. Проверены сохранение нужной ссылки и исключение защищённых чатов. Полная история в БД не изменяется. |
| Подбор инструментов | Выполнен | Каталог учитывает Android/Linux и подключённую папку; инструкция различает сайты, HTML Canvas, файлы и элементы основных окон. |
| Встроенный браузер Canvas | Выполнен | Настоящий Chromium: JavaScript, fill/click, смена HTML, PNG 960×600, блокировка внешнего fetch, закрытие и удаление временных снимков. Это отдельный тестовый Canvas, не автоматизация пользовательской вкладки. |
| Телефон → ПК: HTTP + PostgreSQL | Выполнен | На изолированной БД `xopilot_test`: два сеанса одного аккаунта, разрешение отправителя, шифрованное задание, повтор без дубля, получение/claim, подтверждение с хешем команды, результат, отзыв доступа. Чужому аккаунту доступ запрещён. Лог: `/tmp/xopilot-remote-qa-result.log`. Это протокол двух устройств, не физический телефон. |
| Публичное подключение к ПК | Не выполнен | Авторизованный запрос `/remote/hosts` получил HTTP 404. Рабочий сервер ещё не предоставляет этот маршрут; развёртывание серверного модуля в рамках этой проверки не проводилось. Клиент объясняет необходимость обновления вместо общего сообщения об ошибке. |
| Проверка настоящей моделью | Не выполнен полностью | Модель выполнила search_chats на отдельной тестовой истории; следующий этап остановлен ответом API HTTP 429. Успех всей цепочки не заявляется. Тестовые история/Canvas изолированы и очищены. Лог: `/tmp/xopilot-real-tools-current.log`. |
| Лента вызовов | Код и компонентные проверки выполнены | Более лёгкие строки со значками состояния, подробности раскрываются; подтверждённая карточка сворачивается. Визуальная проверка пользовательской вкладки не выполнена: браузерный инструмент отклонил доступ, обход не применялся. |
| Регрессия приложения | Выполнен | `python/linux/bin/python -m unittest discover -s tests -q`: 429 тестов, 420 успешных, 9 пропущены (включая тест, требующий отдельного QA-сервера; он успешно выполнен отдельно). Лог: `/tmp/xopilot-current-all-suite.log`. |
| Телефон / APK / Live | Не выполнялись | Новая APK не собиралась и на телефон не устанавливалась. Live, микрофон и звук не запускались. |

Дополнительная проверка после объединения свежего `origin/main`: зависимости установлены в отдельный `/tmp/xopilot-dependency-qa-20261015` (основное Python-окружение не заменялось). Flet **1.0.4**, pypdf **6.20.0**, ReportLab **5.0.1**: повторный полный прогон **429 тестов, 420 успешных, 9 пропущенных**. Лог: `/tmp/xopilot-new-dependencies-suite.log`. Пользовательское изменение `org` в `pyproject.toml` сохранено незакоммиченным.

### Браузер, привязка устройств и режим пространства — 15 октября 2026

Все перечисленные проверки выполнял **Codex**. Подтверждение привязки настоящего POCO на ПК нажал пользователь. Статусы ниже относятся к конкретным сценариям, а не ко всем возможным устройствам.

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Регрессия приложения | Выполнен | 440 тестов: 431 успешный, 9 пропущенных. Flet 1.0.4, pypdf 6.20.0, ReportLab 5.0.1 в отдельном окружении. Лог `/tmp/xopilot-final-verified-suite.log`. |
| Бэкенд и PostgreSQL | Выполнен | Полный прогон с включением изолированных проверок: 12 unit + 8 HTTP-тестов, без ошибок. Только отдельная БД `xopilot_test`, не рабочая БД. |
| Развёртывание сервера | Выполнен | Устранён HTTP 404 у удалённых заданий; затем добавлены запросы привязки, подтверждение только целевым ПК, отзыв и heartbeat без восстановления отозванного доступа. Перед обновлением сохранены БД и прежний бинарный файл в `/data_2/backups/xopilot-remote-20261015T131634Z`. |
| Изоляция привязки | Выполнен | Отправитель не может сам подтвердить доступ; чужой аккаунт не может подтвердить запрос; до согласия ПК список разрешённых хостов пуст. Отзыв сохраняется после heartbeat. HTTP-тесты с настоящей БД. |
| Старый поток телефон → ПК | Выполнен физически | POCO отправил задание, настоящий ПК выполнил его, телефон показал `REMOTE_PHONE_OK_15`. Это проверка протокола до переноса отправки в строку ввода пространства. |
| Новая привязка через интерфейс | Выполнен физически | На POCO нажата «Связать» у ПК в сети; на ПК появилось «POCO X5 5G хочет связаться с этим ПК». Пользователь подтвердил; на телефоне появилось «Связано · В сети». Старый сеанс того же ПК остаётся отдельным отключённым устройством; автоматически не удалялся. |
| Продолжение синхронизированного чата | Компонентная проверка выполнена | Используется UUID синхронизации, проверяется принадлежность пространству и последняя реплика. История передаётся модели; новый чат и дубликат пользовательского сообщения не создаются. Физическая проверка новой строки ввода ниже дополняется после выполнения. |
| Настоящая модель и инструменты Canvas | Выполнен | OpenRouter: поиск/краткое чтение тестового чата → создание HTML → DOM → нажатие → проверка кода 647291. Отдельная тестовая БД. В пользовательском интерфейсе собственный тестовый Canvas также дал «Готово 42». Ранее полученные 429 и пустой ответ не выдаются за успех. |
| Восстановление API | Выполнен | 429 ставит текущий шаг на ручную паузу; пустой ответ повторяется один раз, затем ставится на паузу. Выполненные инструменты не запускаются повторно. Проверено тестами. |
| Браузер Material 3 / Xopilot | Выполнен на ПК | Компактная панель, адрес локального Canvas, назад/вперёд/обновление, большая область сайта. Настоящий Chromium: изменение viewport, нажатие по координатам, история переходов назад/вперёд, JavaScript. Сеть и файлы ПК по-прежнему недоступны странице. |
| Скачущая область браузера | Исправлен и проверен | Причина: появление ProgressBar меняло высоту страницы и вызывало цикл resize. Высота индикатора теперь постоянна, одинаковые размеры игнорируются. Регрессионный тест воспроизводит события размера при каждом обновлении; backend resize вызывается один раз. В интерфейсе нажатие показало «Готово 42» без скачков. Снимок `/tmp/xopilot-browser-material3-stable.png`. |
| APK | Выполнен | ARM64, версия 2.0.8, build 4092 / versionCode 6092, 108,0 МиБ. Состав, JNI, ELF 16 КиБ и манифест проверены; Pillow 12.3.0, cryptography 50.0.2. SHA256 `76e515de853dd9bd6fb1c2c4b23be03a4ab2c2b753959e7f4dd23e1cfcb49889`. Установлена на POCO через `adb install -r`, данные сохранены. |
| Курсор ИИ | Код и компонентная проверка выполнены | Размер 36 → 22 пикселя; ошибка визуального overlay больше не помечает успешное действие AT-SPI как ошибку и не провоцирует повторный клик. Обновлены упакованные исходники помощника. Новое управление личными окнами и внешний вид курсора на экране пока не проверялись. |
| Live / звук | Не запускались | По просьбе пользователя микрофон, Live и воспроизведение звука не включались. |

Промежуточный прогон после добавления режима пространства нашёл 30 ошибок тестового стенда: подменённый builder поля ввода возвращал пустой Container. Встраивание переключателя перенесено в явный параметр builder; повторный полный прогон успешен. Первый запуск APK после обновления показал пустой экран до полного перезапуска процесса; после перезапуска профиль и переписки доступны, данные не очищались.


### Общий стиль Material 3 / Xopilot — 15 октября 2026

Все проверки этого раздела выполнял **Codex**. Пользовательские данные и настройки провайдера не очищались и не заменялись. Оценка относится к перечисленным сценариям.

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Общая тема | Выполнен | Явная Material 3 ColorScheme, типографика, поверхности, формы диалогов, кнопки, переключатели и checkbox. В семи палитрах основной и вторичный текст, а также подписи primary проверены на контраст не ниже 4,5:1. Это не полный аудит доступности всех экранов. |
| Регрессия приложения | Выполнен | 443 теста: 434 успешных, 9 пропущены. Лог `/tmp/xopilot-material-final-suite.log`. Отдельное окружение Flet 1.0.4 / pypdf 6.20.0 / ReportLab 5.0.1. `git diff --check` успешен. |
| Настройки на ПК | Выполнен через интерфейс | Нейтральная шапка, заметная кнопка закрытия, карточки разделов, персонализация и раскрытие списка тем. При прокрутке шапка остаётся на месте, «О программе» доступно. Скриншот `/tmp/xopilot-material-settings.png`. |
| Поиск пространств на ПК | Выполнен через интерфейс | Ввод Rust оставил одно соответствующее пространство; очистка вернула весь список. Выбор пространства, создание и удаление данных для этой проверки не требовались. |
| Android APK | Выполнен | 2.0.8, build 4095 / versionCode 6095, ARM64, 108,0 МиБ. Состав, JNI, ELF 16 КиБ и манифест проверены. Pillow 12.3.0, cryptography 50.0.2. SHA256 `32fcfad006f7667bd5cfa1eb7300e4435d6daef3ad64f43de675949ff3ecf0f0`. |
| Настройки на POCO X5 5G | Выполнен физически | APK установлена через `adb install -r`, процесс перезапущен без очистки данных. Открыты меню → настройки → персонализация → список семи тем. При прокрутке заголовок/закрытие сохраняют координаты, последний раздел полностью доступен. Тема пользователя «Лес» сохранена. |
| Пространства на POCO | Выполнен физически | Меню → пространства: поле поиска, карточки и заметная кнопка закрытия. Ввод DeviceQA оставил соответствующее пространство. Клавиатура не перекрывает результат и закрытие. |
| Ответы ИИ в этом проходе | Не проверялись заново | В сохранённой переписке телефона отображались предыдущие HTTP 500 сервиса ИИ. Они не считаются новым успешным или неуспешным запросом этой проверки. Универсальная работоспособность провайдера не заявляется. |
| Live / звук | Не запускались | По просьбе пользователя. |
| Остальные платформы и все функции | Полная ручная проверка не выполнена | Этот проход проверяет общий дизайн, регрессию и перечисленные действия на ПК/POCO; Windows, ChromeOS и все сценарии ИИ им не покрыты. |


### Синхронизация и права подписок — 15 октября 2026

Все проверки выполнял **Codex**. Условия функций выбраны по поручению пользователя. Цены и скидки сохранены, облачная квота остаётся 128 МиБ. Реальные платежи не проводились.

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Полная регрессия приложения | Выполнен | 450 тестов: 441 успешный, 9 пропущены. Финальный лог `/tmp/xopilot-sync-plans-final-suite.log`, 37,348 с. Проверки с неверным ключом специально выводят ошибки SQLCipher, итог набора успешен. |
| Планировщик синхронизации | Выполнен | Завершение ответа будит синхронизацию без обхода сетевой паузы; активный обмен — 15 с, простой — 60 с, занятой lease — повтор через 5 с. Сбои — 15/30/60/120/240/300 с; успех сбрасывает паузу. Состояния аккаунтов изолированы. |
| Повторы транспорта | Выполнен | Обрыв сети и HTTP 500/502/503/504 повторяются до трёх попыток с прежними байтами/operation ID. Ошибки авторизации и бюджет трафика не обходятся. Выбор аккаунта и категорий повторно проверяется. |
| Экран синхронизации на POCO | Выполнен физически | APK 4096 установлена через `adb install -r`, профиль сохранён. Открыты Аккаунт → Синхронизация, нажата ручная синхронизация. Окно само показало завершение 15.10 21:03, отправлено 0 / получено 0, без ошибки. Категории, пароль, трафик и ключ не менялись. Снимок `/tmp/xopilot-sync-phone-20261015.png`. Это не отдельный физический перенос нового файла между телефоном и ПК. |
| Серверные подписки на тестовой БД | Выполнен | 15 Rust-проверок с включёнными изначально ignored DB-тестами, все успешны. В том числе скидки, продление/повтор оплаты, истечение подписки, конкурентные задания, повтор задания при заполненной очереди, ознакомительный режим. Только отдельная `xopilot_test`, не production. |
| Серверные HTTP-сценарии | Выполнен | 8 проверок API с настоящей тестовой PostgreSQL: владельцы/сессии, порядок изменений, конфликты, файлы, отзыв доступа, переименование устройств и привязка. Все успешны. Лог `/tmp/xopilot-sync-plans-integration.log`. |
| Тарифы на POCO | Выполнен физически | После ответа настоящего backend показаны Micro, 128 МБ и ознакомительный режим без продажи. Прокрутка до Elite/Ultra показывает новые права и цены; оформление недоступно. Кнопки оплаты не нажимались. |
| Тарифы в браузере | Выполнен через интерфейс | Карточки Micro/Elite/Ultra/Led содержат новые функции и условия. Покупка недоступна до запуска продаж; курс/валюта отображения сохранены. Скриншот `/tmp/xopilot-subscriptions-20261015.png`. |
| Развёртывание backend | Выполнен | Release-сборка успешна, бинарный файл и БД предварительно сохранены в `/data_2/backups/xopilot-plans-20261015T175913Z`, затем сервис обновлён и health/database проверены. Платёжные настройки не включались. Изменения исходников отдельного backend сохранены патчем в `Server/patches/`. |
| Android APK | Выполнен | 2.0.8, build 4096 / versionCode 6096, ARM64, 108,0 МиБ. Манифест/JNI/ELF 16 КиБ проверены. Pillow 12.3.0, cryptography 50.0.2. SHA256 `b9bb98c4fb5124c869dce782ac83dc871f3f3be67011af05fa616ffd2d9cdb31`. |
| Оплата и облачные модели | Не включены | Нужны OAuth владельца DonationAlerts и реально развёрнутые платные модели. До этого сервер сохраняет ознакомительный доступ; лимиты платных удалённых заданий включаются вместе с продажами. Учёт inference-токенов/трёх Elite-сообщений не заявляется реализованным: облачного inference в этом этапе нет. |
| Live / звук | Не запускались | По просьбе пользователя. |


Дополнительная интеграция синхронизации выполнена: **8 из 8 успешны**, 488,966 с. Два отдельных профиля с SQLCipher и настоящий API с отдельной PostgreSQL `xopilot_test`: библиотека/заметки/файлы, повторное включение материалов, редактирование и удаление, ограничения трафика и повтор передачи, конфликты с сохранением обеих версий, профиль и аватарка, защищённые чаты после закрытия, временные чаты остаются локальными. Лог `/tmp/xopilot-sync-plans-integration.log`.

### Хранилище, профиль, компактный режим ПК и общий журнал действий — 15 октября 2026

Исполнитель всех проверок — **Codex**.

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Регрессия приложения | Выполнен | 451 тест: 442 успешных, 9 пропущены. Лог `/tmp/xopilot-ui-groups-final-suite.log`, 36,848 с. |
| Группировка действий | Компонентная проверка выполнена | Несколько инструментов одного ответа создают один свёрнутый блок. Каждый шаг и результат отдельно сохраняются в БД с идентификатором ответа. Восстановление/повторная группировка истории сохраняют порядок и не дублируют шаги. Подтверждения команд остаются отдельными видимыми запросами. Старые последовательные записи без идентификатора группируются по соседству. |
| Хранилище | Код и проверка функций выполнены | Общие тональные поверхности, карточка объёма, значки файлов и новые сегменты «Устройство/облако». Просмотр, экспорт и поиск проверяются по реальному идентификатору материала. Первая регрессия нашла зависимость старого теста от «первого Container»; после появления сводной карточки тест переведён на идентификатор материала, повтор успешен. |
| Профиль и режим ПК | Код и регрессия выполнены | Убрана белая рамка аватара и белая подложка карточки; кнопка аккаунта использует тональную поверхность. Локально/ПК — компактный сегмент 172×38 вместо двух обычных широких кнопок. Логика разрешений не менялась. |
| Админ-панель | Проверен код и сервер; не развёрнута | Через `ssh -p 2222 denbroliik@ssh.xopilot.by` подтверждён `xopilotunit1`: backend на 127.0.0.1:7060 и службы Xopiser работают, слушателя 7799 и отдельной службы/конфига/установленного бинарного файла панели нет. Это не проверка внешнего проброса порта. `cargo build --release --bin admin --locked --offline` успешен. Вход и административные изменения не проверялись. Исходники и пример службы добавлены в `Server/admin`; пароль администратора не назначался. |


Браузерная проверка последнего интерфейса выполнена: в сохранённой переписке два инструмента отображаются одним свёрнутым блоком «Действия ИИ · 2»; раскрытие показывает оба шага и результаты, повторное нажатие сворачивает. В хранилище проверены новая сводка места и карточки, поиск QA-4063 оставляет соответствующие материалы; поиск очищен. Данные не удалялись. Скриншот `/tmp/xopilot-storage-material-20261015.png`.

Финальная APK этого этапа: **2.0.8 / build 4098 / versionCode 6098**, ARM64, 108,0 МиБ. SHA256 `2930727a2d2b26e5e374fbfbb3a2aa08890f700ea0f045bc78f9649a9c74af4b`; манифест, JNI, ELF 16 КиБ, Pillow 12.3.0 и cryptography 50.0.2 проверены. Установлена на POCO обновлением без очистки данных. Промежуточная 4097 была собрана, но не устанавливалась.

Исходники админ-панели, пример службы и инструкция SSH-подключения через порт 2222 отправлены в `main`, коммит `ebe50cc`. Пароль/конфиг панели на сервере не создавались, служба не включалась; наличие исходников в Git не считается проверкой работающей панели.

POCO / APK 4098: открыты профиль и новое хранилище, сводка объёма и переключатели видны, сведения аккаунта сохранены. В чате подтверждены компактные сегменты «Локально / ПК» (общая ширина 172 dp) и общий свёрнутый блок двух действий; нажатие раскрывает шаги. Доступ к ПК и режим подтверждения не менялись. Live, звук, удаление материалов и выполнение новых команд не запускались.


### Приватная панель управления и удаление исходников из Git — 15 октября 2026

Исполнитель всех проверок — **Codex**. Этот раздел заменяет прежнее состояние админ-панели выше; старые строки сохранены как история этапов.

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Приватность исходников | Выполнен | Серверные файлы удалены из текущего дерева и истории main с отдельного разрешения владельца. Очищенная main отправлена; дерево приложения при переписывании совпало полностью. Теги не содержали Server/. Локальная резервная копия сохранена вне репозитория. Старые клоны, форки и кэш GitHub могут сохранять прежние коммиты. |
| Защита от повторной публикации | Выполнен | Server/ игнорируется в приложении; приватный backend исключён из Git отдельного серверного checkout. Новая реализация панели и конфигурация в публичный репозиторий не отправлялись. |
| Административный API | Выполнен | Реальный HTTP + отдельная PostgreSQL xopilot_test: вход, сессия, Host/Origin, CSRF, подтверждение логина, границы квоты и отказ загрузки сверх неё, ручная подписка и скидка, изоляция отзыва устройств, отмена задания/заказа, блокировка входа и отзыв токенов, разблокировка, аудит, выход. Итоговая повторная проверка: 1 успешный тест, 39,04 с. Лог /tmp/xopilot-private-admin-final-qa.log. |
| Регрессия API | Выполнен | 8 из 8 успешны, 175,99 с; отдельная тестовая база. |
| Внутренние серверные проверки | Выполнен | 15 из 15 успешны, 109,23 с, включая Google, тарифы и хранение файлов. Общий лог /tmp/xopilot-private-admin-integration.log. Два прежних предупреждения компилятора в тестах о неиспользованном Json не являются ошибками. |
| Интерфейс панели | Выполнен в браузере | Вход, поиск тестового пользователя, карточка аккаунта, сохранение квоты 64 МиБ, запись в читаемом журнале. Проверена итоговая release-сборка; пример /tmp/xopilot-admin-final-20261015.png. Пароль и аккаунт синтетические, база xopilot_test. На телефоне в этом этапе не проверялось. |
| Серверная установка | Выполнен | Release API и панели собраны, контрольные суммы сверены после передачи SSH. Перед миграцией создана резервная копия базы и предыдущего бинарного файла. API перезапущен; health сообщает database=ready. Файл службы панели прошёл systemd-analyze verify. |
| Пароль администратора | Ожидает владельца | Подготовлен скрытый ввод в терминале и сохранение только Argon2id-хеша с правами 600. Новый пароль должен задать владелец. Панель не запускается без конфигурации; публичный порт не открывался. |
| Граница доступа | Проверено на отдельной базе | Управление аккаунтами, квотами, подписками, скидками, сеансами, заказами и заданиями. Ключи E2EE и расшифрованная переписка недоступны; удаление аккаунтов/файлов и произвольная серверная консоль не реализованы. Это не полный независимый аудит безопасности. |
| Личные данные и звук | Не затрагивались | На production не изменялись аккаунты, подписки или материалы. Live и звук не запускались. |


Обновление запуска приватной панели: владелец задал пароль через терминал. Codex проверил на сервере active у службы, права 600 у конфигурации, HTTP 200 у формы входа и HTTP 401 у списка аккаунтов без авторизации. Слушатель только 127.0.0.1:7799. SSH-туннель с ПК открыт; через него форма входа также отвечает HTTP 200. Вход с паролем владельца и административные изменения production не выполнялись.

После входа владельца Codex проверил production-панель через браузер: видны 4 аккаунта, 5 активных устройств, 36,2 МБ общего использования и квоты по 128 МБ. Список пользователей и статистика загрузились. Выполнялось только чтение; аккаунты, тарифы, сеансы и данные не изменялись. Личные адреса из панели в отчёт не копировались.


### Расширенная приватная панель, Android и восстановление управления ПК — 16 октября 2026

Исполнитель проверок — **Codex**. Серверные исходники остаются вне публичного репозитория.

| Проверка | Состояние | Результат / границы |
|---|---|---|
| Удаление аккаунтов | Выполнен на xopilot_test | CSRF, причина, логин и UUID; неверный UUID отклоняется. Аккаунт и связанные записи удаляются каскадно, очистка файлов проходит через устойчивую очередь. Проверено сохранение файлов другого владельца и обезличенной платёжной квитанции; административный аудит переживает удаление аккаунта. Production-аккаунты не удалялись. |
| Удаление чата | Выполнен на xopilot_test | Чужой UUID отклоняется; своя запись получает новую ревизию и tombstone в ленте синхронизации. Панель видит UUID/размер, не название или содержимое. Материалы библиотеки, резервные копии и старые зашифрованные версии истории синхронизации этим не стираются. |
| Серверные проверки | Выполнен | 1 расширенный HTTP-тест панели: 31,35 с; 8 API-тестов: 121,38 с; 15 внутренних: 76,20 с. Все успешны. Лог /tmp/xopilot-admin-expanded-all-qa.log. |
| Новая статистика | Выполнен в браузере | Регистрации за сутки/неделю, Google, недавняя активность устройств, чаты, пространства, материалы, файлы, размер БД, ожидающие заказы, подтверждённые платежи, очередь очистки. Проверена форма удаления без отправки запроса из браузера. Скриншот /tmp/xopilot-admin-delete-confirm-20261016.png. |
| Production-развёртывание | Выполнен | Резервная копия /data_2/backups/xopilot-admin-expand-20261016T081746Z. Миграция 12, API database=ready, панель active, форма HTTP 200, данные без входа HTTP 401. В production осталось 4 аккаунта; очередь очистки пуста. Отдельный пароль не менялся. |
| Ошибка HTTP 500 с кадром | Воспроизведён и обход проверен | Текущий llama.xopilot.by / Ornith: обычный текст проходит, синтетическая картинка вызывает 500. Это подтверждённое поведение одного провайдера, не всех. Повтор с настоящими аргументами формата computer_view и синтетическим кадром успешно завершился по controls доступности. При отказе кадра используются только элементы доступности; модель не должна заявлять, что видела картинку. Пользовательские изображения автоматически не убираются. Фактический клик по основным окнам в этом этапе не выполнялся. |
| Совместимость API | Выполнен | Настоящий локальный HTTP-сервер проверил повтор запроса после 500 с изображением/response_format. Действия инструментов не выполняются повторно. |
| Google Android | Код и компонентная проверка выполнены | Окно с «Назад» видно до сетевого запроса; при ошибке остаётся доступным. При сбое нативного открытия браузера проверен внешний fallback. Полный вход в аккаунт друга не проверен. По сообщению пользователя: Android 17, сборка 6098. |
| Поддержка | Код и тесты выполнены | Письмо support@xopilot.by с ником, причиной, шаблоном и ZIP. Android предпочитает Gmail, есть выбор почтового клиента. В диагностику не входят БД, переписка, API-ключи, произвольные тексты ошибок. Проверены содержимое ZIP и безопасный формат журнала; настоящее письмо не отправлялось. |
| Запуск | Частично проверен | Убрана загрузка sounddevice при импорте интерфейса: на ПК app.main 451→314 мс, это не время готовности телефона. После одного обновления обнаружена ошибка распаковки Flet; перезапуск без очистки данных восстановил приложение. Добавлена однократная подготовка Python/мостов на Flutter-engine. Время Android Activity не выдаётся за время полной готовности чата; запуск за 1 секунду не подтверждён. |
| Предыдущая правка клавиатуры | Недостаточна по отзыву пользователя | Debounce Python не устранил видимое дёргание в сборке 6100. Новая правка переносит переход высоты в Flutter и исключает повторную компоновку Python на обычных кадрах IME. |
| Регрессия новой нативной компоновки | Выполнен | 456 тестов: 447 успешных, 9 пропущены; 38,549 с. Лог /tmp/xopilot-keyboard-native-suite.log. |
| Личные данные / Live | Сохранены | APK ставятся обновлением. Не очищались данные приложения, не удалялись настоящие чаты/материалы, не запускались Live и звук. При ранней координатной проверке в черновик попал тестовый текст и содержимое буфера; отправка не выполнялась, поле затем проверено пустым, новых сообщений в переписке нет. Последующие проверки используют элементы UI и не вводят текст. |

Нативная клавиатура: APK **2.0.8 / build 4101 / versionCode 6101**, ARM64, 108,0 МиБ, SHA256 `7e605f82d9ad5d571fca7e392683dc5d12ef4deb09f20a1fb898d698b74bcbaa`. Содержимое, JNI, ELF 16 КиБ и манифест проверены сборочным скриптом. На POCO (SDK 37 / Android 17) обновлена поверх работающего приложения без очистки данных; после PackageUpdateActivity открылся чат без прежней ошибки распаковки. Нативный KeyboardViewport обрабатывает переход высоты в Flutter, Python не перекомпоновывает обычные кадры IME. По отзыву пользователя стало лучше, но небольшой рывок остался; эта сборка не считается финальным исправлением.


### Окончательное исправление клавиатуры POCO — 16 октября 2026

Исполнитель проверок — **Codex**, дополнительная оценка плавности — пользователь на своём телефоне.

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Причина остаточного рывка | Проверена сравнением вариантов | Нативная анимация с повторным стартом на каждом изменении высоты запаздывала за IME. Вариант 6102 без сглаживания также показал скачки промежуточных размеров на записи; не выбран финальным. |
| Нативный переход 6103 | Выполнен, подтверждён пользователем | Критически затухающая анимация сохраняет скорость при смене целевой высоты. Python не перекомпоновывает обычные кадры IME; нативные уведомления передаются после стабилизации. Учитывается системное отключение анимаций. Отзыв пользователя после установки: «Теперь плавно». Это проверка POCO, не всех устройств Android. |
| Проверка настоящего интерфейса | Выполнен | ComposerSmoke через UI Automator трижды открывает/скрывает клавиатуру и сверяет неизменность черновика. Сборка 6103: OK (1 test), лог /tmp/xopilot-composer-6103.log. Сообщения не отправлялись, Live и звук не запускались. |
| Проверки мобильной логики | Выполнен | 19 тестов, 1,471 с, и 1 проверка версии, 0,009 с; все успешны. Логи /tmp/xopilot-ime-mobile-tests.log и /tmp/xopilot-ime-version-tests.log. Полная регрессия Python выше: 447 успешных и 9 пропущенных. |
| Финальная APK | Выполнен | 2.0.8 / build 4103 / versionCode 6103, ARM64, 108,0 МиБ; JNI, ELF 16 КиБ, манифест и зависимости проверены сборочным скриптом. SHA256 588a6e1605d2f1bcb56942e6603c62395b87d90777347477b521de69cd634d27. Установлена обновлением без очистки данных. |

Исходники серверной панели в этот публичный commit не входят. Полный вход Google на телефоне друга и отправка черновика через настоящий Gmail остаются отдельными непроведёнными проверками; исправление плавности не означает завершение этих сценариев.


### Сортировка App/app по назначению — 16 октября 2026

Исполнитель всех проверок — **Codex**.

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Перенос модулей | Выполнен | 48 модулей сгруппированы по предложенной структуре: theme, shared, menu, chat, voice, settings, models, workspace, materials, canvas, browser, tasks. backgraund.py переименован в theme/background.py. Пустые core/state/account не создавались; действующие службы и страницы аккаунта остались в App/services и App/settings. |
| Импорты и шапки | Выполнен | Исправлены относительные, абсолютные импорты, строковые пути mock/patch и шапки исходников. Оба режима запуска (App.app и app) проверяются отдельным тестом импорта всех UI-модулей в свежих процессах. Пакетные __init__.py не загружают компоненты заранее. |
| Полная регрессия | Выполнен | 456 тестов, 38,034 с: 447 успешных, 9 пропущены. Лог /tmp/xopilot-reorganize-suite.log. Дополнительная проверка обоих режимов импортов успешна; лог /tmp/xopilot-package-imports.log. |
| Настоящий интерфейс | Выполнен в браузере | Отдельный пустой профиль /tmp/xopilot-reorganize-profile, порт 8568: главный экран, рабочие пространства, возврат, настройки и персонализация открылись. Ошибок в журнале запуска нет. Временная вкладка и сервер закрыты после проверки. |
| Границы проверки | Зафиксированы | Это перенос структуры исходников. Новые ответы ИИ, Live, операции с личными данными и серверная админ-панель в этом этапе не проверялись и не менялись. |

Android: сборка **2.0.8 / build 4104 / versionCode 6104**, ARM64, 108,0 МиБ успешна. Проверены состав APK, JNI, ELF 16 КиБ, манифест и зависимости; SHA256 `23001584838ad1eecfa63cdefa023eb4caddb7b89d7a67f0cb83e2b73e446d91`. На телефон эта сборка в данном этапе не устанавливалась.

Дополнение: APK 6104 установлена Codex на POCO X5 5G через `adb install -r`, без очистки данных. Package Manager подтвердил versionCode 6104; приложение запущено, через UI Automator видна строка ввода, видимых ошибок запуска нет. Live и звук не запускались.

### Настройки, поддержка и ручные аккаунты — 2.0.9, 16 октября 2026

Исполнитель всех проверок — **Codex**. Проверки production ограничены установкой кода, миграцией и чтением состояния; личные аккаунты не создавались, не удалялись и их пароли не менялись.

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Полная регрессия Python | Выполнен | 462 теста за 53,358 с: 453 успешны, 9 пропущены. Лог /tmp/xopilot-209-final-suite.log. Добавлены проверки viewport настроек, различения DNS/TLS/таймаута и видимого восстановления поддержки. Изолированный тест overlay не требует системного PyGObject. |
| Настройки на POCO | Выполнен через настоящий интерфейс | Конечный viewport ListView и постоянный scrollbar; длинный профиль прокручивается внутри диалога, заголовок остаётся на месте. Добавлены плавное появление разделов и переход состояния кнопок. Это не проверка всех моделей телефонов. |
| Поддержка на POCO | Выполнен без отправки | Синтетические ник QA и причина Support test - do not send. Открылся Gmail: получатель support@xopilot.by, шаблон и реальный ZIP xopilot-support.zip, 457 Б. Письмо не отправлялось; после возврата возможен тестовый черновик. При сбое открытия есть таймаут, сообщение и отдельное сохранение диагностики. Телефон друга не проверялся. |
| Google и регистрация | Частично выполнен | Ошибки DNS, TLS и таймаута различаются; после ошибки Google доступны возврат и повтор без бесконечного spinner. В APK присутствует certifi/cacert.pem. На публичном сервере SMTP не настроен: обычная регистрация по почте остаётся недоступной и теперь объясняет причину. Вход Google на телефоне друга не воспроизведён. |
| Ручной аккаунт и сброс пароля | Выполнен на xopilot_test | Реальный HTTP-тест: CSRF, валидация, дубликат почты, создание по трём полям без подтверждения почты, вход, отзыв старого токена, отклонение старого пароля, вход с новым. Google-only аккаунту сброс пароля запрещён; секреты не попадают в аудит. 1 интеграционный тест успешен за 45,29 с. |
| Форма администратора | Выполнен в браузере | Проверена форма из трёх полей: ник, почта, пароль. Административное создание не выставляет почте ложный статус проверенной. Проверка на синтетическом профиле и отдельной базе. Серверные исходники остаются вне публичного Git. |
| Установка сервера | Выполнен | API и панель собраны, SHA256 сверены после загрузки; резервная копия /data_2/backups/xopilot-209-20261016T131741Z. Миграция 0013, обе службы active, database ready. Панель только 127.0.0.1:7799 через SSH-туннель. Полный независимый аудит безопасности не проводился. |
| APK и установка | Выполнен | 2.0.9 / build 4106 / versionCode 6106, ARM64, около 108 МиБ. JNI, ELF 16 КиБ, манифест и зависимости проверены сборочным скриптом. SHA256 1216997f0af9a66721a6de2e89eec9938e92f2aa77e56c7ff0d73052d799e030. Установлена на POCO обновлением без очистки данных. Live и звук не запускались. |

Сборка Windows в GitHub Actions не считается успешной на основании локальных Python-тестов или сборки APK; результат нового запуска проверяется отдельно после публикации тега dev-v2.0.9.

Дополнение по предыдущему GitHub Actions: Linux останавливался на тестовом импорте отсутствующего gi (исправлена изоляция теста), Windows — на строковом сравнении RUNNER~1 и runneradmin для одной папки. Для папки оставлена проверка os.path.samefile. Три теста панели пространства после исправления успешны за 0,203 с. Тег dev-v2.0.9 пересоздаётся с этим исправлением; завершение новых сборок Windows/Linux/Android пока не подтверждено.

Дополнение по красной отметке connection_failed: в запуске 38908094039 Linux и Android завершились успешно, но Python matcher GitHub создал error-аннотацию из traceback намеренно вызванной сетевой ошибки в тесте восстановления Google. Тест теперь перехватывает ожидаемый WARNING через assertLogs и проверяет тип CloudError; реальные неожиданные ошибки не скрываются. Пять проверок поддержки/восстановления успешны за 1,304 с. На момент проверки Windows ещё собирался, поэтому успешность всего выпуска не заявляется. Исполнитель — Codex.

### Облако, синхронизация и голос — 16 октября 2026

Исполнитель всех перечисленных тестов — **Codex**. Пользователь дополнительно подтвердил слышимость русского голоса на POCO: «да был слышен».

| Проверка | Состояние | Результат / ограничение |
|---|---|---|
| Причина расхождения объёма облака и списка файлов | Выполнен на сервере и двух телефонах | Облачный объём включает прежние вложения и историю синхронизации. Устройство знало описания только части вложений. После чтения разрешённых зашифрованных описаний на POCO и Redmi отображаются 33 материала: около 34,2 МиБ, включая прежние видео и изображения. Общий объём около 36,3 МиБ также включает блоки синхронизации и метаданные. Личные файлы не удалялись. |
| Восстановление каталога | Выполнен через интерфейс | Кнопка «Найти прежние вложения» читает описания доступных чатов и пространств, не восстанавливает переписки и не скачивает содержимое файлов. Категории защищённых чатов, профиля и Canvas этим сканированием не раскрываются. Учтены выбранные области синхронизации, смена аккаунта и исключения файлов. |
| Настоящая синхронизация POCO → Redmi | Выполнен | Через UI создано пространство QA_SYNC_1610 и заметка QA_SYNC_NOTE.md. На обоих телефонах файл открылся с точным текстом QA_SYNC_BODY_1610_verified (26 байт). Проверены не только имена, но и содержимое. Предсуществующий конфликт версий не разрешался автоматически. |
| Удаление только собственных тестовых данных | Выполнен | Собственный тестовый облачный блок 55 байт удалён с подтверждением через интерфейс; сервер подтвердил tombstone. Пространство удалено на Redmi, локальные копии заметки удалены отдельно на обоих телефонах. Прочие проекты, включая старые QA-проекты, не затронуты. |
| Хранилище и библиотека на маленьком экране | Выполнен через UI | Тональные карточки Material 3, разбор объёма, поиск, действия с файлами, закреплённая видимая кнопка «Готово». Исправлены конечный viewport и прокрутка общей панели пространства: заметка доступна на Redmi 7A. Переходы используют нативные анимации; субъективная плавность всех устройств не гарантируется. |
| Устойчивость синхронизации | Выполнен тестами | Повтор временных сетевых ошибок с сохранением изменений, появившихся во время обмена; TLS, авторизация и квота не маскируются повтором. Состояние чтения прежних вложений больше не стирается периодическим обновлением списка. Обрывы настоящей мобильной сети отдельно не имитировались. |
| Русский голос | Выполнен на POCO, подтверждён пользователем | Исправлено распознавание network_required="0" из flutter_tts. Короткий русский TTS-пример слышен. Для отсутствующего английского офлайн-голоса выводится отдельное сообщение. На Redmi 7A не найден системный TTS-движок; сторонний движок не устанавливался. Полный Live-разговор, распознавание микрофона и локальная аудиомодель в этом этапе не проверены. |
| Регрессия Python | Выполнен | 471 тест за 41,721 с: 462 успешны, 9 пропущены. Лог /tmp/xopilot-storage-voice-final-regression.log. |
| Выбор офлайн-голоса Dart | Выполнен | tests/android/speech_voices_test.dart с --enable-asserts: варианты false/0/"0"/"false", локаль, отсутствие/сетевой голос. |
| Серверный HTTP-тест | Выполнен на отдельной xopilot_test | 1 интеграционный тест за 46,32 с: учёт блоков и метаданных, маркировка блоков синхронизации, изоляция аккаунтов. Лог /tmp/xopilot-storage-backend-http.log. Серверные исходники вне публичного Git. |
| Серверное обновление | Выполнен | Резервная копия /data_2/backups/xopilot-storage-20261016T173926Z. Core active после установки; SHA256 бинарного файла 1e1cacb29dbf83a20443e98119059b2e6c7c6343effc3736a1b9d51ce47ed4db. Админ-панель этим обновлением не заменялась. |
| Android-сборка | Выполнен | 2.0.9 / build 4114 / versionCode 6114, ARM64, 108,0 МиБ. Сборочный скрипт проверил состав APK, JNI, ELF 16 КиБ, манифест и зависимости. SHA256 63e1032bf17b554bc6ad14022f72af4204ebc2a1e575bf9d8811eae2b98bfb29. Лог /tmp/xopilot-storage-voice-6114-build.log. |
| Конкурентная подготовка Android bundle | Исправлено; проверено на промежуточной 6113 | При обновлении обнаружена гонка удаления files/flet/app. Добавлены файловая блокировка подготовки и singleTask. Повторный запуск Activity доставляется существующему экземпляру; POCO и Redmi открылись с сохранёнными данными. Это не проверка всех OEM. |

Финальная установка 6114 и запуск на обоих устройствах фиксируются дополнением ниже после фактической проверки. Новые сборки Windows/Linux этим отчётом не заявляются успешными; новый тег выпуска в этом этапе не переносился.

Дополнение по финальной APK: **6114 установлена обновлением без очистки данных на POCO X5 5G (Android 17) и Redmi 7A (Android 16)**. Package Manager подтвердил versionCode 6114 на обоих устройствах. Повторный запуск доставляет Intent текущему экземпляру Activity. Через настоящий UI на обоих телефонах открыты разделы хранилища; после загрузки показаны одинаковые 36,3 МиБ общего объёма и 34,2 МиБ известных материалов, кнопка «Готово» доступна. Собственное QA_SYNC_1610 удалено также на POCO: удаление с Redmi ещё не отобразилось там автоматически к моменту проверки, поэтому мгновенное распространение удалений не считается подтверждённым. Существующий конфликт синхронизации оставлен без перезаписи пользовательских версий. Локальные копии собственного QA-файла и его облачный блок удалены отдельно.

### Компактное меню и dev-v2.0.10 — 16 октября 2026

Исполнитель проверок — **Codex**. Окончательное уточнение пользователя: под «Показать ещё / Скрыть» убраны только «Материалы» и «Защищённые чаты»; «Настройки» и «Аккаунт» остаются видимыми внизу.

- Выполнен: осмотр настоящего меню Redmi 7A. Навигация занимала большую часть высоты, список чатов вмещал одну строку.
- Выполнен: мобильные строки уменьшены до области нажатия 48 dp, уменьшены иконки и промежутки. На промежуточной APK 6115 через UI Redmi и POCO проверены меню, список чатов и переход в настройки. На Redmi вмещаются две строки чатов. Личные чаты не удалялись, Live не запускался.
- Выполнен: полная регрессия перед добавлением сворачиваемого блока — 471 тест, 41,060 с: 462 успешны, 9 пропущены. Лог /tmp/xopilot-2010-regression.log. После добавления блока четыре проверки sidebar успешны за 0,785 с; три проверки Android version contract успешны за 0,026 с.
- Изменено: два дополнительных пункта перемещены в нативный ExpansionTile с переключением подписи «Показать ещё / Скрыть». Открытие анимируется Flutter, без покадровой перекомпоновки через Python. Финальная визуальная проверка и сборка записываются ниже после выполнения.

Финальная проверка выполнена Codex на **POCO X5 5G и Redmi 7A** через настоящий интерфейс: APK **2.0.10 / build 4117 / versionCode 6117** установлена обновлением без очистки данных. Проверены открытие меню, раскрытие дополнительных пунктов, смена подписи на «Скрыть», обратное сворачивание и отсутствие обрезания основных пунктов. Сделан визуальный осмотр снимков обоих экранов. Светлая тема Redmi и тёмная тема POCO проверены. SHA256 APK `7cff7e4d55fa7b616df28d90e1433b2bd12663d821dd38844241bcca5ccb4f57`; размер 108,0 МиБ, состав/JNI/ELF 16 КиБ/манифест проверены сборочным скриптом. Лог /tmp/xopilot-menu-6117-build.log. Live и звук на этом этапе не запускались. Результат новых GitHub Actions проверяется отдельно после отправки тега.

### Финальная доработка, Live, синхронизация и подключения — 17 октября 2026

Исполнитель всех технических проверок — **Codex**. Пользователь отдельно подтвердил: «я слышал голоса». Этап продолжается; незавершённые проверки не считаются успешными.

| Проверка | Состояние | Доказательство / ограничение |
|---|---|---|
| Меню | Выполнен на ПК и обоих телефонах | Удалён пункт «Меню» внутри раскрытого меню, возвращены все пункты без «Показать ещё». Порядок: Новый чат, Чаты, Рабочие пространства, Материалы, Защищённые чаты. Настройки и Аккаунт остаются внизу. На Redmi 7A пункты доступны, список чатов прокручивается отдельно. |
| Нативное появление ответа | Реализовано, проводится UI-проверка | Новый ответ появляется с opacity/offset за 220 мс. При чтении истории анимация не запускается. Покадровые вызовы Python не используются. |
| Интервал обмена | Реализовано | Проверка раз в секунду для целевой задержки около двух секунд между двумя устройствами плюс сеть. Лимит трафика и backoff сохраняются; Android в фоне не даёт гарантии такого интервала. Это обмен сохранёнными сообщениями, не поток несохранённого черновика. |
| Синхронизация занятого устройства | Выполнен с реальным API и SQLCipher | Изолированная xopilot_test, три профиля: исходящие сохранённые сообщения отправляются в upload_only; входящий контекст остаётся отложенным и применяется после обычного обмена. 1 интеграционный тест за 26,257 с, /tmp/xopilot-live-sync-integration.log. Полный набор интеграционных проверок повторно запущен отдельно. |
| Удаление своего аккаунта | Выполнен на синтетических аккаунтах | Отдельная xopilot_test: отказ без авторизации, проверка точной почты и пароля, отклонение подмены владельца, каскадное завершение сеансов и очередь очистки файлов; чужой аккаунт доступен. 1 HTTP-тест за 136,62 с. Личные аккаунты не удалялись. Google-only требует свежего входа; этот отдельный сценарий пока не проверен HTTP-тестом. |
| Локальное стирание | Выполнен в временном каталоге | Отложенная очистка до открытия БД при следующем запуске. Проверены сохранность внешнего исходника и отсутствие перехода по символьной ссылке; при ошибке маркер остаётся для повтора. Удаление облачного аккаунта не стирает другие телефоны, внешние исходники и серверные резервные копии. |
| Серверное обновление | Выполнен | Новый маршрут самоудаления установлен с резервной копией /data_2/backups/xopilot-storage-20261017T055109Z; API и панель active. SHA256 backend: 7a89eeee2eeb4a1aa649071142bc63c0caad1a2e0e2e1b3c30042e229e3bac92. Серверные исходники не входят в публичный Git. |
| Импорт модели на POCO | Выполнен через UI | Gemma4-e2b (2 588 147 712 байт) скопирована по USB, затем выбрана в системном picker. Приложение подтвердило SHA-256 и установку. Модель не буферизуется целиком в памяти при импорте. Временная копия из Downloads удалена после подтверждения; установленная модель сохранена. |
| Локальная генерация Live | Выполнен на ПК и POCO | Настоящая Gemma4-e2b: на ПК ответила «Два плюс два будет четыре» и «Столица Беларуси — Минск»; на POCO — «Два плюс два — это четыре». Вопросы и ответы сохранены в отдельных QA-чатах. Проба началась с выключенным микрофоном и текстовым вопросом. |
| Ленивая загрузка PortAudio | Найден и исправлен реальный баг | piper_voice, live_audio и devices удерживали None после отложенной загрузки sounddevice. Библиотека на ПК установлена; исправлена загрузка перед использованием, шесть проверок Piper и проверки Live успешны. До исправления Live явно показывал ошибку озвучки; после исправления получен новый настоящий ответ, слышимость пользователь подтвердил. |
| Микрофон POCO | Частично выполнен | Android запросил запись; выбрано разовое разрешение. Live достиг состояния «Слушаю вас». Распознанной реплики не было, поэтому ASR не считается проверенным. При mute/stop обнаружено зависание завершения: конкурирующий stop одного recorder. Добавлена сериализация stopAudio; повторная физическая проверка продолжается. Тестовая сессия была закрыта force-stop, данные не очищались. |
| Тарифы и платежи | Серверная логика проверена, реальные списания не проводились | 3 обычных теста и 2 интеграционных на xopilot_test: проверка платежной квитанции, идемпотентности, продления, истечения тарифа и серверных лимитов удалённых заданий. Интеграционные — 22,06 с, /tmp/xopilot-20261017-billing-http.log. Платные модели Zephyr не развёрнуты. |
| DonationAlerts OAuth | Выполнен владельцем и проверен Codex | Владелец выполнил разовую авторизацию через SSH loopback. Проверены принадлежность denbroliik и чтение платежей; серверный файл токенов имеет mode 600, access/refresh присутствуют, срок не истёк. Значения токенов не выводились. Приём оплаты оставлен выключенным до решения владельца о наборе доступных платных услуг. |
| SMTP | Ожидает доступного провайдера | Brevo потребовал недоступный пользователю иностранный номер. Нужен именно отправитель support@xopilot.by; Gmail/Яндекс с другим From пользователь не выбрал. Подготовлен и установлен приватный configure_mail.py: скрытый ввод, TLS-проверка, mode 600 и подключение mail.env к systemd. Реальное письмо пока не отправлено. |
| Проверка опубликованного APK 2.0.10 | Выполнен без переустановки телефонов | GitHub Actions 38950547470: Linux, Windows, Android и release успешны. Загруженный ARM64 APK: CRC без ошибок, SHA256 f6dd97048b5b7fd384193ec6da435fc087d1662f60b8deab5836604af47496d5 совпадает с SHA256SUMS; v2-подпись, manifest/JNI/ELF 16 КиБ проверены. У друга Android 15 показывает «пакет недействителен»; точная модель и файл ещё уточняются. Причина не установлена. |
| Подпись APK | Обнаружено ограничение выпуска | CI использует одноразовую debug-подпись ff4a84…25b4f; локальные APK — другую 2c94d2…4ccdb3. Такие сборки не могут обновлять друг друга без миграции. Постоянный ключ ещё не установлен; запрошено решение пользователя. Нельзя считать эту разницу доказанной причиной ошибки друга. |
| Python-регрессия | Выполнен на текущем этапе | 476 тестов за 38,963 с: 466 успешны, 10 пропущены (в том числе отдельные API-интеграции, выполняемые отдельно). После последней корректировки интервала семь проверок расписания успешны за 0,213 с. Модельный импорт/загрузки: 6 успешны за 7,595 с. |
| README | Обновлён | Возможности, платформы, защита и ограничения, тарифы, сборка и структура проекта; удалены устаревшие заявления про «облако запланировано». Не заявляется завершённая проверка ChromeOS или всех устройств. |

#### Продолжение 17 октября: подпись и отмена записи

Проверки выполняет Codex. Постоянный ключ RSA-3072 создан **вне репозитория**, в каталоге `/home/denis/.local/share/XopilotSigning` (каталог 700, файлы 600). Четыре Android signing secret установлены и их имена проверены в GitHub Actions. Публичный SHA256 сертификата: `52e6ebc1d0610f9c5797e6cc14e02a3920d4cf998d19eefce15f882691135ccc`. Секретные значения в отчёт и Git не включены. Подготовлена локальная цепочка смены debug → release; установка этой цепочки на телефоны пока ожидает сборку. Проверка личности Google разработчика отложена владельцем.

- **Выполнено:** три теста записи Android — отмена ожидания, получение WAV, освобождение при ошибке. Долгая нативная `recordUtterance` заменена короткими begin/poll запросами для доступности команды отмены. Реальная проверка завершения Live на телефоне ещё ожидается; исправление зависания пока не подтверждено устройством.
- **Исправлена изоляция тестов:** новый тест занятой реплики использовал общий аккаунт и оставлял два чата для последующего теста. Теперь создаёт отдельный аккаунт. Полный набор API-синхронизации запущен повторно.
- **Уточнение от владельца:** Tecno Pova 6 Neo успешно установил APK dev-v2.0.9 повторно. Повреждённая загрузка возможна, но не доказана. Друг №2 вошёл через Google; результат друга №1 неизвестен.
- **Платежи:** по явному решению владельца приём остаётся выключенным до запуска облачных моделей Zephyr. Авторизация DonationAlerts сама по себе не означает готовую оплату.

Результаты повторного прогона Codex: **479 Python-тестов за 38,408 с: 469 успешны, 10 пропущены**; **все 9 API/SQLCipher интеграций синхронизации успешны за 234,949 с**. Отдельная изоляция аккаунта устранила взаимное влияние тестов, продуктовые проверки не ослаблялись.

APK **6123** собран и проверен (ARM64, JNI/ELF 16 КиБ, manifest). На **POCO X5 5G и Redmi 7A** установлен поверх 6121 с цепочкой перехода к постоянному ключу, обе установки `Success`, старые чаты видны. На Redmi затем отдельно установлен APK с **только новым ключом**, также `Success`: последующие обновления не требуют старого debug-ключа. Эта миграция относится к нашим локальным сборкам; для прежних GitHub APK чужой одноразовый ключ недоступен.

**Live ещё не завершён:** POCO 6123 дошёл до «Слушаю вас», но снова завис при завершении; Android показывал активную запись. Codex остановил тестовый процесс приложения, чтобы освободить микрофон. Запущена диагностическая сборка 6124, логируются только этапы службы, без PCM, текста или ключей. Предыдущая правка не объявляется исправлением подтверждённого зависания.

Опубликованы три небольших коммита в main: `2872e69`, `f98c0c5`, `0aa548b`. Незавершённая правка Live пока не опубликована.

### 2026-10-17 — компактный Live и ожидание ответа

Проверки проводил Codex (ИИ-ассистент).

- **Выполнено:** Live переработан в компактную панель: состояние, отдельное завершение, микрофон и перебивание, горизонтальный ряд источников. Убрана повторная кнопка завершения. Значки камеры и экрана читаемы на тональном фоне.
- **Выполнено:** нативный индикатор Flutter показывает ожидание ответа в обычном чате и подготовку/распознавание в Live. Индикатор обычной задачи останавливается на паузе и исчезает после завершения; Python не обновляет кадры анимации.
- **Выполнено:** 59 проверок Live, основного композера и сохранения ответов прошли за 4,580 с. Проверка композера наблюдает индикатор внутри настоящего вызова генерации и после завершения.
- **Выполнено:** визуальная проверка панели в браузере при ширине 370 пикселей; это проверка макета, без вызова модели или записи микрофона.
- **Выполнено:** общий прогон Python — 488 тестов за 45,460 с, 478 успешны, 10 пропущены.
- **Ожидается:** проверка этой версии панели в новой APK на телефоне. Автоматическое голосовое перебивание не проверено и этим изменением не добавлено.

**Завершение проверки панели:** APK 6131 (ARM64) собран, проверен и подписан постоянным ключом; установлен на POCO X5 5G через `install -r`, результат `Success`. Старый тестовый чат и его сообщения сохранены. Через настоящий интерфейс открыта новая панель Live: кнопки помещаются, подсказка читается, значки камеры и экрана контрастны в теме «Лес». Запись микрофона и озвучивание в этой проверке не запускались. После последней правки прошла 41 проверка Live/композера. Реальный полный голосовой цикл этой сборкой повторно не проверялся.

### 2026-10-17 — отдельный экран Live

Проверки проводил Codex (ИИ-ассистент).

- **Выполнено:** вместо панели внутри строки ввода сделан отдельный экран поверх чата: состояние и индикатор ожидания в центре, источники и управление разговором снизу, возврат к чату и раскрытие текста сверху. В чате остаётся компактная плашка возврата к активному разговору.
- **Выполнено:** 489 Python-тестов за 38,915 с: 479 успешны, 10 пропущены. Дополнительно все 20 проверок мобильного интерфейса прошли за 1,456 с после добавления проверки расположения оверлея. Проверка контроллера подтверждает: сворачивание не отменяет активный разговор, повторное открытие его сохраняет.
- **Выполнено на устройстве:** APK 6132 подписан постоянным ключом и установлен поверх предыдущей версии на POCO X5 5G, без очистки данных. Через интерфейс проверены открытие полноэкранного Live, возврат к прежнему чату и повторное открытие; элементы помещаются в портретном режиме. Сохранён снимок `/tmp/xopilot-live-6132-poco.png`.
- **Не проверено этим прогоном:** реальный голосовой цикл, камера и передача экрана. Для проверки расположения микрофон и захват не запускались. Анимация отображает состояние ожидания, не измеренную громкость голоса. Автоматическое голосовое перебивание этим изменением не добавлено.

### 2026-10-17 — голосовое перебивание Android, проверка отложена

Проверки проводил Codex (ИИ-ассистент).

- **Код добавлен:** отдельная запись новой реплики во время генерации и TTS, независимая отмена ответа и записи, сохранение начала новой фразы. Запись во время воспроизведения требует успешно включённого Android AcousticEchoCanceler; при отказе остаётся перебивание кнопкой. На ПК автоматическое перебивание пока не включено.
- **Выполнено:** 38 проверок Live/Android-записи прошли за 3,570 с. Проверяются отмена TTS по началу речи, сохранение новой записи до завершения фразы, закрытие фоновой записи и продолжение разговора при недоступном AEC. Отдельный Dart-тест порога шума/тихой речи прошёл.
- **На POCO:** APK 6133 установлен поверх предыдущего; микрофон выдаёт PCM, параллельная запись с обязательным AEC запустилась без ошибки, Gemma выполнялась на GPU. Полное голосовое перебивание пользователем **не подтверждено**. Зафиксировано плохое распознавание первого слова и большая задержка ответа на длинный запрос. По просьбе владельца итоговая проверка Live перенесена в конец; звонок остановлен.
- **Доработано после наблюдения:** вместо высокого фиксированного порога в режиме AEC — порог с учётом фонового шума. APK 6134 собран и проверен, но на устройство не установлен; это не считается успешным тестом голоса на телефоне.

### 2026-10-17 — резерв окна и сжатие контекста

Проверки проводил Codex (ИИ-ассистент).

- **Выполнено:** локальный движок получает явное рабочее окно 4096 токенов; это фактическая настройка LiteRT, а не заявление о теоретическом максимуме Gemma. Лимиты OpenRouter/Google AI Studio читаются из метаданных. Неизвестному совместимому API не назначается выдуманный лимит; если он явно сообщает предел в ошибке, выполняется одна повторная попытка со сжатием.
- **Выполнено:** перед заполнением окна оставляется 15% резерва, старая история сжимается той же выбранной моделью примерно до 15% окна. Короткие важные указания пользователя и доступные последние реплики сохраняются дословно. Полная переписка в БД не изменяется. Обычные сводки кэшируются только в памяти; сводки защищённых чатов не кэшируются.
- **Найдено и исправлено:** первоначальный реальный прогон Gemma исказил порт 7799 до 7999. Теперь числовые значения и пути проверяются по исходнику. Несуществующие значения не подставляются как факты; при необходимости они помечаются неподтверждёнными, а дословные указания имеют приоритет. Если безопасное сжатие невозможно, запрос завершается понятной ошибкой с сохранением исходной истории.
- **Выполнено с реальной моделью:** Gemma4-e2b на GPU после сжатия длинной истории правильно вернула имя Денис, проект Xopilot, путь `src/server.py`, порт **7799**, запрет удаления файлов и условие подтверждения команд. Проверялись сведения из середины разговора. Финальный прогон — **26,3 с**, журнал `/tmp/xopilot-context-middle-debug-3.log`. E4B не установлена и этим прогоном не проверялась.
- **Выполнено:** локальный HTTP-сервер проверил весь транспорт: отказ по переполнению → получение лимита → запросы сжатия к той же модели → сокращённая история с последним вопросом. Тесты также проверяют отсутствие ключа в публичном каталоге, Google-метаданные, неизвестный лимит, ограничения вывода сводки и неизменность оригиналов. Это не проверка платных запросов к живому API-провайдеру.
- **Выполнено:** общий прогон — **502 теста за 40,295 с: 492 успешны, 10 пропущены**. Дополнительные 15 проверок бюджета/метаданных прошли. При отсутствии доступного токенизатора подсчёт приблизительный с запасом. Запрос, в котором уже сами инструкции и текущие вложения превышают окно, явно отклоняется без скрытого обрезания.

Источники контрактов метаданных: [Google Models](https://ai.google.dev/api/models), [OpenRouter Models](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties).

## 2026-10-17 — восстановление задачи агента и ожидание ответа

Все перечисленные проверки выполнил Codex (ИИ), не пользователь.

- ВЫПОЛНЕНО: воспроизведён контракт ошибки из экспорта чата: служебная просьба вернуть JSON становилась последним запросом. Теперь восстановление формата повторяет актуальную задачу пользователя; она также повторяется после результатов инструментов. Уточнения пользователя сохраняются.
- ВЫПОЛНЕНО: регрессия проверяет сохранение имени из истории и исходного вопроса после неверного формата. Отдельная регрессия проверяет сохранение кадра экрана при исправлении следующего ответа. Эти проверки используют подставной генератор; качество настоящего провайдера ими не подтверждено.
- ВЫПОЛНЕНО: все RPC чтения AT-SPI теперь используют общий бюджет 3 с и ожидание одного RPC до 250 мс; после чтения восстанавливается обычный таймаут действий. Обновлены исходник и упакованный помощник. Проверены исчерпание бюджета и восстановление после ошибки.
- ВЫПОЛНЕНО: кольцо ожидания заменено нативной неопределённой полоской в чате и Live. Состояния видимости проверены тестами; Python не запускает покадровый цикл анимации.
- ВЫПОЛНЕНО: полный набор — 505 тестов, 495 успешно, 10 пропущено; журнал /tmp/xopilot-repair-screen-tests.log. После уточнения геометрии полоски дополнительно прошли 49 тестов Live и агента.
- НЕ ПОДТВЕРЖДЕНО: исчезновение реального зависания интерфейса при просмотре экрана. Пользователь уточнил, что используется API. Ограничены задержки обхода доступности, но это ещё не доказательство устранения причины зависания Flutter. Нужен повтор настоящего сценария в обновлённом приложении.
- НЕ ВЫПОЛНЯЛОСЬ: запись микрофона, воспроизведение голоса и проверка перебивания — пользователь отложил их до конца.
- НЕ ПОДТВЕРЖДЕНО: финальная визуальная проверка положения новой полоски Live. Изолированный web-предпросмотр открывался, но после перезапуска тестовой сессии браузер показывал пустую страницу; поэтому успешную визуальную приёмку этой версии не заявляю.

## 2026-10-17 — отзывчивость журнала действий и установка голосов

Исполнитель всех проверок этого раздела: Codex (ИИ).

### Интерфейс и БД

- ВЫПОЛНЕНО: чтение доступности только собственного окна Xopilot заняло 0,257 с (13 элементов). Постоянное зависание при таком чтении не воспроизведено.
- ВЫПОЛНЕНО: на отдельной зашифрованной БД воспроизведено блокирование Python при ожидании внешнего писателя SQLCipher. Даже запись через asyncio.to_thread до исправления дала паузу цикла UI 5,025 с. После освобождения GIL в нативных методах тот же сценарий дал максимум 0,028 с. Ожидаемая ошибка записи после 5 с блокировки сохранена; скрывать ошибку или менять защиту БД не стали.
- ВЫПОЛНЕНО: нативная Linux-библиотека собрана в release и заменена атомарно, резервная копия старой библиотеки сохранена в /tmp/xopilot-native-before-responsiveness.so. Проверялся модуль со схемой 2; незавершённое расширение длительности сообщений не включалось в проверяемую сборку.
- ВЫПОЛНЕНО: журнал действий и промежуточные комментарии сохраняются в worker, обратные вызовы меняют интерфейс только на UI-потоке. Перед итоговым ответом ожидается сохранение уже выпущенных событий. Регрессия проверяет медленную запись, отзывчивость цикла и завершение drain.
- ВЫПОЛНЕНО: конкурентное первое обращение создаёт одно соединение с БД. Отдельный тест SQLCipher с внешней блокировкой на 0,8 с проверяет продолжение цикла UI и успешное сохранение.
- НЕ ПОДТВЕРЖДЕНО: устранение конкретного зависания при настоящем просмотре экрана с пользовательским API. Запущенный пользовательский процесс не перезапускался; ему требуется перезапуск для новых Python-модулей и нативной библиотеки.

### Голоса

- ВЫПОЛНЕНО: исправлена причина отказа Miku в установленной версии: launcher Xopilot больше не используется как интерпретатор Python. Для Linux/Windows x64 предусмотрена отдельная закреплённая среда Python 3.12.15 с проверкой SHA-256 архива. На Linux она реально скачана, распакована и запущена.
- ВЫПОЛНЕНО: исходники экспортёра и лицензии включены отдельным комплектом 21 КБ. Дочернему Python не нужны .pyc основной программы другой версии. Проверено совпадение комплекта с исходниками и компиляция под Python 3.12.
- ВЫПОЛНЕНО: реальная подготовка отдельного окружения CPU PyTorch/ONNX и экспорт Miku в изолированном тестовом каталоге. ONNX: 115245467 байт; SHA-256 0fdae5068c9236895f68ba15ea6278de1bae3ee69191e8e1f8b896efc7a60482. Проверки формы, конечности и совпадения с исходной моделью прошли для 37, 83 и 140 кадров; максимальная абсолютная ошибка 0,001123 при допустимых 0,025.
- Ограничение проверки: исходные веса и энкодеры использовались из проверенного локального кэша; повторное скачивание всех голосовых весов с CDN не выполнялось. Первичная загрузка компонентов один раз оборвалась по сетевому таймауту; добавлены pip с восстановлением загрузки, увеличенное ожидание сети и повторные попытки. Один дальнейший QA-процесс завершился сигналом до публикации результата; повтор с подготовленным окружением завершил установку полностью. Журнал успешного прохода: /tmp/xopilot-miku-packaged-qa-complete.log.
- ВЫПОЛНЕНО: в карточках COVE/Miku/Maple есть прогресс файла в МБ и процентах, неопределённый индикатор проверки/подготовки и отмена. Проверены байты, SHA-256, сохранение старого файла при ошибке/отмене, передача прогресса pip и остановка дочерней команды.
- ВЫПОЛНЕНО: через браузерный интерфейс изолированной страницы проверены появление полоски и счётчика под Miku и сообщение об отмене с возвратом доступных кнопок. Для UI использовался тестовый поток прогресса; это не выдано за сетевую загрузку. Снимок: /tmp/xopilot-voice-download-progress.png.
- НЕ ПРОВЕРЯЛОСЬ: выполнение установки на Windows и озвучка в Live. Микрофон, динамик и голосовой вызов не включались.

Общий итог: 513 тестов, 503 успешно, 10 пропущено. Журнал: /tmp/xopilot-responsiveness-voice-final-tests.log.

## 17 октября: время ответа, подготовка 2.0.11

Исполнитель: Codex. Проверки проводились в отдельных временных базах и каталогах.

- Выполнено: нативный модуль Linux собран со схемой БД 3; длительность записывается атомарно вместе с ответом.
- Выполнено: миграция настоящей базы схемы 2 сохраняет сообщения; старые ответы не получают выдуманное время.
- Выполнено: время сохраняется после открытия БД, переноса через снимок синхронизации и открытия зашифрованного чата; временный чат удаляется по прежним правилам.
- Выполнено: отрицательные/NaN/бесконечные значения отклоняются до записи; отображение секунд/минут отделено от копируемого текста.
- Значение включает подготовку модели, ожидание подтверждения и паузы; это полное время до ответа, а не чистое время GPU.
- Новая версия Android и Windows на данном этапе ещё не собрана; голосовые проверки отложены.

## 18 октября 2026: контекст, инструменты Gemma и dev-v2.0.11

Все проверки этого раздела проводил я, **Codex, ИИ-ассистент**. Личные чаты, проекты и аккаунты в заданиях не использовались: создавались временная SQLCipher-база и отдельная папка проекта.

| Проверка | Состояние | Результат и границы |
|---|---|---|
| Полный Python-прогон | Выполнен, успешно | 524 теста: 512 успешно, 12 пропущено; 64,781 с. Лог `/tmp/xopilot-2.0.11-release-tests.log`. Тесты с намеренными HTTP 400/500 и проверкой отсутствующего провайдера схемы не означают сбой реального сервера. |
| Дополнительная проверка факта перед вопросом | Выполнен, успешно | После полного прогона добавлен случай «Меня зовут Денис. Как меня зовут?». Повторно прошли 17 тестов контекста и HTTP-переноса, 1,110 с. В выдержку попадает имя, а не вопрос. |
| Версия и Android-контракт упаковки | Выполнен, успешно | 12 проверок, 1,319 с; `/tmp/xopilot-2.0.11-release-contract.log`. Это не установка APK на телефон. |
| Сжатие длинной истории, Gemma E2B | Выполнен на настоящей модели, успешно | GPU. В середине длинной реплики исправлены Иван → Денис и 7799 → 8800; ответ сохранил Денис, Xopilot, 8800, `src/server.py`, запрет удаления и условие подтверждения команд. Список исходных сообщений не изменён. `/tmp/xopilot-2.0.11-context-current.log`. |
| Сжатие длинной истории, Gemma E4B | Выполнен на настоящей модели, успешно | Отдельный запуск на GPU дал те же правильные актуальные факты и ограничения. `/tmp/xopilot-2.0.11-e4b-final.log`. Сжатие большой истории на E4B существенно дольше обычного ответа. |
| Инструменты E2B | Выполнен на настоящей модели, успешно | Из библиотеки прочитан бюджет **593**, отличающийся от числа в примере инструкции; создан Canvas с этой суммой. Затем прочитан и заменён `main.py`, реально запущен разрешённый Python, единственный вывод — `42`. Проверены сохранённый документ, содержимое файла и настоящий результат процесса. |
| Инструменты E4B | Выполнен на настоящей модели, успешно | Первый отдельный запуск на GPU: поиск материала, создание Canvas, чтение/замена файла и запуск Python с выводом `42`; `/tmp/xopilot-e4b-schema.log`. Повторный отдельный запуск с суммой **593** тоже прошёл: 101,40 с, backend GPU. Оба метода реальной проверки E4B (контекст и инструменты) завершились успешно за 309,802 с; `/tmp/xopilot-2.0.11-e4b-final.log`, результаты инструментов `/tmp/xopilot-2.0.11-e4b-final.json`. |
| Формат и разрешения действий | Выполнен | LiteRT на Linux использует JSON-схему доступных инструментов. Нативная форма Gemma `tool_name`/список нормализуется; подтверждения и ограничения папки сохраняются. Отклонённая тестовым обработчиком запись не создаёт файл. Зависимые запись/чтение в одном пакете выполняются по порядку; независимые команды сохраняют параллельность. |
| Отсутствующий провайдер JSON-схемы | Выполнен с тестовой заменой runtime | Повторяется только создание диалога, до генерации и выполнения инструментов; затем остаётся обычный проверяемый протокол. На Android текущий мост использует этот обычный протокол, без настольного провайдера схемы. |
| Новые Android/Windows сборки и проверка телефона | Ещё не выполнен в этом разделе | Будут собраны отдельным запуском GitHub Actions по тегу. Реальные задания моделей выше проверены на Linux, а не на мобильном runtime. Live, камера, микрофон и звук здесь не проверялись. |

Первоначальные реальные задания выявили копирование `tool: name`, неправильные JSON-конверты, повторение выполненных команд и неполную замену файла. После исправлений прошли отдельные задания на E2B/E4B. Это проверка указанных сценариев, а не гарантия безошибочности любых действий модели.

Один дополнительный параллельный запуск двух E4B исчерпал VRAM RTX 3050 6 ГБ (`VK_ERROR_OUT_OF_DEVICE_MEMORY`); его результат — **неуспешный запуск проверки**, не успешный тест. После освобождения GPU модели проверялись по очереди. Это не CPU-подмена: успешные запуски проверяют backend `gpu`.

Размер окна берётся из действующего локального runtime, метаданных Google/OpenRouter или явного ответа об ограничении API. Для неизвестных API размер не угадывается. В сводке используются дословные важные выдержки пользователя и приоритет поздних исправлений; полный текст истории остаётся в БД. Это не постоянная память профиля и не гарантия сохранения каждой детали в краткой сводке.

### 2026-10-18 — исправление сборки 2.0.11 и повторная проверка Live

Все проверки этого раздела выполнял **Codex, ИИ-ассистент**.

| Проверка | Состояние | Результат и границы |
|---|---|---|
| Причина сбоя GitHub Actions 39098980581 | Установлена | `shared_preferences_android 2.5.0` требует JNI 1.1, тогда как Flet использует JNI 1.0. Закреплена совместимая версия 2.4.28. |
| Локальная APK 6137 / 2.0.11 | Выполнена успешно | ARM64, 108,1 МиБ. Реальная сборка использовала JDK 21 через изолированный адаптер Flet CLI; без адаптера CLI заменял его JDK 17. Проверены содержимое, JNI, ELF 16 KiB и манифест. Лог `/tmp/xopilot-2011-live-build.log`. Это ещё не успешная сборка Windows/Linux в CI. |
| Полный Python-прогон | Выполнен успешно | 529 тестов, 517 успешно, 12 пропущено, 46,054 с; `/tmp/xopilot-2011-regression.log`. |
| Live и освобождение аудиоресурсов | Автоматические проверки выполнены | 42 теста, 4,505 с. Отдельно настоящий PipeWire-источник записывал до отмены через 2,03 с; после закрытия виртуальный источник удалён. Перебивание человеческим голосом и отсутствие ложного срабатывания от TTS этим не подтверждены. |
| Ornith API, текст | Выполнен успешно | Ответ `2 + 2 = 4`, 2,71 с. Ornith не поддерживает изображения; его HTTP 500 на картинку не является проверкой рабочего vision. |
| Полный Live и интерфейс на трёх устройствах | Не завершены | Новые результаты реальных проверок будут добавлены отдельно. Прохождение модульных тестов не заменяет проверку микрофона, экрана и интерфейса на устройстве. |

Дополнение к проверке 2026-10-18:

- **Выполнено на POCO и Redmi 7A:** подписанная APK установлена через `adb install -r`, обе установки `Success`, данные сохранены. Версия 2.0.11; входной номер сборки 6137, фактический Android versionCode 8137 (смещение ABI Flutter). Созданы отдельные QA-чаты. Через настоящий интерфейс отправлены текстовые запросы; ответы `2+2 = 4` получены, время ответа видно: POCO 9,5 с, Redmi 14,0 с. Кнопка отправки во время генерации имела доступное имя «Приостановить задачу», после ответа вернулась Live.
- **Выполнено на настоящей Gemma E2B:** GPU распознала синюю тестовую картинку: «Изображение имеет ярко-синий цвет». 13,36 с включая загрузку и выгрузку; `/tmp/xopilot-gemma-vision-qa.log`. Это проверка изображения, а не камеры телефона.
- **Выполнено на ПК, сервис захвата:** настоящий `ComputerSession.start/view` получил кадр 1920×1200 и 15 элементов. Захват и инспекция 3,15 с; контрольный asyncio-цикл дал 308 отсчётов, максимальный разрыв 11 мс; `/tmp/xopilot-screen-responsiveness.log`. Проверено отсутствие блокировки Python-цикла в этом сервисном пути, визуальная приёмка основного окна этим не заменяется.
- **GitHub Actions:** исправление сборки отправлено в `ad39e95`, запущен новый прогон https://github.com/Xopilot-AI-NN/Xopilot/actions/runs/39101098656. На момент этой записи Android/Linux/Windows ещё собираются; успех CI не заявляется.

- **Дополнительная причина Windows CI установлена:** старый job `117591163690` завершился на тестах: SQLCipher-файл удерживался после проверки отказа инструмента, а staging Miku нормализовал CRLF в LF. Тестовая БД теперь закрывается явно; сравнение исходников учитывает переводы строк без игнорирования содержимого. 34 связанные проверки прошли локально; успешный Windows-прогон ещё требуется.
- **Live на POCO, частично выполнено:** реальная фраза «Расскажи короткую сказку» распознана и показана в чате, backend — GPU. На Redmi отсутствие аудиомодели показано понятным сообщением, без падения. Ответ и перебивание пока ожидают отдельного результата.
- **Холодный старт Live:** журнал устройства выявил загрузку модели, немедленное закрытие и повторную загрузку для аудиокодировщика. Исправлена первичная загрузка с аудио. 57 связанных проверок прошли; новый полный прогон — 530 тестов, 518 успешно, 12 пропущено, 44,870 с. Новая APK с этой оптимизацией ещё собирается.
- **Синхронизация, частично выполнено:** QA-чат с Redmi появился в действующей БД ПК вместе с двумя сообщениями. Полная двусторонняя сверка POCO/Redmi/ПК и восстановление после обрыва сети ещё не завершены.

- **Live на POCO — перебивание НЕ подтверждено:** первоначальный ответ пользователя был понят как успешный тест, но затем пользователь уточнил «СТОП нет оно не сработало». Предыдущая отметка об успехе отозвана. ASR и генерация наблюдались в журнале, но корректное перебивание и обработка новой фразы требуют диагностики. Проверка остановлена. Задержка полного локального ответа заметная; потоковое озвучивание первых фраз здесь не реализовано и не проверено.

- **Уточнение результата Live:** пользователь пояснил, что был получен ответ на первую просьбу «Расскажи короткую сказку»; перебивание остаётся непроверенным, а не доказанно неисправным. Начат повторный сценарий на POCO с APK 2.0.11 / versionCode 8138. В этой сборке первичная загрузка Live сразу включает аудиокодировщик.

- **Повторная проверка Live на POCO — выполнена успешно:** на APK 2.0.11 / versionCode 8138 пользователь повторил сценарий с настоящим микрофоном: просьба о сказке, затем перебивание во время озвучивания. После повторного теста пользователь подтвердил: «да теперь точно убедился сработало». Успех относится к этому сценарию на POCO; камера, экран и перебивание на ПК этим не проверены. Проверку организовал и журналы проверял Codex, голосовые фразы произносил и результат прослушивал пользователь.
- **Холодная загрузка Live на POCO:** журнал новой сборки содержит один `Begin load` в 08:44:55,369 и `Complete load` в 08:45:12,953 (Europe/Minsk), затем начинается запись микрофона. Повторной загрузки перед записью нет. Время загрузки — 17,584 с; это запуск локальной модели Live, не запуск самого приложения.

## 18 октября 2026: потоковая озвучка и восстановление синхронизации

Исполнитель всех проверок этого раздела — **Codex, ИИ-ассистент**. Проверки телефона выполнялись через ADB и настоящий интерфейс Redmi 7A. Для переписки и файлов использован отдельный QA-чат; личные сообщения не изменялись.

| Проверка | Состояние | Результат и ограничения |
|---|---|---|
| Полный Python-прогон | Выполнен, успешно | 538 тестов: 526 успешно, 12 пропущено, 44,301 с. Лог `/tmp/xopilot-stream-final2-tests.log`. |
| Поток Live и отмена | Выполнен в тестах | Первая законченная фраза передаётся озвучке до конца генерации. Полный ответ сохраняется один раз. Перебивание отменяет генерацию и отбрасывает очередь речи; ошибка аудиоустройства сохраняет полный текст. Android-поллинг передаёт чанки и не выдаёт ошибку модели за успешный частичный ответ. |
| Настоящий поток Gemma E2B на ПК | Выполнен, успешно | GPU: первый фрагмент через 2,284 с, 29 фрагментов, полный ответ через 4,087 с. Склеенные фрагменты совпали с ответом. Лог `/tmp/xopilot-real-stream.log`. Это измерение текста модели, не времени появления звука. |
| Новая APK | Собрана, установлена на Redmi | Версия 2.0.11, Android versionCode 8139. Нативный Java-мост потокового ответа скомпилирован; установка с сохранением данных. Потоковая речь на настоящем телефоне ещё не проверена: на Redmi нет локальной аудиомодели, POCO отключён. |
| ПК → Redmi: вложение | Выполнен, успешно | Файл `qa-sync-1810.txt`, 54 байта, появился в QA-чате, открылся в просмотре и дважды сохранился через системное окно Android. Оба скачанных файла имеют SHA-256 `d34c23e8244b129e5427b8f88336e5e30b27d5e7a20a100a6efc6aea5b555d55`, совпадающий с исходником ПК. |
| Обрыв сети Redmi | Восстановление выполнено, задержка требует доработки | При выключенном Wi-Fi отправлено `QA_SYNC_OFFLINE_1810: Reply OK.`; интерфейс показал «Нет соединения · продолжу автоматически». Wi-Fi восстановлен в `finally`. Без повторной отправки появился ответ `OK.` (метка ответа 20,9 с). Оба сообщения впоследствии найдены в QA-чате ПК. В первые 55 с наблюдения на ПК изменений не было; позднее использовалась и ручная проверка синхронизации, поэтому автоматические две секунды и точное время доставки не подтверждены. |
| Возврат из системного сохранения файла | Наблюдение, не исправлено | Android завершал фоновый процесс Xopilot; при возврате наблюдался пустой экран на время повторного старта, затем чат восстановился без потери файла. Причина завершения процесса окончательно не установлена; ANR не найден. |
| Предыдущий CI | Выполнен, успешно | Run `39101403687`: Linux, Windows, Android — success. Этот прогон предшествует текущему изменению потока Live и не подтверждает его CI-сборку. |
| Камера, экран и перебивание на ПК | Не завершено | Настоящая GUI-проверка зависания ожидает результата пользователя; сервисный heartbeat не заменяет её. Камера/экран и потоковая речь на POCO пока не проверены в новой APK. |

- **Дополнительная доставка при стабильной сети — выполнено:** настоящее сообщение `QA_SYNC_RETURN_1810: Reply OK.` отправлено кнопкой в интерфейсе Redmi; в БД ПК оно обнаружено через **1,87 с** от команды нажатия, без ручного запуска синхронизации. Обратное сообщение `QA_SYNC_ONLINE_1810: marker 921764` автоматически появилось в интерфейсе Redmi; первый подтвердивший это снимок получен через **8,65 с**, включая затраты ADB/UIAutomator. Это верхняя граница наблюдения, а не точное время транспортировки. Один успешный замер не гарантирует такую задержку при любой сети.
- **CI текущего потока запущен:** https://github.com/Xopilot-AI-NN/Xopilot/actions/runs/39117576038, commit `269f4e9`. На момент записи Linux, Windows, Android ещё выполняются.

## 18 октября 2026: зависание API, одно сообщение задачи и анимации

Исполнитель проверок — **Codex, ИИ-ассистент**. Пользователь отдельно воспроизвёл зависание настоящего окна ПК. Этот исходный сбой не считается устранённым только на основании тестов транспорта.

| Проверка | Состояние | Результат и границы |
|---|---|---|
| Полный прогон | Выполнен, успешно | Последний прогон: 552 теста, 540 успешно, 12 пропущено, 49,036 с. `/tmp/xopilot-ui-release-tests.log`. |
| Медленный HTTP с изображением | Выполнен на настоящем локальном HTTP-сервере | Пока сервер удерживает ответ, asyncio продолжает работать; отмена прерывает чтение в пределах тестового таймаута 1 с. Это проверка транспорта, не настоящего окна Flutter. |
| Отказ модели от изображения | Выполнен | Явный HTTP 400 с неподдерживаемым изображением запоминается для выбранных URL/модели. Для кадров управления разрешён один текстовый повтор по настоящим controls; обычные пользовательские фото не отбрасываются. HTTP 500 больше не вызывает дополнительный повтор того же снимка с другим JSON-форматом. Сам по себе 500 не маркирует модель как лишённую vision. |
| Миниатюра снимка | Блокирующая операция вынесена из UI, проверено | Раньше `build_file_tile()` синхронно читал и декодировал изображение. Теперь это фоновая задача с проверкой размонтирования. Настоящий PNG 5000×3000: 0,417 с обработки, 80 отсчётов heartbeat, максимальный разрыв 6 мс. Карточка имеет постоянный размер; готовая миниатюра появляется через fade. |
| Само окно ассистента в AT-SPI | Исправлен обход собственного приложения; GUI-приёмка впереди | До изменения среди доступных приложений был `com.appveyor.flet`; в пользовательском скриншоте ИИ пытался вызвать `Maximize` своего окна. Теперь помощник исключает собственный процесс/родственный клиент Flet по PID, сохраняя доступ к другим приложениям. Настоящий D-Bus-тест исключил один собственный корень; оставшийся обход дал 2 элемента за 3 мс. Это ещё не подтверждение исчезновения зависания после перезапуска ПК. |
| Одно сообщение агента | Выполнен на настоящей временной SQLCipher-БД | Несколько пояснений и итог обновляют одну запись с тем же ID. Проверены параллельные пояснения, сохранение вложения/времени и повтор финализации без дубликата. Удалённая пользователем запись не восстанавливается автоматически. Старые переписки не переписывались. |
| Появление текста и ожидание | Проверено в тестах; визуальная приёмка новой APK впереди | Анимируется только новый текст, история при открытии не перепечатывается. Длинный код использует fade без многократной Markdown-разметки. После анимации текст полный. Индикатор ожидания не обновляется в скрытом состоянии; убрано размытие под пузырями сообщений. Измерение FPS не проводилось. |
| Диагностика UI | Выполнен | Искусственная блокировка цикла фиксируется; в безопасный журнал попадают только относительные пути исходников, номера строк и имена функций, без локальных переменных/чатов/ключей. Во время пользовательского воспроизведения до последнего изменения AT-SPI зафиксирован HTTP 500, но остановки Python-цикла не было. |

- **Проверка интерфейса Redmi, APK 8141 — выполнена:** настоящая API-задача с отдельными `list_library`/`list_apps` дала сворачиваемую группу из двух действий; `STEP_A`, `STEP_B` и итог отображались одним узлом сообщения с одной меткой времени **21,3 с**. XML `/tmp/xopilot-narration-progress.xml`. Видеозапись предыдущего ожидания `/tmp/xopilot-ui8141.mp4` и кадры 5/6 с показывают разные фазы нового индикатора. FPS и субъективная плавность пользователем пока не оценивались.
- **Ограничение текущей API-модели:** в первом, менее явном запросе модель вызвала только `list_library`, но заявила и о `list_apps`. Это не засчитано как выполнение двух инструментов. Повтор с явными отдельными вызовами и полями `message` прошёл; универсальная надёжность планирования этой модели не заявляется.
- **Предыдущий CI `39117576038`:** Android успешно; Linux/Windows остановились на `test_speech_failure_preserves_full_streamed_reply`. Исправлена гонка порядка событий Live: данные попадают в потокобезопасную FIFO до возврата генератора, уведомление asyncio лишь будит потребителя. Новый тест намеренно задерживает уведомления: старая реализация воспроизводимо его проваливает, новая проходит. Нужен новый CI-прогон.
- **Финальная APK 8142:** собрана, подписана постоянным ключом, подпись проверена. Содержимое/JNI/ELF 16 KiB/manifest проверены сборочным скриптом. SHA-256 неподписанной APK `2fb7f78d5004dac75e5c83ac97d40673a347c588a03bfbce69633be57d90d686`. Во время переноса записи/подготовки установки Redmi исчез из ADB; финальная установка ещё не состоялась. Пользователь сообщил о переходе телефона в recovery и перезапускает его. Причина перезагрузки не установлена; это не считается успешной проверкой стабильности устройства.

- **После перезапуска Redmi — выполнено:** дождался `sys.boot_completed=1`; установил APK через `adb install -r`, результат `Success`, versionCode **8142**, версия **2.0.11**. После открытия сохранились `STEP_A`, `STEP_B`, итог и время 21,3 с в одном сообщении, а также группа двух инструментов; `/tmp/xopilot-ui8142-ready.xml`. В crash-буфере текущей загрузки Java-падение Xopilot не найдено; это не проверка журнала предыдущей загрузки. Системное свойство причины содержало `reboot,userrequested,recovery`, окончательная причина не установлена.
- **Появление текста на настоящем экране — выполнено:** запись `/tmp/xopilot-narration8141.mp4` успешно скопирована после перезапуска. На кадре 23,5 с виден частичный новый итог после уже показанных `STEP_A`/`STEP_B`; на кадре 25 с — полный текст в том же пузыре. Исходные записи 15/60 с удалены только из созданных мной временных файлов на телефоне; локальные копии сохранены. FPS не измерялся.
- **Новый CI запущен:** https://github.com/Xopilot-AI-NN/Xopilot/actions/runs/39124927175, исходники `b02ce47` (включают исправление FIFO `f2fff2e`). Итог пока не получен. Последнюю ручную проверку исчезновения зависания ПК пользователь отложил; она остаётся невыполненной.
