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
# Скрипт для копирования файлов узла в /home/mamont/test-n/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="/etc/nebula/"

echo "Копирование файлов узла из: ${SCRIPT_DIR}"
echo "В директорию: ${TARGET_DIR}"

mkdir -p "${TARGET_DIR}"

# Копируем файлы узла
cp -r "${SCRIPT_DIR}/config.yaml" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/ca.crt" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/nebula" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/nebula-cert" "${TARGET_DIR}/"
cp -r "${SCRIPT_DIR}/nebula_service.sh" "${TARGET_DIR}/"

# Копируем сертификат узла (crt и key)
for f in "${SCRIPT_DIR}"/*.crt "${SCRIPT_DIR}"/*.key; do
    [ -f "${f}" ] && cp "${f}" "${TARGET_DIR}/"
done

# Копируем backup если есть
for f in "${SCRIPT_DIR}"/*.backup; do
    [ -f "${f}" ] && cp "${f}" "${TARGET_DIR}/"
done

chmod +x "${TARGET_DIR}/nebula" "${TARGET_DIR}/nebula-cert" "${TARGET_DIR}/nebula_service.sh"

echo "Готово!"
ls -la "${TARGET_DIR}"
DEPLOY_EOF
        chmod +x "${dir}deploy.sh"
        echo "✓ Создан: ${dir}deploy.sh"
    fi
done

echo ""
echo "Готово! Скрипты deploy.sh созданы для всех узлов (исключая CA)."
