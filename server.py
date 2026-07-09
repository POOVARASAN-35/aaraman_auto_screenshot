import uvicorn
import os
import sys
import re
import time
import datetime
import uuid
import shutil
import zipfile
import io
import threading
import warnings
import cv2
import numpy as np
import gdown
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List

# Silence BeautifulSoup warnings from gdown
try:
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:
    pass

app = FastAPI(title="SlideCapture AI Backend")

# Ensure Output and Temp directories exist
os.makedirs("Output", exist_ok=True)
os.makedirs("temp_downloads", exist_ok=True)

# Global Tasks Store
# task_id -> { status, progress, progress_detail, logs, screenshots_saved, screenshots, video_duration, elapsed_time, cancel_requested, run_id }
tasks = {}
tasks_lock = threading.Lock()

class ExtractRequest(BaseModel):
    video_path: str
    presenter_name: str
    presentation_date: str
    threshold: float = 8.0
    sample_interval: float = 1.0
    cooldown: float = 10.0
    crop_mode: str = "auto" # auto, manual, none
    crop_left: float = 0.0
    crop_right: float = 0.0
    crop_top: float = 0.0
    crop_bottom: float = 0.0

class PreviewRequest(BaseModel):
    video_path: str

# ----------------- Core Helper Functions -----------------

def clean_gdrive_url(url):
    url = url.strip()
    if re.match(r'^[a-zA-Z0-9_-]{25,50}$', url):
        return f"https://drive.google.com/uc?id={url}"
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

def resolve_output_dir(presenter_name, presentation_date, base_output_dir="Output"):
    sanitized_name = re.sub(r'[<>:"/\\|?* ]', '_', presenter_name)
    sanitized_date = re.sub(r'[<>:"/\\|?* ]', '_', presentation_date)
    sanitized_name = re.sub(r'_+', '_', sanitized_name).strip('_')
    sanitized_date = re.sub(r'_+', '_', sanitized_date).strip('_')
    
    folder_base_name = f"{sanitized_name}_{sanitized_date}"
    os.makedirs(base_output_dir, exist_ok=True)
    
    target_dir = os.path.join(base_output_dir, folder_base_name)
    if not os.path.exists(target_dir):
        return target_dir, folder_base_name
        
    counter = 1
    while True:
        candidate_dir = os.path.join(base_output_dir, f"{folder_base_name}_{counter}")
        if not os.path.exists(candidate_dir):
            return candidate_dir, f"{folder_base_name}_{counter}"
        counter += 1

def log_task(task_id, message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(f"Task {task_id}: {formatted_msg}")
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id]['logs'].append(formatted_msg)

def update_task(task_id, **kwargs):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id].update(kwargs)

# ----------------- Video Processing Core -----------------

def detect_presentation_bbox_for_frame(frame, last_valid_bbox=None, max_gap=150):
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    col_means = np.mean(gray, axis=0)
    col_stds = np.std(gray, axis=0)
    
    is_bg = (col_means < 15.0) | (col_stds < 2.0)
    active_indices = np.where(~is_bg)[0]
    
    if len(active_indices) == 0:
        return last_valid_bbox if last_valid_bbox is not None else (0, 0, width, height)
        
    raw_segments = []
    start = active_indices[0]
    for i in range(1, len(active_indices)):
        if active_indices[i] != active_indices[i-1] + 1:
            raw_segments.append((start, active_indices[i-1]))
            start = active_indices[i]
    raw_segments.append((start, active_indices[-1]))
    
    raw_segments = [seg for seg in raw_segments if (seg[1] - seg[0]) >= 10]
    if not raw_segments:
        return last_valid_bbox if last_valid_bbox is not None else (0, 0, width, height)
        
    presentation_segments = []
    for s, e in raw_segments:
        seg_w = e - s
        is_rightmost_panel = False
        if s > width * 0.65 and e >= width * 0.95 and seg_w < width * 0.35:
            is_rightmost_panel = True
            
        if not is_rightmost_panel:
            presentation_segments.append((s, e))
            
    if not presentation_segments:
        presentation_segments = raw_segments
        
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
        
    merged_presentation.sort(key=lambda val: val[1] - val[0], reverse=True)
    best_x1, best_x2 = merged_presentation[0]
    
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
    
    if (w_box * h_box) < (width * height * 0.10):
        return last_valid_bbox if last_valid_bbox is not None else (0, 0, width, height)
        
    return (best_x1, best_y1, w_box, h_box)

