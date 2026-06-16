#!/usr/bin/env python3

"""

Video Overlay - Chèn overlay vào video với cắt max duration.

Reads settings from setting_overlay.json

"""

import sys
import os
import json
import shutil
from datetime import datetime
import time


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QDialog, QScrollArea, QFrame, QTabWidget
)

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QIcon
from PyQt6.QtMultimedia import QSoundEffect


# Resolve base directory

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        BASE_DIR = os.getcwd()


SETTINGS_FILE = os.path.join(BASE_DIR, "setting_overlay.json")
LOG_FILE = os.path.join(BASE_DIR, "overlay_logs.txt")


def load_settings() -> dict:

    """Load settings from JSON file"""

    # Default 5 overlay settings

    default_overlays = []

    for i in range(5):

        default_overlays.append({

            "enable": False,

            "name": "",

            "file": "",

            "type": "Video MP4",

            "zindex": i + 1,

            "width": 200,

            "height": 200,

            "x": 0,

            "y": 0,

            "start": 0.0,

            "end": 0.0,

            "opacity": 100.0

        })



    defaults = {

        "general_settings": {

            "source_dir": "",

            "export_dir": "",

            "target_bitrate": "4M",

            "maxrate": "5M",

            "bufsize": "8M",

            "max_duration": 50,

            "encoder": "nvenc",

            "preset": "p2",

            "video_fps": "30",

            "sample_rate": "48000",

            "audio_bitrate": "128",

            "canvas_width": 1080,

            "canvas_height": 1920,

            "ffmpeg_timeout": 120,

            "scale_x": 1.0,

            "scale_y": 1.0,

            "video_x": 0,

            "video_y": 0

        },

        "overlay_settings": default_overlays,

        "effect_settings": {

            "color_grading_enable": False,

            "contrast_min": 1.02,

            "contrast_max": 1.06,

            "saturation_min": 1.04,

            "saturation_max": 1.10,

            "brightness_min": -0.01,

            "brightness_max": 0.005,

            "hue_min": 5,

            "hue_max": 10,

            "unsharp_enable": False,

            "unsharp_x": 5,

            "unsharp_y": 5,

            "unsharp_amount": 0.4

        },

        "custom_effect_settings": {
            "speed_enable": False,
            "speed_min": 1.0,
            "speed_max": 1.0,
            "delay_frame_enable": False,
            "delay_frame_min": 1,
            "delay_frame_max": 5,
            "delay_audio_min": 0.0,
            "delay_audio_max": 0.0,
            "delay_audio_decimals": 3
        }

    }

    

    try:

        if os.path.exists(SETTINGS_FILE):

            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:

                data = json.load(f)

                # Validate that we got valid data

                if data and isinstance(data, dict) and "general_settings" in data:

                    return data

    except Exception as e:

        print(f"⚠️ Lỗi load settings: {str(e)}")

    

    # Return defaults if file doesn't exist or error

    return defaults





def save_settings(data: dict) -> None:

    """Save settings to JSON file"""

    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:

        json.dump(data, f, indent=2, ensure_ascii=False)





def write_log(msg: str) -> None:

    """Write to log file"""

    try:

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(LOG_FILE, 'a', encoding='utf-8') as lf:

            lf.write(f"{ts} - {msg}\n")

            lf.flush()

    except Exception:

        pass





def find_ffmpeg_path() -> str:

    """Find ffmpeg path"""

    # Check common locations

    possible_paths = [

        "ffmpeg",

        "ffmpeg.exe",

        os.path.join(BASE_DIR, "ffmpeg.exe"),

        os.path.join(BASE_DIR, "bin", "ffmpeg.exe"),

        "C:\\ffmpeg\\bin\\ffmpeg.exe",

        "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",

    ]

    

    for path in possible_paths:

        if os.path.exists(path) or shutil.which(path):

            return path

    

    # Default to just 'ffmpeg' and hope it's in PATH

    return "ffmpeg"


def run_ffmpeg(cmd: list, output_path: str, timeout: int = 120, logger=None) -> tuple:
    import subprocess
    import sys
    import os

    def log(msg):
        if logger:
            logger(msg)
        else:
            print(msg)


    # Kill Process
    def _kill_process(proc):
        import subprocess
        import sys

        if sys.platform == "win32":
            try:
                creationflags = (
                    subprocess.CREATE_NO_WINDOW |
                    subprocess.DETACHED_PROCESS
                )

                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=creationflags,
                    shell=False
                )

            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            try:
                proc.kill()
            except Exception:
                pass

    def _cleanup():
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass

    log(f"   [*] FFmpeg: {' '.join(cmd[:4])}...")
    log(f"   [*] Timeout: {timeout}s")

    proc = None
    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                subprocess.CREATE_NO_WINDOW |
                subprocess.DETACHED_PROCESS
            )

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags
        )

        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            log(f"   [!] Timeout sau {timeout}s - kill process...")
            _kill_process(proc)
            _cleanup()
            return (False, f"Timeout sau {timeout}s")

        if proc.returncode != 0:
            log(f"   [X] FFmpeg lỗi (exit {proc.returncode})")
            _cleanup()
            return (False, f"FFmpeg exit code {proc.returncode}")

        if output_path and not os.path.exists(output_path):
            log(f"   [X] Không tạo được file: {output_path}")
            return (False, "Không tạo được file output")

        log(f"   [OK] FFmpeg xong")
        return (True, "")

    except Exception as e:
        log(f"   [X] Lỗi run_ffmpeg: {str(e)}")
        if proc:
            _kill_process(proc)
        _cleanup()
        return (False, str(e))



def get_video_duration(ffmpeg_path: str, video_path: str) -> float:
    import subprocess
    import sys
    import json

    ffprobe_path = ffmpeg_path.replace('ffmpeg', 'ffprobe')

    cmd = [
        ffprobe_path,
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        video_path
    ]

    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                subprocess.CREATE_NO_WINDOW |
                subprocess.DETACHED_PROCESS
            )

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=creationflags
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data.get('format', {}).get('duration', 0))

    except Exception:
        pass

    return 0.0


def has_audio_stream(video_path: str) -> bool:
    import subprocess, sys
    try:
        ffprobe_path = find_ffmpeg_path().replace('ffmpeg', 'ffprobe')
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            video_path,
        ]
        kwargs = dict(capture_output=True, text=True, encoding='utf-8', errors='ignore')
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(cmd, **kwargs)
        return result.returncode == 0 and result.stdout.strip() != ""
    except Exception:
        return False


def get_video_files_recursive(directory: str) -> list:

    """Get all video files recursively"""

    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}

    videos = []



    for root, dirs, files in os.walk(directory):

        for file in files:

            if os.path.splitext(file)[1].lower() in video_extensions:

                full_path = os.path.join(root, file)

                rel_path = os.path.relpath(full_path, directory)

                videos.append((full_path, rel_path))



    return videos


def get_video_size(path):
    import subprocess, sys, json

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        path
    ]

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            subprocess.CREATE_NO_WINDOW |
            subprocess.DETACHED_PROCESS
        )

    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=creationflags
    )

    data = json.loads(res.stdout)
    return data["streams"][0]["width"], data["streams"][0]["height"]


def even(x):
    x = int(x)
    return x if x % 2 == 0 else x - 1


