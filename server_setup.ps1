# Run on the MAIN warehouse PC only (the one with PostgreSQL installed).
# Lets the other PCs on the same network connect to PostgreSQL.
$ErrorActionPreference = 'Stop'
$pg = Get-ChildItem 'C:\Program Files\PostgreSQL' -Directory -ErrorAction SilentlyContinue |
      Sort-Object { [int]($_.Name -replace '\D', '') } | Select-Object -Last 1
if (-not $pg) { Write-Host 'PostgreSQL is not installed in C:\Program Files\PostgreSQL'; exit 1 }
$data = Join-Path $pg.FullName 'data'
$hba  = Join-Path $data 'pg_hba.conf'
$conf = Join-Path $data 'postgresql.conf'

# 1) allow PCs on the same local network (password required)
if (-not (Select-String -Path $hba -Pattern '^\s*host\s+all\s+all\s+samenet' -Quiet)) {
    Add-Content -Path $hba -Value "`r`nhost    all    all    samenet    scram-sha-256" -Encoding ASCII
    Write-Host 'pg_hba.conf: local network allowed'
} else { Write-Host 'pg_hba.conf: already OK' }

# 2) listen on the network, not only this PC
$c = Get-Content $conf
if (-not ($c -match "^\s*listen_addresses\s*=\s*'\*'")) {
    $c = $c -replace "^\s*#?\s*listen_addresses\s*=.*", "listen_addresses = '*'"
    Set-Content -Path $conf -Value $c -Encoding ASCII
    Write-Host 'postgresql.conf: listening on the network'
} else { Write-Host 'postgresql.conf: already OK' }

# 3) firewall: PostgreSQL port for the local network only
$port = 5432
$pl = (Get-Content $conf) | Where-Object { $_ -match '^\s*port\s*=\s*(\d+)' } | Select-Object -First 1
if ($pl -match '(\d+)') { $port = [int]$Matches[1] }
netsh advfirewall firewall delete rule name="PostgreSQL Warehouse" | Out-Null
netsh advfirewall firewall add rule name="PostgreSQL Warehouse" dir=in action=allow protocol=TCP localport=$port remoteip=localsubnet profile=any | Out-Null
Write-Host "Firewall: port $port open for the local network only"

# 4) restart PostgreSQL
Get-Service postgresql* | Restart-Service
Write-Host 'PostgreSQL restarted'

Write-Host ''
Write-Host "Port: $port"
Write-Host 'Write this address in the other PCs (Server IP):'
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254*' } |
  ForEach-Object { Write-Host ('   ' + $_.IPAddress + '   (' + $_.InterfaceAlias + ')') }
