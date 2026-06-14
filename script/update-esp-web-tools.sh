#!/usr/bin/env bash
# Re-bundle esp-web-tools and replace installer/install-button.js.
# Usage: script/update-esp-web-tools.sh [version]
#   version defaults to 10.2.1
set -euo pipefail

VERSION="${1:-10.2.1}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/installer/install-button.js"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$TMP"
echo '{"private":true,"type":"module"}' > package.json
echo "Installing esp-web-tools@$VERSION ..."
npm install "esp-web-tools@$VERSION" --silent

echo "Bundling to $DEST ..."
npx --yes esbuild node_modules/esp-web-tools/dist/install-button.js \
  --bundle --format=esm --minify --target=es2020 \
  --outfile="$DEST"

ls -lh "$DEST"
echo "Done. Commit and push when you're happy."
