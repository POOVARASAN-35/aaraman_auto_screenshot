import cv2
import numpy as np
import os
from test_refined_crop import detect_presentation_segment

for pct in [5, 25, 50, 75]:
    path = f"Output/layout_sample_{pct}.png"
    if os.path.exists(path):
        detect_presentation_segment(path, f"sample_{pct}")
