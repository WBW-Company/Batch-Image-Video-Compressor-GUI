# Batch Image & Video Compressor GUI

A Python application with a Graphical User Interface (GUI) for batch compressing images and videos within a selected folder and its subfolders. It supports converting images to WEBP (with lossless or lossy fallback) and compressing videos to MP4, offering options for resizing and removing metadata/audio.

## Features

*   **GUI:** User-friendly graphical interface.
*   **Folder Processing:** Processes all supported files within a selected folder and its subfolders, maintaining the original structure in the output directory.
*   **Image Compression (WEBP):**
    *   Attempts lossless WEBP compression.
    *   If lossless results in a larger file, it falls back to lossy WEBP compression (quality 85).
    *   If both lossless and lossy WEBP are larger than the original, the file is skipped.
    *   Option to remove image metadata (primarily EXIF).
    *   Option to resize large images (dimensions exceeding a threshold) by a specified percentage.
*   **Video Compression (MP4):**
    *   Compresses videos to MP4 (H.264 video codec, AAC audio codec by default).
    *   Option to remove video audio stream.
    *   Option to remove video metadata streams.
*   **Progress Tracking:** Displays overall progress with a progress bar.
*   **Detailed Logs:** Provides a log area showing the status and result for each processed file, including errors.
*   **Compression Statistics:** Shows total original size, total compressed size, and estimated data saved.
*   **Output Management:** Automatically creates a `compressed` subfolder within the source directory.

## Requirements

*   Python 3.x
*   Pillow library (`pip install Pillow`)
*   ffmpeg (must be installed and available in your system's PATH for video processing)

## Installation

1.  **Clone or Download:** Get the script files from this repository.
2.  **Install Python Dependencies:** Open your terminal or command prompt and run:
    ```bash
    pip install Pillow
    ```
3.  **Install ffmpeg:**
    ffmpeg is a separate command-line tool. You need to install it and ensure it's accessible from your system's command line (added to the PATH environment variable).
    *   **Windows:**
        *   **Recommended (using winget):** Open Command Prompt or PowerShell **as Administrator** and run: `winget install ffmpeg`.
        *   **Manual:** Download a build from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) (e.g., from gyan.dev or BtbN). Extract the zip file and add the path to the `/bin` folder (containing `ffmpeg.exe`) to your system's `PATH` environment variable.
    *   **macOS (using Homebrew):** Open Terminal and run: `brew install ffmpeg`. (Install Homebrew first if you don't have it).
    *   **Linux (using package manager):** Open Terminal and run:
        *   Debian/Ubuntu: `sudo apt update && sudo apt install ffmpeg`
        *   Fedora/CentOS/RHEL: `sudo dnf install ffmpeg ffmpeg-devel` (or `yum`)
4.  **Verify ffmpeg Installation:** Open a **new** terminal or command prompt window and run:
    ```bash
    ffmpeg -version
    ```
    You should see version information if it's installed and in your PATH. If not, video compression will fail.

## How to Use

1.  Run the Python script from your terminal:
    ```bash
    python your_script_name.py
    ```
    (Replace `your_script_name.py` with the actual name of the script file).
2.  The GUI window will open.
3.  Click the "Browse" button to select the folder containing the images and videos you want to compress.
4.  Check the desired options (Image Compression, Remove Metadata, Resize, Video Audio, Video Metadata). For resizing, enter the percentage reduction and the minimum dimension threshold for applying the resize.
5.  Click the "Start Compression" button.
6.  Monitor the "Logs" area for per-file status updates and the "Progress" bar and "Statistics" area for overall progress and results.
7.  Skompresowane pliki pojawią się w podfolderze `compressed` wewnątrz wybranego folderu źródłowego.

## Troubleshooting

*   **`ffmpeg not found` errors:** This means the program could not execute the `ffmpeg` command. Ensure `ffmpeg` is correctly installed and that its executable path is added to your system's `PATH` environment variable. **Remember to open a brand new terminal/command prompt window after modifying PATH** before running the script again.

## License

(You can add a license here, e.g., MIT, GPL, etc. or state if it's public domain)
