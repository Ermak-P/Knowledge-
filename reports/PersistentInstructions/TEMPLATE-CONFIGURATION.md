# Пример одноразовой настройки template

Это пример owner policy, **не обнаруженная инфраструктура пользователя**.
Замените `<...>` на реальные абсолютные пути и имя/pattern рецепта. Объект ниже —
значение `memory` внутри runner. Сначала настройте/проверьте runner, затем выполните
обычный preview/apply enrollment. Локальная нормализация использует существующий
loopback provider runner; не нужно подключать удалённую модель.

```json
{
  "procedure_templates": [
    {
      "id": "local_kafka",
      "kind": "docker-kafka-existing",
      "procedure_id": "local_broker",
      "python": "<ABS_INSTALLED_PYTHON>",
      "docker": "<ABS_DOCKER>",
      "defaults": {"host": "127.0.0.1"},
      "deadline": 30,
      "interval": 0.25,
      "attempts": 1,
      "check_timeout": 4,
      "probe_timeout": 1
    }
  ],
  "allowed_templates": ["local_kafka"],
  "bindings": [
    {
      "aliases": ["Kafka"],
      "description": "Check local Kafka protocol before dependent tests; start only its stopped existing container if permitted.",
      "trigger": {"tool": "dependency", "name": "local_broker"},
      "template": "local_kafka"
    }
  ],
  "requirements": [
    {"trigger": {"tool": "recipe", "name": "<TEST_RECIPE_PATTERN>"}, "dependency": "local_broker"}
  ]
}
```

Если общая среда ограничена конкретной машиной, добавьте в binding
`applicability.machine` с фактическим `platform.node()` и/или environment tag,
который объявлен в `memory.environment`. Новый проект объявляет собственное
requirement и independently approved template; shared запись не копируется.
При нестандартной сетевой топологии используйте заранее проверенный exact
procedure: данный template принимает только loopback host и existing Docker container.

1. Пользователь: «Запомни для всех проектов с этой локальной Kafka: перед зависимыми
   тестами проверяй готовность. Разрешаю запуск указанного существующего контейнера».
2. При незаданных container/port сохраняется unbound intent и выдаётся один вопрос.
3. Ответьте одним сообщением с точным именем контейнера и портом. Config повторно
   редактировать не нужно. В памяти сохраняется тот же ID с новой revision.
4. Завершите host session, откройте новую и дайте обычное задание на тесты без
   повторения правила. Для настоящей A02 используйте real-host driver из руководства.

Запись не даёт права создавать контейнеры или перезапускать работающую нездоровую
службу. Замена ресурса требует нового явного startup grant либо запрета старта.
Неизразимые дополнительные условия сохраняются unbound и блокируют действие.
`allowed_templates: []` запрещает исполнение независимо от сохранённого grant.
