param(
  [string]$HostName = "localhost",
  [string]$Database = "tienda_digital",
  [string]$User = "tienda_user",
  [string]$OutputDir = ".\backups"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$output = Join-Path $OutputDir "$Database`_$timestamp.sql"

Write-Host "Generando respaldo en $output"
mysqldump -h $HostName -u $User -p $Database > $output
Write-Host "Respaldo finalizado. Guarde el archivo en almacenamiento externo si es para recuperacion real."

