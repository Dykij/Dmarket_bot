
function Fix-Imports {
    param(
        [string]$Old,
        [string]$New
    )
    Write-Host "Fixing imports: $Old -> $New" -ForegroundColor Cyan
    Get-ChildItem -Path "src" -Recurse -Filter "*.py" | ForEach-Object {
        $content = Get-Content -Path $_.FullName -Raw -Encoding UTF8
        if ($content -match [regex]::Escape($Old)) {
            $content = $content -replace [regex]::Escape($Old), $New
            Set-Content -Path $_.FullName -Value $content -Encoding UTF8
            Write-Host "Updated: $($_.Name)" -ForegroundColor Green
        }
    }
}

function Start-Bot {
    Write-Host "Starting Bot..." -ForegroundColor Yellow
    $env:PYTHONPATH = $PWD
    python -m src.main
}

function Fix-Crash-Log {
    Write-Host "Fixing log_crash..." -ForegroundColor Cyan
    $path = "src/core/application.py"
    if (Test-Path $path) {
        $content = Get-Content -Path $path -Raw -Encoding UTF8
        # Fix the specific logging error
        $content = $content -replace '\.exception\("Critical error"\)', '.error("Critical application error", exc_info=True)'
        $content = $content -replace '\.log_crash\(', '.error('
        Set-Content -Path $path -Value $content -Encoding UTF8
        Write-Host "Fixed application.py" -ForegroundColor Green
    }
}
