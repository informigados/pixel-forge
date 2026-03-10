@echo off
setlocal EnableExtensions
set "APP_VERSION=v1.0.0"
title PIXEL FORGE %APP_VERSION% - Sistema Profissional
set "PYTHON_EXE="

echo.
echo  ======================================================================
echo    ########  #### ##   ## ######## ##         ########  #######  ########   ######  ########
echo    ##    ##   ##   ## ##  ##       ##         ##       ##   ##  ##    ## ##       ##
echo    ########   ##    ###   ######   ##         ######   ##   ##  ######## ##   #### ######
echo    ##         ##   ## ##  ##       ##         ##       ##   ##  ##  ##   ##    ## ##
echo    ##       #### ##   ## ########  ########   ##       #######  ##   ##   ######  ########
echo.
echo                  Sistema Profissional de Conversao de Midia
echo        Versao: %APP_VERSION%                  Status: Inicializando
echo  ======================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
    where python >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERRO] Python nao encontrado no PATH.
        echo Instale o Python 3.11+ e tente novamente.
        pause
        exit /b 1
    )
)

echo [1/4] Verificando pip...
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] pip nao encontrado. Tentando instalar com ensurepip...
    "%PYTHON_EXE%" -m ensurepip --upgrade
    if %ERRORLEVEL% NEQ 0 (
        echo [ERRO] Falha ao instalar pip.
        pause
        exit /b 1
    )
)

echo [2/4] Instalando/atualizando dependencias principais...
"%PYTHON_EXE%" -c "import importlib.util,sys; req=['fastapi','uvicorn','PIL','pillow_avif','multipart','websockets']; missing=[m for m in req if importlib.util.find_spec(m) is None]; sys.exit(1 if missing else 0)"
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Dependencias principais ausentes. Instalando...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [ERRO] Falha ao instalar dependencies de requirements.txt
        pause
        exit /b 1
    )
) else (
    echo [OK] Dependencias principais ja estao instaladas.
)

echo [3/4] Verificando FFmpeg e iniciando sistema...
"%PYTHON_EXE%" -c "from pathlib import Path; import shutil,sys; b=Path('bin'); local=((b/'ffmpeg.exe').exists() and (b/'ffprobe.exe').exists()) or ((b/'ffmpeg').exists() and (b/'ffprobe').exists()); onpath=bool(shutil.which('ffmpeg')) and bool(shutil.which('ffprobe')); sys.exit(0 if (local or onpath) else 1)"
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] FFmpeg nao encontrado. Configurando...
    "%PYTHON_EXE%" setup_ffmpeg.py
    if %ERRORLEVEL% NEQ 0 (
        echo [ERRO] Falha na configuracao do FFmpeg.
        pause
        exit /b 1
    )
) else (
    echo [OK] FFmpeg ja disponivel.
)

if /I "%PIXEL_FORGE_SKIP_START%"=="1" (
    echo.
    echo [OK] Bootstrap concluido. Inicio pulado por PIXEL_FORGE_SKIP_START=1
    exit /b 0
)

echo.
echo [OK] Ambiente pronto. Iniciando Pixel Forge...
"%PYTHON_EXE%" start.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Ocorreu um erro ao executar o sistema.
    pause
    exit /b 1
)
