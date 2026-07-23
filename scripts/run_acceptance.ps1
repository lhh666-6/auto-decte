$ErrorActionPreference = "Continue"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$artifactDir = Join-Path $repoRoot "artifacts\acceptance\$runId"
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

$env:ACCEPTANCE_RUN_ID = $runId
$env:ACCEPTANCE_ARTIFACT_DIR = $artifactDir

Write-Host "Acceptance run: $runId"
Write-Host "Artifacts: $artifactDir"

uv run pytest tests/acceptance -v --tb=long --junitxml="$artifactDir\junit.xml"
$pytestExit = $LASTEXITCODE

uv run python scripts/build_acceptance_summary.py $artifactDir
$summaryExit = $LASTEXITCODE

uv run ruff check tests/acceptance scripts/build_acceptance_summary.py
$ruffExit = $LASTEXITCODE

Write-Host ""
Write-Host "Report: $artifactDir\summary.md"
Write-Host "JUnit: $artifactDir\junit.xml"

if ($pytestExit -ne 0 -or $summaryExit -ne 0 -or $ruffExit -ne 0) {
    exit 1
}
exit 0
