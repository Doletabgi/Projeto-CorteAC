# Cria/atualiza o atalho do CorteAC na Area de Trabalho com a VERSAO no nome.
# Ex.: "CorteAC-1.6.11.lnk"  (mantem o icone embutido no .exe)
#
# Uso: clique com o botao direito -> "Executar com PowerShell" nesta pasta,
# ou no terminal:  powershell -ExecutionPolicy Bypass -File .\criar_atalho_windows.ps1

$ErrorActionPreference = 'Stop'
$pasta = Split-Path -Parent $MyInvocation.MyCommand.Definition
$exe = Join-Path $pasta 'CorteAC.exe'

if (-not (Test-Path $exe)) {
    Write-Host "CorteAC.exe nao encontrado nesta pasta: $pasta" -ForegroundColor Red
    exit 1
}

# Versao: arquivo versao.txt gerado no empacotamento; senao, versao do proprio .exe
$versao = $null
$arquivoVersao = Join-Path $pasta 'versao.txt'
if (Test-Path $arquivoVersao) {
    $versao = (Get-Content $arquivoVersao -Raw).Trim()
}
if ([string]::IsNullOrWhiteSpace($versao)) {
    $versao = (Get-Item $exe).VersionInfo.ProductVersion
}
if ([string]::IsNullOrWhiteSpace($versao)) { $versao = 'dev' }

$nome = "CorteAC-$versao.lnk"
$desktop = [Environment]::GetFolderPath('Desktop')

# Remove atalhos antigos do CorteAC na Area de Trabalho (CorteAC.lnk e CorteAC-*.lnk)
Get-ChildItem -Path $desktop -Filter 'CorteAC*.lnk' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

$atalho = Join-Path $desktop $nome
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($atalho)
$s.TargetPath = $exe
$s.WorkingDirectory = $pasta
$s.IconLocation = "$exe,0"
$s.Description = "CorteAC $versao - JobManager 2000 Reborn"
$s.Save()

Write-Host "Atalho criado: $nome" -ForegroundColor Green
Write-Host "  destino: $exe"
Write-Host "  area de trabalho: $desktop"
Write-Host "Se o icone ou o nome nao atualizarem, pressione F5 na Area de Trabalho."
