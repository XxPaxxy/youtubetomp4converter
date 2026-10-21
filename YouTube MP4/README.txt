YouTube to MP4 - Windows

Double-click Start.cmd. Paste a YouTube video link, select a quality and folder,
then click Download MP4. Python 3 with Tkinter is required (already present on
the computer this was created on).

The first download fetches yt-dlp and Deno from their official GitHub releases.
It uses FFmpeg from your computer, or downloads a Windows build from gyan.dev.
Tools are kept in the app's tools folder. Internet access is required.

4K is downloaded only when available in the original upload. Lower-resolution
uploads stay at their available quality; the app does not upscale them.
An MP4 container may contain VP9 or AV1 video. Older players may need a newer
player or codec. Video streams are merged without a slow quality-losing re-encode.

Private, restricted, DRM-protected videos and some live streams may not work.
Use this for videos you own or have permission to download.

If YouTube changes and downloads stop working, close the app and delete only
tools/yt-dlp.exe; the next download fetches the latest engine.

Sources: https://github.com/yt-dlp/yt-dlp
https://github.com/yt-dlp/yt-dlp/wiki/EJS
https://www.gyan.dev/ffmpeg/builds/
