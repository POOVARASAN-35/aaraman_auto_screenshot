import cv2
import numpy as np

img = cv2.imread("Output/layout_sample_75.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
h, w = gray.shape

col_means = np.mean(gray, axis=0)
col_stds = np.std(gray, axis=0)

# Print columns and check their active state
print("Sample 75 Columns Analysis (x from 200 to 1100):")
for x in range(200, 1100, 20):
    chunk_mean = np.mean(col_means[x:x+20])
    chunk_std = np.mean(col_stds[x:x+20])
    print(f"  x={x:04d}..{x+20:04d}: mean={chunk_mean:.2f}, std={chunk_std:.2f}")
