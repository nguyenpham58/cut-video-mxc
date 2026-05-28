import json
import subprocess
from pathlib import Path


# =========================================================
# SETTINGS
# =========================================================

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

FPS = 30

VIDEO_ZOOM = 1.3

VIDEO_CROP_WIDTH = 1060
VIDEO_CROP_HEIGHT = 1900

#
# offset tính từ tâm crop
#

CROP_POS_X = 0
CROP_POS_Y = 0

PRESET = "p2"

BITRATE = "5M"
BUFSIZE = "5.5M"
MAXRATE = "8M"

BACKGROUND_VIDEO = Path(
    r"OVERLAY/BG.mp4"
)

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


def ffprobe_video_info(
    video_path: str | Path
):

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

    data = json.loads(
        result.stdout
    )

    stream = data["streams"][0]

    width = int(stream["width"])
    height = int(stream["height"])

    fps_raw = stream["r_frame_rate"]

    if "/" in fps_raw:

        a, b = fps_raw.split("/")

        fps = float(a) / float(b)

    else:

        fps = float(fps_raw)

    duration = float(
        data["format"]["duration"]
    )

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

    with open(
        OVERLAY_CONFIG,
        "r",
        encoding="utf-8"
    ) as f:

        overlays = json.load(f)

    #
    # preload source size
    #

    for overlay in overlays:

        overlay_path = Path(
            overlay["file_path"]
        )

        info = ffprobe_video_info(
            overlay_path
        )

        overlay["source_width"] = (
            info["width"]
        )

        overlay["source_height"] = (
            info["height"]
        )

    return overlays


# =========================================================
# OVERLAY INPUTS
# =========================================================

def build_overlay_input_args(
    overlays
):

    args = []

    for overlay in overlays:

        overlay_path = overlay[
            "file_path"
        ]

        overlay_loop = overlay.get(
            "loop",
            True
        )

        #
        # loop overlay
        #

        if overlay_loop:

            args.extend([
                "-stream_loop",
                "-1"
            ])

        args.extend([
            "-i",
            str(overlay_path)
        ])

    return args


# =========================================================
# OVERLAY PREPARE FILTERS
# =========================================================

def build_overlay_prepare_filters(
    overlays
):

    filter_parts = []

    #
    # index:
    #
    # 0 = input
    # 1 = bg
    # 2+ = overlays
    #

    for i, overlay in enumerate(
        overlays,
        start=2
    ):

        target_width = round(
            overlay["width"] / 2
        ) * 2

        target_height = round(
            overlay["height"] / 2
        ) * 2

        source_width = overlay[
            "source_width"
        ]

        source_height = overlay[
            "source_height"
        ]

        opacity = float(
            overlay.get(
                "opacity",
                1.0
            )
        )

        overlay_path = overlay[
            "file_path"
        ]

        extension = (
            Path(overlay_path)
            .suffix
            .lower()
        )

        chain = (
            f"[{i}:v]"
            f"fps={FPS}"
        )

        #
        # scale
        #

        need_scale = (
            source_width != target_width
            or
            source_height != target_height
        )

        if need_scale:

            #
            # auto width
            #

            if target_width == 1:
                target_width = -2

            #
            # auto height
            #

            if target_height == 1:
                target_height = -2

            chain += (
                f",scale="
                f"{target_width}:"
                f"{target_height}"
            )

        #
        # opacity
        #

        if opacity < 1.0:

            chain += (
                f",format=rgba,"
                f"colorchannelmixer="
                f"aa={opacity}"
            )

        else:

            #
            # MOV giữ alpha
            #

            if extension == ".mov":

                chain += (
                    ",format=rgba"
                )

            else:

                chain += (
                    ",format=yuv420p"
                )

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

    for i, overlay in enumerate(
        overlays,
        start=2
    ):

        pos_x = overlay[
            "position_x"
        ]

        pos_y = overlay[
            "postion_y"
        ]

        overlay_loop = overlay.get(
            "loop",
            True
        )

        out_label = (
            final_label
            if i == len(overlays) + 1
            else f"tmp{i}"
        )

        #
        # loop overlay
        #

        if overlay_loop:

            chain = (
                f"[{previous}]"
                f"[ov{i}]"
                f"overlay="
                f"{pos_x}:{pos_y}"
                f"[{out_label}]"
            )

        #
        # non loop overlay
        #

        else:

            chain = (
                f"[{previous}]"
                f"[ov{i}]"
                f"overlay="
                f"{pos_x}:{pos_y}:"
                f"eof_action=pass"
                f"[{out_label}]"
            )

        filter_parts.append(chain)

        previous = out_label

    #
    # no overlay
    #

    if not overlays:

        filter_parts.append(
            f"[{start_label}]"
            f"copy"
            f"[{final_label}]"
        )

    return filter_parts


# =========================================================
# BUILD FILTER COMPLEX
# =========================================================

