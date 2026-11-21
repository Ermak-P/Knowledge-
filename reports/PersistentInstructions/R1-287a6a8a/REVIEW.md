# Persistent Instructions R1 — исправления review

Code fixes: **IMPLEMENTED**. Host validation: **PENDING**.
Общий вердикт: **IMPLEMENTED / HOST VALIDATION PENDING**, не ACCEPTED.

Исходники: [`287a6a8aa976b40a0117684a213ee46310df27bc`](https://github.com/Ermak-P/Knowledge-/commit/287a6a8aa976b40a0117684a213ee46310df27bc).
Source identity: `b31ef8805fc704c5f3d2d4e035f3958e2e80963ee5e93f2d4df6a9cafbad58c9`.
[Карта файлов](source.json), [задание](../../../tasks/Knowledge-Harness-Persistent-Instructions-R1-Fixes-Codex-Task.md).
Report-only commits не меняют этот product source. Ветка остаётся
`codex/persistent-instructions`; merge/release не выполнялись.

| Item | Результат и свидетельство |
|---|---|
| R1-01 | CLI передаёт no-start и format-input в настоящий resume. Под execution lease запреты объединяются с сохранёнными и commit выполняется до broker/provider continuation. Обычный resume и пустой список API не снимают запрет. Saved startup grant остаётся в memory, но affected action получает `current-service-start-denied`; **0 startup calls** в Docker command double. Format override до intent даёт точные UTF-8/no-BOM/LF bytes без новой revision default. После intent и после первой записи несовместимый override даёт `resume-format-conflicts-with-edit-intent`, без новых writes/provider calls; последующий обычный resume завершает тот же run. Другие command paths отклоняют controls. [Регрессии](focused-tests.log). |
| R1-02 | Неверные schema-valid model responses больше не превращают denial, quotation/example, прошлый успех, чужой ресурс, неподдержанное условие и revoked/original quote в новый grant. Actual ingress, SQLite commit и command/broker contract. Exact review probe: [до](denial-before.json) — persisted grant=true, 1 startup call; [после](denial-after.json) — false, **0 startup calls**. Это model/Docker doubles, не реальные Docker effects. Readiness остаётся доступной; положительные EN/RU grants, `start if stopped; never restart` и fresh-process persistence проходят. [Probe](denial-probe.py), [тесты](focused-tests.log). |
| R1-03 | [Discovery](host-discovery.json): OpenCode и Ollama не найдены; на 127.0.0.1:11434/1234/8080/8000 нет listeners. [Изолированный driver](host-validation.json) вернул BLOCKED до host session. Host version отсутствует; actual model/version неизвестны (`unavailable-local-model` — явный placeholder, не реальная модель). Session IDs и live record IDs/revisions отсутствуют, live A01/A02/A05/A17 **NOT RUN/BLOCKED**. Guide исправлен: plugin/provider/host settings до preview/apply. Driver проверяет enrollment до/после. Published plugin 1.19.6 и companion v2 MCP layout остаются отдельными предположениями; actual combination не подтверждена. |
| Regression | Из нового offline kit, вне checkout: **50/50 test_persistent*.py PASS**, включая 12 новых R1 tests с subcases. **18/18** isolated Docker/CLI сценариев пройдены с отдельными ожидаемыми негативными исходами. [Offline install](install.log), [пакет и проверка source](package-validation.json), [scenarios](scenarios/acceptance.json). Full Linux/native Windows qualification — отдельная секция ниже. |
| Coverage | Enrolled `harness_run`, CLI run/resume, existing Harness roles и automatic test operations используют тот же broker. Read-only MCP не запускает процедуры. Native host shell/edit и внешние процессы остаются bypass paths; их права не расширялись. Shared/project stores, lifecycle/provenance и guards сохранены. |

## Reproduction и различие уровней

[Новые регрессии на прежнем установленном runtime](before-focused.log): 12 tests,
25 failed subcases/assertions и 1 error — ожидаемый отрицательный результат.
Это исходники `5dfc4c52`, квалифицированные на reviewed HEAD `1cf9619f`.
[Baseline package validation](baseline-source-validation.json) сверяет каждый Python
source asset обоих установленных packages с Git blobs reviewed product source
(документированная LF-нормализация builder). Старые passing receipts не выдаются
за квалификацию нового кода. Новые тесты лежат в `tests/test_persistent_r1.py`.
Первый development run нового кода также обнаружил ошибку fixture: control JSON
добавлялся в source tree после snapshot и корректно срабатывал source-conflict.
Fixture теперь держит этот input в `.harness`; source guard не ослаблен.

Основная команда (из Python, установленного offline kit; cwd вне checkout):

```text
python -m unittest discover -s <repo>/tests -p "test_persistent*.py" -v
python -I <repo>/scripts/persistent_instructions_scenarios.py --output <new-dir>
```

Full source-bound route, одинаковый с CI:

```text
<repo>/.venv/bin/python <repo>/scripts/verify_p4.py
```

Native Windows route: `scripts/verify-p4-windows.ps1`; workflow
[44905870792](https://github.com/Ermak-P/Knowledge-/actions/runs/44905870792).

Модельные решения — намеренно неверные HTTP protocol doubles. R1 startup эффект
считает DockerContract; он не исполняет Docker. Иные 18 сценариев действительно
исполняют Docker/Kafka и broker subprocesses, создают/удаляют только owned fixtures.
SDK/TRX и process/storage проверки в полной квалификации являются настоящими;
provider decisions остаются doubles. Ни один из этих уровней не заменяет OpenCode.

## Граница разрешений

Механически проверяется `startup-en-ru-v1`: полная текущая фраза положительного
разрешения + selected exact resource; явное startup denial сильнее model boolean.
Цитата из original/history не является новым разрешением. Deictic `it/этого
контейнера` допустим только с одной Docker/template привязкой; имя должно
совпасть точно, включая регистр. Проверка состояния, immutable resource/daemon,
current no-start и independent allowlist остаются отдельными execution guards.

[Полный контракт EN/RU](../../../docs/P4/PERSISTENT-INSTRUCTIONS.md) перечисляет
формы, отрицания, контекстные markers и ограничения. Неподдержанный язык не даёт
нового grant; intent/readiness сохраняются, вопрос касается только необходимого
разрешения. Grammar не доказывает понимание произвольного естественного языка;
общая классификация intent/scope/семантики по-прежнему зависит от локальной модели.
Trusted operator CLI и явный catalog fixture mode не являются model write tools.
Существующие записи не мигрируются и старые grants массово не переписываются.

## Полная квалификация

Локальный installed route: **PASS_PORTABLE**, 22/22 commands, 299 tests —
288 PASS, 11 native-only SKIP, 0 FAIL/ERROR. Source unchanged=true.
[Ledger и raw command logs](local-qualified/) проверены по source map/commit и
SHA-256 каждого лога. Финальный CI завершён на том же product source:

| Платформа | Qualification | Commands | Tests | PASS | SKIP | FAIL/ERROR |
|---|---|---:|---:|---:|---:|---:|
| Linux | PASS_PORTABLE | 22/22 | 299 | 288 | 11 native-only | 0 |
| Native Windows | PASS_NATIVE | 23/23 | 299 | 299 | 0 | 0 |

[Retained receipts, test ledger и command logs](ci/),
[результат независимой сверки](ci/validation.json).
Данные прочитаны из Git evidence branch `96e7821bb4595bc09f8c967117abeb53dcdac5e9`;
код артефактов не исполнялся. Exact commit/source map, source unchanged,
SHA-256 каждого command log и всех файлов обоих CI kits сверены с переданным
local offline kit. Native Windows результаты квалифицируют этот R1 source,
но не являются real OpenCode/local-model или Windows Docker trial.

## Что требуется на пользовательском хосте

[Исправленный live guide](../../../docs/P4/PERSISTENT-INSTRUCTIONS-LIVE-HOST.md)
и `scripts/validate_persistent_host_isolated.py` готовы к запуску с существующим
OpenCode и loopback model. Временные HOME/XDG/AppData и memory roots отделены от
реальных stores. Kafka trial требует owned stopped fixture, обычный fresh-session
запрос тестов без Kafka/memory reminder, matched ID/revision, один разрешённый start,
protocol readiness и отдельный исход исходных tests; затем ready/unrelated/no-start/
running-unhealthy negatives. Docker daemon/Desktop автоматически не запускается.
До этих реальных свидетельств общий вердикт остаётся HOST VALIDATION PENDING.
