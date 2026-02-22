# TikTok + YouTube Shorts Poster

Production-ready Streamlit приложение для одновременной публикации коротких видео в:

- YouTube Shorts через **YouTube Data API v3**
- TikTok через **официальный TikTok Content Posting API**

> Используются только официальные API.

## Возможности

- UI c тремя страницами:
  - **New Post** — загрузка mp4/mov, метаданные, выбор платформ, privacy YouTube, schedule UTC, прогресс и результат.
  - **Settings** — настройка YouTube OAuth путей и TikTok токенов, сохранение в `secrets.json`, опциональная перезапись `.env`.
  - **History** — история публикаций из SQLite.
- SQLite лог/очередь таблица `posts`.
- Параллельный постинг в обе платформы (`asyncio.gather`) с независимым успехом/падением.
- Retry с экспоненциальной задержкой при сетевых ошибках.
- Валидация видео через `ffprobe`:
  - вертикальное (близко к 9:16)
  - длительность до 60 секунд.
- Централизованное логирование и аккуратные ошибки.

## Структура проекта

- `app.py` — Streamlit UI
- `config.py` — загрузка/сохранение `.env` + `secrets.json`
- `db.py` — SQLite функции
- `validators/video.py` — ffprobe валидация
- `publishers/youtube.py` — OAuth + upload в YouTube
- `publishers/tiktok.py` — TikTok Content Posting API flow
- `services/poster.py` — `post_both`, retry, orchestration

## Требования

- Python 3.11+
- Установленный `ffprobe` (из пакета ffmpeg)

## Настройка API

### YouTube

1. Создайте OAuth client credentials в Google Cloud.
2. Скачайте `client_secret.json`.
3. В Settings укажите путь к `client_secret.json` и путь для `token.json`.
4. Нажмите **Run YouTube OAuth flow**.
5. Scope: `https://www.googleapis.com/auth/youtube.upload`.

### TikTok

1. Создайте приложение в TikTok for Developers.
2. Получите `access_token` и `open_id`.
3. Заполните в Settings.
4. Если приложение не прошло нужный audit, TikTok может возвращать `draft/private/limited`.

## Запуск

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment (VPS)

1. Установите Python 3.11+, ffmpeg/ffprobe.
2. Скопируйте проект.
3. Создайте виртуальное окружение и установите зависимости.
4. Настройте `.env` и/или заполните Settings в UI.
5. Запустите `streamlit run app.py --server.port 8501 --server.address 0.0.0.0`.

## Безопасность

- Не коммитьте `secrets.json`, `.env`, `token.json`, `uploads/`.
- Токены не логируются приложением.
