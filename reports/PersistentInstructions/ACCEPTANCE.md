# Persistent instructions — приёмка

Результат: **PARTIAL / real host A02 BLOCKED**. Реализованы внешняя память,
автоматический доверенный ingress, локальная семантическая нормализация,
ограниченный lookup и применение в owned Harness. Это внешняя память,
а не обучение весов модели. OpenCode и локальная модель в среде отсутствуют;
полный host E2E не подменяется протокольными doubles.

Проверяемый код: `7f6ea1df8f56720787776e943d8a284a870bdcac`, поверх опубликованного
`37a280da38d913b6fef7867e0f988ad40026947f`. Source identity:
`07e36dc018a1d91b1d10660024c233d3d3537af4048171d20721665280877bd8`.

- [Ветка GitHub](https://github.com/Ermak-P/Knowledge-/tree/codex/persistent-instructions)
- [Изменения относительно main](https://github.com/Ermak-P/Knowledge-/compare/main...codex/persistent-instructions)
- [Exact-source CI](https://github.com/Ermak-P/Knowledge-/actions/runs/44877877238)
- [Карта возможностей и аудит](../../docs/P4/PERSISTENT-INSTRUCTIONS-AUDIT.md)
- [Установка, обучение, обслуживание и откат](../../docs/P4/PERSISTENT-INSTRUCTIONS.md)
- [Пример template policy](TEMPLATE-CONFIGURATION.md)
- [Offline kit](7f6ea1df/distribution/knowledge-harness-0.5.0rc1.zip)
- [Хеши исходников](7f6ea1df/source.json)

Candidate остаётся `0.5.0rc1`, release не опубликован, main не изменялся.
Существующие `knowledge-init`, `knowledge-candidates-update`,
`knowledge-candidates-push` сохранены. Worktrees, новая архитектура делегирования
и broad permissions не вводились.

## Матрица

Ссылки ниже относительно [каталога финального кода](7f6ea1df/).
Профильные **24/24 PASS** выполнены из offline установленного kit вне checkout.
Provider нормализации и UI в этих проверках — явно обозначенные doubles;
Python/Node процессы, SQLite commits, owned broker и Docker/Kafka — настоящие.

| ID | Статус | Тип, результат и свидетельство |
|---|---|---|
| A01 | PASS | Contract/process integration: неизвестная ранее формулировка без alias/«remember» проходит локальный model protocol, сохраняется до receipt с original/scope/ID/revision. `focused-tests.log`; настоящий OpenCode отдельно BLOCKED. |
| A02 | BLOCKED | Teaching process и endpoint завершаются; новые broker/CLI процессы применяют правило без transcript. Настоящий новый OpenCode session не проверен: executable отсутствует, `real-host.json`. Runnable driver — `scripts/validate_persistent_host.py`. |
| A03 | PASS | Real broker/Docker: другой проект применяет одну каноническую shared запись, включая параметризованный template. `scenarios/A03-cross-project/`, `scenarios/A03-template-cross-project/`. Нет копии записи в новом проекте. |
| A04 | PASS | Unit/process contract: project isolation, machine/OS/exact tool mismatch. `focused-tests.log`, `extra-validation.json`. Machine/OS/Python берутся из runtime; дополнительные tool tags — assertions владельца policy. |
| A05 | PASS | Real stopped Kafka fixture: ровно один owned start, ApiVersions/Metadata/controller и advertised endpoints проверены из среды теста, затем исходный integration test. `scenarios/A05-stopped/`, `scenarios/A16-resource-bound-fresh-process/`. |
| A06 | PASS | Real ready Kafka: повторный независимый процесс без start/restart. `scenarios/A06-ready/`. |
| A07 | PASS | Real Docker: отсутствующий resource, running-not-ready container; отдельно отсутствующий executable. Ограниченный отказ, ноль стартов. `scenarios/A07-*/`. Windows Docker и недоступный remote daemon не квалифицированы. |
| A08 | PASS | Real protocol/test integration: ready Kafka + application failure остаётся test failure без infrastructure recovery; unrelated suite не запускает остановленную Kafka. `scenarios/A08-*/`. |
| A09 | PASS | Real user ingress + отдельный broker: текущий запрет и current allowlist нельзя обойти remembered grant. `scenarios/A09-*/`. Contract проверяет trusted session ID, семантический deny/clear и сохранность durable default. |
| A10 | PASS | Unit/process: source retry, semantic dedup разных формулировок, CAS correction/history/retirement без cache. Смена ресурса не переносит startup grant. `focused-tests.log`. |
| A11 | PASS | Real recovery создаёт project `experience/candidate`, evidence refs, вмешательство, исход и uncertainty. Не повышается в обязательную причинную инструкцию. `scenarios/acceptance.json`, поле `candidates`. |
| A12 | PASS | Process/byte integration: UTF-8 BOM/CRLF/no-final-newline, UTF-16 BOM и mid-text U+FEFF. Явное текущее изменение на UTF-8/no-BOM/LF не переписывает default; новая сессия сохраняет исходный формат. Новый archive_guard обучен без изменения production code. `focused-tests.log`. |
| A13 | PASS | Temporary homes, 8 независимых CLI writers + 8 retries: без потери/дубликатов. Standalone Knowledge без Harness и старый reader 0.4.0rc3 сохраняют архитектуру и обе DB byte-for-byte. `extra-validation.json`, `compatibility.json`; native CI см. ниже. |
| A14 | PASS | Fault после реального INSERT до commit откатывает новую запись/history/receipt, сохраняет предыдущую запись; retry один раз. Corrupt retrieval блокирует действие без false no-match. Remote normalizer/неизвестная команда/придуманный ресурс не исполняются. `focused-tests.log`, `extra-validation.json`. |
| A15 | PASS | Unit/process: исключены unrelated shared records, проверен byte cap. Context содержит ID/revision/source hashes/inspect refs; canonical source в DB. Реальные traces дают bytes/time/applicability. `scenarios/acceptance.json`, `focused-tests.log`. |
| A16 | PASS | Real ingress/SQLite/Docker с model protocol double: исходный intent unbound, один вопрос о container/port; один ответ связывает тот же ID, rev2 без правки config/повторного обучения. Normalizer затем завершён, новый broker применяет процедуру. `scenarios/A16-resource-unbound/`, `scenarios/A16-resource-bound-fresh-process/`, `semantic_ingress` в acceptance.json. |

Невыразимое «только в maintenance window» сохраняется unbound и блокирует старый
широкий default до эффектов. Неясная scope вызывает один вопрос; ответ об общей
области сохраняет shared successor и audit прежней project записи. Подстановка
моделью усечённого container name или port не проходит проверку цитаты источника.

Матрица не означает универсальное исполнение произвольного языка. Модель выбирает
только owner-configured bindings/templates; команды материализует типизированный
код. Текущая policy независимо разрешает exact procedure/template, а для startup
нужно отдельное пользовательское разрешение. Проверены adapters check, dependency
и preserve-format. Native tools хоста вне Harness этим механизмом не управляются.
Режим `teaching_mode:catalog` — явный literal/alias режим для operator fixtures;
он не заменяет семантический разбор свободных формулировок. По умолчанию Harness
использует существующий loopback provider. Качество реальной модели не измерено.

## Свежий процесс и измерения

[Raw acceptance JSON](7f6ea1df/scenarios/acceptance.json) содержит ID/revision,
readiness command receipts, отдельный test result и полные lookup/recovery timings.
Для параметризованного пути: два user message, две нормализации protocol double,
одна запись `3d2f6023934e7261088646043106bedc57a02af99164e73c5645b0e70f1fb763`,
rev2. Исходное teaching сохранено; ответ добавил только точное имя fixture и port.
Настоящий контейнер имеет собственный label и удалён после проверки владения.

Один последовательный trial каждого сценария. Baseline/enabled начинают с
остановленного одинакового fixture; protocol integration test не меняется.

| Сценарий | Итог | Failed test attempts | Starts | Wall, s | Records / bytes |
|---|---|---:|---:|---:|---:|
| Baseline, memory disabled | test failure | 1 | 0 | 0.207 | 0 / 0 |
| Enabled, stopped Kafka | PASS | 0 | 1 | 4.058 | 1 / 1652 |
| Enabled, ready Kafka | PASS | 0 | 0 | 0.278 | 1 / 1652 |
| Другой проект | PASS | 0 | 0 | 0.321 | 1 / 1652 |
| Ready Kafka, application failure | test failure | 1 | 0 | 0.351 | 3 / 8362* |
| Unrelated suite, stopped Kafka | PASS | 0 | 0 | 0.177 | 0 / 2 |
| Binding supplied once, fresh process | PASS | 0 | 1 | 4.091 | 1 / 2126 |
| Template, другой проект | PASS | 0 | 0 | 0.332 | 1 / 2126 |

`*` Сумма before-action и targeted after-error lookup, включая candidate; каждый
lookup ограничен отдельно. `2` — bytes пустого массива. Неправильных remedies в
fixtures — 0. Это отдельные измеренные trial, не статистическое сравнение.
Real-model token usage/latency недоступны; выигрыша по скорости/токенам не заявлено.
Числа test-double token usage не считаются метриками модели.

## Совместимость и границы

Final kit установлен в `/tmp/persistent-semantic-runtime`, standalone — в
`/tmp/persistent-semantic-knowledge-only`. Drivers и результаты приложены.
Rollback reader 0.4.0rc3 читает прежние архитектурные данные; project/shared DB
не меняются, повторная установка нового reader возвращает доступ к инструкциям.
Реальные user stores не использовались. Корни только project `.knowledge` и
programmatic `Path.home()/.local/share/knowledge`; явный absolute override доступен.

Старые runners без `memory` сохраняют поведение. Включённый gateway закрыт при
retrieval failure. Нет модельного write MCP с authority user. Original source
не подменяется техническим доказательством; configured не означает verified.
Нормализация остаётся локальной, без proxy/redirect/remote provider. Credential-like
input не сохраняется и не отправляется normalizer; полные логи не копируются в shared.

Текущие запреты и format exceptions действуют в trusted host session; для CLI
они относятся к конкретному run. Явный reset/clear поддержан, новые host sessions
не наследуют временные исключения. Durable defaults не переписываются.

Откат: отключить plugin, вернуть прежний runner без ключа `memory`, заново enroll
проверенное задание, установить прежние wheels. Обе SQLite сохранить. Подробная
инструкция и runnable real-host trial — в docs/P4/PERSISTENT-INSTRUCTIONS.md.

## Полная квалификация

Для финального source запущены Linux installed route и native Windows CI
[44877877238](https://github.com/Ermak-P/Knowledge-/actions/runs/44877877238).
Окончательные receipts добавляются после проверки их commit/source identity и
хешей logs. До получения receipts текущий native результат не считается PASS.
Предыдущий `95828e84` прошёл PASS_PORTABLE/PASS_NATIVE в CI 44821592828; это
доказательство совместимости предшественника, а не квалификация нового source.
Сохранённый `e603c584` содержит известный Windows fixture failure: ожидание LF hash
при фактическом CRLF; исправлено в 95828e84 по persisted bytes.
