param([string[]]$Cases=@('control','13x','100pips','duck','london','gold','gap'),[string]$Batch='pilot27',
      [ValidateRange(120,3600)][int]$MaxTestSeconds=900,
      [switch]$CollectCompleted,[datetime]$CapturedAfter=[datetime]::MinValue,
      [string]$DestinationRoot='')
if($Batch -notmatch '^pilot[0-9a-z_]+$') {throw 'Invalid batch label'}
$ErrorActionPreference='Stop'
$project=Split-Path -Parent $PSScriptRoot
$terminal='C:\Program Files\Honor Pro MT5 Terminal\terminal64.exe'
$agentRoot='C:\Users\vish8\AppData\Roaming\MetaQuotes\Tester\90A3EE13DEA06374A8DE536622D95A3C'
# Capturas longas (anos) vão para fora do OneDrive via -DestinationRoot.
# Padrão: HD externo (D:), fora do disco do PC e do OneDrive; volta para o projeto se o D: não existir.
$defaultRoot=if(Test-Path 'D:\OneB\research') {'D:\OneB\research\vendor_indicator_research'} else {Join-Path $project 'output\vendor_indicator_research'}
$destination=if($DestinationRoot) {Join-Path $DestinationRoot $Batch} else {Join-Path $defaultRoot $Batch}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
if(Get-Process terminal64 -ErrorAction SilentlyContinue) { throw 'Close MT5 normally first; this script never kills the terminal or collects a running test.' }
if($CollectCompleted -and $CapturedAfter -eq [datetime]::MinValue) {throw 'CollectCompleted requires an explicit CapturedAfter cutoff'}
foreach($case in $Cases) {
  if($case -notmatch '^(control|13x|100pips|duck|london|gold|gap)(_(M1|M5|M10|M15|M30|H1))?$') {throw 'Unknown case'}
  $config=Join-Path $project "configs\mt5\${Batch}_$case.ini"
  $started=if($CollectCompleted) {$CapturedAfter} else {Get-Date}
  if(-not $CollectCompleted) {
    $process=Start-Process -FilePath $terminal -ArgumentList ('/config:"'+$config+'"') -WindowStyle Hidden -PassThru
    if(-not $process.WaitForExit($MaxTestSeconds*1000)) { throw "Timeout $case; terminal left untouched. Inspect manually." }
  }
  # MT5 may select another local agent when a visualizer occupies port 3000.
  # Resolve the actual agent by fresh run-specific files, never assume a port.
  $matchingAgents=@(Get-ChildItem -LiteralPath $agentRoot -Directory -Filter 'Agent-*' | Where-Object {
    $candidateFiles=@(Get-ChildItem -LiteralPath (Join-Path $_.FullName 'MQL5\Files') -Filter "${Batch}_${case}_*.csv" -ErrorAction SilentlyContinue)
    $candidateFiles.Count -eq 2 -and @($candidateFiles | Where-Object LastWriteTime -LT $started.AddSeconds(-2)).Count -eq 0
  })
  if($matchingAgents.Count -ne 1) {throw "Ambiguous or absent fresh local agent for $case"}
  $agent=$matchingAgents[0].FullName
  $files=Get-ChildItem -LiteralPath (Join-Path $agent 'MQL5\Files') -Filter "${Batch}_${case}_*.csv"
  if(-not $files -or ($files | Where-Object LastWriteTime -LT $started.AddSeconds(-2))) {throw "Missing or stale captures for $case"}
  foreach($file in $files) {Copy-Item -LiteralPath $file.FullName -Destination $destination}
  # Journals rotate at midnight: a test that crosses it has START in the
  # previous day's file and END in today's, so read both (in order).
  $logs=@($started.ToString('yyyyMMdd'),(Get-Date -Format yyyyMMdd)) | Select-Object -Unique |
    ForEach-Object {Join-Path $agent ('logs\'+$_+'.log')} | Where-Object {Test-Path -LiteralPath $_}
  # Keep a bounded journal excerpt; the agent journal is cumulative and an
  # earlier debug build produced millions of repeated readiness messages.
  $logs | ForEach-Object {Get-Content -LiteralPath $_ -Tail 2000} | Set-Content -LiteralPath (Join-Path $destination "$case.log") -Encoding utf8
  $journal=Get-Content -LiteralPath (Join-Path $destination "$case.log") -Raw
  $startIndex=$journal.LastIndexOf("AUDIT START: ${Batch}_${case}_")
  # Agent journals are cumulative; do not assign a previous case's warning to
  # the current test when the current start marker remains in the excerpt.
  if($startIndex -ge 0) {$journal=$journal.Substring($startIndex)}
  $unsupported=$journal -match 'aplique no gráfico H1'
  if(((-not $unsupported) -and $journal -notmatch ('AUDIT START: '+[regex]::Escape("${Batch}_${case}_"))) -or $journal -notmatch 'AUDIT END reason=1' -or $journal -notmatch 'Test passed in') {throw "Unconfirmed completion $case"}
  if($unsupported) {Write-Output "UNSUPPORTED TIMEFRAME $case; vendor requires H1. Not an economic test."}
  foreach($file in $files | Where-Object Name -Like '*_buffers.csv') {
    if($file.Length -lt 100) {throw "Empty capture $case; not valid"}
    python (Join-Path $project 'scripts\analyze_vendor_signal_audit.py') $file.FullName --output (Join-Path $destination ($file.BaseName+'.json'))
    if($LASTEXITCODE -ne 0) {throw "Analysis failed $case"}
  }
  foreach($file in $files | Where-Object Name -Like '*_objects.csv') {
    python (Join-Path $project 'scripts\analyze_vendor_objects.py') $file.FullName --output (Join-Path $destination ($file.BaseName+'.json'))
    if($LASTEXITCODE -ne 0) {throw "Object analysis failed $case"}
  }
  Write-Output "COMPLETED $case; raw data and log archived. Not a profitability test."
}
