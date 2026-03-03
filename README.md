# hx_Agent

# 环境
python 3.10.12


# 如何启动
## windows
```bash
pip install -e .
`hx-agent init-db`
`hx-agent ingest data`
`hx-agent study start --name "同步机制" --source data`
# 这里记得加入Key不然只有检索功能
`hx-agent ask --question "讲解一下这一段讲了什么？" --query "mutex" #或者其他关键字
```

# Linux


# 设置API

打开powershell 或者vscode终端设置
```bash
# 单次设置
$env:HX_AGENT_DEEPSEEK_API_KEY="你的key"
#永久生效
setx HX_AGENT_DEEPSEEK_API_KEY "你的key"
```