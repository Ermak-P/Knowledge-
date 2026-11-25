# Реальный host: оставшаяся проверка A01/A02/A05/A17

Текущий вердикт — **IMPLEMENTED / HOST VALIDATION PENDING**. Здесь нет OpenCode и
живой локальной модели. Contract double, full CLI и Docker fixtures проверяют
исполнение, но не означают ACCEPTED для нового host-сеанса.

Для encoding используйте установленный Python и репозиторный driver:

```text
python -I <repo>/scripts/validate_persistent_host_isolated.py --model <existing-local-model> --endpoint http://127.0.0.1:<port>/v1/chat/completions --output <new-output-directory>
```

Он завершает teaching process, запускает обычный запрос на изменение Feature.cs
и configured checks без имени памяти, rule ID или подсказки искать Knowledge,
требует иной session ID, matched revision, completed receipt и точные BOM/CRLF bytes.
PASS этого encoding trial оставляет Kafka A05/A17 NOT RUN.

Обёртка направляет HOME/USERPROFILE, XDG и AppData в временный профиль, удаляет
OpenCode config overrides и вызывает тот же encoding driver. Нужен установленный
OpenCode в PATH (или `--opencode <absolute-path>`) и уже доступная loopback model.
Она не устанавливает хост, модель или Docker daemon. Сначала сохраните
`opencode --version`, точный model ID/version и источник API именно установленной
версии. Published plugin hooks 1.19.6 и companion v2 MCP layout — отдельные
контракты: версия npm package не доказывает поддержку их комбинации вашим хостом.
Driver фиксирует actual host version и отмечает compatibility только после
реального успешного hook + MCP + independent-session trial. Отказ загрузки
plugin/config/MCP — не PASS и не повод расширять permissions.

Порядок для обоих trials: runner + provider + plugin URI в `opencode.json` +
`.knowledge-host.json` + task, **затем** `harness-host preview/apply`. Driver
соблюдает этот порядок и проверяет `companion.doctor` до/после trial. Правки
`opencode.json` после enrollment требуют обычного remove/review/re-enrollment;
host-config digest guard остаётся обязательным.

Для Kafka выполните следующий live trial в отдельном fixture проекте и временном
shared root. Конфигурация — владелец выбирает только существующий локальный Docker
daemon, собственный fixture container и test-accessible endpoint. Не используйте
реальные user stores/сервисы для automated trial. До teaching уже должны быть
настроены разрешённая процедура/template, runner requirement конкретного suite,
plugin и enrolled task. Пример template — в основном руководстве. Для automatic
tests укажите `suite` из verified inventory; не подключайте Kafka ко всем тестам.

1. Создайте один собственный labelled Kafka fixture с закреплённым образом из
   `scripts/persistent_instructions_scenarios.py`. Он должен существовать и быть
   остановлен. Запишите его ID/label; cleanup выполняйте только после проверки
   владения. Не запускайте Docker daemon/Desktop по разрешению на контейнер.
2. В настоящем OpenCode/local-model чате объясните один раз: проверять readiness
   перед тестами объявленного suite, запускать только этот остановленный existing
   container при необходимости, никогда не restart работающий. Дайте явное право
   startup. Если имя/порт ещё отсутствуют, ответьте только недостающими деталями.
   Зафиксируйте durable receipt, scope, ID/revision и оригинальный source.
3. Завершите host process. Откройте новый независимый сеанс без continue/session
   resume, старого transcript или вставленных правил.
4. Обычный запрос: «Выполни настроенные тесты проекта и сообщи результат».
   Не вставляйте Kafka reminder, rule ID, название memory tool или просьбу query
   Knowledge. Стандартная постоянная host integration остаётся подключённой.
5. Проверьте другой session ID; before-action trace suite -> dependency -> shared
   record; существующий resource ID/daemon; ровно один start; успешный protocol
   readiness из test execution environment; затем отдельный результат исходного
   теста. Одного TCP/Running недостаточно. Сохраните actual receipts/log hashes.
6. Ещё один новый сеанс и тот же обычный запрос: ready, ноль start/restart.
   Другой fixture проект с собственным requirement должен использовать тот же
   canonical shared ID, без копирования записи и project init requirement.
7. В новых trials проверьте current no-start, running-not-ready, application test
   failure при ready Kafka, unrelated suite, changed context/container и failed
   remedy. Сбрасывайте только owned fixtures. Неудачный remedy не должен повторять
   startup в каждом новом сеансе; исходный user intent должен сохраниться.

По завершении приложите host/model versions, источник поддержанных hooks,
независимые session IDs, suite metadata, IDs/revisions, snapshot/binding state,
readiness и test receipts, фактические tokens (если доступны) и payload bytes.
**ACCEPTED** допустим только после реальных A01/A02/A05/A17 и применимых negative
checks. Unsupported raw shell/edit пути остаются за пределами принятого контура.
