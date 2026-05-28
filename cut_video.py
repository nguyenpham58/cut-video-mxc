import random
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import json
import time
import string

INPUT_DIR = Path(r"C:\PHIM_MXC\01_INPUT")
OUTPUT_DIR = Path(r"02_OUTPUT")
CANVAS_WIDTH = 960
CANVAS_HEIGHT = 720
SKIP_INTRO = 15
SKIP_OUTRO = 30

font_path = (
    Path(r"fonts/InstrumentSerif-Regular.ttf")
    .resolve()
    .as_posix()
    .replace(":", r"\:")
)

def build_filter_complex(date_text, overlays):
    contrast = round(random.uniform(1.02, 1.08), 2)
    saturation = round(random.uniform(1.04, 1.12), 2)
    brightness = round(random.uniform(-0.01, 0.015), 3)
    hue_shift = random.randint(5, 12)
    rand_postion_y = random.randint(74, 88)
    rand_font_size = random.randint(40, 50)


    filter_parts = []

    base_chain = (
        f"[0:v]"
        f"fps=30,"
        f"scale=-2:{CANVAS_HEIGHT},"
        f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT},"
        # RANDOM COLOR
        f"eq="
        f"contrast={contrast}:"
        f"saturation={saturation}:"
        f"brightness={brightness},"

        f"hue=h={hue_shift},"
        f"unsharp=5:5:0.4,"
        
        f"format=yuv420p,"
        f"drawtext="
        f"fontfile='{font_path}':"
        f"text='{date_text}':"
        f"fontcolor=white:"
        f"fontsize={rand_font_size}:"
        f"x=(w-text_w)/2:"
        f"y={rand_postion_y}"
        f"[v0]"
    )

    filter_parts.append(base_chain)

    for i, overlay in enumerate(overlays, start=1):

        target_width = round(overlay["width"] / 2) * 2
        target_height = round(overlay["height"] / 2) * 2

        source_width = overlay.get("source_width")
        source_height = overlay.get("source_height")

        opacity = float(overlay.get("opacity", 1.0))

        overlay_path = overlay["file_path"]
        extension = Path(overlay_path).suffix.lower()

        overlay_chain = f"[{i}:v]fps=30"

        #
        # Chỉ scale nếu source size khác target size
        #

        need_scale = (
            source_width != target_width
            or
            source_height != target_height
        )

        if need_scale:

            overlay_chain += (
                f",scale={target_width}:{target_height}"
            )

        #
        # MOV alpha overlay
        #

        if extension == ".mov":

            #
            # Chỉ xử lý rgba runtime nếu opacity < 1
            #

            if opacity < 1.0:

                overlay_chain += (
                    f",format=rgba,"
                    f"colorchannelmixer=aa={opacity}"
                )

        #
        # MP4 / normal overlay
        #

        else:

            if opacity < 1.0:

                overlay_chain += (
                    f",format=rgba,"
                    f"colorchannelmixer=aa={opacity}"
                )

            else:

                overlay_chain += (
                    f",format=yuv420p"
                )

        overlay_chain += f"[ov{i}]"

        filter_parts.append(overlay_chain)

    previous = "v0"

    for i, overlay in enumerate(overlays, start=1):

        pos_x = overlay["position_x"]
        pos_y = overlay["postion_y"]

        overlay_loop = overlay.get("loop", True)

        out_label = (
            "vout"
            if i == len(overlays)
            else f"tmp{i}"
        )

        #
        # Nếu loop:
        # overlay vô hạn
        # không cần shortest
        #

        if overlay_loop:

            overlay_chain = (
                f"[{previous}][ov{i}]"
                f"overlay={pos_x}:{pos_y}"
                f"[{out_label}]"
            )

        #
        # Nếu không loop:
        # overlay kết thúc thì stop overlay stream
        #

        else:

            overlay_chain = (
                f"[{previous}][ov{i}]"
                f"overlay={pos_x}:{pos_y}:eof_action=pass"
                f"[{out_label}]"
            )

        filter_parts.append(overlay_chain)

        previous = out_label

    return ";".join(filter_parts)



def random_date(start="10/01/2020", end="30/05/2026"):
    start_dt = datetime.strptime(start, "%d/%m/%Y")
    end_dt = datetime.strptime(end, "%d/%m/%Y")

    random_days = random.randint(0, (end_dt - start_dt).days)
    result = start_dt + timedelta(days=random_days)

    return result.strftime("%d/%m/%Y")


