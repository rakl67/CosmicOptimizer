@echo off
taskkill /F /FI "IMAGENAME eq SystemSettings.exe"
echo
net stop wuauserv
net stop UsoSvc
echo
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services" /v "wuauserv" /t REG_DWORD /d "4" /f
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services" /v "WaaSMedicSvc" /t REG_DWORD /d "4" /f
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services" /v "UsoSvc" /t REG_DWORD /d "4" /f
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services" /v "BITS" /t REG_DWORD /d "4" /f
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services" /v "DoSvc" /t REG_DWORD /d "4" /f

schtasks /change /TN "Microsoft\Windows\WindowsUpdate\DoNotConnectToWindowsUpdateInternetLocations" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\WindowsUpdate\SetDisableUXWUAccess" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\WindowsUpdate\ExcludeWUDriversInQualityUpdate" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\WindowsUpdate\AU\NoAutoUpdate" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\UpdateOrchestrator\Schedule Scan Static Task" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\UpdateOrchestrator\Start Oobe Expedite Work" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\UpdateOrchestrator\Schedule Scan" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\UpdateOrchestrator\USO_UxBroker" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\UpdateOrchestrator\UpdateModelTask" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\WaaSMedic\PerformRemediation" /DISABLE > NUL 2>&1
schtasks /change /TN "Microsoft\Windows\WindowsUpdate\Scheduled Start" /DISABLE > NUL 2>&1

rd /s /q C:\Windows\SoftwareDistribution
md C:\Windows\SoftwareDistribution
echo.
pause