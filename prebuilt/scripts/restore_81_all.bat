@echo off
REM ============================================================
REM  PD1610 Android 8.1 FULL RESTORE (47 partitions / 3.67 GB)
REM  Usage: restore_81_all.bat 5      (COM number of 9008 port)
REM  Source: D:\16\PD1610_81\backup\81_*.bin
REM  No --reset: device stays in 9008, power-cycle manually.
REM ============================================================
setlocal
set PORT=%1
if "%PORT%"=="" ( echo Usage: restore_81_all.bat [COM number] & exit /b 1 )
set N=%PORT:COM=%
set N=%N:com=%
set QFIL=D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5
set FH=D:\16\PD1610_81\scripts\prog_ufs_firehose_8996_ddr.elf
set SRC=D:\16\PD1610_81\scripts
set BAK=D:\16\PD1610_81\backup
if not exist "%FH%" ( echo [X] firehose missing & exit /b 1 )
echo ============================================================
echo  RESTORE 8.1 FULL   COM %N%   47 partitions / 3.67 GB
echo ============================================================
"%QFIL%\QSaharaServer.exe" -u %N% -s 13:"%FH%"
if errorlevel 1 ( echo [X] Sahara failed & exit /b 2 )
echo [OK] programmer loaded
"%QFIL%\fh_loader.exe" --port=\\.\COM%N% --sendxml=restore_81_all.xml --search_path="%BAK%" --memoryname=ufs --noprompt --showpercentagecomplete --zlpawarehost=1
echo.
echo fh_loader exit code: %ERRORLEVEL%
echo Device stays in 9008; power-cycle manually (do NOT soft-reset).
endlocal
