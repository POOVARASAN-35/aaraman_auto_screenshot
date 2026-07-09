import os
import sys
import re
import time
import datetime
import argparse
import uuid
import warnings
import shutil
import gdown
import cv2
import numpy as np
from tqdm import tqdm

# Silence BeautifulSoup warnings from gdown
try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    pass

def clean_gdrive_url(url):
    """
    Cleans and extracts the file ID from a Google Drive URL,
    returning a direct download URL. If already a direct URL or ID, returns it.
    """
    url = url.strip()
    
    # Check if the input is already just a Google Drive ID
    if re.match(r'^[a-zA-Z0-9_-]{25,50}$', url):
        return f"https://drive.google.com/uc?id={url}"
    
    # Extractor regex patterns for various Drive sharing link formats
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'drive/folders/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?id={file_id}"
            
    return url

def download_from_gdrive(url_or_id):
    """
    Downloads a file or folder from Google Drive using gdown.
    Downloads to a unique subdirectory to prevent file lock/overwrite conflicts.
    Handles invalid links and folder downloads gracefully.
    """
    url_or_id = url_or_id.strip()
    
    # Quick sanity check: check if it contains drive.google.com, docs.google.com, or is a raw ID
    is_gdrive = ("drive.google.com" in url_or_id or 
                 "docs.google.com" in url_or_id or 
                 re.match(r'^[a-zA-Z0-9_-]{25,50}$', url_or_id))
                 
    if not is_gdrive:
        print("\nWarning: The provided link does not look like a standard Google Drive link.")
        print("Will attempt download, but it may fail. Please ensure it is a valid Google Drive link.\n")
        
    is_folder = "drive/folders/" in url_or_id or "folders/" in url_or_id
    
    # Create unique subdirectory for download to isolate files and avoid file locks
    unique_dir = os.path.join("temp_downloads", f"dl_{uuid.uuid4().hex[:8]}")
    os.makedirs(unique_dir, exist_ok=True)
    
    try:
        if is_folder:
            print("Folder link detected. Initializing Google Drive folder download...")
            gdown.download_folder(url=url_or_id, output=unique_dir, quiet=False, remaining_ok=True)
            
            # Scan unique_dir for downloaded video files
            video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
            video_files = []
            for root, dirs, files in os.walk(unique_dir):
                for f in files:
                    if f.lower().endswith(video_extensions):
                        video_files.append(os.path.join(root, f))
            
            if video_files:
                # Use the largest video file
                video_files.sort(key=lambda p: os.path.getsize(p), reverse=True)
                downloaded_path = video_files[0]
                print(f"\nFolder download completed. Found video file: {downloaded_path}\n")
                return downloaded_path
            else:
                # Cleanup if no video found
                try:
                    shutil.rmtree(unique_dir)
                except:
                    pass
                print("\nError: Folder downloaded successfully, but no video file was found inside.\n")
                return None
        else:
            direct_url = clean_gdrive_url(url_or_id)
            print("Initializing Google Drive file download...")
            # Appending separator forces gdown to treat output as folder and preserve original filename
            output_target = unique_dir + os.sep
            downloaded_path = gdown.download(url=direct_url, output=output_target, quiet=False, fuzzy=True)
            
            if downloaded_path and os.path.exists(downloaded_path):
                print(f"\nDownload completed successfully: {downloaded_path}\n")
                return downloaded_path
            else:
                # Fallback: if the input is a raw ID and normal download failed, try treating it as a folder ID
                if re.match(r'^[a-zA-Z0-9_-]{25,50}$', url_or_id):
                    print("\nFile download failed. Attempting folder download fallback...")
                    folder_url = f"https://drive.google.com/drive/folders/{url_or_id}"
                    try:
                        gdown.download_folder(url=folder_url, output=unique_dir, quiet=True, remaining_ok=True)
                        video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
                        video_files = []
                        for root, dirs, files in os.walk(unique_dir):
                            for f in files:
                                if f.lower().endswith(video_extensions):
                                    video_files.append(os.path.join(root, f))
                        if video_files:
                            video_files.sort(key=lambda p: os.path.getsize(p), reverse=True)
                            downloaded_path = video_files[0]
                            print(f"\nFallback folder download completed. Found video file: {downloaded_path}\n")
                            return downloaded_path
                    except:
                        pass
                
                # Cleanup folder if download failed
                try:
                    os.rmdir(unique_dir)
                except:
                    pass
                print("\nError: Download failed. No file was saved.\n")
                print("="*60)
                print(" HINT FOR GOOGLE DRIVE DOWNLOAD BLOCKS:")
                print(" 1. Ensure the sharing settings are set to 'Anyone with the link'.")
                print(" 2. Alternatively, open the link in your browser, download the file")
                print("    manually, and enter the local file path (e.g. '04.06.26.mp4')")
                print("    directly into this tool to process it locally without download!")
                print("="*60 + "\n")
                return None
    except Exception as e:
        # Cleanup folder if download failed
        try:
            shutil.rmtree(unique_dir)
        except:
            try:
                os.rmdir(unique_dir)
            except:
                pass
        print(f"\nError: Google Drive download failed.\nDetails: {e}\n")
        print("="*60)
        print(" HINT FOR GOOGLE DRIVE DOWNLOAD BLOCKS:")
        print(" 1. Ensure the sharing settings are set to 'Anyone with the link'.")
        print(" 2. Alternatively, open the link in your browser, download the file")
        print("    manually, and enter the local file path (e.g. '04.06.26.mp4')")
        print("    directly into this tool to process it locally without download!")
        print("="*60 + "\n")
        return None

