# Imagine Video Frame Editor (Extend your Imagine Videos)

## Overview

The **Imagine Video Frame Editor** is a graphical user interface (GUI) application built in Python using Tkinter, designed for batch processing and editing video files. It specializes in extracting the last frame from videos as JPEG images and trimming the last frame from videos to create shortened copies, all while preserving the original files. The app supports multiple video formats and includes an auto-processing feature that monitors a selected directory for new videos and processes them automatically if enabled.

This tool is particularly useful for users dealing with large collections of videos, such as content creators, researchers, or anyone needing to analyze or modify video endings efficiently. It leverages FFmpeg for video processing tasks, ensuring fast operations without re-encoding (for trimming), and provides a user-friendly interface with progress tracking.

## Use Case: Extending Videos with Imagine

This script is optimized for integration with Imagine feature, which generates 6-second videos. To create longer, seamless videos, users can:
- Extract the last frame from a generated video and upload it to Imagine as a starting point for the next segment.
- Use the trimmed video (which removes the last frame) to concatenate with the next generated video, avoiding a "double frame" effect where the end of one segment and start of the next overlap visually.
- This process allows chaining multiple 6-second clips into a continuous, longer video without noticeable jumps or duplications at the seams.

For example:
1. Generate a 6-second video with Imagine.
2. Use this app to extract the last frame (`_last_N.jpg`) and trim the video (`_trimmed_N.mp4`).
3. Upload the extracted frame to Imagine to generate the next 6-second continuation.
4. Concatenate the trimmed video with the new one (using tools like FFmpeg externally).
5. Repeat for extended sequences.

The auto-processing mode is ideal for this workflow, as new videos added to the directory (e.g., from Imagine downloads) are immediately processed.

Key capabilities include:
- **Batch Extraction of Last Frames**: Extract the last frame from selected or all videos in a directory and save them as JPEG images in a `last_frames` subfolder.
- **Batch Trimming of Last Frames**: Trim the last frame from selected or all videos, creating new copies in a `trimmed_videos` subfolder using stream copying for efficiency.
- **Auto-Processing**: Automatically detect and process new video files added to the monitored directory (requires the `watchdog` library).
- **Supported Formats**: Handles common video extensions like `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.webm`, `.m4v`, and `.3gp`.
- **Sequential Naming**: Output files are named with the original video stem plus `_last_N.jpg` or `_trimmed_N.ext`, where `N` is a sequential counter based on existing files to avoid overwrites.
- **Progress and Status Indicators**: Real-time progress bar and status messages during operations.
- **Threaded Operations**: Processing runs in background threads to keep the UI responsive.
- **File Stability Check**: For auto-processing, waits for new files to stabilize (size stops changing) before processing, preventing issues with incomplete files.

The app does not modify original videos; all outputs are saved in dedicated subfolders.

## Features in Detail

### Directory Selection and Video Loading
- Browse and select a directory containing video files.
- Automatically loads and lists all supported videos in the directory, sorted alphabetically.
- Displays the count of loaded videos.
- Videos are shown in a scrollable listbox with multi-selection support for targeted operations.

### Extraction of Last Frames
- **Selected Videos**: Extract from user-selected videos in the list.
- **All Videos**: Extract from every loaded video.
- Uses FFmpeg to seek to the last frame (offset by one frame duration) and export it as a high-quality JPEG.
- Skips videos with one or fewer frames.
- Outputs to `./last_frames/` with names like `video_stem_last_N.jpg`, where `N` is the next available sequential number (scanned from existing files to ensure uniqueness).

### Trimming of Last Frames
- **Selected Videos**: Trim from user-selected videos.
- **All Videos**: Trim from every loaded video.
- Uses FFmpeg to copy video streams up to the duration minus one frame, without re-encoding for speed and quality preservation.
- Confirms action via a dialog to prevent accidental processing.
- Skips videos shorter than one frame.
- Outputs to `./trimmed_videos/` with names like `video_stem_trimmed_N.ext`, preserving the original extension, where `N` is the next sequential number.

### Auto-Processing Mode
- Toggleable checkbox to enable/disable auto-processing.
- Monitors the selected directory for new video files using the `watchdog` library.
- When a new supported video is detected (via file creation event), it:
  - Waits for the file to stabilize (file size stops changing, up to 60 seconds).
  - Automatically extracts the last frame and trims the video if enabled.
- Runs processing in a daemon thread to avoid blocking the UI.
- Refreshes the video list automatically upon new file detection.
- Status updates to indicate watching or auto-processing mode.

### Progress and Error Handling
- Progress bar shows percentage completion during batch operations.
- Status label provides real-time feedback (e.g., "Processing: video_name.mp4").
- Error messages for issues like missing FFmpeg, invalid directories, or processing failures.
- Skips problematic videos and continues with others.
- Cleans up file watcher on app close to prevent resource leaks.

