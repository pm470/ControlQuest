# Start the ControlQuest MPC engine in Docker (Windows PowerShell).
#   .\game\engine_server\start_engine.ps1
# Override the image with:  $env:CONTROLQUEST_IMAGE = "my-image"; .\start_engine.ps1
# Stop it with Ctrl+C.

$ErrorActionPreference = "Stop"
$image = $env:CONTROLQUEST_IMAGE
if (-not $image) {
    $image = "vsc-mpcrl26-exercises-570cc587851b7c4c296579abda9e2ed1f22a62772feeee307a76615826aa7aad"
}
$port = $env:CONTROLQUEST_PORT
if (-not $port) { $port = "8000" }

# repository root = two folders above this script; mounted at /workspace
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

Write-Host "Starting MPC engine from image $image on http://127.0.0.1:$port"
docker run --rm -it -p "127.0.0.1:${port}:8000" -v "${repo}:/workspace" -w /workspace/game/engine_server $image python server.py --host 0.0.0.0 --port 8000
