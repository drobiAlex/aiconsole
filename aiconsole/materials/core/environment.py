from datetime import datetime
import getpass
import os
import platform
import getpass
import os
import platform
import subprocess
import datetime
    
def collect_python_packages():
    try:
        output = subprocess.check_output(['pip', 'freeze']).decode('utf-8')
        package_lines = output.split('\n')
        package_names = [line.split("==")[0] for line in package_lines]
        return ' '.join(package_names)
    except subprocess.CalledProcessError:
        return ''

def content(context):
    return f"""
# Execution environment

os: {platform.system()}
cwd: {os.getcwd()}
user_name: {getpass.getuser()}
time_stamp: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
python_version: {platform.python_version()}
default_shell: {os.environ.get('SHELL')}

## Python Packages
{collect_python_packages()}

## Hardware Statistics:
cpu: {subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string']).decode('utf-8')}
memory:: {subprocess.check_output(['sysctl', '-n', 'hw.memsize']).decode('utf-8')}

## Network Information:
ip: {subprocess.check_output(['ipconfig', 'getifaddr', 'en0']).decode('utf-8')}
connection_status: {subprocess.check_output(['ping', '-c', '1', '-W', '100', '8.8.8.8']).decode('utf-8')}
"""


material = {
    "usage": "Use this always when code is about to be executed. Execution environment information, like operating system, shell, current working directory and Python packages will be collected.",
    "content": content,
}