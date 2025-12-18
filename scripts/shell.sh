# 启动此文件会停留在命令行
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
echo "✅ venv activated. Try: hx-agent --help"
exec bash -i