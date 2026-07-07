# SkynetVS — локальный голосовой помощник для Windows

**Стабильная точка:** `SkynetVS Runtime Refactor V1`  
**Назначение README:** быстро поднять проект на другом компьютере и безопасно продолжить разработку.

---

## 1. Что это за проект

`SkynetVS` — локальный голосовой помощник под Windows.

Сейчас проект умеет:

- слушать голос через **Vosk STT**;
- реагировать на hotword: `скайнет` / `skynet`;
- открывать окно голосовых команд после фразы `скайнет`;
- выполнять команды сразу: `скайнет открой ютуб`;
- работать в режиме диктовки;
- управлять громкостью;
- переключать аудиовыходы;
- использовать Edge TTS для озвучки;
- прерывать длинную озвучку голосовой командой;
- вести логи и собирать hard cases для дальнейшего обучения;
- запускать набор eval/smoke-проверок через `tools/pipeline.py`.

Главный принцип проекта:

```text
Проблема -> тест/eval -> исправление -> pipeline check -> ручная проверка -> commit
```

---

## 2. Текущая архитектура

После рефакторинга `main.py` больше не содержит основную бизнес-логику. Он отвечает в основном за wiring, создание зависимостей и event loop.

### Верхний уровень

```text
main.py
  ├─ создаёт STT / TTS / Router / Actions / ModeManager
  ├─ запускает STT producer thread
  ├─ создаёт CommandProcessor
  ├─ создаёт PhraseEventProcessor
  └─ обрабатывает события из очереди
```

### Главные процессоры

```text
modules/command_processor.py
  └─ обработка одной текстовой команды:
     command text -> understanding -> decision/outcome -> runtime

modules/phrase_event_processor.py
  └─ обработка одной STT-фразы:
     speech interrupt -> guards -> confirmation -> dictation -> hotword -> command window
```

### Runtime-слои

```text
modules/command_runtime.py
modules/command_window_runtime.py
modules/hotword_activation_runtime.py
modules/confirmation_runtime.py
modules/dictation_runtime.py
modules/speech_interrupt.py
modules/phrase_guards.py
```

### NLU / понимание команд

```text
modules/nlu.py
modules/intent_rules.py
modules/command_understanding.py
modules/command_decision.py
modules/command_outcome.py
modules/entity_resolver.py
modules/reply_builder.py
modules/command_learning.py
```

### Данные

```text
data/intents.json          # примеры фраз для intent classifier
data/say_templates.json    # ответы ассистента
models/nlu_intent.joblib   # обученная NLU-модель, генерируется локально
```

---

## 3. Что должно быть в Git, а что не должно

### Должно быть в Git

```text
main.py
modules/
tools/
train/
data/intents.json
data/say_templates.json
requirements.txt
requirements-train.txt
.env.example
.gitignore
.gitattributes
README.md
```

### Не должно быть в Git

```text
.env
.venv/
venv/
__pycache__/
.pytest_cache/
models/
data/logs/
data/learning/*.jsonl
data/inbox_unlabeled.jsonl
data/inbox_labeled.jsonl
data/screenshots/
*.joblib
*.pkl
*.pickle
*.onnx
*.pt
*.pth
*.gguf
*.bin
*.wav
*.mp3
*.png
*.jpg
*.jpeg
*.webp
```

### Что перенести вручную на другой ПК

Если хочешь продолжить не только код, но и локальное состояние:

```text
.env                                  # локальные настройки
models/model_small/                   # Vosk small model
models/model_large/                   # Vosk large model, если используешь
models/nlu_intent.joblib              # можно не копировать, можно пересоздать train
data/learning/                        # история обучения, если нужна
data/inbox_labeled.jsonl              # если есть размеченные примеры
data/inbox_unlabeled.jsonl            # если нужно продолжить разметку
```

**Не копируй `.venv` на другой компьютер.** Виртуальное окружение лучше создать заново.

---

## 4. Требования к компьютеру

Рекомендуемая среда:

```text
Windows 10/11
Python 3.12 x64
PowerShell
микрофон
динамики/наушники
интернет для Edge TTS
```

Почему Windows: проект использует Windows-специфичные вещи:

- `pycaw` / `comtypes` для аудио;
- PowerShell MediaPlayer для воспроизведения TTS;
- управление окнами/скриншотами/аудиовыходами под Windows.

