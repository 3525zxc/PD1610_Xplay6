@echo off
REM ===========================================================================
REM  PD1610 BLM RAM log capture over EDL Firehose peek -- READ ONLY
REM
REM  Prerequisite: device is in 9008 / Qualcomm HS-USB QDLoader mode
REM  (adb reboot edl, or power off + VolUp+VolDown + USB).
REM  Usage: blm_capture_edl.bat 5
REM
REM  Reads 0x40000 bytes at physical 0x42100000 in 0x10000 chunks,
REM  writes flash_log\blm_ram.bin, prints BLM diagnosis, then resets device.
REM  No partition is written. Only <peek> and a final power reset are sent.
REM ===========================================================================
setlocal
set COM=%1
if "%COM%"=="" (
  echo Usage: blm_capture_edl.bat [COM number]  e.g. blm_capture_edl.bat 5
  exit /b 1
)
set PY=C:\Users\Tse\.workbuddy\binaries\python\versions\3.14.3\python.exe
set ROOT=D:\xplay6\evidence\kernel_re\out\stage2\bootloop_monitor
set OUT=%ROOT%\flash_log\blm_ram.bin
set WD=%ROOT%\edl_probe

if not exist "%PY%"   ( echo [X] python missing   & exit /b 1 )
if not exist "%ROOT%\tools\blm_firehose_peek.py" ( echo [X] peek tool missing & exit /b 1 )

echo === BLM EDL PEEK CAPTURE COM %COM% ===
"%PY%" "%ROOT%\tools\blm_firehose_peek.py" --com %COM% --address 0x42100000 --size 0x40000 --chunk 0x10000 --reset --out "%OUT%" --workdir "%WD%"
if errorlevel 1 (
  echo [X] peek failed - device may still be in firehose mode; re-enter 9008 and retry
  exit /b 2
)

echo === BLM DIAGNOSIS ===
"%PY%" "%ROOT%\tools\blm_read.py" --input "%OUT%" --already-region
echo === DONE ===
endlocal
