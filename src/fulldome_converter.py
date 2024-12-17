import sys
import cv2
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                           QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QProgressBar,
                           QComboBox, QMessageBox, QFrame, QDialog, QScrollArea, QGroupBox,
                           QSlider, QSpinBox, QDoubleSpinBox, QTextBrowser)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor, QImage, QPixmap
from PIL import Image

class ConversionThread(QThread):
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, input_path, output_path, is_video, input_format, dome_type, rotation, zoom_factor, tilt, pan, roll, flip_h, flip_v):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.is_video = is_video
        self.input_format = input_format
        self.dome_type = dome_type
        self.rotation = rotation
        self.zoom_factor = zoom_factor
        self.tilt = tilt
        self.pan = pan
        self.roll = roll
        self.flip_h = flip_h
        self.flip_v = flip_v
        
    def convert_frame(self, frame):
        try:
            height, width = frame.shape[:2]
            
            # Create a square output image
            dome_size = min(height, width)
            result = np.zeros((dome_size, dome_size, 3), dtype=np.uint8)
            
            # Create coordinate maps
            y, x = np.meshgrid(np.arange(dome_size), np.arange(dome_size), indexing='ij')
            center = dome_size // 2
            
            # Calculate normalized coordinates
            dx = (x - center) / center
            dy = (y - center) / center
            r = np.sqrt(dx**2 + dy**2)
            theta = np.arctan2(dy, dx)
            
            # Create circular mask
            mask = r <= 1.0
            
            # Apply rotation
            rotation_rad = -np.radians(self.rotation)
            theta_rot = theta + rotation_rad
            
            # Apply zoom factor to radius calculation
            r_scaled = r[mask] * self.zoom_factor
            
            # Convert to spherical coordinates
            phi = r_scaled * 0.5 * np.pi  # Azimuthal angle (0 to pi/2)
            theta_sph = theta_rot[mask]   # Polar angle (-pi to pi)
            
            # Convert to 3D cartesian coordinates
            x_cart = np.sin(phi) * np.cos(theta_sph)
            y_cart = np.sin(phi) * np.sin(theta_sph)
            z_cart = np.cos(phi)
            
            # Convert angles to radians
            tilt_rad = np.radians(self.tilt)
            pan_rad = np.radians(self.pan)
            roll_rad = np.radians(self.roll)
            
            # Apply rotations in order: tilt (X) -> pan (Y) -> roll (Z)
            
            # Tilt rotation (around X-axis)
            y_tilt = y_cart * np.cos(tilt_rad) - z_cart * np.sin(tilt_rad)
            z_tilt = y_cart * np.sin(tilt_rad) + z_cart * np.cos(tilt_rad)
            x_tilt = x_cart
            
            # Pan rotation (around Y-axis)
            x_pan = x_tilt * np.cos(pan_rad) + z_tilt * np.sin(pan_rad)
            z_pan = -x_tilt * np.sin(pan_rad) + z_tilt * np.cos(pan_rad)
            y_pan = y_tilt
            
            # Roll rotation (around Z-axis)
            x_roll = x_pan * np.cos(roll_rad) - y_pan * np.sin(roll_rad)
            y_roll = x_pan * np.sin(roll_rad) + y_pan * np.cos(roll_rad)
            z_roll = z_pan
            
            # Convert back to spherical coordinates
            phi_rot = np.arccos(z_roll)
            theta_rot = np.arctan2(y_roll, x_roll)
            
            # Convert to image coordinates
            x_src = ((theta_rot + np.pi) / (2 * np.pi)) * width
            y_src = (phi_rot / np.pi) * height
            
            # Handle wraparound and clipping
            x_src = np.mod(x_src, width)
            y_src = np.clip(y_src, 0, height - 1)
            
            # Sample pixels
            result[mask] = frame[y_src.astype(np.int32), x_src.astype(np.int32)]
            
            return result
            
        except Exception as e:
            raise Exception(f"Frame conversion error: {str(e)}")
    
    def run(self):
        try:
            if self.is_video:
                self.convert_video()
            else:
                self.convert_image()
        except Exception as e:
            self.error.emit(str(e))
    
    def convert_image(self):
        try:
            # Read input image
            img = cv2.imread(self.input_path)
            if img is None:
                raise Exception("Failed to load input image")
            
            # Apply flips if needed
            if self.flip_h:
                img = cv2.flip(img, 1)
            if self.flip_v:
                img = cv2.flip(img, 0)
            
            # Convert the image
            result = self.convert_frame(img)
            
            # Save the result
            cv2.imwrite(self.output_path, result)
            
            self.progress.emit(100)
            
        except Exception as e:
            self.error.emit(f"Image conversion error: {str(e)}")
    
    def convert_video(self):
        try:
            # Read input video
            cap = cv2.VideoCapture(self.input_path)
            if not cap.isOpened():
                raise Exception("Failed to open input video")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Create output video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(self.output_path, fourcc, fps, (width, height))
            
            # Convert frames
            for i in range(total_frames):
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Apply flips if needed
                if self.flip_h:
                    frame = cv2.flip(frame, 1)
                if self.flip_v:
                    frame = cv2.flip(frame, 0)
                
                # Convert frame
                result = self.convert_frame(frame)
                
                # Write frame to output video
                out.write(result)
                
                # Emit progress signal
                self.progress.emit(int((i + 1) / total_frames * 100))
            
            # Release resources
            cap.release()
            out.release()
            
        except Exception as e:
            self.error.emit(f"Video conversion error: {str(e)}")

