import json
import subprocess
import random
import string
import time
from pathlib import Path


# =========================================================
# SETTINGS
# =========================================================
INPUT_DIR = Path(r"01_INPUT")
OUTPUT_DIR = Path(r"02_OUTPUT")

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

FPS = 30

VIDEO_SCALE_W = 1.3
VIDEO_SCALE_H = 1.1

VIDEO_CROP_WIDTH = 1060
VIDEO_CROP_HEIGHT = 1900

# offset tính từ tâm crop
CROP_POS_X = 0
CROP_POS_Y = 0

SKIP_INTRO = (0,3) # Random Từ 0 - 3.0 mỗi lần xử lý
MAX_DURATION = 123


PRESET = "p2"

BITRATE = "5M"
BUFSIZE = "5.5M"
MAXRATE = "8M"

BACKGROUND_DIR = Path(r"overlay/background")

OVERLAY_CONFIG = Path(
    "overlay_shorts.json"
)


# =========================================================
# HELPERS
# =========================================================

def clamp(value, min_value, max_value):
    return max(
        min_value,
        min(value, max_value)
    )


def get_random_name(length=12):
    chars = string.ascii_lowercase + string.digits
    return ''.join(
        random.choice(chars) for _ in range(length)
    )


def get_random_background():
    bg_files = list(BACKGROUND_DIR.glob("*.mp4"))
    return random.choice(bg_files)


def format_time(total_seconds):
    h, rem = divmod(int(total_seconds), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def ffprobe_video_info(video_path: str | Path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate",
        "-show_entries",
        "format=duration",
        "-of", "json",
        str(video_path)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )

    data = json.loads(result.stdout)
    stream = data["streams"][0]

    width = int(stream["width"])
    height = int(stream["height"])

    fps_raw = stream["r_frame_rate"]
    if "/" in fps_raw:
        a, b = fps_raw.split("/")
        fps = float(a) / float(b)
    else:
        fps = float(fps_raw)

    duration = float(data["format"]["duration"])

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
    }


# =========================================================
# OVERLAY CONFIG
# =========================================================

def load_overlays():
    if not OVERLAY_CONFIG.exists():
        return []

    with open(OVERLAY_CONFIG, "r", encoding="utf-8") as f:
        overlays = json.load(f)

    # preload source size
    for overlay in overlays:
        overlay_path = Path(overlay["file_path"])
        info = ffprobe_video_info(overlay_path)
        overlay["source_width"] = info["width"]
        overlay["source_height"] = info["height"]

    return overlays


# =========================================================
# OVERLAY INPUTS
# =========================================================

def build_overlay_input_args(overlays):
    args = []

    for overlay in overlays:
        overlay_path = overlay["file_path"]
        overlay_loop = overlay.get("loop", True)

        if overlay_loop:
            args.extend(["-stream_loop", "-1"])

        args.extend(["-i", str(overlay_path)])

    return args


# =========================================================
# OVERLAY PREPARE FILTERS
# =========================================================

def build_overlay_prepare_filters(overlays):
    filter_parts = []

    # index: 0 = input, 1 = bg, 2+ = overlays
    for i, overlay in enumerate(overlays, start=2):
        target_width = round(overlay["width"] / 2) * 2
        target_height = round(overlay["height"] / 2) * 2
        source_width = overlay["source_width"]
        source_height = overlay["source_height"]
        opacity = float(overlay.get("opacity", 1.0))
        overlay_path = overlay["file_path"]
        extension = Path(overlay_path).suffix.lower()

        chain = f"[{i}:v]fps={FPS}"

        # scale
        need_scale = (
            source_width != target_width
            or source_height != target_height
        )
        if need_scale:
            if target_width == 1:
                target_width = -2
            if target_height == 1:
                target_height = -2
            chain += (
                f",scale={target_width}:{target_height}"
            )

        # opacity
        if opacity < 1.0:
            chain += (
                f",format=rgba,"
                f"colorchannelmixer=aa={opacity}"
            )
        else:
            if extension == ".mov":
                chain += ",format=rgba"
            else:
                chain += ",format=yuv420p"

        chain += f"[ov{i}]"
        filter_parts.append(chain)

    return filter_parts


