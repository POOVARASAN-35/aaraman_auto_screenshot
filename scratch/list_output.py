import os

sub_dir = "Output/Kalpanasankar_04-06-2026_2"
print(f"Files in {sub_dir} (exists={os.path.exists(sub_dir)}):")
if os.path.exists(sub_dir):
    for name in os.listdir(sub_dir):
        print(f"  {name}")
