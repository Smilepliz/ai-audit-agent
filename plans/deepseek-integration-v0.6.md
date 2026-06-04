# План: v0.6 — Интеграция DeepSeek

## Цель версии

Интегрировать LLM DeepSeek для генерации улучшенных рекомендаций **поверх** существующего правило-ориентированного аудита, не нарушая текущую модульную архитектуру.

## Основной принцип

DeepSeek — это **неразрушающий enhancements-слой**. Все существующие проверки, парсеры, классификаторы и отчёты продолжают работать идентично. Без флага `--llm` v0.6 ведёт себя точно как v0.5. С флагом `--llm` DeepSeek добавляет в отчёт секцию с AI-анализом.

## Какие файлы создать

### `audit/deepseek.py` — клиент DeepSeek (НОВЫЙ)

Модуль-клиент для взаимодействия с DeepSeek API. Содержит:

- **`DeepSeekConfig`** — dataclass с полями:
  - `api_key: str` — ключ API (fallback: переменная окружения `DEEPSEEK_API_KEY`)
  - `model: str = "deepseek-chat"` — модель (также `deepseek-reasoner`)
  - `temperature: float = 0.3`
  - `max_tokens: int = 2000`
- **`build_prompt(analysis, fetch, config_any)`** — собирает структурированный промпт на русском языке из результатов аудита
- **`generate_recommendations(analysis, fetch, cfg)`** — вызывает DeepSeek API и возвращает словарь с ключами:
  - `overall_assessment` — общая оценка (строка)
  - `top_issues` — список ключевых проблем
  - `top_actions` — список наиболее эффективных действий
  - `blind_spots` — слепые зоны, не покрытые техническими проверками
  - `raw_response` — сырой ответ API

Что делает модуль:
- Читает `DEEPSEEK_API_KEY` из переменной окружения (или `cfg.api_key`)
- Строит структурированный промпт на русском из `analysis`: заголовок, описание, H1, тип сайта, оценка доверия, CTA, контакты, все найденные проблемы, сигналы ecommerce
- Вызывает DeepSeek API через пакет `openai` (OpenAI-совместимый эндпоинт: `https://api.deepseek.com`)
- Парсит JSON-ответ в структурированный словарь
- Возвращает результат (или словарь с ошибкой — никогда не роняет аудит)

## Какие файлы изменить

### `audit/config.py` — добавить настройки DeepSeek

В dataclass `AuditConfig` добавить поля:

```python
deepseek_model: str = "deepseek-chat"
deepseek_temperature: float = 0.3
deepseek_max_tokens: int = 2000
```

### `audit/__init__.py` — добавить CLI-флаг `--llm`

Изменения в `main()`:
- Добавить `parser.add_argument("--llm", action="store_true", help="Включить AI-анализ через DeepSeek")`
- После `analysis = analyze_html(...)` и перед `build_report(...)`:

```python
llm_result = None
if args.llm and analysis:
    from audit.deepseek import generate_recommendations
    deepseek_cfg = DeepSeekConfig(
        model=config.deepseek_model,
        temperature=config.deepseek_temperature,
        max_tokens=config.deepseek_max_tokens,
    )
    llm_result = generate_recommendations(analysis, fetch, deepseek_cfg)
```

- Передать `llm_result` в `build_report()`

### `audit/reporter.py` — добавить AI-секцию в отчёт

Изменения в `build_report()`:
- Принять новый опциональный параметр `llm_result: dict | None = None`
- После секции "Ключевые проблемы" (или между "Ключевые проблемы" и "Что сделать в первую очередь") добавить:

```python
if llm_result:
    lines.append("## AI-анализ (DeepSeek)")
    lines.append("")
    # overall_assessment, top_issues, top_actions, blind_spots
```

Секция рендерится только при использовании `--llm`.

### `requirements.txt` — добавить зависимость

```
openai>=1.0.0
```

## Какие файлы не трогать

| Файл | Причина |
|------|---------|
| `audit/analyze.py` | Оркестратор не меняется; LLM-вызовов внутри нет |
| `audit/fetcher.py` | HTTP-слой не меняется |
| `audit/parser.py` | Парсинг HTML не меняется |
| `audit/quality.py` | Проверка качества входных данных не меняется |
| `audit/models.py` | Новые модели не нужны (результат LLM — обычный dict) |
| `audit/utils.py` | Утилиты не меняются |
| `audit/checks/*.py` | Все проверки без изменений, тесты продолжают проходить |
| `audit/classifiers/*.py` | Логика классификации без изменений |

