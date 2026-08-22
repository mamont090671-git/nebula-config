#!/bin/bash
# Генерация deploy.sh для каждого узла/маяка (ИСКЛЮЧАЯ папку CA)

OUTPUT_DIR="./output"

for dir in ${OUTPUT_DIR}/*/; do
    if [ -d "${dir}" ]; then
        name=$(basename "${dir}")
        
        # Пропускаем папку CA
        if [ "${name}" = "ca" ]; then
            echo "Пропуск папки CA: ${dir}"
            continue
        fi
        
        cat > "${dir}deploy.sh" << 'DEPLOY_EOF'
#!/bin/bash
# Скрипт для копирования файлов узла Nebula
# Использование: ./deploy.sh [/etc/nebula]
#   Если путь не указан — используется /etc/nebula/ по умолчанию

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-/etc/nebula/}"

echo "Копирование файлов узла из: ${SCRIPT_DIR}"
echo "В директорию: ${TARGET_DIR}"

mkdir -p "${TARGET_DIR}"

# Копируем файлы узла
cp -r "${SCRIPT_DIR}/config.yaml" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/ca.crt" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/nebula" "${TARGET_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/nebula-cert" "${TARGET_DIR}/" 2>/dev/null || true
cp -r "${SCRIPT_DIR}/nebula_service.sh" "${TARGET_DIR}/" 2>/dev/null || true

# Копируем сертификат узла (crt и key)
for f in "${SCRIPT_DIR}"/*.crt "${SCRIPT_DIR}"/*.key; do
    [ -f "${f}" ] && cp "${f}" "${TARGET_DIR}/"
done

chmod +x "${TARGET_DIR}/nebula" "${TARGET_DIR}/nebula-cert" "${TARGET_DIR}/nebula_service.sh" 2>/dev/null || true

echo "Готово!"
ls -la "${TARGET_DIR}"
DEPLOY_EOF
        chmod +x "${dir}deploy.sh"
        echo "✓ Создан: ${dir}deploy.sh"
    fi
done

echo ""
echo "Готово! Скрипты deploy.sh созданы для всех узлов (исключая CA)."
echo "Использование: ./deploy.sh [путь_к_директории]  (по умолчанию: /etc/nebula/)"
