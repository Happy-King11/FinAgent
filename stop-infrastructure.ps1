$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
docker compose --env-file infrastructure.env -f docker-compose.infrastructure.yml down