def build_filter_safe(
    input_video,
    canvas_width,
    canvas_height,
    video_fps,
    scale_x,
    scale_y,
    video_x,
    video_y
):
    src_w, src_h = get_video_size(input_video)

    src_ratio = src_w / src_h
    canvas_ratio = canvas_width / canvas_height

    # ===== FIT =====
    if src_ratio > canvas_ratio:
        cover_w = canvas_width
        cover_h = int(cover_w / src_ratio)
    else:
        cover_h = canvas_height
        cover_w = int(cover_h * src_ratio)

    # ===== ZOOM =====
    scaled_w = even(max(2, cover_w * scale_x))
    scaled_h = even(max(2, cover_h * scale_y))

    # =====================================================
    # STEP 1: scale
    # =====================================================
    chain = [
        "setsar=1",
        "setpts=PTS-STARTPTS",
        f"scale={scaled_w}:{scaled_h}",
        f"fps={video_fps}",
    ]

    current_w = scaled_w
    current_h = scaled_h

    # =====================================================
    # STEP 2: crop nếu lớn hơn canvas
    # =====================================================

    if current_w > canvas_width:

        crop_x = (current_w - canvas_width) // 2 - int(video_x)

        crop_x = max(0, min(crop_x, current_w - canvas_width))
        crop_x = even(crop_x)

        chain.append(
            f"crop={canvas_width}:{current_h}:{crop_x}:0"
        )

        current_w = canvas_width

    if current_h > canvas_height:

        crop_y = (current_h - canvas_height) // 2 - int(video_y)

        crop_y = max(0, min(crop_y, current_h - canvas_height))
        crop_y = even(crop_y)

        chain.append(
            f"crop={current_w}:{canvas_height}:0:{crop_y}"
        )

        current_h = canvas_height

    # =====================================================
    # STEP 3: pad nếu nhỏ hơn canvas
    # =====================================================

    if current_w < canvas_width or current_h < canvas_height:

        pad_x = max(0, (canvas_width - current_w) // 2 + int(video_x))
        pad_y = max(0, (canvas_height - current_h) // 2 + int(video_y))

        pad_x = even(pad_x)
        pad_y = even(pad_y)

        chain.append(
            f"pad={canvas_width}:{canvas_height}:{pad_x}:{pad_y}:black"
        )

    filter_str = f"[0:v]{','.join(chain)}[v0]"

    return filter_str


def apply_overlays(
    ffmpeg_path: str,
    input_video: str,
    output_path: str,
    overlay_settings: list,
    target_bitrate: str,
    max_duration: int,
    input_video_duration: float = None,
    video_fps: str = "30",
    sample_rate: str = "44100",
    audio_bitrate: str = "128",
    preset: str = "p2",
    maxrate: str = None,
    bufsize: str = None,
    canvas_width: int = 1080,
    canvas_height: int = 1920,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    video_x: int = 0,
    video_y: int = 0,
    ffmpeg_timeout: int = 120,
    logger=None,
    effect_settings: dict = None,
    custom_effect_settings: dict = None
) -> tuple:
    import uuid, random, os, sys
    effect_settings = effect_settings or {}
    custom_effect_settings = custom_effect_settings or {}

    def log(msg):
        logger(msg) if logger else print(msg)

    temp_dir = os.path.join(os.getcwd(), 'temp_video')
    os.makedirs(temp_dir, exist_ok=True)
    temp_output = os.path.join(temp_dir, f'video_{uuid.uuid4().hex[:8]}.mp4')

    try:
        actual_duration = input_video_duration if input_video_duration and input_video_duration < max_duration else max_duration
        log(f"   [i] Thời lượng sử dụng: {actual_duration}s")

        active_overlays = []
        for o in overlay_settings:
            if not o.get('enable', False): continue
            ov_type = o.get('type', 'Video MP4')
            if 'Random MP4 Folder' in ov_type:
                if o.get('folder'): active_overlays.append(o)
            else:
                if o.get('file'): active_overlays.append(o)

        active_overlays.sort(key=lambda x: x.get('zindex', 1))

        if not active_overlays:
            log(f"   [i] Không có overlay → chỉ xử lý video gốc")

        cmd = [ffmpeg_path, '-y', '-fflags', '+genpts', '-i', input_video]

        # ===== FIX 1: normalize overlay input =====
        for overlay in active_overlays:
            overlay_type = overlay.get('type', 'Video MP4')
            if 'Random MP4 Folder' in overlay_type:
                folder = overlay.get('folder')
                files = [f for f in os.listdir(folder) if f.lower().endswith('.mp4')] if folder and os.path.exists(folder) else []
                if not files:
                    log(f"   [!] Không có file mp4: {folder}"); continue
                rf = random.choice(files)
                overlay['_actual_file'] = os.path.join(folder, rf)
                log(f"   [R] Chọn: {rf}")
            else:
                overlay['_actual_file'] = overlay.get('file')

            # ⚠️ FIX: thêm genpts cho từng input overlay
            overlay_file = overlay['_actual_file']
            if overlay_file.lower().endswith('.png'):
                cmd.extend([
                    '-loop', '1',
                    '-framerate', str(video_fps),
                    '-i', overlay_file
                ])
            else:
                cmd.extend([
                    '-fflags', '+genpts',
                    '-i', overlay_file
                ])


        # ===== CONDITIONAL COLOR GRADING & UNSHARP =====
        color_grading_enable = effect_settings.get('color_grading_enable', False)
        unsharp_enable = effect_settings.get('unsharp_enable', False)

        if color_grading_enable:
            contrast = round(random.uniform(
                effect_settings.get('contrast_min', 1.02),
                effect_settings.get('contrast_max', 1.06)
            ), 2)
            saturation = round(random.uniform(
                effect_settings.get('saturation_min', 1.04),
                effect_settings.get('saturation_max', 1.10)
            ), 2)
            brightness = round(random.uniform(
                effect_settings.get('brightness_min', -0.01),
                effect_settings.get('brightness_max', 0.005)
            ), 3)
            hue_shift = random.randint(
                effect_settings.get('hue_min', 5),
                effect_settings.get('hue_max', 10)
            )

        unsharp_x = effect_settings.get('unsharp_x', 5)
        unsharp_y = effect_settings.get('unsharp_y', 5)
        unsharp_amount = effect_settings.get('unsharp_amount', 0.4)

        # ===== FIX 2: chuẩn hóa input chính =====
        if scale_x == 1.0 and scale_y == 1.0 and video_x == 0 and video_y == 0:
            chain_parts = [
                f"fps={video_fps}",
                f"setpts=PTS-STARTPTS",
                f"scale={canvas_width}:{canvas_height}:force_original_aspect_ratio=decrease",
                f"pad={canvas_width}:{canvas_height}:(ow-iw)/2:(oh-ih)/2:black",
                f"setsar=1",
            ]
            if color_grading_enable:
                chain_parts.append(f"eq=contrast={contrast}:saturation={saturation}:brightness={brightness}")
                chain_parts.append(f"hue=h={hue_shift}")
            if unsharp_enable:
                chain_parts.append(f"unsharp={unsharp_x}:{unsharp_y}:{unsharp_amount}")
            chain_parts.append("format=yuv420p")

            filter_parts = [
                f"[0:v]{','.join(chain_parts)}[v0]"
            ]
        else:
            # ===== PIPELINE: cover + scale + crop + offset =====
            base_filter = build_filter_safe(
                input_video=input_video,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                video_fps=video_fps,
                scale_x=scale_x,
                scale_y=scale_y,
                video_x=video_x,
                video_y=video_y
            )

            # remove [v0] cuối để nối thêm filter
            base_filter = base_filter.rstrip('[v0]')

            if not base_filter.endswith(','):
                base_filter += ','

            extra_filters = []
            if color_grading_enable:
                extra_filters.append(f"eq=contrast={contrast}:saturation={saturation}:brightness={brightness}")
                extra_filters.append(f"hue=h={hue_shift}")
            if unsharp_enable:
                extra_filters.append(f"unsharp={unsharp_x}:{unsharp_y}:{unsharp_amount}")
            extra_filters.append("format=yuv420p")

            filter_parts = [
                f"{base_filter}{','.join(extra_filters)}[v0]"
            ]

            print("\n===== FILTER PARTS =====\n")
            print(filter_parts)
            print("\n=========================\n")

        current_video = 'v0'

        for i, overlay in enumerate(active_overlays, 1):
            w = max(1, int(overlay.get('width', 200)))
            h = max(1, int(overlay.get('height', 200)))

            x, y = overlay.get('x', 0), overlay.get('y', 0)
            start, end = overlay.get('start', 0.0), overlay.get('end', 0.0)
            opacity = overlay.get('opacity', 100.0)

            duration = (end - start) if end > 0 and end <= actual_duration else (actual_duration - start)
            if start >= actual_duration or duration <= 0:
                continue

            alpha = min(1.0, max(0.0001, opacity / 100.0))

            # ===== FIX 3: normalize overlay fps + pts =====
            if opacity < 100.0:

                filter_parts.append(
                    f'[{i}:v]'
                    f'fps={video_fps},'
                    f'setpts=PTS-STARTPTS,'
                    f'scale={w}:{h},'
                    f'format=rgba,'
                    f'colorchannelmixer=aa={alpha},'
                    f'trim=duration={duration}'
                    f'[ov{i}]'
                )
            else:
                filter_parts.append(
                    f'[{i}:v]'
                    f'fps={video_fps},'
                    f'setpts=PTS-STARTPTS,'
                    f'scale={w}:{h},'
                    f'format=yuv420p,'
                    f'trim=duration={duration}'
                    f'[ov{i}]'
                )

            filter_parts.append(
                f'[{current_video}][ov{i}]'
                f'overlay={x}:{y}:'
                f"enable='between(t,{start},{start+duration})':"
                f'eof_action=pass'
                f'[vtmp{i}]'
            )

            # 🔥 FIX CHUẨN: tách overlay và format
            filter_parts.append(
                f'[vtmp{i}]format=yuv420p[v{i}]'
            )

            current_video = f'v{i}'

        # Post-processing: speed + delay (single-pass)
        post_video_filters = []
        post_audio_filters = []

        speed_value = custom_effect_settings.get('speed_value', 1.0)
        speed_enable = custom_effect_settings.get('speed_enable', False)
        delay_frame_enable = custom_effect_settings.get('delay_frame_enable', False)
        delay_frame_count = custom_effect_settings.get('delay_frame_count', 0)
        delay_audio_seconds = custom_effect_settings.get('delay_audio_seconds', 0.0)

        if delay_frame_enable and delay_frame_count > 0:
            first_frame_sec = delay_frame_count / 30
            post_video_filters.append(f"tpad=start_duration={first_frame_sec}:start_mode=clone")
            if delay_audio_seconds > 0:
                delay_ms = int(delay_audio_seconds * 1000)
                post_audio_filters.append(f"adelay={delay_ms}|{delay_ms}")
            log(f"   [*] Delay: {delay_frame_count} frames, {delay_audio_seconds}s audio")

        if speed_enable and speed_value != 1.0:
            post_video_filters.append(f"setpts=PTS/{speed_value}")
            post_audio_filters.append(f"atempo={speed_value}")
            log(f"   [*] Speed: {speed_value}x")

        if post_video_filters:
            filter_parts.append(
                f"[{current_video}]{','.join(post_video_filters)}[vfinal]"
            )
            current_video = 'vfinal'

        _has_audio = has_audio_stream(input_video)
        if post_audio_filters and _has_audio:
            filter_parts.append(
                f"[0:a]{','.join(post_audio_filters)}[afinal]"
            )

        filter_complex = ';'.join(filter_parts)

        print("\n===== FILTER COMPLEX =====\n")
        print(filter_complex)
        print("\n=========================\n")

        _preset = preset or "p2"
        _maxrate = maxrate or target_bitrate
        _bufsize = bufsize or target_bitrate


        # FFMPEG CMD HOÀN THIỆN
        cmd.extend([
            '-t', str(actual_duration),
            '-map_metadata', '-1',
            '-map_chapters', '-1',
            '-metadata', 'title=',
            '-metadata', 'comment=',
            '-metadata', 'encoder=',
            '-filter_complex', filter_complex,
            '-map', f'[{current_video}]',
        ])
        if post_audio_filters and _has_audio:
            cmd.extend(['-map', '[afinal]'])
        else:
            cmd.extend(['-map', '0:a?'])
        cmd.extend([
            '-fps_mode', 'cfr',
            '-r', str(video_fps),
            '-c:v', 'h264_nvenc',
            '-preset', _preset,
            '-rc', 'vbr',
            '-b:v', target_bitrate,
            '-maxrate', _maxrate,
            '-bufsize', _bufsize,
            '-g', '60',
            '-profile:v', 'high',
            '-c:a', 'aac',
            '-b:a', f'{audio_bitrate}k',
            '-ar', str(sample_rate),
            '-movflags', '+faststart',
            temp_output
        ])

        print(f"="*50)
        print(f"DEBUG CMD: {cmd}")
        print(f"="*50)

        ok, err = run_ffmpeg(cmd, temp_output, timeout=ffmpeg_timeout, logger=logger)
        if not ok:
            return (False, None)

        return (True, temp_output)

    except Exception as e:
        log(f"   [X] Lỗi: {str(e)}")
        return (False, None)



class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class ProcessorThread(QThread):

    progress = pyqtSignal(int, int, str)

    line = pyqtSignal(str)

    finished = pyqtSignal(bool, str)



    def __init__(self, source_dir: str, export_dir: str, max_duration: int, target_bitrate: str,
                 overlay_settings: list, video_fps: str = "30", sample_rate: str = "48000",
                 audio_bitrate: str = "128", preset: str = "p2", maxrate: str = None,
                 bufsize: str = None, canvas_width: int = 1080, canvas_height: int = 1920,
                 scale_x: float = 1.0, scale_y: float = 1.0, video_x: int = 0, video_y: int = 0,
                 ffmpeg_timeout: int = 120, effect_settings: dict = None,
                 custom_effect_settings: dict = None):

        super().__init__()

        self.source_dir = source_dir

        self.export_dir = export_dir

        self.max_duration = max_duration

        self.target_bitrate = target_bitrate

        self.overlay_settings = overlay_settings

        self.video_fps = video_fps

        self.sample_rate = sample_rate

        self.audio_bitrate = audio_bitrate

        self.preset = preset

        self.maxrate = maxrate

        self.bufsize = bufsize

        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.video_x = video_x
        self.video_y = video_y
        self.ffmpeg_timeout = ffmpeg_timeout
        self.effect_settings = effect_settings or {}
        self.custom_effect_settings = custom_effect_settings or {}

        self._running = True

        self.success_count = 0

        self.failure_count = 0



    def stop(self):

        self._running = False



    def log(self, msg: str):

        self.line.emit(msg)



    def run(self):
        import random

        try:

            ffmpeg_path = find_ffmpeg_path()

            if not ffmpeg_path:

                self.finished.emit(False, "Không tìm thấy FFmpeg")

                return



            if not os.path.exists(self.source_dir):

                self.finished.emit(False, f"Thư mục nguồn không tồn tại: {self.source_dir}")

                return



            videos = get_video_files_recursive(self.source_dir)

            total = len(videos)

            if total == 0:

                self.finished.emit(False, "Không tìm thấy file video trong thư mục nguồn")

                return



            self.log(f"📁 Tìm thấy {total} video. Bắt đầu xử lý...")

            start_time = datetime.now()



            for idx, (video_path, rel) in enumerate(videos, 1):

                if not self._running:

                    self.finished.emit(False, "Đã dừng bởi người dùng")

                    return



                filename = os.path.basename(video_path)

                name_no_ext = os.path.splitext(filename)[0]

                

                # Preserve folder structure from input

                # rel is like: phone\account\video.mp4

                # Convert to: export_dir\phone\account\video.mp4

                rel_without_ext = os.path.splitext(rel)[0]

                out_path = os.path.join(self.export_dir, rel_without_ext + ".mp4")



                self.progress.emit(idx, total, f"➡️ {rel}")



                # Create temp directory for this video

                import uuid

                video_temp_dir = os.path.join(os.getcwd(), 'temp_video', uuid.uuid4().hex[:8])

                os.makedirs(video_temp_dir, exist_ok=True)

                

                # Copy input video to temp directory (to avoid issues with special characters in path)

                temp_input_video = os.path.join(video_temp_dir, 'input_video.mp4')

                

                try:

                    # Copy to temp first (to handle special characters in filename/path)

                    shutil.copy2(video_path, temp_input_video)

                    

                    # Get duration from temp video

                    duration = get_video_duration(ffmpeg_path, temp_input_video)

                    

                    # Determine actual duration to use

                    if duration < self.max_duration:

                        actual_duration = duration

                        self.log(f"   📏 Video Input Duration: {duration:.1f}s (ngắn hơn max, giữ nguyên)")

                    else:

                        actual_duration = self.max_duration

                        self.log(f"   📏 Video Input Duration: {duration:.1f}s (sẽ cắt tới {actual_duration}s)")

                    

                    # Ensure output directory

                    out_dir = os.path.dirname(out_path)

                    if out_dir and not os.path.exists(out_dir):

                        os.makedirs(out_dir, exist_ok=True)



                    # Randomize custom effect values per video
                    custom_fx = dict(self.custom_effect_settings)
                    if custom_fx.get('speed_enable', False):
                        speed_min = custom_fx.get('speed_min', 1.0)
                        speed_max = custom_fx.get('speed_max', 1.0)
                        custom_fx['speed_value'] = round(random.uniform(speed_min, speed_max), 2)
                    else:
                        custom_fx['speed_value'] = 1.0

                    if custom_fx.get('delay_frame_enable', False):
                        frame_min = custom_fx.get('delay_frame_min', 1)
                        frame_max = custom_fx.get('delay_frame_max', 5)
                        custom_fx['delay_frame_count'] = random.randint(frame_min, frame_max)
                        audio_min = custom_fx.get('delay_audio_min', 0.0)
                        audio_max = custom_fx.get('delay_audio_max', 0.0)
                        decimals = custom_fx.get('delay_audio_decimals', 3)
                        custom_fx['delay_audio_seconds'] = round(random.uniform(audio_min, audio_max), decimals)
                    else:
                        custom_fx['delay_frame_count'] = 0
                        custom_fx['delay_audio_seconds'] = 0.0

                    self._current_custom_fx = custom_fx

                    apply_result = apply_overlays(

                        ffmpeg_path=ffmpeg_path,

                        input_video=temp_input_video,

                        output_path=out_path,

                        overlay_settings=self.overlay_settings,

                        target_bitrate=self.target_bitrate,

                        max_duration=self.max_duration,

                        input_video_duration=duration,

                        video_fps=self.video_fps,

                        sample_rate=self.sample_rate,

                        audio_bitrate=self.audio_bitrate,

                        preset=self.preset,

                        maxrate=self.maxrate,

                        bufsize=self.bufsize,

                        canvas_width=self.canvas_width,

                        canvas_height=self.canvas_height,
                        scale_x=self.scale_x,
                        scale_y=self.scale_y,
                        video_x=self.video_x,
                        video_y=self.video_y,
                        ffmpeg_timeout=self.ffmpeg_timeout,
                        logger=self.log,
                        effect_settings=self.effect_settings,
                        custom_effect_settings=self._current_custom_fx
                    )



                    # Unpack the result

                    ok = apply_result[0]

                    temp_file = apply_result[1]

                    temp_dir = os.path.join(os.getcwd(), 'temp_video')

                    # FINAL STEP: Copy final temp file to OUTPUT folder (only once!)

                    if ok and temp_file and os.path.exists(temp_file):

                        # Copy to output path

                        shutil.copy2(temp_file, out_path)

                        self.log(f"   📦 Đã copy output tới: {out_path}")



                    # Cleanup entire temp directory after processing is complete

                    try:

                        if os.path.exists(temp_dir):

                            shutil.rmtree(temp_dir, ignore_errors=True)

                        # Cleanup video temp directory (input video copy)

                        if os.path.exists(video_temp_dir):

                            shutil.rmtree(video_temp_dir, ignore_errors=True)

                    except:

                        pass



                    if ok and os.path.exists(out_path):

                        final_duration = get_video_duration(ffmpeg_path, out_path)

                        self.log(f"   ✅ Hoàn thành: {final_duration:.1f}s\n")

                        time.sleep(2)

                        self.success_count += 1

                    else:

                        self.log(f"   ❌ Thất bại")

                        self.failure_count += 1



                except Exception as e:

                    self.log(f"   ❌ Lỗi: {str(e)}")

                    self.failure_count += 1

                    # Cleanup video temp directory on error

                    try:

                        if os.path.exists(video_temp_dir):

                            shutil.rmtree(video_temp_dir, ignore_errors=True)

                    except:

                        pass



            end_time = datetime.now()

            elapsed = (end_time - start_time).total_seconds()

            single_video_time = round(elapsed / total, 2)

            

            self.log("")

            self.log("=" * 40)

            self.log("📊 BÁO CÁO TỔNG KẾT:")

            self.log("=" * 40)

            self.log(f"✅ Thành công: {self.success_count}")

            self.log(f"❌ Thất bại: {self.failure_count}")

            self.log(f"📊 Tổng số video: {total}")

            self.log(f"⏱️ Thời gian: {int(elapsed)}s")

            self.log(f"🏆 Thời gian TB mỗi video: {single_video_time}s")

            self.log("=" * 40)

            

            self.finished.emit(True, "Xử lý xong")

            

        except Exception as e:

            self.finished.emit(False, f"Lỗi: {str(e)}")





class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Video Overlay 2026 - V1.6.1 - By Nguyên Phạm")

        self.setWindowIcon(QIcon("movie.ico"))

        self.setGeometry(100, 100, 800, 750)

        self.thread = None



        self.settings = load_settings()

        self.init_ui()

        self.load_defaults_to_ui()



    def init_ui(self):

        central = QWidget()

        self.setCentralWidget(central)

        layout = QVBoxLayout(central)



        # Notice

        notice_label = QLabel("<b>📢 Video Overlay 2026 - V1.6.1:</b>\n"

                            "<li>• Add: Speed Video, Delay Frame, Delay Audio - Lách Tiktok HQ</li> \n"

                            "<li>• Thêm Zoom & Crop Video Short</li>\n"

                            "<li>• Sử Dụng Tối Đa 8 Overlay</li>\n"

                            )

        notice_label.setStyleSheet("""

            QLabel {

                background-color: #e3f2fd;

                border: 1px solid #90caf9;

                border-radius: 6px;

                padding: 10px;

                color: #1565c0;

                font-size: 12px;

            }

        """)

        layout.addWidget(notice_label)



        # Create Tab Widget

        self.tab_widget = QTabWidget()

        layout.addWidget(self.tab_widget)



        # ============= TAB 1: General Settings =============

        general_tab = QWidget()

        general_layout = QVBoxLayout(general_tab)

        general_layout.setSpacing(10)



        # Input folder

        row1 = QHBoxLayout()

        row1.addWidget(QLabel("Input:"))

        self.input_edit = QLineEdit()

        row1.addWidget(self.input_edit)

        btn_in = QPushButton("Choose")

        btn_in.clicked.connect(self.choose_input)

        row1.addWidget(btn_in)

        general_layout.addLayout(row1)



        # Output folder

        row2 = QHBoxLayout()

        row2.addWidget(QLabel("Output:"))

        self.output_edit = QLineEdit()

        row2.addWidget(self.output_edit)

        btn_out = QPushButton("Choose")

        btn_out.clicked.connect(self.choose_output)

        row2.addWidget(btn_out)

        general_layout.addLayout(row2)



        # Max Duration

        row3 = QHBoxLayout()

        row3.addWidget(QLabel("Thời Lượng Video (s):"))

        self.max_duration_spin = NoScrollSpinBox()

        self.max_duration_spin.setRange(1, 600)

        self.max_duration_spin.setValue(50)

        self.max_duration_spin.setToolTip("Video ngắn hơn sẽ giữ nguyên, video dài hơn sẽ bị cắt")

        row3.addWidget(self.max_duration_spin)

        row3.addStretch()

        general_layout.addLayout(row3)



        # Encoder (always NVENC, hidden but kept for compat)
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["nvenc"])
        self.encoder_combo.setCurrentIndex(0)
        self.encoder_combo.setVisible(False)

        # Bitrate row: Bitrate | Maxrate | Bufsize
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Bitrate (M):"))
        self.bitrate_edit = QLineEdit("4")
        self.bitrate_edit.setMaximumWidth(80)
        row4.addWidget(self.bitrate_edit)

        row4.addSpacing(10)
        row4.addWidget(QLabel("Maxrate (M):"))
        self.maxrate_edit = QLineEdit("5")
        self.maxrate_edit.setMaximumWidth(80)
        row4.addWidget(self.maxrate_edit)

        row4.addSpacing(10)
        row4.addWidget(QLabel("Bufsize (M):"))
        self.bufsize_edit = QLineEdit("8")
        self.bufsize_edit.setMaximumWidth(80)
        row4.addWidget(self.bufsize_edit)
        row4.addStretch()
        general_layout.addLayout(row4)

        # Preset + FPS row
        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["p1", "p2", "p3", "p4", "p5", "p6", "p7"])
        self.preset_combo.setCurrentText("p2")
        self.preset_combo.setToolTip("Preset NVENC: p1=nhanh nhat, p7=chat luong cao nhat")
        row5.addWidget(self.preset_combo)

        row5.addSpacing(10)
        row5.addWidget(QLabel("FPS Video:"))
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["23.98", "25", "29.97", "30", "50", "59.94", "60"])
        self.fps_combo.setCurrentText("30")
        self.fps_combo.setToolTip("Đặt FPS cho video output")
        row5.addWidget(self.fps_combo)
        row5.addStretch()
        general_layout.addLayout(row5)

        # Sample Rate + Audio Bitrate row
        row6 = QHBoxLayout()
        row6.addWidget(QLabel("Sample Rate:"))
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["44100", "48000"])
        self.sample_rate_combo.setCurrentText("48000")
        self.sample_rate_combo.setToolTip("Tần số mẫu âm thanh: 44100 (CD) hoặc 48000 (Professional)")
        row6.addWidget(self.sample_rate_combo)

        row6.addSpacing(10)
        row6.addWidget(QLabel("Audio Bitrate:"))
        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(["128", "256", "320"])
        self.audio_bitrate_combo.setCurrentText("128")
        self.audio_bitrate_combo.setToolTip("Bitrate âm thanh: 128k, 256k, hoặc 320k")
        row6.addWidget(self.audio_bitrate_combo)
        row6.addStretch()
        general_layout.addLayout(row6)

        # Timeout
        row_timeout = QHBoxLayout()
        row_timeout.addWidget(QLabel("FFmpeg Timeout (s):"))
        self.timeout_spin = NoScrollSpinBox()
        self.timeout_spin.setRange(10, 1800)
        self.timeout_spin.setValue(120)
        self.timeout_spin.setMaximumWidth(80)
        self.timeout_spin.setToolTip("Thời gian chờ tối đa cho mỗi lệnh ffmpeg (10-1800 giây)")
        row_timeout.addWidget(self.timeout_spin)
        row_timeout.addStretch()
        general_layout.addLayout(row_timeout)

        # Canvas Size row
        row7 = QHBoxLayout()
        row7.addWidget(QLabel("Canvas W:"))
        self.canvas_width_spin = NoScrollSpinBox()
        self.canvas_width_spin.setRange(100, 4000)
        self.canvas_width_spin.setValue(1080)
        self.canvas_width_spin.setMaximumWidth(80)
        self.canvas_width_spin.setToolTip("Chiều rộng canvas đen (px)")
        row7.addWidget(self.canvas_width_spin)

        row7.addSpacing(10)
        row7.addWidget(QLabel("Canvas H:"))
        self.canvas_height_spin = NoScrollSpinBox()
        self.canvas_height_spin.setRange(100, 4000)
        self.canvas_height_spin.setValue(1920)
        self.canvas_height_spin.setMaximumWidth(80)
        self.canvas_height_spin.setToolTip("Chiều cao canvas đen (px)")
        row7.addWidget(self.canvas_height_spin)
        row7.addStretch()
        general_layout.addLayout(row7)

        # Scale + Position row
        row_scale = QHBoxLayout()
        row_scale.addWidget(QLabel("Scale X:"))
        self.scale_x_spin = NoScrollDoubleSpinBox()
        self.scale_x_spin.setRange(0.1, 10.0)
        self.scale_x_spin.setSingleStep(0.1)
        self.scale_x_spin.setValue(1.0)
        self.scale_x_spin.setMaximumWidth(70)
        self.scale_x_spin.setToolTip("Phóng to/thu nhỏ chiều ngang video (1.0 = bình thường)")
        row_scale.addWidget(self.scale_x_spin)

        row_scale.addSpacing(8)
        row_scale.addWidget(QLabel("Scale Y:"))
        self.scale_y_spin = NoScrollDoubleSpinBox()
        self.scale_y_spin.setRange(0.1, 10.0)
        self.scale_y_spin.setSingleStep(0.1)
        self.scale_y_spin.setValue(1.0)
        self.scale_y_spin.setMaximumWidth(70)
        self.scale_y_spin.setToolTip("Phóng to/thu nhỏ chiều dọc video (1.0 = bình thường)")
        row_scale.addWidget(self.scale_y_spin)

        row_scale.addSpacing(8)
        row_scale.addWidget(QLabel("Video X:"))
        self.video_x_spin = NoScrollSpinBox()
        self.video_x_spin.setRange(-5000, 5000)
        self.video_x_spin.setValue(0)
        self.video_x_spin.setMaximumWidth(70)
        self.video_x_spin.setToolTip("Dịch chuyển video sang ngang (pixel)")
        row_scale.addWidget(self.video_x_spin)

        row_scale.addSpacing(8)
        row_scale.addWidget(QLabel("Video Y:"))
        self.video_y_spin = NoScrollSpinBox()
        self.video_y_spin.setRange(-5000, 5000)
        self.video_y_spin.setValue(0)
        self.video_y_spin.setMaximumWidth(70)
        self.video_y_spin.setToolTip("Dịch chuyển video theo chiều dọc (pixel)")
        row_scale.addWidget(self.video_y_spin)
        row_scale.addStretch()
        general_layout.addLayout(row_scale)

        general_layout.addStretch()
        self.tab_widget.addTab(general_tab, "General Setting")



        # ============= TAB 2: Overlay Settings =============

        overlay_tab = QWidget()

        overlay_layout = QVBoxLayout(overlay_tab)

        overlay_layout.setSpacing(5)



        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)



        scroll_content = QWidget()

        scroll_content_layout = QVBoxLayout(scroll_content)

        scroll_content_layout.setSpacing(10)

        scroll_content_layout.setContentsMargins(5, 5, 5, 5)



        # Create 5 overlay controls
        self.overlay_controls = []
        for i in range(8):
            overlay_frame = QFrame()
            overlay_frame.setFrameShape(QFrame.Shape.Box)
            overlay_frame_layout = QVBoxLayout(overlay_frame)
            overlay_frame_layout.setSpacing(4)
            overlay_frame_layout.setContentsMargins(12, 8, 12, 8)

            # === HEADER ROW (always visible): Enable + Name + Type + Z-Index + Toggle ===
            row_header = QHBoxLayout()
            row_header.setSpacing(6)

            enable_chk = QCheckBox(f"Overlay {i+1}")
            enable_chk.setStyleSheet("font-weight: bold;")
            enable_chk.setMaximumWidth(120)
            row_header.addWidget(enable_chk)

            name_edit = QLineEdit()
            name_edit.setPlaceholderText("Name...")
            name_edit.setMinimumWidth(280)
            row_header.addWidget(name_edit)

            row_header.addWidget(QLabel("Type:"))
            type_combo = QComboBox()
            type_combo.addItems(["Video MP4", "Video MOV", "Image PNG", "Random MP4 Folder"])
            type_combo.setMaximumWidth(160)
            row_header.addWidget(type_combo)

            row_header.addWidget(QLabel("Z:"))
            zindex_spin = NoScrollSpinBox()
            zindex_spin.setRange(1, 10)
            zindex_spin.setValue(i + 1)
            zindex_spin.setMaximumWidth(50)
            row_header.addWidget(zindex_spin)

            toggle_btn = QPushButton("▼")
            toggle_btn.setMaximumWidth(30)
            toggle_btn.setStyleSheet("font-size: 10px; padding: 2px 4px; min-width: 24px;")
            row_header.addWidget(toggle_btn)

            row_header.addStretch()
            overlay_frame_layout.addLayout(row_header)

            # === DETAIL WIDGET (collapsible) ===
            detail_widget = QWidget()
            detail_layout = QVBoxLayout(detail_widget)
            detail_layout.setSpacing(6)
            detail_layout.setContentsMargins(0, 4, 0, 4)

            # File path
            row_file = QHBoxLayout()
            row_file.addWidget(QLabel("File:"))
            file_edit = QLineEdit()
            file_edit.setPlaceholderText("Đường dẫn tới file overlay")
            row_file.addWidget(file_edit)
            choose_btn = QPushButton("Choose")
            choose_btn.clicked.connect(lambda checked, idx=i: self.choose_overlay_file(idx))
            row_file.addWidget(choose_btn)
            detail_layout.addLayout(row_file)

            # Folder path for Random MP4
            row_folder = QHBoxLayout()
            row_folder.addWidget(QLabel("Folder:"))
            folder_edit = QLineEdit()
            folder_edit.setPlaceholderText("Đường dẫn thư mục chứa MP4 (cho Random MP4 Folder)")
            row_folder.addWidget(folder_edit)
            folder_btn = QPushButton("Choose")
            folder_btn.clicked.connect(lambda checked, idx=i: self.choose_overlay_folder(idx))
            row_folder.addWidget(folder_btn)
            detail_layout.addLayout(row_folder)

            # Width, Height, X, Y
            row_size = QHBoxLayout()
            row_size.addWidget(QLabel("Width:"))
            width_spin = NoScrollSpinBox()
            width_spin.setRange(1, 4000)
            width_spin.setValue(200)
            width_spin.setMaximumWidth(70)
            row_size.addWidget(width_spin)
            row_size.addWidget(QLabel("Height:"))
            height_spin = NoScrollSpinBox()
            height_spin.setRange(1, 4000)
            height_spin.setValue(200)
            height_spin.setMaximumWidth(70)
            row_size.addWidget(height_spin)
            row_size.addWidget(QLabel("X:"))
            x_spin = NoScrollSpinBox()
            x_spin.setRange(-2000, 4000)
            x_spin.setValue(0)
            x_spin.setMaximumWidth(70)
            row_size.addWidget(x_spin)
            row_size.addWidget(QLabel("Y:"))
            y_spin = NoScrollSpinBox()
            y_spin.setRange(-2000, 4000)
            y_spin.setValue(0)
            y_spin.setMaximumWidth(70)
            row_size.addWidget(y_spin)
            row_size.addStretch()
            detail_layout.addLayout(row_size)

            # Start Time, End Time
            row_time = QHBoxLayout()
            row_time.addWidget(QLabel("Start (s):"))
            start_spin = NoScrollDoubleSpinBox()
            start_spin.setRange(0.0, 600.0)
            start_spin.setValue(0.0)
            start_spin.setDecimals(1)
            start_spin.setMaximumWidth(80)
            start_spin.setToolTip("Thời gian bắt đầu hiển thị overlay (giây)")
            row_time.addWidget(start_spin)
            row_time.addWidget(QLabel("End (s):"))
            end_spin = NoScrollDoubleSpinBox()
            end_spin.setRange(0.0, 600.0)
            end_spin.setValue(0.0)
            end_spin.setDecimals(1)
            end_spin.setMaximumWidth(80)
            end_spin.setToolTip("Thời gian kết thúc overlay (0 = đến hết video)")
            row_time.addWidget(end_spin)
            row_time.addStretch()
            detail_layout.addLayout(row_time)

            # Opacity
            row_opacity = QHBoxLayout()
            row_opacity.addWidget(QLabel("Opacity (%):"))
            opacity_spin = NoScrollDoubleSpinBox()
            opacity_spin.setRange(0.01, 100.0)
            opacity_spin.setValue(100.0)
            opacity_spin.setDecimals(2)
            opacity_spin.setMaximumWidth(80)
            opacity_spin.setToolTip("Độ mờ: 100% = đầy đủ, 0.01% = gần trong suốt")
            row_opacity.addWidget(opacity_spin)
            row_opacity.addStretch()
            detail_layout.addLayout(row_opacity)

            detail_widget.setVisible(False)
            overlay_frame_layout.addWidget(detail_widget)

            toggle_btn.clicked.connect(lambda checked, dw=detail_widget, tb=toggle_btn: self._toggle_overlay_detail(dw, tb))

            scroll_content_layout.addWidget(overlay_frame)

            self.overlay_controls.append({
                'enable': enable_chk,
                'name': name_edit,
                'type': type_combo,
                'zindex': zindex_spin,
                'file': file_edit,
                'folder': folder_edit,
                'width': width_spin,
                'height': height_spin,
                'x': x_spin,
                'y': y_spin,
                'start': start_spin,
                'end': end_spin,
                'opacity': opacity_spin,
                'detail_widget': detail_widget,
                'toggle_btn': toggle_btn,
            })



        scroll_content_layout.addStretch()

        scroll_area.setWidget(scroll_content)

        overlay_layout.addWidget(scroll_area)



        self.tab_widget.addTab(overlay_tab, "Overlay Setting")




        # ============= TAB 5: Effect Setting =============

        effect_tab = QWidget()

        effect_layout = QVBoxLayout(effect_tab)

        effect_layout.setSpacing(10)

        effect_layout.setContentsMargins(15, 15, 15, 15)



        # Color Grading Frame
        color_frame = QFrame()
        color_frame.setFrameShape(QFrame.Shape.Box)
        color_frame_layout = QVBoxLayout(color_frame)
        color_frame_layout.setSpacing(10)

        color_header = QHBoxLayout()
        self.color_grading_chk = QCheckBox("🎨 Random Color Grading")
        self.color_grading_chk.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.color_grading_chk.setToolTip("Bật/Tắt Random Color Grading cho video")
        color_header.addWidget(self.color_grading_chk)
        color_header.addStretch()
        color_frame_layout.addLayout(color_header)

        contrast_row = QHBoxLayout()
        contrast_row.addWidget(QLabel("Contrast Random:"))
        self.contrast_min_spin = NoScrollDoubleSpinBox()
        self.contrast_min_spin.setRange(0.50, 2.00)
        self.contrast_min_spin.setValue(1.02)
        self.contrast_min_spin.setSingleStep(0.01)
        self.contrast_min_spin.setDecimals(3)
        contrast_row.addWidget(self.contrast_min_spin)
        contrast_row.addWidget(QLabel("~"))
        self.contrast_max_spin = NoScrollDoubleSpinBox()
        self.contrast_max_spin.setRange(0.50, 2.00)
        self.contrast_max_spin.setValue(1.06)
        self.contrast_max_spin.setSingleStep(0.01)
        self.contrast_max_spin.setDecimals(3)
        contrast_row.addWidget(self.contrast_max_spin)
        contrast_row.addStretch()
        color_frame_layout.addLayout(contrast_row)

        saturation_row = QHBoxLayout()
        saturation_row.addWidget(QLabel("Saturation Random:"))
        self.saturation_min_spin = NoScrollDoubleSpinBox()
        self.saturation_min_spin.setRange(0.50, 2.00)
        self.saturation_min_spin.setValue(1.04)
        self.saturation_min_spin.setSingleStep(0.01)
        self.saturation_min_spin.setDecimals(3)
        saturation_row.addWidget(self.saturation_min_spin)
        saturation_row.addWidget(QLabel("~"))
        self.saturation_max_spin = NoScrollDoubleSpinBox()
        self.saturation_max_spin.setRange(0.50, 2.00)
        self.saturation_max_spin.setValue(1.10)
        self.saturation_max_spin.setSingleStep(0.01)
        self.saturation_max_spin.setDecimals(3)
        saturation_row.addWidget(self.saturation_max_spin)
        saturation_row.addStretch()
        color_frame_layout.addLayout(saturation_row)

        brightness_row = QHBoxLayout()
        brightness_row.addWidget(QLabel("Brightness Random:"))
        self.brightness_min_spin = NoScrollDoubleSpinBox()
        self.brightness_min_spin.setRange(-1.0, 1.0)
        self.brightness_min_spin.setValue(-0.01)
        self.brightness_min_spin.setSingleStep(0.001)
        self.brightness_min_spin.setDecimals(3)
        brightness_row.addWidget(self.brightness_min_spin)
        brightness_row.addWidget(QLabel("~"))
        self.brightness_max_spin = NoScrollDoubleSpinBox()
        self.brightness_max_spin.setRange(-1.0, 1.0)
        self.brightness_max_spin.setValue(0.005)
        self.brightness_max_spin.setSingleStep(0.001)
        self.brightness_max_spin.setDecimals(3)
        brightness_row.addWidget(self.brightness_max_spin)
        brightness_row.addStretch()
        color_frame_layout.addLayout(brightness_row)

        hue_row = QHBoxLayout()
        hue_row.addWidget(QLabel("Hue Shift:"))
        self.hue_min_spin = NoScrollSpinBox()
        self.hue_min_spin.setRange(0, 360)
        self.hue_min_spin.setValue(5)
        hue_row.addWidget(self.hue_min_spin)
        hue_row.addWidget(QLabel("~"))
        self.hue_max_spin = NoScrollSpinBox()
        self.hue_max_spin.setRange(0, 360)
        self.hue_max_spin.setValue(10)
        hue_row.addWidget(self.hue_max_spin)
        hue_row.addStretch()
        color_frame_layout.addLayout(hue_row)

        effect_layout.addWidget(color_frame)

        # Unsharp Frame
        unsharp_frame = QFrame()
        unsharp_frame.setFrameShape(QFrame.Shape.Box)
        unsharp_frame_layout = QVBoxLayout(unsharp_frame)
        unsharp_frame_layout.setSpacing(10)

        unsharp_header = QHBoxLayout()
        self.unsharp_chk = QCheckBox("🔍 Unsharp Video")
        self.unsharp_chk.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.unsharp_chk.setToolTip("Bật/Tắt Unsharp Video")
        unsharp_header.addWidget(self.unsharp_chk)
        unsharp_header.addStretch()
        unsharp_frame_layout.addLayout(unsharp_header)

        unsharp_row = QHBoxLayout()
        unsharp_row.addWidget(QLabel("Unsharp (lx:ly:amount):"))
        self.unsharp_x_spin = NoScrollSpinBox()
        self.unsharp_x_spin.setRange(1, 99)
        self.unsharp_x_spin.setValue(5)
        unsharp_row.addWidget(self.unsharp_x_spin)
        self.unsharp_y_spin = NoScrollSpinBox()
        self.unsharp_y_spin.setRange(1, 99)
        self.unsharp_y_spin.setValue(5)
        unsharp_row.addWidget(self.unsharp_y_spin)
        self.unsharp_amount_spin = NoScrollDoubleSpinBox()
        self.unsharp_amount_spin.setRange(0.0, 5.0)
        self.unsharp_amount_spin.setValue(0.4)
        self.unsharp_amount_spin.setSingleStep(0.1)
        self.unsharp_amount_spin.setDecimals(1)
        unsharp_row.addWidget(self.unsharp_amount_spin)
        unsharp_row.addStretch()
        unsharp_frame_layout.addLayout(unsharp_row)

        effect_layout.addWidget(unsharp_frame)

        effect_layout.addStretch()

        self.tab_widget.addTab(effect_tab, "Color Effect")


        # ============= TAB: Custom Effect =============

        custom_effect_tab = QWidget()
        custom_effect_layout = QVBoxLayout(custom_effect_tab)
        custom_effect_layout.setSpacing(10)
        custom_effect_layout.setContentsMargins(15, 15, 15, 15)

        # Speed Video Frame
        speed_frame = QFrame()
        speed_frame.setFrameShape(QFrame.Shape.Box)
        speed_frame_layout = QVBoxLayout(speed_frame)
        speed_frame_layout.setSpacing(10)

        self.custom_speed_chk = QCheckBox("🎬 Speed Video")
        self.custom_speed_chk.setStyleSheet("font-weight: bold; font-size: 14px;")
        speed_frame_layout.addWidget(self.custom_speed_chk)

        row_speed = QHBoxLayout()
        row_speed.addWidget(QLabel("Tốc độ:"))
        self.custom_speed_min_spin = NoScrollDoubleSpinBox()
        self.custom_speed_min_spin.setRange(0.50, 2.00)
        self.custom_speed_min_spin.setValue(1.0)
        self.custom_speed_min_spin.setSingleStep(0.01)
        self.custom_speed_min_spin.setDecimals(2)
        self.custom_speed_min_spin.setMaximumWidth(80)
        self.custom_speed_min_spin.setEnabled(False)
        row_speed.addWidget(self.custom_speed_min_spin)
        row_speed.addWidget(QLabel("~"))
        self.custom_speed_max_spin = NoScrollDoubleSpinBox()
        self.custom_speed_max_spin.setRange(0.50, 2.00)
        self.custom_speed_max_spin.setValue(1.0)
        self.custom_speed_max_spin.setSingleStep(0.01)
        self.custom_speed_max_spin.setDecimals(2)
        self.custom_speed_max_spin.setMaximumWidth(80)
        self.custom_speed_max_spin.setEnabled(False)
        row_speed.addWidget(self.custom_speed_max_spin)
        row_speed.addWidget(QLabel("(1.0 = giữ nguyên)"))
        row_speed.addStretch()
        speed_frame_layout.addLayout(row_speed)

        self.custom_speed_chk.toggled.connect(self.custom_speed_min_spin.setEnabled)
        self.custom_speed_chk.toggled.connect(self.custom_speed_max_spin.setEnabled)

        custom_effect_layout.addWidget(speed_frame)

        # Delay Frame + Audio Frame
        delay_frame = QFrame()
        delay_frame.setFrameShape(QFrame.Shape.Box)
        delay_frame_layout = QVBoxLayout(delay_frame)
        delay_frame_layout.setSpacing(10)

        self.custom_delay_frame_chk = QCheckBox("⏸️ Delay Frame")
        self.custom_delay_frame_chk.setStyleSheet("font-weight: bold; font-size: 14px;")
        delay_frame_layout.addWidget(self.custom_delay_frame_chk)

        row_delay_frame = QHBoxLayout()
        row_delay_frame.addWidget(QLabel("Số Frame Delay:"))
        self.custom_delay_frame_min_spin = NoScrollSpinBox()
        self.custom_delay_frame_min_spin.setRange(1, 30)
        self.custom_delay_frame_min_spin.setValue(1)
        self.custom_delay_frame_min_spin.setMaximumWidth(80)
        self.custom_delay_frame_min_spin.setEnabled(False)
        row_delay_frame.addWidget(self.custom_delay_frame_min_spin)
        row_delay_frame.addWidget(QLabel("~"))
        self.custom_delay_frame_max_spin = NoScrollSpinBox()
        self.custom_delay_frame_max_spin.setRange(1, 30)
        self.custom_delay_frame_max_spin.setValue(5)
        self.custom_delay_frame_max_spin.setMaximumWidth(80)
        self.custom_delay_frame_max_spin.setEnabled(False)
        row_delay_frame.addWidget(self.custom_delay_frame_max_spin)
        row_delay_frame.addStretch()
        delay_frame_layout.addLayout(row_delay_frame)

        row_delay_audio = QHBoxLayout()
        row_delay_audio.addWidget(QLabel("Delay Audio (s):"))
        self.custom_delay_audio_min_spin = NoScrollDoubleSpinBox()
        self.custom_delay_audio_min_spin.setRange(0.0, 10.0)
        self.custom_delay_audio_min_spin.setValue(0.0)
        self.custom_delay_audio_min_spin.setSingleStep(0.05)
        self.custom_delay_audio_min_spin.setDecimals(3)
        self.custom_delay_audio_min_spin.setMaximumWidth(80)
        self.custom_delay_audio_min_spin.setEnabled(False)
        row_delay_audio.addWidget(self.custom_delay_audio_min_spin)
        row_delay_audio.addWidget(QLabel("~"))
        self.custom_delay_audio_max_spin = NoScrollDoubleSpinBox()
        self.custom_delay_audio_max_spin.setRange(0.0, 10.0)
        self.custom_delay_audio_max_spin.setValue(0.0)
        self.custom_delay_audio_max_spin.setSingleStep(0.05)
        self.custom_delay_audio_max_spin.setDecimals(3)
        self.custom_delay_audio_max_spin.setMaximumWidth(80)
        self.custom_delay_audio_max_spin.setEnabled(False)
        row_delay_audio.addWidget(self.custom_delay_audio_max_spin)
        row_delay_audio.addSpacing(10)
        row_delay_audio.addWidget(QLabel("Decimals:"))
        self.custom_delay_audio_decimals_spin = NoScrollSpinBox()
        self.custom_delay_audio_decimals_spin.setRange(0, 6)
        self.custom_delay_audio_decimals_spin.setValue(3)
        self.custom_delay_audio_decimals_spin.setMaximumWidth(60)
        self.custom_delay_audio_decimals_spin.setEnabled(False)
        row_delay_audio.addWidget(self.custom_delay_audio_decimals_spin)
        row_delay_audio.addStretch()
        delay_frame_layout.addLayout(row_delay_audio)

        self.custom_delay_frame_chk.toggled.connect(self.custom_delay_frame_min_spin.setEnabled)
        self.custom_delay_frame_chk.toggled.connect(self.custom_delay_frame_max_spin.setEnabled)
        self.custom_delay_frame_chk.toggled.connect(self.custom_delay_audio_min_spin.setEnabled)
        self.custom_delay_frame_chk.toggled.connect(self.custom_delay_audio_max_spin.setEnabled)
        self.custom_delay_frame_chk.toggled.connect(self.custom_delay_audio_decimals_spin.setEnabled)

        custom_effect_layout.addWidget(delay_frame)

        custom_effect_layout.addStretch()

        self.tab_widget.addTab(custom_effect_tab, "Custom Effect")


        # Buttons

        row5 = QHBoxLayout()

        self.start_btn = QPushButton("Start")

        self.start_btn.setObjectName("startBtn")

        self.start_btn.clicked.connect(self.start)

        row5.addWidget(self.start_btn)

        

        self.stop_btn = QPushButton("Stop")

        self.stop_btn.setObjectName("stopBtn")

        self.stop_btn.setEnabled(False)

        self.stop_btn.clicked.connect(self.stop)

        row5.addWidget(self.stop_btn)

        row5.addStretch()

        

        # Load/Save JSON buttons

        load_json_btn = QPushButton("Load JSON")

        load_json_btn.clicked.connect(self.load_json_settings)

        row5.addWidget(load_json_btn)

        

        save_json_btn = QPushButton("Save JSON")

        save_json_btn.clicked.connect(self.save_json_settings)

        row5.addWidget(save_json_btn)

        

        save_btn = QPushButton("Lưu Settings")

        save_btn.clicked.connect(self.save_current_settings)

        row5.addWidget(save_btn)

        

        layout.addLayout(row5)



        # Progress

        self.progress = QProgressBar()

        self.progress.setFormat("0 / 0")

        layout.addWidget(self.progress)



        # Logs

        self.logs = QTextEdit()

        self.logs.setReadOnly(True)

        layout.addWidget(self.logs)

        self.logs.setMinimumHeight(250)



        # Log controls

        logs_row = QHBoxLayout()

        clear_btn = QPushButton("Clear Logs")

        clear_btn.clicked.connect(self.clear_logs)

        logs_row.addWidget(clear_btn)

        logs_row.addStretch()

        layout.addLayout(logs_row)



    def choose_overlay_file(self, idx):

        """Choose overlay file"""

        overlay_type = self.overlay_controls[idx]['type'].currentText()

        if "PNG" in overlay_type:

            filter_str = "PNG Images (*.png)"

        elif "MOV" in overlay_type:

            filter_str = "MOV Videos (*.mov)"

        else:

            filter_str = "MP4 Videos (*.mp4);;MOV Videos (*.mov);;All Videos (*.mp4 *.mov)"



        file_path, _ = QFileDialog.getOpenFileName(self, f"Chọn file Overlay {idx+1}", "", filter_str)

        if file_path:

            self.overlay_controls[idx]['file'].setText(file_path)



    def choose_overlay_folder(self, idx):

        """Choose overlay folder for Random MP4"""

        folder_path = QFileDialog.getExistingDirectory(self, f"Chọn thư mục chứa MP4 cho Overlay {idx+1}")

        if folder_path:

            self.overlay_controls[idx]['folder'].setText(folder_path)

    def _toggle_overlay_detail(self, detail_widget, toggle_btn):
        visible = not detail_widget.isVisible()
        detail_widget.setVisible(visible)
        toggle_btn.setText("▲" if visible else "▼")

    def load_defaults_to_ui(self):

        g = self.settings.get("general_settings", {})

        self.input_edit.setText(g.get("source_dir", ""))

        self.output_edit.setText(g.get("export_dir", ""))

        self.max_duration_spin.setValue(int(g.get("max_duration", 50)))


        tb = str(g.get("target_bitrate", "4M")).replace("M", "").replace("m", "")

        self.bitrate_edit.setText(tb)

        maxrate = str(g.get("maxrate", "5M")).replace("M", "").replace("m", "")

        self.maxrate_edit.setText(maxrate)

        bufsize = str(g.get("bufsize", "8M")).replace("M", "").replace("m", "")

        self.bufsize_edit.setText(bufsize)

        preset = g.get("preset", "p2")

        preset_idx = self.preset_combo.findText(preset)

        if preset_idx >= 0:

            self.preset_combo.setCurrentIndex(preset_idx)

        else:

            self.preset_combo.setCurrentText("p2")



        # Load video FPS

        fps = g.get("video_fps", "30")

        fps_idx = self.fps_combo.findText(str(fps))

        if fps_idx >= 0:

            self.fps_combo.setCurrentIndex(fps_idx)

        else:

            self.fps_combo.setCurrentText("30")



        # Load sample rate

        sample_rate = g.get("sample_rate", "48000")

        sr_idx = self.sample_rate_combo.findText(str(sample_rate))

        if sr_idx >= 0:

            self.sample_rate_combo.setCurrentIndex(sr_idx)

        else:

            self.sample_rate_combo.setCurrentText("48000")



        # Load audio bitrate

        audio_bitrate = g.get("audio_bitrate", "128")

        ab_idx = self.audio_bitrate_combo.findText(str(audio_bitrate))

        if ab_idx >= 0:

            self.audio_bitrate_combo.setCurrentIndex(ab_idx)

        else:

            self.audio_bitrate_combo.setCurrentText("128")



        # Load canvas size

        self.canvas_width_spin.setValue(int(g.get("canvas_width", 1080)))

        self.canvas_height_spin.setValue(int(g.get("canvas_height", 1920)))



        # Load timeout
        timeout_val = int(g.get("ffmpeg_timeout", 120))
        self.timeout_spin.setValue(timeout_val)

        # Load scale + position
        self.scale_x_spin.setValue(float(g.get("scale_x", 1.0)))
        self.scale_y_spin.setValue(float(g.get("scale_y", 1.0)))
        self.video_x_spin.setValue(int(g.get("video_x", 0)))
        self.video_y_spin.setValue(int(g.get("video_y", 0)))

        # Load overlay settings - overlay_settings is at root level, not in general_settings
        overlay_list = self.settings.get("overlay_settings", [])

        for i, ov_ctrl in enumerate(self.overlay_controls):

            if i < len(overlay_list):

                ov = overlay_list[i]

                ov_ctrl['enable'].setChecked(bool(ov.get('enable', False)))

                ov_ctrl['name'].setText(ov.get('name', ''))

                ov_ctrl['file'].setText(ov.get('file', ''))

                ov_ctrl['folder'].setText(ov.get('folder', ''))

                type_text = ov.get('type', 'Video MP4')

                type_idx = ov_ctrl['type'].findText(type_text)

                if type_idx >= 0:

                    ov_ctrl['type'].setCurrentIndex(type_idx)

                ov_ctrl['zindex'].setValue(int(ov.get('zindex', i + 1)))

                ov_ctrl['width'].setValue(int(ov.get('width', 200)))

                ov_ctrl['height'].setValue(int(ov.get('height', 200)))

                ov_ctrl['x'].setValue(int(ov.get('x', 0)))

                ov_ctrl['y'].setValue(int(ov.get('y', 0)))

                ov_ctrl['start'].setValue(float(ov.get('start', 0.0)))

                ov_ctrl['end'].setValue(float(ov.get('end', 0.0)))

                ov_ctrl['opacity'].setValue(float(ov.get('opacity', 100.0)))



        # Load effect settings

        effect_settings = self.settings.get("effect_settings", {})

        self.color_grading_chk.setChecked(bool(effect_settings.get("color_grading_enable", False)))
        self.contrast_min_spin.setValue(float(effect_settings.get("contrast_min", 1.02)))
        self.contrast_max_spin.setValue(float(effect_settings.get("contrast_max", 1.06)))
        self.saturation_min_spin.setValue(float(effect_settings.get("saturation_min", 1.04)))
        self.saturation_max_spin.setValue(float(effect_settings.get("saturation_max", 1.10)))
        self.brightness_min_spin.setValue(float(effect_settings.get("brightness_min", -0.01)))
        self.brightness_max_spin.setValue(float(effect_settings.get("brightness_max", 0.005)))
        self.hue_min_spin.setValue(int(effect_settings.get("hue_min", 5)))
        self.hue_max_spin.setValue(int(effect_settings.get("hue_max", 10)))
        self.unsharp_chk.setChecked(bool(effect_settings.get("unsharp_enable", False)))
        self.unsharp_x_spin.setValue(int(effect_settings.get("unsharp_x", 5)))
        self.unsharp_y_spin.setValue(int(effect_settings.get("unsharp_y", 5)))
        self.unsharp_amount_spin.setValue(float(effect_settings.get("unsharp_amount", 0.4)))

        # Load custom effect settings
        custom_effect = self.settings.get("custom_effect_settings", {})
        self.custom_speed_chk.setChecked(bool(custom_effect.get("speed_enable", False)))
        self.custom_speed_min_spin.setValue(float(custom_effect.get("speed_min", 1.0)))
        self.custom_speed_max_spin.setValue(float(custom_effect.get("speed_max", 1.0)))
        self.custom_delay_frame_chk.setChecked(bool(custom_effect.get("delay_frame_enable", False)))
        self.custom_delay_frame_min_spin.setValue(int(custom_effect.get("delay_frame_min", 1)))
        self.custom_delay_frame_max_spin.setValue(int(custom_effect.get("delay_frame_max", 5)))
        self.custom_delay_audio_min_spin.setValue(float(custom_effect.get("delay_audio_min", 0.0)))
        self.custom_delay_audio_max_spin.setValue(float(custom_effect.get("delay_audio_max", 0.0)))
        self.custom_delay_audio_decimals_spin.setValue(int(custom_effect.get("delay_audio_decimals", 3)))


    def current_settings_dict(self) -> dict:

        overlay_list = []

        for ov_ctrl in self.overlay_controls:

            overlay_list.append({

                'enable': ov_ctrl['enable'].isChecked(),

                'name': ov_ctrl['name'].text(),

                'file': ov_ctrl['file'].text(),

                'folder': ov_ctrl['folder'].text(),

                'type': ov_ctrl['type'].currentText(),

                'zindex': ov_ctrl['zindex'].value(),

                'width': ov_ctrl['width'].value(),

                'height': ov_ctrl['height'].value(),

                'x': ov_ctrl['x'].value(),

                'y': ov_ctrl['y'].value(),

                'start': ov_ctrl['start'].value(),

                'end': ov_ctrl['end'].value(),

                'opacity': ov_ctrl['opacity'].value()

            })



        return {

            "general_settings": {

                "source_dir": self.input_edit.text(),

                "export_dir": self.output_edit.text(),

                "max_duration": self.max_duration_spin.value(),

                "target_bitrate": f"{self.bitrate_edit.text()}M",

                "maxrate": f"{self.maxrate_edit.text()}M",

                "bufsize": f"{self.bufsize_edit.text()}M",

                "encoder": "nvenc",

                "preset": self.preset_combo.currentText(),

                "video_fps": self.fps_combo.currentText(),

                "sample_rate": self.sample_rate_combo.currentText(),

                "audio_bitrate": self.audio_bitrate_combo.currentText(),

                "canvas_width": self.canvas_width_spin.value(),

                "canvas_height": self.canvas_height_spin.value(),

                "ffmpeg_timeout": self.timeout_spin.value(),

                "scale_x": self.scale_x_spin.value(),

                "scale_y": self.scale_y_spin.value(),

                "video_x": self.video_x_spin.value(),

                "video_y": self.video_y_spin.value()

            },

            "overlay_settings": overlay_list,
            "effect_settings": {
                "color_grading_enable": self.color_grading_chk.isChecked(),
                "contrast_min": self.contrast_min_spin.value(),
                "contrast_max": self.contrast_max_spin.value(),
                "saturation_min": self.saturation_min_spin.value(),
                "saturation_max": self.saturation_max_spin.value(),
                "brightness_min": self.brightness_min_spin.value(),
                "brightness_max": self.brightness_max_spin.value(),
                "hue_min": self.hue_min_spin.value(),
                "hue_max": self.hue_max_spin.value(),
                "unsharp_enable": self.unsharp_chk.isChecked(),
                "unsharp_x": self.unsharp_x_spin.value(),
                "unsharp_y": self.unsharp_y_spin.value(),
                "unsharp_amount": self.unsharp_amount_spin.value()
            },
            "custom_effect_settings": {
                "speed_enable": self.custom_speed_chk.isChecked(),
                "speed_min": self.custom_speed_min_spin.value(),
                "speed_max": self.custom_speed_max_spin.value(),
                "delay_frame_enable": self.custom_delay_frame_chk.isChecked(),
                "delay_frame_min": self.custom_delay_frame_min_spin.value(),
                "delay_frame_max": self.custom_delay_frame_max_spin.value(),
                "delay_audio_min": self.custom_delay_audio_min_spin.value(),
                "delay_audio_max": self.custom_delay_audio_max_spin.value(),
                "delay_audio_decimals": self.custom_delay_audio_decimals_spin.value()
            }

        }



    def choose_input(self):

        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục INPUT")

        if d:

            self.input_edit.setText(d)



    def choose_output(self):

        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục OUTPUT")

        if d:

            self.output_edit.setText(d)



    def append_log(self, msg: str):

        self.logs.append(msg)

        self.logs.verticalScrollBar().setValue(self.logs.verticalScrollBar().maximum())



    def on_progress(self, current: int, total: int, message: str):

        self.progress.setMaximum(total)

        self.progress.setValue(current)

        self.progress.setFormat(f"{current} / {total}")

        if message:

            self.append_log(message)



    def on_line(self, msg: str):

        self.append_log(msg)



    def on_finished(self, ok: bool, msg: str):

        self.start_btn.setEnabled(True)

        self.stop_btn.setEnabled(False)

        self.thread = None

        if ok:

            self.show_completion_popup()



    def start(self):

        if not self.input_edit.text() or not self.output_edit.text():

            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn thư mục INPUT và OUTPUT")

            return



        save_settings(self.current_settings_dict())



        videos = get_video_files_recursive(self.input_edit.text())

        self.progress.setMaximum(len(videos))

        self.progress.setValue(0)

        self.progress.setFormat(f"0 / {len(videos)}")



        # Reload settings from JSON to ensure we use saved values
        self.settings = load_settings()
        g = self.settings.get("general_settings", {})
        overlay_data = self.settings.get("overlay_settings", [])
        effect_data = self.settings.get("effect_settings", {})

        preset = g.get("preset", "p2")
        maxrate = g.get("maxrate")
        bufsize = g.get("bufsize")
        canvas_width = int(g.get("canvas_width", 1080))
        canvas_height = int(g.get("canvas_height", 1920))
        scale_x = float(g.get("scale_x", 1.0))
        scale_y = float(g.get("scale_y", 1.0))
        video_x = int(g.get("video_x", 0))
        video_y = int(g.get("video_y", 0))

        # Build overlay settings from loaded JSON
        overlay_settings = []
        for i, ov_item in enumerate(overlay_data):
            ctrl = self.overlay_controls[i] if i < len(self.overlay_controls) else None
            overlay_settings.append({
                'enable': ctrl['enable'].isChecked() if ctrl else False,
                'file': ctrl['file'].text() if ctrl else '',
                'folder': ctrl['folder'].text() if ctrl else '',
                'type': ctrl['type'].currentText() if ctrl else 'Video MP4',
                'zindex': ctrl['zindex'].value() if ctrl else 1,
                'width': ctrl['width'].value() if ctrl else 200,
                'height': ctrl['height'].value() if ctrl else 200,
                'x': ctrl['x'].value() if ctrl else 0,
                'y': ctrl['y'].value() if ctrl else 0,
                'start': ctrl['start'].value() if ctrl else 0.0,
                'end': ctrl['end'].value() if ctrl else 0.0,
                'opacity': ctrl['opacity'].value() if ctrl else 100.0,
            })

        effect_settings = {
            "color_grading_enable": self.color_grading_chk.isChecked(),
            "contrast_min": self.contrast_min_spin.value(),
            "contrast_max": self.contrast_max_spin.value(),
            "saturation_min": self.saturation_min_spin.value(),
            "saturation_max": self.saturation_max_spin.value(),
            "brightness_min": self.brightness_min_spin.value(),
            "brightness_max": self.brightness_max_spin.value(),
            "hue_min": self.hue_min_spin.value(),
            "hue_max": self.hue_max_spin.value(),
            "unsharp_enable": self.unsharp_chk.isChecked(),
            "unsharp_x": self.unsharp_x_spin.value(),
            "unsharp_y": self.unsharp_y_spin.value(),
            "unsharp_amount": self.unsharp_amount_spin.value()
        }

        custom_effect_settings = {
            "speed_enable": self.custom_speed_chk.isChecked(),
            "speed_min": self.custom_speed_min_spin.value(),
            "speed_max": self.custom_speed_max_spin.value(),
            "delay_frame_enable": self.custom_delay_frame_chk.isChecked(),
            "delay_frame_min": self.custom_delay_frame_min_spin.value(),
            "delay_frame_max": self.custom_delay_frame_max_spin.value(),
            "delay_audio_min": self.custom_delay_audio_min_spin.value(),
            "delay_audio_max": self.custom_delay_audio_max_spin.value(),
            "delay_audio_decimals": self.custom_delay_audio_decimals_spin.value()
        }

        self.thread = ProcessorThread(
            source_dir=self.input_edit.text(),
            export_dir=self.output_edit.text(),
            max_duration=self.max_duration_spin.value(),
            target_bitrate=g.get("target_bitrate", "4M"),
            overlay_settings=overlay_settings,
            video_fps=g.get("video_fps", "30"),
            sample_rate=g.get("sample_rate", "48000"),
            audio_bitrate=g.get("audio_bitrate", "128"),
            preset=preset,
            maxrate=maxrate,
            bufsize=bufsize,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            scale_x=scale_x,
            scale_y=scale_y,
            video_x=video_x,
            video_y=video_y,
            ffmpeg_timeout=self.timeout_spin.value(),
            effect_settings=effect_settings,
            custom_effect_settings=custom_effect_settings,
        )

        self.thread.progress.connect(self.on_progress)

        self.thread.line.connect(self.on_line)

        self.thread.finished.connect(self.on_finished)

        self.thread.start()

        

        self.start_btn.setEnabled(False)

        self.stop_btn.setEnabled(True)

        self.append_log("🚀 Bắt đầu xử lý...")



    def stop(self):

        if self.thread and self.thread.isRunning():

            self.thread.stop()

            self.thread.terminate()

            self.thread.wait()

            self.append_log("⏹️ Đã dừng")

        self.start_btn.setEnabled(True)

        self.stop_btn.setEnabled(False)



    def save_current_settings(self):

        try:

            save_settings(self.current_settings_dict())

            self.append_log(f"💾 Đã lưu {SETTINGS_FILE}")

        except Exception as e:

            QMessageBox.critical(self, "Lỗi", f"Không thể lưu: {str(e)}")



    def load_json_settings(self):

        """Load settings from JSON file chosen by user"""

        try:

            file_path, _ = QFileDialog.getOpenFileName(

                self, 

                "Chọn file JSON Settings", 

                BASE_DIR, 

                "JSON Files (*.json)"

            )

            if file_path:

                with open(file_path, 'r', encoding='utf-8') as f:

                    loaded_settings = json.load(f)

                

                # Apply loaded settings to UI

                self.settings = loaded_settings

                self.load_defaults_to_ui()

                self.append_log(f"📂 Đã load settings từ: {os.path.basename(file_path)}")

        except Exception as e:

            QMessageBox.critical(self, "Lỗi", f"Không thể load file JSON: {str(e)}")



    def save_json_settings(self):

        """Save current settings to a new JSON file (doesn't overwrite default)"""

        try:

            # Create default filename with timestamp

            default_name = f"overlay_settings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            file_path, _ = QFileDialog.getSaveFileName(

                self, 

                "Lưu Settings ra file JSON", 

                os.path.join(BASE_DIR, default_name), 

                "JSON Files (*.json)"

            )

            if file_path:

                settings_data = self.current_settings_dict()

                with open(file_path, 'w', encoding='utf-8') as f:

                    json.dump(settings_data, f, indent=2, ensure_ascii=False)

                self.append_log(f"💾 Đã lưu settings ra: {os.path.basename(file_path)}")

        except Exception as e:

            QMessageBox.critical(self, "Lỗi", f"Không thể lưu file JSON: {str(e)}")



    def clear_logs(self):

        self.logs.clear()

        self.append_log("📝 Logs đã được xóa")



    def show_completion_popup(self):

        # Play sound

        sound = QSoundEffect()

        sound.setSource(QUrl.fromLocalFile("audio.wav"))

        sound.setVolume(0.8)

        sound.play()



        dlg = QDialog(self)

        dlg.setWindowTitle("Hoàn thành")

        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)

        dlg.setFixedSize(350, 140)



        v = QVBoxLayout(dlg)

        v.setSpacing(15)

        v.setContentsMargins(20, 20, 20, 20)



        msg = QLabel("✅ Xử lý video hoàn thành!")

        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        msg.setStyleSheet("font-size: 16px; font-weight: bold; color: #485460; background-color: transparent;")

        v.addWidget(msg)



        h = QHBoxLayout()

        open_btn = QPushButton("Open Folder")

        def open_output():

            folder = self.output_edit.text()

            if folder and os.path.exists(folder):

                try:

                    if sys.platform == "win32":

                        os.startfile(folder)

                except Exception:

                    pass

        open_btn.clicked.connect(open_output)

        h.addWidget(open_btn)



        ok_btn = QPushButton("OK")

        ok_btn.clicked.connect(dlg.accept)

        h.addWidget(ok_btn)



        v.addLayout(h)

        dlg.exec()





