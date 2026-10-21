param()
if ($args.Count) { throw 'This fixed release accepts no seed or approval switches.' }
& (Join-Path $PSScriptRoot 'Operator.ps1') -Action start
