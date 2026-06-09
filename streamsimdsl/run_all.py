import os
import subprocess

# Folders to scan
folders = [
    "streamsimdsl/models/things",
    "streamsimdsl/models/actors",
    "streamsimdsl/models/environments",
]

for folder in folders:
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        if fname.endswith(".actor"):
            print(f"\n[RUNNING] {fpath}")
            subprocess.run(["python", "-m", "streamsimdsl.cli.cli", "t2d", fpath])
            subprocess.run(["python", "-m", "streamsimdsl.cli.cli", "t2vc", fpath])
        elif fname.endswith(".thing"):
            print(f"\n[RUNNING] {fpath}")
            subprocess.run(["python", "-m", "streamsimdsl.cli.cli", "t2d", fpath])
            subprocess.run(["python", "-m", "streamsimdsl.cli.cli", "t2c", fpath])
            subprocess.run(["python", "-m", "streamsimdsl.cli.cli", "t2vc", fpath])
        elif fname.endswith(".env"):
            # Check if this env file contains a real Environment definition
            with open(fpath, "r") as f:
                content = f.read()
            if "Environment:" not in content:
                print(f"[SKIP] {fpath} (no Environment block)")
                continue
            print(f"\n[RUNNING] {fpath}")
            subprocess.run(["python", "-m", "streamsimdsl.cli.cli", "t2vc", fpath])