# =========================================================
# APPLY OVERLAYS
# =========================================================

def build_overlay_apply_filters(
    overlays,
    start_label="v0",
    final_label="vout",
):
    filter_parts = []
    previous = start_label

    for i, overlay in enumerate(overlays, start=2):
        pos_x = overlay["position_x"]
        pos_y = overlay["postion_y"]
        overlay_loop = overlay.get("loop", True)

        out_label = (
            final_label
            if i == len(overlays) + 1
            else f"tmp{i}"
        )

        if overlay_loop:
            chain = (
                f"[{previous}][ov{i}]"
                f"overlay={pos_x}:{pos_y}"
                f"[{out_label}]"
            )
        else:
            chain = (
                f"[{previous}][ov{i}]"
                f"overlay={pos_x}:{pos_y}:"
                f"eof_action=pass"
                f"[{out_label}]"
            )

        filter_parts.append(chain)
        previous = out_label

    if not overlays:
        filter_parts.append(
            f"[{start_label}]copy[{final_label}]"
        )

    return filter_parts


# =========================================================
# BUILD FILTER COMPLEX
# =========================================================

def build_filter_complex(overlays, input_info):
    filter_parts = []

    # =====================================================
    # BACKGROUND
    # =====================================================
    filter_parts.append(
        f"[1:v]"
        f"fps={FPS},"
        f"scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}"
        f"[bg]"
    )

    # =====================================================
    # INPUT VIDEO
    # =====================================================
    input_scale_width = CANVAS_WIDTH
    input_scale_height = int(
        input_info["height"]
        * (CANVAS_WIDTH / input_info["width"])
    )

    # zoom
    zoom_width = int(round(input_scale_width * VIDEO_SCALE_W))
    zoom_height = int(round(input_scale_height * VIDEO_SCALE_H))

    # crop center
    center_crop_x = (zoom_width - VIDEO_CROP_WIDTH) // 2
    center_crop_y = (zoom_height - VIDEO_CROP_HEIGHT) // 2

    # offset crop
    crop_x = center_crop_x + CROP_POS_X
    crop_y = center_crop_y + CROP_POS_Y

    # clamp
    crop_x = clamp(crop_x, 0, zoom_width - VIDEO_CROP_WIDTH)
    crop_y = clamp(crop_y, 0, zoom_height - VIDEO_CROP_HEIGHT)

    # center overlay
    overlay_x = (CANVAS_WIDTH - VIDEO_CROP_WIDTH) // 2
    overlay_y = (CANVAS_HEIGHT - VIDEO_CROP_HEIGHT) // 2

    # prepare input video
    filter_parts.append(
        f"[0:v]"
        f"fps={FPS},"
        f"scale={input_scale_width}:{input_scale_height},"
        f"scale={zoom_width}:{zoom_height},"
        f"crop={VIDEO_CROP_WIDTH}:{VIDEO_CROP_HEIGHT}:"
        f"{crop_x}:{crop_y}"
        f"[fg]"
    )

    # bg + input
    filter_parts.append(
        f"[bg][fg]"
        f"overlay={overlay_x}:{overlay_y}"
        f"[v0]"
    )

    # =====================================================
    # OVERLAY VIDEOS
    # =====================================================
    filter_parts.extend(
        build_overlay_prepare_filters(overlays)
    )
    filter_parts.extend(
        build_overlay_apply_filters(
            overlays=overlays,
            start_label="v0",
            final_label="vout",
        )
    )

    return ";".join(filter_parts)


# =========================================================
# BUILD COMMAND
# =========================================================

