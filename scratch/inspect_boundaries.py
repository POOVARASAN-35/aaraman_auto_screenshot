import cv2
import numpy as np

img = cv2.imread("Output/layout_sample_25.png")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
h, w = gray.shape

# Let's inspect columns from x=1580 to x=1620
col_means = np.mean(gray, axis=0)
col_stds = np.std(gray, axis=0)

print("Columns around 1595-1600 in sample_25:")
for x in range(1580, 1620):
    print(f"  x={x}: mean={col_means[x]:.2f}, std={col_stds[x]:.2f}, min={np.min(gray[:, x])}, max={np.max(gray[:, x])}")
