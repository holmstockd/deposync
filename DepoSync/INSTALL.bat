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
echo No NVIDIA GPU -- using CPU mode
echo (Note: the Whisper engine supports NVIDIA CUDA or CPU only.
echo  AMD/Intel GPUs are not accelerated; CPU is normal and expected.)
pip install torch
:deps
pip install stable-ts faster-whisper PyQt6 python-vlc soundfile numpy pywin32
echo.
echo Done. Run DepoSync.bat to start.
pause