def build_filter_complex(
    overlays,
    input_info,
):

    filter_parts = []

    #
    # =====================================================
    # BACKGROUND
    # =====================================================
    #

    filter_parts.append(

        f"[1:v]"

        f"fps={FPS},"

        f"scale="
        f"{CANVAS_WIDTH}:"
        f"{CANVAS_HEIGHT}"

        f"[bg]"
    )

    #
    # =====================================================
    # INPUT VIDEO
    # =====================================================
    #

    input_scale_width = (
        CANVAS_WIDTH
    )

    input_scale_height = int(

        input_info["height"]

        *

        (
            CANVAS_WIDTH
            /
            input_info["width"]
        )
    )

    #
    # zoom
    #

    zoom_width = int(
        input_scale_width
        *
        VIDEO_ZOOM
    )

    zoom_height = int(
        input_scale_height
        *
        VIDEO_ZOOM
    )

    #
    # crop center
    #

    center_crop_x = (
        (
            zoom_width
            -
            VIDEO_CROP_WIDTH
        ) // 2
    )

    center_crop_y = (
        (
            zoom_height
            -
            VIDEO_CROP_HEIGHT
        ) // 2
    )

    #
    # offset crop
    #

    crop_x = (
        center_crop_x
        +
        CROP_POS_X
    )

    crop_y = (
        center_crop_y
        +
        CROP_POS_Y
    )

    #
    # clamp
    #

    crop_x = clamp(
        crop_x,
        0,
        zoom_width
        -
        VIDEO_CROP_WIDTH
    )

    crop_y = clamp(
        crop_y,
        0,
        zoom_height
        -
        VIDEO_CROP_HEIGHT
    )

    #
    # center overlay
    #

    overlay_x = (
        (
            CANVAS_WIDTH
            -
            VIDEO_CROP_WIDTH
        ) // 2
    )

    overlay_y = (
        (
            CANVAS_HEIGHT
            -
            VIDEO_CROP_HEIGHT
        ) // 2
    )

    #
    # prepare input video
    #

    filter_parts.append(

        f"[0:v]"

        f"fps={FPS},"

        f"scale="
        f"{input_scale_width}:"
        f"{input_scale_height},"

        f"scale="
        f"{zoom_width}:"
        f"{zoom_height},"

        f"crop="
        f"{VIDEO_CROP_WIDTH}:"
        f"{VIDEO_CROP_HEIGHT}:"
        f"{crop_x}:"
        f"{crop_y}"

        f"[fg]"
    )

    #
    # bg + input
    #

    filter_parts.append(

        f"[bg][fg]"

        f"overlay="
        f"{overlay_x}:"
        f"{overlay_y}"

        f"[v0]"
    )

    #
    # =====================================================
    # OVERLAY VIDEOS
    # =====================================================
    #

    filter_parts.extend(

        build_overlay_prepare_filters(
            overlays
        )
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

    input_video = Path(
        input_video
    )

    output_video = Path(
        output_video
    )

    input_info = ffprobe_video_info(
        input_video
    )

    input_duration = input_info[
        "duration"
    ]

    overlays = load_overlays()

    #
    # =====================================================
    # BASE CMD
    # =====================================================
    #

    cmd = [

        "ffmpeg",

        "-y",

        #
        # input video
        #

        "-i",
        str(input_video),

        #
        # background
        #

        "-stream_loop",
        "-1",

        "-i",
        str(BACKGROUND_VIDEO),
    ]

    #
    # overlay inputs
    #

    cmd.extend(
        build_overlay_input_args(
            overlays
        )
    )

    #
    # filter complex
    #

    filter_complex = (
        build_filter_complex(
            overlays=overlays,
            input_info=input_info,
        )
    )

    cmd.extend([

        #
        # stop by input duration
        #

        "-t",
        str(input_duration),

        #
        # filter complex
        #

        "-filter_complex",
        filter_complex,

        #
        # map
        #

        "-map",
        "[vout]",

        "-map",
        "0:a?",

        #
        # encoder
        #

        "-c:v",
        "h264_nvenc",

        "-preset",
        PRESET,

        #
        # bitrate
        #

        "-b:v",
        BITRATE,

        "-maxrate",
        MAXRATE,

        "-bufsize",
        BUFSIZE,

        #
        # pixel format
        #

        "-pix_fmt",
        "yuv420p",

        # AUDIO
        "-c:a", "aac",
        "-ar", "44100",
        "-b:a", "128k",

        "-shortest",

        #
        # output fps
        #

        "-r",
        str(FPS),

        # Ghi đè metadata encoder mặc định
        "-metadata", "title=",
        "-metadata", "comment=",
        "-metadata", "description=",
        "-metadata", "artist=",
        "-metadata", "album=",
        "-metadata", "creation_time=",
        "-metadata", "encoder=",

        #
        # output
        #

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

    print("=" * 120)
    print("FFMPEG COMMAND")
    print("=" * 120)

    print(" ".join(cmd))

    print("\n" + "=" * 120)

    process = subprocess.run(cmd)

    if process.returncode != 0:

        raise RuntimeError(
            "FFmpeg render failed"
        )

    print("Render success!")


# =========================================================
# EXAMPLE
# =========================================================

if __name__ == "__main__":

    render_video(
        input_video="input.mp4",
        output_video="output.mp4",
    )