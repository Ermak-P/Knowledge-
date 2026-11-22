# Постоянные инструкции Knowledge

Это внешняя память, а не обучение модели. Knowledge самостоятельно хранит
инструкции; Harness применяет их перед своими действиями. Изменения опциональны:
старый runner без поля `memory` сохраняет прежний контракт, включая выполнение
при недоступном архитектурном capture. Для нового контура добавьте `memory: {}`
в проверяемую конфигурацию runner **до** enrollment companion. `enabled: false`
отключает контур, сохраняя все записи.

Вердикт поставки: **IMPLEMENTED / HOST VALIDATION PENDING**. Изолированные
проверки не закрывают реальные OpenCode/local-model A01, A02, A05 и A17.

## Что поддерживается

- Проектная SQLite: `<project>/.knowledge/store.sqlite3`.
- Общая SQLite: `<programmatic Path.home()>/.local/share/knowledge/store.sqlite3`,
  включая Windows. Не используется `.config/knowledge`, shell `~` или отдельная
  машинная база. `memory.shared_root` задаёт абсолютный override; у CLI явный
  `--shared-root` имеет приоритет над policy во входном JSON. Env override не введён.
- В тех же базах — совместимое расширение `operations=1`, отдельные current,
  immutable history и receipts. Claims, очередь архитектурных кандидатов,
  точные approvals и legacy migration не меняются. Чтение не создаёт базу.
- Намеренное обучение, постоянная коррекция или обновление правила сохраняется
  из доверенного сообщения пользователя. Обычная задача не становится правилом.
  Исходная формулировка и источник сохраняются; ответ о сохранении появляется
  после commit и повторной проверки базы.
- По умолчанию Harness повторно использует существующий **локальный** provider
  runner для семантической классификации: слова aliases служат описаниями каталога,
  а не обязательными маркерами. `memory.normalizer` может явно задать loopback
  `/chat/completions`, model, timeout (до 45 s), key_env. Remote URL, proxy и redirect
  запрещены. Knowledge самостоятельно принимает тот же normalizer в policy.
- Модель выбирает только типизированный binding или owner-approved template и
  явные пользовательские параметры. Команды из свободного текста не исполняются.
  Неизвестные или невыразимые условия сохраняются `unbound`, с исходником и одним
  вопросом; такой intent блокирует старый более широкий default для этого действия.
  При недоступной модели распознанное явное обучение сохраняется неисполняемым;
  ошибка классификации обычного сообщения не подменяется успешным no-match.
- По умолчанию область — текущий проект. Shared scope требует явного решения и
  исходной цитаты; неоднозначная область остаётся unbound до уточнения. Correction
  сохраняет прежнюю область, если пользователь явно не меняет её.
- `teaching_mode:"catalog"` — явный ограниченный режим для буквальных operator
  aliases и воспроизводимых fixtures без модели. Он не является семантическим
  разбором произвольных условий. Для свободного обучения используйте local-model.

## Подключение хоста

Установка offline core остаётся прежней: `python install.py install --env <env>`.
Плагин включён в wheel Knowledge (`knowledge/host/opencode.mjs`) и в `host/` kit.
MCP-профиль ставится прежним способом; новый удалённый сервис не нужен.

Сначала настройте и проверьте runner, provider, plugin и `.knowledge-host.json`,
затем enroll неизменяемое задание через существующий `harness-host preview/apply`.
В `.knowledge-host.json` проекта:

```json
{"python":"<абсолютный путь к Python установленного kit>"}
```

**До preview/apply** добавьте URI локального `host/opencode.mjs` в настройку
`plugin` проекта `opencode.json`. Поздняя правка меняет enrolled host-config digest
и требует обычного пересмотра enrollment; digest guard не отключается. Это
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
Запрет и исключения формата действуют в текущей host session; новая сессия их
не наследует. Явное разрешение текущего пользователя снимает session-запрет,
не меняя durable правило. Для format CLI есть `--format-input <JSON-file>`.

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
задаются `compose_file` (absolute), `service`, явные `project_name` и `env_file`
(absolute, может быть пустым). Используются явные project directory/name/env-file,
`ps -a -q`, проверка единственного ID и старт именно этого существующего ID.
Изменение Compose/env файла требует перепроверки привязки. `up`, restart, создание
контейнера и удаление томов не являются действиями памяти.

Если имя контейнера и порт ещё неизвестны, настройте вместо фиксированного
behavior типизированный template. Это пример схемы, не найденный пользовательский
ресурс; абсолютные пути выбирает владелец среды:

