@echo off
rem ===========================================================================
rem  PD1610 / vivo Xplay6  --  LineageOS 16.0 UNOFFICIAL  --  flash helper
rem  Build 2026-11-12 (system = sys13, boot = boot_pddiag5)
rem
rem  HOW TO USE (Windows)
rem    1. Unzip this archive with ALL files (do not flash from inside the zip).
rem    2. Unlock the bootloader FIRST (devinfo +0x10 = 0xFF on this device).
rem    3. Boot the phone into fastboot and connect USB (driver: "Android
rem       Bootloader Interface").
rem    4. Double-click flash_all.bat, answer the wipe question.
rem       --wipe      : wipe userdata + cache WITHOUT asking (first flash from
rem                    stock Funtouch 8.1 MUST wipe, encrypted /data cannot
rem                    be mounted by this ROM; unlock also needs one erase).
rem       --recovery  : additionally flash images/recovery.img (optional,
rem                    this Lineage recovery is NOT validated on PD1610).
rem       --help      : show this text.
rem    5. First boot takes ~40 s. Do not interrupt.
rem
rem  Flashed partitions: boot, system [, recovery] [, userdata/cache erase].
rem  NOT touched: aboot, xbl, modem, persist, dsp, devinfo, misc.
rem
rem  If any command fails with "AdbWriteEndpointSync failed" or
rem  "Write to device failed (no link)": unplug/replug the USB cable while
rem  the phone stays in fastboot, then run this script again.
rem
rem  STATUS / KNOWN ISSUES -- DEVELOPMENT BUILD, NOT A FINAL RELEASE
rem   Verified on one PD1610: first boot ~40 s, setup wizard, WiFi enabled and
rem   scanning APs, audio, camera provider HAL, fingerprint, bluetooth,
rem   sensors, keymaster/keystore, gnss, OMX all register and run.
rem   Known broken / unfinished:
rem    - Camera reports 0 devices (camera apps cannot shoot yet).
rem    - xtwifi-inet-agent fails: missing libcurl.so (XTRA download only).
rem    - SELinux is permissive; avc denials not yet collected/converged.
rem    - Diagnostic code is STILL in this build: boot.img init writes a
rem      first-boot marker to a raw block device, init rc has kmsg markers,
rem      a disabled 120 s watchdog and a temporary "pd1610-crypto-fix"
rem      action. They are harmless on PD1610 but MUST be removed + retested
rem      before any public release.
rem   Backup your partitions first. Never flash a locked bootloader.
rem ===========================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "FB=%~dp0tools\fastboot.exe"
set "WIPE="
set "DORECOVERY="
set "TMPFB=%TEMP%\pd1610_fastboot.txt"

:parse
if "%~1"=="" goto :parsed
if /i "%~1"=="--wipe" set "WIPE=1"
if /i "%~1"=="--recovery" set "DORECOVERY=1"
if /i "%~1"=="--help" goto :usage
if /i "%~1"=="-h" goto :usage
shift
goto :parse
:parsed

echo.
echo ============================================================
echo  PD1610 / vivo Xplay6 - LineageOS 16.0 UNOFFICIAL
echo  Build 2026-11-12  ^|  sys13 system + verified boot
echo ============================================================
echo.

if not exist "images\boot.img" goto :missing
if not exist "images\system.img" goto :missing
if not exist "%FB%" goto :missing

rem ---- device present? -----------------------------------------------------
"%FB%" devices > "%TMPFB%" 2>&1
set "FBDEVS="
for /f "tokens=1,2" %%A in ('type "%TMPFB%"') do (
  if /i "%%B"=="fastboot" set "FBDEVS=!FBDEVS! %%A"
)
if "!FBDEVS!"=="" (
  echo ERROR: no device in fastboot mode.
  echo   - power off, hold Volume Down + USB to enter fastboot
  echo   - install the "Android Bootloader Interface" USB driver
  goto :fail
)
echo  Device(s) in fastboot:!FBDEVS!

rem ---- endpoint sanity (a stuck endpoint sends 1.8 GB in one block) --------
"%FB%" getvar max-download-size > "%TMPFB%" 2>&1
findstr /i /c:"FAILED" "%TMPFB%" >nul && (
  echo ERROR: fastboot cannot talk to the device.
  echo   Unplug/replug the USB cable, keep the phone in fastboot, retry.
  goto :fail
)
findstr /i /c:"max-download-size" "%TMPFB%" >nul || (
  echo ERROR: unexpected getvar result:
  type "%TMPFB%"
  goto :fail
)
for /f "tokens=1,*" %%A in ('type "%TMPFB%"') do echo  %%A %%B

rem ---- wipe question -------------------------------------------------------
if defined WIPE goto :wipeset
echo.
echo  IMPORTANT: flashing from stock Funtouch 8.1 requires erasing userdata.
echo             Encrypted /data will not mount otherwise, and the unlock
echo             itself only takes effect after one erase.
set "ANS="
set /p "ANS=Erase userdata + cache now? [y/N] "
if /i "!ANS!"=="y" set "WIPE=1"
if /i "!ANS!"=="yes" set "WIPE=1"
:wipeset
if defined WIPE (echo  Mode: WIPE userdata/cache) else (echo  Mode: KEEP userdata/cache)

echo.
echo  Starting flash. Keep the cable connected, do NOT unplug.
echo.

echo  [1/3] boot.img ...
"%FB%" flash boot images\boot.img
if errorlevel 1 goto :flashfail

echo  [2/3] system.img  ^(Android sparse, 4 chunks, ~60 s^) ...
"%FB%" flash system images\system.img
if errorlevel 1 goto :flashfail

if defined DORECOVERY (
  echo  [opt] recovery.img ...
  "%FB%" flash recovery images\recovery.img
  if errorlevel 1 goto :flashfail
)

if defined WIPE (
  echo  [3/3] erasing userdata + cache ...
  "%FB%" erase userdata
  if errorlevel 1 goto :flashfail
  "%FB%" erase cache
) else (
  echo  [3/3] wipe skipped.
)

echo  Rebooting ... first boot takes about 40 seconds.
"%FB%" reboot
echo.
echo  DONE. Verify with:  tools\adb.exe shell getprop sys.boot_completed
echo  Expected result: 1
goto :end

:missing
echo ERROR: missing file. Make sure you EXTRACTED the whole zip first.
echo   images\boot.img, images\system.img, tools\fastboot.exe
goto :fail

:flashfail
echo.
echo ERROR: fastboot failed.
echo   If the error mentions AdbWriteEndpointSync / "no link" / timeout,
echo   unplug and replug the USB cable (phone stays in fastboot) and retry.
echo   Do NOT power-cycle unless the phone is completely unresponsive.
goto :fail

:usage
echo  Usage: flash_all.bat [--wipe] [--recovery] [--help]
echo    --wipe      erase userdata + cache without asking
echo    --recovery  also flash recovery.img (unvalidated Lineage recovery)
goto :end

:fail
echo.
echo  Flash aborted.
exit /b 1

:end
echo.
pause
exit /b 0
