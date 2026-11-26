$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath "infrastructure.env")) {
    Copy-Item -LiteralPath "infrastructure.env.example" -Destination "infrastructure.env"
}

docker compose --env-file infrastructure.env -f docker-compose.infrastructure.yml up -d --build
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
docker compose --env-file infrastructure.env -f docker-compose.infrastructure.yml ps