def generate_ffmpeg_command(
    input_video: str | Path,
    output_video: str | Path,
):
    input_video = Path(input_video)
    output_video = Path(output_video)

    input_info = ffprobe_video_info(input_video)
    input_duration = input_info["duration"]

    # skip intro + max duration
    skip_intro = round(random.uniform(*SKIP_INTRO), 1)
    effective_end = min(input_duration, MAX_DURATION)
    actual_duration = effective_end - skip_intro

    overlays = load_overlays()

    # =====================================================
    # BASE CMD
    # =====================================================
    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel", "cuda",

        # input video
        "-ss", str(skip_intro),
        "-i", str(input_video),

        # background
        "-stream_loop", "-1",
        "-i", str(get_random_background()),
    ]

    # overlay inputs
    cmd.extend(
        build_overlay_input_args(overlays)
    )

    # filter complex
    filter_complex = build_filter_complex(
        overlays=overlays,
        input_info=input_info,
    )

    cmd.extend([
        # stop by actual duration
        "-t", str(actual_duration),

        # filter complex
        "-filter_complex", filter_complex,

        # map
        "-map", "[vout]",
        "-map", "0:a?",

        # xoá sạch metadata / chapter / data / subtitle
        "-map_metadata", "-1",
        "-map_chapters", "-1",
        "-dn",
        "-sn",

        # encoder
        "-c:v", "h264_nvenc",
        "-preset", PRESET,

        # bitrate
        "-b:v", BITRATE,
        "-maxrate", MAXRATE,
        "-bufsize", BUFSIZE,

        # pixel format
        "-pix_fmt", "yuv420p",

        # audio
        "-c:a", "aac",
        "-ar", "44100",
        "-b:a", "128k",

        "-shortest",

        # output fps
        "-r", str(FPS),

        # output
        str(output_video),
    ])

    return cmd


# =========================================================
# RENDER
# =========================================================

def render_video(
    input_video: str | Path,
    output_video: str | Path,
):
    cmd = generate_ffmpeg_command(
        input_video=input_video,
        output_video=output_video,
    )

    print(f"="*50)
    print(f"DEBUG CMD: {cmd}")

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    if result.returncode != 0:
        print(result.stderr)
        return False

    return True


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = sorted(INPUT_DIR.rglob("*.mp4"))
    if not videos:
        print("No .mp4 files found in INPUT_DIR")
    else:
        print(f"Found {len(videos)} video(s) to process\n")

    total = len(videos)
    total_completed = 0
    start_time = time.time()

    for idx, video in enumerate(videos, 1):
        original_name = video.stem
        relative_dir = video.parent.relative_to(INPUT_DIR)
        output_sub_dir = OUTPUT_DIR / relative_dir
        output_sub_dir.mkdir(parents=True, exist_ok=True)

        random_name = get_random_name() + ".mp4"
        temp_path = video.parent / random_name

        video.rename(temp_path)
        print(f"[{idx}/{total}] Processing: {original_name}.mp4")

        try:
            temp_output_name = f"{get_random_name()}.mp4"
            output_path = output_sub_dir / temp_output_name

            success = render_video(
                input_video=temp_path,
                output_video=output_path,
            )

            if success:
                final_output = output_sub_dir / f"{original_name}.mp4"
                output_path.replace(final_output)
                total_completed += 1
                print(f"Done: {original_name}.mp4\n")
            else:
                print(f"Failed: {original_name}.mp4\n")
                if output_path.exists():
                    output_path.unlink()
        finally:
            temp_path.rename(video)

    elapsed = time.time() - start_time

    print("=" * 50)
    print(f"Tổng số video hoàn thành: {total_completed}")
    print(f"Tổng thời gian xử lý: {format_time(elapsed)}")

    if total_completed > 0:
        avg = elapsed / total_completed
        print(f"Thời gian xử lý TB mỗi video: {format_time(avg)}")
