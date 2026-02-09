$path = "C:\Users\west2\.openclaw\openclaw.json"
(Get-Content $path) -replace 'google/gemini-3-flash-preview', 'google/gemini-3-pro-preview' | Set-Content $path
Write-Host "MAIN CONFIG: Switched to Gemini-3-PRO" -ForegroundColor Cyan
