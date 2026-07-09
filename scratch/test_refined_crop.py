import cv2
import numpy as np
import os

def detect_presentation_segment(img_path, name):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Failed to read {img_path}")
        return None
        
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Compute column-wise means and standard deviations
    col_means = np.mean(gray, axis=0)
    col_stds = np.std(gray, axis=0)
    
    # Define a column as background/flat if its std is very low AND/OR its mean is very low.
    # In some videos, the background is not pure black, but a dark color.
    # Let's check the distribution of col_stds to find a threshold, or use a safe threshold.
    # Typically, background columns are extremely uniform. Let's use a std threshold of 2.0.
    # Also, we check if the mean is very low (e.g. < 15.0) to capture dark margins.
    is_bg = (col_means < 15.0) | (col_stds < 2.0)
    
    # Active columns are columns that are NOT background
    active_indices = np.where(~is_bg)[0]
    
    if len(active_indices) == 0:
        print(f"[{name}] No active columns found! The frame seems empty/black.")
        return (0, 0, w, h)
        
    # Group active columns into continuous segments
    segments = []
    start = active_indices[0]
    for i in range(1, len(active_indices)):
        if active_indices[i] != active_indices[i-1] + 1:
            segments.append((start, active_indices[i-1]))
            start = active_indices[i]
    segments.append((start, active_indices[-1]))
    
    print(f"\n--- Refined Detection on {name} ---")
    print(f"  Detected segments: {[(s, e, e - s) for s, e in segments]}")
    
    # Filter segments:
    # We want to identify and remove the participant panel on the right.
    # A segment is classified as a participant panel if:
    # - It is the rightmost segment.
    # - It starts after 65% of the frame width.
    # - Its width is less than 35% of the frame width.
    valid_segments = []
    for s, e in segments:
        seg_w = e - s
        if seg_w < 10:  # Skip noise segments
            continue
            
        # Check if it is the rightmost panel
        is_rightmost_panel = False
        if s > w * 0.65 and e >= w * 0.95 and seg_w < w * 0.35:
            is_rightmost_panel = True
            print(f"  Classified segment {s}..{e} (width {seg_w}) as PARTICIPANT PANEL -> Exclude.")
            
        if not is_rightmost_panel:
            valid_segments.append((s, e))
            
    if not valid_segments:
        print("  Warning: All segments were filtered out! Falling back to the largest detected segment.")
        valid_segments = segments
        
    # Choose the largest segment among the valid ones
    valid_segments.sort(key=lambda val: val[1] - val[0], reverse=True)
    best_x1, best_x2 = valid_segments[0]
    
    # Now, find the active vertical boundaries (y1, y2) within this column segment
    seg_gray = gray[:, best_x1:best_x2]
    row_means = np.mean(seg_gray, axis=1)
    row_stds = np.std(seg_gray, axis=1)
    
    # A row is background if it has low mean or low std
    is_row_bg = (row_means < 15.0) | (row_stds < 2.0)
    active_rows = np.where(~is_row_bg)[0]
    
    if len(active_rows) > 0:
        best_y1 = active_rows[0]
        best_y2 = active_rows[-1]
    else:
        best_y1 = 0
        best_y2 = h
        
    print(f"  Selected Presentation Box: x={best_x1}..{best_x2}, y={best_y1}..{best_y2} (w={best_x2-best_x1}, h={best_y2-best_y1})")
    
    cropped = img[best_y1:best_y2, best_x1:best_x2]
    out_path = f"Output/refined_{name}.png"
    cv2.imwrite(out_path, cropped)
    print(f"  Saved refined crop to {out_path}")
    return (best_x1, best_y1, best_x2 - best_x1, best_y2 - best_y1)

if __name__ == "__main__":
    detect_presentation_segment("Output/layout_sample_25.png", "sample_25")
    detect_presentation_segment("Output/layout_sample_50.png", "sample_50")
