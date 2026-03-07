import cv2
import numpy as np

class VisionTracker:
    def __init__(self):
        # Widened HSV ranges for pastel blocks
        self.color_ranges = {
            "Orange": {"lower": np.array([5, 50, 150]), "upper": np.array([22, 255, 255])},
            "Light_Blue": {"lower": np.array([80, 40, 150]), "upper": np.array([110, 255, 255])},
            "Green": {"lower": np.array([35, 40, 150]), "upper": np.array([80, 255, 255])},
            # "Brown_Wood": {"lower": np.array([10, 40, 100]), "upper": np.array([25, 200, 255])}
        }
        
        self.color_bgr = {
            "Orange": (0, 165, 255), 
            "Light_Blue": (255, 200, 0), 
            "Green": (0, 255, 0), 
            "Brown_Wood": (42, 42, 165)
        }
        
        self.latest_status = "Waiting for data..."
        self.is_sorted = False
        self.block_counts = {"Orange": 0, "Light_Blue": 0, "Green": 0, "Brown_Wood": 0}

    def boxes_overlap(self, r1, r2):
        """Checks if two rectangles (x, y, w, h) intersect."""
        x1, y1, w1, h1 = r1
        x2, y2, w2, h2 = r2
        if (x1 + w1 < x2) or (x2 + w2 < x1): return False
        if (y1 + h1 < y2) or (y2 + h2 < y1): return False
        return True

    def process_frame(self, frame, depth_frame=None):
        img = frame.copy()

        # Keep heatmap viewer for depth debugging
        if depth_frame is not None and np.max(depth_frame) > 0:
            depth_colormap = cv2.normalize(depth_frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            depth_colormap = cv2.applyColorMap(depth_colormap, cv2.COLORMAP_JET)
            # cv2.imshow("Raw Depth Heatmap", depth_colormap)

        # =======================================================
        # PHASE 1 & 2: DETECT BLOCKS BY COLOR
        # =======================================================
        hsv_full = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        block_contours_by_color = {"Orange": [], "Light_Blue": [], "Green": [], "Brown_Wood": []}
        
        # Reset counters
        self.block_counts = {k: 0 for k in self.block_counts}

        for color_name, bounds in self.color_ranges.items():
            mask = cv2.inRange(hsv_full, bounds["lower"], bounds["upper"])
            
            kernel = np.ones((7,7), np.uint8) 
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for cnt in contours:
                if cv2.contourArea(cnt) > 300: 
                    block_contours_by_color[color_name].append(cnt)
                    self.block_counts[color_name] += 1
                    
                    # Draw borders directly on the image
                    cv2.drawContours(img, [cnt], -1, self.color_bgr[color_name], 2)

        # =======================================================
        # PHASE 3: DYNAMIC SORTING LOGIC
        # =======================================================
        self.is_sorted = True
        sorting_status_msg = "All blocks are sorted!"
        group_boxes = {}

        for color, contours in block_contours_by_color.items():
            if len(contours) == 0:
                continue
                
            all_points = np.vstack(contours)
            gx, gy, gw, gh = cv2.boundingRect(all_points)
            group_area = gw * gh
            
            blocks_area = sum(cv2.contourArea(c) for c in contours)
            density = blocks_area / group_area if group_area > 0 else 0
            
            group_boxes[color] = (gx, gy, gw, gh)
            
            # Draw the bounding box for the whole color pile
            cv2.rectangle(img, (gx, gy), (gx+gw, gy+gh), self.color_bgr[color], 3)
            cv2.putText(img, f"{color} Pile (Den: {density:.2f})", (gx, gy-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.color_bgr[color], 2)

            # If density is less than 15%, they are scattered
            if density < 0.15 and len(contours) > 1:
                self.is_sorted = False
                sorting_status_msg = f"{color} blocks are scattered!"

        # Check for mixed piles
        colors_present = list(group_boxes.keys())
        for i in range(len(colors_present)):
            for j in range(i + 1, len(colors_present)):
                col1 = colors_present[i]
                col2 = colors_present[j]
                
                if self.boxes_overlap(group_boxes[col1], group_boxes[col2]):
                    self.is_sorted = False
                    sorting_status_msg = f"{col1} & {col2} piles mixed!"

        # If there are no blocks at all on the table
        if sum(self.block_counts.values()) == 0:
            self.is_sorted = False
            sorting_status_msg = "No blocks detected."

        self.latest_status = sorting_status_msg
        
        # =======================================================
        # UI DRAWING
        # =======================================================
        status_color = (0, 255, 0) if self.is_sorted else (0, 0, 255)
        cv2.putText(img, f"STATUS: {sorting_status_msg}", (30, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        
        y_offset = 80
        for color, count in self.block_counts.items():
            cv2.putText(img, f"{color}: {count}", (30, y_offset), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.color_bgr[color], 2)
            y_offset += 30

        return img