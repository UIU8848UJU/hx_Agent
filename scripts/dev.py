import os
import platform
import subprocess
from pathlib import Path
import shutil


def run(cmd, cwd):
    print("+", " ".join(map(str, cmd)))
    subprocess.check_call(list(map(str, cmd)), cwd=str(cwd))

# 后续加入检查环境，一键启动
def checkenvir():
    print("正在拉取环境..........")

def main():
    checkenvir()
    scripts_dir = Path(__file__).resolve().parent  
    repo_root   = scripts_dir.parent
    
    sysname = platform.system().lower()
    
    if "windows" in sysname:
        ps1_scripts = scripts_dir /"bootstrap_win.ps1"
        if not ps1_scripts.exists():
            raise FileNotFoundError(ps1_scripts)
        
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if not pwsh:
            raise RuntimeError("PowerShell not found (pwsh/powershell).")

        run([pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1_scripts)], cwd=repo_root)
    else:
        sh_scripts = scripts_dir/ "bootstrap_Linux.sh" 
        if not sh_scripts.exists():
            raise FileNotFoundError(sh_scripts)

        run(["bash", str(sh_scripts)], cwd=repo_root)

if __name__ == "__main__":
    main()