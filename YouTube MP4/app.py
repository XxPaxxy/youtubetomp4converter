import os
import queue
import shutil
import subprocess
import threading
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BASE = Path(__file__).resolve().parent
TOOLS = BASE / 'tools'


def youtube_url(value):
    parsed = urllib.parse.urlparse(value.strip())
    if parsed.scheme not in ('https', 'http') or parsed.hostname not in (
        'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be',
        'music.youtube.com'):
        raise ValueError('Paste a valid YouTube video link.')
    return value.strip()


def fetch(url, target):
    temporary = target.with_suffix(target.suffix + '.part')
    try:
        with urllib.request.urlopen(url, timeout=60) as source, temporary.open('wb') as output:
            shutil.copyfileobj(source, output)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def dependencies(log):
    TOOLS.mkdir(exist_ok=True)
    downloader = TOOLS / 'yt-dlp.exe'
    if not downloader.exists():
        log('Setting up the download engine...')
        fetch('https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe', downloader)
    for name, url, member in [
        ('deno', 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip', 'deno.exe'),
        ('ffmpeg', 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip', None),
    ]:
        if (TOOLS / (name + '.exe')).exists() or shutil.which(name):
            continue
        log('Setting up ' + name + ' (first run only)...')
        archive = TOOLS / (name + '.zip')
        fetch(url, archive)
        with zipfile.ZipFile(archive) as package:
            members = [member] if member else [n for n in package.namelist() if n.endswith(('/ffmpeg.exe', '/ffprobe.exe'))]
            if not members:
                raise RuntimeError('The FFmpeg package did not contain the expected tools.')
            for item in members:
                with package.open(item) as source, (TOOLS / Path(item).name).open('wb') as output:
                    shutil.copyfileobj(source, output)
        archive.unlink()
    return downloader


def command(executable, url, folder, height):
    return [str(executable), '--ignore-config', '--no-playlist', '--newline',
            '--windows-filenames', '--no-overwrites', '--js-runtimes',
            'deno:' + str(TOOLS / 'deno.exe') if (TOOLS / 'deno.exe').exists() else 'deno',
            '--ffmpeg-location', str(TOOLS) if (TOOLS / 'ffmpeg.exe').exists() else str(Path(shutil.which('ffmpeg') or 'ffmpeg').parent),
            '-f', f'bv[height<={height}]+ba/b[height<={height}]',
            '--merge-output-format', 'mp4', '--remux-video', 'mp4',
            '-P', str(folder), '-o', '%(title).160B [%(id)s].%(ext)s', '--', url]


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.process = None
        self.busy = False
        root.title('YouTube to MP4')
        root.geometry('720x510')
        root.minsize(600, 450)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='YouTube to MP4', font=('Segoe UI', 22, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Save a video with audio, up to 4K when available.').pack(anchor='w', pady=(4, 20))
        ttk.Label(frame, text='YouTube link').pack(anchor='w')
        self.url = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url).pack(fill='x', pady=(4, 12))
        row = ttk.Frame(frame)
        row.pack(fill='x')
        self.quality = tk.StringVar(value='4K (2160p)')
        ttk.Combobox(row, textvariable=self.quality, state='readonly', values=['4K (2160p)', '1440p', '1080p', '720p'], width=18).pack(side='left')
        self.folder = tk.StringVar(value=str(Path.home() / 'Downloads'))
        ttk.Button(row, text='Choose save folder', command=self.choose).pack(side='right')
        ttk.Label(frame, textvariable=self.folder, wraplength=650).pack(anchor='w', pady=10)
        self.download = ttk.Button(frame, text='Download MP4', command=self.start)
        self.download.pack(fill='x')
        self.status = tk.StringVar(value='Ready. First download sets up the required tools.')
        ttk.Label(frame, textvariable=self.status, wraplength=650).pack(anchor='w', pady=10)
        self.log = tk.Text(frame, height=10, wrap='word', state='disabled', font=('Consolas', 9))
        self.log.pack(fill='both', expand=True)
        ttk.Label(frame, text='Use for videos you own or have permission to download.').pack(anchor='w', pady=(10, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def choose(self):
        result = filedialog.askdirectory(initialdir=self.folder.get())
        if result:
            self.folder.set(result)

    def start(self):
        try:
            url = youtube_url(self.url.get())
        except ValueError as error:
            messagebox.showerror('Check the link', str(error))
            return
        height = {'4K (2160p)': 2160, '1440p': 1440, '1080p': 1080, '720p': 720}[self.quality.get()]
        folder = Path(self.folder.get())
        self.busy = True
        self.download.configure(state='disabled')
        self.status.set('Preparing download...')
        threading.Thread(target=self.work, args=(url, folder, height), daemon=True).start()

    def work(self, url, folder, height):
        try:
            executable = dependencies(lambda text: self.events.put(('log', text)))
            folder.mkdir(parents=True, exist_ok=True)
            self.process = subprocess.Popen(command(executable, url, folder, height), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for line in self.process.stdout:
                self.events.put(('log', line.rstrip()))
            code = self.process.wait()
            if code:
                raise RuntimeError('Download failed. See the details above. YouTube may restrict this video; updating the engine can help.')
            self.events.put(('done', 'Finished. Your MP4 is in the selected save folder.'))
        except Exception as error:
            self.events.put(('done', str(error)))
        finally:
            self.process = None

    def poll(self):
        while not self.events.empty():
            kind, text = self.events.get_nowait()
            if kind == 'done':
                self.busy = False
                self.download.configure(state='normal')
            self.status.set(text[-220:])
            self.log.configure(state='normal')
            self.log.insert('end', text + '\n')
            self.log.see('end')
            self.log.configure(state='disabled')
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('Download in progress', 'Wait for the current download and setup to finish before closing.')
            return
        self.root.destroy()


if __name__ == '__main__':
    window = tk.Tk()
    App(window)
    window.mainloop()
