# LLM Project

Документный анализатор на `FastAPI + PostgreSQL + Nginx`.

## Что уже реализовано

- Регистрация/логин пользователей (JWT).
- Роли пользователей: `user`/`admin`.
- Загрузка документов (`.txt`, `.pdf`, `.docx`) с хранением файла в БД (`BYTEA`).
- Для документа хранится уровень конфиденциальности: `public|confidential`.
- Извлечение текста и нарезка на чанки (параграфы/блоки) с метриками.
- Анализ текста через LLM (или mock-режим при отсутствии модели).
- Гибридный анализ `LLM + Rule Engine`:
  - термины из глоссария (`forbidden_variants`),
  - шаблонные правила (`regex`),
  - цитируемые источники (`source_references`),
  - `policy_hash` для безопасного кеширования результатов.
- Сохранение результатов анализа в БД:
  - оценки,
  - список проблем,
  - список рекомендаций,
  - raw JSON-ответ.

## Основные API

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /api/documents/upload`
- `GET /api/documents`
- `GET /api/documents/{document_id}`
- `GET /api/documents/{document_id}/content`
- `DELETE /api/documents/{document_id}`
- `POST /api/analyze`
- `GET /api/analysis/history`
- `POST /api/chat`
- `GET /api/admin/overview` (admin only)
- `GET /api/admin/audit-logs` (admin only)
- `GET /api/admin/users-summary` (admin only)
- `PATCH /api/admin/users/{user_id}/status` (admin only)
- `GET /api/admin/knowledge/overview` (admin only)
- `POST /api/admin/knowledge/seed-defaults` (admin only)
- `GET/POST/PATCH/DELETE /api/admin/knowledge/sources` (admin only)
- `GET/POST/PATCH/DELETE /api/admin/knowledge/glossary` (admin only)
- `GET/POST/PATCH/DELETE /api/admin/knowledge/rules` (admin only)
- `GET /health`

## Лимиты

- Максимальный размер загружаемого файла: `10 MB` (настраивается через `MAX_UPLOAD_SIZE_MB`).
- Для `POST /api/documents/upload` можно передать `purpose`: `check` или `training` (по умолчанию `check`).
- Для `POST /api/documents/upload` можно передать `confidentiality_level`: `public` или `confidential` (по умолчанию `confidential`).
- `GET /api/documents` поддерживает фильтр `purpose=check|training`.
- `GET /api/documents` поддерживает фильтр `confidentiality_level=public|confidential`.

## Хранение в БД

- `users`
- `documents`
- `document_chunks`
- `analysis_runs`
- `analysis_issues`
- `analysis_recommendations`
- `audit_logs`
- `source_references`
- `glossary_terms`
- `rule_patterns`

## Поведение чата

- `/api/chat` ищет релевантные чанки из загруженных пользователем документов и подмешивает их как контекст.
- Это дает "моментальный эффект дообучения" без перезапуска модели.

## Администратор

- У пользователя есть флаг `is_admin`.
- Админ видит общую статистику и аудит всех пользователей.
- В `GET /api/analysis/history` для админа возвращаются все проверки (с `user_id`/`user_email`).
- В `GET /api/documents` админ может фильтровать по `purpose` (`check`/`training`).
