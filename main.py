import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
import os
import subprocess
import pathlib
from PIL import Image, UnidentifiedImageError, ExifTags
from PIL import Image
import sys
import time
import concurrent.futures
import shutil

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

DEFAULT_RESIZE_PERCENTAGE = 15.0
DEFAULT_RESIZE_THRESHOLD = 2000
WEBP_LOSSY_FALLBACK_QUALITY = 85

def format_bytes(byte_count):
    if byte_count is None:
        return "N/A"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while byte_count >= power and n < len(power_labels) - 1:
        byte_count /= power
        n += 1
    return f"{byte_count:.2f} {power_labels[n]}B"

def process_image(file_path, output_folder, options):
    original_size = 0
    compressed_size = 0
    status = 'skipped'
    message = f"Skipped {os.path.basename(file_path)} (No image processing selected)."

    try:
        original_size = os.path.getsize(file_path)
        file_ext = pathlib.Path(file_path).suffix.lower()

        if file_ext in IMAGE_EXTS and options.get('compress_images_webp', False):
            status = 'fail'
            temp_message = f"Processing {os.path.basename(file_path)}..."

            relative_path = pathlib.Path(file_path).relative_to(options['source_folder'])
            output_path = pathlib.Path(output_folder) / relative_path.with_suffix('.webp')

            output_path.parent.mkdir(parents=True, exist_ok=True)

            img = Image.open(file_path)
            original_dimensions = img.size

            resized = False
            if options.get('enable_resize', False) and (img.width > options.get('resize_threshold', DEFAULT_RESIZE_THRESHOLD) or img.height > options.get('resize_threshold', DEFAULT_RESIZE_THRESHOLD)):
                try:
                    resize_percentage = options.get('resize_percentage', DEFAULT_RESIZE_PERCENTAGE)
                    if 0 < resize_percentage < 100:
                        scale_factor = 1.0 - (resize_percentage / 100.0)
                        new_width = int(img.width * scale_factor)
                        new_height = int(img.height * scale_factor)
                        new_width = max(1, new_width)
                        new_height = max(1, new_height)

                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        resized = True
                        temp_message += f" (resized from {original_dimensions[0]}x{original_dimensions[1]} to {new_width}x{new_height})"
                    else:
                         temp_message += f" (invalid resize percentage, skipping resize)"
                except Exception as e:
                    temp_message += f" (error during resize: {e}, skipping resize)"

            if img.mode in ('P', 'L', 'LA', 'CMYK', 'RGB'):
                 if img.mode in ('RGB', 'P', 'L'):
                     img = img.convert('RGBA')
                 elif img.mode == 'LA':
                     img = img.convert('RGBA')

            save_options = {'format': 'WEBP'}
            if options.get('remove_image_metadata', False):
                 save_options['exif'] = b''

            temp_message += " Trying lossless WEBP..."
            lossless_output_path = output_path.parent / f"{output_path.stem}_lossless{output_path.suffix}"
            lossless_size = None
            try:
                img.save(lossless_output_path, quality=100, lossless=True, **save_options)
                lossless_size = lossless_output_path.stat().st_size
            except Exception as e:
                 temp_message += f" Lossless save failed: {e}"

            use_lossy_fallback = False
            if lossless_size is not None and lossless_size < original_size:
                 compressed_size = lossless_size
                 final_save_path = lossless_output_path
                 status = 'success'
                 message = f"Compressed {os.path.basename(file_path)} to lossless WEBP"
                 if resized: message += f" (resized from {original_dimensions[0]}x{original_dimensions[1]})"
                 message += f" ({format_bytes(original_size)} -> {format_bytes(compressed_size)})"

            else:
                 use_lossy_fallback = True
                 temp_message += f" Lossless size {format_bytes(lossless_size) if lossless_size is not None else 'N/A'} >= original {format_bytes(original_size)}. Trying lossy WEBP (Q={WEBP_LOSSY_FALLBACK_QUALITY})..."
                 if lossless_output_path.exists():
                      lossless_output_path.unlink()

            if use_lossy_fallback:
                lossy_output_path = output_path.parent / f"{output_path.stem}_lossy{output_path.suffix}"
                lossy_size = None
                try:
                    img.save(lossy_output_path, quality=WEBP_LOSSY_FALLBACK_QUALITY, **save_options)
                    lossy_size = lossy_output_path.stat().st_size

                    if lossy_size is not None and lossy_size < original_size:
                        compressed_size = lossy_size
                        final_save_path = lossy_output_path
                        status = 'success_lossy'
                        message = f"Compressed {os.path.basename(file_path)} to lossy WEBP (Q={WEBP_LOSSY_FALLBACK_QUALITY})"
                        if resized: message += f" (resized from {original_dimensions[0]}x{original_dimensions[1]})"
                        message += f" ({format_bytes(original_size)} -> {format_bytes(compressed_size)})"
                    else:
                        status = 'skipped_size_increase'
                        message = f"Skipped {os.path.basename(file_path)} (Both lossless and lossy WEBP ({format_bytes(lossy_size) if lossy_size is not None else 'N/A'}) resulted in larger file than original ({format_bytes(original_size)}))."
                        if lossy_output_path.exists():
                             lossy_output_path.unlink()
                        compressed_size = 0

                except Exception as e:
                    status = 'fail'
                    message = f"Error processing image {os.path.basename(file_path)}: Lossy save failed - {e}"
                    compressed_size = 0
                    if lossy_output_path.exists():
                         lossy_output_path.unlink()

            if status in ('success', 'success_lossy'):
                try:
                    shutil.move(final_save_path, output_path)
                except Exception as e:
                    status = 'fail'
                    message = f"Error renaming/moving temporary file for {os.path.basename(file_path)}: {e}"
                    compressed_size = 0
                    if final_save_path.exists():
                        final_save_path.unlink()

        elif file_ext in IMAGE_EXTS and not options.get('compress_images_webp', False):
             status = 'skipped'
             message = f"Skipped {os.path.basename(file_path)} (Image compression disabled)."


    except FileNotFoundError:
        status = 'fail'
        message = f"Error: File not found {os.path.basename(file_path)}"
        compressed_size = 0
    except UnidentifiedImageError:
        status = 'fail'
        message = f"Error: Cannot identify image file {os.path.basename(file_path)}"
        compressed_size = 0
    except Exception as e:
        status = 'fail'
        message = f"An unexpected error occurred processing image {os.path.basename(file_path)}: {e}"
        compressed_size = 0
    finally:
         if 'img' in locals() and img:
              try:
                   img.close()
              except Exception:
                   pass

    return {
        'original_size': original_size,
        'compressed_size': compressed_size,
        'status': status,
        'message': message,
        'file_path': file_path
    }

