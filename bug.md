Глубокий аудит generate_configs.py и validators.py выявил ряд критических багов в логике деплоя/перевыпуска сертификатов и уязвимостей безопасности (Command Injection).
Ниже приведён детальный разбор найденных проблем с конкретными исправлениями.

1. Критические баги (Ломают функциональность)


1.1. Конфликт деплоя и скрипта отката (nebula_service.sh)

• Проблема: В README заявлено, что при деплое делается бэкап, запускается nebula -test и выполняется авто-откат через nebula_service.sh. Однако в функции deploy_configs() (generate_configs.py) скрипт nebula_service.sh просто копируется на сервер, но не запускается. Вместо него deploy_configs() напрямую перезаписывает файлы через scp и вызывает systemctl restart nebula. Если в конфиге ошибка — служба просто упадёт без отката.
• Решение: Либо вызывать ssh "{remote_host}" "bash {remote_base}/nebula_service.sh {remote_base}" вместо ручного перезапуска, либо добавить nebula -test -config {remote_base}/config.yaml перед рестартом прямо в deploy_configs().

1.2. Баг с хэш-фильтрацией при деплое (deploy_configs)

• Проблема: В цикле проверки хэшей стоит break на первом же изменённом файле:python
if local_hash != remote_hash:
    needs_deploy = True
    changed_files.append(f"[ИЗМЕНЁН] {item.name}")
    break  # <-- обрывает проверку остальных файлов!
Используйте код с осторожностью.
В результате при --dry-run пользователь видит только первый изменённый файл, а не полный список. Кроме того, compute_remote_file_hash скачивает каждый файл целиком по scp ради подсчёта хэша на локальной машине, что медленно для больших бинарников или медленных каналов.
• Решение: Убрать break в цикле проверки и считать хэши прямо на удалённом сервере одной SSH-командой (sha256sum /etc/nebula/*).

1.3. Сломанный поиск узла при --renew-expiring

• Проблема: В блоке --renew-expiring скрипт ищет имя узла в конфиге по имени файла сертификата:python
if name not in all_nodes:
Используйте код с осторожностью.
Но в список expiring_soon попадает crt_file.name (то есть "server-1.crt", а не "server-1"), либо кастомное имя из поля node_data.get("name"). Из-за суффикса .crt условие name not in all_nodes сработает всегда, и перевыпуск завершится с ошибкой Узел 'server-1.crt' не найден в конфиге.
• Решение: Хранить в списках expiring_soon и expired не имя файла, а кортеж (node_name, crt_file, days_str), где node_name = crt_file.parent.name.

1.4. Нерабочий флаг --only-hosts / --host при старте с нуля

• Проблема: Если запустить python3 generate_configs.py --only-hosts --host server-1 и при этом ca.crt ещё не создан, скрипт сгенерирует CA (auto_generate = True), но сгенерирует сертификат только для server-1, оставив остальные узлы без сертификатов.

2. Уязвимости безопасности


2.1. Command Injection в SSH/SCP вызовах

• Проблема: В функциях compute_remote_file_hash, detect_remote_arch, deploy_binaries, deploy_service и deploy_configs параметры ssh_target и remote_base подставляются в строку с shell=True:python
cmd = f'scp "{item}" "{ssh_target}:{remote_path}"'
subprocess.run(cmd, shell=True, ...)
Используйте код с осторожностью.
Если в ssh_target или имени файла окажутся символы $, ` или ", произойдёт инъекция команд на локальной машине.
• Решение: Отказаться от shell=True и передавать аргументы списком:python
subprocess.run(["scp", str(item), f"{ssh_target}:{remote_path}"], check=False)
Используйте код с осторожностью.

2.2. Небезопасное создание временных файлов при скачивании бинарников

• Проблема: В deploy_binaries() архив скачивается в предсказуемый путь /tmp/{archive} с правами root (Symlink attack / перезапись файлов при одновременном запуске).
• Решение: Использовать TMPDIR=$(mktemp -d) внутри bash-скрипта и удалять его через trap 'rm -rf "$TMPDIR"' EXIT.

2.3. Утечка приватного ключа CA при проверке на шифрование

• Проблема: В generate_node_certificate() открывается файл ca.key для чтения первой строки:python
with open(ca_key, "r") as kf:
    first_line = kf.readline().strip()
Используйте код с осторожностью.
Если ca_key_path указывает на несуществующий или недоступный по правам файл, скрипт упадёт с необработанным PermissionError/FileNotFoundError до блока try/except.

3. Архитектурные улучшения и качество кода


3.1. Замена строкового парсинга YAML на yaml.safe_load

• Проблема: В render_config() и verify_generated_configs() конфиг собирается и проверяется через строковые подстановки (result.replace(...)) и поиск подстрок ("use_relays: true" not in content). Если в комментарии или имени хоста встретится похожая строка, проверка даст ложное срабатывание, а неверный отступ при replace сломает синтаксис YAML.
• Решение: Загружать шаблон templates/config.yaml через yaml.safe_load(), модифицировать словарь Python и сохранять через yaml.safe_dump(). Это на 100% гарантирует валидность итогового YAML.

3.2. Усиление валидации в validators.py

• Отказ от Pydantic оправдан: Использование чистого stdlib (dataclasses + ipaddress) — отличное решение для CLI-утилиты, так как избавляет от внешних зависимостей.
• Что стоит доработать в validators.py:
	1. Проверка уникальности IP-адресов: Сейчас можно случайно назначить двум узлам одинаковый nebula_ip.ipv4 или ipv6 — валидатор это пропустит.
	2. Поддержка IPv6 для public_ip: Сейчас IPv4Address(self.public_ip) отклонит валидный публичный IPv6-адрес маяка. Лучше использовать ipaddress.ip_address(self.public_ip) (поддерживает и v4, и v6).
	3. Валидация ssh_target: Добавить проверку формата user@host:/abs/path на этапе валидации конфига, а не во время деплоя.
	4. Проверка relay_servers: Убедиться, что каждый IP в relay_servers является валидным IP-адресом и соответствует одному из маяков с am_relay: true.

3.3. Устранение дублирования в generate_configs.py

• В main() файл config-nebula.yaml загружается трижды подряд (load_config() вызывается на строках 651, 661 и 669), а модуль ipaddress импортируется дважды (в начале файла и внутри main()).
• Функции build_static_host_map_for_client и build_static_host_map_for_lighthouse дублируют друг друга на 80% — их легко объединить в одну функцию с параметром include_self: bool.
