$ErrorActionPreference = "Stop"

$instanceId = (Get-ItemProperty -LiteralPath "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL").SQLEXPRESS
if ($instanceId -ne "MSSQL17.SQLEXPRESS") {
    throw "Unexpected SQL Express instance ID: $instanceId"
}

$tcpRoot = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$instanceId\MSSQLServer\SuperSocketNetLib\Tcp"
$ipAll = "$tcpRoot\IPAll"

if (-not (Test-Path -LiteralPath $tcpRoot) -or -not (Test-Path -LiteralPath $ipAll)) {
    throw "SQL Express TCP configuration paths were not found."
}

Set-ItemProperty -LiteralPath $tcpRoot -Name Enabled -Value 1 -Type DWord
Set-ItemProperty -LiteralPath $ipAll -Name TcpDynamicPorts -Value "" -Type String
Set-ItemProperty -LiteralPath $ipAll -Name TcpPort -Value "14330" -Type String

Restart-Service -Name "MSSQL`$SQLEXPRESS" -Force

$service = Get-Service -Name "MSSQL`$SQLEXPRESS"
$tcp = Get-ItemProperty -LiteralPath $tcpRoot
$ports = Get-ItemProperty -LiteralPath $ipAll

if ($service.Status -ne "Running" -or $tcp.Enabled -ne 1 -or $ports.TcpPort -ne "14330") {
    throw "SQL Express TCP configuration did not complete successfully."
}

"SUCCESS"
