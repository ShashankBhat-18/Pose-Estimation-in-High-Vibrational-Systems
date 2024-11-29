import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from collections import deque
import math
import os
import time
import torch
import requests
import matplotlib.pyplot as plt
import urllib.request
from datetime import datetime
class MiDaSDepthEstimator:
    def __init__(self, model_type='small', model_path='midas_model'):
        """
        Initialize MiDaS depth estimation model
        
        Args:
            model_type (str): Type of MiDaS model ('small' or 'large')
            model_path (str): Directory to save the model
        """
        # Ensure model directory exists
        os.makedirs(model_path, exist_ok=True)
        
        # Model URLs and paths
        model_urls = {
            'small': "https://github.com/isl-org/MiDaS/releases/download/v2_1/midas_v21_small-70d6b9c8.pt",
            'large': "https://github.com/isl-org/MiDaS/releases/download/v3/dpt_large-midas-2f21e586.pt"
        }
        
        # Full path to the model file
        model_filename = os.path.basename(model_urls[model_type])
        self.model_path = os.path.join(model_path, model_filename)
        
        # Download model if not exists
        if not os.path.exists(self.model_path):
            print(f"Downloading MiDaS {model_type} model...")
            urllib.request.urlretrieve(model_urls[model_type], self.model_path)
            print("Download complete.")
        
        # Set device
        self.device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        
        # Load MiDaS model
        self.model = torch.hub.load("intel-isl/MiDaS", f"MiDaS_{model_type}")
        self.model.to(self.device)
        self.model.eval()
        
        # Load transforms
        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
        self.transform = midas_transforms.small_transform if model_type == 'small' else midas_transforms.dpt_transform
    
    def estimate_depth(self, frame):
        """
        Estimate depth for a given frame
        
        Args:
            frame (numpy.ndarray): Input image frame
        
        Returns:
            numpy.ndarray: Depth map visualization
        """
        # Prepare input for MiDaS
        input_batch = self.transform(frame).to(self.device)
        
        # Estimate depth
        with torch.no_grad():
            prediction = self.model(input_batch)
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=frame.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        
        # Convert to numpy and normalize
        depth_map = prediction.cpu().numpy()
        depth_map = cv2.normalize(depth_map, None, 0, 1, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_32F)
        
        # Create colormap
        depth_colormap = cv2.applyColorMap((depth_map * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
        
        return depth_colormap
    
    def visualize_depth_overlay(self, frame, depth_map, alpha=0.6):
        """
        Create an overlay of the original frame and depth map
        
        Args:
            frame (numpy.ndarray): Original frame
            depth_map (numpy.ndarray): Depth map visualization
            alpha (float): Transparency of the depth map overlay
        
        Returns:
            numpy.ndarray: Frame with depth map overlay
        """
        # Resize depth map to match original frame
        depth_resized = cv2.resize(depth_map, (frame.shape[1], frame.shape[0]))
        
        # Create overlay
        overlay = cv2.addWeighted(frame, 1 - alpha, depth_resized, alpha, 0)
        return overlay
class AdvancedPyramidDetector:
    def __init__(self, effects_config=None):
        # Default configuration
        self.config = {
            'motion_trail': True,
            'glow_effect': True,
            'particle_system': True,
            'wireframe': True,
            'measurements': True
        }
        
        # Update with user config if provided
        if effects_config:
            self.config.update(effects_config)
            
        # Detection parameters
        self.prev_contour = None
        
        # Visual effects
        self.motion_trail = deque(maxlen=30)
        self.hue_offset = 0
        self.glow_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15,15))
        self.particle_system = ParticleSystem(max_particles=100)
        self.confidence_scores = []
        self.detection_times = []
        self.fps_history = deque(maxlen=100)  # Keep last 100 FPS values
        self.contour_areas = []
    def analyze_frame(self, frame, pyramid_contour, processing_time):
        if pyramid_contour is not None:
            # Calculate confidence score based on contour properties
            area = cv2.contourArea(pyramid_contour)
            perimeter = cv2.arcLength(pyramid_contour, True)
            circularity = 4 * np.pi * area / (perimeter ** 2)
            confidence = circularity * 0.7 + (area / (frame.shape[0] * frame.shape[1])) * 0.3
            
            self.confidence_scores.append(confidence)
            self.contour_areas.append(area)
        else:
            self.confidence_scores.append(0)
            self.contour_areas.append(0)
            
        self.detection_times.append(processing_time)
        fps = 1.0 / processing_time if processing_time > 0 else 0
        self.fps_history.append(fps)
    def plot_metrics(self):
        plt.style.use('ggplot')  # Changed from 'seaborn' to 'default'
        fig = plt.figure(figsize=(15, 10))
        
        # Plot 1: Detection Confidence Over Time
        plt.subplot(2, 2, 1)
        plt.plot(self.confidence_scores, 'g-', label='Confidence Score')
        plt.title('Pyramid Detection Confidence Over Time')
        plt.xlabel('Frame Number')
        plt.ylabel('Confidence Score')
        plt.grid(True)
        plt.legend()
        
        # Plot 2: Processing Time Distribution
        plt.subplot(2, 2, 2)
        plt.hist(self.detection_times, bins=30, color='blue', alpha=0.7)
        plt.title('Processing Time Distribution')
        plt.xlabel('Processing Time (seconds)')
        plt.ylabel('Frequency')
        plt.grid(True)
        
        # Plot 3: FPS Over Time
        plt.subplot(2, 2, 3)
        plt.plot(list(self.fps_history), 'r-', label='FPS')
        plt.title('Frames Per Second Over Time')
        plt.xlabel('Frame Number')
        plt.ylabel('FPS')
        plt.grid(True)
        plt.legend()
        
        # Plot 4: Contour Area Variation
        plt.subplot(2, 2, 4)
        plt.plot(self.contour_areas, 'b-', label='Contour Area')
        plt.title('Pyramid Size Variation')
        plt.xlabel('Frame Number')
        plt.ylabel('Contour Area (pixels²)')
        plt.grid(True)
        plt.legend()
        
        plt.tight_layout()
        plt.show()
        
        # Print summary statistics
        print("\nPerformance Summary:")
        print(f"Average FPS: {np.mean(list(self.fps_history)):.2f}")
        print(f"Average Processing Time: {np.mean(self.detection_times)*1000:.2f} ms")
        print(f"Average Confidence Score: {np.mean(self.confidence_scores):.3f}")

    def detect_pyramid(self, frame):
        # Edge detection (keeping the working detection logic)
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        # Dilation
        kernel = np.ones((3,3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
        
        best_contour = None
        max_score = 0
        
        for contour in contours:
            # Approximate the contour
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            if len(approx) in [3, 4]:
                # Calculate shape score
                area = cv2.contourArea(approx)
                perimeter = cv2.arcLength(approx, True)
                shape_score = 4 * np.pi * area / (perimeter ** 2)
                
                # Calculate color score
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                cv2.drawContours(mask, [approx], 0, 255, -1)
                mean_color = cv2.mean(frame, mask=mask)[0]
                color_score = mean_color / 255.0
                
                # Calculate continuity score
                continuity_score = 1.0
                if self.prev_contour is not None:
                    continuity_score = cv2.matchShapes(approx, self.prev_contour, cv2.CONTOURS_MATCH_I2, 0)
                    continuity_score = 1 / (1 + continuity_score)
                
                score = shape_score * 0.4 + color_score * 0.4 + continuity_score * 0.2
                
                if score > max_score:
                    max_score = score
                    best_contour = approx
        
        self.prev_contour = best_contour
        return best_contour, edges

    def create_glow_effect(self, frame, contour, color):
        if contour is None:
            return frame
        
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], 0, 255, -1)
        
        glow = cv2.dilate(mask, self.glow_kernel)
        glow = cv2.GaussianBlur(glow, (21, 21), 0)
        
        glow_color = np.zeros(frame.shape, dtype=np.uint8)
        glow_color[:] = color
        
        mask_3d = cv2.cvtColor(glow, cv2.COLOR_GRAY2BGR) / 255.0
        frame = frame * (1 - mask_3d * 0.5) + glow_color * (mask_3d * 0.5)
        
        return frame.astype(np.uint8)

    def create_energy_field(self, frame, contour):
        if contour is None:
            return frame
        
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Create energy field particles
            self.particle_system.emit_particles(cx, cy)
        
        # Update and draw particles
        frame = self.particle_system.update_and_draw(frame)
        return frame

    def draw_3d_wireframe(self, frame, contour, rvec, tvec):
        if contour is None:
            return frame
        
        # Draw base
        cv2.drawContours(frame, [contour], 0, (0, 255, 0), 2)
        
        # Get centroid
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Calculate pyramid height based on contour area
            height = cv2.contourArea(contour) ** 0.25 * 2
            
            # Get base points
            points = contour.reshape(-1, 2)
            
            # Calculate apex point
            if rvec is not None:
                rotation = Rotation.from_rotvec(rvec)
                height_vector = rotation.apply([0, 0, height])
                apex = (int(cx + height_vector[0]), int(cy + height_vector[1]))
            else:
                apex = (cx, cy - int(height))
            
            # Define colors for pyramid faces (RGBY with 80% opacity)
            face_colors = [
                (100, 149, 237, 0.8),  # Cornflower Blue (softer blue)
                (152, 251, 152, 0.8),  # Pale Green (muted green)
                (255, 160, 122, 0.8),  # Light Salmon (soft reddish tone)
                (175, 238, 238, 0.8),  # Pale Turquoise (subtle yellow-green)
            ]
            
            # Draw colored faces
            for i in range(len(points)):
                next_point = points[(i + 1) % len(points)]
                
                # Create a polygon representing the face
                face_points = np.array([
                    points[i],
                    next_point,
                    apex
                ], np.int32)
                
                # Create an overlay for semi-transparent coloring
                overlay = frame.copy()
                cv2.fillPoly(overlay, [face_points], face_colors[i % len(face_colors)][:3])
                
                # Apply semi-transparent overlay
                cv2.addWeighted(overlay, face_colors[i % len(face_colors)][3], frame, 1 - face_colors[i % len(face_colors)][3], 0, frame)
            
            # Draw wireframe edges
            for point in points:
                pt1 = tuple(map(int, point))
                cv2.line(frame, pt1, apex, (0, 0, 255), 2)
        
        return frame

    def draw_augmented_reality(self, frame, contour):
        if contour is None:
            return frame
        
        # Estimate pose
        rvec, tvec = self.estimate_pose(contour, frame.shape)
        
        # Create rainbow color effect
        hue = (self.hue_offset % 180)
        self.hue_offset += 2
        color = [hue, 255, 255]
        color_bgr = cv2.cvtColor(np.uint8([[color]]), cv2.COLOR_HSV2BGR)[0][0]
        
        # Update motion trail
        if self.config['motion_trail']:
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                self.motion_trail.append((cx, cy))
        
        # Apply visual effects
        if self.config['glow_effect']:
            frame = self.create_glow_effect(frame, contour, color_bgr)
        if self.config['particle_system']:
            frame = self.create_energy_field(frame, contour)
        if self.config['wireframe']:
            frame = self.draw_3d_wireframe(frame, contour, rvec, tvec)
        
        # Draw motion trail
        if self.config['motion_trail'] and len(self.motion_trail) > 1:
            points = np.array(list(self.motion_trail))
            for i in range(len(points) - 1):
                pt1 = tuple(points[i])
                pt2 = tuple(points[i + 1])
                alpha = (i + 1) / len(points)
                trail_color = tuple(map(int, color_bgr * alpha))
                cv2.line(frame, pt1, pt2, trail_color, 2)
        
        # Add measurements overlay
        if self.config['measurements']:
            self.draw_measurements(frame, contour, rvec, tvec)
        
        return frame

    def estimate_pose(self, contour, frame_shape):
        if contour is None or len(contour) < 3:
            return None, None
        
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
        else:
            cx, cy = frame_shape[1] // 2, frame_shape[0] // 2
        
        rect = cv2.minAreaRect(contour)
        angle = rect[2]
        
        position = np.array([(cx - frame_shape[1]/2) / frame_shape[1],
                           (cy - frame_shape[0]/2) / frame_shape[0],
                           0])
        
        rvec = np.array([0, 0, np.radians(angle)])
        tvec = position
        
        return rvec, tvec
    def analyze_frame(self, frame, pyramid_contour, processing_time):
        if pyramid_contour is not None:
            # Calculate confidence score based on contour properties
            area = cv2.contourArea(pyramid_contour)
            perimeter = cv2.arcLength(pyramid_contour, True)
            circularity = 4 * np.pi * area / (perimeter ** 2)
            confidence = circularity * 0.7 + (area / (frame.shape[0] * frame.shape[1])) * 0.3
            
            self.confidence_scores.append(confidence)
            self.contour_areas.append(area)
        else:
            self.confidence_scores.append(0)
            self.contour_areas.append(0)
            
        self.detection_times.append(processing_time)
        fps = 1.0 / processing_time if processing_time > 0 else 0
        self.fps_history.append(fps)
        
    def plot_metrics(self):
        plt.style.use('default')
        fig = plt.figure(figsize=(15, 10))
        
        # Plot 1: Detection Confidence Over Time
        plt.subplot(2, 2, 1)
        plt.plot(self.confidence_scores, 'g-', label='Confidence Score')
        plt.title('Pyramid Detection Confidence Over Time')
        plt.xlabel('Frame Number')
        plt.ylabel('Confidence Score')
        plt.grid(True)
        plt.legend()
        
        # Plot 2: Processing Time Distribution
        plt.subplot(2, 2, 2)
        plt.hist(self.detection_times, bins=30, color='blue', alpha=0.7)
        plt.title('Processing Time Distribution')
        plt.xlabel('Processing Time (seconds)')
        plt.ylabel('Frequency')
        plt.grid(True)
        
        # Plot 3: FPS Over Time
        plt.subplot(2, 2, 3)
        plt.plot(list(self.fps_history), 'r-', label='FPS')
        plt.title('Frames Per Second Over Time')
        plt.xlabel('Frame Number')
        plt.ylabel('FPS')
        plt.grid(True)
        plt.legend()
        
        # Plot 4: Contour Area Variation
        plt.subplot(2, 2, 4)
        plt.plot(self.contour_areas, 'b-', label='Contour Area')
        plt.title('Pyramid Size Variation')
        plt.xlabel('Frame Number')
        plt.ylabel('Contour Area (pixels²)')
        plt.grid(True)
        plt.legend()
        
        # Save the plot to the outputs folder before showing it
        output_dir = os.path.join(os.getcwd(), 'outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
        file_path = os.path.join(output_dir, f"metric_plots_{current_datetime}.png")
        plt.savefig(file_path, dpi=300, bbox_inches='tight')
        
        # Show the plot
        plt.tight_layout()
        plt.show()
        
        # Print summary statistics
        print("\nPerformance Summary:")
        print(f"Average FPS: {np.mean(list(self.fps_history)):.2f}")
        print(f"Average Processing Time: {np.mean(self.detection_times)*1000:.2f} ms")
        print(f"Average Confidence Score: {np.mean(self.confidence_scores):.3f}")
    def draw_measurements(self, frame, contour, rvec, tvec):
        if contour is None:
            return frame
        
        # Create measurement overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, frame.shape[0]-120), (300, frame.shape[0]-10), (0,0,0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        
        # Calculate measurements
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        
        if rvec is not None:
            rotation = Rotation.from_rotvec(rvec)
            euler = rotation.as_euler('xyz', degrees=True)
            
            cv2.putText(frame, f"Rotation: {euler[2]:.1f}°", (20, frame.shape[0]-90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        
        cv2.putText(frame, f"Area: {area:.1f}", (20, frame.shape[0]-60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        cv2.putText(frame, f"Perimeter: {perimeter:.1f}", (20, frame.shape[0]-30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = np.random.randn() * 2
        self.vy = np.random.randn() * 2
        self.life = 1.0
        self.color = np.random.randint(0, 180)  # Random hue
        
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 0.02
        return self.life > 0

class ParticleSystem:
    def __init__(self, max_particles=100):
        self.particles = []
        self.max_particles = max_particles
    
    def emit_particles(self, x, y):
        if len(self.particles) < self.max_particles:
            self.particles.append(Particle(x, y))
    
    def update_and_draw(self, frame):
        new_particles = []
        for particle in self.particles:
            if particle.update():
                # Convert HSV color to BGR
                color = cv2.cvtColor(np.uint8([[[particle.color, 255, 255]]]), 
                                   cv2.COLOR_HSV2BGR)[0][0]
                
                # Scale color by particle life
                color = color * particle.life
                
                # Draw particle
                cv2.circle(frame, (int(particle.x), int(particle.y)), 
                          2, tuple(map(int, color)), -1)
                new_particles.append(particle)
        
        self.particles = new_particles
        return frame

def main():
    input_video = 'input_video.mp4'
    output_video = 'outputs/output_advanced_pyramid_opencv.mp4'
    
    # FPS calculation variables
    fps_start_time = 0
    fps = 0
    
    effects_config = {
        'motion_trail': False,    
        'glow_effect': False,      
        'particle_system': False,  
        'wireframe': True,        
        'measurements': True,
        'depth_estimation': True  # New config for depth estimation
    }
    
    slowdown_factor = 0.5
    
    cap = cv2.VideoCapture(input_video)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    orig_fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    output_fps = int(orig_fps * slowdown_factor)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video, fourcc, output_fps, (frame_width, frame_height))
    
    detector = AdvancedPyramidDetector(effects_config)
    
    # Initialize MiDaS depth estimator (only if depth estimation is enabled)
    depth_estimator = None
    if effects_config.get('depth_estimation', False):
        depth_estimator = MiDaSDepthEstimator(model_type='small')
    
    while True:
        start_time = time.time()  # Start timing
        ret, frame = cap.read()
        if not ret:
            break
            
        # Calculate FPS
        fps_end_time = time.time()
        time_diff = fps_end_time - fps_start_time
        if time_diff > 0:
            fps = 1/time_diff
        fps_start_time = fps_end_time
        
        pyramid_contour, edges = detector.detect_pyramid(frame)
        processing_time = time.time() - start_time  # Calculate processing time
        detector.analyze_frame(frame, pyramid_contour, processing_time)
        
        if pyramid_contour is not None:
            frame = detector.draw_augmented_reality(frame, pyramid_contour)
            
            # Add depth estimation overlay if enabled
            if depth_estimator and effects_config.get('depth_estimation', False):
                depth_map = depth_estimator.estimate_depth(frame)
                frame = depth_estimator.visualize_depth_overlay(frame, depth_map, alpha=0.4)
        else:
            alpha = (1 + math.sin(time.time() * 4)) / 2 * 0.5 + 0.5
            overlay = frame.copy()
            cv2.putText(overlay, "Searching for pyramid...", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        # Draw FPS counter
        cv2.putText(frame, f"FPS: {fps:.1f}", (frame_width - 120, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Show frame
        cv2.imshow('Pyramid Detection', frame)
        
        # Save frame
        out.write(frame)
        
        # Break loop with 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    detector.plot_metrics()
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print(f"Processing complete. Output saved as {output_video}")

if __name__ == "__main__":
    main()