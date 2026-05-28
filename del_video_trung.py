from pathlib import Path

# Thư mục cần xoá file
folder = Path(r"01_INPUT")

# Xoá tất cả file .mp4 có "(1)" trong tên
for file in folder.rglob("*.mp4"):
    if "(1)" in file.name:
        try:
            file.unlink()
            print(f"Deleted: {file}")
        except Exception as e:
            print(f"Error deleting {file}: {e}")

print("Done!")