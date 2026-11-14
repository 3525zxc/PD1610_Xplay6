@echo off
REM ============================================================
REM  PD1610 Android 8.1 full READ-ONLY partition backup
REM  Usage: readback_81.bat 5       (COM number of 9008 port)
REM  Output: D:\16\PD1610_81\backup\81_*.bin
REM  Nothing is written to the device. Read + reset only.
REM ============================================================
setlocal
set PORT=%1
if "%PORT%"=="" ( echo Usage: readback_81.bat [COM number] & exit /b 1 )
set N=%PORT:COM=%
set N=%N:com=%
set QFIL=D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5
set FH=D:\16\PD1610_81\scripts\prog_ufs_firehose_8996_ddr.elf
set SRC=D:\16\PD1610_81\scripts
set OUT=D:\16\PD1610_81\backup

if not exist "%FH%" ( echo [X] firehose programmer missing: %FH% & exit /b 1 )
echo ============================================================
echo  PD1610 8.1 READ-ONLY BACKUP   COM %N%
echo  Output : %OUT%
echo ============================================================

echo [1/2] Uploading firehose programmer ...
"%QFIL%\QSaharaServer.exe" -u %N% -s 13:"%FH%"
if errorlevel 1 ( echo [X] Sahara failed & exit /b 2 )
echo [OK] programmer loaded

echo [2/2] Reading partitions ...
"%QFIL%\fh_loader.exe" --port=\\.\COM%N% --sendxml=readback_81_all.xml --convertprogram2read --search_path="%SRC%" --mainoutputdir="%OUT%" --memoryname=ufs --noprompt --zlpawarehost=1 --showpercentagecomplete --reset
echo.
echo fh_loader exit code: %ERRORLEVEL%
echo --- output files ---
dir /b "%OUT%\81_*.bin" 2>nul
echo ---------------------
endlocal
