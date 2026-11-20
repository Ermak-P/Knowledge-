# Установка на машине

Нужен Python 3.12; для .NET-проектов — уже установленный подходящий SDK. Исходники IPM/UMUH и локальная модель для установки не требуются.

Сборка из репозитория: `python scripts/build_p4.py --output /absolute/output` (предварительно `python scripts/setup_p3.py`). Сборщик включает runtime, offline wheels, документацию и шаблоны.

Скопируйте содержимое собранного комплекта, например, в `C:\Temp\Harness`, затем:

```powershell
py -3.12 C:\Temp\Harness\install.py install --env C:\LLM\harness-runtime --profile full
C:\LLM\harness-runtime\Scripts\python.exe -I -m harness.run_cli version --root C:\Projects\Application
```

После установки staging-каталог можно удалить: Harness импортируется из установленного environment. Core wheels устанавливаются offline, без GitHub checkout и скачивания Python-зависимостей. Knowledge-only устанавливается отдельно через `--profile knowledge`; optional MCP требует отдельно выбранного `--mcp-online` и его сетевых зависимостей.

В этом репозитории installer использует **`--env`**. Отдельного standalone wrapper с `--mcp-dir` и размещением `C:\LLM\mcp\harness` здесь нет; такой архив не реконструируется этой задачей. Существующая project-local регистрация OpenCode сохраняет имя **`harness_companion`**. Настройка проекта описана отдельно в `PROJECT-SETUP-RU.md`.
