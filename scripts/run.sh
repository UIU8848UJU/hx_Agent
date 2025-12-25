# 启动此文件会 后面需要跟一个开始的参数
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
hx-agent "$@"ls
