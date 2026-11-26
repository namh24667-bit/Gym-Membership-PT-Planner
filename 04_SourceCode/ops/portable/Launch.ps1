param(
    [ValidateSet('serve','check','restart','stop','credentials','version')][string]$Mode = 'serve',
    [switch]$UseHttps,
    [switch]$NoBrowser,
    [pscredential]$RuntimeCredential,
    [ValidatePattern('^IronPulseTeam-[0-9a-f]{32}$')][string]$WorkerPipe
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runner = Join-Path $PSScriptRoot 'main.py'
$environment = '.venv'
$active = Join-Path $root 'instance\portable-venv.txt'
if (Test-Path -LiteralPath $active) {
    $environment = (Get-Content -Raw -LiteralPath $active).Trim()
    if ($environment -notmatch '^\.venv-team-[a-f0-9]{12}$') { throw 'Moi truong Python khong hop le.' }
}
$python = Join-Path $root ($environment + '\Scripts\python.exe')
$pipe = $null

try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Chay Setup-IronPulse.cmd truoc.' }
    if ($Mode -notin 'stop','credentials','version' -and
        ((Test-Path -LiteralPath (Join-Path $root 'instance\portable-update.lock')) -or
         (Test-Path -LiteralPath (Join-Path $root 'instance\portable-update-pending.json')))) { throw 'Dang cap nhat. Chay lai sau.' }
    if ($Mode -in 'credentials','version') {
        & $python -X utf8 -I -B $runner $Mode
        exit $LASTEXITCODE
    }
    $configuration = & $python -I -B $runner configuration
    if ($LASTEXITCODE -ne 0 -or $configuration.Count -ne 2) { throw 'Cau hinh local khong hop le.' }
    $login, $port = $configuration
    if ($WorkerPipe) {
        if ([Security.Principal.WindowsIdentity]::GetCurrent().Name -ine $login) { throw 'Sai danh tinh runtime.' }
        $pipe = [IO.Pipes.NamedPipeClientStream]::new('.', $WorkerPipe, [IO.Pipes.PipeAccessRights]'ReadWrite, Synchronize',
            'Asynchronous', 'Identification', 'None')
        $pipe.Connect(15000)
        $reader = [IO.StreamReader]::new($pipe)
        $writer = [IO.StreamWriter]::new($pipe)
        $writer.AutoFlush = $true
        $password = $reader.ReadLine()
        $start = [Diagnostics.ProcessStartInfo]::new($python)
        $start.UseShellExecute = $false
        $start.RedirectStandardInput = $true
        $start.RedirectStandardOutput = $true
        foreach ($argument in @('-I','-B',$runner,'runtime',$Mode)) { $start.ArgumentList.Add($argument) }
        if ($UseHttps) { $start.ArgumentList.Add('--https') }
        $worker = [Diagnostics.Process]::Start($start)
        try {
            $worker.StandardInput.WriteLine($password)
            $worker.StandardInput.Close()
            Remove-Variable password
            $line = $worker.StandardOutput.ReadLine()
            $writer.WriteLine($line)
            $pipe.Dispose()
            $worker.WaitForExit()
            if ($worker.ExitCode -ne 0) { Read-Host 'Nhan Enter de dong cua so loi'; exit 1 }
        } finally {
            if (-not $worker.HasExited) { $worker.Kill() }
            $worker.Dispose()
        }
        exit
    }
    $owner = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $app = ([Security.Principal.NTAccount]$login).Translate([Security.Principal.SecurityIdentifier])
    $acl = [IO.Pipes.PipeSecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule([IO.Pipes.PipeAccessRule]::new($owner, 'FullControl', 'Allow'))
    $acl.AddAccessRule([IO.Pipes.PipeAccessRule]::new($app, 'ReadWrite, Synchronize', 'Allow'))
    $name = 'IronPulseTeam-' + [guid]::NewGuid().ToString('N')
    $pipe = [IO.Pipes.NamedPipeServerStreamAcl]::Create($name, 'InOut', 1, 'Byte', 'Asynchronous',
        0, 0, $acl, 'None', [IO.Pipes.PipeAccessRights]0)
    $password = ''
    if ($Mode -ne 'stop') {
        $password = & $python -I -B $runner credentials --pipe
        if ($LASTEXITCODE -ne 0) { throw 'Can dung tai khoan Windows da chay Setup.' }
    }
    $pwsh = Join-Path $PSHOME 'pwsh.exe'
    $command = '"{0}" -NoProfile -File "{1}" -Mode {2} -WorkerPipe {3}' -f $pwsh, $PSCommandPath, $Mode, $name
    if ($UseHttps) { $command += ' -UseHttps' }
    if ($RuntimeCredential) {
        if ($RuntimeCredential.UserName -ine $login) { throw 'Sai tai khoan runtime duoc cau hinh.' }
        $workerArgs = $command.Substring(('"{0}" ' -f $pwsh).Length)
        Start-Process -FilePath $pwsh -ArgumentList $workerArgs -Credential $RuntimeCredential -LoadUserProfile -WindowStyle Hidden
    } else {
        Write-Host "Nhap mat khau Windows cua $login tai loi nhac runas."
        & "$env:SystemRoot\System32\runas.exe" '/profile' "/user:$login" $command
        if ($LASTEXITCODE -ne 0) { throw 'Windows runtime dang nhap that bai.' }
    }
    if (-not $pipe.WaitForConnectionAsync().Wait(20000)) { throw 'Runtime khong ket noi. Kiem tra quyen doc thu muc va Python.' }
    $send = [IO.StreamWriter]::new($pipe)
    $send.AutoFlush = $true
    $send.WriteLine($password)
    Remove-Variable password
    $reading = [IO.StreamReader]::new($pipe).ReadLineAsync()
    if (-not $reading.Wait(90000)) { throw 'Qua han doi preflight.' }
    $result = $reading.Result
    if ($result -cnotin @('READY','CHECK_PASS','STOPPED')) { throw 'Preflight that bai. Xem cua so runtime.' }
    Write-Host $result
    if ($result -eq 'READY') {
        $protocol = if ($UseHttps) { 'https' } else { 'http' }
        $url = $protocol + '://localhost:' + $port + '/login'
        Write-Host $url
        if (-not $NoBrowser) { Start-Process $url }
    }
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    exit 1
} finally {
    if ($pipe) { $pipe.Dispose() }
}
