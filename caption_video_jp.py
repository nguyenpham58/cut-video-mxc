from pathlib import Path
from deep_translator import GoogleTranslator
import time

FOLDER = r"D:\BETA\B200\jp\YOUTUBE"

translator = GoogleTranslator(source="en", target="ja")

for file in Path(FOLDER).iterdir():
    if not file.is_file():
        continue

    old_name = file.stem
    ext = file.suffix

    try:
        jp_name = translator.translate(old_name)

        # Loại bỏ ký tự không hợp lệ trong tên file Windows
        for c in r'<>:"/\|?*':
            jp_name = jp_name.replace(c, "_")

        new_path = file.with_name(jp_name + ext)

        if new_path.exists():
            print(f"SKIP (exists): {new_path.name}")
            continue

        file.rename(new_path)

        print(f"{file.name} -> {new_path.name}")

        time.sleep(1)  # tránh rate limit

    except Exception as e:
        print(f"ERROR {file.name}: {e}")