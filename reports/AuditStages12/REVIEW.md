# Этапы аудита 1–2: пакет для независимого ревью

Вердикт: **этапы 1–2 готовы к независимому ревью; установленная поставка прошла
portable/native qualification; проверка настоящего host/модели остаётся отдельным этапом**. Выполнены AUD-01/02/03/04/05/07/09. Merge, deployment и rollout
не выполнялись. Все проекты/SQLite/shared roots и process fixtures принадлежат
испытаниям; пользовательские базы, Docker daemon и контейнеры не затрагивались.

## Что проверять

- [ACCEPTANCE.json](ACCEPTANCE.json): все 24 строки S1-01…08, S2-01…12, C-01…04;
  конкретные test IDs, installed/native/real-host статусы и ссылки на evidence.
- [Контракты продукта](../../docs/P4/AUDIT-STAGES-1-2.md): поля, совместимость,
  таблица degraded behavior, порядок переноса и recovery/rollback.
- [source.json](source.json): полный source map, не только номер версии.
- [local/run.json](local/run.json), [local/tests.json](local/tests.json) и
  [ci/validation.json](ci/validation.json): реальные qualification ledgers.
- [Поставка](distribution/knowledge-harness-0.5.0rc1.zip) и
  [package.json](distribution/package.json): текущий kit, SHA-256 и wheel hashes.

## Код и исправленное поведение

Baseline: `152e372eafac74c39236a3f6b0e55808769d910e`, main, product `0.5.0rc1`.
Работа in-place, без worktrees и сбросов. Стартовое дерево чистое, применимых
AGENTS.md не найдено; Linux uid=1000. [Исходная среда](environment.json).

Stage 1: `70ce9af6f` — сначала baseline failures, затем исправления и 9 focused /
55 прежних persistent tests PASS. Stage 2: `5e53ff4f1`; P0-граница: `3e35f966b`; native handle/ACL fixes и итоговый product source:
`74b2dee16aaf8fd0dfe25854fae47d8bf8bcf016`. Отчётные коммиты после него меняют только reports.

P0 regression: [до](stage2/legacy-unverified-before.json) → [после](stage2/legacy-unverified-after.json). P4 withholding не меняет чтение legacy core/task-v1 или SQLite; 20 stage-2 tests включают эту границу. Промежуточный неизменный source 5e53ff4f1 прошёл 23-command qualification; его ledger сохранён в stage2/interim-qualified и не подменяет final source ниже.

