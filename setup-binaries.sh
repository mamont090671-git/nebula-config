#!/usr/bin/env bash
# Автоустановка бинарников Nebula v2 на целевую машину
# Определяет ОС и архитекцию при запуске, скачивает нужный релиз
# Использование: ./setup-binaries.sh [--dir /путь/куда/установить]
# По умолчанию: /usr/local/bin (требует root)

set -euo pipefail

TARGET_DIR="${2:-/usr/local/bin}"
mkdir -p "$TARGET_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

detect_arch() {
    case "$(uname -m)" in
        x86_64)   echo "amd64" ;;
        aarch64|arm64) echo "arm64" ;;
        armv7l|armhf) echo "arm" ;;
        riscv64)  echo "riscv64" ;;
        s390x)    echo "s390x" ;;
        ppc64le)  echo "ppc64le" ;;
        *)        echo "unknown" ;;
    esac
}

get_latest() {
    if command -v gh &>/dev/null; then
        gh release list --repo slackhq/nebula --limit 1 --json tagName --jq '.[0].tagName' 2>/dev/null
    elif command -v curl &>/dev/null; then
        curl -sL https://api.github.com/repos/slackhq/nebula/releases/latest | grep -oP '"tag_name":\s*"\K[^"]+'
    elif command -v wget &>/dev/null; then
        wget -qO- https://api.github.com/repos/slackhq/nebula/releases/latest | grep -oP '"tag_name":\s*"\K[^"]+'
    else
        echo "Ошибка: нужен gh, curl или wget" >&2; exit 1
    fi
}

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(detect_arch)"

if [[ "$ARCH" == "unknown" ]]; then
    echo "❌ Неизвестная архитектура: $(uname -m)" >&2; exit 1
fi

VERSION="$(get_latest)"
ARCHIVE="nebula-${VERSION}-${OS}-${ARCH}.tar.gz"
URL="https://github.com/slackhq/nebula/releases/download/${VERSION}/${ARCHIVE}"

echo "📦 $OS / $ARCH ($(uname -m)) → $VERSION"
echo "⬇️  $URL"

if command -v curl &>/dev/null; then
    curl -fSL --retry 3 "$URL" -o "${TMP_DIR}/${ARCHIVE}"
elif command -v wget &>/dev/null; then
    wget -qO "${TMP_DIR}/${ARCHIVE}" "$URL"
fi

tar -xzf "${TMP_DIR}/${ARCHIVE}" -C "$TMP_DIR"

for bin in nebula nebula-cert; do
    src=$(find "$TMP_DIR" -name "$bin" -type f ! -name "*_test" 2>/dev/null | head -1)
    if [[ -n "$src" ]]; then
        cp -v "$src" "$TARGET_DIR/$bin"
        chmod +x "$TARGET_DIR/$bin"
    else
        echo "⚠️  Не найден: $bin" >&2
    fi
done

echo "✅ $TARGET_DIR/"
ls -lh "$TARGET_DIR"/nebula* 2>/dev/null