def resolve_output_dir(presenter_name, presentation_date, base_output_dir="Output"):
    """
    Creates and returns the output directory path.
    Saves under Output/<Presenter_Name>_<DD-MM-YYYY>
    Appends _1, _2, etc. if the folder already exists to avoid overwriting.
    """
    # Sanitize inputs for folder names
    sanitized_name = re.sub(r'[<>:"/\\|?* ]', '_', presenter_name)
    sanitized_date = re.sub(r'[<>:"/\\|?* ]', '_', presentation_date)
    
    # Remove consecutive underscores
    sanitized_name = re.sub(r'_+', '_', sanitized_name).strip('_')
    sanitized_date = re.sub(r'_+', '_', sanitized_date).strip('_')
    
    folder_base_name = f"{sanitized_name}_{sanitized_date}"
    
    # Ensure base output dir exists
    os.makedirs(base_output_dir, exist_ok=True)
    
    target_dir = os.path.join(base_output_dir, folder_base_name)
    if not os.path.exists(target_dir):
        return target_dir
        
    # Suffix matching
    counter = 1
    while True:
        candidate_dir = os.path.join(base_output_dir, f"{folder_base_name}_{counter}")
        if not os.path.exists(candidate_dir):
            return candidate_dir
        counter += 1

def detect_presentation_bbox_for_frame(frame, last_valid_bbox=None, max_gap=150):
    """
    Dynamically detects and crops only the presentation/PPT screen from a single frame.
    Returns (x, y, w, h) bounding box.
    """
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 1. Compute column-wise means and standard deviations
    col_means = np.mean(gray, axis=0)
    col_stds = np.std(gray, axis=0)
    
    # Classify columns as background/flat
    is_bg = (col_means < 15.0) | (col_stds < 2.0)
    active_indices = np.where(~is_bg)[0]
    
    if len(active_indices) == 0:
        return last_valid_bbox if last_valid_bbox is not None else (0, 0, width, height)
        
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
    
    if not raw_segments:
        return last_valid_bbox if last_valid_bbox is not None else (0, 0, width, height)
        
    # 2. Identify and exclude participant panel first
    presentation_segments = []
    for s, e in raw_segments:
        seg_w = e - s
        
        # Check if it fits the participant panel signature:
        # - Starts in the right portion of the screen (s > w * 0.65)
        # - Extends near the right edge (e >= w * 0.95)
        # - Width is relatively narrow (seg_w < w * 0.35)
        is_rightmost_panel = False
        if s > width * 0.65 and e >= width * 0.95 and seg_w < width * 0.35:
            is_rightmost_panel = True
            
        if not is_rightmost_panel:
            presentation_segments.append((s, e))
            
    if not presentation_segments:
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
    if not merged_presentation:
        return last_valid_bbox if last_valid_bbox is not None else (0, 0, width, height)
        
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
        best_y2 = height
        
    w_box = best_x2 - best_x1
    h_box = best_y2 - best_y1
    
    # Area validation: must occupy at least 10% of total area
    if (w_box * h_box) < (width * height * 0.10):
        return last_valid_bbox if last_valid_bbox is not None else (0, 0, width, height)
        
    return (best_x1, best_y1, w_box, h_box)