### Technical Notes
- **Sequential Counters**: Counters are dynamically calculated by scanning the output directories for the highest existing `_last_` or `_trimmed_` number across all files. This ensures continuity even if files are manually renamed or added. A lock ensures thread safety during concurrent operations.
- **File Watching**: Uses `watchdog` for efficient, event-based monitoring (creation events only, non-recursive).
- **Video Info Retrieval**: Uses `ffprobe` (part of FFmpeg) to get duration and FPS accurately.
- **Thread Safety**: Uses locks when calculating counters to handle concurrent auto-processing.
- **Timeouts**: FFmpeg commands have timeouts (e.g., 300 seconds) to prevent hangs.
- **No Re-Encoding for Trims**: Leverages `-c copy` in FFmpeg for fast, lossless trimming.
- **Placeholder Files**: Creates empty placeholder files before FFmpeg runs to reserve the filename during counter calculation, preventing race conditions in multi-threaded environments.

## Installation and Setup

### Prerequisites
- **Python**: Version 3.8 or higher (tested on 3.12). Download from [python.org](https://www.python.org/downloads/).
- **FFmpeg**: Required for video processing. Install on your system:
  - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.
  - **macOS**: Use Homebrew: `brew install ffmpeg`.
  - **Linux**: Use package manager, e.g., `sudo apt install ffmpeg` (Ubuntu) or `sudo yum install ffmpeg` (Fedora).
- **watchdog**: For auto-processing (optional but recommended for the Imagine workflow).

The app uses built-in Python libraries like `tkinter`, `pathlib`, `subprocess`, `json`, `threading`, and `time`. No additional GUI libraries are needed as Tkinter is included in standard Python installations.

### Installation Steps
1. **Clone or Download the Script**:
   - Save the script as `xai_video_editor.py` (or any name).

2. **Install Python Dependencies**:
   - Open a terminal/command prompt.
   - Navigate to the script's directory.
   - Run: `pip install watchdog`
     - This installs the file monitoring library. If you don't need auto-processing, you can skip this, but the app will warn you if it's missing. It's highly recommended for seamless integration with Imagine.

3. **Verify FFmpeg**:
   - Run `ffmpeg -version` in your terminal. If it works, you're good. If not, install FFmpeg as above.

4. **Run the App**:
   - Execute: `python xai_video_editor.py`
   - The GUI window will open.

### Troubleshooting Installation
- **Tkinter Not Found**: On some Linux systems, install `sudo apt install python3-tk`. On Windows/macOS, it's usually bundled.
- **FFmpeg Not Found**: Ensure it's in your system's PATH. Restart your terminal after installation.
- **Permission Issues**: Run as administrator if accessing protected directories.
- **Python Version**: Use `python --version` to check. Upgrade if below 3.8.
- **watchdog ImportError**: Install via pip as above. If unavailable, auto-processing is disabled with a warning.
- **App Freezes on Startup**: Ensure no prior instances are running; kill any hanging Python processes.

## Usage Guide

1. **Launch the App**:
   - Run the script as described.

2. **Select Directory**:
   - Click "Browse" to choose a folder with videos (e.g., where you save Imagine outputs).
   - Or enter the path manually and click "Load Videos".
   - Videos load into the listbox.

3. **Enable Auto-Processing (Recommended for Imagine Workflow)**:
   - Check the "Auto-process new videos" box.
   - The app starts monitoring; status updates accordingly.

4. **Perform Operations**:
   - Select videos (Ctrl+click for multiple) or use "All".
   - Click "Extract Last Frame: Selected/All" for extraction.
   - Click "Trim Last Frame: Selected/All" for trimming (confirm prompt appears).
   - Watch the progress bar and status.

5. **Add New Videos (e.g., from Imagine)**:
   - Download a new video from Imagine and save it to the monitored directory.
   - If auto-process is on, it processes automatically: extracts last frame for upload back to Imagine, and trims for concatenation.
   - List refreshes automatically.

6. **View Outputs**:
   - Check `./last_frames/` for images to upload to Imagine.
   - Check `./trimmed_videos/` for trimmed clips ready for merging.
   - Files are named sequentially to avoid conflicts.

7. **Close the App**:
   - Click the window close button; watcher stops cleanly.

### Example Workflow with Imagine
- Generate a 6-second video with Imagine and save to the directory.
- App auto-processes: Creates `video_last_1.jpg` (upload this to Imagine for continuation) and `video_trimmed_1.mp4`.
- Generate next segment in Imagine using the extracted frame.
- Save new video to directory; app auto-processes to `video2_last_2.jpg` and `video2_trimmed_2.mp4`.
- Concatenate trimmed videos externally (e.g., via FFmpeg: `ffmpeg -f concat -i files.txt -c copy output.mp4`).
- Repeat for longer videos without seam issues.

## Limitations
- **No Editing of Existing Outputs**: The app doesn't modify or delete outputs; manage manually.
- **Short Videos**: Skips videos ≤1 frame.
- **Large Files**: May timeout (300s); increase in code if needed.
- **No Re-Encoding for Trims**: Trims are fast but may have minor timestamp issues (mitigated with `-avoid_negative_ts`).
- **Directory Changes**: Reload videos manually if files are deleted/renamed.
- **Platform**: Tested on Linux/Windows/macOS, but FFmpeg paths may vary.
- **Imagine Integration**: Manual upload/download; no direct API connection.

## Contributing
- Fork the script and suggest improvements (e.g., add concatenation feature, custom FPS handling).
- Report issues like hangs or errors with details (OS, Python version, FFmpeg version).

## License
This script is open-source under the MIT License. Use and modify freely.

For questions, refer to the code comments or experiment with the GUI. Enjoy extending your Imagine videos!"
