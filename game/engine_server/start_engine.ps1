# Start the ControlQuest MPC engine in Docker (Windows PowerShell).
#   .\game\engine_server\start_engine.ps1
# The course image is found automatically: VS Code names it vsc-mpcrl26-exercises-<hash>,
# and the hash differs on every computer, so it must NOT be hard-coded here.
# Override with:  $env:CONTROLQUEST_IMAGE = "my-image"; .\start_engine.ps1
# Stop it with Ctrl+C.

$ErrorActionPreference = "Stop"
$image = $env:CONTROLQUEST_IMAGE
if (-not $image) {
    # newest local image whose name starts with vsc-mpcrl26-exercises-
    $image = docker images --format "{{.Repository}}" | Where-Object { $_ -like "vsc-mpcrl26-exercises-*" } | Select-Object -First 1
}
if (-not $image) {
    Write-Host "No course Docker image found (vsc-mpcrl26-exercises-...)." -ForegroundColor Red
    Write-Host "Build it by opening the course repository mpcrl26-exercises in its VS Code Dev Container,"
    Write-Host "or set the image name yourself:  `$env:CONTROLQUEST_IMAGE = '<image>'  (see: docker images)"
    exit 1
}
$port = $env:CONTROLQUEST_PORT
if (-not $port) { $port = "8000" }

# repository root = two folders above this script; mounted at /workspace
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

Write-Host "Starting MPC engine from image $image on http://127.0.0.1:$port"
docker run --rm -it -p "127.0.0.1:${port}:8000" -v "${repo}:/workspace" -w /workspace/game/engine_server $image python server.py --host 0.0.0.0 --port 8000
