import cv2
import numpy as np
import os

def detect_presentation_segment_safe(img_path, name, max_gap=150):
    img = cv2.imread(img_path)
    if img is None:
        return None
        
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    col_means = np.mean(gray, axis=0)
    col_stds = np.std(gray, axis=0)
    
    # 1. Classify columns as background/flat
    is_bg = (col_means < 15.0) | (col_stds < 2.0)
    active_indices = np.where(~is_bg)[0]
    
    if len(active_indices) == 0:
        print(f"[{name}] No active columns found!")
        return (0, 0, w, h)
        
    # Group active columns into continuous segments
    raw_segments = []
    start = active_indices[0]
    for i in range(1, len(active_indices)):
        if active_indices[i] != active_indices[i-1] + 1:
            raw_segments.append((start, active_indices[i-1]))
            start = active_indices[i]
    raw_segments.append((start, active_indices[-1]))
    
    # Filter raw segments by minimum width
    raw_segments = [seg for seg in raw_segments if (seg[1] - seg[0]) >= 10]
    
    print(f"\n--- Safe Detection on {name} ---")
    print(f"  Raw segments: {[(s, e, e - s) for s, e in raw_segments]}")
    
    # 2. Identify and exclude participant panel first
    presentation_segments = []
    for s, e in raw_segments:
        seg_w = e - s
        
        # Check if it fits the participant panel signature:
        # - Starts in the right portion of the screen (s > w * 0.65)
        # - Extends near the right edge (e >= w * 0.95)
        # - Width is relatively narrow (seg_w < w * 0.35)
        is_rightmost_panel = False
        if s > w * 0.65 and e >= w * 0.95 and seg_w < w * 0.35:
            is_rightmost_panel = True
            print(f"  Classified segment {s}..{e} (width {seg_w}) as PARTICIPANT PANEL -> Exclude.")
            
        if not is_rightmost_panel:
            presentation_segments.append((s, e))
            
    if not presentation_segments:
        print("  Warning: All segments were classified as participant panel! Restoring raw segments.")
        presentation_segments = raw_segments
        
    # 3. Merge remaining presentation segments
    def merge_adjacent_segments(segs, gap_thresh):
        if not segs:
            return []
        segs = sorted(segs, key=lambda x: x[0])
        merged = [segs[0]]
        for next_seg in segs[1:]:
            curr_start, curr_end = merged[-1]
            next_start, next_end = next_seg
            gap = next_start - curr_end
            if gap <= gap_thresh:
                merged[-1] = (curr_start, max(curr_end, next_end))
            else:
                merged.append(next_seg)
        return merged
        
    merged_presentation = merge_adjacent_segments(presentation_segments, max_gap)
    print(f"  Merged segments: {[(s, e, e - s) for s, e in merged_presentation]}")
    
    # 4. Choose the largest merged segment as the presentation screen
    merged_presentation.sort(key=lambda val: val[1] - val[0], reverse=True)
    best_x1, best_x2 = merged_presentation[0]
    
    # 5. Crop vertically inside this segment
    seg_gray = gray[:, best_x1:best_x2]
    row_means = np.mean(seg_gray, axis=1)
    row_stds = np.std(seg_gray, axis=1)
    
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
    out_path = f"Output/safe_{name}.png"
    cv2.imwrite(out_path, cropped)
    return (best_x1, best_y1, best_x2 - best_x1, best_y2 - best_y1)

if __name__ == "__main__":
    for pct in [5, 25, 50, 75]:
        path = f"Output/layout_sample_{pct}.png"
        if os.path.exists(path):
            detect_presentation_segment_safe(path, f"sample_{pct}")
