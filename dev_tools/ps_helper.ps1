function Safe-Read-File {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Path
    )
    try {
        if (-not (Test-Path $Path)) {
            Write-Error "File not found: $Path"
            return
        }
        Get-Content -Path $Path -Raw -ErrorAction Stop
    }
    catch {
        Write-Error "Failed to read file '$Path': $_"
    }
}

function Safe-Write-File {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$Path,
        [Parameter(Mandatory=$true)]
        [string]$Content,
        [switch]$Force
    )
    try {
        $Dir = Split-Path -Parent $Path
        if (-not (Test-Path $Dir)) {
            New-Item -ItemType Directory -Path $Dir -Force | Out-Null
        }
        Set-Content -Path $Path -Value $Content -Force:$Force -ErrorAction Stop
        Write-Host "Successfully wrote to $Path"
    }
    catch {
        Write-Error "Failed to write file '$Path': $_"
    }
}

function Safe-List-Files {
    [CmdletBinding()]
    param(
        [string]$Path = ".",
        [switch]$Recurse
    )
    try {
        Get-ChildItem -Path $Path -Recurse:$Recurse -ErrorAction Stop | Select-Object Name, FullName, Length, LastWriteTime
    }
    catch {
        Write-Error "Failed to list files in '$Path': $_"
    }
}

Export-ModuleMember -Function Safe-Read-File, Safe-Write-File, Safe-List-Files