---

## 5. Установка на новом компьютере

### 5.1. Клонировать или скопировать проект

```powershell
cd C:\Project
git clone <URL_ТВОЕГО_РЕПОЗИТОРИЯ> SkynetVS
cd C:\Project\SkynetVS
```

Если переносишь без git, скопируй папку проекта без `.venv`, `venv`, `data/logs`, `__pycache__`.

---

### 5.2. Создать виртуальное окружение

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Если PowerShell запрещает активацию:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

После этого снова:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

### 5.3. Установить зависимости

Основные зависимости:

```powershell
pip install -r requirements.txt
```

Текущий `requirements.txt`:

```text
vosk>=0.3.45
sounddevice>=0.4.6
numpy>=1.24
colorama>=0.4.6
edge-tts>=6.1.12
pydub>=0.25.1
scikit-learn>=1.3.0
joblib>=1.3.0
pycaw>=20240210
comtypes>=1.4.0
python-dotenv>=1.0.1
```

`requirements-train.txt` сейчас отдельный минимальный файл для обучения NLU-модели. В нём нет Whisper-зависимостей, только зависимости для `train/train_nlu.py`:

```text
scikit-learn>=1.3.0
joblib>=1.3.2
numpy>=1.24
```

Так как эти пакеты уже есть в основном `requirements.txt`, на новом ПК обычно достаточно:

```powershell
pip install -r requirements.txt
```

Отдельная установка `requirements-train.txt` не обязательна, но её можно выполнить для контроля:

```powershell
pip install -r requirements-train.txt
```

---

## 6. Настройка `.env`

Скопируй пример:

```powershell
copy .env.example .env
notepad .env
```

### Важно про текущий `.env.example`

В старом `.env.example` может быть переменная:

```text
NLU_MIN_CONF=0.35
```

Но актуальный `modules/config.py` читает:

```text
NLU_ACCEPT_CONF
```

Поэтому лучше использовать актуальный вариант ниже.

### Рекомендуемый `.env`

```dotenv
# ---- STT / Vosk ----
STT_MODEL_SMALL=models/model_small
STT_MODEL_LARGE=models/model_large
STT_DEVICE=

# ---- Wake word / flow ----
HOTWORDS=скайнет,skynet
COMMAND_WINDOW_SEC=7.0
IGNORE_AFTER_TTS_SEC=1.0
ACK_TEXT=Слушаю
ACK_IGNORE_SEC=1.2

# ---- NLU ----
NLU_ACCEPT_CONF=0.35
NLU_SAY_CONF=0.55

# ---- Audio ----
VOLUME_STEP=10
AUDIO_OUTPUT_HEADPHONES=Динамики (6- USB Audio Device)
AUDIO_OUTPUT_SPEAKERS=Динамики (Realtek High Definition Audio)

# ---- Whisper refine ----
WHISPER_ENABLE=0
WHISPER_MODEL=small
WHISPER_LANG=ru
WHISPER_TRIGGER_CONF=0.45

# ---- TTS / Edge ----
TTS_VOLUME=+20%
AUDIO_DUCKING_ENABLE=1
AUDIO_DUCKING_LEVEL=0.25

# ---- Logging ----
LOG_ENABLE=1
LOG_PATH=data/logs/runtime.jsonl
INBOX_PATH=data/inbox_unlabeled.jsonl

# ---- Router / execution ----
EXEC_MODE=direct
REPEAT_CONTEXT_SEC=15
```

---

## 7. Скачать и положить Vosk-модели

Проект использует Vosk как основной STT.

Официальная страница моделей:

```text
https://alphacephei.com/vosk/models
```

Рекомендуемое:

```text
small model: vosk-model-small-ru-0.22
large model: vosk-model-ru-0.22 или vosk-model-ru-0.42
```

### Куда положить

Создай папки:

```powershell
mkdir models
mkdir models\model_small
mkdir models\model_large
```

Распакуй small model так, чтобы внутри было не так:

```text
models/model_small/vosk-model-small-ru-0.22/am/...
```

а так:

```text
models/model_small/am/...
models/model_small/conf/...
models/model_small/graph/...
models/model_small/ivector/...
```

То есть содержимое архива должно лежать прямо внутри `models/model_small`.

Large model аналогично:

