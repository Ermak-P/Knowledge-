# Постоянные инструкции Knowledge

Это внешняя память, а не обучение модели. Knowledge самостоятельно хранит
инструкции; Harness применяет их перед своими действиями. Изменения опциональны:
старый runner без поля `memory` сохраняет прежний контракт, включая выполнение
при недоступном архитектурном capture. Для нового контура добавьте `memory: {}`
в проверяемую конфигурацию runner **до** enrollment companion. `enabled: false`
отключает контур, сохраняя все записи.

## Что поддерживается

- Проектная SQLite: `<project>/.knowledge/store.sqlite3`.
- Общая SQLite: `<programmatic Path.home()>/.local/share/knowledge/store.sqlite3`,
  включая Windows. Не используется `.config/knowledge`, shell `~` или отдельная
  машинная база. `memory.shared_root` задаёт абсолютный override; у CLI явный
  `--shared-root` имеет приоритет над policy во входном JSON. Env override не введён.
- В тех же базах — совместимое расширение `operations=1`, отдельные current,
  immutable history и receipts. Claims, очередь архитектурных кандидатов,
  точные approvals и legacy migration не меняются. Чтение не создаёт базу.
- Явное «Запомни…», «Впредь…», «Всегда…», `Remember…`, `From now on…` сохраняется
  из доверенного сообщения пользователя. Обычная задача не становится правилом.
  Исходная формулировка и источник сохраняются; ответ о сохранении появляется
  после commit и повторной проверки базы.
- Автоматическая локальная нормализация связывает **настроенные имена/aliases**
  операций с типизированными действиями. Поддержаны сохранение формата текста,
  проверка условия и readiness/recovery зависимости. Нет удалённой модели,
  embeddings или исполнения команд из свободного текста. Неизвестное намерение
  сохраняется как `unbound`; это не утверждение об исполнимости произвольного языка.
- По умолчанию область — текущий проект. `для всех проектов`, `для проектов`,
  `общее правило`, `all projects`, `for projects`, `shared memory` явно выбирают
  общую память. При неоднозначном выборе нескольких bindings сохранение
  отклоняется с `ambiguous-teaching-binding`; нужно уточнить одну операцию.
  Неясную область следует уточнить явно, а не считать её общей.

## Подключение хоста

Установка offline core остаётся прежней: `python install.py install --env <env>`.
Плагин включён в wheel Knowledge (`knowledge/host/opencode.mjs`) и в `host/` kit.
MCP-профиль ставится прежним способом; новый удалённый сервис не нужен.

Сначала настройте и проверьте runner, затем enroll неизменяемое задание через
существующий `harness-host preview/apply`. В `.knowledge-host.json` проекта:

```json
{"python":"<абсолютный путь к Python установленного kit>"}
```

Добавьте URI локального `host/opencode.mjs` в настройку `plugin` хоста. Это
**opt-in адаптер опубликованного hook API `@opencode-ai/plugin` 1.19.6**:
`chat.message`, `tool.execute.before`, `tui.showToast`. Его исходники и CLI
исследованы; ссылки/хеши — в `PERSISTENT-INSTRUCTIONS-PROTOCOLS.json`.
Существующие документы companion описывают v2 MCP layout. Совместимость плагина
с конкретным v2-хостом не следует из регистрации MCP и требует отдельного запуска.

Плагин захватывает только несинтетические user text parts, запускает локальный
Python без shell и выдаёт UI/синтетический receipt после durable save. MCP
Knowledge остаётся read-only: новая `knowledge_instructions` только читает.
Нельзя передать `source_type=user` через модельный MCP write tool — такого tool нет.
Обычные логи и tool output не проходят user ingress.

Для Knowledge без Harness укажите `backend: "knowledge"` и `policy` с bindings
в `.knowledge-host.json`. Тогда тот же hook вызывает только Knowledge CLI.
Управление исполнением/текущими restrictions остаётся обязанностью самостоятельного
потребителя read-only API. Harness backend — default интеграционного профиля.

Поддерживаемый путь исполнения — enrolled `harness_run`, включая существующие
делегирования и автоматические тесты: все они доходят до owned broker. Native
shell/edit инструменты произвольного хоста этим механизмом не управляются;
расширять их разрешения не требуется. При подключённом плагине trusted session ID
подставляется перед `harness_run`, модель не может отбросить текущий запрет старта.
Для прямого CLI есть `harness-run run ... --no-service-start`.

