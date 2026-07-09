import cv2
import time

def test_face_detection(path):
    img = cv2.imread(path)
    if img is None:
        print(f"Failed to read {path}")
        return
        
    start = time.time()
    h, w = img.shape[:2]
    # Resize to width 640 to speed up detection significantly
    scale = 640.0 / w
    resized = cv2.resize(img, (640, int(h * scale)))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    
    # Load pre-trained Haar Cascade face detector
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # Detect faces
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(20, 20))
    duration = time.time() - start
    
    print(f"Image {path}: original={w}x{h}, resized={resized.shape[1]}x{resized.shape[0]}, detected {len(faces)} faces, took {duration:.3f}s")
    for i, (fx, fy, fw, fh) in enumerate(faces):
        # Convert back to original coordinates
        orig_x = int(fx / scale)
        orig_y = int(fy / scale)
        orig_w = int(fw / scale)
        orig_h = int(fh / scale)
        print(f"  Face {i+1}: original x={orig_x}, y={orig_y}, w={orig_w}, h={orig_h}")

if __name__ == "__main__":
    test_face_detection("c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_1/Screenshot_001.png")
    test_face_detection("c:/Users/arasu/aaraman/Output/Kalpanasankar_04-06-2026_1/Screenshot_012.png")
