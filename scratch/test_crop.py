import cv2
import numpy as np
import os

def test_method_1(img_path, name):
    """
    Method 1: Find contours of dilated edges, filter out the participant panel, 
    and pick the largest remaining rectangle that matches the presentation layout.
    """
    img = cv2.imread(img_path)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Bilateral filter to preserve edges while smoothing flat areas
    blurred = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Canny edge detection
    edged = cv2.Canny(blurred, 30, 150)
    
    # Morphological dilation to close gaps in the presentation content
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
    dilated = cv2.dilate(edged, kernel, iterations=2)
    
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"\n--- Method 1 on {name} ---")
    
    candidates = []
    for cnt in contours:
        x, y, w_box, h_box = cv2.boundingRect(cnt)
        area = w_box * h_box
        
        # Filter: Presentation must be at least 10% of width and 10% of height
        if w_box > w * 0.1 and h_box > h * 0.1:
            # Avoid full screen frame contour
            if w_box < w * 0.995 or h_box < h * 0.995:
                # Also, usually participant thumbnails are on the far right.
                # Let's check if the bounding box is likely a participant panel or a webcam.
                # Participant thumbnails are usually smaller and have a high aspect ratio or are small boxes on the right.
                # Let's store all valid candidates.
                candidates.append((area, (x, y, w_box, h_box)))
                print(f"  Contour: x={x}, y={y}, w={w_box}, h={h_box}, area={area} ({area/(w*h)*100:.1f}%)")
                
    if not candidates:
        print("  No candidates found")
        return None
        
    # Sort candidates by area descending
    candidates.sort(key=lambda val: val[0], reverse=True)
    
    # Let's look at the largest candidate.
    # Wait, in layout_sample_50.png, does the participant panel get detected as one large block,
    # or does the phone screen get detected as the largest block?
    # Let's see: the participant panel has multiple webcams. If they are separated by black gaps,
    # they might form separate small contours, or they might merge if dilated.
    # In layout_sample_50.png:
    # Let's write the cropped image for the best candidate.
    best_area, (x, y, w_box, h_box) = candidates[0]
    cropped = img[y:y+h_box, x:x+w_box]
    out_path = f"Output/m1_{name}.png"
    cv2.imwrite(out_path, cropped)
    print(f"  Saved Method 1 crop to {out_path} with box: x={x}, y={y}, w={w_box}, h={h_box}")
    return (x, y, w_box, h_box)

