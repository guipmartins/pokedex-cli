"""Cache em disco para respostas da PokeAPI e sprites.

Os dados da PokeAPI praticamente não mudam, então guardar tudo localmente deixa
a segunda consulta instantânea e permite usar a Pokédex offline.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


def default_cache_dir() -> Path:
    if env := os.environ.get("POKEDEX_CACHE_DIR"):
        return Path(env)
    if os.name == "nt" and (local := os.environ.get("LOCALAPPDATA")):
        return Path(local) / "pokedex-cli" / "cache"
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "pokedex-cli"


class DiskCache:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else default_cache_dir()

    def _path(self, key: str, suffix: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.root / digest[:2] / f"{digest}{suffix}"

    def get_json(self, key: str) -> Any | None:
        path = self._path(key, ".json")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def set_json(self, key: str, value: Any) -> None:
        self._write(self._path(key, ".json"), json.dumps(value).encode("utf-8"))

    def get_bytes(self, key: str) -> bytes | None:
        try:
            return self._path(key, ".bin").read_bytes()
        except OSError:
            return None

    def set_bytes(self, key: str, value: bytes) -> None:
        self._write(self._path(key, ".bin"), value)

    def _write(self, path: Path, data: bytes) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)  # escrita atômica: nunca deixa arquivo pela metade
        except OSError:
            pass  # cache é otimização; falhar aqui não pode quebrar o programa

    def stats(self) -> tuple[int, int]:
        """(quantidade de arquivos, bytes totais)."""
        if not self.root.exists():
            return 0, 0
        files = [p for p in self.root.rglob("*") if p.is_file()]
        return len(files), sum(p.stat().st_size for p in files)

    def clear(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
