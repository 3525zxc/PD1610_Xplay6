@echo off
REM ============================================================
REM  PD1610 对照组：写回官方 boot 并以相同方式(--reset)开机
REM  步骤: 1) 上传 programmer  2) 写官方 boot  3) 读回校验
REM        4) --reset  5) 高频轮询 fastboot/adb 枚举
REM  用法: control_official_boot.bat 5
REM ============================================================
setlocal
set PORT=%1
if "%PORT%"=="" set PORT=5
set N=%PORT:COM=%
set N=%N:com=%
set QFIL=D:\16\Qualcomm_Flash_Image_Loader_v2.0.3.5
set FH=D:\16\PD1610_81\scripts\prog_ufs_firehose_8996_ddr.elf
set SCR=D:\16\PD1610_81\scripts
set WORK=D:\16\PD1610_81\work
set PT=C:\qfilx\platform-tools\platform-tools

echo === [1/5] 上传 firehose programmer (COM %N%) ===
cd /d "%QFIL%"
timeout 12 QSaharaServer.exe -u %N% -s 13:"%FH%" > "%WORK%\sahara_control.log" 2>&1
type "%WORK%\sahara_control.log" | findstr /C:"completed" /C:"transferred" /C:"ERROR"
if not exist "%WORK%\sahara_control.log" ( echo [X] sahara log missing & exit /b 2 )

echo === [2/5] 写回官方 boot (整分区备份逐字节副本) ===
timeout 300 fh_loader.exe --port=\\.\COM%N% --sendxml="%SCR%\restore_boot_only.xml" --search_path="%WORK%" --memoryname=ufs --noprompt --zlpawarehost=1 --showpercentagecomplete 2>&1 | findstr /C:"Finished" /C:"ERROR" /C:"percent"

echo === [3/5] 读回 boot 校验 ===
timeout 300 fh_loader.exe --port=\\.\COM%N% --sendxml="%SCR%\readback_boot_only.xml" --convertprogram2read --search_path="%SCR%" --mainoutputdir="%WORK%\readback" --memoryname=ufs --noprompt --zlpawarehost=1 2>&1 | findstr /C:"Finished" /C:"ERROR"
python -c "a=open(r'%WORK%\readback\rb_boot_LUN4.bin','rb').read(); b=open(r'%WORK%\flash_boot_official_full.bin','rb').read(); c=open(r'D:\16\PD1610_81\backup\81_boot_LUN4.bin','rb').read(); print('readback==official payload:', a==b); print('readback==11-10 backup   :', a==c)"

echo === [4/5] reset 设备出 9008 ===
timeout 60 fh_loader.exe --port=\\.\COM%N% --reset --memoryname=ufs --noprompt 2>&1 | findstr /C:"Finished" /C:"ERROR" /C:"ACK"

echo === [5/5] 轮询枚举 (最多 240 s, 每 2 s) ===
set /a i=0
:loop
set /a i+=1
if %i% GTR 120 goto done
for /f "delims=" %%t in ('powershell -NoProfile -Command "Get-Date -Format HH:mm:ss"') do set TS=%%t
set FB=
set AD=
for /f "delims=" %%d in ('"%PT%\fastboot.exe" devices 2^>nul') do set FB=%%d
for /f "delims=" %%d in ('"%PT%\adb.exe" devices 2^>nul') do set AD=%%d
echo %TS% fastboot=[%FB%] adb=[%AD%]
echo %TS%|%FB%|%AD%>> "%WORK%\control_poll.log"
timeout /t 2 /nobreak > nul
goto loop
:done
echo === 轮询结束，日志: %WORK%\control_poll.log ===
endlocal