def get_light_stylesheet() -> str:

    """Light theme stylesheet"""

    return """

    QMainWindow { background-color: #f5f5f5; }

    QWidget { background-color: #f5f5f5; color: #333333; font-family: 'Segoe UI', sans-serif; font-size: 12px; }

    QLabel { color: #333333; background-color: transparent; padding: 2px; }

    

    QPushButton {

        background-color: #808e9b; color: white; border: none;

        border-radius: 5px; padding: 8px 16px; font-weight: bold; min-width: 70px;

    }

    QPushButton:hover { background-color: #606c78; }

    QPushButton:disabled { background-color: #cccccc; color: #FFFFFF; }

    

    QPushButton#startBtn { background-color: #28a745; }

    QPushButton#startBtn:hover { background-color: #2fbc4e; }

    QPushButton#stopBtn { background-color: #dc3545; }

    QPushButton#stopBtn:hover { background-color: #e04555; }

    

    QLineEdit {

        background-color: #ffffff; color: #333333;

        border: 1px solid #c0c0c0; border-radius: 4px; padding: 6px 10px;

    }

    QLineEdit:focus { border: 2px solid #0078d4; }

    

    QSpinBox, QDoubleSpinBox {

        background-color: #ffffff; color: #333333;

        border: 1px solid #c0c0c0; border-radius: 4px; padding: 4px 8px;

    }

    QSpinBox:focus, QDoubleSpinBox:focus { border: 2px solid #0078d4; }

    

    QComboBox {

        background-color: #ffffff; color: #333333;

        border: 1px solid #c0c0c0; border-radius: 4px; padding: 5px 10px;

    }

    QComboBox:focus { border: 2px solid #0078d4; }

    QComboBox QAbstractItemView {

        background-color: #ffffff; color: #333333;

        selection-background-color: #0078d4; selection-color: white;

    }

    

    QCheckBox { spacing: 8px; color: #333333; background-color: transparent; }

    QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; border: 2px solid #888888; background-color: #ffffff; }

    QCheckBox::indicator:checked { background-color: #0078d4; border: 2px solid #0078d4; }

    

    QProgressBar {

        background-color: #e0e0e0; border: none; border-radius: 6px;

        text-align: center; color: #333333; font-weight: bold; min-height: 22px;

    }

    QProgressBar::chunk {

        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #28a745, stop:1 #34ce57);

        border-radius: 6px;

    }

    

    QTextEdit {

        background-color: #ffffff; color: #333333;

        border: 1px solid #c0c0c0; border-radius: 5px; padding: 8px;

        font-family: 'Consolas', monospace; font-size: 12px;

    }

    

    QScrollArea { background-color: transparent; border: none; }

    QScrollBar:vertical { background-color: #f0f0f0; width: 12px; border-radius: 6px; }

    QScrollBar::handle:vertical { background-color: #c0c0c0; border-radius: 6px; margin: 2px; }

    QScrollBar::handle:vertical:hover { background-color: #a0a0a0; }

    

    QFrame { background-color: #fafafa; border: 1px solid #d0d0d0; border-radius: 8px; }

    QDialog, QMessageBox { background-color: #f5f5f5; }

    """





def main():

    app = QApplication(sys.argv)

    app.setStyle('Fusion')

    app.setStyleSheet(get_light_stylesheet())

    

    w = MainWindow()

    w.show()

    sys.exit(app.exec())





if __name__ == "__main__":

    main()


