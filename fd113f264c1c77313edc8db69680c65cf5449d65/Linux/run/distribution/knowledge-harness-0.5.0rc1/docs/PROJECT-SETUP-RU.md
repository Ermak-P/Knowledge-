# Настройка отдельного .NET-проекта

1. Используйте установленный Python runtime. Адаптируйте `examples/runner.json`: runner **version 2**, provider/model, limits/capture и доверенный `recipes.build` с абсолютным `dotnet`. Ветки `recipes.test`, списка тестовых проектов и ручного TRX-пути нет.
2. В task v2 задайте goal, acceptance, writable и `"recipes":["build"]`. Это не отключает тесты.
3. Выполните:

```powershell
$Python = 'C:\LLM\harness-runtime\Scripts\python.exe'
& $Python -I -m harness.run_cli configure --root C:\Projects\Application --input runner.json --init-knowledge
& $Python -I -m harness.run_cli discover-tests --root C:\Projects\Application
& $Python -I -m harness.run_cli run --root C:\Projects\Application --input task.json
& $Python -I -m harness.run_cli status --root C:\Projects\Application --run-id RUN_ID
```

Harness рекурсивно находит **каждый basename с суффиксом `Tests.csproj`, без учёта регистра**. И `IpmAzureCommon.UnitTests.csproj`, и `IpmAzureAutotests.csproj` подходят. Каталог, namespace и включение в solution не определяют совпадение. `bin/obj` и служебные деревья исключены; ссылки и неоднозначности показаны в диагностике.

Все проекты восстанавливаются, собираются и тестируются через owned broker, с отдельным TRX на каждый framework/attempt. Успех требует полного успешного набора и review: отсутствие проектов, ноль тестов, skips, испорченный/старый отчёт и частичный запуск не проходят gate. Добавленный до нового run проект обнаружится автоматически. Изменение набора во время run требует новой валидации; права записи в `.csproj` не расширяются.

Для MCP/OpenCode сохранён `harness_companion`: используйте существующие `harness-host preview/apply` с точным fingerprint и task v2. MCP-команды `harness_discover_tests`, `harness_run` и `harness_status` работают с теми же authority checks. Credentials задаются через provider `key_env`, не в JSON.

Runner v1 и старые task/run сохраняют явные recipes. Завершите старые pending runs под исходной конфигурацией; мигрируйте на runner v2 и запускайте новый task v2. Не меняйте конфигурацию активного run в попытке заменить его авторизацию.