```text
models/model_large/am/...
models/model_large/conf/...
...
```

Если large model не нужен, можешь оставить:

```dotenv
STT_MODEL_LARGE=
```

Или удалить/очистить путь в `.env`.

---

## 8. Обучить NLU-модель

NLU-модель хранится здесь:

```text
models/nlu_intent.joblib
```

Она генерируется из:

```text
data/intents.json
```

Команда:

```powershell
python train/train_nlu.py
```

Ожидаемый результат:

```text
[OK] trained on ... samples
[OK] saved model: models/nlu_intent.joblib
```

Если `models/nlu_intent.joblib` уже скопирован со старого компьютера, этот шаг можно пропустить. Но после изменений в `data/intents.json` модель нужно переобучать.

---

## 9. Проверка проекта

Главная команда качества:

```powershell
python tools/pipeline.py check
```

Pipeline сам выставляет `PYTHONPATH`, поэтому лучше запускать eval-скрипты через него.

Если запускаешь eval напрямую, используй формат:

```powershell
python -m tools.eval_command_runtime
```

А не:

```powershell
python tools/eval_command_runtime.py
```

Иначе может быть ошибка:

```text
ModuleNotFoundError: No module named 'modules'
```

---

## 10. Основные pipeline-команды

```powershell
python tools/pipeline.py check
python tools/pipeline.py main_inventory
python tools/pipeline.py audit
python tools/pipeline.py eval
python tools/pipeline.py train
python tools/pipeline.py analyze
python tools/pipeline.py promote
python tools/pipeline.py raw_inbox
python tools/pipeline.py label
```

### Самые важные

| Flow | Для чего |
| --- | --- |
| `check` | полный контроль качества |
| `main_inventory` | структура и размеры функций `main.py` |
| `audit` | проверка intent/reply/router consistency |
| `train` | обучение NLU |
| `eval` | проверка NLU |
| `analyze` | отчёты по learning/corrections/promotions |
| `promote` | экспорт promotion-кандидатов |
| `label` | интерактивная разметка inbox |

Логи pipeline сохраняются сюда:

```text
data/logs/pipeline/
```

Можно указать файл явно:

```powershell
python tools/pipeline.py check --log-file data/logs/pipeline/last_check.log
```

Или отключить лог:

```powershell
python tools/pipeline.py check --no-log
```

---

## 11. Первый запуск

После установки, `.env`, моделей и NLU:

```powershell
python tools/pipeline.py check
python main.py
```

Ожидаемый старт:

```text
[BOOT] SkynetVS
[INFO] Скажи: 'Скайнет' / 'Skynet'
[STT] small model: models/model_small
```

---

## 12. Ручной smoke test

После запуска `main.py` проверь голосом.

### Hotword и окно команд

```text
скайнет
открой
блокнот
```

Ожидаемо:

```text
ассистент говорит "Слушаю"
после "открой" ждёт хвост команды
после "блокнот" открывает блокнот
окно команд остаётся открытым
```

### Команда сразу

```text
скайнет открой ютуб
```

Ожидаемо:

```text
YouTube открывается сразу
```

### Диктовка

```text
скайнет режим диктовки
привет мир
заверши диктовку
```

Ожидаемо:

```text
включается режим диктовки
текст печатается в активное окно
режим диктовки выключается
```

### Подтверждение опасной команды

```text
скайнет очисти корзину
нет
```

Ожидаемо:

```text
ассистент просит подтверждение
"нет" отменяет действие
```

### Звук

```text
скайнет громкость 50
скайнет сделай громче
скайнет выключи звук
скайнет включи звук
```

---

## 13. Настройка микрофона

Чтобы посмотреть устройства ввода:

```powershell
python -c "from modules.stt_vosk import VoskSTT; VoskSTT.print_input_devices()"
```

В `.env` можно указать:

```dotenv
STT_DEVICE=1
```

или часть имени устройства:

```dotenv
STT_DEVICE=Microphone
```

Если оставить пустым:

```dotenv
STT_DEVICE=
```

будет использоваться системное устройство по умолчанию.

---

## 14. Настройка аудиовыходов

В `.env`:

```dotenv
AUDIO_OUTPUT_HEADPHONES=Динамики (6- USB Audio Device)
AUDIO_OUTPUT_SPEAKERS=Динамики (Realtek High Definition Audio)
```

