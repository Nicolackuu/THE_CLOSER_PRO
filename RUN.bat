@echo off
echo ========================================
echo THE CLOSER PRO - Lancement
echo ========================================
echo.

if not exist venv (
    echo ERREUR: Environnement virtuel non trouve
    echo Lancez d'abord INSTALL.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Demarrage de THE CLOSER PRO...
echo.

python main.py

pause
