#!/usr/bin/env bash
# Автоматическая загрузка бинарников Nebula v2 с GitHub Releases
# Определяет ОС и архитектуру, скачивает последний релиз, распаковывает в for-all/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${SCRIPT_DIR}/for-all"
TMP_DIR="$(mktemp -d)"

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

detect_arch() {
    case "$(uname -m)" in
        x86_64)   echo "amd64" ;;
        aarch64)  echo "arm64" ;;
        armv7l)   echo "arm" ;;
        armhf)    echo "arm" ;;
        riscv64)  echo "riscv64" ;;
        s390x)    echo "s390x" ;;
        ppc64le)  echo "ppc64le" ;;
        *)        echo "unknown" ;;
    esac
}

get_last_release() {
    if command -v gh &>/dev/null; then
        gh release list --repo slackhq/nebula --limit 1 --json tagName --jq '.[0].tagName' 2>/dev/null
    elif command -v curl &>/dev/null; then
        curl -sL https://api.github.com/repos/slackhq/nebula/releases/latest | grep -oP '"tag_name":\s*"\K[^"]+'
    elif command -v wget &>/dev/null; then
        wget -qO- https://api.github.com/repos/slackhq/nebula/releases/latest | grep -oP '"tag_name":\s*"\K[^"]+'
    else
        echo "Ошибка: ни gh, ни curl, ни wget не найдены." >&2
        exit 1
    fi
}

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(detect_arch)"

if [[ "$OS" != "linux" ]]; then
    echo "❌ Поддерживается только Linux (текущая: $OS)" >&2
    exit 1
fi

if [[ "$ARCH" == "unknown" ]]; then
    echo "❌ Неизвестная архитектура: $(uname -m)" >&2
    exit 1
fi

echo "📦 ОС: $OS, архитектура: $ARCH ($(uname -m))"

NEBULA_VERSION="$(get_last_release)"
echo "📌 Релиз: $NEBULA_VERSION"

ARCHIVE="nebula-${NEBULA_VERSION}-linux-${ARCH}.tar.gz"
URL="https://github.com/slackhq/nebula/releases/download/${NEBULA_VERSION}/${ARCHIVE}"

mkdir -p "$DEST_DIR"

echo "⬇️  Скачивание: $URL"
if command -v curl &>/dev/null; then
    curl -fSL --retry 3 --retry-delay 5 -o "${TMP_DIR}/${ARCHIVE}" "$URL"
elif command -v wget &>/dev/null; then
    wget -qO "${TMP_DIR}/${ARCHIVE}" "$URL"
fi

echo "📂 Распаковка..."
tar -xzf "${TMP_DIR}/${ARCHIVE}" -C "$TMP_DIR"

for bin in nebula nebula-cert; do
    src=$(find "$TMP_DIR" -name "$bin" -type f -not -path "*_test" 2>/dev/null | head -1)
    if [[ -n "$src" ]]; then
        cp -v "$src" "$DEST_DIR/$bin"
        chmod +x "$DEST_DIR/$bin"
    else
        echo "⚠️  Не найден: $bin" >&2
    fi
done

echo "✅ Готово: $DEST_DIR/"
ls -lh "$DEST_DIR"/nebula* 2>/dev/null
