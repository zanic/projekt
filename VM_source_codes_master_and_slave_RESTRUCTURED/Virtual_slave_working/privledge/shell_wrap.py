import subprocess

def run_shell_process(cmd):
    try:
        output = subprocess.check_output(cmd, shell=True,stderr=subprocess.STDOUT)
    except Exception as err:
        return str(err)
    return output