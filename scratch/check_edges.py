import cv2
import numpy as np

def analyze_edges(path):
    img = cv2.imread(path)
    if img is None:
        print(f"Failed to read {path}")
        return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    
    # Calculate percentage of edge pixels
    edge_ratio = np.sum(edges > 0) / edges.size * 100
    print(f"Image {path}: shape={img.shape[:2]}, edge ratio={edge_ratio:.3f}%")

if __name__ == "__main__":
    analyze_edges("c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_2/Screenshot_001.png")
    analyze_edges("c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_1/Screenshot_001.png")
    analyze_edges("c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_1/Screenshot_012.png")
    analyze_edges("c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_1/Screenshot_020.png")
