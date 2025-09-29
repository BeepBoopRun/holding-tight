from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import BinaryIO
import hashlib

from django.http.request import QueryDict


@dataclass
class ResumableFile:
    relative_path: str
    filename: str
    total_chunks: int
    chunks_added: int
    chunks: list[Path | None]
    write_directory: Path

    temp_files_path: Path

    def add_chunk(self, chunk_number: int, file_handle: BinaryIO) -> tuple[bool, bool]:
        """Adds chunk if doesn't exist yet.
        When all chunks are collected, writes out the whole file.
        """
        if self.has_chunk(chunk_number=chunk_number):
            return True, False
        path_hash = hashlib.md5(self.relative_path.encode("utf-8")).hexdigest()
        chunk_file_path = self.temp_files_path / f"{path_hash}_chunk_{chunk_number}"
        self.temp_files_path.mkdir(parents=True, exist_ok=True)
        with open(chunk_file_path, "wb") as f:
            f.write(file_handle.read())
        self.chunks[chunk_number - 1] = chunk_file_path

        chunk_written = True
        self.chunks_added += 1
        file_writen = False
        if self.total_chunks == self.chunks_added:
            print("writing out file", flush=True)
            self.write_finished_file()
            file_writen = True

        print(f"chunk file created!: {chunk_file_path}", flush=True)
        return chunk_written, file_writen

    def has_chunk(self, chunk_number: int) -> bool:
        return self.chunks[chunk_number - 1] is not None

    def write_finished_file(self) -> bool:
        """Writes file with all chunks to specified location.
        Returns true if succeded, false otherwise.
        """
        containing_dir = (self.write_directory / self.relative_path).parent
        containing_dir.mkdir(parents=True, exist_ok=True)
        with open(containing_dir / self.filename, "wb") as f:
            for chunk in self.chunks:
                if chunk is None:
                    return False
                with open(chunk, "rb") as f_chunk:
                    f.write(f_chunk.read())
        return True

    def remove_temp_directory(self) -> None:
        """Remove directory with chunks."""
        shutil.rmtree(self.temp_files_path)


class ResumableFilesManager:
    managed_files: dict[str, ResumableFile]
    managed_directories: dict[Path, list[ResumableFile]]
    directory_file_count: dict[Path, list[int]]
    # how many files received, how many expected

    def __init__(self) -> None:
        self.managed_files = {}
        self.managed_directories = {}
        self.directory_file_count = {}

    def clean(self) -> None:
        # TODO!!
        pass

    def get_writing_directory(
        self, resumable_data: QueryDict, main_write_directory: Path
    ):
        base_dir = Path(resumable_data.get("resumableRelativePath") or "").parts[0]
        return main_write_directory / base_dir

    def check_if_directory_finished(self, write_directory: Path):
        return (
            self.directory_file_count[write_directory][0]
            == self.directory_file_count[write_directory][1]
        )

    def handle_resumable_post_request(
        self,
        resumable_data: QueryDict,
        file_handle: BinaryIO,
        main_write_directory: Path,
    ) -> tuple[bool, Path | None]:
        file_id = resumable_data.get("resumableIdentifier", None)
        base_dir = Path(resumable_data.get("resumableRelativePath") or "").parts[0]
        temp_dir = main_write_directory / "temp" / base_dir
        write_directory = self.get_writing_directory(
            resumable_data, main_write_directory
        )
        if file_id is None:
            return False, None
        if write_directory not in self.managed_directories:
            self.managed_directories[write_directory] = []
            expected_file_count = int(resumable_data.get("fileCount") or 0)
            self.directory_file_count[write_directory] = [0, expected_file_count]
        handler = self.managed_files.get(file_id, None)
        if handler is None:
            handler = ResumableFile(
                total_chunks=int(resumable_data.get("resumableTotalChunks") or 0),
                filename=resumable_data.get("resumableFilename") or "",
                relative_path=resumable_data.get("resumableRelativePath") or "",
                chunks_added=0,
                chunks=(
                    [None] * int(resumable_data.get("resumableTotalChunks") or "0")
                ),
                write_directory=write_directory,
                temp_files_path=temp_dir,
            )
            self.managed_directories[write_directory].append(handler)
            self.managed_files[file_id] = handler
        print(handler.chunks_added, flush=True)
        chunk_number = resumable_data.get("resumableChunkNumber") or 0
        chunk_written, file_written = handler.add_chunk(
            chunk_number=int(chunk_number), file_handle=file_handle
        )
        directory_complete = False
        if file_written:
            print(f"File written: {resumable_data.get('resumableFilename')}")
            self.directory_file_count[write_directory][0] += 1
            directory_complete = self.check_if_directory_finished(write_directory)
        return chunk_written, write_directory if directory_complete else None

    def handle_resumable_get_request(
        self, resumable_data: QueryDict, main_write_directory: Path
    ) -> tuple[bool, Path | None]:
        write_directory = self.get_writing_directory(
            resumable_data, main_write_directory
        )
        file_id = resumable_data.get("resumableIdentifier", None)
        if file_id is None:
            return False, None
        if write_directory not in self.managed_directories:
            return False, None
        handler = self.managed_files.get(file_id, None)
        if handler is None:
            return False, None
        has_chunk = handler.has_chunk(
            int(resumable_data.get("resumableChunkNumber") or 0)
        )
        dir_ready = self.check_if_directory_finished(write_directory)
        return has_chunk, write_directory if dir_ready else None

    def list_completed_directories(self):
        return [
            dir
            for dir in self.managed_directories
            if self.check_if_directory_finished(dir)
        ]
