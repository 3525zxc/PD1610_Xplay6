@echo off
REM  Write a boot image over EDL/9008 (bypasses fastboot "device is lock")
REM  Usage: write_boot_edl.bat flash_boot_test.xml 5
setlocal
set XML=%1
set PORT=%2
if "%XML%"=="" ( echo Usage: write_boot_edl.bat ^<xml^> [COM number] & exit /b 1 )
if "%PORT%"=="" set PORT=5
set N=%PORT:COM=%
set N=%N:com=%
set QFIL=D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5
set FH=D:\16\PD1610_81\scripts\prog_ufs_firehose_8996_ddr.elf
set SRC=D:\16\PD1610_81\work
echo === EDL write boot : %XML%  COM %N% ===
"%QFIL%\QSaharaServer.exe" -u %N% -s 13:"%FH%"
if errorlevel 1 ( echo [X] Sahara failed & exit /b 2 )
echo [OK] programmer loaded
REM  No --reset: soft reboot on this unit often hangs at the vivo logo with no USB.
REM  Stay in 9008 after writing; power-cycle manually (hold POWER 15s, then power on).
"%QFIL%\fh_loader.exe" --port=\\.\COM%N% --sendxml=%XML% --search_path="%SRC%" --memoryname=ufs --noprompt --showpercentagecomplete --zlpawarehost=1
echo.
echo fh_loader exit code: %ERRORLEVEL%
endlocal
