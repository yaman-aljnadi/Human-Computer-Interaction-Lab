import cv2
import numpy as np

def boxes_overlap(r1, r2):
    """Checks if two rectangles (x, y, w, h) intersect."""
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2
    
    # If one rectangle is entirely to the left of the other
    if (x1 + w1 < x2) or (x2 + w2 < x1):
        return False
    # If one rectangle is entirely above the other
    if (y1 + h1 < y2) or (y2 + h2 < y1):
        return False
    return True

def detect_and_check_sorting(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print("Error: Could not load image.")
        return

    # =======================================================
    # PHASE 1: DYNAMIC ROI (Fixing the Carpet Issue)
    # =======================================================
    hsv_full = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([179, 255, 80]) 
    
    black_mask = cv2.inRange(hsv_full, lower_black, upper_black)
    kernel_large = np.ones((15, 15), np.uint8)
    black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_OPEN, kernel_large)
    black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel_large)

    contours_mats, _ = cv2.findContours(black_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Grab ONLY the absolute largest black contour to prevent grabbing the carpet
    if contours_mats:
        largest_mat = max(contours_mats, key=cv2.contourArea)
        if cv2.contourArea(largest_mat) > 20000:
            roi_x, roi_y, roi_w, roi_h = cv2.boundingRect(largest_mat)
            roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
            cv2.rectangle(img, (roi_x, roi_y), (roi_x+roi_w, roi_y+roi_h), (255, 0, 255), 4)
        else:
            roi = img
            roi_x, roi_y = 0, 0
    else:
        roi = img
        roi_x, roi_y = 0, 0

    # =======================================================
    # PHASE 2: DETECT BLOCKS 
    # =======================================================
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    color_ranges = {
        "Orange": {"lower": np.array([8, 100, 150]), "upper": np.array([18, 255, 255])},
        "Light_Blue": {"lower": np.array([80, 20, 200]), "upper": np.array([100, 100, 255])},
        "Green": {"lower": np.array([25, 30, 200]), "upper": np.array([45, 120, 255])},
        "Brown_Wood": {"lower": np.array([15, 20, 150]), "upper": np.array([25, 100, 255])}
    }

    block_contours_by_color = {"Orange": [], "Light_Blue": [], "Green": [], "Brown_Wood": []}
    color_bgr = {"Orange": (0, 165, 255), "Light_Blue": (255, 200, 0), "Green": (0, 255, 0), "Brown_Wood": (42, 42, 165)}

    for color_name, bounds in color_ranges.items():
        mask = cv2.inRange(hsv_roi, bounds["lower"], bounds["upper"])
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            if cv2.contourArea(cnt) > 100: # Raised slightly to ignore speckles
                # Offset the contour to match the original image coordinates
                cnt_offset = cnt + np.array([[roi_x, roi_y]])
                block_contours_by_color[color_name].append(cnt_offset)

    # =======================================================
    # PHASE 3: DYNAMIC SORTING LOGIC
    # =======================================================
    is_sorted = True
    sorting_status_msg = "All blocks are sorted!"
    group_boxes = {}

    for color, contours in block_contours_by_color.items():
        if len(contours) == 0:
            continue
            
        # 1. Combine all blocks of this color to find the master bounding box
        all_points = np.vstack(contours)
        gx, gy, gw, gh = cv2.boundingRect(all_points)
        group_area = gw * gh
        
        # 2. Calculate Density
        blocks_area = sum(cv2.contourArea(c) for c in contours)
        density = blocks_area / group_area if group_area > 0 else 0
        
        group_boxes[color] = (gx, gy, gw, gh)
        
        # Draw the Group Box (Thick outline around the whole pile)
        cv2.rectangle(img, (gx, gy), (gx+gw, gy+gh), color_bgr[color], 3)
        cv2.putText(img, f"{color} Pile (Den: {density:.2f})", (gx, gy-10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_bgr[color], 2)

        # Threshold: If density is below 15%, the blocks are scattered
        # (You can tweak this 0.15 value up or down based on testing!)
        if density < 0.15 and len(contours) > 1:
            is_sorted = False
            sorting_status_msg = f"{color} blocks are scattered!"

    # 3. Check for Overlaps (Are the piles mixed?)
    colors_present = list(group_boxes.keys())
    for i in range(len(colors_present)):
        for j in range(i + 1, len(colors_present)):
            col1 = colors_present[i]
            col2 = colors_present[j]
            
            if boxes_overlap(group_boxes[col1], group_boxes[col2]):
                is_sorted = False
                sorting_status_msg = f"The {col1} and {col2} piles are mixed together!"

    # =======================================================
    # DISPLAY RESULTS
    # =======================================================
    print(f"\n--- Sorting Status: {'SORTED' if is_sorted else 'NOT SORTED'} ---")
    print(f"Reason: {sorting_status_msg}")
    
    # Draw huge text on the screen
    status_color = (0, 255, 0) if is_sorted else (0, 0, 255)
    cv2.putText(img, f"STATUS: {sorting_status_msg}", (50, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, status_color, 3)

    display_img = cv2.resize(img, (1280, 720))
    cv2.imshow("Dynamic Sorting Tracker", display_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_and_check_sorting("test_image.png")