param([switch]$Reseed)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "[run-seed] Reading azd env values ..."
$envValues = azd env get-values --output json | ConvertFrom-Json
$env:SQL_SERVER_FQDN   = $envValues.SQL_SERVER_FQDN
$env:SQL_DATABASE_NAME = $envValues.SQL_DATABASE_NAME
$env:RESEED            = if ($Reseed) { '1' } else { '0' }
if (-not $env:SQL_SERVER_FQDN -or -not $env:SQL_DATABASE_NAME) {
    throw "SQL_SERVER_FQDN / SQL_DATABASE_NAME not in azd env. Did 'azd provision' complete?"
}
Write-Host "[run-seed] Target: $($env:SQL_SERVER_FQDN) / $($env:SQL_DATABASE_NAME)  (RESEED=$($env:RESEED))"
python -m pip install --quiet -r (Join-Path $here 'requirements.txt')
python (Join-Path $here 'seed.py')