```json
{
  "procedure_templates":[{
    "id":"local_kafka","kind":"docker-kafka-existing","procedure_id":"local_broker",
    "python":"<ABS_PYTHON>","docker":"<ABS_DOCKER>","defaults":{"host":"127.0.0.1"},
    "deadline":30,"interval":0.25,"attempts":1,"check_timeout":4,"probe_timeout":1
  }],
  "allowed_templates":["local_kafka"],
  "bindings":[{"aliases":["Kafka"],"trigger":{"tool":"dependency","name":"local_broker"},"template":"local_kafka"}]
}
```

Оставьте requirements/environment отдельно как выше. Определение template само по
себе не даёт права исполнения: нужен `allowed_templates` либо точный разрешённый
procedure. После обучения достаточно одного ответа с точным существующим именем
контейнера и портом, без изменения конфигурации или повторного «запомни».
Детали проверяются по цитатам источника; процедура материализуется кодом и полностью
сверяется с текущим template перед каждым исполнением. При смене уже разрешённого
ресурса startup grant не переносится автоматически: требуется явное разрешение
для нового ресурса либо запрет старта. Частичные известные параметры сохраняются.

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
Если деталей не хватает, правило получает `unbound`, а хост задаёт один вопрос
только о недостающем. В той же сессии достаточно ответить деталями — повторять
«запомни» или ID не нужно. Pending reference переживает перезапуск хоста.
В следующей независимой сессии binding уже хранится в SQLite.

Для формата добавьте binding с aliases `encoding`, `BOM`, `кодировку`, trigger
`{"tool":"patch","name":"*.cs"}` и behavior `{"adapter":"preserve-format"}`:

> В дальнейших правках сохраняй исходную кодировку, BOM и окончания строк файлов, если текущая задача явно не требует другого формата.

Поддержаны strict UTF-8, UTF-8 BOM, UTF-16/32 с BOM и однородные LF/CRLF/CR.
Сохраняется наличие завершающего newline. Смешанные окончания отклоняются явно;
неизвестная legacy encoding не угадывается. Для текущего исключения скажите,
например: «В этой задаче переведи Feature.cs в UTF-8 без BOM и с LF». Normalizer
передаст типизированные session format_changes, не изменяя сохранённый default.
Можно явно сбросить исключение для пути; новая host session начинает без исключений.
Для CLI JSON — массив `[{"path":"Feature.cs","encoding":"utf-8","bom":false,"eol":"lf"}]`.
`harness-run resume --root <project> --run-id <id> --no-service-start` сохраняет
текущий запрет под execution lease до продолжения. Без флага старый запрет остаётся;
пустой список API также не снимает запрет. Durable memory grant не меняется.
`--format-input <json>` поддержан на `run` и `resume`: до edit intent он меняет
только текущие выходные bytes и имеет приоритет над session format setting.
После journaled edit intent разрешены только overrides, совместимые с уже
зафиксированными bytes; несовместимый формат или reset этого пути даёт
`resume-format-conflicts-with-edit-intent` без новых writes/provider calls.
Другие command paths отклоняют оба control flags явно. Terminal run с новыми
controls отклоняется; обычный resume сохраняет прежний terminal-result контракт.
U+FEFF внутри
текста не удаляется как BOM; отсутствие final newline не трактуется как BOM-ошибка.

Инспекция и история через обычный локальный Knowledge CLI:

```text
knowledge memory-inspect --root <project> --scope project
knowledge memory-inspect --root <project> --scope shared
knowledge memory-history --root <project> --scope shared --id <ID>
knowledge memory-retire --root <project> --scope shared --id <ID> --expected-revision <REV>
knowledge memory-rebind --root <project> --scope shared --id <ID> --expected-revision <REV> --input <revalidation.json>
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

`memory-rebind` повторно проверяет **текущую** установку той же процедуры: JSON
содержит `text` (обоснование), `source:{type:"user-message",id:"unique-id"}` и
`recovery_authorized` (по умолчанию false). ID, normalized intent и original
сохраняются; создаётся revision, старые blocked/attempted сигналы больше не
разрешают и не блокируют новую привязку. Для изменения самой команды/ресурса
используйте обычную correction `memory-teach --id --expected-revision` с новым
binding и независимым текущим allowlist. Перепривязка не выдаётся как модельный MCP.

## Среда исполнения и устаревание

### Механическая граница startup permission (R1)

В semantic ingress модель предлагает intent, binding и цитату, но сама не выдаёт
startup grant. `knowledge/startup_authorization.py`, контракт `startup-en-ru-v1`,
проверяет полную самостоятельную фразу **текущего** genuine user message.
Поддержаны `You may start container NAME`, `I allow/authorize you to start ...`,
`I allow/authorize starting ...`, `Разрешаю запуск контейнера NAME` и
`Даю разрешение на запуск контейнера NAME`. Допустимы окончания `if/when (it is)
stopped`, `for this purpose`, `если (он) остановлен`, `для этой цели`.
Имя обязано точно совпасть с configured/materialized container или Compose service.
`it`, `that/the/this ... container`, `этого/указанного/... контейнера` допустимы
только при одной Docker/template привязке в каталоге. После уточнения missing
parameters ранее проверенный intent переносится только в его resource binding.

Отрицательные startup-фразы (`you may not`, `do not/don't/never start`,
`не запускай/запускать`, `запрещаю запуск`, `запуск ... запрещён`) сильнее
утвердительной фразы и модельного boolean. Quotation/example/past markers и
неподдержанная грамматика не дают нового grant. Полная фраза, а не вырезанная
цитата, проверяет условия: `You may start it if stopped; never restart a running
container` разрешает только start остановленного объекта. Restart не реализуется
адаптером. Не требуется отсутствие любого `not`/`only`/`не` во всём сообщении.

