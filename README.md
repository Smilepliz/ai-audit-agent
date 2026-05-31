# AI Audit Agent

Инструмент для автоматического аудита сайтов.

## Возможности

### SEO
- Проверка Title
- Проверка Description
- Проверка H1
- Проверка Canonical
- Проверка robots.txt
- Проверка sitemap.xml

### Технический аудит
- Schema.org / JSON-LD
- Alt-атрибуты изображений

### Конверсия
- CTA элементы
- Контактная информация
- Элементы доверия

### Ecommerce
- Каталог
- Карточки товаров
- Корзина
- Цены
- Кнопки покупки

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python -m audit https://example.com
```

## Примеры

```bash
python -m audit https://profi-studio.ru
python -m audit https://nadin-tkani.ru
```

## Структура проекта

```text
audit/
├── checks/
├── classifiers/
├── analyze.py
├── fetcher.py
├── parser.py
├── reporter.py
└── ...
```

## Roadmap

- [ ] Проверка hreflang
- [ ] Анализ скорости сайта
- [ ] Обход нескольких страниц
- [ ] CMS detection
- [ ] Экспорт в JSON
- [ ] Веб-интерфейс
