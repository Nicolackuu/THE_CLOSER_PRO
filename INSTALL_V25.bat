@echo off
echo ====================================================================
echo THE CLOSER PRO V25 - ELITE INSTALLATION
echo ====================================================================
echo.

REM Vérifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou n'est pas dans le PATH
    pause
    exit /b 1
)

echo [OK] Python detecte
echo.

REM Créer l'environnement virtuel si nécessaire
if not exist venv (
    echo [CREATION] Environnement virtuel...
    python -m venv venv
    echo [OK] Environnement virtuel cree
) else (
    echo [OK] Environnement virtuel existe deja
)

echo.
echo [ACTIVATION] Environnement virtuel...
call venv\Scripts\activate.bat

echo.
echo [INSTALLATION] Mise a jour de pip...
python -m pip install --upgrade pip

echo.
echo [INSTALLATION] Dependencies V25...
pip install -r requirements.txt

echo.
echo ====================================================================
echo INSTALLATION TERMINEE
echo ====================================================================
echo.
echo Pour lancer THE CLOSER PRO V25, executez: RUN_V25.bat
echo.
pause
