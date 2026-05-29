@echo off
echo DepoSync Installer
echo ==================
echo.
nvidia-smi --query-gpu=name --format=csv,noheader,nounits >nul 2>&1
if %errorlevel% == 0 (
    echo NVIDIA GPU detected -- installing CUDA PyTorch
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    goto deps
)
for /f "usebackq tokens=*" %%A in (`powershell -NoProfile -Command "Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty AdapterCompatibility"`) do (
    echo %%A | findstr /i "Advanced Micro Devices" >nul
    if not errorlevel 1 (
        echo AMD GPU detected -- installing ROCm PyTorch
        pip install torch --index-url https://download.pytorch.org/whl/rocm6.2
        echo For faster-whisper AMD support: see README.txt
        goto deps
    )
)
echo No GPU -- CPU mode
pip install torch
:deps
pip install stable-ts faster-whisper PyQt6 python-vlc soundfile numpy pywin32
echo.
echo Done. Run DepoSync.bat to start.
pause
