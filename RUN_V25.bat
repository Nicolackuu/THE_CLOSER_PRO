@echo off
echo ====================================================================
echo THE CLOSER PRO V25 - ELITE LAUNCHER
echo ====================================================================
echo.

REM Activer l'environnement virtuel
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [OK] Environnement virtuel active
) else (
    echo [ERREUR] Environnement virtuel non trouve
    echo Executez d'abord INSTALL_V25.bat
    pause
    exit /b 1
)

echo.
echo [LANCEMENT] Demarrage de THE CLOSER PRO V25...
echo.

REM Lancer le système V25
python main_v25.py

echo.
echo [FIN] Session terminee
pause