def detect_presentation_bbox(video_path, samples=5):
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
    height, width = frame.shape[:2]
    if width <= 0 or height <= 0:
        return False
        
    scale = 640.0 / width
    resized = cv2.resize(frame, (640, int(height * scale)))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    if face_cascade.empty():
        return False
        
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
    return len(faces) >= face_threshold

def apply_crop(frame, crop_left=0.0, crop_right=0.0, crop_top=0.0, crop_bottom=0.0):
    if crop_left == 0.0 and crop_right == 0.0 and crop_top == 0.0 and crop_bottom == 0.0:
        return frame
        
    height, width = frame.shape[:2]
    left_px = int(width * (crop_left / 100.0))
    right_px = int(width * (1.0 - (crop_right / 100.0)))
    top_px = int(height * (crop_top / 100.0))
    bottom_px = int(height * (1.0 - (crop_bottom / 100.0)))
    
    left_px = max(0, min(width - 1, left_px))
    right_px = max(left_px + 1, min(width, right_px))
    top_px = max(0, min(height - 1, top_px))
    bottom_px = max(top_px + 1, min(height, bottom_px))
    
    return frame[top_px:bottom_px, left_px:right_px]

def is_different(frame1, frame2, pixel_threshold=8.0):
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    
    resized1 = cv2.resize(gray1, (64, 64))
    resized2 = cv2.resize(gray2, (64, 64))
    
    blurred1 = cv2.GaussianBlur(resized1, (5, 5), 0)
    blurred2 = cv2.GaussianBlur(resized2, (5, 5), 0)
    
    diff = cv2.absdiff(blurred1, blurred2)
    mean_diff = np.mean(diff)
    
    return mean_diff > pixel_threshold, mean_diff

# ----------------- Background Worker Thread -----------------

