# Persistent instructions — reviewed task

Вердикт: **IMPLEMENTED / HOST VALIDATION PENDING**.
Реальные OpenCode/local-model A01, A02, A05 и A17 не выполнены: хост отсутствует.
Изолированные PASS ниже не означают ACCEPTED. Это внешняя память, не обучение модели.

Исходники: `90d3db8ad4ab1ac1b3fc8a97ba429e1581835c80`, source identity
`2a0f12a455650d25fa0328889d6527962bdb43e7c8819671662264b4c4e97b7e`.
Новая редакция задания: [Task-1](../../tasks/Knowledge-Harness-Persistent-Instructions-Codex-Task-1.md).

- [Ветка GitHub](https://github.com/Ermak-P/Knowledge-/tree/codex/persistent-instructions)
- [Изменения относительно main](https://github.com/Ermak-P/Knowledge-/compare/main...codex/persistent-instructions)
- [Аудит и карта возможностей](../../docs/P4/PERSISTENT-INSTRUCTIONS-AUDIT.md)
- [Установка, scopes, teaching, maintenance, coverage table и rollback](../../docs/P4/PERSISTENT-INSTRUCTIONS.md)
- [Гайд настоящего host trial](../../docs/P4/PERSISTENT-INSTRUCTIONS-LIVE-HOST.md)
- [Offline kit](90d3db8a/distribution/knowledge-harness-0.5.0rc1.zip)
- [Хеши исходников](90d3db8a/source.json)
- [Exact-source CI](https://github.com/Ermak-P/Knowledge-/actions/runs/44896791625)

## Реализованное поведение

Сохранены две SQLite, самостоятельность Knowledge и существующие lifecycle/claims
контракты. Shared teaching не требует `.knowledge` проекта; absent store нормален,
corrupt/unreadable existing store означает отказ. Сохранение подтверждается после
commit и проверки; original wording/history остаются независимо от binding state.

Новая installation binding отдельно фиксирует execution machine/context, Docker
context и хеши известных inputs. Изменение блокирует затронутую процедуру. При
recovery фиксируются daemon и immutable container ID: прежнее имя не разрешает
старт другого объекта. Compose требует project name/directory и явный env-file.
Docker daemon/Desktop автоматически не запускаются; remote Docker вне покрытия.

Attempted/blocked/verified сигналы привязаны к revision и не заменяют пользовательский
intent. Неудача/неизвестный исход startup не повторяется при каждом новом run:
допускается безопасный readiness recheck, затем явный blocked до исправления или
operator rebind. CAS-перепривязка сохраняет ID, normalized intent, original и audit.
Startup grant для новой привязки задаётся явно; allowlist остаётся независимым.

Suite -> dependency -> shared procedure определяется существующим runner requirement.
У automatic tests optional `suite` выбирает проверенный inventory path и только test
phase. Нет новой discovery-системы, LLM на каждый tool call или recursive lookup.
Отсутствующий activation route, current tool denial и unsupported trigger отражаются
в receipt; сохранение intent не обещает исполнение неподдержанного действия.

## Матрица A01–A20

Все пути свидетельств ниже относительно [90d3db8a](90d3db8a/).
**35/35 профильных проверок PASS** из offline установленного runtime вне checkout.
UI/model/provider doubles явно отделены от реальных Python/Node процессов,
SQLite transactions, broker/supervisor, Docker/Kafka и .NET SDK/TRX.

| ID | Статус требования | Уровень и свидетельство |
|---|---|---|
| A01 | BLOCKED: real host | PASS contract/process: genuine user ingress, unseen wording, source/scope/ID/revision и durable receipt. `focused-tests.log`, `scenarios/host-contract.log`. Реальная модель/хост не проверены. |
| A02 | BLOCKED: real host | PASS independent installed ingress/broker/CLI processes без transcript/reminder; model endpoint завершается. `focused-tests.log`. Реальный encoding host driver: `real-host.json`, BLOCKED. |
| A03 | PASS | Real broker/Docker: shared canonical record работает в другом fixture проекте без project init/копирования. `scenarios/A03-*/`. |
| A04 | PASS | Unit/process: project isolation, machine/OS/tool mismatch, execution context mismatch до любого процесса. `focused-tests.log`, `extra-validation.json`. |
| A05 | BLOCKED: real host | PASS real stopped Kafka fixture: один start, protocol readiness и отдельный исходный test result. `scenarios/A05-stopped/`, `A16-resource-bound-fresh-process/`. Настоящий OpenCode не участвовал. |
| A06 | PASS | Real ready Kafka, новый процесс, ноль start/restart. `scenarios/A06-ready/`. |
| A07 | PASS | Real owned resources: missing/unhealthy; отдельно unavailable executable/non-executable binding. Concrete bounded errors, ноль стартов. `scenarios/A07-*/`. Remote daemon и Windows Docker не квалифицированы. |
| A08 | PASS | Ready Kafka + application failure остаётся test failure без инфраструктурного remedy. Unrelated suite не запускает остановленную Kafka. `scenarios/A08-*/`. |
| A09 | PASS | Actual ingress/broker/Docker: текущий no-start и пустой allowlist сильнее memory. Hook contract подставляет trusted session. `scenarios/A09-*/`, `focused-tests.log`. |
| A10 | PASS | Unit/process: source/hash replay, recovery потерянного pending pointer, semantic dedup, CAS correction, retirement/history. `focused-tests.log`. |
| A11 | PASS | Real recovery пишет project candidate с evidence/uncertainty, не causal/mandatory rule. `scenarios/acceptance.json`, поле candidates. |
| A12 | PASS: component fresh session | Byte-exact UTF-8 BOM/no-BOM и UTF-16, non-ASCII/untouched content, EOL/final newline, current format exception без смены default. Новый guard без production branch, отдельный CLI/SDK trial. `focused-tests.log`, `automatic-suite/`. Настоящий host encoding trial BLOCKED. |
| A13 | PASS: isolated storage/process | Temporary roots; 8 parallel CLI writers + 8 replays, без потери/дубликатов. Standalone без Harness и rollback reader 0.4.0rc3 сохраняют архитектуру/обе DB byte-for-byte. `extra-validation.json`, `compatibility.json`. Native qualification отдельно ниже. |
| A14 | PASS | Fault после INSERT до commit откатывает record/history/receipt и сохраняет предыдущий commit; corrupt retrieval не становится no-match. Недоступная/изменённая binding отражена как non-executable. `focused-tests.log`, `extra-validation.json`. |
| A15 | PASS | Unrelated records исключены, overflow явный, без top-k потери обязательных правил; IDs/revs/source refs/bytes/time доступны в traces. `focused-tests.log`, `scenarios/acceptance.json`. |
| A16 | PASS | Real ingress/SQLite/Docker + local-model protocol double: unbound intent, один ответ container/port, тот же ID/rev2, новый процесс без normalization endpoint. `scenarios/A16-*/`. |
| A17 | BLOCKED: real host | PASS full ordinary-goal CLI/role/broker/Docker path с model double, без Kafka/memory reminder. PASS actual SDK: 3 discovered projects, guard только у declared suite. `scenarios/A17-full-cli/`, `automatic-suite/`. OpenCode fresh session не проверен. |
| A18 | PASS: contract/process | Негативные условия/unsupported guard сохраняются; unresolved conflict блокирует affected action; current format/no-start не переписывает default. Реальный running-not-ready fixture не restart. `focused-tests.log`, `scenarios/A07-unhealthy/`. |
| A19 | PASS | Shared без project init, corruption отдельно. Actual same-name replacement даёт docker-resource-changed до start; unit daemon/context/Compose input changes. `scenarios/A19-resource-changed/`, `focused-tests.log`. |
| A20 | PASS | Actual failed readiness/start attempt, затем fresh no-replay; intent active, binding blocked. Full CLI private checks без recursive lookup. Known bypasses в coverage table. `scenarios/A20-*/`, `scenarios/A17-full-cli/`, docs. |

## Измерения

Один trial каждого сценария; baseline/enabled сброшены к одному owned stopped
fixture. Model token usage/real-model latency недоступны; synthetic usage не
считается метрикой модели. Выигрыш по скорости/токенам не установлен.

| Сценарий | Исход | Failed test attempts | Starts | Wall, s | Records / bytes |
|---|---|---:|---:|---:|---:|
| baseline-stopped-memory-disabled | test failure | 1 | 0 | 0.204 | 0 / 0 |
| A05-stopped | PASS | 0 | 1 | 4.104 | 1 / 2350 |
| A06-ready | PASS | 0 | 0 | 0.391 | 1 / 2350 |
| A08-application-failure | test failure | 1 | 0 | 0.339 | 3 / 9760 |
| A08-unrelated | PASS | 0 | 0 | 0.163 | 0 / 2 |
| A17-full-cli | PASS | 0 | 1 | 5.024 | 1 / 2776 |
| A19-resource-changed | docker-resource-changed | 0 | 0 | 0.579 | 3 / 10599 |
| A20-readiness-failed | dependency-readiness-timeout | 0 | 1 | 1.779 | 3 / 9642 |
| A20-fresh-no-replay | memory-remedy-blocked | 0 | 0 | 0.262 | 3 / 9642 |

Records/bytes — сумма across before-action/after-error lookups, не число уникальных
канонических записей. Каждый lookup имеет собственный byte/item cap. Raw receipts,
lookup/diagnosis/recovery timings, ID/revision и отдельный test result:
[acceptance.json](90d3db8a/scenarios/acceptance.json).

Дополнительно actual SDK10/CLI/TRX: три теста из трёх обнаруженных проектов PASS,
новый guard сработал ровно один раз перед `integration/IpmAzureAutotests.csproj`,
ни перед restore/build, ни перед другими suites. Обычный task goal не содержит
memory rule/ID. [Результат](90d3db8a/automatic-suite/result.json); provider — double.

## Границы и воспроизведение

[Coverage table](../../docs/P4/PERSISTENT-INSTRUCTIONS.md) сопоставляет genuine
chat.message, enrolled harness_run, CLI run/resume, automatic tests и existing
roles с Broker preflight. Read-only MCP не запускает процедуры. Native host
shell/edit и внешние оркестраторы не покрываются этим enforcement.

Только project `.knowledge` и programmatic Path.home()/.local/share/knowledge;
explicit absolute shared-root override имеет документированный приоритет.
Binding fingerprints/сигналы живут в той же SQLite, третьей machine DB нет.
Секреты не копируются в shared; Docker context metadata сохраняет выбранную
идентичность без auth/credential payload. Исходники и логи проекта туда не inject.

Operator maintenance: inspect/history/retire, memory-teach correction и
memory-rebind с expected revision. Ни одна дата проверки сама не удаляет intent.
Новая binding требует текущего allowlist и явного startup grant; rebind default
его не переносит автоматически. При rollback отключите plugin, верните runner
без ключа memory, reenroll task и установите старые wheels, сохранив обе SQLite.

Полный live-host driver использует обычный запрос на правку/checks без memory/tool
reminder; Kafka trial описан в отдельном гайде. До реальных A01/A02/A05/A17 и
применимых negatives итог остаётся IMPLEMENTED / HOST VALIDATION PENDING.

## Квалификация пакета

Пакет установлен вне checkout; профильные 35 tests, 18 Docker/CLI scenarios,
standalone/rollback и fault/concurrency checks PASS. Локальный полный regression
набор: 284 tests, 273 PASS, 11 native-only SKIP, 0 FAIL/ERROR. Остальная installed
qualification выполняется. CI 44896791625: Linux job завершился ошибкой, причина
ожидает retained log; Windows job ещё выполняется. Это не текущий PASS_NATIVE.
Каталоги предшественников 7f6ea1df/95828e84/e603c584 не квалифицируют новый source.
