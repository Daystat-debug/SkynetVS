# tools/README.md

# Tools pipeline for SkynetVS

Этот каталог нужен не для “ещё одной фичи”, а для **управляемого цикла улучшения ассистента**.

Главная идея:

```text
ассистент поработал
→ накопил learning-логи
→ мы посмотрели отчёты
→ разложили кандидатов по правильным корзинам
→ только потом решили, что идёт в intents, alias, phrase correction
→ переобучили NLU
```

---

## Главное правило

**Не всё, что ассистент перепутал, должно попадать в `data/intents.json`.**

У нас есть 3 разных типа улучшений:

1. **Intent examples**  
   Для естественных пользовательских формулировок.  
   Это кандидаты в `data/intents.json`.

2. **Entity aliases**  
   Для искажённых сущностей внутри уже понятного интента.  
   Примеры:
   - `дискомфорт` → `дискорд`
   - `гед хаб` → `гитхаб`

3. **Phrase corrections**  
   Для искажённой целой команды.  
   Пример:
   - `останови мужик` → `останови музыку`

Если смешивать это в один слой, модель начнёт учиться на мусоре.

---

# Карта tools

## Аналитика

### `learning_report.py`
Показывает, что накопилось в learning-логах:

- hard cases
- repeat-like hard cases
- missing slots
- action failures
- resolver candidates
- correction pairs
- alias candidates
- suggestions

### `correction_memory_report.py`
Показывает, что уже лежит в `correction_memory.jsonl` и какие записи выглядят сильными.

### `promotion_report.py`
Классифицирует correction memory по корзинам:

- `INTENT EXAMPLES`
- `ENTITY ALIASES`
- `PHRASE CORRECTIONS`
- `REJECTS`

---

## Построение памяти и экспорт

### `build_correction_memory.py`
Берёт correction pairs из анализа и складывает их в:

- `data/learning/correction_memory.jsonl`

### `export_learning_to_inbox.py`
Берёт raw learning-кейсы и складывает их в:

- `data/inbox_unlabeled.jsonl`

Используется для ручной разметки сложных случаев через `label_inbox.py`.

### `export_promotions.py`
Берёт результаты promotion engine и раскладывает их по файлам:

- `INTENT EXAMPLES` → `data/inbox_unlabeled.jsonl`
- `ENTITY ALIASES` → `data/learning/alias_suggestions.jsonl`
- `PHRASE CORRECTIONS` → `data/learning/phrase_correction_suggestions.jsonl`

---

## Ручная разметка и обучение

### `label_inbox.py`
Интерактивно размечает `data/inbox_unlabeled.jsonl` и добавляет хорошие intent examples в:

- `data/intents.json`

Результат разметки сохраняется в:

- `data/inbox_labeled.jsonl`

### `train/train_nlu.py`
Переобучает NLU-модель на актуальном `data/intents.json`.

---

# Какие файлы появляются и зачем

## `data/learning/command_history.jsonl`
История команд:

- raw_text
- final_text
- intent
- confidence
- slots
- accepted / not accepted
- mode
- missing_slots

## `data/learning/nlu_hard_cases.jsonl`
Сюда попадают сложные случаи:

- intent пустой
- команда не принята
- низкая уверенность

## `data/learning/action_failures.jsonl`
Падения execution-слоя.

## `data/learning/resolver_candidates.jsonl`
Кейсы, где intent понятен, а ключевой slot пустой.

## `data/learning/correction_memory.jsonl`
Память исправлений:

- failed_text
- corrected_text
- corrected_intent
- confidence
- slots
- seen_count

## `data/learning/alias_suggestions.jsonl`
Кандидаты для alias/entity resolver.

## `data/learning/phrase_correction_suggestions.jsonl`
Кандидаты для phrase correction layer.

## `data/inbox_unlabeled.jsonl`
Сырые кандидаты для ручной разметки.

## `data/inbox_labeled.jsonl`
Уже размеченные кейсы.

---

# Что реально меняет модель, а что нет

## Меняет модель
Только это:

1. `label_inbox.py`
2. `train/train_nlu.py`

И только потому, что они приводят к изменению:

- `data/intents.json`
- обученной NLU-модели

