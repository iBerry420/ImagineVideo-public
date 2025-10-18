import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import subprocess
import json
import threading
import time
from typing import List, Optional, Tuple

# Try to import watchdog for file watching functionality
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True

    class VideoFileHandler(FileSystemEventHandler):
        """Handler for file system events to automatically process new video files."""

        def __init__(self, ui_app):
            self.ui_app = ui_app
            self.supported_extensions = ui_app.video_extensions

        def on_created(self, event):
            """Called when a new file is created."""
            if event.is_directory:
                return

            file_path = event.src_path
            if Path(file_path).suffix.lower() in self.supported_extensions:
                # Refresh the video list on the main thread
                self.ui_app.root.after(0, self.ui_app.load_videos)
                # Auto-process if enabled
                if self.ui_app.auto_process_var.get():
                    # Run processing in a separate thread to avoid blocking
                    import threading
                    thread = threading.Thread(target=self.ui_app.process_new_video, args=(file_path,))
                    thread.daemon = True
                    try:
                        thread.start()
                    except Exception as e:
                        print(f"Warning: Could not start auto-processing thread: {e}")

except ImportError:
    WATCHDOG_AVAILABLE = False
    VideoFileHandler = None

class VideoEditorUI:
    """
    A GUI application for video frame editing operations.
    
    Features:
    - Extract last frames from videos
    - Trim last frames from videos
    - Batch processing with progress indication
    - Support for multiple video formats
    """
    
    def __init__(self, root):
        """Initialize the VideoEditorUI application."""
        self.root = root
        self.root.title("xAI Video Frame Editor")
        self.root.geometry("900x600")
        self.root.minsize(700, 500)

        # Handle application close to clean up file watcher
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Variables
        self.video_dir = tk.StringVar()
        self.video_listbox = None
        self.videos: List[str] = []  # List of video paths
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="Ready")
        self.is_processing = False
        self.auto_process_var = tk.BooleanVar(value=False)
        self.observer = None  # File watcher observer
        self.watching = False  # Flag to track if watching is active
        self.lock = threading.Lock()
        
        # Supported video formats
        self.video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v', '.3gp'}
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface components."""
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        
        # Directory selection frame
        dir_frame = ttk.LabelFrame(self.root, text="Video Directory", padding="10")
        dir_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        ttk.Label(dir_frame, text="Directory:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(dir_frame, textvariable=self.video_dir, width=50).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(dir_frame, text="Browse", command=self.browse_dir).grid(row=0, column=2, padx=(0, 5))
        ttk.Button(dir_frame, text="Load Videos", command=self.load_videos).grid(row=0, column=3)
        dir_frame.columnconfigure(1, weight=1)

        # Auto-process toggle
        ttk.Checkbutton(dir_frame, text="Auto-process new videos (extract & trim)", variable=self.auto_process_var,
                       command=self.toggle_auto_process).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))

        
        # Video list frame
        list_frame = ttk.LabelFrame(self.root, text="Videos", padding="10")
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=5)
        
        # Video count label
        self.video_count_label = ttk.Label(list_frame, text="No videos loaded")
        self.video_count_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.video_listbox = tk.Listbox(listbox_frame, height=12, selectmode=tk.EXTENDED)
        self.video_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.video_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.video_listbox.config(yscrollcommand=scrollbar.set)
        
        listbox_frame.columnconfigure(0, weight=1)
        listbox_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)
        
        # Progress frame
        progress_frame = ttk.Frame(self.root, padding="10")
        progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.grid(row=0, column=1, sticky=tk.W)
        progress_frame.columnconfigure(0, weight=1)
        
        # Buttons frame
        btn_frame = ttk.LabelFrame(self.root, text="Operations", padding="10")
        btn_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        # Extract buttons
        extract_frame = ttk.Frame(btn_frame)
        extract_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        ttk.Label(extract_frame, text="Extract Last Frame:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Button(extract_frame, text="Selected", command=lambda: self.extract_last_frames(selected=True)).grid(row=0, column=1, padx=2)
        ttk.Button(extract_frame, text="All", command=lambda: self.extract_last_frames(selected=False)).grid(row=0, column=2, padx=2)
        
        # Trim buttons
        trim_frame = ttk.Frame(btn_frame)
        trim_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        ttk.Label(trim_frame, text="Trim Last Frame:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Button(trim_frame, text="Selected", command=lambda: self.trim_last_frames(selected=True)).grid(row=0, column=1, padx=2)
        ttk.Button(trim_frame, text="All", command=lambda: self.trim_last_frames(selected=False)).grid(row=0, column=2, padx=2)
        
        btn_frame.columnconfigure(0, weight=1)
    
    def browse_dir(self):
        """Open directory browser and load videos from selected directory."""
        directory = filedialog.askdirectory(title="Select Video Directory")
        if directory:
            self.stop_watching()  # Stop any previous watcher
            self.video_dir.set(directory)
            self.load_videos()
    
    def load_videos(self):
        """Load video files from the selected directory."""
        dir_path = self.video_dir.get()
        if not dir_path:
            messagebox.showwarning("Warning", "Please select a directory first.")
            return

        if not os.path.exists(dir_path):
            messagebox.showerror("Error", "Selected directory does not exist.")
            return
        
        try:
            self.videos = []
            self.video_listbox.delete(0, tk.END)
            
            # Find video files
            video_files = []
            for file in os.listdir(dir_path):
                if Path(file).suffix.lower() in self.video_extensions:
                    video_files.append(file)
            
            video_files.sort()  # Sort alphabetically for consistent order
            
            for filename in video_files:
                video_path = os.path.join(dir_path, filename)
                self.videos.append(video_path)
                self.video_listbox.insert(tk.END, Path(filename).stem)
            
            # Update video count
            count = len(self.videos)
            self.video_count_label.config(text=f"{count} video{'s' if count != 1 else ''} loaded")
            
            if not self.videos:
                messagebox.showinfo("Info", "No supported video files found in the directory.")
                self.video_count_label.config(text="No videos loaded")
                
        except PermissionError:
            messagebox.showerror("Error", "Permission denied accessing the directory.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load videos: {str(e)}")

        # Always restart file watching for the (possibly new) directory
        self.start_file_watching()

    def get_max_counter(self, output_dir: str, pattern: str) -> int:
        """Get the maximum existing counter from files in the directory."""
        max_num = 0
        for file in os.listdir(output_dir):
            if pattern in file:
                parts = file.rsplit(pattern, 1)
                if len(parts) > 1:
                    num_str, _ = os.path.splitext(parts[1])
                    try:
                        num = int(num_str)
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
        return max_num

    def wait_for_file_ready(self, file_path: str, max_wait: int = 60, check_interval: float = 1.0) -> bool:
        """Wait until the file size stabilizes, indicating it's fully written."""
        import time
        start_time = time.time()
        last_size = -1
        while time.time() - start_time < max_wait:
            try:
                current_size = os.path.getsize(file_path)
                if current_size == last_size and current_size > 0:
                    time.sleep(0.5)  # Brief extra wait to confirm stability
                    return True
                last_size = current_size
            except OSError:
                # File might be temporarily inaccessible; retry
                pass
            time.sleep(check_interval)
        return False

    def on_closing(self):
        """Handle application closing - clean up file watcher."""
        self.stop_watching()
        self.root.destroy()

    def toggle_auto_process(self):
        """Update status when auto-process toggle changes."""
        if self.observer and self.observer.is_alive():
            if self.auto_process_var.get():
                self.status_var.set("Auto-processing enabled...")
            else:
                self.status_var.set("Watching for new videos...")

    def start_file_watching(self):
        """Start watching the directory for new video files."""
        if not WATCHDOG_AVAILABLE or not VideoFileHandler:
            messagebox.showwarning("Warning", "File watching requires the 'watchdog' package. Please install it with: pip install watchdog")
            return

        dir_path = self.video_dir.get()
        if not dir_path or not os.path.exists(dir_path):
            messagebox.showwarning("Warning", "Please select a valid directory first.")
            return

        if self.observer:
            try:
                self.stop_watching()
            except Exception as e:
                print(f"Warning: Error stopping previous watcher: {e}")
                self.observer = None

        event_handler = VideoFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, dir_path, recursive=False)
        self.observer.start()
        self.watching = True

        # Set status based on auto-process state
        if self.auto_process_var.get():
            self.status_var.set("Auto-processing enabled...")
        else:
            self.status_var.set("Watching for new videos...")

    def stop_watching(self):
        """Stop watching the directory."""
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=5.0)  # Increased timeout to prevent hanging
            except Exception as e:
                print(f"Warning: Error stopping file watcher: {e}")
            finally:
                self.observer = None
                self.watching = False
                self.status_var.set("Ready")

    def process_new_video(self, video_path: str):
        """Automatically process a newly added video file."""
        if not self.wait_for_file_ready(video_path):
            print(f"Timeout waiting for {video_path} to stabilize; skipping auto-processing.")
            return

        filename = Path(video_path).stem

        # Extract last frame using FFmpeg
        try:
            if not self._check_ffmpeg():
                return

            output_dir = os.path.join(self.video_dir.get(), "last_frames")
            os.makedirs(output_dir, exist_ok=True)

            duration, fps = self.get_video_info(video_path)
            if duration is None or fps is None or duration <= 1 / fps:
                return

            seek_offset = 1 / fps
            with self.lock:
                current_max = self.get_max_counter(output_dir, "_last_")
                counter = current_max + 1
                frame_path = os.path.join(output_dir, f"{filename}_last_{counter}.jpg")
                open(frame_path, 'a').close()  # Create placeholder file
            cmd = [
                'ffmpeg', '-y',
                '-sseof', f'-{seek_offset}',
                '-i', video_path,
                '-update', '1',
                '-q:v', '1',
                frame_path
            ]
            subprocess.run(cmd, capture_output=True, check=True, timeout=300)

        except Exception as e:
            print(f"Error extracting frame from {video_path}: {e}")

        # Trim last frame
        try:
            if not self._check_ffmpeg():
                return

            output_dir = os.path.join(self.video_dir.get(), "trimmed_videos")
            os.makedirs(output_dir, exist_ok=True)

            duration, fps = self.get_video_info(video_path)
            if duration is None or fps is None:
                return

            if duration <= 1 / fps:  # Less than or equal to one frame
                return

            trim_duration = duration - (1 / fps)
            ext = Path(video_path).suffix
            with self.lock:
                current_max = self.get_max_counter(output_dir, "_trimmed_")
                counter = current_max + 1
                out_path = os.path.join(output_dir, f"{filename}_trimmed_{counter}{ext}")
                open(out_path, 'a').close()  # Create placeholder file

            # FFmpeg command: copy streams up to trim_duration
            cmd = [
                'ffmpeg', '-y',  # Overwrite output
                '-i', video_path,
                '-t', str(trim_duration),
                '-c', 'copy',  # No re-encoding
                '-avoid_negative_ts', 'make_zero',
                out_path
            ]

            subprocess.run(cmd, capture_output=True, check=True, timeout=300)

        except Exception as e:
            print(f"Error trimming {video_path}: {e}")

    def get_selected_videos(self, selected: bool = True) -> List[str]:
        """Get list of selected videos or all videos."""
        if selected:
            indices = self.video_listbox.curselection()
            return [self.videos[i] for i in indices]
        else:
            return self.videos.copy()
    
    def extract_last_frames(self, selected: bool = True):
        """Extract last frames from selected or all videos."""
        if self.is_processing:
            messagebox.showwarning("Warning", "Another operation is in progress. Please wait.")
            return
            
        videos = self.get_selected_videos(selected)
        if not videos:
            messagebox.showwarning("Warning", "No videos selected or loaded.")
            return
        
        # Run in separate thread to avoid blocking UI
        thread = threading.Thread(target=self._extract_last_frames_thread, args=(videos,))
        thread.daemon = True
        thread.start()
    
    def _extract_last_frames_thread(self, videos: List[str]):
        """Thread function for extracting last frames."""
        self.is_processing = True
        self.progress_var.set(0)
        self.status_var.set("Extracting last frames...")
        
        try:
            if not self._check_ffmpeg():
                raise Exception("FFmpeg not available")

            output_dir = os.path.join(self.video_dir.get(), "last_frames")
            os.makedirs(output_dir, exist_ok=True)
            
            success_count = 0
            total_videos = len(videos)
            
            for i, video_path in enumerate(videos):
                try:
                    # Update progress
                    progress = (i / total_videos) * 100
                    self.progress_var.set(progress)
                    self.status_var.set(f"Processing: {Path(video_path).name}")
                    
                    if not os.path.exists(video_path):
                        continue
                    
                    duration, fps = self.get_video_info(video_path)
                    if duration is None or fps is None or duration <= 1 / fps:
                        continue
                    
                    seek_offset = 1 / fps
                    filename = Path(video_path).stem
                    with self.lock:
                        current_max = self.get_max_counter(output_dir, "_last_")
                        counter = current_max + 1
                        frame_path = os.path.join(output_dir, f"{filename}_last_{counter}.jpg")
                        open(frame_path, 'a').close()  # Create placeholder file
                    cmd = [
                        'ffmpeg', '-y',
                        '-sseof', f'-{seek_offset}',
                        '-i', video_path,
                        '-update', '1',
                        '-q:v', '1',
                        frame_path
                    ]
                    subprocess.run(cmd, capture_output=True, check=True, timeout=300)
                    
                    success_count += 1
                    
                except Exception as e:
                    print(f"Error processing {video_path}: {e}")
                    continue
            
            # Update UI on main thread
            self.root.after(0, lambda: self._extraction_complete(success_count, output_dir, total_videos))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Extraction failed: {str(e)}"))
        finally:
            self.is_processing = False
    
    def _extraction_complete(self, success_count: int, output_dir: str, total_videos: int):
        """Handle completion of frame extraction."""
        self.progress_var.set(100)
        self.status_var.set(f"Extracted {success_count}/{total_videos} frames")
        messagebox.showinfo("Success", f"Extracted last frames from {success_count} out of {total_videos} videos to '{output_dir}'.")
    
    def get_video_info(self, video_path: str) -> Tuple[Optional[float], Optional[float]]:
        """Use ffprobe to get duration and fps of a video file."""
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            data = json.loads(result.stdout)
            
            # Get duration from format
            duration = float(data['format']['duration'])
            
            # Get fps from video stream
            video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
            if video_stream and 'r_frame_rate' in video_stream:
                r_frame_rate = video_stream['r_frame_rate'].split('/')
                if len(r_frame_rate) == 2 and r_frame_rate[1] != '0':
                    fps = float(r_frame_rate[0]) / float(r_frame_rate[1])
                else:
                    fps = 30.0  # Fallback
            else:
                fps = 30.0  # Fallback
            
            return duration, fps
            
        except subprocess.TimeoutExpired:
            print(f"Timeout getting info for {Path(video_path).name}")
            return None, None
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, ZeroDivisionError, ValueError) as e:
            print(f"Error getting info for {Path(video_path).name}: {e}")
            return None, None
    
    def trim_last_frames(self, selected: bool = True):
        """Trim last frames from selected or all videos."""
        if self.is_processing:
            messagebox.showwarning("Warning", "Another operation is in progress. Please wait.")
            return
            
        videos = self.get_selected_videos(selected)
        if not videos:
            messagebox.showwarning("Warning", "No videos selected or loaded.")
            return
        
        # Check if FFmpeg is available
        if not self._check_ffmpeg():
            return
        
        if messagebox.askyesno("Confirm", 
                              "Trimming will create new videos without the last frame in a 'trimmed_videos' subfolder using FFmpeg (no re-encoding). Originals will be preserved. Proceed?"):
            # Run in separate thread to avoid blocking UI
            thread = threading.Thread(target=self._trim_last_frames_thread, args=(videos,))
            thread.daemon = True
            thread.start()
    
    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available on the system."""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=10)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            messagebox.showerror("Error", "FFmpeg is not installed or not available. Please install FFmpeg to use trimming functionality.")
            return False
    
    def _trim_last_frames_thread(self, videos: List[str]):
        """Thread function for trimming last frames."""
        self.is_processing = True
        self.progress_var.set(0)
        self.status_var.set("Trimming last frames...")
        
        try:
            output_dir = os.path.join(self.video_dir.get(), "trimmed_videos")
            os.makedirs(output_dir, exist_ok=True)
            
            success_count = 0
            total_videos = len(videos)
            
            for i, video_path in enumerate(videos):
                try:
                    # Update progress
                    progress = (i / total_videos) * 100
                    self.progress_var.set(progress)
                    self.status_var.set(f"Processing: {Path(video_path).name}")
                    
                    if not os.path.exists(video_path):
                        continue
                    
                    duration, fps = self.get_video_info(video_path)
                    if duration is None or fps is None:
                        continue
                    
                    if duration <= 1 / fps:  # Less than or equal to one frame
                        continue
                    
                    trim_duration = duration - (1 / fps)
                    filename = Path(video_path).stem
                    ext = Path(video_path).suffix
                    with self.lock:
                        current_max = self.get_max_counter(output_dir, "_trimmed_")
                        counter = current_max + 1
                        out_path = os.path.join(output_dir, f"{filename}_trimmed_{counter}{ext}")
                        open(out_path, 'a').close()  # Create placeholder file
                    
                    # FFmpeg command: copy streams up to trim_duration
                    cmd = [
                        'ffmpeg', '-y',  # Overwrite output
                        '-i', video_path,
                        '-t', str(trim_duration),
                        '-c', 'copy',  # No re-encoding
                        '-avoid_negative_ts', 'make_zero',
                        out_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, check=True, timeout=300)
                    success_count += 1
                    
                except subprocess.TimeoutExpired:
                    print(f"Timeout trimming {Path(video_path).name}")
                    continue
                except subprocess.CalledProcessError as e:
                    print(f"Failed to trim {Path(video_path).name}: {e}")
                    continue
                except Exception as e:
                    print(f"Error processing {video_path}: {e}")
                    continue
            
            # Update UI on main thread
            self.root.after(0, lambda: self._trimming_complete(success_count, output_dir, total_videos))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Trimming failed: {str(e)}"))
        finally:
            self.is_processing = False
    
    def _trimming_complete(self, success_count: int, output_dir: str, total_videos: int):
        """Handle completion of frame trimming."""
        self.progress_var.set(100)
        self.status_var.set(f"Trimmed {success_count}/{total_videos} videos")
        messagebox.showinfo("Success", f"Trimmed last frames from {success_count} out of {total_videos} videos to '{output_dir}'.")

def main():
    """Main function to run the application."""
    try:
        root = tk.Tk()
        app = VideoEditorUI(root)
        root.mainloop()
    except Exception as e:
        print(f"Application error: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {str(e)}")

if __name__ == "__main__":
    main()
