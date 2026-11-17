cls
echo Включение полноэкранной оптимизации
reg add "HKCU\System\GameConfigStore" /v "GameDVR_DSEBehavior" /t REG_DWORD /d "2" /f >nul 2>&1
reg add "HKCU\System\GameConfigStore" /v "GameDVR_DXGIHonorFSEWindowsCompatible" /t REG_DWORD /d "1" /f >nul 2>&1
reg add "HKCU\System\GameConfigStore" /v "GameDVR_EFSEFeatureFlags" /t REG_DWORD /d "0" /f >nul 2>&1
reg add "HKCU\System\GameConfigStore" /v "GameDVR_FSEBehavior" /t REG_DWORD /d "2" /f >nul 2>&1
reg add "HKCU\System\GameConfigStore" /v "GameDVR_FSEBehaviorMode" /t REG_DWORD /d "2" /f >nul 2>&1
reg add "HKCU\System\GameConfigStore" /v "GameDVR_HonorUserFSEBehaviorMode" /t REG_DWORD /d "1" /f >nul 2>&1
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v "__COMPAT_LAYER" /t REG_SZ /d "~ DISABLEDXMAXIMIZEDWINDOWEDMODE" /f >nul 2>&1
reg add "HKCU\System\GameBar" /v "GamePanelStartupTipIndex" /t REG_DWORD /d "3" /f  >nul 2>&1
reg add "HKCU\System\GameBar" /v "ShowStartupPanel" /t REG_DWORD /d "0" /f >nul 2>&1
reg add "HKCU\System\GameBar" /v "UseNexusForGameBarEnabled" /t REG_DWORD /d "0" /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\WindowsRuntime\ActivatableClassId\Windows.Gaming.GameBar.PresenceServer.Internal.PresenceWriter" /v "ActivationType" /t REG_DWORD /d "0" /f >nul 2>&1
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR" /v "AllowGameDVR" /t REG_DWORD /d "0" /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\PolicyManager\default\ApplicationManagement\AllowGameDVR" /v "value" /t REG_DWORD /d "0" /f >nul 2>&1
reg add "HKCU\System\GameConfigStore" /v "GameDVR_Enabled" /t REG_DWORD /d "0" /f >nul 2>&1
reg add "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR" /v "AppCaptureEnabled" /t REG_DWORD /d "0" /f >nul 2>&1
timeout /t 1 /nobreak > NUL