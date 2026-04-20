param(
    [string]$ApiConfig = "configs/api.yaml",
    [int]$MaxDatasets = 10,
    [int]$Workers = 1,
    [int]$Seed = 42
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python interpreter not found: $PythonExe"
}

if (-not $env:OPENAI_API_KEY) {
    throw "Missing environment variable OPENAI_API_KEY"
}

$env:PYTHONUTF8 = "1"

Push-Location $RepoRoot
try {
    & $PythonExe -m src.app.run_benchmark `
        --models-dir configs/models `
        --benchmark-config configs/benchmark/glycoforge_648.yaml `
        --api-config $ApiConfig `
        --only-models qwen3.5-122b-a10b.yaml `
        --max-datasets $MaxDatasets `
        --workers $Workers `
        --seed $Seed
}
finally {
    Pop-Location
}
