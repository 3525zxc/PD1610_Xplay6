@echo off
rem  Verify the extracted archive before flashing (Windows, no extra tools).
rem  Compare the printed hashes with sha256sums.txt.
setlocal
cd /d "%~dp0"
for %%F in (images\boot.img images\system.img images\recovery.img) do (
  if not exist "%%F" ( echo MISSING %%F & goto :done )
  echo.
  echo === %%F ===
  certutil -hashfile "%%F" SHA256 | findstr /r /c:"^[0-9a-fA-F][0-9a-fA-F]*$"
)
echo.
echo Compare the values above with sha256sums.txt
:done
echo.
pause