def process_video(file_path, output_folder, options):
    original_size = 0
    compressed_size = 0
    status = 'fail'
    message = f"Error processing video {os.path.basename(file_path)}"

    try:
        original_size = os.path.getsize(file_path)
        file_ext = pathlib.Path(file_path).suffix.lower()

        if file_ext in VIDEO_EXTS:

            relative_path = pathlib.Path(file_path).relative_to(options['source_folder'])
            output_path = pathlib.Path(output_folder) / relative_path.with_suffix('.mp4')

            output_path.parent.mkdir(parents=True, exist_ok=True)

            command = [
                'ffmpeg',
                '-i', file_path,
                '-c:v', 'libx264',
                '-crf', '23',
                '-preset', 'medium',
            ]

            if options.get('remove_video_audio', False):
                command.extend(['-an'])
            else:
                command.extend(['-c:a', 'aac', '-b:a', '128k'])

            if options.get('remove_video_metadata', False):
                 command.extend(['-map_metadata', '-1'])

            command.extend(['-f', 'mp4'])

            command.extend([
                '-y',
                str(output_path)
            ])

            process = subprocess.run(command, capture_output=True, text=True)

            if process.returncode == 0:
                if output_path.exists() and os.path.getsize(output_path) > 0:
                    compressed_size = os.path.getsize(output_path)
                    status = 'success'
                    message = f"Compressed {os.path.basename(file_path)} to MP4 ({format_bytes(original_size)} -> {format_bytes(compressed_size)})"
                else:
                    status = 'fail'
                    message = f"Error processing video {os.path.basename(file_path)}: Output file not created or is empty."
                    if process.stderr.strip():
                         message += f"\nffmpeg output:\n{process.stderr.strip()}"
                    if output_path.exists():
                        output_path.unlink()
            else:
                status = 'fail'
                message = f"Error processing video {os.path.basename(file_path)}. ffmpeg failed with code {process.returncode}."
                if process.stderr.strip():
                     message += f"\nffmpeg output:\n{process.stderr.strip()}"
                print(f"FFmpeg stderr for {os.path.basename(file_path)}:\n{process.stderr.strip()}")


    except FileNotFoundError:
        status = 'fail'
        message = f"Error: ffmpeg not found. Please ensure it's installed and in your system's PATH."
        print("Error: ffmpeg not found. Please install ffmpeg and ensure it's in your system's PATH.")
    except Exception as e:
        status = 'fail'
        message = f"An unexpected error occurred processing video {os.path.basename(file_path)}: {e}"

    return {
        'original_size': original_size,
        'compressed_size': compressed_size,
        'status': status,
        'message': message,
        'file_path': file_path
    }

class CompressorApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Image & Video Compressor")
        self.geometry("750x650")
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        self.source_folder = ""
        self.total_files_to_process = 0
        self.files_processed_count = 0
        self.total_original_size = 0
        self.total_compressed_size = 0
        self.processing_start_time = None
        self.executor = None
        self.futures = []

        self.enable_resize_var = tk.BooleanVar(value=False)
        self.resize_percent_var = tk.StringVar(value=str(DEFAULT_RESIZE_PERCENTAGE))
        self.resize_threshold_var = tk.StringVar(value=str(DEFAULT_RESIZE_THRESHOLD))


        self.create_widgets()
        self.update_stats_display()

        self.check_ffmpeg()

    def create_widgets(self):
        folder_frame = ttk.LabelFrame(self, text="Folders", padding="10")
        folder_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        ttk.Label(folder_frame, text="Source Folder:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.folder_entry = ttk.Entry(folder_frame, width=50)
        self.folder_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(folder_frame, text="Browse", command=self.select_folder).grid(row=0, column=2, padx=5, pady=5)

        folder_frame.columnconfigure(1, weight=1)

        options_frame = ttk.LabelFrame(self, text="Options", padding="10")
        options_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        ttk.Label(options_frame, text="Image Options:").grid(row=0, column=0, sticky="w", pady=(0, 2), columnspan=2)
        self.compress_images_webp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text=f"Compress Images (Lossless WEBP or Lossy Q={WEBP_LOSSY_FALLBACK_QUALITY} fallback if larger)", variable=self.compress_images_webp_var).grid(row=1, column=0, sticky="w", padx=10, pady=2, columnspan=2)

        self.remove_image_metadata_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Remove Metadata from Images", variable=self.remove_image_metadata_var).grid(row=2, column=0, sticky="w", padx=10, pady=2, columnspan=2)

        self.enable_resize_check = ttk.Checkbutton(options_frame, text="Resize Large Images", variable=self.enable_resize_var, command=self.toggle_resize_options)
        self.enable_resize_check.grid(row=3, column=0, sticky="w", padx=10, pady=(5,2), columnspan=2)

        self.resize_percent_label = ttk.Label(options_frame, text="Percentage (%):")
        self.resize_percent_label.grid(row=4, column=0, sticky="e", padx=(20, 0), pady=2)

        self.resize_percent_entry = ttk.Entry(options_frame, textvariable=self.resize_percent_var, width=5)
        self.resize_percent_entry.grid(row=4, column=1, sticky="w", padx=(0, 5), pady=2)

        self.resize_threshold_label = ttk.Label(options_frame, text="Threshold (px, max dim >):")
        self.resize_threshold_label.grid(row=5, column=0, sticky="e", padx=(20, 0), pady=2)

        self.resize_threshold_entry = ttk.Entry(options_frame, textvariable=self.resize_threshold_var, width=7)
        self.resize_threshold_entry.grid(row=5, column=1, sticky="w", padx=(0, 5), pady=2)

        self.toggle_resize_options()

        ttk.Label(options_frame, text="Video Options:").grid(row=6, column=0, sticky="w", pady=(10, 2), columnspan=2)
        self.remove_video_audio_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Remove Audio from Videos", variable=self.remove_video_audio_var).grid(row=7, column=0, sticky="w", padx=10, pady=2, columnspan=2)
        self.remove_video_metadata_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Remove Metadata from Videos", variable=self.remove_video_metadata_var).grid(row=8, column=0, sticky="w", padx=10, pady=2, columnspan=2)

        options_frame.columnconfigure(1, weight=1)

        control_frame = ttk.Frame(self, padding="10")
        control_frame.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")

        self.start_button = ttk.Button(control_frame, text="Start Compression", command=self.start_compression)
        self.start_button.grid(row=0, column=0, columnspan=2, pady=10)

        ttk.Label(control_frame, text="Progress:").grid(row=1, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(control_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=1, column=1, sticky="ew", padx=5)

        control_frame.columnconfigure(1, weight=1)

        stats_frame = ttk.LabelFrame(self, text="Statistics", padding="10")
        stats_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        self.stats_label = ttk.Label(stats_frame, text="Processing statistics will appear here.")
        self.stats_label.grid(row=0, column=0, sticky="w")
        stats_frame.columnconfigure(0, weight=1)


        log_frame = ttk.LabelFrame(self, text="Logs", padding="10")
        log_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")

        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, wrap='word')
        self.log_text.grid(row=0, column=0, sticky="nsew")

        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)

    def toggle_resize_options(self):
        state = 'normal' if self.enable_resize_var.get() else 'disabled'
        self.resize_percent_entry.config(state=state)
        self.resize_threshold_entry.config(state=state)

    def log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.update_idletasks()

    def check_ffmpeg(self):
         try:
             subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True)
             self.log_message("ffmpeg found.")
         except FileNotFoundError:
             self.log_message("Warning: ffmpeg not found. Video compression will not work. Please install it and ensure it's in your system's PATH.")
             print("ffmpeg not found warning displayed.")

    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.source_folder = folder_selected
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, self.source_folder)
            self.log_message(f"Source folder selected: {self.source_folder}")

    def start_compression(self):
        self.source_folder = self.folder_entry.get()
        if not self.source_folder or not os.path.isdir(self.source_folder):
            messagebox.showwarning("Invalid Folder", "Please select a valid source folder.")
            self.log_message("Operation failed: Invalid source folder.")
            return

        resize_percentage = DEFAULT_RESIZE_PERCENTAGE
        resize_threshold = DEFAULT_RESIZE_THRESHOLD
        enable_resize = self.enable_resize_var.get()

        if enable_resize:
            try:
                resize_percentage = float(self.resize_percent_var.get())
                if not (0 < resize_percentage < 100):
                     messagebox.showwarning("Invalid Input", "Resize percentage must be between 0 and 100.")
                     return
            except ValueError:
                messagebox.showwarning("Invalid Input", "Resize percentage must be a number.")
                return

            try:
                resize_threshold = int(self.resize_threshold_var.get())
                if resize_threshold <= 0:
                     messagebox.showwarning("Invalid Input", "Resize threshold must be a positive integer.")
                     return
            except ValueError:
                messagebox.showwarning("Invalid Input", "Resize threshold must be an integer.")
                return


        output_folder = os.path.join(self.source_folder, "compressed")

        try:
            os.makedirs(output_folder, exist_ok=True)
            self.log_message(f"Output folder created/ensured: {output_folder}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not create output folder: {e}")
            self.log_message(f"Operation failed: Could not create output folder {output_folder}. Error: {e}")
            return

        self.log_message("Scanning for supported files...")
        self.files_to_process = []
        for root, _, files in os.walk(self.source_folder):
            abs_root = os.path.abspath(root)
            abs_output_folder = os.path.abspath(output_folder)
            if abs_root.startswith(abs_output_folder):
                 continue

            for file in files:
                file_path = os.path.join(root, file)
                file_ext = pathlib.Path(file).suffix.lower()
                if file_ext in IMAGE_EXTS or file_ext in VIDEO_EXTS:
                    self.files_to_process.append(file_path)

        self.total_files_to_process = len(self.files_to_process)
        self.files_processed_count = 0
        self.total_original_size = 0
        self.total_compressed_size = 0

        if self.total_files_to_process == 0:
            messagebox.showinfo("No Files Found", "No supported image or video files found in the selected folder (excluding 'compressed' subfolder).")
            self.log_message("Scan complete: No supported files found.")
            self.update_stats_display()
            return

        image_compression_enabled = self.compress_images_webp_var.get()
        has_videos = any(pathlib.Path(f).suffix.lower() in VIDEO_EXTS for f in self.files_to_process)

        if not image_compression_enabled and not has_videos:
             messagebox.showinfo("No Processing Selected", "No image compression selected and no videos found. Select image compression or ensure videos are present.")
             self.log_message("Operation aborted: No applicable processing options selected for the scanned files.")
             self.update_stats_display()
             return


        self.log_message(f"Found {self.total_files_to_process} supported files.")
        self.progress_bar.config(maximum=self.total_files_to_process, value=0)
        self.start_button.config(state='disabled')

        self.processing_start_time = time.time()
        self.update_stats_display()


        options = {
            'source_folder': self.source_folder,
            'compress_images_webp': image_compression_enabled,
            'remove_image_metadata': self.remove_image_metadata_var.get(),
            'enable_resize': enable_resize,
            'resize_percentage': resize_percentage,
            'resize_threshold': resize_threshold,
            'remove_video_audio': self.remove_video_audio_var.get(),
            'remove_video_metadata': self.remove_video_metadata_var.get(),
        }

        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count())
        self.futures = []

        for file_path in self.files_to_process:
            file_ext = pathlib.Path(file_path).suffix.lower()
            if file_ext in IMAGE_EXTS:
                if options['compress_images_webp']:
                     future = self.executor.submit(process_image, file_path, output_folder, options)
                     self.futures.append(future)
                else:
                    self.files_processed_count += 1
                    self.log_message(f"[SKIPPED] Skipped {os.path.basename(file_path)} (Image compression disabled).")
                    self.update_progress()

            elif file_ext in VIDEO_EXTS:
                 future = self.executor.submit(process_video, file_path, output_folder, options)
                 self.futures.append(future)
            else:
                 self.files_processed_count += 1
                 self.log_message(f"[SKIPPED] File {os.path.basename(file_path)} has unsupported extension.")
                 self.update_progress()


        if not self.futures:
             self.log_message("No files were submitted for processing based on selected options.")
             self.processing_start_time = None
             self.update_stats_display()
             self.start_button.config(state='normal')
             messagebox.showinfo("Process Complete", "Compression process has finished. No files were processed.")
             if self.executor:
                  self.executor.shutdown(wait=False)
                  self.executor = None
             return

        self.after(100, self.check_futures_completion)

    def check_futures_completion(self):
        for future in list(self.futures):
            if future.done():
                try:
                    result = future.result()
                    status = result.get('status', 'unknown')
                    message = result.get('message', 'No message provided')
                    original_size = result.get('original_size', 0)
                    compressed_size = result.get('compressed_size', 0)

                    if status == 'success':
                        self.log_message(f"[SUCCESS] {message}")
                        self.total_original_size += original_size
                        self.total_compressed_size += compressed_size
                    elif status == 'success_lossy':
                         self.log_message(f"[SUCCESS - LOSSY] {message}")
                         self.total_original_size += original_size
                         self.total_compressed_size += compressed_size
                    elif status == 'skipped_size_increase':
                        self.log_message(f"[SKIPPED] {message}")
                        self.total_original_size += original_size
                    elif status == 'skipped':
                         self.log_message(f"[SKIPPED] {message}")
                         self.total_original_size += original_size
                    elif status == 'fail':
                        self.log_message(f"[FAILED] {message}")
                        self.total_original_size += original_size
                    else:
                        self.log_message(f"[UNKNOWN STATUS] {message}")
                        self.total_original_size += original_size

                    self.update_stats_display()

                except concurrent.futures.CancelledError:
                     self.log_message("[CANCELLED] A task was cancelled.")
                except Exception as exc:
                    self.log_message(f"[CRITICAL ERROR] An unhandled exception occurred in a worker process: {exc}")


                self.futures.remove(future)
                self.files_processed_count += 1
                self.update_progress()

        if self.futures:
            if self.files_processed_count < self.total_files_to_process:
                 self.after(100, self.check_futures_completion)
            else:
                 pass

        if not self.futures and self.files_processed_count == self.total_files_to_process:
            if self.executor:
                 self.executor.shutdown(wait=True)
                 self.executor = None
            self.processing_start_time = None
            self.update_stats_display()
            self.start_button.config(state='normal')
            self.log_message("Compression process finished.")
            messagebox.showinfo("Process Complete", "Compression process has finished.")
        elif not self.futures and self.files_processed_count < self.total_files_to_process:
             pass

    def update_progress(self):
        self.progress_bar['value'] = min(self.files_processed_count, self.total_files_to_process)

    def update_stats_display(self):
        total_original_processed_mb = self.total_original_size / (1024 * 1024)
        total_compressed_mb = self.total_compressed_size / (1024 * 1024)

        saved_mb = max(0, total_original_processed_mb - total_compressed_mb)
        savings_percent = (saved_mb / total_original_processed_mb * 100) if total_original_processed_mb > 0 else 0

        stats_text = f"Files Processed: {self.files_processed_count} / {self.total_files_to_process}\n"
        stats_text += f"Total Original Size (from {self.files_processed_count} files): {format_bytes(self.total_original_size)}\n"
        stats_text += f"Total Compressed Size (from successful): {format_bytes(self.total_compressed_size)}\n"
        stats_text += f"Data Saved: {format_bytes(saved_mb * 1024 * 1024)} ({savings_percent:.1f}%)"

        if self.processing_start_time:
            elapsed_time = time.time() - self.processing_start_time
            stats_text += f"\nElapsed Time: {elapsed_time:.1f} seconds"


        self.stats_label.config(text=stats_text)

    def run(self):
        self.mainloop()

if __name__ == "__main__":
    app = CompressorApp()
    app.run()