При запуске проект выводит список аудиоустройств через `AudioOutputControl.debug_dump_devices()`.

Если переключение не работает:

1. запусти `python main.py`;
2. посмотри точные имена аудиоустройств в консоли;
3. скопируй нужные имена в `.env`;
4. перезапусти проект.

---

## 15. TTS и ducking

TTS работает через `edge-tts`, генерирует MP3 и проигрывает его через PowerShell MediaPlayer.

Настройки:

```dotenv
TTS_VOLUME=+20%
AUDIO_DUCKING_ENABLE=1
AUDIO_DUCKING_LEVEL=0.25
```

`AUDIO_DUCKING_ENABLE=1` означает, что на время речи ассистента другие аудиосессии временно приглушаются.

Если TTS не говорит:

- проверь интернет;
- проверь системный звук;
- проверь, что PowerShell доступен;
- попробуй временно выключить ducking:

```dotenv
AUDIO_DUCKING_ENABLE=0
```

---

## 16. Whisper refine

Whisper-refine сейчас опциональный.

По умолчанию:

```dotenv
WHISPER_ENABLE=0
```

Если включить:

```dotenv
WHISPER_ENABLE=1
WHISPER_MODEL=small
WHISPER_LANG=ru
WHISPER_TRIGGER_CONF=0.45
```

Важно: текущий `requirements-train.txt` не содержит Whisper-зависимостей. Он нужен только для обучения NLU-модели:

```text
scikit-learn>=1.3.0
joblib>=1.3.2
numpy>=1.24
```

Если после включения Whisper падает импорт `faster_whisper`, значит Whisper-зависимости нужно будет добавить отдельно в `requirements-whisper.txt` или расширить `requirements-train.txt`. Сейчас README не фиксирует их как обязательные, потому что в присланном файле их нет.

---

## 17. Learning / inbox / promotion workflow

Проект умеет собирать сложные случаи в JSONL.

Основные файлы:

```text
data/learning/command_history.jsonl
data/learning/nlu_hard_cases.jsonl
data/learning/resolver_candidates.jsonl
data/learning/correction_memory.jsonl
data/inbox_unlabeled.jsonl
data/inbox_labeled.jsonl
```

Нормальный цикл:

```powershell
python tools/pipeline.py analyze
python tools/pipeline.py promote
python tools/pipeline.py label
python tools/pipeline.py train
python tools/pipeline.py check
```

`raw_inbox` не является обычной частью promote-flow. Его использовать только если специально нужно выгрузить шумные raw cases:

```powershell
python tools/pipeline.py raw_inbox
```

---

## 18. Типовые ошибки

### `ModuleNotFoundError: No module named 'modules'`

Причина: eval-скрипт запущен напрямую как файл.

Плохо:

```powershell
python tools/eval_command_runtime.py
```

Хорошо:

```powershell
python -m tools.eval_command_runtime
```

Лучше:

```powershell
python tools/pipeline.py command_runtime
```

---

### Vosk model path error

Если Vosk пишет, что модель не найдена или путь неправильный, проверь структуру:

Плохо:

```text
models/model_small/vosk-model-small-ru-0.22/am/...
```

Хорошо:

```text
models/model_small/am/...
```

---

### Микрофон не слушает

Проверь:

```powershell
python -c "from modules.stt_vosk import VoskSTT; VoskSTT.print_input_devices()"
```

Потом укажи `STT_DEVICE` в `.env`.

Также проверь разрешения микрофона Windows:

```text
Параметры Windows -> Конфиденциальность и безопасность -> Микрофон
```

---

### Команды плохо распознаются

Проверь NLU:

```powershell
python tools/pipeline.py eval
```

После изменений в `data/intents.json`:

```powershell
python tools/pipeline.py train
python tools/pipeline.py check
```

---

### Команда не выполняется из-за missing slots

Это нормально для неполных команд:

```text
открой
найди
переключи
```

Проект должен не выполнять такие команды, а ждать уточнение или отвечать, что данных не хватает.

---

### Confirmation-тесты падают из-за текста

Если шаблон подтверждения меняется, тест не должен зависеть от конкретной случайно выбранной фразы. В eval лучше нормализовать confirmation prompt, а не сравнивать точный текст.

---

## 19. Как сохранить структуру проекта в файл

Полный tree:

