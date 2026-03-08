# Dashboard Launcher (Tray)

## What it does
- Double-click once: start local dashboard service in background and open browser.
- Double-click again: if already running, just reopen browser.
- Tray icon menu: `Open Dashboard` / `Exit`.
- `Exit` will stop the service process started by the launcher.

## Build EXE
Run:

```bat
Launcher\build_launcher_exe.bat
```

Output:

```text
Launcher\dist\DashboardLauncher.exe
```

## Install Guide EXE
Run:

```bat
Launcher\build_install_guide_exe.bat
```

Output:

```text
Launcher\dist\InstallGuide.exe
```

Install guide flow:
- Check Chrome first (open official site or exit when missing)
- Check Python version (exit / show install command / continue with risk)
- Install/repair environment dependencies
- Open XHS + Bilibili login windows
- Prompt user to keep login pages open for at least 10 seconds before closing

## Notes
- This launcher expects the project virtual environment to exist:
  - `venv\Scripts\python.exe`
- Existing BAT files are not modified or removed.