## Одноразовая привязка среды

В runner допускается поле `memory` следующего вида. Это **шаблон**, а не найденная
конфигурация вашей Kafka; заполнить нужно реальные, явно выбранные значения.
Права и конкретная инфраструктура задаются владельцем конфигурации, а не моделью.

```json
{
  "environment": {"environment":"<имя локальной среды>"},
  "requirements": [
    {"trigger":{"tool":"recipe","name":"<имя рецепта или точный pattern автоматического suite>"},"dependency":"local_broker"}
  ],
  "bindings": [
    {
      "aliases":["Kafka"],
      "applicability":{"environment":"<имя локальной среды>","machine":"<реальное platform.node()>"},
      "trigger":{"tool":"dependency","name":"local_broker"},
      "behavior":{"adapter":"dependency","procedure":{
        "id":"local_broker",
        "check":{"argv":["<ABS_PYTHON>","-I","-m","knowledge.probes","kafka","--host","<HOST>","--port","<PORT>"],"timeout":4},
        "docker":{"executable":"<ABS_DOCKER>","container":"<EXACT_EXISTING_CONTAINER>"},
        "attempts":1,"deadline":30,"interval":0.25
      }}
    }
  ],
  "allowed_procedures":["<тот же объект procedure, а не строка: JSON должен точно совпадать>"]
}
```

В реальном JSON `allowed_procedures` содержит объекты, идентичные процедуре
binding. Изменение команды требует нового разрешённого объекта и корректировки
инструкции; одного текста в памяти недостаточно. Для Compose вместо `container`
задаются только `compose_file` (absolute) и `service`: используется `ps -a -q`,
проверка единственного ID и `start` существующего сервиса. `up`, restart, создание
контейнера и удаление томов не являются действиями памяти.

Требование проекта (`requirements`) отдельно от общей инструкции/процедуры.
В другом проекте нужны его собственные требования и разрешение на тот же exact
procedure; каноническая shared запись не копируется. Идентификатор проекта для её
доступа не нужен. Machine/OS/tool constraints фильтруются до исполнения; machine,
OS и Python version определяет runtime. Прочие tool version tags — утверждения
владельца среды; если нужен живой контроль версии, включите его в разрешённый check.

Readiness выполняется из того же cwd и sanitized process environment, что и тест.
Kafka probe проверяет ApiVersions, Metadata/controller и доступность advertised
broker endpoints, а не только TCP или состояние контейнера. Уже готовая зависимость
не запускается заново. Не готовая работающая служба не перезапускается. Для
остановленной службы нужны и `attempts:1`, и явное сохранённое разрешение пользователя
на старт контейнера, и текущий allowlist; `deadline` ограничивает ожидание readiness.
Каждая диагностическая команда дополнительно ограничена timeout. Неизвестный исход
старта не повторяется вслепую; повторный INTENT сначала проверяет readiness/состояние.

## Как обучать и исправлять

В подключённом чате:

> Запомни для всех проектов с этой локальной Kafka: перед зависимыми тестами проверяй готовность. Разрешаю запуск этого контейнера для этой цели.

Ответ содержит область, статус, trigger, сохранённое поведение и признак разрешения.
Это authority о желании пользователя; `configured` не доказывает исправность команды.
Если привязки нет, правило получает `unbound`, а хост задаёт один вопрос о настроенной
операции. В этой же сессии достаточно ответить её именем после настройки binding —
повторять «запомни» или ID не нужно. Pending reference переживает перезапуск хоста.
В следующей независимой сессии binding уже хранится в SQLite.

Для формата добавьте binding с aliases `encoding`, `BOM`, `кодировку`, trigger
`{"tool":"patch","name":"*.cs"}` и behavior `{"adapter":"preserve-format"}`:

> Запомни: сохраняй кодировку, BOM и окончания строк при правках файлов с binding encoding.

Поддержаны strict UTF-8, UTF-8 BOM, UTF-16/32 с BOM и однородные LF/CRLF/CR.
Сохраняется наличие завершающего newline. Смешанные окончания отклоняются явно;
неизвестная legacy encoding не угадывается. Если задача требует смены формата,
сначала явно скорректируйте/выведите из действия scoped правило. U+FEFF внутри
текста не удаляется как BOM; отсутствие final newline не трактуется как BOM-ошибка.