```powershell
cd C:\Project\SkynetVS
cmd /c "tree /F /A" | Out-File -FilePath .\project_tree.txt -Encoding utf8
```

Но полный tree может захватить `.venv` и стать огромным.

Лучше чистый список:

```powershell
cd C:\Project\SkynetVS

Get-ChildItem -Recurse -Force |
  Where-Object {
    $_.FullName -notmatch '\\\.git\\' -and
    $_.FullName -notmatch '\\\.venv\\' -and
    $_.FullName -notmatch '\\venv\\' -and
    $_.FullName -notmatch '\\__pycache__\\' -and
    $_.FullName -notmatch '\\models\\' -and
    $_.FullName -notmatch '\\data\\logs\\' -and
    $_.FullName -notmatch '\\\.pytest_cache\\'
  } |
  Select-Object FullName |
  Out-File -FilePath .\project_files_clean.txt -Encoding utf8
```

---

## 20. Перед переносом на другой ПК

### 20.1. Проверить текущий проект

```powershell
python tools/pipeline.py check
python tools/pipeline.py main_inventory
```

### 20.2. Закоммитить

```powershell
git status
git add .
git commit -m "stable: SkynetVS Runtime Refactor V1"
git push
```

### 20.3. Отдельно сохранить локальное состояние

Если нужно сохранить локальные модели и learning history:

```text
.env
models/model_small/
models/model_large/
models/nlu_intent.joblib
data/learning/
data/inbox_labeled.jsonl
data/inbox_unlabeled.jsonl
```

Не сохраняй в git:

```text
.venv/
venv/
data/logs/
__pycache__/
```

---

## 21. Как продолжить разработку

Следующий рекомендуемый этап:

```text
Resolver Quality V1
```

Цель — улучшить понимание команд и слотов:

```text
открой браузер
открой хром
открой проводник
открой папку загрузки
найди в интернете ...
поставь громкость ...
переключи на наушники
переключи на колонки
```

Правило развития:

```text
не добавлять хаотично rules на каждую фразу
rules — только для коротких/system/опасных/режимных/параметрических случаев
обычные естественные формулировки — через data/intents.json + eval
```

---

## 22. Минимальный чеклист нового компьютера

```powershell
cd C:\Project
git clone <URL> SkynetVS
cd SkynetVS

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

copy .env.example .env
notepad .env

mkdir models
mkdir models\model_small
# распаковать Vosk small model внутрь models\model_small

python train/train_nlu.py
python tools/pipeline.py check
python main.py
```

После запуска проверить голосом:

```text
скайнет
скайнет открой ютуб
скайнет режим диктовки
заверши диктовку
скайнет очисти корзину
нет
```

---

## 23. Короткая карта проекта

```text
SkynetVS/
  main.py
  requirements.txt
  requirements-train.txt
  .env.example

  data/
    intents.json
    say_templates.json
    learning/
    logs/
    screenshots/

  models/
    model_small/
    model_large/
    nlu_intent.joblib

  modules/
    command_processor.py
    phrase_event_processor.py
    command_runtime.py
    command_window_runtime.py
    hotword_activation_runtime.py
    confirmation_runtime.py
    dictation_runtime.py
    command_understanding.py
    command_decision.py
    command_outcome.py
    command_learning.py
    reply_builder.py
    router.py
    actions.py
    stt_vosk.py
    stt_whisper.py
    tts_edge.py
    speech_io.py
    speech_interrupt.py
    phrase_guards.py
    mode_manager.py
    entity_resolver.py
    audio_control.py
    audio_output.py
    typing_service.py
    weather_service.py
    window_context_service.py

  tools/
    pipeline.py
    command_audit.py
    eval_*.py
    learning_report.py
    promotion_report.py
    main_inventory.py

  train/
    train_nlu.py
```

---

## 24. Контрольная стабильная точка

Текущая стабильная точка:

```text
SkynetVS Runtime Refactor V1
```

Что входит:

```text
CommandProcessor
PhraseEventProcessor
command_runtime
command_window_runtime
hotword_activation_runtime
confirmation_runtime
dictation_runtime
speech_interrupt
phrase_guards
reply_builder
command_understanding
command_outcome
command_learning
pipeline check
main inventory
```

Перед крупными изменениями желательно делать snapshot/commit от этой точки.
