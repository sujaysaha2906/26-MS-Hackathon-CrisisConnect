"""Explicit one-time model download; never invoked during a conversation."""
from .local_recognition import model_directory


def main():
    from faster_whisper.utils import download_model
    path = model_directory()
    path.mkdir(parents=True, exist_ok=True)
    download_model("base", output_dir=str(path))
    print("Multilingual speech model ready. The demo can now recognize speech offline.")


if __name__ == "__main__":
    main()
