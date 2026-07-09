import cv2
import os

folder = "c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_1"
if not os.path.exists(folder):
    print("Folder does not exist!")
    exit()

files = sorted([f for f in os.listdir(folder) if f.endswith(".png")])
print(f"Total screenshots: {len(files)}")

dimensions = {}
for file in files:
    path = os.path.join(folder, file)
    img = cv2.imread(path)
    if img is not None:
        h, w = img.shape[:2]
        dims = (w, h)
        dimensions[dims] = dimensions.get(dims, 0) + 1

print("\nScreenshot dimensions count:")
for dims, count in sorted(dimensions.items(), key=lambda x: x[1], reverse=True):
    print(f"  {dims[0]}x{dims[1]} : {count} screenshots")
