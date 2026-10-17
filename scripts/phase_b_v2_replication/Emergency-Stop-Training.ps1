param([Parameter(Mandatory=$true)][ValidateSet(2027,2028)][int]$Seed)
& (Join-Path $PSScriptRoot 'Operator.ps1') -Seed $Seed -Action emergency-stop
