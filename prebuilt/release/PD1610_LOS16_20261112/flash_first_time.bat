@echo off
rem  First-time flash from stock Funtouch 8.1: forces the required data wipe.
call "%~dp0flash_all.bat" --wipe %*
