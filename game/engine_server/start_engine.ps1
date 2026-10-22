# Start the ControlQuest MPC engine in Docker (Windows PowerShell).
#   .\game\engine_server\start_engine.ps1
# Override the image with:  $env:CONTROLQUEST_IMAGE = "my-image"; .\start_engine.ps1
# Stop it with Ctrl+C.

$ErrorActionPreference = "Stop"
$image = $env:CONTROLQUEST_IMAGE
if (-not $image) {
    $image = "vsc-mpcrl26-exercises-94d9982245bae36f409cb410a37b514aafe63fa52604de9d9dc9f0c9c94c729a"
}
$port = $env:CONTROLQUEST_PORT
if (-not $port) { $port = "8000" }

# repository root = two folders above this script; mounted at /workspace
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

Write-Host "Starting MPC engine from image $image on http://127.0.0.1:$port"
docker run --rm -it -p "127.0.0.1:${port}:8000" -v "${repo}:/workspace" -w /workspace/game/engine_server $image python server.py --host 0.0.0.0 --port 8000
