@echo off
REM ============================================================
REM  PD1610 boot-chain READ-ONLY backup  (fh_loader / firehose)
REM  Usage:  run_readback.bat COM5
REM  Storage: UFS  (ro.boot.bootdevice = 624000.ufshc)
REM  Nothing is written to the device. Read + reset only.
REM ============================================================
setlocal
set PORT=%1
if "%PORT%"=="" (
  echo Usage: run_readback.bat COMx
  echo   e.g. run_readback.bat COM5
  exit /b 1
)

set QFIL=D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5
set FH=C:\qfilx\prog_ufs_firehose_8996_ddr.elf
set OUT=C:\qfilx\backup

if not exist "%FH%" (
  echo [X] UFS firehose programmer not found: %FH%
  exit /b 1
)
if not exist "%OUT%\readback_program.xml" (
  echo [X] readback_program.xml not found in %OUT%
  exit /b 1
)

echo ============================================================
echo  Port      : %PORT%
echo  Programmer: %FH%   (UFS)
echo  Output    : %OUT%
echo  Mode      : READ-ONLY (no write commands are sent)
echo ============================================================
echo.

echo [1/2] Uploading firehose programmer (Sahara) ...
"%QFIL%\QSaharaServer.exe" -u \\.\%PORT% -s 13:"%FH%"
if errorlevel 1 (
  echo.
  echo [X] Sahara upload failed.
  echo     - Is the device really in 9008 mode?
  echo     - Is the COM port number correct?
  echo     - Is the Qualcomm USB driver installed?
  exit /b 2
)
echo [OK] programmer loaded.
echo.

echo [2/2] Reading 22 partitions (272 MB, may take 3-8 minutes) ...
"%QFIL%\fh_loader.exe" --port=\\.\%PORT% --sendxml=readback_program.xml --convertprogram2read --search_path="%OUT%" --mainoutputdir="%OUT%" --memoryname=ufs --noprompt --zlpawarehost=1 --showpercentagecomplete --reset
set RC=%ERRORLEVEL%
echo.
echo fh_loader exit code: %RC%
echo.
echo --- output files ---
dir /b "%OUT%\backup_*.bin" 2>nul
echo ---------------------
echo If exit code is 0 and files above look right, Stage 0 is DONE.
echo Do NOT flash anything yet. Send the file list + sizes back for verification.
endlocal
