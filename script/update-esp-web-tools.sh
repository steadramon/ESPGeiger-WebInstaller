#!/usr/bin/env bash
# Re-bundle esp-web-tools and replace installer/install-button.js.
# Usage: script/update-esp-web-tools.sh [version]
#   version defaults to 10.2.1
set -euo pipefail

VERSION="${1:-10.2.1}"
DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/installer"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$TMP"
echo '{"private":true,"type":"module"}' > package.json
echo "Installing esp-web-tools@$VERSION ..."
npm install "esp-web-tools@$VERSION" --silent

echo "Bundling to $DEST_DIR ..."
# --splitting keeps the dynamic imports inside esp-web-tools (flash dialog,
# esptool-js) as separate chunks that load on click. Page-load cost is just
# the install-button shell; everything else lazy-loads.
find "$DEST_DIR" -maxdepth 1 -name '*.js' -delete
npx --yes esbuild node_modules/esp-web-tools/dist/install-button.js \
  --bundle --splitting --format=esm --minify --target=es2020 \
  --outdir="$DEST_DIR"

ls -lh "$DEST_DIR"

# Cache-bust the shell entry. Chunks are content-hashed by esbuild so they
# bust themselves; install-button.js has a stable name, so an old cached
# shell would reference renamed chunks and 404. Patch the bundle's content
# hash into index.htm so a re-bundle forces browsers to re-fetch the shell.
INDEX="$(cd "$DEST_DIR/.." && pwd)/index.htm"
HASH="$(shasum "$DEST_DIR/install-button.js" | cut -c1-8)"
perl -i -pe "s|install-button\.js\?v=[^\"]+|install-button.js?v=$HASH|" "$INDEX"
echo "Patched index.htm with ?v=$HASH"
echo "Done. Commit and push when you're happy."