R2: denial checks читают clause view **без удаления teaching prefix**: весь текст
перед `:` остаётся видимым. Поэтому `Remember you may not start the container:
You may start it` и `Запомни не запускай контейнер: Разрешаю запуск этого
контейнера` дают deny независимо от модельного предложения. Original сохраняется
дословно; clause view нормализует только разделители и `ё/е`.
Для affirmative view отдельно разрешены только `Remember:`/`Запомни:`, topic из
single-word catalog alias (1–64 word characters, без reserved negative/conditional
слов), и перечисленная в `permission_clauses()` EN/RU project-scope grammar.
Например: `Remember Kafka:`, `Запомни Kafka:`, `Remember for all projects using
my local Kafka environment:`, `Запомни для всех проектов с этой локальной Kafka:`.
Alias сопоставляется буквально, а не как regex; arbitrary prose не удаляется.
Неизвестный teaching header с двоеточием запрещает affirmative grant для всего
сообщения, включая последующие предложения. Для clear-denial без каталога topic
headers не распознаются: используйте самостоятельную current clear phrase ниже.
Это ограниченная грамматика wrappers, а не универсальное понимание условий.

Неподтверждённое разрешение оставляет сохранённое правило доступным для readiness;
receipt сообщает эффективный `recovery_authorized:false`. Если автоматический
старт нужен, задаётся один вопрос о разрешении. Текущая отрицательная фраза также
устанавливает session no-start независимо от классификации. Снять session denial
может только полная текущая фраза `You may/can start services again [for this
run/attempt]` или `Разрешаю [снова] запуск сервисов [в этом запуске]`; observation
и old quote не снимают запрет. Пустой CLI/API resume не снимает его.

Новая permission quote из original/history не восстанавливает revoked grant.
Смена resource требует нового подходящего разрешения; независимый текущий
procedure/template allowlist проверяется отдельно при исполнении. Trusted operator
`memory-teach`/`memory-rebind` и явный fixture catalog mode не являются модельными
write tools и сохраняют свои контракты. Старые записи не мигрируются массово.
Произвольный естественный язык, выбор общего teaching intent/scope и семантическое
соответствие инструкции каталогу всё ещё зависят от локальной модели. Это
ограниченная recognition grammar, а не доказательство полного понимания языка.

Исполнимые check/dependency привязки отдельно фиксируют ОС, machine/context hash,
SHA-256 явно используемых инструментов/файлов, Compose/env inputs и Docker context.
На Linux context учитывает machine-id и UTS namespace, на Windows — MachineGuid;
сырые идентификаторы не сохраняются. Это среда выполнения инструмента, а не
предполагаемый рабочий стол пользователя. preserve-format переносим между средами.
Читается только небольшой набор указанных файлов, без нового обхода репозитория.
Отсутствующий/недоступный input означает non-executable binding, а не потерю intent.

Docker всегда получает явные `--config` и `--context`. Поддержаны локальные unix
socket/npipe; remote tcp/ssh и удалённый named pipe в этом контуре не поддержаны.
Ambient DOCKER_HOST/DOCKER_CONTEXT/DOCKER_CONFIG не меняют выбранную привязку.
При необходимости восстановления supervisor сверяет daemon ID и immutable
container ID, затем сохраняет attempted **до** старта. Переиспользованное имя не
переносит разрешение на другой контейнер. Daemon/Desktop автоматически не стартуют.

