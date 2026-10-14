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
