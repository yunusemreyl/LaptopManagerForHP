import subprocess

try:
    out = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=power.max_limit", "--format=csv,noheader,nounits"],
        timeout=2.0
    ).decode().strip()
    print("max_limit:", out)
except Exception as e:
    print("max_limit error:", e)

try:
    out = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=power.default_limit", "--format=csv,noheader,nounits"],
        timeout=2.0
    ).decode().strip()
    print("default_limit:", out)
except Exception as e:
    print("default_limit error:", e)
