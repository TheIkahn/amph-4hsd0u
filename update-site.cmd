@echo off
rem Copies the latest Amphoreus notes from the shared vault into the site and publishes them.
cd /d "%~dp0"
python -I sync_site.py "C:\Users\duke0\Documents\obsidian\DnD Shared Vault\Haydens Campaign\Amphoreus - Twelve Coreflames" content || goto :error
git add -A
git commit -m "Update notes" || echo Nothing new to publish.
git push || goto :error
echo.
echo Done. GitHub will rebuild the site in a minute or two.
pause
exit /b 0
:error
echo Something went wrong; see the message above.
pause
exit /b 1
