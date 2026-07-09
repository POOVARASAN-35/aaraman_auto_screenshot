import sys
sys.path.append('.')
from main import resolve_output_dir

resolved = resolve_output_dir("Kalpanasankar", "04-06-2026")
print("Resolved Output Dir in Python:", resolved)
