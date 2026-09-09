param([string]$ServiceName="PLCGateway")
Write-Host "Stop and remove $ServiceName using the same approved Windows service wrapper used during installation."
Write-Host "Do not delete configuration, logs, or SQL audit data during rollback."
