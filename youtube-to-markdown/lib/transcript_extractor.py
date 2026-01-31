"""Transcript extraction library."""

from pathlib import Path

from lib.shared_types import (
    CommandNotFoundError,
    CommandRunner,
    FileOperationError,
    FileSystem,
    RealCommandRunner,
    RealFileSystem,
    TranscriptNotAvailableError,
    extract_video_id,
)


class TranscriptExtractor:
    """Extracts transcript/subtitles from YouTube videos."""

    def __init__(self, fs: FileSystem = RealFileSystem(), cmd: CommandRunner = RealCommandRunner()):
        self.fs = fs
        self.cmd = cmd

    def check_yt_dlp(self) -> None:
        try:
            self.cmd.run(["yt-dlp", "--version"], capture_output=True, check=True)
        except Exception as e:
            raise CommandNotFoundError("yt-dlp is not installed") from e

    def get_video_language(self, youtube_url: str) -> str:
        result = self.cmd.run(["yt-dlp", "--print", "%(language)s", youtube_url], capture_output=True, text=True)
        video_lang = result.stdout.strip() if result.returncode == 0 else "unknown"
        print(f"Video language: {video_lang}")
        return video_lang

    def download_manual_subtitles(self, youtube_url: str, subtitle_lang: str, output_name: Path) -> Path | None:
        self.cmd.run(
            ["yt-dlp", "--write-sub", "--sub-langs", subtitle_lang, "--skip-download", "--output", str(output_name), youtube_url],
            capture_output=True,
        )
        temp_files = self.fs.glob(f"{output_name.name}.*.vtt", output_name.parent)
        if temp_files:
            print(f"Manual subtitles downloaded ({subtitle_lang})")
            return temp_files[0]
        return None

    def download_auto_subtitles(self, youtube_url: str, subtitle_lang: str, output_name: Path) -> Path | None:
        self.cmd.run(
            ["yt-dlp", "--write-auto-sub", "--sub-langs", subtitle_lang, "--skip-download", "--output", str(output_name), youtube_url],
            capture_output=True,
        )
        temp_files = self.fs.glob(f"{output_name.name}.*.vtt", output_name.parent)
        if temp_files:
            print(f"Auto-generated subtitles downloaded ({subtitle_lang})")
            return temp_files[0]
        return None

    def download_subtitles(self, youtube_url: str, subtitle_lang: str, output_name: Path) -> Path:
        subtitle_file = self.download_manual_subtitles(youtube_url, subtitle_lang, output_name)
        if subtitle_file:
            return subtitle_file

        subtitle_file = self.download_auto_subtitles(youtube_url, subtitle_lang, output_name)
        if subtitle_file:
            return subtitle_file

        raise TranscriptNotAvailableError(f"No subtitles available for language: {subtitle_lang}")

    def rename_subtitle_file(self, temp_file: Path, final_output: Path) -> Path:
        try:
            temp_file.rename(final_output)
        except Exception as e:
            raise FileOperationError(f"Failed to rename transcript file: {e}") from e

        if not self.fs.exists(final_output):
            raise FileOperationError(f"{final_output} not created")

        return final_output

    def extract_transcript(self, youtube_url: str, output_dir: Path, subtitle_lang: str = "en") -> Path:
        self.check_yt_dlp()
        video_id = extract_video_id(youtube_url)
        base_name = f"youtube_{video_id}"
        self.fs.mkdir(output_dir)
        self.get_video_language(youtube_url)

        output_name = output_dir / f"{base_name}_transcript_temp"
        final_output = output_dir / f"{base_name}_transcript.vtt"
        temp_file = self.download_subtitles(youtube_url, subtitle_lang, output_name)
        final_file = self.rename_subtitle_file(temp_file, final_output)

        print(f"SUCCESS: {final_file}")
        return final_file
