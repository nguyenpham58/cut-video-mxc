import random
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import json
import time
import string


INPUT_DIR = Path(r"C:\PHIM_MXC\01_INPUT")
OUTPUT_DIR = Path(r"02_OUTPUT")
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
SKIP_INTRO = 15
SKIP_OUTRO = 30

BG_FOLDER = "overlay/BG_FILM"

# SETTING DELAY FRAME
DELAY_ACTIVE = True
FIRST_FRAME = random.randint(1, 1)
DELAY_AUDIO = round(random.uniform(0.05, 0.06), 3)
SPEED_VIDEO = round(random.uniform(1.1, 1.1), 5)
SPEED_AUDIO = round(random.uniform(1.09995, 1.09998), 5)

RANDOM_HOOK = False
RANDOM_HOOK_INTRO = round(random.uniform(9, 12), 2)


font_path = (
    Path(r"fonts/InstrumentSerif-Regular.ttf")
    .resolve()
    .as_posix()
    .replace(":", r"\:")
)

def run_cmd(cmd, timeout=30):
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"FFmpeg timeout after {timeout}s\n"
            f"CMD: {' '.join(map(str, cmd))}"
        )
    

def resolve_media_path(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tồn tại: {file_path}")

    # Folder -> random mp4
    if path.is_dir():
        mp4_files = [
            f for f in path.iterdir()
            if f.is_file() and f.suffix.lower() == ".mp4"
        ]

        if not mp4_files:
            raise FileNotFoundError(
                f"Không tìm thấy file mp4 trong folder: {file_path}"
            )

        return str(random.choice(mp4_files))

    # File -> giữ nguyên
    return str(path)

def build_filter_complex(date_text, overlays, video_input_label="0:v", background_input_label="1:v", overlay_start_index=2):
    contrast = round(random.uniform(1.05, 1.12), 3)
    saturation = round(random.uniform(1.05, 1.12), 3)
    brightness = round(random.uniform(0.01, 0.02), 4)
    hue_shift = random.randint(-3, 3)
    rand_postion_y = random.randint(60,70)
    rand_font_size = random.randint(52,58)

    # Zoom BG và Video
    bg_zoom = round(random.uniform(1.03, 1.06), 3)
    main_zoom_w = round(random.uniform(1.10, 1.18), 3)
    main_zoom_h = round(random.uniform(1.15, 1.18), 3)

    bg_w = int(CANVAS_WIDTH * bg_zoom)
    bg_h = int(CANVAS_HEIGHT * bg_zoom)

    main_w = int(CANVAS_WIDTH * main_zoom_w)

    filter_parts = []

    bg_chain = (
        f"[{background_input_label}]"
        f"fps=22,"
        f"scale={bg_w}:{bg_h},"
        f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT}:"
        f"x=(iw-{CANVAS_WIDTH})/2:"
        f"y=(ih-{CANVAS_HEIGHT})/2,"
        f"format=yuv420p"
        f"[bg]"
    )
    filter_parts.append(bg_chain)

    base_chain = (
        f"[{video_input_label}]"
        f"fps=22,"
        # scale full width trước, rồi zoom width
        f"scale={main_w}:-2,"
        # zoom height riêng, không phụ thuộc 16:9
        f"scale=iw:trunc(ih*{main_zoom_h}/2)*2,"
        # crop phần thừa theo width canvas
        f"crop={CANVAS_WIDTH}:ih:"
        f"x=(iw-{CANVAS_WIDTH})/2:"
        f"y=0,"
        # RANDOM COLOR
        f"eq="
        f"contrast={contrast}:"
        f"saturation={saturation}:"
        f"brightness={brightness},"
        f"hue=h={hue_shift},"
        
        f"format=yuv420p,"
        f"drawtext="
        f"fontfile='{font_path}':"
        f"text='{date_text}':"
        f"fontcolor=white:"
        f"fontsize={rand_font_size}:"
        f"x=(w-text_w)/2:"
        f"y={rand_postion_y}"
    )

    if DELAY_ACTIVE:
        first_frame_sec = FIRST_FRAME / 30
        base_chain += f",tpad=start_duration={first_frame_sec}:start_mode=clone"

    base_chain += f"[main]"

    filter_parts.append(base_chain)

    final_label = "vout" if not overlays else "v0"
    compose_chain = f"[bg][main]overlay=(W-w)/2:(H-h)/2:shortest=1[{final_label}]"
    filter_parts.append(compose_chain)

    for i, overlay in enumerate(overlays, start=1):

        target_width = overlay["width"]
        target_height = overlay["height"]

        opacity = float(overlay.get("opacity", 1.0))

        overlay_path = resolve_media_path(overlay["file_path"])
        extension = Path(overlay_path).suffix.lower()

        input_idx = i + overlay_start_index - 1

        overlay_chain = (
            f"[{input_idx}:v]"
            f"fps=22,"
            f"scale={target_width}:{target_height}"
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



def random_date(start="10/01/2020", end="30/06/2026"):
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


def ffprobe_has_audio(video_path):
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
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    data = json.loads(result.stdout)
    return len(data.get("streams", [])) > 0


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
        with open("overlay_v3.json", "r", encoding="utf-8") as f:
            overlay_data = json.load(f)

        has_audio = ffprobe_has_audio(video_path)

        # Hook logic
        use_hook = False
        hook_start = 0
        if RANDOM_HOOK:
            hook_offset = round(random.uniform(0.5, 1.0), 2)
            candidate_hook_start = current_time + part_duration - hook_offset
            if candidate_hook_start + RANDOM_HOOK_INTRO <= duration:
                hook_start = candidate_hook_start
                use_hook = True
            else:
                available_before = current_time - RANDOM_HOOK_INTRO - SKIP_INTRO
                if available_before >= 0:
                    hook_start = round(random.uniform(
                        SKIP_INTRO, current_time - RANDOM_HOOK_INTRO
                    ), 2)
                    use_hook = True

        bg_path = resolve_media_path(BG_FOLDER)

        # Build filter_complex
        video_label = "cv" if use_hook else "0:v"
        bg_label = "2:v" if use_hook else "1:v"
        overlay_offset = 3 if use_hook else 2

        filter_complex = build_filter_complex(
            date_text=date_text,
            overlays=overlay_data,
            video_input_label=video_label,
            background_input_label=bg_label,
            overlay_start_index=overlay_offset
        )

        # Concat filter (hook + main)
        if use_hook:
            if has_audio:
                concat_filter = "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[cv][ca]"
            else:
                concat_filter = "[0:v][1:v]concat=n=2:v=1:a=0[cv]"
            filter_complex = concat_filter + ";" + filter_complex

        # Video speed
        if SPEED_VIDEO != 1.0:
            filter_complex = filter_complex.replace("[vout]", "[vpre_speed]")
            filter_complex += f";[vpre_speed]setpts=PTS/{SPEED_VIDEO}[vout]"

        # Audio chain: fade_in → delay → speed → trim → fade_out
        if has_audio:
            input_dur = part_duration
            if use_hook:
                input_dur += RANDOM_HOOK_INTRO
            tpad_dur = FIRST_FRAME / 30 if DELAY_ACTIVE else 0
            if SPEED_VIDEO != 1.0:
                video_output_dur = (input_dur + tpad_dur) / SPEED_VIDEO
            else:
                video_output_dur = input_dur + tpad_dur

            audio_parts = []
            audio_parts.append("afade=t=in:d=0.1")

            if DELAY_ACTIVE:
                delay_ms = int(DELAY_AUDIO * 1000)
                audio_parts.append(f"adelay={delay_ms}|{delay_ms}")

            if SPEED_AUDIO != 1.0:
                audio_parts.append(f"atempo={SPEED_AUDIO}")

            audio_trim_end = round(video_output_dur - 1 / 30, 4)
            audio_parts.append(f"atrim=end={audio_trim_end}")
            audio_parts.append(
                f"afade=t=out:st={round(audio_trim_end - 0.1, 4)}:d=0.1"
            )

            # Random audio fingerprint
            audio_parts.append(f"highpass=f={random.randint(100, 150)}")
            audio_parts.append(f"lowpass=f={random.randint(16500, 18000)}")
            audio_parts.append(
                f"equalizer=f={random.randint(1500, 2500)}"
                f":t=q:w=1:g={random.uniform(-0.3, 0.3):.2f}"
            )
            audio_parts.append(
                f"acompressor="
                f"threshold={random.uniform(-20, -16):.3f}dB:"
                f"ratio={random.uniform(3.5, 4.5):.3f}:"
                f"attack={random.uniform(4, 8):.3f}:"
                f"release={random.uniform(120, 180):.3f}:"
                f"makeup={random.uniform(3, 4):.3f}"
            )
            audio_parts.append(f"volume={random.uniform(0.5, 1):.3f}")
            audio_parts.append(
                f"alimiter=limit={random.uniform(0.92, 0.98):.3f}"
            )

            audio_label = "ca" if use_hook else "0:a"
            filter_complex += (
                f";[{audio_label}]{','.join(audio_parts)}[aout]"
            )

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-hwaccel", "cuda",
        ]

        if use_hook:
            cmd.extend([
                "-ss", str(hook_start),
                "-t", str(RANDOM_HOOK_INTRO),
                "-i", str(video_path),
            ])

        cmd.extend([
            "-ss", str(current_time),
            "-t", str(part_duration),
            "-i", str(video_path),
        ])

        cmd.extend([
            "-stream_loop", "-1",
            "-i", bg_path,
        ])

        # Overlay inputs
        for overlay in overlay_data:
            media_path = resolve_media_path(overlay["file_path"])

            if overlay.get("loop", True):
                cmd.extend([
                    "-stream_loop", "-1",
                    "-i", media_path
                ])
            else:
                cmd.extend([
                    "-i", media_path
                ])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
        ])

        if has_audio:
            cmd.extend(["-map", "[aout]"])
        else:
            cmd.extend(["-map", "0:a?"])

        # Random Meta Data
        _rand_id = random.randint(100000, 999999)
        _ts = int(time.time())
        _meta_tag = f"Unique_{_rand_id}_{_ts}"

        cmd.extend([
            # XÓA SẠCH METADATA / CHAPTER / DATA / SUBTITLE
            "-map_metadata", "-1",
            "-map_chapters", "-1",

            # Chỉ map video + audio => loại bỏ toàn bộ stream phụ
            "-dn",
            "-sn",

            # VIDEO
            "-c:v", "hevc_nvenc",
            "-preset", "p2",

            "-b:v", "3.5M",
            "-maxrate", "3.8M",
            "-bufsize", "5M",

            "-r", "30",

            # AUDIO
            "-c:a", "aac",
            "-b:a", f"{random.randint(96, 128)}k",
            "-ar", "44100",

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
        # print(f"="*50)

        print(f"Creating: {original_name} - P{part_index}.mp4")

        try:
            result = run_cmd(cmd, timeout=30)

            if result.returncode != 0:
                print(result.stderr)
            else:
                final_output = output_dir / f"{original_name} - P{part_index}.mp4"
                output_path.replace(final_output)
                completed_parts += 1

        except TimeoutError as e:
            print(e)

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
                random_part=(160, 205)
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