## Как будет работать CLI-флаг `--llm`

Механизм работы:

1. Флаг `--llm` добавляется в аргументы CLI через `argparse`
2. При запуске `python -m audit https://example.com --llm`:
   - Выполняется стандартный аудит (загрузка, парсинг, проверки, классификация)
   - Полученный словарь `analysis` и результат загрузки `fetch` передаются в `generate_recommendations()`
   - DeepSeek API вызывается с русскоязычным промптом
   - Результат сохраняется в `llm_result` и передаётся в `build_report()`
3. При запуске **без** `--llm`:
   - `llm_result` равен `None`
   - Отчёт генерируется без AI-секции — поведение идентично v0.5

## Как будет добавляться AI-раздел в отчёт

В функции `build_report()`:

- Добавляется опциональный параметр `llm_result: dict | None = None`
- В секции "Ключевые проблемы" блоки:

```python
# Общая оценка
if llm_result.get("overall_assessment"):
    lines.append(f"Общая оценка: {llm_result['overall_assessment']}")

# Ключевые проблемы
if llm_result.get("top_issues"):
    lines.append("Ключевые проблемы (AI):")
    for issue in llm_result["top_issues"]:
        lines.append(f"  - {issue}")

# Рекомендованные действия
if llm_result.get("top_actions"):
    lines.append("Рекомендованные действия (AI):")
    for action in llm_result["top_actions"]:
        lines.append(f"  - {action}")

# Слепые зоны
if llm_result.get("blind_spots"):
    lines.append("Слепые зоны (AI):")
    for spot in llm_result["blind_spots"]:
        lines.append(f"  - {spot}")
```

Секция рендерится **только** когда `llm_result` не `None` и не пуст.

## Промпт (русский язык)

Промпт, отправляемый в DeepSeek, включает:

1. **Полный контекст аудита** — URL, тип сайта, HTTP-статус, время загрузки
2. **SEO-данные** — title, description, H1 (с длинами и выдержками)
3. **Конверсионные данные** — найденные CTA-кнопки, контактная информация
4. **Сигналы доверия** — оценка и какие сигналы присутствуют/отсутствуют
5. **Все найденные проблемы** — сгруппированные по серьёзности и категории
6. **Чеклист ecommerce** — какие сигналы присутствуют
7. **Инструкция** — запросить: общую оценку (2-3 предложения), 3 неочевидные критические проблемы, 3 наиболее эффективных действия, слепые зоны, не покрытые техническими проверками

Промпт требует от модели вернуть **JSON**:

```json
{
  "overall_assessment": "...",
  "top_issues": ["...", "...", "..."],
  "top_actions": ["...", "...", "..."],
  "blind_spots": ["...", "..."]
}
```

## Риски и как их снизить

| Риск | Снижение |
|------|----------|
| Отсутствует API-ключ | Проверить env var + конфиг; вывести предупреждение и пропустить |
| Таймаут / ошибка API | Обернуть в try/except; залогировать ошибку, вернуть `None`, продолжить аудит |
| LLM даёт плохие советы | Промпт-инжиниринг; подавать как дополнение, а не замену |
| Дополнительная задержка (1-3 сек на вызов) | Запускать только с `--llm`; пользователь сознательно включает |
| Стоимость запросов | Пользователь контролирует через `--llm`; рекомендуется `deepseek-chat` ($0.27/M токенов) |

## Порядок реализации

1. Добавить `openai` в `requirements.txt`
2. Создать `audit/deepseek.py` — конфиг, сборщик промпта, вызов API, парсинг ответа
3. Изменить `audit/config.py` — добавить поля DeepSeek в `AuditConfig`
4. Изменить `audit/__init__.py` — добавить `--llm`, вызвать `generate_recommendations`, передать результат
5. Изменить `audit/reporter.py` — отрендерить AI-секцию

## Проверки после реализации

1. `python -m audit https://example.com` (без `--llm`) — убедиться, что поведение идентично v0.5
2. `python -m audit https://example.com --llm` — убедиться, что AI-секция отображается
3. `python -m audit https://example.com --llm` без API-ключа — убедиться в корректном пропуске без падения