class UIScaleDialog(QDialog):
    def __init__(self, current_scale, parent=None):
        super().__init__(parent)
        self.setWindowTitle("UI Scale Settings")
        self.setModal(True)
        self.current_scale = current_scale
        
        layout = QVBoxLayout(self)
        
        # Scale slider
        scale_layout = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(50, 150)
        self.scale_slider.setValue(int(current_scale * 100))
        self.scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.scale_slider.setTickInterval(10)
        
        self.scale_label = QLabel(f"Scale: {int(current_scale * 100)}%")
        self.scale_slider.valueChanged.connect(self.update_label)
        
        scale_layout.addWidget(QLabel("UI Scale:"))
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_label)
        
        # Preview text
        preview_label = QLabel("Preview Text")
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setFont(QFont('Segoe UI', 10))
        
        # Buttons
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        cancel_btn = QPushButton("Cancel")
        
        apply_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        
        # Add all to main layout
        layout.addLayout(scale_layout)
        layout.addWidget(preview_label)
        layout.addLayout(button_layout)
        
        self.setFixedSize(400, 200)
    
    def update_label(self, value):
        self.scale_label.setText(f"Scale: {value}%")
        
    def get_scale(self):
        return self.scale_slider.value() / 100

class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui_scale = 1.0  # Default scale
        self.initUI()
        self.preview_image = None
        self.original_image = None
        self.video_capture = None
        self.current_frame = None
        self.is_playing = False
        self.total_frames = 0
        self.fps = 0
        self.zoom_factor = 1.0
        self.tilt = 0.0
        self.pan = 0.0
        self.roll = 0.0
        self.flip_h = False
        self.flip_v = False
        self.current_theme = "green"  # Default theme
        
    def get_theme_colors(self, theme_name):
        themes = {
            "green": {
                "accent": "#c2ff4d",
                "dark": "#333333",
                "darker": "#222222",
                "hover": "#444444"
            },
            "purple": {
                "accent": "#b14cff",
                "dark": "#2d1b33",
                "darker": "#1a0f1f",
                "hover": "#3d2645"
            },
            "red": {
                "accent": "#ff4d4d",
                "dark": "#331b1b",
                "darker": "#1f0f0f",
                "hover": "#452626"
            },
            "default": {
                "accent": "#4d9fff",
                "dark": "#1b2633",
                "darker": "#0f151f",
                "hover": "#263545"
            }
        }
        return themes.get(theme_name, themes["green"])

    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        colors = self.get_theme_colors(theme_name)
        
        # Update all styled components
        self.update_component_styles(colors)
        
    def update_component_styles(self, colors):
        # Button style
        button_style = f"""
            QPushButton {{
                background-color: {colors['dark']};
                color: {colors['accent']};
                border: 2px solid {colors['accent']};
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {colors['hover']};
            }}
            QPushButton:disabled {{
                color: #666666;
                border-color: #666666;
            }}
        """
        
        # Label style
        label_style = f"""
            QLabel {{
                background-color: {colors['dark']};
                border: 2px solid {colors['accent']};
                border-radius: 10px;
                color: {colors['accent']};
                font-size: 16px;
            }}
        """
        
        # GroupBox style
        groupbox_style = f"""
            QGroupBox {{
                color: {colors['accent']};
                border: 2px solid {colors['accent']};
                border-radius: 5px;
                margin-top: 1ex;
                padding: 10px;
                font-size: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}
        """
        
        # Slider style
        slider_style = f"""
            QSlider {{
                min-height: 30px;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid #999999;
                height: 12px;
                background: {colors['dark']};
                margin: 2px 0;
                border-radius: 6px;
            }}
            QSlider::handle:horizontal {{
                background: {colors['accent']};
                border: 1px solid {colors['darker']};
                width: 24px;
                height: 24px;
                margin: -6px 0;
                border-radius: 12px;
            }}
        """
        
        # SpinBox style
        spinbox_style = f"""
            QSpinBox, QDoubleSpinBox {{
                background-color: {colors['dark']};
                color: {colors['accent']};
                border: 2px solid {colors['accent']};
                border-radius: 5px;
                padding: 5px;
                font-size: 14px;
                min-width: 80px;
                min-height: 30px;
            }}
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background-color: {colors['hover']};
                min-width: 20px;
                min-height: 15px;
            }}
        """
        
        # Apply styles
        self.import_image_btn.setStyleSheet(button_style)
        self.import_video_btn.setStyleSheet(button_style)
        self.export_btn.setStyleSheet(button_style)
        self.preview_label.setStyleSheet(label_style)
        self.controls_group.setStyleSheet(groupbox_style)
        
        for slider in [self.tilt_slider, self.pan_slider, self.roll_slider, self.zoom_slider]:
            slider.setStyleSheet(slider_style)
            
        for spinbox in [self.tilt_spinbox, self.pan_spinbox, self.roll_spinbox, self.zoom_spinbox]:
            spinbox.setStyleSheet(spinbox_style)
            
        for label in [self.tilt_label, self.pan_label, self.roll_label, self.zoom_label]:
            label.setStyleSheet(f"color: {colors['accent']}; font-size: 14px;")

    def initUI(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)  # Reduced spacing
        main_layout.setContentsMargins(10, 10, 10, 10)  # Reduced margins
        
        # Top section (Import buttons, theme selector, and scale button)
        top_layout = QHBoxLayout()
        
        # Import buttons
        import_layout = QHBoxLayout()
        self.import_image_btn = QPushButton("Import Image")
        self.import_video_btn = QPushButton("Import Video")
        self.scale_settings_btn = QPushButton("UI Scale")
        self.feedback_btn = QPushButton("Feedback")
        
        # Set button properties with scale consideration
        for btn in [self.import_image_btn, self.import_video_btn, self.scale_settings_btn, self.feedback_btn]:
            btn.setMinimumHeight(int(40 * self.ui_scale))
            btn.setFont(QFont('Segoe UI', int(10 * self.ui_scale)))
        
        import_layout.addWidget(self.import_image_btn)
        import_layout.addWidget(self.import_video_btn)
        import_layout.addWidget(self.scale_settings_btn)
        import_layout.addWidget(self.feedback_btn)
        
        # Theme selector
        theme_layout = QHBoxLayout()
        self.theme_label = QLabel("Theme:")  # Store reference
        self.theme_label.setStyleSheet("color: #c2ff4d; font-size: 14px;")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Green (Default)", "Neon Purple", "Christmas Red", "Classic Blue"])
        self.theme_combo.setMinimumHeight(int(40 * self.ui_scale))
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #333333;
                color: #c2ff4d;
                border: 2px solid #c2ff4d;
                border-radius: 5px;
                padding: 5px;
                min-width: 150px;
                font-size: 14px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 2px solid #c2ff4d;
                width: 12px;
                height: 12px;
            }
        """)
        
        theme_layout.addWidget(self.theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.setSpacing(10)  # Space between label and combo
        
        top_layout.addLayout(import_layout)
        top_layout.addStretch()
        top_layout.addLayout(theme_layout)
        
        # Video timeline controls
        self.video_controls = QWidget()
        video_controls_layout = QVBoxLayout(self.video_controls)
        video_controls_layout.setSpacing(10)
        
        # Timeline slider and time label
        timeline_layout = QHBoxLayout()
        self.timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self.timeline_slider.setEnabled(False)
        self.timeline_slider.setMinimumWidth(400)  # Make slider wider
        
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("color: #c2ff4d; font-size: 14px;")
        self.time_label.setMinimumWidth(100)  # Fixed width for time label
        
        timeline_layout.addWidget(self.timeline_slider)
        timeline_layout.addWidget(self.time_label)
        
        # Playback controls
        playback_layout = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setEnabled(False)
        self.play_button.setMinimumWidth(100)
        self.play_button.setMinimumHeight(30)
        
        playback_layout.addStretch()
        playback_layout.addWidget(self.play_button)
        playback_layout.addStretch()
        
        # Add layouts to video controls
        video_controls_layout.addLayout(timeline_layout)
        video_controls_layout.addLayout(playback_layout)
        
        # Initially hide video controls
        self.video_controls.setVisible(False)
        
        # Preview section
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel("Import an image or video to start")
        self.preview_label.setMinimumSize(600, 600)  # Reduced size
        self.preview_label.setMaximumSize(800, 800)  # Maximum size limit
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_label)

        # Flip controls
        flip_layout = QHBoxLayout()
        self.flip_h_btn = QPushButton("Flip Horizontal")
        self.flip_v_btn = QPushButton("Flip Vertical")
        self.flip_h_btn.setEnabled(False)
        self.flip_v_btn.setEnabled(False)
        self.flip_h_btn.setMinimumHeight(30)
        self.flip_v_btn.setMinimumHeight(30)
        self.flip_h_btn.setFont(QFont('Segoe UI', 10))
        self.flip_v_btn.setFont(QFont('Segoe UI', 10))
        
        flip_layout.addWidget(self.flip_h_btn)
        flip_layout.addWidget(self.flip_v_btn)
        
        # Add flip controls after preview
        preview_layout.addLayout(flip_layout)
        
        # Controls section
        self.controls_group = QGroupBox("Media Controls")
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(15)  # Space between controls
        
        # Store references to labels
        self.tilt_label = QLabel("Tilt (X-axis):")
        self.pan_label = QLabel("Pan (Y-axis):")
        self.roll_label = QLabel("Roll (Z-axis):")
        self.zoom_label = QLabel("Field of View:")
        
        # Tilt controls (X-axis)
        tilt_layout = QHBoxLayout()
        self.tilt_slider = QSlider(Qt.Orientation.Horizontal)
        self.tilt_spinbox = QSpinBox()
        self.setup_control_group(tilt_layout, self.tilt_label, self.tilt_slider, self.tilt_spinbox, -180, 180)
        
        # Pan controls (Y-axis)
        pan_layout = QHBoxLayout()
        self.pan_slider = QSlider(Qt.Orientation.Horizontal)
        self.pan_spinbox = QSpinBox()
        self.setup_control_group(pan_layout, self.pan_label, self.pan_slider, self.pan_spinbox, -180, 180)
        
        # Roll controls (Z-axis)
        roll_layout = QHBoxLayout()
        self.roll_slider = QSlider(Qt.Orientation.Horizontal)
        self.roll_spinbox = QSpinBox()
        self.setup_control_group(roll_layout, self.roll_label, self.roll_slider, self.roll_spinbox, -180, 180)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_spinbox = QDoubleSpinBox()
        self.setup_zoom_control_group(zoom_layout)
        
        # Add all controls to the group
        controls_layout.addLayout(tilt_layout)
        controls_layout.addLayout(pan_layout)
        controls_layout.addLayout(roll_layout)
        controls_layout.addLayout(zoom_layout)
        self.controls_group.setLayout(controls_layout)
        
        # Export button
        self.export_btn = QPushButton("Export")
        self.export_btn.setMinimumHeight(50)
        self.export_btn.setFont(QFont('Segoe UI', 12))
        self.export_btn.setEnabled(False)
        
        # Add all sections to main layout with proper spacing
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.video_controls)  # Add video controls right after top layout
        main_layout.addLayout(preview_layout)
        main_layout.addWidget(self.controls_group)
        main_layout.addWidget(self.export_btn)
        
        # Connect theme change signal
        self.theme_combo.currentTextChanged.connect(self.handle_theme_change)
        
        # Connect all control signals
        self.tilt_slider.valueChanged.connect(self.tilt_changed)
        self.tilt_spinbox.valueChanged.connect(self.tilt_value_changed)
        self.pan_slider.valueChanged.connect(self.pan_changed)
        self.pan_spinbox.valueChanged.connect(self.pan_value_changed)
        self.roll_slider.valueChanged.connect(self.roll_changed)
        self.roll_spinbox.valueChanged.connect(self.roll_value_changed)
        self.zoom_slider.valueChanged.connect(self.zoom_changed)
        self.zoom_spinbox.valueChanged.connect(self.zoom_value_changed)
        
        # Connect video control signals
        self.timeline_slider.sliderPressed.connect(self.timeline_pressed)
        self.timeline_slider.sliderReleased.connect(self.timeline_released)
        self.timeline_slider.valueChanged.connect(self.timeline_changed)
        self.play_button.clicked.connect(self.toggle_playback)
        
        # Connect flip buttons
        self.flip_h_btn.clicked.connect(self.toggle_flip_h)
        self.flip_v_btn.clicked.connect(self.toggle_flip_v)
        
        # Connect scale settings button
        self.scale_settings_btn.clicked.connect(self.show_scale_settings)
        
        # Connect feedback button
        self.feedback_btn.clicked.connect(self.open_feedback)
        
        # Apply initial theme
        self.apply_theme("green")

    def setup_control_group(self, layout, label, slider, spinbox, min_val, max_val):
        label.setStyleSheet("color: #c2ff4d; font-size: 14px;")
        label.setMinimumWidth(120)
        
        slider.setRange(min_val, max_val)
        slider.setEnabled(False)
        
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(1)
        spinbox.setEnabled(False)
        
        layout.addWidget(label)
        layout.addWidget(slider)
        layout.addWidget(spinbox)
        layout.setSpacing(10)

    def setup_zoom_control_group(self, layout):
        self.zoom_label.setStyleSheet("color: #c2ff4d; font-size: 14px;")
        self.zoom_label.setMinimumWidth(120)
        
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setEnabled(False)
        
        self.zoom_spinbox.setRange(0.1, 2.0)
        self.zoom_spinbox.setSingleStep(0.1)
        self.zoom_spinbox.setValue(1.0)
        self.zoom_spinbox.setEnabled(False)
        
        layout.addWidget(self.zoom_label)
        layout.addWidget(self.zoom_slider)
        layout.addWidget(self.zoom_spinbox)
        layout.setSpacing(10)
        
    def zoom_changed(self, value):
        zoom = value / 100.0
        self.zoom_spinbox.setValue(zoom)
        self.zoom_factor = zoom
        self.update_preview()
        
    def zoom_value_changed(self, value):
        self.zoom_slider.setValue(int(value * 100))
        self.zoom_factor = value
        self.update_preview()
        
    def tilt_changed(self, value):
        self.tilt_spinbox.setValue(value)
        self.tilt = value
        self.update_preview()
        
    def tilt_value_changed(self, value):
        self.tilt_slider.setValue(value)
        self.tilt = value
        self.update_preview()

    def pan_changed(self, value):
        self.pan_spinbox.setValue(value)
        self.pan = value
        self.update_preview()
        
    def pan_value_changed(self, value):
        self.pan_slider.setValue(value)
        self.pan = value
        self.update_preview()

    def roll_changed(self, value):
        self.roll_spinbox.setValue(value)
        self.roll = value
        self.update_preview()
        
    def roll_value_changed(self, value):
        self.roll_slider.setValue(value)
        self.roll = value
        self.update_preview()
        
    def set_video(self, video_path):
        try:
            if self.video_capture is not None:
                self.video_capture.release()
            
            self.video_capture = cv2.VideoCapture(video_path)
            if not self.video_capture.isOpened():
                raise Exception("Failed to open video")
            
            # Get video properties
            self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            
            # Setup timeline
            self.timeline_slider.setRange(0, self.total_frames - 1)
            self.timeline_slider.setValue(0)
            self.timeline_slider.setEnabled(True)
            self.play_button.setEnabled(True)
            
            # Show video controls
            self.video_controls.setVisible(True)
            
            # Enable flip controls
            self.flip_h_btn.setEnabled(True)
            self.flip_v_btn.setEnabled(True)
            
            # Read first frame
            self.seek_frame(0)
            
            # Enable other controls
            self.enable_controls()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load video: {str(e)}")

    def set_image(self, image_path):
        try:
            # Stop video playback if active
            self.is_playing = False
            if self.video_capture is not None:
                self.video_capture.release()
                self.video_capture = None
            
            # Hide video controls
            self.video_controls.setVisible(False)
            
            self.original_image = cv2.imread(image_path)
            if self.original_image is None:
                raise Exception("Failed to load image")
            
            # Enable flip controls
            self.flip_h_btn.setEnabled(True)
            self.flip_v_btn.setEnabled(True)
            
            # Enable other controls
            self.enable_controls()
            
            self.update_preview()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preview image: {str(e)}")

    def enable_controls(self):
        # Enable all controls
        self.tilt_slider.setEnabled(True)
        self.tilt_spinbox.setEnabled(True)
        self.pan_slider.setEnabled(True)
        self.pan_spinbox.setEnabled(True)
        self.roll_slider.setEnabled(True)
        self.roll_spinbox.setEnabled(True)
        self.zoom_slider.setEnabled(True)
        self.zoom_spinbox.setEnabled(True)
        self.export_btn.setEnabled(True)

    def seek_frame(self, frame_number):
        if self.video_capture is None:
            return
            
        self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.video_capture.read()
        if ret:
            self.current_frame = frame
            self.update_preview()
            
            # Update time label
            current_time = frame_number / self.fps
            total_time = self.total_frames / self.fps
            self.time_label.setText(f"{self.format_time(current_time)} / {self.format_time(total_time)}")

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"

    def timeline_pressed(self):
        self.is_playing = False
        self.play_button.setText("Play")

    def timeline_released(self):
        self.seek_frame(self.timeline_slider.value())

    def timeline_changed(self, value):
        if not self.timeline_slider.isSliderDown():  # Only update if changed programmatically
            self.seek_frame(value)

    def toggle_playback(self):
        self.is_playing = not self.is_playing
        self.play_button.setText("Pause" if self.is_playing else "Play")
        
        if self.is_playing:
            self.play_video()

    def play_video(self):
        if not self.is_playing or self.video_capture is None:
            return
            
        current_frame = self.timeline_slider.value()
        if current_frame >= self.total_frames - 1:
            current_frame = 0
            self.timeline_slider.setValue(0)
            
        self.seek_frame(current_frame)
        self.timeline_slider.setValue(current_frame + 1)
        
        # Schedule next frame
        delay = int(1000 / self.fps)  # Convert to milliseconds
        QTimer.singleShot(delay, self.play_video)

    def convert_to_fisheye(self, frame, rotation_degrees):
        try:
            height, width = frame.shape[:2]
            
            # Create a square output image
            dome_size = min(height, width)
            result = np.zeros((dome_size, dome_size, 3), dtype=np.uint8)
            
            # Create coordinate maps
            y, x = np.meshgrid(np.arange(dome_size), np.arange(dome_size), indexing='ij')
            center = dome_size // 2
            
            # Calculate normalized coordinates
            dx = (x - center) / center
            dy = (y - center) / center
            r = np.sqrt(dx**2 + dy**2)
            theta = np.arctan2(dy, dx)
            
            # Create circular mask
            mask = r <= 1.0
            
            # Apply zoom factor to radius calculation
            r_scaled = r[mask] * self.zoom_factor
            
            # Convert to spherical coordinates
            phi = r_scaled * 0.5 * np.pi  # Azimuthal angle (0 to pi/2)
            theta_sph = theta[mask]       # Polar angle (-pi to pi)
            
            # Convert to 3D cartesian coordinates
            x_cart = np.sin(phi) * np.cos(theta_sph)
            y_cart = np.sin(phi) * np.sin(theta_sph)
            z_cart = np.cos(phi)
            
            # Convert angles to radians
            tilt_rad = np.radians(self.tilt)
            pan_rad = np.radians(self.pan)
            roll_rad = np.radians(self.roll)
            
            # Apply rotations in order: tilt (X) -> pan (Y) -> roll (Z)
            
            # Tilt rotation (around X-axis)
            y_tilt = y_cart * np.cos(tilt_rad) - z_cart * np.sin(tilt_rad)
            z_tilt = y_cart * np.sin(tilt_rad) + z_cart * np.cos(tilt_rad)
            x_tilt = x_cart
            
            # Pan rotation (around Y-axis)
            x_pan = x_tilt * np.cos(pan_rad) + z_tilt * np.sin(pan_rad)
            z_pan = -x_tilt * np.sin(pan_rad) + z_tilt * np.cos(pan_rad)
            y_pan = y_tilt
            
            # Roll rotation (around Z-axis)
            x_roll = x_pan * np.cos(roll_rad) - y_pan * np.sin(roll_rad)
            y_roll = x_pan * np.sin(roll_rad) + y_pan * np.cos(roll_rad)
            z_roll = z_pan
            
            # Convert back to spherical coordinates
            phi_rot = np.arccos(z_roll)
            theta_rot = np.arctan2(y_roll, x_roll)
            
            # Convert to image coordinates
            x_src = ((theta_rot + np.pi) / (2 * np.pi)) * width
            y_src = (phi_rot / np.pi) * height
            
            # Handle wraparound and clipping
            x_src = np.mod(x_src, width)
            y_src = np.clip(y_src, 0, height - 1)
            
            # Sample pixels
            result[mask] = frame[y_src.astype(np.int32), x_src.astype(np.int32)]
            
            # Convert BGR to RGB for Qt
            result = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            
            return result
            
        except Exception as e:
            raise Exception(f"Preview conversion error: {str(e)}")
        
    def update_preview(self):
        if self.video_capture is not None and self.current_frame is not None:
            frame = self.current_frame.copy()
        elif self.original_image is not None:
            frame = self.original_image.copy()
        else:
            return
            
        try:
            # Apply flips before preview conversion
            if self.flip_h:
                frame = cv2.flip(frame, 1)  # 1 for horizontal flip
            if self.flip_v:
                frame = cv2.flip(frame, 0)  # 0 for vertical flip
            
            # Create a preview version
            preview_size = 600  # Reduced size
            height, width = frame.shape[:2]
            scale = preview_size / max(height, width)
            small_image = cv2.resize(frame, (int(width * scale), int(height * scale)))
            
            # Convert to fisheye with current rotation
            preview = self.convert_to_fisheye(small_image, 0)
            
            # Convert to Qt image
            height, width = preview.shape[:2]
            bytes_per_line = 3 * width
            qt_image = QImage(preview.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Scale the image to fit the label while maintaining aspect ratio
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            # Display preview
            self.preview_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update preview: {str(e)}")

    def toggle_flip_h(self):
        self.flip_h = not self.flip_h
        self.flip_h_btn.setStyleSheet(f"background-color: {'#444444' if self.flip_h else '#333333'}")
        self.update_preview()

    def toggle_flip_v(self):
        self.flip_v = not self.flip_v
        self.flip_v_btn.setStyleSheet(f"background-color: {'#444444' if self.flip_v else '#333333'}")
        self.update_preview()

    def handle_theme_change(self, theme_text):
        theme_map = {
            "Green (Default)": "green",
            "Neon Purple": "purple",
            "Christmas Red": "red",
            "Classic Blue": "default"
        }
        self.apply_theme(theme_map[theme_text])

    def show_scale_settings(self):
        dialog = UIScaleDialog(self.ui_scale, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_scale = dialog.get_scale()
            if new_scale != self.ui_scale:
                self.ui_scale = new_scale
                self.apply_scale()
    
    def apply_scale(self):
        # Update font sizes and dimensions
        for btn in [self.import_image_btn, self.import_video_btn, self.scale_settings_btn, self.feedback_btn]:
            btn.setMinimumHeight(int(40 * self.ui_scale))
            btn.setFont(QFont('Segoe UI', int(10 * self.ui_scale)))
        
        # Update preview size
        base_preview_size = 600
        scaled_size = int(base_preview_size * self.ui_scale)
        self.preview_label.setMinimumSize(scaled_size, scaled_size)
        self.preview_label.setMaximumSize(int(800 * self.ui_scale), int(800 * self.ui_scale))
        
        # Update control fonts and sizes
        for slider in [self.tilt_slider, self.pan_slider, self.roll_slider, self.zoom_slider]:
            slider.setMinimumHeight(int(20 * self.ui_scale))
        
        for spinbox in [self.tilt_spinbox, self.pan_spinbox, self.roll_spinbox, self.zoom_spinbox]:
            spinbox.setMinimumHeight(int(25 * self.ui_scale))
            spinbox.setFont(QFont('Segoe UI', int(10 * self.ui_scale)))
        
        # Update flip buttons
        for btn in [self.flip_h_btn, self.flip_v_btn]:
            btn.setMinimumHeight(int(30 * self.ui_scale))
            btn.setFont(QFont('Segoe UI', int(10 * self.ui_scale)))
        
        # Update export button
        self.export_btn.setMinimumHeight(int(40 * self.ui_scale))
        self.export_btn.setFont(QFont('Segoe UI', int(10 * self.ui_scale)))
        
        # Update theme selector
        self.theme_combo.setMinimumHeight(int(30 * self.ui_scale))
        self.theme_combo.setFont(QFont('Segoe UI', int(10 * self.ui_scale)))
        
        # Update video controls if they exist
        if hasattr(self, 'timeline_slider'):
            self.timeline_slider.setMinimumHeight(int(20 * self.ui_scale))
        if hasattr(self, 'play_button'):
            self.play_button.setMinimumHeight(int(30 * self.ui_scale))
            self.play_button.setFont(QFont('Segoe UI', int(10 * self.ui_scale)))
        
        # Force layout update
        self.updateGeometry()
        if self.parent():
            self.parent().adjustSize()

    def open_feedback(self):
        import webbrowser
        webbrowser.open('https://www.facebook.com/daciansolgen24')

class FulldomeConverter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.current_file = None
        self.is_video = False
        
    def initUI(self):
        self.setWindowTitle('Fulldome Exporter')
        self.setGeometry(100, 100, 1200, 700)
        
        # Create main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Left side - Settings
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Add title
        title_label = QLabel('Fulldome Exporter')
        title_label.setStyleSheet("""
            font-size: 48px;
            font-weight: bold;
            color: #c2ff4d;
            margin-bottom: 20px;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title_label)
        
        # Settings group
        settings_group = QGroupBox("Export Settings")
        settings_layout = QVBoxLayout()
        
        # Input format selection
        format_layout = QHBoxLayout()
        format_label = QLabel("Input Format:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(['Equirectangular', 'Cubemap'])
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        settings_layout.addLayout(format_layout)
        
        # Dome type selection
        dome_layout = QHBoxLayout()
        dome_label = QLabel("Dome Type:")
        self.dome_combo = QComboBox()
        self.dome_combo.addItems(['Standard Fulldome', 'Virtual Sky'])
        dome_layout.addWidget(dome_label)
        dome_layout.addWidget(self.dome_combo)
        settings_layout.addLayout(dome_layout)
        
        settings_group.setLayout(settings_layout)
        left_layout.addWidget(settings_group)
        
        # Add about button
        self.btn_about = QPushButton("About & Instructions")
        self.btn_about.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #c2ff4d;
                border: 2px solid #c2ff4d;
                border-radius: 5px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        left_layout.addWidget(self.btn_about)
        left_layout.addStretch()
        
        # Right side - Preview
        self.preview_widget = PreviewWidget()
        
        # Add both sides to main layout
        main_layout.addWidget(left_widget)
        main_layout.addWidget(self.preview_widget)
        
        # Connect signals
        self.preview_widget.import_image_btn.clicked.connect(self.import_image)
        self.preview_widget.import_video_btn.clicked.connect(self.import_video)
        self.preview_widget.export_btn.clicked.connect(self.export_image)
        self.btn_about.clicked.connect(self.show_about)
        
    def import_image(self):
        try:
            file_filter = "Image files (*.jpg *.png);;All files (*.*)"
            input_path, _ = QFileDialog.getOpenFileName(self, "Select input image", "", file_filter)
            
            if input_path:
                self.current_file = input_path
                self.is_video = False
                self.preview_widget.set_image(input_path)
                
        except Exception as e:
            self.show_error(str(e))
    
    def import_video(self):
        try:
            file_filter = "Video files (*.mp4 *.avi);;All files (*.*)"
            input_path, _ = QFileDialog.getOpenFileName(self, "Select input video", "", file_filter)
            
            if input_path:
                # Show warning about conversion time
                reply = QMessageBox.warning(
                    self,
                    "Video Conversion Warning",
                    "Video conversion can take a long time depending on the file size and length. "
                    "The application will be unresponsive during conversion. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.current_file = input_path
                    self.is_video = True
                    self.preview_widget.set_video(input_path)
                    
        except Exception as e:
            self.show_error(str(e))

    def export_image(self):
        try:
            if not self.current_file:
                raise Exception("No media loaded")
                
            # Get output file
            if self.is_video:
                default_ext = ".mp4"
                file_filter = "Video files (*.mp4);;All files (*.*)"
            else:
                default_ext = ".jpg"
                file_filter = "Image files (*.jpg);;All files (*.*)"
                
            output_path, _ = QFileDialog.getSaveFileName(self, "Save output file", "", file_filter)
            
            if output_path:
                # Get settings
                dome_type = 'standard' if self.dome_combo.currentText() == 'Standard Fulldome' else 'virtual_sky'
                tilt = self.preview_widget.tilt
                pan = self.preview_widget.pan
                roll = self.preview_widget.roll
                zoom_factor = self.preview_widget.zoom_factor
                flip_h = self.preview_widget.flip_h
                flip_v = self.preview_widget.flip_v
                
                # Start conversion
                self.conversion_thread = ConversionThread(
                    self.current_file,
                    output_path,
                    self.is_video,
                    self.format_combo.currentText(),
                    dome_type,
                    0,  # rotation
                    zoom_factor,
                    tilt,
                    pan,
                    roll,
                    flip_h,
                    flip_v
                )
                
                # Connect signals
                self.conversion_thread.progress.connect(self.update_progress)
                self.conversion_thread.finished.connect(self.conversion_finished)
                self.conversion_thread.error.connect(self.show_error)
                
                # Disable controls during conversion
                self.preview_widget.export_btn.setEnabled(False)
                self.preview_widget.import_image_btn.setEnabled(False)
                self.preview_widget.import_video_btn.setEnabled(False)
                
                # Show progress bar
                self.progress_bar = QProgressBar()
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)
                self.statusBar().addWidget(self.progress_bar)
                
                self.conversion_thread.start()
                
        except Exception as e:
            self.show_error(str(e))

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def conversion_finished(self):
        self.progress_bar.setVisible(False)
        self.statusBar().removeWidget(self.progress_bar)
        QMessageBox.information(self, "Success", "Export completed successfully!")
        self.preview_widget.export_btn.setEnabled(True)
        self.preview_widget.import_image_btn.setEnabled(True)
        self.preview_widget.import_video_btn.setEnabled(True)
    
    def show_about(self):
        about_text = """
        <h2>Fulldome Converter</h2>
        <p>A powerful tool for converting 360° videos and photos into fulldome format, designed for planetariums and dome projections.</p>
        
        <p><b>How to Use:</b></p>
        <ol>
            <li><b>Import Media:</b>
                <ul>
                    <li>Click "Import Image" for photos or "Import Video" for video files</li>
                    <li>Supported formats: JPG, PNG, MP4, MOV, AVI</li>
                    <li>For videos, use the timeline slider and play/pause controls to preview</li>
                </ul>
            </li>
            <li><b>Adjust Settings:</b>
                <ul>
                    <li>Input Format: Choose between Equirectangular (360°) or Cubemap</li>
                    <li>Dome Type: Select Standard Fulldome or Virtual Sky based on your projection needs</li>
                </ul>
            </li>
            <li><b>Fine-tune the View:</b>
                <ul>
                    <li>Tilt (X-axis): Adjust vertical rotation (-180° to 180°)</li>
                    <li>Pan (Y-axis): Adjust horizontal rotation (-180° to 180°)</li>
                    <li>Roll (Z-axis): Rotate around the center (-180° to 180°)</li>
                    <li>Zoom: Adjust field of view (0.1 to 2.0)</li>
                    <li>Flip: Use horizontal/vertical flip buttons if needed</li>
                </ul>
            </li>
            <li><b>Preview:</b>
                <ul>
                    <li>Changes are shown in real-time in the preview window</li>
                    <li>For videos, scrub through timeline to check different parts</li>
                    <li>Use UI Scale button to adjust interface size if needed</li>
                </ul>
            </li>
            <li><b>Export:</b>
                <ul>
                    <li>Click "Export" when satisfied with the preview</li>
                    <li>Choose output location and filename</li>
                    <li>For videos: Be patient, conversion may take time</li>
                    <li>Progress bar will show conversion status</li>
                </ul>
            </li>
        </ol>

        <p><b>Tips:</b></p>
        <ul>
            <li>Preview your video thoroughly before exporting to ensure correct orientation</li>
            <li>Use the timeline to check critical moments in your video</li>
            <li>For better precision, use the spinboxes instead of sliders</li>
            <li>The UI can be scaled up/down using the UI Scale button if needed</li>
            <li>Don't close the application during video conversion</li>
        </ul>
        
        <p><b>Features:</b></p>
        <ul>
            <li>Support for images and videos</li>
            <li>Real-time preview with adjustable parameters</li>
            <li>Multiple dome configurations</li>
            <li>Video timeline control</li>
            <li>Horizontal and vertical flip options</li>
            <li>Adjustable UI scaling</li>
        </ul>
        
        <p><b>Open Source Project:</b></p>
        <p>This tool is open source and free to use. We welcome contributions from the community! Whether you're interested in:</p>
        <ul>
            <li>Adding new features</li>
            <li>Improving existing functionality</li>
            <li>Fixing bugs</li>
            <li>Enhancing the user interface</li>
            <li>Optimizing performance</li>
            <li>Adding support for new formats</li>
        </ul>
        
        <p>Feel free to fork the project, make improvements, and submit pull requests. Together, we can make this tool even better for the fulldome community!</p>
        
        <p><b>Technical Information:</b></p>
        <ul>
            <li>Built with Python and PyQt6</li>
            <li>Uses OpenCV for video processing</li>
            <li>Cross-platform compatible</li>
        </ul>
        
        <p><b>Warning:</b> Video conversion may take significant time depending on the file size and length.</p>
        
        <p><b>Contact & Support:</b><br>
        Email: <a href="mailto:dacsol@gmail.com">dacsol@gmail.com</a><br>
        Feedback: <a href="https://www.facebook.com/daciansolgen24">Facebook Page</a></p>
        
        <p><b>Get Involved:</b><br>
        If you're interested in contributing or have suggestions, please reach out! All skill levels are welcome.</p>
        
        <p> 2024 Fulldome Converter - Open Source Project<br>
        Released under the MIT License</p>
        """
        
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("About Fulldome Converter")
        about_dialog.setFixedSize(600, 800)  # Increased size for better readability
        
        layout = QVBoxLayout()
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setHtml(about_text)
        
        layout.addWidget(text_browser)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(about_dialog.close)
        layout.addWidget(close_button)
        
        about_dialog.setLayout(layout)
        about_dialog.exec()
    
    def show_error(self, message):
        QMessageBox.critical(self, "Error", str(message))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont('Segoe UI', 10)
    app.setFont(font)
    
    ex = FulldomeConverter()
    ex.show()
    sys.exit(app.exec())
