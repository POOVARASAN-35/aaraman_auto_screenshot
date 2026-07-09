import cv2
import numpy as np
import sys
sys.path.append('.')
from main import detect_presentation_bbox_for_frame

cap = cv2.VideoCapture("04.06.26.mp4")
fps = cap.get(cv2.CAP_PROP_FPS)
if fps <= 0:
    fps = 25.0

# Simulated values
crop_bbox = (467, 24, 507, 1024)
is_baseline_subrectangle = True
last_valid_bbox = crop_bbox

frame_idx = 0
saved_count = 0
while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame_idx += 1
    
    current_bbox = detect_presentation_bbox_for_frame(frame, last_valid_bbox=last_valid_bbox)
    height_orig, width_orig = frame.shape[:2]
    
    is_webcam_grid = is_baseline_subrectangle and current_bbox[2] >= width_orig * 0.95
    
    if is_webcam_grid:
        # skipped
        continue
        
    # If not skipped, this would be the first saved frame!
    print(f"First non-skipped frame found at index {frame_idx} (time: {frame_idx/fps:.2f}s):")
    print(f"  Detected BBox: {current_bbox}")
    
    # Save a copy of this frame to scratch to inspect it
    cv2.imwrite("scratch/first_nonskipped_frame.png", frame)
    
    # Apply crop
    x, y, w, h = current_bbox
    crop_f = frame[y:y+h, x:x+w]
    cv2.imwrite("scratch/first_nonskipped_cropped.png", crop_f)
    print("  Saved raw and cropped frames to scratch/ for inspection.")
    break

cap.release()
