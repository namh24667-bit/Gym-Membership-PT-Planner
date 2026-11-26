param(
    [string]$Instance = 'SQLEXPRESS',
    [string]$Database = 'IronPulse_CleanDemoQA',
    [string]$RuntimeAccount = 'IronPulseTeamApp',
    [int]$Port = 5443,
    [string]$Python,
    [string]$OfflineWheels,
    [switch]$ConfirmNew
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runner = Join-Path $PSScriptRoot 'main.py'
$config = Join-Path $root 'instance\portable.json'
$venv = Join-Path $root '.venv\Scripts\python.exe'

try {
    if (-not (Test-Path -LiteralPath (Join-Path $root 'package-manifest.json'))) {
        throw 'Giai nen ZIP ban kiem thu vao thu muc rieng truoc khi chay Setup.'
    }
    if (-not $Python) {
        $sharedPython = Join-Path $env:ProgramFiles 'Python312\python.exe'
        if (Test-Path -LiteralPath $sharedPython) { $Python = $sharedPython }
        else {
            $py = Get-Command py.exe -ErrorAction SilentlyContinue
            if (-not $py) { throw 'Can Python 3.12 x64, cai cho tat ca nguoi dung Windows.' }
            $Python = & $py.Source -3.12 -c "import sys; print(sys.executable)"
        }
    }
    if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { throw 'Khong tim thay Python 3.12 x64.' }
    & $Python -I -c "import sys,struct; raise SystemExit(sys.version_info[:2] != (3,12) or struct.calcsize('P') != 8)"
    if ($LASTEXITCODE -ne 0) { throw 'Can Python 3.12 x64.' }
    if (-not (Get-OdbcDriver -Name 'ODBC Driver 18 for SQL Server' -Platform '64-bit' -ErrorAction SilentlyContinue)) {
        throw 'Can cai Microsoft ODBC Driver 18 x64.'
    }
    & $Python -X utf8 -I -B (Join-Path $PSScriptRoot 'release.py') verify-dir
    if ($LASTEXITCODE -ne 0) { throw 'Goi ban kiem thu khong vuot kiem tra SHA-256.' }
    if (-not (Test-Path -LiteralPath $config) -and -not $ConfirmNew) {
        $value = Read-Host "SQL instance [$Instance], nhap MSSQLSERVER neu la default instance"
        if ($value.Trim()) { $Instance = $value.Trim() }
        $value = Read-Host "Database QA moi [$Database]"
        if ($value.Trim()) { $Database = $value.Trim() }
        $value = Read-Host "Ten tai khoan Windows tieu chuan rieng [$RuntimeAccount]"
        if ($value.Trim()) { $RuntimeAccount = $value.Trim() }
        $value = Read-Host "Cong loopback [$Port]"
        if ($value.Trim()) { $Port = [int]$value.Trim() }
        Write-Host "Setup se tao $Database va cap quyen toi thieu chi cho $env:COMPUTERNAME\$RuntimeAccount."
        if ((Read-Host 'Nhap CAI DAT de tiep tuc') -cne 'CAI DAT') { throw 'Setup da huy.' }
    }
    if ($RuntimeAccount -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$') { throw 'Ten tai khoan Windows khong hop le.' }
    $reuse = Test-Path -LiteralPath $config
    if (-not $reuse) {
        if ($RuntimeAccount -ieq $env:USERNAME) { throw 'Can tai khoan runtime rieng voi tai khoan setup.' }
        $account = $env:COMPUTERNAME + '\' + $RuntimeAccount
        $sid = ([Security.Principal.NTAccount]$account).Translate([Security.Principal.SecurityIdentifier]).Value
        & "$env:SystemRoot\System32\icacls.exe" $root /grant ('*' + $sid + ':(OI)(CI)(RX)') | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Khong cap duoc quyen doc thu muc cho runtime.' }
    }
    if (-not (Test-Path -LiteralPath $venv)) {
        & $Python -I -m venv (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Khong tao duoc .venv trong thu muc nay.' }
    }
    if (-not $reuse) {
        $packageArgs = @('--disable-pip-version-check','--require-hashes','-r',(Join-Path $root 'requirements-team.lock'))
        if ($OfflineWheels) { $packageArgs += @('--no-index','--find-links',$OfflineWheels) }
        & $venv -X utf8 -I -m pip install @packageArgs
        if ($LASTEXITCODE -ne 0) { throw 'Cai thu vien that bai. Kiem tra Internet hoac dung -OfflineWheels.' }
    }
    & $venv -X utf8 -I -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency hien tai khong tuong thich.' }
    & $venv -X utf8 -I -B $runner setup --instance $Instance --database $Database --account $RuntimeAccount --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Setup SQL that bai. Giu nguyen database de kiem tra.' }
    Write-Host 'Buoc tiep theo la Mo-IronPulse.cmd --check, sau do Mo-IronPulse.cmd.'
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
}
