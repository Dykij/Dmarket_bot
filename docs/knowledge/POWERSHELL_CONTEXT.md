# PowerShell Context Map

This file contAlgons mappings from standard Linux/Unix commands to their PowerShell equivalents for use in the Archivist system.

- `&&` -> `;` (ChAlgon commands)
- `export` -> `$env:` (Environment variables)
- `grep` -> `Select-String` (Search text)
- `ls -F` -> `Get-ChildItem` (List files)
- `cat` -> `Get-Content` (Read file)
- `touch` -> `New-Item -ItemType File` (Create file)