def test_method_2(img_path, name):
    """
    Method 2: Smart Layout Analysis using Horizontal/Vertical Projections.
    Zoom/Teams screen sharing typically has:
    1. A shared content screen (usually on the left or center).
    2. A participant panel (usually on the right or top/bottom).
    3. Black border padding to fit the aspect ratio.
    Let's find the non-black bounding box, and then check for vertical boundaries
    (e.g., black lines or columns with zero variance/low mean) that separate the
    shared screen from the participant webcam strip.
    """
    img = cv2.imread(img_path)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Find overall active region (crop out absolute black borders at the very edges)
    # Use a threshold of 10 to find non-black rows and columns
    row_means = np.mean(gray, axis=1)
    col_means = np.mean(gray, axis=0)
    
    active_rows = np.where(row_means > 5)[0]
    active_cols = np.where(col_means > 5)[0]
    
    if len(active_rows) == 0 or len(active_cols) == 0:
        print("  Empty frame or completely black.")
        return None
        
    y1, y2 = active_rows[0], active_rows[-1]
    x1, x2 = active_cols[0], active_cols[-1]
    
    print(f"\n--- Method 2 on {name} ---")
    print(f"  Overall active region: x={x1}..{x2}, y={y1}..{y2} (w={x2-x1}, h={y2-y1})")
    
    # Within this active region, let's analyze if there's a vertical dividing line
    # representing the boundary between the shared screen and the participant webcams.
    # Usually, the participant webcams are a vertical panel on the right side.
    # In layout_sample_25.png: webcams are at the right (around x=1595 to 1920).
    # In layout_sample_50.png: phone screen is in the middle (466 to 974), webcams are on the right (1436 to 1920).
    # Let's inspect column averages and standard deviations in the active area.
    # A dividing line or gap between the presentation and the webcam strip will typically be
    # a vertical column range of low intensity (black separator) or very low variance.
    # Let's find columns in [x1, x2] that have very low mean or variance (e.g. mean < 10)
    # signifying vertical black bars.
    
    # Let's look for black columns inside the active region
    # To be robust, let's calculate column-wise means in the vertical range [y1, y2]
    sub_gray = gray[y1:y2, x1:x2]
    sub_col_means = np.mean(sub_gray, axis=0)
    
    # Let's find "black" column indices relative to x1
    black_thresh = 5.0
    black_cols = np.where(sub_col_means < black_thresh)[0]
    
    # Group consecutive black columns to find vertical black dividers
    if len(black_cols) > 0:
        print(f"  Found black columns inside active region!")
        # Let's identify the continuous black bands
        bands = []
        start = black_cols[0]
        for i in range(1, len(black_cols)):
            if black_cols[i] != black_cols[i-1] + 1:
                bands.append((start + x1, black_cols[i-1] + x1))
                start = black_cols[i]
        bands.append((start + x1, black_cols[-1] + x1))
        
        print(f"  Vertical black dividers detected: {bands}")
        
        # If there are dividers, they partition the x range [x1, x2] into multiple segments.
        # Let's find these segments!
        segments = []
        curr_x = x1
        for b_start, b_end in bands:
            # Segment before the black band
            if b_start - curr_x > 20: # ignore very thin segments
                segments.append((curr_x, b_start))
            curr_x = b_end
        if x2 - curr_x > 20:
            segments.append((curr_x, x2))
            
        print(f"  Partitioned segments: {segments}")
        
        # Now, which segment is the presentation screen?
        # The presentation screen is the largest shared content area.
        # But wait! The participant panel on the right might be a large segment containing webcams.
        # How do we distinguish the presentation screen from the participant webcam segment?
        # 1. The participant panel on the right consists of webcams, which typically have high high-frequency content,
        #    names, faces, profile photos.
        # 2. More importantly, the shared screen is usually the LEFTMOST or the LARGEST segment.
        # Let's look at the segments and select the one that is largest, or check if we can filter out the webcam panel.
        # Let's write down the logic to choose the correct segment.
        best_seg = None
        max_seg_w = 0
        for seg_x1, seg_x2 in segments:
            seg_w = seg_x2 - seg_x1
            # Filter out participant webcams:
            # Normally, the webcam strip has a fixed width (e.g. around 300-350 pixels out of 1920).
            # Also, the presentation is the primary content, so it should be larger.
            # If there's a segment on the right that matches typical webcam strip width (e.g. 15-25% of frame width)
            # and another segment that is much larger or represents the main shared area, we prefer the main shared area.
            if seg_w > max_seg_w:
                # Let's check if this segment is at the very right and looks like a participant panel.
                # If seg_x2 == x2 (touches the right edge) and seg_w is small relative to the total width (e.g. < 25%),
                # it's likely the webcam strip.
                # Let's keep the largest one as the default, but we can refine this.
                max_seg_w = seg_w
                best_seg = (seg_x1, seg_x2)
                
        if best_seg:
            px1, px2 = best_seg
            # Let's crop vertically as well inside this segment
            # Find the active rows specifically inside this column segment [px1, px2]
            seg_gray = gray[:, px1:px2]
            seg_row_means = np.mean(seg_gray, axis=1)
            seg_active_rows = np.where(seg_row_means > 5)[0]
            if len(seg_active_rows) > 0:
                py1, py2 = seg_active_rows[0], seg_active_rows[-1]
            else:
                py1, py2 = y1, y2
                
            cropped = img[py1:py2, px1:px2]
            out_path = f"Output/m2_{name}.png"
            cv2.imwrite(out_path, cropped)
            print(f"  Selected Segment: x={px1}..{px2}, y={py1}..{py2} (w={px2-px1}, h={py2-py1})")
            print(f"  Saved Method 2 crop to {out_path}")
            return (px1, py1, px2 - px1, py2 - py1)
    else:
        print("  No vertical dividers found. The entire active area is a single block.")
        # If there are no vertical dividers, the presentation is the entire active area.
        # But wait! In layout_sample_25.png, is there a black vertical divider between the browser and the webcams?
        # Let's check: the browser window ends at x=1595, and the webcam panel starts at x=1595.
        # In this case, is there a black divider? There is no black column between them! The browser window
        # is white, and the webcam panel is black, so there is a sharp white-to-black edge at x=1595.
        # Since the webcam panel has a black background, the columns containing webcams have non-zero means
        # because the webcams themselves are not black. But the space between webcams is black.
        # Let's think: how can we detect the transition at x=1595?
        # Let's write an algorithm to find this transition.
        pass

    return (x1, y1, x2-x1, y2-y1)

if __name__ == "__main__":
    test_method_1("Output/layout_sample_25.png", "sample_25")
    test_method_1("Output/layout_sample_50.png", "sample_50")
    
    test_method_2("Output/layout_sample_25.png", "sample_25")
    test_method_2("Output/layout_sample_50.png", "sample_50")
