#!/usr/bin/env bash
# Vendor the upstream Unity Catalog Helm chart into chart/charts/unitycatalog
# and apply the pack's patches. Usage: scripts/vendor-upstream.sh [TAG]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="${1:-$(cat "$ROOT/UPSTREAM_VERSION")}"
DEST="$ROOT/chart/charts/unitycatalog"
PATCHES="$ROOT/patches/chart"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Vendoring unitycatalog helm chart at $TAG"
git clone --quiet --depth 1 --branch "$TAG" https://github.com/unitycatalog/unitycatalog.git "$WORK/uc"

rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$WORK/uc/helm/." "$DEST/"
rm -f "$DEST/generate-docs.sh" "$DEST/README.md.gotmpl"

shopt -s nullglob
for p in "$PATCHES"/*.patch; do
  echo "Applying $(basename "$p")"
  patch -p1 -d "$DEST" --no-backup-if-mismatch < "$p"
done

echo "$TAG" > "$ROOT/UPSTREAM_VERSION"
echo "Done. Review with: git status chart/charts/unitycatalog"