def get_random_name(length=12):
    """Generate random name with letters and digits (a-z, 0-9)"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def get_video_duration(video_path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video_path)
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    data = json.loads(result.stdout)

    return float(data["format"]["duration"])


def split_video_random(video_path, output_dir, original_name, random_part=(180, 255)):
    video_path = Path(video_path)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration(video_path)
    effective_end = duration - SKIP_OUTRO

    current_time = SKIP_INTRO
    part_index = 1
    completed_parts = 0

    while current_time < effective_end:
        part_duration = random.randint(*random_part)

        if current_time + part_duration > effective_end:
            part_duration = effective_end - current_time

        if part_duration <= 1:
            break

        temp_output_name = f"{get_random_name()}.mp4"
        output_path = output_dir / temp_output_name

        date_text = random_date()
        with open("overlay.json", "r", encoding="utf-8") as f:
            overlay_data = json.load(f)

        filter_complex = build_filter_complex(
            date_text=date_text,
            overlays=overlay_data
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-hwaccel", "cuda",

            "-ss", str(current_time),
            "-t", str(part_duration),

            "-i", str(video_path),
        ]

        for overlay in overlay_data:  
            if overlay.get("loop", True):
                cmd.extend([
                    "-stream_loop", "-1",
                    "-i", overlay["file_path"]
                ])
            else:
                cmd.extend([
                    "-i", overlay["file_path"]
                ])

        cmd.extend([
            "-filter_complex", filter_complex,

            "-map", "[vout]",
            "-map", "0:a?",

            # XÓA SẠCH METADATA / CHAPTER / DATA / SUBTITLE
            "-map_metadata", "-1",
            "-map_chapters", "-1",

            # Chỉ map video + audio => loại bỏ toàn bộ stream phụ
            "-dn",
            "-sn",

            # VIDEO
            "-c:v", "h264_nvenc",
            "-preset", "p2",

            "-b:v", "4M",
            "-maxrate", "4.2M",
            "-bufsize", "6M",

            "-r", "30",

            # AUDIO
            "-c:a", "aac",
            "-ar", "44100",
            "-b:a", "128k",

            "-shortest",

            # Ghi đè metadata encoder mặc định
            "-metadata", "title=",
            "-metadata", "comment=",
            "-metadata", "description=",
            "-metadata", "artist=",
            "-metadata", "album=",
            "-metadata", "creation_time=",
            "-metadata", "encoder=",

            str(output_path)
        ])

        # print(f"="*50)
        # print(f"DEBUG CMD: {cmd}")

        print(f"Creating: {original_name} - P{part_index}.mp4")
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
        else:
            final_output = output_dir / f"{original_name} - P{part_index}.mp4"
            output_path.replace(final_output)
            completed_parts += 1

        time.sleep(0.5)
        current_time += part_duration
        part_index += 1

    return completed_parts




if __name__ == "__main__":
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = sorted(INPUT_DIR.glob("*.mp4"))
    if not videos:
        print("No .mp4 files found in INPUT_DIR")
    else:
        print(f"Found {len(videos)} video(s) to process\n")

    total = len(videos)
    total_completed_parts = 0
    start_time = time.time()

    for idx, video in enumerate(videos, 1):
        original_name = video.stem
        random_name = get_random_name() + ".mp4"
        temp_path = video.parent / random_name

        video.rename(temp_path)
        print(f"[{idx}/{total}] Processing: {original_name}.mp4")

        try:
            parts = split_video_random(
                video_path=temp_path,
                output_dir=OUTPUT_DIR,
                original_name=original_name,
                random_part=(160, 225)
            )
            total_completed_parts += parts
        finally:
            temp_path.rename(video)

        print(f"Done: {original_name}.mp4\n")

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

    elapsed = time.time() - start_time

    print("=" * 50)
    print(f"Tổng số video part hoàn thành: {total_completed_parts}")
    print(f"Tổng thời gian xử lý: {format_time(elapsed)}")

    if total_completed_parts > 0:
        avg = elapsed / total_completed_parts
        print(f"Thời gian xử lý TB mỗi video: {format_time(avg)}")
