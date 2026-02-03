import cv2
import mediapipe as mp
import numpy as np

class HeadTracker:
    def __init__(self, robot_interface):
        self.robot = robot_interface
        
        # Load MediaPipe Face Detector (Fast & Accurate)
        self.mp_face_detection = mp.solutions.face_detection
        self.detector = self.mp_face_detection.FaceDetection(
            model_selection=0,       # 0 = Close range (2m), 1 = Far range (5m)
            min_detection_confidence=0.5
        )
        
        # Target coordinates (Smoothed)
        self.target_y = 0.0 
        self.target_z = 0.0 
        self.target_x = 0.5 
        
        # Smoothing factor (Lower = smoother/slower, Higher = twitchy)
        self.alpha = 0.15 

    def track_face(self, frame):
        if frame is None: return

        # MediaPipe needs RGB, OpenCV gives BGR
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.detector.process(rgb_frame)
        
        height, width = frame.shape[:2]

        if not results.detections:
            return # No face found

        # Find the largest face (closest person)
        largest_face = None
        max_area = 0

        for detection in results.detections:
            bboxC = detection.location_data.relative_bounding_box
            area = bboxC.width * bboxC.height
            if area > max_area:
                max_area = area
                largest_face = bboxC

        if largest_face:
            # Calculate Center of Face
            # MediaPipe gives relative coords (0.0 to 1.0), so we don't need to divide by width/height!
            face_cx = largest_face.xmin + (largest_face.width / 2)
            face_cy = largest_face.ymin + (largest_face.height / 2)

            # Draw Box
            start_point = (int(largest_face.xmin * width), int(largest_face.ymin * height))
            end_point = (int((largest_face.xmin + largest_face.width) * width), int((largest_face.ymin + largest_face.height) * height))
            cv2.rectangle(frame, start_point, end_point, (0, 255, 0), 2)
            
            # --- COORDINATE MAPPING ---
            # Center of image is 0.5, 0.5
            # X axis (Image) -> Y axis (Reachy) (Inverted)
            # Y axis (Image) -> Z axis (Reachy) (Inverted)

            # Calculate offsets (-0.5 to 0.5)
            offset_x = 0.5 - face_cx
            offset_y = 0.5 - face_cy 

            # Scale to Look Range (Sensitivity)
            target_y_raw = offset_x * 1.5  # Left/Right range
            target_z_raw = offset_y * 1.0  # Up/Down range

            # Apply Smoothing
            self.target_y = (self.alpha * target_y_raw) + ((1 - self.alpha) * self.target_y)
            self.target_z = (self.alpha * target_z_raw) + ((1 - self.alpha) * self.target_z)

            # Send Command
            self.robot.look_at_smooth(x=self.target_x, y=self.target_y, z=self.target_z)