def extraction_worker(
    task_id: str,
    req: ExtractRequest,
    output_dir: str,
    run_id: str
):
    video_path = req.video_path
    presenter_name = req.presenter_name
    presentation_date = req.presentation_date
    threshold = req.threshold
    sample_interval = req.sample_interval
    cooldown = req.cooldown
    crop_mode = req.crop_mode
    crop_left = req.crop_left
    crop_right = req.crop_right
    crop_top = req.crop_top
    crop_bottom = req.crop_bottom

    is_local_file = False
    downloaded_video_path = None
    
    try:
        # --- PHASE 1: DOWNLOAD ---
        update_task(task_id, status="downloading", progress=5, progress_detail="Checking video location...")
        
        if os.path.exists(video_path) and os.path.isfile(video_path):
            log_task(task_id, f"Local file detected: {video_path}")
            is_local_file = True
            local_video_path = video_path
            update_task(task_id, progress=25, progress_detail="Local file loaded.")
        else:
            log_task(task_id, "Google Drive link detected. Initializing download...")
            is_gdrive = ("drive.google.com" in video_path or 
                         "docs.google.com" in video_path or 
                         re.match(r'^[a-zA-Z0-9_-]{25,50}$', video_path))
                         
            if not is_gdrive:
                log_task(task_id, "Warning: Link does not resemble standard Google Drive URLs. Attempting anyway...")
            
            is_folder = "drive/folders/" in video_path or "folders/" in video_path
            unique_dir = os.path.join("temp_downloads", f"dl_{uuid.uuid4().hex[:8]}")
            os.makedirs(unique_dir, exist_ok=True)
            
            if is_folder:
                log_task(task_id, "Folder link detected. Fetching folder structure...")
                update_task(task_id, progress_detail="Downloading folder from Drive...")
                gdown.download_folder(url=video_path, output=unique_dir, quiet=True, remaining_ok=True)
                
                video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
                video_files = []
                for root, dirs, files in os.walk(unique_dir):
                    for f in files:
                        if f.lower().endswith(video_extensions):
                            video_files.append(os.path.join(root, f))
                
                if video_files:
                    video_files.sort(key=lambda p: os.path.getsize(p), reverse=True)
                    downloaded_video_path = video_files[0]
                    log_task(task_id, f"Folder downloaded. Selected video: {os.path.basename(downloaded_video_path)}")
                else:
                    raise Exception("Folder downloaded, but no video file was found inside.")
            else:
                direct_url = clean_gdrive_url(video_path)
                update_task(task_id, progress_detail="Downloading file from Drive...")
                output_target = unique_dir + os.sep
                downloaded_path = gdown.download(url=direct_url, output=output_target, quiet=True, fuzzy=True)
                
                if downloaded_path and os.path.exists(downloaded_path):
                    downloaded_video_path = downloaded_path
                    log_task(task_id, f"File downloaded successfully: {os.path.basename(downloaded_video_path)}")
                else:
                    # Fallback raw ID check
                    if re.match(r'^[a-zA-Z0-9_-]{25,50}$', video_path):
                        log_task(task_id, "File download failed. Retrying treating ID as a folder...")
                        folder_url = f"https://drive.google.com/drive/folders/{video_path}"
                        gdown.download_folder(url=folder_url, output=unique_dir, quiet=True, remaining_ok=True)
                        video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
                        video_files = []
                        for root, dirs, files in os.walk(unique_dir):
                            for f in files:
                                if f.lower().endswith(video_extensions):
                                    video_files.append(os.path.join(root, f))
                        if video_files:
                            video_files.sort(key=lambda p: os.path.getsize(p), reverse=True)
                            downloaded_video_path = video_files[0]
                            log_task(task_id, f"Fallback folder downloaded video: {os.path.basename(downloaded_video_path)}")
                        else:
                            raise Exception("Download failed. No files saved.")
                    else:
                        raise Exception("Download failed. Please check sharing permissions.")
            
            local_video_path = downloaded_video_path
            update_task(task_id, progress=25, progress_detail="Download completed.")
            
        # Check cancellation
        if tasks[task_id]['cancel_requested']:
            raise Exception("Cancelled")

        # --- PHASE 2: INITIALIZATION & AUTO-CROP ---
        log_task(task_id, "Opening video container and analyzing metadata...")
        cap = cv2.VideoCapture(local_video_path)
        if not cap.isOpened():
            raise Exception("OpenCV failed to open the video file container.")
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0:
            fps = 25.0
            
        duration_seconds = total_frames / fps if total_frames > 0 else 0
        duration_str = str(datetime.timedelta(seconds=int(duration_seconds)))
        update_task(task_id, video_duration=duration_str)
        
        log_task(task_id, f"Video Duration: {duration_str}")
        log_task(task_id, f"Video FPS: {fps:.2f}")
        log_task(task_id, f"Total Frames: {total_frames}")
        
        # Bounding box detection if auto crop
        crop_bbox = None
        if crop_mode == "auto":
            log_task(task_id, "Analyzing video to auto-detect presentation screen bounds...")
            update_task(task_id, progress=27, progress_detail="Auto-detecting screen boundaries...")
            crop_bbox = detect_presentation_bbox(local_video_path)
            if crop_bbox:
                log_task(task_id, f"Auto-Crop Area detected: x={crop_bbox[0]}, y={crop_bbox[1]}, w={crop_bbox[2]}, h={crop_bbox[3]}")
                update_task(task_id, progress=30, progress_detail="Screen bounds detected.")
            else:
                log_task(task_id, "Warning: Bounding box detection failed. Using full frame.")
                update_task(task_id, progress=30, progress_detail="No screen bounds found. Using full-frame.")
        else:
            update_task(task_id, progress=30, progress_detail="Ready for frame parsing.")

        if tasks[task_id]['cancel_requested']:
            raise Exception("Cancelled")

        # Save a crop preview image
        cap_preview = cv2.VideoCapture(local_video_path)
        if cap_preview.isOpened():
            seek_frame = int(min(total_frames - 1, max(1, fps * 5)))
            cap_preview.set(cv2.CAP_PROP_POS_FRAMES, seek_frame)
            ret_p, frame_p = cap_preview.read()
            if ret_p:
                if crop_bbox:
                    x, y, w, h = crop_bbox
                    height_o, width_o = frame_p.shape[:2]
                    frame_p = frame_p[max(0, y):min(height_o, y+h), max(0, x):min(width_o, x+w)]
                if crop_mode == "manual":
                    frame_p = apply_crop(frame_p, crop_left, crop_right, crop_top, crop_bottom)
                os.makedirs(output_dir, exist_ok=True)
                cv2.imwrite(os.path.join(output_dir, "crop_preview.png"), frame_p)
            cap_preview.release()

        # --- PHASE 3: EXTRACTION ---
        update_task(task_id, status="analyzing", progress=30, progress_detail="Extracting unique slides...")
        log_task(task_id, "Slide extraction loop started...")
        
        frame_step = max(1, int(round(fps * sample_interval)))
        saved_count = 0
        last_saved_frame = None
        last_saved_time = -cooldown
        last_valid_bbox = crop_bbox
        
        height_orig_baseline, width_orig_baseline = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        if width_orig_baseline <= 0:
            width_orig_baseline = 1920
        is_baseline_subrectangle = (crop_bbox is not None and crop_bbox[2] < width_orig_baseline * 0.95)
        
        frame_idx = 0
        start_process_time = time.time()
        
        while True:
            # Check cancel in loop
            if tasks[task_id]['cancel_requested']:
                raise Exception("Cancelled")
                
            actual_skipped = 0
            for _ in range(frame_step - 1):
                grabbed = cap.grab()
                if not grabbed:
                    break
                frame_idx += 1
                actual_skipped += 1
                
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            
            # Auto-crop logic inside loop
            if crop_mode == "auto":
                current_bbox = detect_presentation_bbox_for_frame(frame, last_valid_bbox=last_valid_bbox)
                
                # Suspected grid check
                height_orig, width_orig = frame.shape[:2]
                if is_baseline_subrectangle and current_bbox[2] >= width_orig * 0.95:
                    continue
                    
                if last_valid_bbox is not None:
                    px, py, pw, ph = last_valid_bbox
                    cx, cy, cw, ch = current_bbox
                    if (abs(cx - px) < 15 and abs(cy - py) < 15 and 
                        abs(cw - pw) < 15 and abs(ch - ph) < 15):
                        current_bbox = last_valid_bbox
                        
                last_valid_bbox = current_bbox
                x, y, w, h = current_bbox
                frame = frame[max(0, y):min(height_orig, y+h), max(0, x):min(width_orig, x+w)]
            elif crop_bbox: # baseline crop box if auto crop detected but dynamic disabled or similar
                x, y, w, h = crop_bbox
                height_orig, width_orig = frame.shape[:2]
                frame = frame[max(0, y):min(height_orig, y+h), max(0, x):min(width_orig, x+w)]
                
            if crop_mode == "manual":
                frame = apply_crop(frame, crop_left, crop_right, crop_top, crop_bottom)
                
            # Skip black screens
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
                # Suspected webcam grid checks
                if is_participant_grid(frame):
                    timestamp_str = str(datetime.timedelta(seconds=int(current_time_seconds)))
                    log_task(task_id, f"[{timestamp_str}] Ignored frame - suspected participant webcam grid (multiple faces detected)")
                    continue
                    
                saved_count += 1
                screenshot_name = f"Screenshot_{saved_count:03d}.png"
                screenshot_path = os.path.join(output_dir, screenshot_name)
                
                os.makedirs(output_dir, exist_ok=True)
                cv2.imwrite(screenshot_path, frame)
                
                last_saved_frame = frame.copy()
                last_saved_time = current_time_seconds
                
                timestamp_str = str(datetime.timedelta(seconds=int(current_time_seconds)))
                log_task(task_id, f"[{timestamp_str}] Saved {screenshot_name} - {reason}")
                
                # Update task's screenshots list
                with tasks_lock:
                    tasks[task_id]['screenshots_saved'] = saved_count
                    tasks[task_id]['screenshots'].append(screenshot_name)
            
            # Progress reporting
            if total_frames > 0:
                progress_val = 30 + int((frame_idx / total_frames) * 70)
            else:
                progress_val = 50 # fallback if total frames is unknown
                
            elapsed = time.time() - start_process_time
            update_task(
                task_id, 
                progress=min(99, progress_val), 
                progress_detail=f"Processed frame {frame_idx}/{total_frames} ({int(current_time_seconds)}s)",
                elapsed_time=elapsed
            )
            
        cap.release()
        
        # Done
        update_task(
            task_id, 
            status="completed", 
            progress=100, 
            progress_detail="Extraction finished successfully.",
            elapsed_time=time.time() - start_process_time
        )
        log_task(task_id, f"Successfully completed. Extracted {saved_count} slides.")
        
    except Exception as e:
        # Cleanup cap if open
        if 'cap' in locals() and cap.isOpened():
            cap.release()
            
        err_msg = str(e)
        if err_msg == "Cancelled":
            update_task(task_id, status="cancelled", progress_detail="Cancelled by user.")
            log_task(task_id, "Task execution cancelled by user request.")
        else:
            update_task(task_id, status="failed", progress_detail="Process error occurred.", error=err_msg)
            log_task(task_id, f"Task failed with error: {err_msg}")
            
    finally:
        # Clean up downloaded video
        if not is_local_file and downloaded_video_path and os.path.exists(downloaded_video_path):
            try:
                log_task(task_id, "Cleaning up downloaded temporary video files...")
                os.remove(downloaded_video_path)
                parent_dir = os.path.dirname(downloaded_video_path)
                if "temp_downloads" in parent_dir:
                    os.rmdir(parent_dir)
            except Exception as e:
                log_task(task_id, f"Warning: Could not remove temp downloaded video: {e}")

