import cv2
import numpy as np
import sys
sys.path.append('.')
from main import detect_presentation_bbox_for_frame

img = cv2.imread("c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_2/Screenshot_001.png")
h, w = img.shape[:2]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

col_means = np.mean(gray, axis=0)
col_stds = np.std(gray, axis=0)

is_bg = (col_means < 15.0) | (col_stds < 2.0)
active_indices = np.where(~is_bg)[0]

print("Active indices count:", len(active_indices))

raw_segments = []
start = active_indices[0]
for i in range(1, len(active_indices)):
    if active_indices[i] != active_indices[i-1] + 1:
        raw_segments.append((start, active_indices[i-1]))
        start = active_indices[i]
raw_segments.append((start, active_indices[-1]))

raw_segments = [seg for seg in raw_segments if (seg[1] - seg[0]) >= 10]
print("Raw segments:", raw_segments)

presentation_segments = []
for s, e in raw_segments:
    seg_w = e - s
    is_rightmost_panel = False
    if s > w * 0.65 and e >= w * 0.95 and seg_w < w * 0.35:
        is_rightmost_panel = True
        print(f"  Classified segment {s}..{e} (width {seg_w}) as PARTICIPANT PANEL -> Exclude.")
    if not is_rightmost_panel:
        presentation_segments.append((s, e))

print("Presentation segments:", presentation_segments)

bbox = detect_presentation_bbox_for_frame(img)
print("Detected BBox:", bbox)
