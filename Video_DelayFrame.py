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

FIRST_FRAME = 3  # Kéo dài 3 frame đầu tiên (fps=30 → 0.1s)
DELAY_AUDIO = 0.2  # Delay audio của video_out 0.2s so với video gốc

MAX_DURATION = 999

PRESET = "p2"

BITRATE = "10M"
BUFSIZE = "10.5M"
MAXRATE = "12M"


# =========================================================
# HELPERS
# =========================================================

def get_random_name(length=12):
    chars = string.ascii_lowercase + string.digits
    return ''.join(
        random.choice(chars) for _ in range(length)
    )


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


def ffprobe_has_audio(video_path: str | Path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=index",
        "-of", "json",
        str(video_path)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)
    return len(data.get("streams", [])) > 0


# =========================================================
# BUILD FILTER COMPLEX
# =========================================================

def build_filter_complex(input_info, has_audio):
    input_width = input_info["width"]
    input_height = input_info["height"]

    # scale to canvas width, giữ ratio
    scale_w = CANVAS_WIDTH
    scale_h = round(
        input_height * (CANVAS_WIDTH / input_width) / 2
    ) * 2

    # crop nếu cao hơn canvas
    if scale_h > CANVAS_HEIGHT:
        crop_h = CANVAS_HEIGHT
        crop_y = (scale_h - CANVAS_HEIGHT) // 2
    else:
        crop_h = scale_h
        crop_y = 0

    # pad ra canvas
    pad_y = (CANVAS_HEIGHT - crop_h) // 2

    # first frame duration
    first_frame_sec = FIRST_FRAME / FPS

    # video filter
    video_filter = (
        f"[0:v]"
        f"fps={FPS},"
        f"scale={scale_w}:{scale_h},"
        f"crop={CANVAS_WIDTH}:{crop_h}:0:{crop_y},"
        f"pad={CANVAS_WIDTH}:{CANVAS_HEIGHT}:0:{pad_y}:black,"
        f"setsar=1,"
        f"tpad=start_duration={first_frame_sec}:start_mode=clone"
        f"[vout]"
    )

    if not has_audio:
        return video_filter

    # audio filter
    delay_ms = int(DELAY_AUDIO * 1000)
    audio_filter = (
        f"[0:a]adelay={delay_ms}|{delay_ms}[aout]"
    )

    return f"{video_filter};{audio_filter}"


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
    has_audio = ffprobe_has_audio(input_video)

    # giới hạn input
    if input_duration < MAX_DURATION:
        read_duration = input_duration - 1
    else:
        read_duration = MAX_DURATION

    # filter complex
    filter_complex = build_filter_complex(
        input_info=input_info,
        has_audio=has_audio,
    )

    # base cmd
    cmd = [
        "ffmpeg",
        "-y",
        "-hwaccel", "cuda",

        # giới hạn đọc input
        "-t", str(read_duration),
        "-i", str(input_video),

        # filter complex
        "-filter_complex", filter_complex,

        # map
        "-map", "[vout]",
    ]

    if has_audio:
        cmd.extend(["-map", "[aout]"])

    cmd.extend([
        # xoá metadata
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
    ])

    if has_audio:
        cmd.extend([
            "-c:a", "aac",
            "-ar", "44100",
            "-b:a", "128k",
        ])

    cmd.extend([
        "-shortest",

        # output fps
        "-r", str(FPS),

        # output
        str(output_video),
    ])

    # DEBUG CMD FILTER
    print(f"="*50)
    print(f"DEBUG CMD: {cmd}")
    print(f"="*50)

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
                time.sleep(0.3)
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
