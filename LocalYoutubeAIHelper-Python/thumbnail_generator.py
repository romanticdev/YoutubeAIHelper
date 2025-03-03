import os
import logging
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import random
import json
from ai_client import AIClient
from utilities import create_dir_if_not_exists
import tempfile

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ThumbnailGenerator:
    """
    Generates optimized thumbnails for YouTube videos by extracting key frames
    and adding text overlays based on video content.
    """
    
    def __init__(self, config_folder, video_folder=None):
        """
        Initialize the ThumbnailGenerator with configuration
        
        Args:
            config_folder (str): Path to the configuration folder
            video_folder (str): Path to the video folder
        """
        self.config_folder = config_folder
        self.video_folder = video_folder
        self.config = self._load_config()
        
        # Get config from config.py's load_config_from_folder function
        from config import load_config_from_folder
        config, whisper_config = load_config_from_folder(config_folder)
        self.ai_client = AIClient(config, whisper_config)
        
    def _load_config(self):
        """Load thumbnail configuration from config folder"""
        config_path = os.path.join(self.config_folder, "thumbnail_config.txt")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.loads(f.read())
        else:
            # Default configuration
            config = {
                "num_candidate_frames": 10,
                "frame_selection_method": "contrast",  # contrast, brightness, faces
                "font": "Arial",
                "font_size": 40,
                "font_color": "#FFFFFF",
                "overlay_opacity": 0.7,
                "text_position": "bottom",
                "max_candidates": 3
            }
        return config
    
    def _extract_video_frames(self, video_path, num_frames=10):
        """
        Extract frames from video at different intervals
        
        Args:
            video_path (str): Path to video file
            num_frames (int): Number of frames to extract
            
        Returns:
            list: List of extracted frame images
        """
        try:
            # Try using OpenCV to extract frames
            return self._extract_frames_opencv(video_path, num_frames)
        except Exception as e:
            logging.warning(f"OpenCV frame extraction failed: {e}")
            try:
                # Fallback to ffmpeg if OpenCV fails
                return self._extract_frames_ffmpeg(video_path, num_frames)
            except Exception as e:
                logging.error(f"All frame extraction methods failed: {e}")
                return []
                
    def _extract_frames_opencv(self, video_path, num_frames=10):
        """Extract frames using OpenCV"""
        video = cv2.VideoCapture(video_path)
        if not video.isOpened():
            logging.error(f"Error opening video file: {video_path}")
            raise ValueError("Could not open video file with OpenCV")
            
        # Get video properties
        frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = video.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps
        
        # Calculate frame positions to extract (skip first and last 10%)
        safe_start = int(frame_count * 0.1)
        safe_end = int(frame_count * 0.9)
        safe_range = safe_end - safe_start
        
        interval = max(1, safe_range // num_frames)
        frame_positions = [safe_start + (i * interval) for i in range(num_frames)]
        
        # Extract frames
        frames = []
        for pos in frame_positions:
            video.set(cv2.CAP_PROP_POS_FRAMES, pos)
            success, frame = video.read()
            if success:
                # Convert BGR to RGB for PIL
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(Image.fromarray(frame_rgb))
            
        video.release()
        
        if not frames:
            raise ValueError("No frames extracted with OpenCV")
            
        return frames
        
    def _extract_frames_ffmpeg(self, video_path, num_frames=10):
        """Extract frames using ffmpeg as a fallback method"""
        import subprocess
        import os
        
        frames = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Get video duration using ffprobe
            duration_cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                video_path
            ]
            
            # Redirect stderr to suppress error messages
            process = subprocess.run(
                duration_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                raise ValueError(f"ffprobe failed: {process.stderr}")
                
            duration = float(process.stdout.strip())
            
            # Calculate time positions for frames
            safe_start = duration * 0.1
            safe_end = duration * 0.9
            safe_range = safe_end - safe_start
            
            interval = safe_range / num_frames
            time_positions = [safe_start + (i * interval) for i in range(num_frames)]
            
            # Extract frames at specified positions
            for i, pos in enumerate(time_positions):
                output_file = os.path.join(temp_dir, f"frame_{i:03d}.jpg")
                
                cmd = [
                    'ffmpeg',
                    '-ss', str(pos),
                    '-i', video_path,
                    '-vframes', '1',
                    '-q:v', '2',
                    '-f', 'image2',
                    output_file
                ]
                
                process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if process.returncode != 0:
                    logging.warning(f"ffmpeg frame extraction failed: {process.stderr}")
                
                if os.path.exists(output_file):
                    img = Image.open(output_file)
                    frames.append(img.copy())
                    img.close()
            
            return frames
                    
        except Exception as e:
            logging.error(f"Error extracting frames with ffmpeg: {e}")
            raise
        finally:
            # Clean up temporary files
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _score_frame(self, frame):
        """
        Score a frame based on visual quality metrics
        
        Args:
            frame (PIL.Image): Frame to evaluate
            
        Returns:
            float: Quality score
        """
        try:
            # Convert PIL image to numpy array for OpenCV
            frame_np = np.array(frame)
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(frame_np, cv2.COLOR_RGB2GRAY)
            
            # Calculate contrast (standard deviation of pixel values)
            contrast = np.std(gray)
            
            # Calculate brightness (mean of pixel values)
            brightness = np.mean(gray)
            
            # Calculate sharpness using Laplacian
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = np.var(laplacian)
            
            # Combined score (normalized)
            # Prefer high contrast, moderate brightness, high sharpness
            brightness_factor = 1.0 - abs(brightness - 127.5) / 127.5  # Closer to 127.5 is better
            
            score = (contrast / 255.0) * 0.4 + brightness_factor * 0.3 + (sharpness / 1000.0) * 0.3
            
            return score
        except Exception as e:
            logging.warning(f"Error scoring frame: {e}")
            return 0.5  # Return middle score on error
    
    def _select_best_frames(self, frames, method="contrast"):
        """
        Select the best frames from candidates
        
        Args:
            frames (list): List of frame images
            method (str): Frame selection method
            
        Returns:
            list: Sorted list of (frame, score) tuples
        """
        if not frames:
            return []
            
        scored_frames = []
        
        for frame in frames:
            score = self._score_frame(frame)
            scored_frames.append((frame, score))
            
        # Sort by score (highest first)
        scored_frames.sort(key=lambda x: x[1], reverse=True)
        
        return scored_frames
    
    def _add_text_overlay(self, image, text, position="bottom"):
        """
        Add text overlay to an image
        
        Args:
            image (PIL.Image): Image to modify
            text (str): Text to overlay
            position (str): Text position (top, bottom, center)
            
        Returns:
            PIL.Image: Modified image
        """
        try:
            draw = ImageDraw.Draw(image)
            width, height = image.size
            
            # Use default font if custom font not available
            try:
                font = ImageFont.truetype(self.config["font"], self.config["font_size"])
                logging.info(f"Using a font {self.config['font']} with size {self.config['font_size']}")
            except IOError:
                font = ImageFont.load_default(size=self.config["font_size"])
                logging.info(f"Using aa default font because {self.config['font']} is not available")
                
            if not text or len(text) == 0:
                text = "Click to Watch"
                
            # Wrap text if too long
            max_width = width - 40
            words = text.split()
            if not words:
                words = ["Click", "to", "Watch"]
                
            lines = []
            current_line = words[0]
            
            for word in words[1:]:
                test_line = current_line + " " + word
                text_bbox = draw.textbbox((0, 0), test_line, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                
                if text_width <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
                    
            lines.append(current_line)
            
            # Calculate text position
            line_height = draw.textbbox((0, 0), lines[0], font=font)[3]
            total_text_height = line_height * len(lines)
            
            # Calculate horizontal alignment for multi-position options
            text_width = max([draw.textbbox((0, 0), line, font=font)[2] for line in lines])
            
            # Default positions
            x_position = 20  # Default left margin
            y_position = height - total_text_height - 20  # Default to bottom
            
            # Vertical positioning
            if position in ["top", "top-left", "top-center", "top-right"]:
                y_position = 20
            elif position in ["center", "center-left", "center-center", "center-right", "middle", "middle-left", "middle-center", "middle-right"]:
                y_position = (height - total_text_height) // 2
            elif position in ["bottom", "bottom-left", "bottom-center", "bottom-right"]:
                y_position = height - total_text_height - 20
                
            # Initialize background rectangles for all lines
            bg_rects = []
            
            # Calculate position for each line
            for i, line in enumerate(lines):
                # Calculate line width for horizontal centering of individual lines
                line_bbox = draw.textbbox((0, 0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]
                
                # Determine x position for this specific line
                if position in ["top-center", "center-center", "middle-center", "bottom-center"]:
                    line_x = (width - line_width) // 2
                elif position in ["top-right", "center-right", "middle-right", "bottom-right"]:
                    line_x = width - line_width - 20
                else:
                    line_x = x_position
                
                # Calculate text bounding box
                text_bbox = draw.textbbox((line_x, y_position + i * line_height), line, font=font)
                padding = 10
                bg_bbox = (
                    text_bbox[0] - padding, 
                    text_bbox[1] - padding,
                    text_bbox[2] + padding, 
                    text_bbox[3] + padding
                )
                
                bg_rects.append((line, line_x, y_position + i * line_height, bg_bbox))
            
            # Draw all background boxes first
            try:
                overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                
                for _, _, _, bg_bbox in bg_rects:
                    overlay_draw.rectangle(bg_bbox, fill=(0, 0, 0, int(self.config["overlay_opacity"] * 255)))
                
                image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
            except Exception as e:
                logging.warning(f"Error creating overlay: {e}")
                # Fallback to simpler background
                draw = ImageDraw.Draw(image)
                for _, _, _, bg_bbox in bg_rects:
                    draw.rectangle(bg_bbox, fill=(0, 0, 0))
            
            # Draw text on the new image
            draw = ImageDraw.Draw(image)
            for line, line_x, line_y, _ in bg_rects:
                draw.text(
                    (line_x, line_y),
                    line,
                    fill=self.config["font_color"],
                    font=font
                )
                
            return image
        except Exception as e:
            logging.error(f"Error adding text overlay: {e}")
            return image  # Return original image if overlay fails
    
    def generate_thumbnail(self):
        """
        Generate thumbnail from video frames with text overlay
        
        Returns:
            str: Path to the generated thumbnail
        """
        if not self.video_folder:
            logging.error("No video folder specified")
            return None
            
        # Find video file
        video_files = [f for f in os.listdir(self.video_folder) 
                      if f.endswith(('.mp4', '.mkv', '.webm', '.avi', '.m4a'))]
        
        if not video_files:
            # If no video file found, try using a default thumbnail or placeholder image
            logging.warning(f"No video files found in {self.video_folder}, using placeholder image")
            return self._generate_text_based_thumbnails()
            
        video_path = os.path.join(self.video_folder, video_files[0])
        
        # Extract frames
        frames = self._extract_video_frames(video_path, self.config["num_candidate_frames"])
        if not frames:
            logging.error("Failed to extract frames from video")
            # Fallback to generating text-based thumbnails
            return self._generate_text_based_thumbnails()
            
        # Select best frames
        best_frames = self._select_best_frames(frames, self.config["frame_selection_method"])
        
        # Generate thumbnail text overlay using dedicated prompt
        thumbnail_text = self._get_thumbnail_text()
        
        # Create thumbnails with text overlay
        thumbnails_folder = os.path.join(self.video_folder, "thumbnails")
        create_dir_if_not_exists(thumbnails_folder)
        
        thumbnail_paths = []
        
        # If we have frames, create thumbnails from them
        if best_frames:
            for i, (frame, score) in enumerate(best_frames[:self.config["max_candidates"]]):
                try:
                    # Convert to RGB if needed
                    if frame.mode != 'RGB':
                        frame = frame.convert('RGB')
                        
                    # Add text overlay
                    thumbnail = self._add_text_overlay(frame, thumbnail_text, self.config["text_position"])
                    
                    # Save thumbnail
                    thumbnail_path = os.path.join(thumbnails_folder, f"thumbnail_{i+1}.jpg")
                    thumbnail.save(thumbnail_path, "JPEG", quality=95)
                    thumbnail_paths.append(thumbnail_path)
                except Exception as e:
                    logging.error(f"Error creating thumbnail {i+1}: {e}")
        
        # If no thumbnails were created, create a text-based thumbnail
        if not thumbnail_paths:
            text_thumbnail_paths = self._generate_text_based_thumbnails()
            if text_thumbnail_paths:
                thumbnail_paths.extend(text_thumbnail_paths)
            
        return thumbnail_paths
        
    def _get_thumbnail_text(self):
        """Get or generate text for thumbnail overlay"""
        thumbnail_text_path = os.path.join(self.video_folder, "thumbnail_text.txt")
        thumbnail_prompt_path = os.path.join(self.video_folder, "thumbnail.prompt.txt")
        
        # If we already generated thumbnail text, use it
        if os.path.exists(thumbnail_text_path):
            with open(thumbnail_text_path, "r", encoding="utf-8") as f:
                thumbnail_text = f.read().strip()
                logging.info(f"Using existing thumbnail text: {thumbnail_text}")
                return thumbnail_text
                
        # If we already generated thumbnail prompt result, use it
        if os.path.exists(thumbnail_prompt_path):
            with open(thumbnail_prompt_path, "r", encoding="utf-8") as f:
                thumbnail_text = f.read().strip()
                logging.info(f"Using thumbnail.prompt.txt: {thumbnail_text}")
                
                # Save it as thumbnail_text.txt for future use
                with open(thumbnail_text_path, "w", encoding="utf-8") as f2:
                    f2.write(thumbnail_text)
                
                return thumbnail_text
                
        # Otherwise generate new thumbnail text
        summary_path = os.path.join(self.video_folder, "summary.txt")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = f.read().strip()
            
            # Load thumbnail prompt template
            prompt_path = os.path.join(self.config_folder, "prompts", "thumbnail.txt")
            if os.path.exists(prompt_path):
                with open(prompt_path, "r", encoding="utf-8") as f:
                    prompt_template = f.read()
            else:
                prompt_template = "Create a short, engaging thumbnail title (max 8 words) based on this content summary:\n\n{summary}"
            
            # Generate thumbnail text
            try:
                prompt = prompt_template.format(summary=summary)
                thumbnail_text = self.ai_client.create_completion(prompt).strip()
                logging.info(f"Generated thumbnail text: {thumbnail_text}")
                
                # Save thumbnail text for future use
                with open(thumbnail_text_path, "w", encoding="utf-8") as f:
                    f.write(thumbnail_text)
                    
                return thumbnail_text
            except Exception as e:
                logging.error(f"Failed to generate thumbnail text: {e}")
        
        # Fallback to title text if available
        title_path = os.path.join(self.video_folder, "title.txt")
        if os.path.exists(title_path):
            with open(title_path, "r", encoding="utf-8") as f:
                thumbnail_text = f.read().strip()
                return thumbnail_text
                
        return "Click to Watch"
    
    def _generate_text_based_thumbnails(self):
        """Generate basic thumbnails with just text on a colored background"""
        thumbnail_text = self._get_thumbnail_text()
        thumbnails_folder = os.path.join(self.video_folder, "thumbnails")
        create_dir_if_not_exists(thumbnails_folder)
        
        # Standard YouTube thumbnail size (1920x1080 for high res)
        width, height = 1920, 1080
        thumbnail_paths = []
        
        # Generate thumbnails with different colored backgrounds
        background_colors = [
            (33, 33, 33),      # Dark gray
            (194, 24, 7),      # Red
            (3, 98, 193),      # Blue
            (0, 148, 50),      # Green
            (107, 32, 165)     # Purple
        ]
        
        for i, color in enumerate(background_colors[:self.config["max_candidates"]]):
            try:
                # Create blank image with colored background
                img = Image.new('RGB', (width, height), color=color)
                
                # Add text overlay
                thumbnail = self._add_text_overlay(img, thumbnail_text, "center")
                
                # Save thumbnail
                thumbnail_path = os.path.join(thumbnails_folder, f"thumbnail_{i+1}.jpg")
                thumbnail.save(thumbnail_path, "JPEG", quality=95)
                thumbnail_paths.append(thumbnail_path)
            except Exception as e:
                logging.error(f"Error creating text thumbnail {i+1}: {e}")
                
        return thumbnail_paths