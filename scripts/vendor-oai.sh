#!/usr/bin/env bash
# Re-vendor the OAI's own schema tests and schemas from github.com/OAI/OpenAPI-Specification at the current branch heads,
# unmodified, and record the commit SHAs in cases/oai/SOURCE. Re-run, then scripts/run.py, to pick up upstream changes.
#   3.1, 3.2, 3.3 (draft): tests/schema/{pass,fail} + src/schemas/validation on v<line>-dev
#   3.0: _archive_/schemas/v3.0/schema.yaml + _archive_/schemas/v3.0/pass on main (the OAI keeps no 3.0 fail tests)
set -euo pipefail
SUITE=$(cd "$(dirname "$0")/.." && pwd)
SRC=$(mktemp -d)
trap 'rm -rf "$SRC"' EXIT
git clone -q --filter=blob:none --no-checkout https://github.com/OAI/OpenAPI-Specification.git "$SRC"
cd "$SRC"

take() {  # take <branch> <repo dir> <dest dir>: copy every file directly in <repo dir>
  rm -rf "$3"; mkdir -p "$3"
  for f in $(git ls-tree --name-only "origin/$1" "$2/"); do git show "origin/$1:$f" > "$3/$(basename "$f")"; done
}

: > "$SUITE/cases/oai/SOURCE.new"
for line in 3.1 3.2 3.3; do
  b=v$line-dev
  for k in pass fail; do take $b tests/schema/$k "$SUITE/cases/oai/$line/$k"; done
  take $b src/schemas/validation "$SUITE/schemas/$line"
  echo "$line $b $(git rev-parse origin/$b)" >> "$SUITE/cases/oai/SOURCE.new"
done
take main _archive_/schemas/v3.0/pass "$SUITE/cases/oai/3.0/pass"
rm -rf "$SUITE/cases/oai/3.0/fail"
mkdir -p "$SUITE/schemas/3.0" && git show origin/main:_archive_/schemas/v3.0/schema.yaml > "$SUITE/schemas/3.0/schema.yaml"
echo "3.0 main $(git rev-parse origin/main) _archive_/schemas/v3.0 (schema + pass examples; the OAI keeps no 3.0 fail tests)" >> "$SUITE/cases/oai/SOURCE.new"
mv "$SUITE/cases/oai/SOURCE.new" "$SUITE/cases/oai/SOURCE"
cat "$SUITE/cases/oai/SOURCE"