Неудачный старт, readiness timeout или неизвестный исход сохраняются отдельно от
инструкции. Новый run делает одну безопасную readiness-проверку; при продолжающемся
отказе не повторяет remedy. Если readiness уже подтверждена, может продолжить
исходный тест. Изменённые файлы/среда и обнаруженная замена daemon/container требуют
исправления/перепривязки. Intent и история сохраняются. Потеря даты проверки сама по
себе не отзывает инструкцию. Старые operational records читаются без миграции;
старую executable-привязку без snapshot нужно явно rebind перед исполнением.

Receipt различает unbound/unavailable, tool-denied и unlinked. Последний означает:
процедура сохранена, но в текущем проекте нет declared suite -> dependency route.
Общая запись может быть связана с requirement другого проекта без копирования.

## Trigger, suite и границы интеграции

Ручной recipe имеет стабильное имя из runner. У automatic tests используются уже
проверенные `automatic_tests.operations` и inventory, а не новая discovery-система.
Для конкретного suite дополните существующий requirement (это пример, не факт о
репозитории пользователя):

```json
{"trigger":{"tool":"recipe","name":"@automatic-tests/*"},"suite":"integration/*Tests.csproj","dependency":"local_broker"}
```

Тогда зависимость нужна только test phase совпавших inventory paths; restore/build
и другие suites её не активируют. Без `suite` requirement сохраняет прежнюю
семантику явного recipe pattern. Объявлять Kafka для всех integration tests по
эвристике не нужно. Trace содержит источник link и путь suite. Повторные links к
одной зависимости объединяются в рамках одного действия; readiness проверяется
заново перед использованием. Новой LLM-классификации на low-level tool call нет.

| Путь | Точка lookup/enforcement | Граница |
|---|---|---|
| OpenCode genuine chat.message | Trusted ingress, durable receipt | Только несинтетические user parts; tool/log/repo text не authority. |
| Enrolled harness_run | Existing task authority, затем Broker recipe/patch preflight | Plugin подставляет trusted session; без установленного/совместимого хоста реальный E2E pending. |
| harness-run run/resume | Тот же Broker, task/source/config/lease checks | Текущие ограничения CLI/session сильнее saved grant. |
| Automatic .NET tests | Broker.recipe после проверки operation/inventory | suite filter использует существующие metadata; нет новой discovery. |
| Existing delegated Harness roles | Тот же owned broker | Новые агенты/права не добавляются. |
| Private memory checks/recovery | Тот же process supervisor, без повторного preflight | Memory actions не вызывают сами себя. |
| Read-only Knowledge MCP | Bounded lookup | Не запускает команды и не записывает user authority. |
| Native shell/edit хоста, внешние процессы и иные оркестраторы | Вне этого enforcement | Не заявлены как автоматически покрытые; unsupported trigger сохраняется intent-only. |

Conflict/overflow блокирует затронутое действие, не всю память сессии. Mandatory
records не отбрасываются по top-k; бюджет превышен — явный отказ для этого lookup.
Ни store write lock, ни knowledge maintenance gate не удерживаются во время Docker,
ожидания готовности или тестов.

## Трасса, опыт и отказы

У action в Harness journal есть `memory_traces`: IDs/revisions, scope,
применимость, bytes, lookup time, отдельные owned command receipts и результат.
Lookup ограничен 8 records/12000 UTF-8 bytes по умолчанию; превышение — явный
отказ, не молчаливое усечение обязательных правил. Нет persistent lookup cache.
В контексте источник заменён UTF-8 SHA-256/размером и ссылкой на inspect/history;
полный исходник остаётся в SQLite. Evidence references ограничены с явным partial
маркером. Normalizer получает каталог, текущий user text и один targeted/pending
record, а не всю общую базу. Учитывается только явно возвращённый token usage;
модельные метрики протокольных doubles не выдаются за реальные измерения.
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
python -m unittest discover -s <repo>/tests -p "test_persistent*.py" -v
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
Локальная семантическая интеграция проверена протокольным double; качество реальной
модели и управление native host tools не заявляются. Исполняются только настроенные
типизированные bindings/templates; неизразимые условия остаются unbound.

Откат: отключить plugin, восстановить прежний runner **без ключа memory** и заново
enroll его проверенный task (старый Harness не знает нового ключа), затем восстановить прежние core
wheels по обычному установочному процессу. Не удалять `.knowledge` или shared root.
Предыдущий reader игнорирует additive operational tables; audit и инструкции
сохраняются для повторной установки. Поддерживаемые backups копируют всю project
SQLite; shared базу резервируйте отдельно под её maintenance gate/SQLite backup,
не копированием открытого файла. Никакой bulk migration при установке не выполняется.

Current audit-stage contracts: [AUDIT-STAGES-1-2.md](AUDIT-STAGES-1-2.md) covers source gaps, transfer/degraded recovery, bounded graph diagnostics and automatic P4 delivery.
