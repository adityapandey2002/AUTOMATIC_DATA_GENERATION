# Offline test suite for the backend. Pure-unit: no network, no API keys, no
# Postgres, no microphone. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File backend\run_tests.ps1
#
# Dev consoles are cp1252 and the tests print Devanagari, so UTF-8 must be
# forced or Python raises UnicodeEncodeError mid-run. There is exactly one
# working interpreter: backend\venv\Scripts\python.exe (3.14).

$env:PYTHONIOENCODING = "utf-8"
$py = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Error "interpreter not found: $py"
    exit 2
}

# Offline suites only. Live/integration suites (test_groq_live, test_echo_live,
# test_bhashini, integration_test) need keys, a fixture, or a running backend
# and are deliberately excluded.
$suites = @(
    "test_local_fill.py",
    "test_asr_failover.py",
    "test_groq_retry.py",
    "test_enrichment.py",
    "test_protocol.py",
    "test_repository.py",
    "test_name_saved.py"
)

Push-Location $PSScriptRoot
$failed = @()
foreach ($suite in $suites) {
    Write-Output "===== $suite ====="
    & $py $suite
    if ($LASTEXITCODE -ne 0) { $failed += $suite }
}
Pop-Location

if ($failed.Count -gt 0) {
    Write-Output "FAILED: $($failed -join ', ')"
    exit 1
}
Write-Output "ALL OFFLINE SUITES PASSED"
exit 0