## Не меняет модель напрямую
Вот это **не переобучает модель**:

- `learning_report.py`
- `build_correction_memory.py`
- `correction_memory_report.py`
- `promotion_report.py`
- `export_promotions.py`
- `export_learning_to_inbox.py`

Они только:

- собирают опыт,
- анализируют,
- готовят кандидатов,
- раскладывают их по корзинам.

---

# Рекомендуемый workflow

## Сценарий A — ассистент поработал, хочу понять, что накопилось

Запускать так:

```bash
python tools/learning_report.py
python tools/build_correction_memory.py
python tools/correction_memory_report.py
python tools/promotion_report.py
```

### Что это даёт
Ты увидишь:

- какие hard cases повторяются;
- какие correction pairs накопились;
- что выглядит как intent example;
- что выглядит как alias;
- что выглядит как phrase correction;
- что нужно выкинуть как шум.

---

## Сценарий B — хочу разложить накопленное по правильным файлам

Запускать так:

```bash
python tools/export_promotions.py
python tools/export_learning_to_inbox.py
```

### Результат
- хорошие `intent_examples` уйдут в `inbox_unlabeled.jsonl`
- `entity_aliases` уйдут в `alias_suggestions.jsonl`
- `phrase_corrections` уйдут в `phrase_correction_suggestions.jsonl`

---

## Сценарий C — хочу доучить intent-модель

Запускать так:

```bash
python tools/label_inbox.py
python train/train_nlu.py
```

### Важно
Перед этим желательно уже посмотреть отчёты, иначе можно потащить в `intents.json` мусор.

---

# Быстрая шпаргалка по порядку

## 1. Посмотреть состояние системы
```bash
python tools/learning_report.py
python tools/build_correction_memory.py
python tools/correction_memory_report.py
python tools/promotion_report.py
```

## 2. Разложить кандидатов
```bash
python tools/export_promotions.py
python tools/export_learning_to_inbox.py
```

## 3. Разметить и переобучить
```bash
python tools/label_inbox.py
python train/train_nlu.py
```

---

# Как принимать решения по кандидатам

## Что можно добавлять в `intents.json`
Только **естественные команды пользователя**.

### Примеры
- `останови музыку`
- `поставь музыку на паузу`
- `выключи музыку`

## Что нельзя добавлять в `intents.json`
Нельзя тащить туда мусор STT.

### Плохие примеры
- `останови мужик`
- `открой де скоро`
- `открой дискомфорт`

---

## Что должно идти в alias suggestions
Когда intent в целом понятен, а ломается сущность.

### Пример
- `дискомфорт` → `дискорд`

---

## Что должно идти в phrase correction suggestions
Когда ломается целая команда.

### Пример
- `останови мужик` → `останови музыку`

---

# Типовые ошибки

## Ошибка 1
Добавлять STT-мусор в `intents.json`.

### Почему плохо
Модель начинает учиться на кривых фразах и деградирует.

---

## Ошибка 2
Переобучать модель без просмотра отчётов.

### Почему плохо
Можно незаметно тащить шум вместо полезных examples.

---

## Ошибка 3
Считать любой correction pair поводом для alias.
### Почему плохо
Не каждый correction pair — это сущность.
Иногда это phrase correction, а иногда вообще шум.

---

# Минимальный безопасный цикл

Если не хочешь путаться, используй этот минимум:

```bash
python tools/learning_report.py
python tools/build_correction_memory.py
python tools/promotion_report.py
python tools/export_promotions.py
python tools/label_inbox.py
python train/train_nlu.py
```

---

# Что будет дальше

Следующие planned steps:

1. `tools/pipeline.py` — единая точка запуска сценариев
2. затем только — следующий слой обучения/коррекции
3. позже — тонкая operator/dev UI оболочка поверх pipeline

---

# Коротко

## Если хочешь понять проблему
Запускай отчёты.

## Если хочешь разложить кандидатов
Запускай export.

## Если хочешь реально улучшить intent-модель
Запускай label + train.

## Если кандидат выглядит криво
Не суй его в intents. Сначала пойми:
- это intent example?
- entity alias?
- phrase correction?
- или шум?
