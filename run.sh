#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

APP_VERSION="v1.0.0"
PYTHON_EXE=""

fail() {
  echo "[ERRO] $1"
  if [ -t 0 ]; then
    read -r -p "Pressione Enter para sair..." _
  fi
  exit 1
}

echo
echo "======================================================================"
echo "  ########  #### ##   ## ######## ##         ########  #######  ########   ######  ########"
echo "  ##    ##   ##   ## ##  ##       ##         ##       ##   ##  ##    ## ##       ##"
echo "  ########   ##    ###   ######   ##         ######   ##   ##  ######## ##   #### ######"
echo "  ##         ##   ## ##  ##       ##         ##       ##   ##  ##  ##   ##    ## ##"
echo "  ##       #### ##   ## ########  ########   ##       #######  ##   ##   ######  ########"
echo
echo "                Sistema Profissional de Conversao de Midia"
echo "      Versao: ${APP_VERSION}                  Status: Inicializando"
echo "======================================================================"
echo

if [ -x ".venv/bin/python" ]; then
  PYTHON_EXE=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_EXE="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_EXE="python"
else
  fail "Python nao encontrado no PATH. Instale Python 3.10+ e tente novamente."
fi

echo "[0/4] Verificando versao do Python..."
"${PYTHON_EXE}" start.py --check-python || fail "Versao de Python incompatível."

echo "[1/4] Verificando pip..."
if ! "${PYTHON_EXE}" -m pip --version >/dev/null 2>&1; then
  echo "[INFO] pip nao encontrado. Tentando instalar com ensurepip..."
  "${PYTHON_EXE}" -m ensurepip --upgrade || fail "Falha ao instalar pip."
fi

echo "[2/4] Instalando/atualizando dependencias principais..."
if ! "${PYTHON_EXE}" -c "import importlib.util,sys; req=['fastapi','uvicorn','PIL','pillow_avif','multipart','websockets']; missing=[m for m in req if importlib.util.find_spec(m) is None]; sys.exit(1 if missing else 0)"; then
  echo "[INFO] Dependencias principais ausentes. Instalando..."
  "${PYTHON_EXE}" -m pip install -r requirements.txt || fail "Falha ao instalar dependencies de requirements.txt"
else
  echo "[OK] Dependencias principais ja estao instaladas."
fi

if [ "${PIXEL_FORGE_INSTALL_DEV:-0}" = "1" ]; then
  echo "[INFO] Instalando dependencias de desenvolvimento..."
  "${PYTHON_EXE}" -m pip install -r requirements-dev.txt || fail "Falha ao instalar dependencies de requirements-dev.txt"
fi

echo "[3/4] Verificando FFmpeg e iniciando sistema..."
if ! "${PYTHON_EXE}" start.py --check-ffmpeg; then
  echo "[INFO] FFmpeg nao encontrado. Configurando..."
  "${PYTHON_EXE}" setup_ffmpeg.py || fail "Falha na configuracao do FFmpeg."
else
  echo "[OK] FFmpeg ja disponivel."
fi

if [ "${PIXEL_FORGE_SKIP_START:-0}" = "1" ]; then
  echo
  echo "[OK] Bootstrap concluido. Inicio pulado por PIXEL_FORGE_SKIP_START=1"
  exit 0
fi

echo
echo "[OK] Ambiente pronto. Iniciando Pixel Forge..."
"${PYTHON_EXE}" start.py || fail "Ocorreu um erro ao executar o sistema."
