import cv2
import os

folder = "c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_1"
for i in range(1, 16):
    name = f"Screenshot_{i:03d}.png"
    path = os.path.join(folder, name)
    if os.path.exists(path):
        img = cv2.imread(path)
        h, w = img.shape[:2]
        print(f"  {name}: {w}x{h}")
    else:
        print(f"  {name}: NOT FOUND")
