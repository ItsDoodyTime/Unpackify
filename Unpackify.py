import os
import sys
import shutil
import threading
import zipfile
import tarfile
import rarfile
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from tkinter import ttk
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import errno

SUPPORTED_EXTENSIONS = (
    ".zip", ".tar", ".tar.gz", ".tgz",
    ".tar.bz2", ".tbz2", ".rar"
)

# ------------------------------
# Estimate total size
# ------------------------------
def estimate_required_space(archives):
    total_size = 0
    for path in archives:
        try:
            total_size += os.path.getsize(path)
        except:
            pass
    return total_size * 2

# ------------------------------
# UI Stuff
# ------------------------------
class UnpackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Unpackify")
        self.root.geometry("700x600")
        
        icon_path = self.get_resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        self.cancel_flag = False
        self.total_files = 0
        self.completed_files = 0
        self.start_time = None

        self.setup_dark_theme()
        self.build_ui()

    def get_resource_path(self, relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    # ------------------------------
    # UI Styling
    # ------------------------------
    def setup_dark_theme(self):
        self.bg = "#1e1e1e"
        self.fg = "#ffffff"
        self.error_color = "#ff4d4d"
        self.success_color = "#4dff88"
        self.accent = "#2d2d2d"

        self.root.configure(bg=self.bg)

    # ------------------------------
    # UI itself
    # ------------------------------
    def build_ui(self):
        tk.Label(self.root, text="Folder Path:", bg=self.bg, fg=self.fg).pack(pady=5)

        self.path_entry = tk.Entry(self.root, width=75, bg=self.accent, fg=self.fg, insertbackground=self.fg)
        self.path_entry.pack(pady=5)

        tk.Button(self.root, text="Browse", command=self.browse_folder,
                  bg=self.accent, fg=self.fg).pack(pady=5)

        self.include_subfolders = tk.BooleanVar()
        tk.Checkbutton(self.root, text="Also unpack files in subfolders",
                       variable=self.include_subfolders,
                       bg=self.bg, fg=self.fg,
                       selectcolor=self.accent).pack(pady=5)

        tk.Label(self.root, text="If destination folder exists:",
                 bg=self.bg, fg=self.fg).pack(pady=5)

        self.overwrite_option = tk.StringVar(value="skip")

        options_frame = tk.Frame(self.root, bg=self.bg)
        options_frame.pack()

        for text, val in [("Skip", "skip"),
                          ("Overwrite", "overwrite"),
                          ("Rename", "rename")]:
            tk.Radiobutton(options_frame, text=text,
                           variable=self.overwrite_option,
                           value=val,
                           bg=self.bg, fg=self.fg,
                           selectcolor=self.accent).pack(side=tk.LEFT, padx=10)

        btn_frame = tk.Frame(self.root, bg=self.bg)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Start Extraction",
                  command=self.start_extraction,
                  bg=self.accent, fg=self.fg).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_frame, text="Cancel",
                  command=self.cancel_extraction,
                  bg=self.accent, fg=self.fg).pack(side=tk.LEFT, padx=10)

        self.progress = ttk.Progressbar(self.root, orient="horizontal",
                                        length=550, mode="determinate")
        self.progress.pack(pady=10)

        info_frame = tk.Frame(self.root, bg=self.bg)
        info_frame.pack()

        self.percent_label = tk.Label(info_frame, text="0%", bg=self.bg, fg=self.fg)
        self.percent_label.pack(side=tk.LEFT, padx=20)

        self.eta_label = tk.Label(info_frame, text="ETA: --", bg=self.bg, fg=self.fg)
        self.eta_label.pack(side=tk.LEFT, padx=20)

        self.output_box = scrolledtext.ScrolledText(
            self.root,
            height=18,
            bg=self.accent,
            fg=self.fg,
            insertbackground=self.fg
        )
        self.output_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # ------------------------------
    # Logging
    # ------------------------------
    def log(self, message, color=None):
        self.output_box.insert(tk.END, message + "\n", color)
        self.output_box.tag_config("error", foreground=self.error_color)
        self.output_box.tag_config("success", foreground=self.success_color)
        self.output_box.see(tk.END)

    # ------------------------------
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)

    # ------------------------------
    def cancel_extraction(self):
        self.cancel_flag = True
        self.log("Cancellation requested...", "error")

    # ------------------------------
    def extract_archive(self, file_path):
        if self.cancel_flag:
            return

        folder_name = os.path.splitext(os.path.basename(file_path))[0]
        extract_path = os.path.join(os.path.dirname(file_path), folder_name)

        if os.path.exists(extract_path):
            mode = self.overwrite_option.get()

            if mode == "skip":
                self.log(f"Skipped: {file_path}")
                return
            elif mode == "rename":
                counter = 1
                new_path = extract_path
                while os.path.exists(new_path):
                    new_path = f"{extract_path}_{counter}"
                    counter += 1
                extract_path = new_path

        os.makedirs(extract_path, exist_ok=True)

        try:
            if file_path.lower().endswith(".zip"):
                with zipfile.ZipFile(file_path, 'r') as archive:
                    archive.extractall(extract_path)

            elif file_path.lower().endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2")):
                with tarfile.open(file_path, 'r:*') as archive:
                    archive.extractall(extract_path)

            elif file_path.lower().endswith(".rar"):
                with rarfile.RarFile(file_path) as archive:
                    archive.extractall(extract_path)

            self.log(f"Extracted: {file_path}")

        except OSError as e:
            if e.errno == errno.ENOSPC:
                self.log(f"Disk full while extracting: {file_path}", "error")
                self.cleanup_partial(extract_path, "Disk space exhausted")
                self.cancel_flag = True
            else:
                self.log(f"Failed: {file_path} -> {e}", "error")
                self.cleanup_partial(extract_path, "Extraction error")

        except Exception as e:
            self.log(f"Failed: {file_path} -> {e}", "error")
            self.cleanup_partial(extract_path, "Extraction error")

    # ------------------------------
    # Cleanup partial extraction
    # ------------------------------
    def cleanup_partial(self, folder_path, reason):
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                self.log(f"Cleaned up partial folder: {folder_path}", "error")
                self.log(f"Reason: {reason}", "error")
            except Exception as e:
                self.log(f"Cleanup failed: {e}", "error")

    # ------------------------------
    def start_extraction(self):
        base_path = self.path_entry.get()

        if not os.path.isdir(base_path):
            messagebox.showerror("Error", "Please select a valid folder path.")
            return

        self.cancel_flag = False
        self.output_box.delete(1.0, tk.END)

        archive_list = []

        for root_dir, dirs, files in os.walk(base_path):
            for file in files:
                if file.lower().endswith(SUPPORTED_EXTENSIONS):
                    archive_list.append(os.path.join(root_dir, file))
            if not self.include_subfolders.get():
                break

        if not archive_list:
            messagebox.showinfo("Info", "No archives found.")
            return

        # STORAGE PRE-CHECK
        required_space = estimate_required_space(archive_list)
        free_space = shutil.disk_usage(base_path).free

        if free_space < required_space:
            messagebox.showerror("Error", "Not enough disk space to safely extract archives.")
            return

        self.total_files = len(archive_list)
        self.completed_files = 0
        self.progress["maximum"] = self.total_files
        self.progress["value"] = 0
        self.start_time = time.time()

        threading.Thread(
            target=self.run_parallel,
            args=(archive_list,),
            daemon=True
        ).start()

    # ------------------------------
    def run_parallel(self, archive_list):
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = [executor.submit(self.extract_archive, f) for f in archive_list]

            for future in as_completed(futures):
                if self.cancel_flag:
                    break

                self.completed_files += 1
                self.root.after(0, self.update_progress)

        if not self.cancel_flag:
            self.root.after(0, lambda: self.log("Done!", "success"))

    # ------------------------------
    def update_progress(self):
        self.progress["value"] = self.completed_files
        percent = int((self.completed_files / self.total_files) * 100)
        self.percent_label.config(text=f"{percent}%")

        elapsed = time.time() - self.start_time
        avg = elapsed / max(1, self.completed_files)
        remaining = avg * (self.total_files - self.completed_files)
        self.eta_label.config(text=f"ETA: {int(remaining)} sec")


if __name__ == "__main__":
    root = tk.Tk()
    app = UnpackerApp(root)
    root.mainloop()
