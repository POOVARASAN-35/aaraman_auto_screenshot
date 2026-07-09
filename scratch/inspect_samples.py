import cv2
import numpy as np

def inspect_image(path):
    img = cv2.imread(path)
    if img is None:
        print(f"Failed to read {path}")
        return
    h, w, c = img.shape
    print(f"Image {path}: shape={img.shape}")
    
    # Let's find column-wise and row-wise properties
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Print mean brightness of columns in steps
    col_means = np.mean(gray, axis=0)
    row_means = np.mean(gray, axis=1)
    
    # Find regions where brightness is not purely black (threshold say > 5)
    non_black_cols = np.where(col_means > 5)[0]
    non_black_rows = np.where(row_means > 5)[0]
    
    if len(non_black_cols) > 0:
        print(f"  Non-black columns range: {non_black_cols[0]} to {non_black_cols[-1]}")
    else:
        print("  No non-black columns found!")
        
    if len(non_black_rows) > 0:
        print(f"  Non-black rows range: {non_black_rows[0]} to {non_black_rows[-1]}")
    else:
        print("  No non-black rows found!")

    # Let's inspect column variance/standard deviation to detect texture/edges
    col_std = np.std(gray, axis=0)
    print(f"  Max col std: {np.max(col_std):.2f}, Mean col std: {np.mean(col_std):.2f}")
    
    # Print out some ranges of std/mean to understand the layout
    # For example, let's print every 100 columns
    print("  Column mean & std every 100 pixels:")
    for x in range(0, w, 100):
        chunk_mean = np.mean(col_means[x:x+100]) if x+100 <= w else np.mean(col_means[x:])
        chunk_std = np.mean(col_std[x:x+100]) if x+100 <= w else np.mean(col_std[x:])
        print(f"    x={x:04d}..{min(x+100, w):04d}: mean={chunk_mean:.2f}, std={chunk_std:.2f}")

if __name__ == "__main__":
    inspect_image("Output/layout_sample_25.png")
    print("-" * 50)
    inspect_image("Output/layout_sample_50.png")