def detect_presentation_bbox(video_path, samples=5):
    """
    Upfront analyzer that samples frames spread across the video and returns
    the baseline median presentation bounding box.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
        
    sample_indices = []
    if total_frames > 0:
        step = max(1, total_frames // (samples + 1))
        sample_indices = [step * i for i in range(1, samples + 1)]
    else:
        sample_indices = [int(fps * 5 * i) for i in range(1, samples + 1)]
        
    bboxes = []
    
    for idx in sample_indices:
        if total_frames > 0 and idx >= total_frames:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
            
        bbox = detect_presentation_bbox_for_frame(frame)
        if bbox and (bbox[2] > 0 and bbox[3] > 0):
            bboxes.append(bbox)
            
    cap.release()
    
    if not bboxes:
        return None
        
    avg_x = int(np.median([b[0] for b in bboxes]))
    avg_y = int(np.median([b[1] for b in bboxes]))
    avg_w = int(np.median([b[2] for b in bboxes]))
    avg_h = int(np.median([b[3] for b in bboxes]))
    
    return (avg_x, avg_y, avg_w, avg_h)

def is_participant_grid(frame, face_threshold=3):
    """
    Checks if a frame is a participant webcam grid by running Haar Cascade face detection.
    Resizes the frame to a width of 640 for extremely fast detection.
    Returns True if face count >= face_threshold, False otherwise.
    """
    height, width = frame.shape[:2]
    if width <= 0 or height <= 0:
        return False
        
    # Resize to width 640 to speed up face detection significantly
    scale = 640.0 / width
    resized = cv2.resize(frame, (640, int(height * scale)))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    
    # Load pre-trained Haar Cascade face detector
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    if face_cascade.empty():
        return False
        
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
    return len(faces) >= face_threshold

def save_grid_preview(video_path, output_dir):
    """
    Saves a preview of the video frame with a percentage-based grid overlay
    to help the user identify crop percentages.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
    seek_frame = int(min(total_frames - 1, max(1, fps * 5)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, seek_frame)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
        
    height, width = frame.shape[:2]
    grid_img = frame.copy()
    
    # Draw vertical lines (from left and right)
    for pct in range(5, 100, 5):
        x = int(width * (pct / 100.0))
        # Draw Left reference line (green)
        cv2.line(grid_img, (x, 0), (x, height), (0, 255, 0), 1)
        # Draw Right reference line (blue, showing distance from right)
        x_right = width - x
        cv2.line(grid_img, (x_right, 0), (x_right, height), (255, 0, 0), 1)
        
        # Put text labels at the top and bottom
        cv2.putText(grid_img, f"L:{pct}%", (x + 2, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        cv2.putText(grid_img, f"R:{pct}%", (x_right - 45, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
        
    # Draw horizontal lines (from top and bottom)
    for pct in range(5, 100, 5):
        y = int(height * (pct / 100.0))
        # Draw Top reference line (yellow)
        cv2.line(grid_img, (0, y), (width, y), (0, 255, 255), 1)
        # Draw Bottom reference line (red)
        y_bottom = height - y
        cv2.line(grid_img, (0, y_bottom), (width, y_bottom), (0, 0, 255), 1)
        
        # Put labels
        cv2.putText(grid_img, f"T:{pct}%", (10, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(grid_img, f"B:{pct}%", (width - 60, y_bottom + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        
    preview_path = os.path.join(output_dir, "crop_grid_helper.png")
    cv2.imwrite(preview_path, grid_img)
    return preview_path

def save_crop_preview(video_path, output_dir, crop_left=0.0, crop_right=0.0, crop_top=0.0, crop_bottom=0.0, crop_bbox=None):
    """
    Saves a preview of the cropped frame to help the user verify their crop settings.
    Saves to <output_dir>/crop_preview.png
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
        
    # Seek to a frame likely to have content (5 seconds in)
    seek_frame = int(min(total_frames - 1, max(1, fps * 5)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, seek_frame)
    
    ret, frame = cap.read()
    if not ret:
        # Fallback to the first frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = cap.read()
        
    cap.release()
    
    if not ret:
        return None
        
    # Apply auto-crop bounding box if present
    if crop_bbox:
        x, y, w, h = crop_bbox
        height_orig, width_orig = frame.shape[:2]
        x_val = max(0, min(width_orig - 1, x))
        y_val = max(0, min(height_orig - 1, y))
        w_val = max(1, min(width_orig - x_val, w))
        h_val = max(1, min(height_orig - y_val, h))
        frame = frame[y_val:y_val+h_val, x_val:x_val+w_val]
        
    # Apply manual percentage crop
    frame = apply_crop(frame, crop_left, crop_right, crop_top, crop_bottom)
    
    # Save the preview image
    os.makedirs(output_dir, exist_ok=True)
    preview_path = os.path.join(output_dir, "crop_preview.png")
    cv2.imwrite(preview_path, frame)
    return preview_path

def apply_crop(frame, crop_left=0.0, crop_right=0.0, crop_top=0.0, crop_bottom=0.0):
    """
    Crops a frame using percentages from the edges (left, right, top, bottom).
    """
    if crop_left == 0.0 and crop_right == 0.0 and crop_top == 0.0 and crop_bottom == 0.0:
        return frame
        
    height, width = frame.shape[:2]
    
    # Calculate pixel offsets based on percentages
    left_px = int(width * (crop_left / 100.0))
    right_px = int(width * (1.0 - (crop_right / 100.0)))
    top_px = int(height * (crop_top / 100.0))
    bottom_px = int(height * (1.0 - (crop_bottom / 100.0)))
    
    # Ensure indices are valid and non-negative
    left_px = max(0, min(width - 1, left_px))
    right_px = max(left_px + 1, min(width, right_px))
    top_px = max(0, min(height - 1, top_px))
    bottom_px = max(top_px + 1, min(height, bottom_px))
    
    return frame[top_px:bottom_px, left_px:right_px]

def is_different(frame1, frame2, pixel_threshold=8.0):
    """
    Determines if two frames are significantly different.
    Converts to grayscale, resizes, blurs, and measures the mean absolute difference.
    """
    # Convert both to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    # Resize to 64x64 to ignore high-frequency details (text change remains visible)
    resized1 = cv2.resize(gray1, (64, 64))
    resized2 = cv2.resize(gray2, (64, 64))
    
    # Apply Gaussian blur to reduce video compression noise
    blurred1 = cv2.GaussianBlur(resized1, (5, 5), 0)
    blurred2 = cv2.GaussianBlur(resized2, (5, 5), 0)
    
    # Compute absolute difference
    diff = cv2.absdiff(blurred1, blurred2)
    mean_diff = np.mean(diff)
    
    return mean_diff > pixel_threshold, mean_diff

def process_video(video_path, presenter_name, presentation_date, 
                  threshold=8.0, sample_interval=1.0, cooldown=10.0,
                  crop_left=0.0, crop_right=0.0, crop_top=0.0, crop_bottom=0.0,
                  crop_bbox=None, auto_crop=False):
    """
    Analyzes the video frame-by-frame (with sampling) and extracts unique screenshots.
    """
    start_time = time.time()
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return None, 0, 0
        
    # Extract properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if fps <= 0:
        fps = 25.0  # Fallback to standard 25 fps
        
    if total_frames <= 0:
        total_frames_est = None
        duration_seconds = 0
        duration_str = "Unknown"
    else:
        total_frames_est = total_frames
        duration_seconds = total_frames / fps
        duration_str = str(datetime.timedelta(seconds=int(duration_seconds)))
        
    print(f"--- Video Information ---")
    print(f"File:            {os.path.basename(video_path)}")
    print(f"Duration:        {duration_str} ({duration_seconds:.2f} seconds)")
    print(f"FPS:             {fps:.2f}")
    print(f"Total Frames:    {total_frames if total_frames > 0 else 'Unknown'}")
    if crop_bbox:
        print(f"Auto-Crop Area:  x={crop_bbox[0]}, y={crop_bbox[1]}, width={crop_bbox[2]}, height={crop_bbox[3]}")
    if crop_left > 0 or crop_right > 0 or crop_top > 0 or crop_bottom > 0:
        print(f"Manual Crop:     Left={crop_left}%, Right={crop_right}%, Top={crop_top}%, Bottom={crop_bottom}%")
    print(f"-------------------------\n")
    
    # Output directory setup
    output_dir = resolve_output_dir(presenter_name, presentation_date)
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output Directory resolved to: {output_dir}\n")
    
    # Setup frame skip stepping (sample interval)
    frame_step = max(1, int(round(fps * sample_interval)))
    
    saved_count = 0
    last_saved_frame = None
    last_saved_time = -cooldown  # Allow the first frame to be saved immediately
    last_valid_bbox = crop_bbox  # Start with the upfront baseline detection
    
    # Check if the baseline presentation screen is a sub-rectangle (signifying split share + webcams layout)
    height_orig_baseline, width_orig_baseline = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    if width_orig_baseline <= 0:
        width_orig_baseline = 1920
    is_baseline_subrectangle = (crop_bbox is not None and crop_bbox[2] < width_orig_baseline * 0.95)
    
    # Progress bar setup
    pbar_total = total_frames_est if total_frames_est else None
    
    with tqdm(total=pbar_total, desc="Analyzing Video", unit="frames") as pbar:
        frame_idx = 0
        while True:
            # Fast-forward frames up to frame_step-1 using cap.grab()
            actual_skipped = 0
            for _ in range(frame_step - 1):
                grabbed = cap.grab()
                if not grabbed:
                    break
                frame_idx += 1
                actual_skipped += 1
                
            if actual_skipped > 0:
                pbar.update(actual_skipped)
                
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            pbar.update(1)
            
            # Apply auto-crop bounding box if present
            if auto_crop:
                # Dynamically detect bounding box for current frame, using last_valid_bbox as fallback
                current_bbox = detect_presentation_bbox_for_frame(frame, last_valid_bbox=last_valid_bbox)
                
                # Check if this frame is a webcam grid frame (no screen share active)
                # This happens if the baseline screen share is a sub-rectangle, but the current frame's
                # detected box is full-screen (meaning no sub-rectangle layout was detected).
                height_orig, width_orig = frame.shape[:2]
                if is_baseline_subrectangle and current_bbox[2] >= width_orig * 0.95:
                    # Skip this frame because it's a webcam grid frame (no screen share)
                    continue
                
                # Apply stabilization/hysteresis to prevent small jitter:
                if last_valid_bbox is not None:
                    px, py, pw, ph = last_valid_bbox
                    cx, cy, cw, ch = current_bbox
                    if (abs(cx - px) < 15 and abs(cy - py) < 15 and 
                        abs(cw - pw) < 15 and abs(ch - ph) < 15):
                        current_bbox = last_valid_bbox
                        
                last_valid_bbox = current_bbox
                x, y, w, h = current_bbox
                x_val = max(0, min(width_orig - 1, x))
                y_val = max(0, min(height_orig - 1, y))
                w_val = max(1, min(width_orig - x_val, w))
                h_val = max(1, min(height_orig - y_val, h))
                frame = frame[y_val:y_val+h_val, x_val:x_val+w_val]
            elif crop_bbox:
                x, y, w, h = crop_bbox
                height_orig, width_orig = frame.shape[:2]
                x_val = max(0, min(width_orig - 1, x))
                y_val = max(0, min(height_orig - 1, y))
                w_val = max(1, min(width_orig - x_val, w))
                h_val = max(1, min(height_orig - y_val, h))
                frame = frame[y_val:y_val+h_val, x_val:x_val+w_val]
            
            # Apply manual cropping to the frame
            frame = apply_crop(frame, crop_left, crop_right, crop_top, crop_bottom)
            
            # Skip completely flat black/blank screens
            h_f, w_f = frame.shape[:2]
            if w_f > 0 and h_f > 0:
                frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if np.mean(frame_gray) < 10.0 and np.std(frame_gray) < 1.0:
                    continue
            
            current_time_seconds = frame_idx / fps
            
            should_save = False
            reason = ""
            
            if last_saved_frame is None:
                should_save = True
                reason = "First frame of the video"
            elif (current_time_seconds - last_saved_time) >= cooldown:
                is_diff, diff_val = is_different(frame, last_saved_frame, threshold)
                if is_diff:
                    should_save = True
                    reason = f"Scene change detected (diff={diff_val:.2f} > {threshold})"
                    
            if should_save:
                # Skip if it is a participant webcam grid
                if is_participant_grid(frame):
                    timestamp_str = str(datetime.timedelta(seconds=int(current_time_seconds)))
                    tqdm.write(f"[{timestamp_str}] Ignored frame - suspected participant webcam grid (multiple faces detected)")
                    continue
                    
                saved_count += 1
                screenshot_name = f"Screenshot_{saved_count:03d}.png"
                screenshot_path = os.path.join(output_dir, screenshot_name)
                
                # Save frame in lossless quality (PNG)
                cv2.imwrite(screenshot_path, frame)
                
                last_saved_frame = frame.copy()
                last_saved_time = current_time_seconds
                
                timestamp_str = str(datetime.timedelta(seconds=int(current_time_seconds)))
                tqdm.write(f"[{timestamp_str}] Saved {screenshot_name} - {reason}")
                
    cap.release()
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    return output_dir, saved_count, duration_str, processing_time

def main():
    parser = argparse.ArgumentParser(
        description="Google Drive Video Unique Screenshot Extractor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-l", "--link", help="Google Drive sharing link or ID")
    parser.add_argument("-n", "--name", help="Presenter Name (e.g., RAMYA)")
    parser.add_argument("-d", "--date", help="Presentation Date (e.g., 05-06-2026)")
    parser.add_argument("-t", "--threshold", type=float, default=8.0, 
                        help="Visual difference threshold for screenshot extraction")
    parser.add_argument("-s", "--sample-interval", type=float, default=1.0, 
                        help="Analysis sample interval in seconds (lower is more thorough)")
    parser.add_argument("-c", "--cooldown", type=float, default=10.0, 
                        help="Cooldown in seconds between screenshots to ignore transition artifacts")
    parser.add_argument("-cl", "--crop-left", type=float, default=0.0, 
                        help="Crop percentage from the left edge (0 to 100)")
    parser.add_argument("-cr", "--crop-right", type=float, default=0.0, 
                        help="Crop percentage from the right edge (0 to 100)")
    parser.add_argument("-ct", "--crop-top", type=float, default=0.0, 
                        help="Crop percentage from the top edge (0 to 100)")
    parser.add_argument("-cb", "--crop-bottom", type=float, default=0.0, 
                        help="Crop percentage from the bottom edge (0 to 100)")
    parser.add_argument("-ac", "--auto-crop", action="store_true",
                        help="Automatically detect and crop to the active presentation screen area")
    parser.add_argument("--no-confirm", action="store_true",
                        help="Bypass the crop preview confirmation step")
    parser.add_argument("--keep-video", action="store_true", 
                        help="Do not delete the downloaded video file after processing")
                        
    args = parser.parse_args()
    
    print("==================================================")
    print("    Google Drive Video Screenshot Extractor       ")
    print("==================================================\n")
    
    # 1. Interactive Inputs fallback
    link = args.link
    if not link:
        link = input("Enter Google Drive Video Link/ID: ").strip()
        while not link:
            link = input("Link cannot be empty. Enter Google Drive Link/ID: ").strip()
            
    name = args.name
    if not name:
        name = input("Enter Presenter Name: ").strip()
        while not name:
            name = input("Name cannot be empty. Enter Presenter Name: ").strip()
            
    date = args.date
    if not date:
        date = input("Enter Presentation Date (e.g., 05-06-2026): ").strip()
        while not date:
            date = input("Date cannot be empty. Enter Presentation Date (e.g., 05-06-2026): ").strip()
            
    # Verify date format DD-MM-YYYY (print warning if different but still allow it)
    if not re.match(r'^\d{2}-\d{2}-\d{4}$', date):
        print("\n[NOTE] Date formatting tip: Dates are typically in DD-MM-YYYY format (e.g., 05-06-2026).")
        print(f"Proceeding with your input: '{date}' (which will be sanitized for folder creation).\n")
        
    # Check if the input is a local file instead of a URL
    is_local_file = False
    downloaded_video_path = None
    
    if os.path.exists(link) and os.path.isfile(link):
        print(f"Local file detected: {link}")
        is_local_file = True
        video_path = link
    else:
        # 2. Download phase
        downloaded_video_path = download_from_gdrive(link)
        if not downloaded_video_path:
            print("Error: Could not obtain the video. Exiting.")
            sys.exit(1)
        video_path = downloaded_video_path

    # Crop inputs interactive fallback
    crop_left = args.crop_left
    crop_right = args.crop_right
    crop_top = args.crop_top
    crop_bottom = args.crop_bottom
    auto_crop = args.auto_crop
    
    has_cli_crop = (crop_left > 0.0 or crop_right > 0.0 or 
                    crop_top > 0.0 or crop_bottom > 0.0 or auto_crop)
                    
    choice = '3'
    if not has_cli_crop:
        print("Would you like to crop the video frame?")
        print("  1. Auto-detect shared presentation screen (Recommended - removes participant bars/margins)")
        print("  2. Manual percentage crop (from edges)")
        print("  3. No crop")
        
        choice = input("Enter choice (1, 2, or 3, default: 3): ").strip()
        if choice == '1':
            auto_crop = True
        elif choice == '2':
            # Generate the grid helper image to help them choose the percentages
            print("Generating crop grid helper image...")
            temp_output_dir = resolve_output_dir(name, date)
            grid_path = save_grid_preview(video_path, temp_output_dir)
            if grid_path:
                print(f"\n[HELP] A visual grid guide has been saved to:")
                print(f"--> {os.path.abspath(grid_path)}")
                print("Please open this image file to see the percentage grid lines overlaid on the frame.")
                print("You can read the Left (L), Right (R), Top (T), and Bottom (B) percentages directly from the lines.")
                print("Then enter the values below:\n")
                
            def get_percentage(prompt):
                while True:
                    val_str = input(prompt).strip()
                    if not val_str:
                        return 0.0
                    try:
                        val = float(val_str)
                        if 0.0 <= val < 100.0:
                            return val
                        print("Please enter a percentage between 0 and 100 (exclusive of 100).")
                    except ValueError:
                        print("Invalid input. Please enter a number.")
            
            crop_left = get_percentage("Crop from LEFT (%): ")
            crop_right = get_percentage("Crop from RIGHT (%): ")
            crop_top = get_percentage("Crop from TOP (%): ")
            crop_bottom = get_percentage("Crop from BOTTOM (%): ")
            print()
            
    # Run auto-crop boundary detection if enabled
    crop_bbox = None
    if auto_crop:
        print("Analyzing video to auto-detect presentation bounding box...")
        crop_bbox = detect_presentation_bbox(video_path)
        if crop_bbox:
            print(f"Detected presentation screen boundary: x={crop_bbox[0]}, y={crop_bbox[1]}, w={crop_bbox[2]}, h={crop_bbox[3]}\n")
        else:
            print("Warning: Auto-detection did not find a sufficiently large presentation screen (suspected webcam grid or dark frame).")
            print("Falling back to capturing FULL PAGE screenshots without cropping to avoid loss of data.\n")
            
    # Supported extensions check
    supported_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    _, ext = os.path.splitext(video_path.lower())
    if ext not in supported_extensions:
        print(f"[Warning] File extension '{ext}' is not explicitly in the supported list: {supported_extensions}")
        print("OpenCV will still attempt to parse the file container, but it may fail.\n")
        
    # Resolve output directory
    final_output_dir = resolve_output_dir(name, date)
    
    # Crop Preview step
    if has_cli_crop or auto_crop or (not has_cli_crop and choice in ('1', '2')):
        print("Generating crop preview...")
        preview_path = save_crop_preview(
            video_path=video_path,
            output_dir=final_output_dir,
            crop_left=crop_left,
            crop_right=crop_right,
            crop_top=crop_top,
            crop_bottom=crop_bottom,
            crop_bbox=crop_bbox
        )
        
        if preview_path:
            print(f"\n[IMPORTANT] A preview of the cropped frame has been saved to:")
            print(f"--> {os.path.abspath(preview_path)}")
            print("Please open this image file to verify if the presentation screen is correctly cropped.")
            if not args.no_confirm:
                print("Press ENTER to continue and analyze the video, or Ctrl+C to stop and adjust settings.\n")
                input("Press Enter to continue...")
            else:
                print("Proceeding automatically (--no-confirm enabled).\n")
                
    # 3. Processing phase
    try:
        output_dir, screenshots_extracted, duration_str, processing_time = process_video(
            video_path=video_path,
            presenter_name=name,
            presentation_date=date,
            threshold=args.threshold,
            sample_interval=args.sample_interval,
            cooldown=args.cooldown,
            crop_left=crop_left,
            crop_right=crop_right,
            crop_top=crop_top,
            crop_bottom=crop_bottom,
            crop_bbox=crop_bbox,
            auto_crop=auto_crop
        )
        
        if output_dir:
            # 4. Summary display
            print("\n" + "="*50)
            print("               PROCESSING SUMMARY               ")
            print("="*50)
            print(f"Video Duration:      {duration_str}")
            print(f"Screenshots Saved:   {screenshots_extracted}")
            print(f"Output Directory:    {os.path.abspath(output_dir)}")
            print(f"Processing Time:     {processing_time:.2f} seconds")
            print("="*50 + "\n")
        else:
            print("\nError: Processing failed.\n")
            
    except Exception as e:
        print(f"\nAn error occurred during video processing: {e}\n")
    finally:
        # 5. Cleanup phase
        if not is_local_file and downloaded_video_path and os.path.exists(downloaded_video_path):
            if args.keep_video:
                print(f"Keeping downloaded video: {downloaded_video_path}")
            else:
                try:
                    print(f"Cleaning up temporary downloaded video: {downloaded_video_path}")
                    os.remove(downloaded_video_path)
                    # Also try to remove parent directory if it's a unique temp download folder
                    parent_dir = os.path.dirname(downloaded_video_path)
                    if "temp_downloads" in parent_dir:
                        os.rmdir(parent_dir)
                except Exception as e:
                    print(f"Warning: Could not remove temporary file/folder: {e}")

if __name__ == "__main__":
    main()