Source identity: `49e8be70d9398daea601520d5f8e7dfcced4c7e64c9f2cd48938e30ffd8a3e27`.
Ветка: [codex/audit-stages-1-2](https://github.com/Ermak-P/Knowledge-/tree/codex/audit-stages-1-2).
CI: [run 44984028401](https://github.com/Ermak-P/Knowledge-/actions/runs/44984028401).

| ID | Исправление и доказательство |
|---|---|
| AUD-01 | Enumeration/read/disappearance учитываются в identity и gaps; неизвестная область блокирует отрицательное доказательство. Harness/maintenance отказывают в полном identity. Настоящий Linux chmod refusal, восстановленный в finally; fault/resume и native ACL проверяются тем же тестом. |
| AUD-02 | Catalog и semantic/CLI/host/fallback/replay используют полный источник и единый startup-en-ru-v1. Denial и неизвестные ограничители сильнее положительной цитаты; quoted/past/resource mismatch/allowlists сохранены. Положительный stopped path — один start на Docker boundary double, ready — ноль, running не restart. |
| AUD-03 | Durable sealed transfer intent в существующей project SQLite: prepared → target-saved → source-retired → completed либо CAS conflict. Related lookup явно pending; replay/recover без модели. Обе стороны, active/unbound, faults и concurrent correction; история/predecessor/successor сохранены. |
| AUD-04 | Ограниченный ordered source envelope; chat/read доступны с причиной degraded, controls сохраняются, patch/recipe/start при неопределённости заблокированы. Late/replayed source не снимает более новый запрет. Sensitive raw text не сохраняется. Реальный Node hook и fresh-process recovery проверены. |
| AUD-05 | Автоматический bounded slice для первого Main, новых Coding items/repair, diagnosis Planning и final Reviewing. Durable delivery/request hashes, ID/revision, binding/cache/invalidation. Installed behavior + disabled control + независимый Reviewer/oracle; provider не вызывает knowledge и не читает Store/evaluator. |
| AUD-07 | depends_on IDs, bounded closure depth=4/ref=128; все возвращённые parents входят в item/byte budgets. Недоставленные причины и partial явны, confidence/provenance/conflicts сохранены. |
| AUD-09 | Отдельные absent/no-match/status/lifecycle/freshness/scope/dependency/budget/corruption состояния. Bounded query-related diagnostics не включают stale statement в trusted claims. Core/CLI/MCP/P4, фактические UTF-8 caps и TextContent без structured duplication проверены. |

Границы: узкая EN/RU грамматика не понимает произвольный язык; два SQLite commit
не объявлены атомарными. Новая coordinator DB/сервер/permissions не добавлены.
Факты не меняют authority или grants. Pending/conflict требует recovery/операторского
разбора. Гарантии broker не распространяются на произвольный native shell/edit
хоста. Retrieval не устанавливает истинность автоматически. Экономия токенов и
качество живой модели не заявляются.

## Воспроизведения и установленные сценарии

[stage1/baseline-installed-source.json](stage1/baseline-installed-source.json)
сопоставляет все 44 установленных Python source файла старого runtime с baseline.
[baseline-failed.log](stage1/baseline-failed.log): 4 reproducer tests, 8 ожидаемых
subtest failures. Там видны реально переданные start calls при EN/RU запрете и
два конкурирующих record после прерванного transfer/replay.

[permission-before.json](stage1/permission-before.json) →
[permission-after.json](stage1/permission-after.json): обычный uid=1000 действительно
получает PermissionError. Старая версия: complete=true, gaps=[], retire живого
класса. Новая: complete=false, явный gap, proposal=null. После finally файл жив.
[stage1/focused-pass.log](stage1/focused-pass.log) проверяет восстановление доступа,
chunk/resume, snapshots и 32 сочетания transfer faults/directions/bound state.

[Installed trial](installed-trial/result.json): setup/teaching завершены до нового
run process; только автоматически доставленный claim `policy.price.threshold`,
revision 1, сообщает необходимую величину 37. Goal/acceptance не содержат ни её,
ни claim ID. Controlled HTTP provider принимает её из обычного system.knowledge,
меняет Feature.py; реальные build/test subprocess и отдельный oracle получают 37.
Без доставки тот же provider завершает run отказом, source остаётся 0, oracle FAIL
ожидаем и является успешным отрицательным контролем. Coding summary намеренно
утверждает 999; final Reviewer использует собственный canonical slice 37.
Сохранены полные provider requests, journal input hashes, selected revisions и
результат. Knowledge DB не меняется в run. Это механическое доказательство
доставки на controlled provider, **не live-model trial**.

[standalone/result.json](standalone/result.json): профиль Knowledge установлен вне
checkout без Harness/MCP. База создана предыдущей версией: revision 2, две receipts,
история, импортированные и pending queue entries, PREPARED plan. Export/status и
SHA-256 SQLite совпадают до/после чтения новой версией; миграции для чтения нет.
[stage2/diagnostics/result.json](stage2/diagnostics/result.json) отдельно проверяет
реальные refusal/deletion и unverifiable/no-match. [large-graph.json](stage2/large-graph.json)
проверяет 131 claim/130 edges: 100 returned, 128 refs, 2 omitted; CLI caps
256/400/1000/32000 соблюдены, после trimming counters совпадают с payload.
[timeout.json](stage2/timeout.json): настоящий HTTP deadline около 1 секунды,
сохранён no-start, explicit degraded, эффект blocked. UI в Node fixture — stub.

## Qualification и отказы

| Профиль | Итог | PASS / SKIP tests | Команд |
|---|---|---|---|
| Local Linux | PASS_PORTABLE | 322 / 11 | 23 |
| CI Linux | PASS_PORTABLE | 322 / 11 | 23 |
| Native Windows | PASS_NATIVE | 333 / 0 | 24 |

Локально всего 333 tests: 322 PASS, 0 FAIL,
0 ERROR, 11 native-only SKIP. Ни один прежний тест не
удалён/ослаблен. Полный route включает install из transferred kit, regressions,
старые upgrades/lifecycle, automatic .NET tests/actual TRX, benchmark/application,
новый delivery trial, Knowledge-only, doctor/uninstall/reinstall. Все исходные
command logs и их SHA-256 сохранены; CI source map и весь kit content map
проверяются как данные collector-ом, код из artifacts не исполняется.

Ранние ожидаемые stage-2 failures сохранены в
[baseline-failed.log](stage2/baseline-failed.log). Первый общий прогон до исправления
совместимости: 327 tests, 3 FAIL, 11 SKIP; лог
[interim-full-failed.log](stage2/interim-full-failed.log) оставлен без переписывания.
Это старый read-only facade (две проверки) и восстановление unbound intent без
host pending pointer. [INTERIM.md](stage2/INTERIM.md) объясняет исправления; финальный
333-test installed route проверяет их вместе со всем набором. Промежуточный
stage-1 CI не используется для квалификации final source: literal allowlist его
receipt publisher дополнен этой веткой в итоговом коммите.

Native попытка на `5e53ff4f1`: 325 PASS / 7 ERROR / 0 SKIP из 332.
[interim-native-failed](stage2/interim-native-failed/run.json) и raw regressions.log
сохранены. Шесть ошибок — незакрытые SQLite read connections в новом P4 cache
(WinError 32 при удалении fixture); одна — ACL-test finally после запрета READ_CONTROL.
Итоговый source явно закрывает connection через closing; тест запрещает только
реальное перечисление каталога `(RD)`, сохраняя права для finally. Assertion настоящего
PermissionError, проверка gaps/no retirement и восстановления остались обязательными.
Дополнительный installed before/after probe [read-handles](stage2/read-handles/after.json) при отключённом на время измерения GC: 100 обращений давали +100 файловых дескрипторов до исправления и +0 после; оба runtime установлены из соответствующих kit.
29 focused tests после исправления — [native-fix-focused-pass.log](stage2/native-fix-focused-pass.log).
Локальный source 3e35 уже выполнил 333 tests без failures, но его полный route
прерван после обнаружения native defects для замены source; FAILED/KeyboardInterrupt
ledger сохранён в [superseded-3e35](stage2/superseded-3e35/run.json), не выдан за PASS.
Попытка CI на source 3e35 тоже сохранена: [interim-native-3e35](stage2/interim-native-3e35/run.json), 325 PASS / 8 ERROR из 333 (та же ACL/handle причина; конкретные cleanup failures зависят от GC). Все команды финального source повторены в ledgers выше.

Исторический SocketException/MSB4216 из задания не считается результатом нового
source. Фактические build/test/qualification результаты — только ledgers выше.
OpenCode executable отсутствует: [host-validation.json](host-validation.json)
содержит честный BLOCKED; никаких host-сеансов не симулировалось.

## Поставка и повторение

Kit SHA-256: `80ad248a15c8850616deca4b562b0ff08cf6fae22251c021b27ffba1c47f4cb5`.
Knowledge wheel: `c3344645a084e552e6269465a3d024afb26dda3eba2f21d627ff337d2a58636b`.
Harness wheel: `0a0688b6b3402ea056a3309dc2baa646333115f2352ab999602ebd74d59dfb15`.
Версия 0.5.0rc1 сохранена; использовать именно source identity и hashes выше.

```text
python scripts/setup_p3.py
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B scripts/verify_p4.py
# Native Windows / PowerShell 5.1:
powershell -NoProfile -File scripts/verify-p4-windows.ps1
# Установленный runtime, новый каталог evidence:
python -I scripts/audit_stages12_trial.py --output NEW_OUTPUT_DIRECTORY
# Реальный host, когда уже установлены совместимые OpenCode и локальная модель:
python -I scripts/validate_persistent_host_isolated.py --model EXISTING_LOCAL_MODEL --endpoint http://127.0.0.1:11434/v1/chat/completions --output NEW_HOST_OUTPUT
```

Точный rollback и фазы recovery описаны в
[AUDIT-STAGES-1-2.md](../../docs/P4/AUDIT-STAGES-1-2.md). Перед rollout: остановить
новые effects, сделать matching backup project/shared SQLite и Harness journal/
sessions, проверить kit hash, install и doctor. Rollback — прежний kit с matching
backup; нельзя продолжать новые pending state старым кодом или повторять неизвестные
process outcomes. Никакой rollout этим заданием не выполнялся.

Остаётся отдельная реальная OpenCode/model приёмка и пользовательский пилот.
Настоящие Kafka/host grants и произвольные native tools не считаются проверенными
по Docker/model doubles. Продукт и воспроизводимые drivers готовы к этому этапу.
