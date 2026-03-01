import cv2
import numpy as np

def detect_blocks(image_path):
    # 1. Load the image
    img = cv2.imread(image_path)
    if img is None:
        print("Error: Could not load image.")
        return

    # =======================================================
    # PHASE 1: FIND THE DYNAMIC ROI (BLACK FOAM MATS)
    # =======================================================
    hsv_full = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Define HSV range for the dark/black foam mats
    # Note: If the lights make the mats look gray, increase the Value (e.g., from 80 up to 120)
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([100, 100, 80]) 
    
    # Create a mask for the black mats
    black_mask = cv2.inRange(hsv_full, lower_black, upper_black)
    
    # Clean up the mask to remove thin shadows/noise
    kernel_large = np.ones((15, 15), np.uint8)
    black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_OPEN, kernel_large)
    black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel_large)

    # Find contours of the black mats
    contours_mats, _ = cv2.findContours(black_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter for very large contours to ignore tiny black objects
    mat_contours = [cnt for cnt in contours_mats if cv2.contourArea(cnt) > 20000]

    if not mat_contours:
        print("Warning: Could not detect the black foam mats. Falling back to full image.")
        roi = img
        roi_x, roi_y = 0, 0
    else:
        # Combine all mat contours into one giant bounding box
        combined_mats = np.vstack(mat_contours)
        roi_x, roi_y, roi_w, roi_h = cv2.boundingRect(combined_mats)
        
        # Crop the image to this exact bounding box
        roi = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        
        # Draw a bright purple box around the ROI on the original image for debugging
        cv2.rectangle(img, (roi_x, roi_y), (roi_x+roi_w, roi_y+roi_h), (255, 0, 255), 4)
        cv2.putText(img, "Dynamic ROI (Foam Mats)", (roi_x, roi_y-15), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)


    # =======================================================
    # PHASE 2: DETECT BLOCKS INSIDE THE DYNAMIC ROI
    # =======================================================
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    color_ranges = {
        "Orange": {"lower": np.array([8, 100, 150]), "upper": np.array([18, 255, 255])},
        "Light_Blue": {"lower": np.array([80, 20, 200]), "upper": np.array([100, 100, 255])},
        "Green": {"lower": np.array([25, 30, 200]), "upper": np.array([45, 120, 255])},
        "Brown_Wood": {"lower": np.array([15, 20, 150]), "upper": np.array([25, 100, 255])}
    }

    block_counts = {"Orange": 0, "Light_Blue": 0, "Green": 0, "Brown_Wood": 0}

    for color_name, bounds in color_ranges.items():
        mask = cv2.inRange(hsv_roi, bounds["lower"], bounds["upper"])
        
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            if cv2.contourArea(cnt) > 100: 
                block_counts[color_name] += 1
                
                # Draw boxes relative to the original image so it displays nicely
                x, y, w, h = cv2.boundingRect(cnt)
                global_x = roi_x + x
                global_y = roi_y + y
                cv2.rectangle(img, (global_x, global_y), (global_x+w, global_y+h), (0, 255, 0), 2)
                cv2.putText(img, color_name, (global_x, global_y-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

    # 6. Display results
    print("--- Blocks Detected Inside Workspace ---")
    for color, count in block_counts.items():
        print(f"{color}: {count}")

    # Resize slightly so it fits on most monitors when viewing
    display_img = cv2.resize(img, (1280, 720))
    cv2.imshow("Dynamic ROI & Block Tracking", display_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_blocks("test_image.png")