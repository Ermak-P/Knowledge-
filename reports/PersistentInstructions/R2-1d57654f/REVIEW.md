# R2 — сохранение запретов при разборе

**R2 parser fix: IMPLEMENTED. Real-host validation: PENDING.**
Общий вердикт: **IMPLEMENTED / HOST VALIDATION PENDING**, не ACCEPTED.

Product source: [`1d57654f385594bbab03178ecc510cace534c51b`](https://github.com/Ermak-P/Knowledge-/commit/1d57654f385594bbab03178ecc510cace534c51b).
Source identity: `44a3e2effad2e9607922375d689502904540a59d259a115dac165d4cb4f3952b`.
[Source map](source.json), [задание](../../../tasks/Knowledge-Harness-Persistent-Instructions-R2-Denial-Preservation-Codex-Task.md).
Report-only commits не меняют product source. Работа выполнена в исходной ветке
`codex/persistent-instructions`, без worktrees, merge или release publication.

## До и после

Сначала добавлены пять R2 tests с EN/RU subcases. На reviewed R1 runtime:
**5 tests, 9 failures**, ожидаемый отрицательный результат — [лог](before-tests.log).
[Проверка baseline](baseline-source-validation.json) сверяет все Python assets
обоих установленных packages с R1 product commit `287a6a8aa` (reviewed HEAD
`a19346331`), с LF-нормализацией builder. Старые R1 receipts не квалифицируют R2.

Намеренно ошибочная schema-valid модель предложила affirmative quote и clear-denial:

| Genuine source | R1 persisted grant / startup calls | R2 persisted grant / startup calls |
|---|---|---|
| `Remember you may not start the container: You may start it.` | true / 1 | **false / 0** |
| `Запомни не запускай контейнер: Разрешаю запуск этого контейнера.` | true / 1 | **false / 0** |

[До](before.json), [после](after.json), [probe](probe.py). Ingress и временные SQLite
настоящие; local normalizer и Docker command boundary — **doubles**. Реальных
Docker effects нет. Original сохранён дословно в обоих вариантах; дефект был в
потере запрета внутри parser view, а не в отсутствии исходного текста в SQLite.
После fix prohibition виден direct deny checks и host session no-start; conflicting
clear proposal его не снимает. Readiness check разрешён без startup.

## Исправление и границы

`clauses()` больше не удаляет teaching prose. Startup и restriction сначала
проверяют отрицания в этом полном представлении. Затем `permission_clauses()`
может убрать только валидированный topic/scope header. Topic — literal catalog
alias из одного word-token; scope — конечная EN/RU grammar. Unknown teaching
header перед `:` не даёт affirmative permission для всего сообщения, включая
следующие предложения. Никакой model-only prompt или нового inference service.
[Точный контракт и примеры](../../../docs/P4/PERSISTENT-INSTRUCTIONS.md).

Обычные `Remember Kafka:`/`Запомни Kafka:`, documented shared wrappers и положительные
EN/RU grants проходят без дополнительного confirmation. `start if stopped; never
restart` сохраняет разрешённый start; foreign/case-mismatched resource отклоняется.
Resource snapshots, independent allowlists, текущие controls, lifecycle и receipt
контракты сохранены. Исправления R1 resume не менялись и проходят полный профиль:
additive no-start, omitted flag, persisted restrictions и byte-intent recovery.

Покрытие прежнее: enrolled `harness_run`, CLI run/resume, existing Harness roles и
automatic test operations через Broker. Native host shell/edit и внешние процессы
остаются bypass paths. Knowledge standalone, shared `~/.local/share/knowledge` и
project `.knowledge` сохранены. Распознавание ограничено описанной грамматикой;
качество общей интерпретации произвольного естественного языка не заявляется.

## Проверки новой версии

Из установленного runtime, cwd вне checkout:

```text
python -m unittest discover -s <repo>/tests -p "test_persistent*.py" -v
```

**55/55 PASS**, включая пять R2 tests и все 12 R1 tests, 0 failures/skips.
[Installed профиль](focused-tests.log), [offline install](install.log),
[новый offline kit](distribution/knowledge-harness-0.5.0rc1.zip),
[проверка package/source](package-validation.json).

Полный source-bound маршрут `.venv/bin/python scripts/verify_p4.py` выполняется.
Новый [CI run 44923713836](https://github.com/Ermak-P/Knowledge-/actions/runs/44923713836)
проверяет Linux и native Windows; Windows command: `scripts/verify-p4-windows.ps1`.
Окончательные результаты будут добавлены сюда. Предыдущие R1 CI не переиспользуются.

## Real-host validation

[Discovery](host-discovery.json): OpenCode/Ollama отсутствуют, проверенные loopback
порты 11434/1234/8080/8000 не слушают. [Existing isolated driver](host-validation.json)
вернул BLOCKED до создания host session. Host/model versions, independent session
IDs и live remembered revisions отсутствуют. `unavailable-local-model` — placeholder,
а не выбранная реальная модель. A01/A02/A05/A17 не помечаются PASS.

Нужны установленный совместимый OpenCode и существующая loopback model. Команда:

```text
python -I <repo>/scripts/validate_persistent_host_isolated.py --model <existing-local-model> --endpoint http://127.0.0.1:<port>/v1/chat/completions --output <new-output-directory>
```

[Live guide](../../../docs/P4/PERSISTENT-INSTRUCTIONS-LIVE-HOST.md) сохраняет порядок
plugin/provider config до enrollment и независимые teaching/fresh sessions.
Kafka trial требует owned fixture и обычного fresh запроса tests без memory/Kafka
reminder, затем applicable negatives. Реальные user stores/services не изменялись;
Docker daemon/Desktop не запускались. Parser/contract/CI PASS не заменяет этот trial.
