@echo off
REM ============================================================
REM  PD1610 EDL read-only: dump devinfo (LUN4 start 882954, 4096B)
REM  Usage: read_devinfo_edl.bat [COM number]
REM  No write, no reset. Device stays in 9008 after read.
REM ============================================================
setlocal
set N=%1
if "%N%"=="" ( echo Usage: read_devinfo_edl.bat [COM number] & exit /b 1 )
set N=%N:COM=%
set N=%N:com=%
set QFIL=D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5
set FH=D:\16\PD1610_81\scripts\prog_ufs_firehose_8996_ddr.elf
set SRC=D:\16\PD1610_81\work

echo ============================================================
echo  READ devinfo   COM%N%
echo ============================================================
if not exist "%QFIL%\QSaharaServer.exe" ( echo [X] QSaharaServer missing & exit /b 3 )
if not exist "%FH%" ( echo [X] programmer elf missing & exit /b 3 )

echo [1/2] Sahara upload programmer ...
"%QFIL%\QSaharaServer.exe" -u %N% -s 13:"%FH%"
if errorlevel 1 ( echo [X] Sahara failed & exit /b 2 )
echo [OK] programmer loaded

echo.
echo [2/2] reading devinfo ...
"%QFIL%\fh_loader.exe" --port=\\.\COM%N% --sendxml=readback_devinfo.xml --search_path="%SRC%" --memoryname=ufs --noprompt --showpercentagecomplete --zlpawarehost=1 --convertprogram2read
echo.
echo fh_loader exit code: %ERRORLEVEL%
if exist "%SRC%\rb_devinfo_LUN4.bin" (
  echo [OK] dumped: %SRC%\rb_devinfo_LUN4.bin
) else (
  echo [X] no output file
)
echo --- end (device still in 9008) ---
endlocal
