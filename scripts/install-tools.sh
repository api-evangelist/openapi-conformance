#!/usr/bin/env bash
# Install the latest release of every tool in tools.yml into TOOLDIR (default ./.tools).
# Java and .NET: uses java / dotnet from PATH when present (CI sets them up), else downloads a JDK 21 and
# the .NET 9 SDK + 8 runtime into TOOLDIR. Nothing is installed globally.
set -euo pipefail
mkdir -p "${1:-.tools}" && T=$(cd "${1:-.tools}" && pwd)
cd "$T"

mkdir -p node && (cd node && [ -f package.json ] || npm init -y >/dev/null) && (cd node && npm i --silent \
  @stoplight/spectral-cli @redocly/cli @apidevtools/swagger-parser @readme/openapi-parser \
  @seriousme/openapi-schema-validator @hyperjump/json-schema@1.18.0 @hyperjump/browser@1.6.0 yaml)

[ -d py ] || python3 -m venv py
py/bin/pip -q install -U openapi-spec-validator pyyaml

GOBIN=$T/go go install github.com/daveshanley/vacuum@latest
GOBIN=$T/go go install github.com/getkin/kin-openapi/cmd/validate@latest
GOBIN=$T/go go install github.com/speakeasy-api/openapi/cmd/openapi@latest

if ! command -v java >/dev/null || ! java -version >/dev/null 2>&1; then
  os=$(uname -s | sed 's/Darwin/mac/;s/Linux/linux/'); arch=$(uname -m | sed 's/arm64/aarch64/;s/x86_64/x64/')
  mkdir -p jdk && curl -sL "https://api.adoptium.net/v3/binary/latest/21/ga/$os/$arch/jdk/hotspot/normal/eclipse" | tar xz -C jdk --strip-components=1
fi
v=$(curl -s https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/maven-metadata.xml | grep -o '<release>[^<]*' | cut -d'>' -f2)
curl -sLo openapi-generator-cli.jar "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/$v/openapi-generator-cli-$v.jar"

if ! command -v dotnet >/dev/null; then
  curl -sLo dotnet-install.sh https://dot.net/v1/dotnet-install.sh
  bash dotnet-install.sh --channel 9.0 --install-dir "$T/dotnet" >/dev/null
  bash dotnet-install.sh --channel 8.0 --runtime dotnet --install-dir "$T/dotnet" >/dev/null
  export DOTNET_ROOT=$T/dotnet PATH=$T/dotnet:$PATH
fi
rm -rf dotnet-tools && dotnet tool install Microsoft.OpenApi.Hidi --tool-path "$T/dotnet-tools" >/dev/null
echo "tools installed in $T"
