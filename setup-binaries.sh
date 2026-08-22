#!/bin/bash
# Загрузка бинарников nebula и nebula-cert для текущей платформы
# Используется: setup-binaries.sh
# или: bash setup-binaries.sh /путь/для/сохранения

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-${SCRIPT_DIR}/for-all}"
NEBULA_VERSION="1.9.7"

# Определяем платформу
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "${OS}" in
    linux)
        case "${ARCH}" in
            x86_64)   PLATFORM="linux-amd64" ;;
            aarch64)  PLATFORM="linux-arm64" ;;
            armv7l)   PLATFORM="linux-armv7" ;;
            *)
                echo "Неизвестная архитектура: ${ARCH}"
                exit 1
                ;;
        esac
        ;;
    darwin)
        case "${ARCH}" in
            x86_64)  PLATFORM="darwin-amd64" ;;
            arm64)   PLATFORM="darwin-arm64" ;;
            *)
                echo "Неизвестная архитектура: ${ARCH}"
                exit 1
                ;;
        esac
        ;;
    *)
        echo "Неизвестная ОС: ${OS}"
        exit 1
        ;;
esac

DOWNLOAD_URL="https://github.com/slackhq/nebula/releases/download/${NEBULA_VERSION}"
NEBULA_URL="${DOWNLOAD_URL}/nebula-${PLATFORM}"
NEBULA_CERT_URL="${DOWNLOAD_URL}/nebula-cert-${PLATFORM}"

mkdir -p "${TARGET_DIR}"

echo "Платформа: ${PLATFORM}"
echo "Скачивание nebula из ${NEBULA_URL}..."
curl -fSL --retry 3 --retry-delay 5 -o "${TARGET_DIR}/nebula" "${NEBULA_URL}"
chmod +x "${TARGET_DIR}/nebula"
echo "✓ nebula скачан"

echo "Скачивание nebula-cert из ${NEBULA_CERT_URL}..."
curl -fSL --retry 3 --retry-delay 5 -o "${TARGET_DIR}/nebula-cert" "${NEBULA_CERT_URL}"
chmod +x "${TARGET_DIR}/nebula-cert"
echo "✓ nebula-cert скачан"

echo "Готово. Бинарники сохранены в ${TARGET_DIR}/"
