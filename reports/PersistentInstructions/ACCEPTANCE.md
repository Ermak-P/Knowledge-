# Persistent instructions — reviewed task

Вердикт: **IMPLEMENTED / HOST VALIDATION PENDING**.
Реальные OpenCode/local-model A01, A02, A05 и A17 не выполнены: хост отсутствует.
Изолированные PASS ниже не означают ACCEPTED. Это внешняя память, не обучение модели.

Актуальное R1: code fixes **IMPLEMENTED**, host validation **PENDING**.
Исходники [`287a6a8aa`](https://github.com/Ermak-P/Knowledge-/commit/287a6a8aa976b40a0117684a213ee46310df27bc).
[Отчёт R1, регрессии и новые exact-source receipts](R1-287a6a8a/REVIEW.md).
R1 исправляет передачу CLI resume controls и независимую проверку startup grants.

Ниже сохранён предыдущий review packet. Его результаты относятся к исходникам
`5dfc4c52` и не являются квалификацией нового R1 source; прежние failures сохранены.

Исходники: `5dfc4c523b1bc5cd5cf48b37f8366c6bb09cdb1d`, source identity
`1ea17652bc9f19353c7e5f706bb298cafdde866e1d1b57f2becaa7c417c3f572`.
Новая редакция задания: [Task-1](../../tasks/Knowledge-Harness-Persistent-Instructions-Codex-Task-1.md).

- [Ветка GitHub](https://github.com/Ermak-P/Knowledge-/tree/codex/persistent-instructions)
- [Изменения относительно main](https://github.com/Ermak-P/Knowledge-/compare/main...codex/persistent-instructions)
- [Аудит и карта возможностей](../../docs/P4/PERSISTENT-INSTRUCTIONS-AUDIT.md)
- [Установка, scopes, teaching, maintenance, coverage table и rollback](../../docs/P4/PERSISTENT-INSTRUCTIONS.md)
- [Гайд настоящего host trial](../../docs/P4/PERSISTENT-INSTRUCTIONS-LIVE-HOST.md)
- [Offline kit](5dfc4c52/distribution/knowledge-harness-0.5.0rc1.zip)
- [Хеши исходников](5dfc4c52/source.json)
- [Exact-source CI](https://github.com/Ermak-P/Knowledge-/actions/runs/44900474104)

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
operator rebind. CAS-перепривязка сохраняет ID, normalized intent, original и audit. Повторное
обучение после уточнения/коррекции сопоставляется по представленному поведению,
не по первоначальному способу формирования ID; новая duplicate не создаётся.
Unbound правило с известным trigger не активируется по случайному слову в тексте.
Startup grant для новой привязки задаётся явно; allowlist остаётся независимым.

Suite -> dependency -> shared procedure определяется существующим runner requirement.
У automatic tests optional `suite` выбирает проверенный inventory path и только test
phase. Нет новой discovery-системы, LLM на каждый tool call или recursive lookup.
Отсутствующий activation route, current tool denial и unsupported trigger отражаются
в receipt; сохранение intent не обещает исполнение неподдержанного действия.

## Матрица A01–A20

Все пути свидетельств ниже относительно [5dfc4c52](5dfc4c52/).
**38/38 профильных проверок PASS** из offline установленного runtime вне checkout.
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
| baseline-stopped-memory-disabled | test failure | 1 | 0 | 0.239 | 0 / 0 |
| A05-stopped | PASS | 0 | 1 | 5.909 | 1 / 2352 |
| A06-ready | PASS | 0 | 0 | 0.416 | 1 / 2352 |
| A08-application-failure | test failure | 1 | 0 | 0.460 | 3 / 9762 |
| A08-unrelated | PASS | 0 | 0 | 0.383 | 0 / 2 |
| A17-full-cli | PASS | 0 | 1 | 6.071 | 1 / 2777 |
| A19-resource-changed | docker-resource-changed | 0 | 0 | 0.776 | 3 / 10603 |
| A20-readiness-failed | dependency-readiness-timeout | 0 | 1 | 2.136 | 3 / 9642 |
| A20-fresh-no-replay | memory-remedy-blocked | 0 | 0 | 0.260 | 3 / 9642 |

Records/bytes — сумма across before-action/after-error lookups, не число уникальных
канонических записей. Каждый lookup имеет собственный byte/item cap. Raw receipts,
lookup/diagnosis/recovery timings, ID/revision и отдельный test result:
[acceptance.json](5dfc4c52/scenarios/acceptance.json).

Дополнительно actual SDK10/CLI/TRX: три теста из трёх обнаруженных проектов PASS,
новый guard сработал ровно один раз перед `integration/IpmAzureAutotests.csproj`,
ни перед restore/build, ни перед другими suites. Обычный task goal не содержит
memory rule/ID. [Результат](5dfc4c52/automatic-suite/result.json); provider — double.

Encoding comparison (actual fresh broker, normalizer protocol double): baseline
byte criterion = false, enabled = true. Wall 0.142/0.087 s,
selected 1 / 1463 bytes. [Raw bytes/result](5dfc4c52/encoding-comparison.json).

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

Для encoding trial предусмотрена [обёртка с временным профилем](5dfc4c52/real-host-isolated.py):
запускайте её Python из установленного runtime, передав `--model`, `--endpoint`
и `--output`, как в live-host гайде. HOME/USERPROFILE, XDG и AppData направлены
во временные каталоги; OpenCode config overrides очищены. Проверка этой обёртки
в данной среде также дала [BLOCKED](5dfc4c52/real-host-isolated.json), поскольку
исполняемый файл OpenCode отсутствует. Это не свидетельство успешного host trial.

## Квалификация пакета

Финальный пакет установлен вне checkout. 38 профильных tests, 18 Docker/CLI
scenarios, реальный automatic suite/SDK/TRX trial, standalone/rollback,
fault/concurrency и byte-level encoding comparison — PASS.
Локальная installed qualification: **PASS_PORTABLE**, все 22 команды, 287 tests
(276 PASS, 11 native-only SKIP, 0 FAIL/ERROR), source unchanged.
[Ledger/logs](5dfc4c52/local-qualified/). Финальный CI
[44900474104](https://github.com/Ermak-P/Knowledge-/actions/runs/44900474104) завершён:

| Платформа | Вердикт | Команды | Tests | PASS | SKIP | FAIL/ERROR |
|---|---|---:|---:|---:|---:|---:|
| Linux | PASS_PORTABLE | 22/22 | 287 | 276 | 11 native-only | 0 |
| Native Windows | PASS_NATIVE | 23/23 | 287 | 287 | 0 | 0 |

[Retained receipts и логи](5dfc4c52/ci/) прочитаны из Git evidence branch как данные;
код артефактов не исполнялся. [Проверка](5dfc4c52/ci/validation.json) подтверждает
exact code commit/source map, unchanged source, SHA-256 всех command logs и
совпадение каждого файла обоих CI kits с переданным offline kit.
Последующие commits отчёта не меняют product source identity, указанную выше.

Предыдущий `90d3db8a` прошёл локальный route, но CI обнаружил выбор candidate по
позиции списка и одинаковые wall-clock timestamps у attempted/verified на Windows.
Исправления выбирают ID и transactionally выделенный revision-scoped sequence;
regression проверяет одинаковые и обратные часы. [Failed receipts/logs](90d3db8a/ci-failed/).
Финальная версия также устраняет ложное срабатывание known unbound trigger на
слово «test» и duplicate после уточнения/изменения binding. Пользовательский intent,
ID и audit остаются; технические сигналы не становятся новой пользовательской волей.

Предшественники 90d3db8a/80ed3a3e/7f6ea1df/95828e84/e603c584 не квалифицируют
новый source. ACCEPTED не заявляется до реального host trial.
