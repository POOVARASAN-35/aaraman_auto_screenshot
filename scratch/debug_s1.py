import cv2
import numpy as np
import sys
sys.path.append('.')
from main import detect_presentation_bbox_for_frame

cap = cv2.VideoCapture("04.06.26.mp4")
ret, frame = cap.read()
cap.release()

if not ret:
    print("Failed to read first frame")
    exit()

h, w = frame.shape[:2]
print(f"Frame size: {w}x{h}")

gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
print("Raw segments:")
for s, e in raw_segments:
    print(f"  {s}..{e} (width {e-s})")

presentation_segments = []
for s, e in raw_segments:
    seg_w = e - s
    is_rightmost_panel = False
    if s > w * 0.65 and e >= w * 0.95 and seg_w < w * 0.35:
        is_rightmost_panel = True
        print(f"  Segment {s}..{e} classified as PARTICIPANT PANEL")
    if not is_rightmost_panel:
        presentation_segments.append((s, e))

print("Presentation segments:", presentation_segments)

bbox = detect_presentation_bbox_for_frame(frame)
print("Detected BBox for first frame:", bbox)
