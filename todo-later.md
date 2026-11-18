---
title: Nebula Config — Сделать позже
created: 2026-08-22
status: pending
---

1. Исправить firewall rule на лайтхаусе: группа "laptop" отсутствует — заменить на реальную группу или удалить правило port 443
2. Добавить logging секцию в клиентский шаблон (level: info, format: text)
3. Добавить IPv6 static_host_map entry если есть публичный IPv6 у лайтхауса
4. Добавить stats (prometheus) на лайтхаус для мониторинга relay-трафика
5. Убрать мёртвое поле "type" из master-конфа (не используется генератором)
6. Добавить второго lighthouse для redundancy
7. Добавить nebula debug print-rules в deploy-скрипт для верификации firewall после деплоя
