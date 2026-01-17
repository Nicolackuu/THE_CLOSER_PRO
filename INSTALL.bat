@echo off
echo ========================================
echo THE CLOSER PRO - Installation Script
echo ========================================
echo.

echo [1/5] Verification de Python...
python --version
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou pas dans le PATH
    pause
    exit /b 1
)
echo.

echo [2/5] Creation de l'environnement virtuel...
python -m venv venv
if errorlevel 1 (
    echo ERREUR: Impossible de creer l'environnement virtuel
    pause
    exit /b 1
)
echo.

echo [3/5] Activation de l'environnement virtuel...
call venv\Scripts\activate.bat
echo.

echo [4/5] Installation de PyTorch avec CUDA 12.1...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo ERREUR: Echec de l'installation de PyTorch
    pause
    exit /b 1
)
echo.

echo [5/5] Installation des autres dependances...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR: Echec de l'installation des dependances
    pause
    exit /b 1
)
echo.

echo ========================================
echo Installation terminee avec succes!
echo ========================================
echo.
echo Pour verifier l'installation CUDA:
echo python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
echo.
echo Pour identifier votre device audio:
echo python -m core.audio_streamer
echo.
echo Pour lancer THE CLOSER PRO:
echo python main.py
echo.
pause
