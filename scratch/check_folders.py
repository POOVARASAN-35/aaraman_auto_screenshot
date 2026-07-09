import os

print("Listing all Kalpanasankar directories in Output:")
for name in os.listdir("Output"):
    if name.startswith("Kalpanasankar"):
        path = os.path.join("Output", name)
        is_dir = os.path.isdir(path)
        files = os.listdir(path) if is_dir else []
        print(f"  {name}: is_dir={is_dir}, files count={len(files)}")
        if len(files) > 0:
            print(f"    First few files: {files[:5]}")
