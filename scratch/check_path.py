import os

path = "c:\\Users\\arasu\\aaraman\\Output\\Kalpanasankar_04-06-2026_2\\Screenshot_001.png"
print("File exists:", os.path.exists(path))
print("Is file:", os.path.isfile(path))

# Print size
if os.path.exists(path):
    print("Size:", os.path.getsize(path))
