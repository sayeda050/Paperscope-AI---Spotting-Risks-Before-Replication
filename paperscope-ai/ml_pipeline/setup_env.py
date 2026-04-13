import subprocess
import sys
import os

# Install dependencies
subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements-ml.txt"])
subprocess.check_call([sys.executable, "-m", "pip", "install", "openreview-py", "--no-deps"])

# Create editdistance shim (no pre-built wheel for Python 3.13)
site_packages = next(p for p in sys.path if "site-packages" in p)
shim_path = os.path.join(site_packages, "editdistance.py")

content = """from rapidfuzz.distance.Levenshtein import distance

def eval(s1, s2):
    return distance(s1, s2)

bycython = eval
"""

with open(shim_path, "w") as f:
    f.write(content)

print("editdistance shim created at:", shim_path)
print("Setup complete.")