Инспекция и история через обычный локальный Knowledge CLI:

```text
knowledge memory-inspect --root <project> --scope project
knowledge memory-inspect --root <project> --scope shared
knowledge memory-history --root <project> --scope shared --id <ID>
knowledge memory-retire --root <project> --scope shared --id <ID> --expected-revision <REV>
```

Коррекция из чата: `Уточни правило <ID>: ... <alias настроенной процедуры> ...`.
ID и исходное обучение сохраняются; создаётся ревизия с ссылкой на прежнюю.
Для operator/API есть `memory-teach --id ... --expected-revision ... --input ...`;
JSON содержит `text`, `source:{type:"user-message",id:"durable-source-id"}`,
`binding`, `applicability`, `recovery_authorized`. Этот локальный вход доверен как
существующие operator CLI, не выдаётся модели через MCP. `memory-ingest` принимает
исходный текст и `message_id` с policy через JSON stdin/`--input`.

Повтор source ID идемпотентен; несовместимое повторное использование отклоняется.
Конкурентные corrections используют revision CAS. Retirement немедленно исключает
правило из следующего lookup, сохраняя аудит. Более узкая применимость/проект может
уточнить общий default; неразрешённые противоречия останавливают действие.

## Трасса, опыт и отказы

У action в Harness journal есть `memory_traces`: IDs/revisions, scope,
применимость, bytes, lookup time, отдельные owned command receipts и результат.
Lookup ограничен 8 records/12000 UTF-8 bytes по умолчанию; превышение — явный
отказ, не молчаливое усечение обязательных правил. Нет persistent lookup cache.
`no-match`, `absent`, store busy, corruption и conflict различаются.

После восстановления создаётся project-scoped `experience/candidate` с операцией,
наблюдаемым состоянием, вмешательством, исходом и ссылками на durable artifacts.
Это диагностическая зацепка, доступная targeted after-error lookup. Она не является
обязательной инструкцией, не утверждает root cause и не повышает статус от повторения
моделью. Отдельные application signals хранят timestamp/preconditions/failure без
перезаписи исходного желания пользователя. Технический результат теста остаётся
в собственном receipt; восстановление инфраструктуры не означает успешного теста.

Приватные исходники/логи не копируются автоматически в shared память; туда попадает
только явное пользовательское обучение с binding. Типовые credentials/private keys
отклоняются; не включайте секреты в обучение или procedure argv. Raw output остаётся
в локальных owned artifacts, а memory evidence содержит ссылки, не stdout.

## Воспроизведение и границы доставки

Из установленного Python вне checkout, используя repository validation drivers:

```text
python -m unittest discover -s <repo>/tests -p test_persistent_instructions.py -v
docker pull apache/kafka@sha256:4ceccc577f03f51f6af8dbfda55194d0d892f4fa7913ffbded567ce3895622ed
python -I <repo>/scripts/persistent_instructions_scenarios.py --output <new-output-dir>
python -I <repo>/scripts/validate_persistent_host.py --model <local-model-id> --endpoint http://127.0.0.1:<port>/v1/chat/completions --output <host-output>
```

Первый сценарный driver создаёт только именованные fixtures с собственным label и
удаляет только их после проверки владения. Сравнение memory disabled/enabled сбрасывает
состояние контейнера. Реальный host driver создаёт временный проект и две базы,
выбирает только loopback provider, завершает teaching process, запускает новый host
без `--session`/`--continue`, требует другой session ID, completed Harness receipt,
matched ID/revision и точные BOM/CRLF bytes. Никакие broad permissions не включаются.

В этой среде OpenCode/local model отсутствуют: **полный A02 host E2E BLOCKED**.
Node hook contract + реальный Python ingress, отдельные broker/CLI процессы и
настоящий Kafka не заменяют эту проверку. Выгода по токенам/скорости не установлена.
Произвольная семантическая нормализация текста и управление native host tools не
заявляются; исполняются только явно настроенные типизированные bindings.

Откат: отключить plugin и `memory` integration, затем восстановить прежние core
wheels по обычному установочному процессу. Не удалять `.knowledge` или shared root.
Предыдущий reader игнорирует additive operational tables; audit и инструкции
сохраняются для повторной установки. Поддерживаемые backups копируют всю project
SQLite; shared базу резервируйте отдельно под её maintenance gate/SQLite backup,
не копированием открытого файла. Никакой bulk migration при установке не выполняется.
