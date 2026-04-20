# GlycoForge 648 小规模评测（示例）。在项目根目录执行: .\scripts\run_benchmark_glycoforge_kimi.ps1
# 需要: data\glycoforge_benchmark_648 下存在 gf_case_* 数据集目录；并配置好 API（如 configs\api.local.yaml）。

param(
    [string]$ApiConfig = "configs/api.local.yaml",
    [int]$MaxDatasets = 5,
    [int]$Workers = 2,
    [string]$ModelYaml = "kimi-k2.5.yaml"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$env:PYTHONUTF8 = "1"

python -m src.app.run_benchmark `
    --models-dir configs/models `
    --benchmark-config configs/benchmark/glycoforge_648.yaml `
    --only-models $ModelYaml `
    --max-datasets $MaxDatasets `
    --api-config $ApiConfig `
    --workers $Workers