# ----------------- FastAPI Web Endpoints -----------------

@app.post("/api/preview/generate")
def generate_preview(req: PreviewRequest):
    video_path = req.video_path.strip()
    is_gdrive = ("drive.google.com" in video_path or 
                 "docs.google.com" in video_path or 
                 re.match(r'^[a-zA-Z0-9_-]{25,50}$', video_path))
                 
    # Determine local vs remote
    if os.path.exists(video_path) and os.path.isfile(video_path):
        target_path = video_path
    elif is_gdrive:
        target_path = clean_gdrive_url(video_path)
    else:
        raise HTTPException(status_code=400, detail="Provided path is not a local file or a valid Drive URL.")
        
    # Attempt to open streaming URL or local file
    cap = cv2.VideoCapture(target_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Failed to open video container. Ensure Drive permissions are 'Anyone with link'.")
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
        
    # Seek to 5 seconds
    seek_frame = int(min(total_frames - 1, max(1, fps * 5))) if total_frames > 0 else int(fps * 5)
    cap.set(cv2.CAP_PROP_POS_FRAMES, seek_frame)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        raise HTTPException(status_code=400, detail="Could not capture reference frame at 5-second mark.")
        
    # Save preview image in static folder to allow instant loading
    preview_filename = f"preview_{uuid.uuid4().hex[:8]}.png"
    preview_static_dir = os.path.join("static", "previews")
    os.makedirs(preview_static_dir, exist_ok=True)
    
    # Delete old previews to save space
    for old_file in os.listdir(preview_static_dir):
        try:
            os.remove(os.path.join(preview_static_dir, old_file))
        except:
            pass
            
    preview_save_path = os.path.join(preview_static_dir, preview_filename)
    cv2.imwrite(preview_save_path, frame)
    
    return {"preview_url": f"/static/previews/{preview_filename}"}

@app.post("/api/extract/start")
def start_extraction(req: ExtractRequest, background_tasks: BackgroundTasks):
    task_id = uuid.uuid4().hex
    
    # Resolve directory
    output_dir, run_id = resolve_output_dir(req.presenter_name, req.presentation_date)
    
    # Init Task Object
    tasks[task_id] = {
        "run_id": run_id,
        "status": "pending",
        "progress": 0,
        "progress_detail": "Task queued...",
        "logs": [],
        "screenshots_saved": 0,
        "screenshots": [],
        "video_duration": "Unknown",
        "elapsed_time": 0.0,
        "cancel_requested": False
    }
    
    log_task(task_id, f"Extraction request received. Resolved Run ID: {run_id}")
    
    # Spawn background worker thread
    t = threading.Thread(
        target=extraction_worker,
        args=(task_id, req, output_dir, run_id),
        daemon=True
    )
    t.start()
    
    return {"task_id": task_id, "run_id": run_id}

@app.get("/api/extract/status/{task_id}")
def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

@app.post("/api/extract/cancel/{task_id}")
def cancel_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    with tasks_lock:
        tasks[task_id]['cancel_requested'] = True
        
    return {"status": "cancellation_requested"}

@app.get("/api/history")
def get_history():
    runs = []
    output_dir = "Output"
    if os.path.exists(output_dir):
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            if os.path.isdir(item_path):
                # Count files inside
                files = [f for f in os.listdir(item_path) if f.lower().endswith('.png') and f.startswith('Screenshot_')]
                runs.append({
                    "id": item,
                    "file_count": len(files),
                    "mtime": os.path.getmtime(item_path)
                })
    # Sort runs by modification time of the directory (newest first)
    runs.sort(key=lambda r: r["mtime"], reverse=True)
    return {"runs": runs}

@app.get("/api/history/{run_id}")
def get_run_details(run_id: str):
    run_dir = os.path.join("Output", run_id)
    if not os.path.exists(run_dir):
        raise HTTPException(status_code=404, detail="Run not found")
        
    files = [f for f in os.listdir(run_dir) if f.lower().endswith('.png') and f.startswith('Screenshot_')]
    files.sort()
    return {"run_id": run_id, "screenshots": files}

@app.delete("/api/history/{run_id}")
def delete_run(run_id: str):
    run_dir = os.path.join("Output", run_id)
    if not os.path.exists(run_dir):
        raise HTTPException(status_code=404, detail="Run folder not found")
    try:
        shutil.rmtree(run_dir)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history/{run_id}/download-zip")
def download_zip(run_id: str):
    run_dir = os.path.join("Output", run_id)
    if not os.path.exists(run_dir):
        raise HTTPException(status_code=404, detail="Run not found")
        
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(run_dir):
            for file in files:
                # Include all slides but exclude helper previews
                if file.lower().endswith('.png') and file.startswith('Screenshot_'):
                    file_path = os.path.join(root, file)
                    zip_file.write(file_path, arcname=file)
                    
    memory_file.seek(0)
    return StreamingResponse(
        memory_file,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={run_id}_slides.zip"}
    )

# Serve Index page at Root
@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# Mount directories
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/output", StaticFiles(directory="Output"), name="output")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
