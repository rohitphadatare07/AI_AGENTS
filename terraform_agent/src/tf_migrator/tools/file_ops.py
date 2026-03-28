"""File operations for Terraform migration."""

import pathlib


class FileOps:
    def read(self, path: str) -> str:
        return pathlib.Path(path).read_text(encoding="utf-8")

    def write(self, path: str, content: str) -> None:
        pathlib.Path(path).write_text(content, encoding="utf-8")
