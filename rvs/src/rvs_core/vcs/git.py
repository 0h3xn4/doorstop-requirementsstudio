"""A small Git facade over dulwich: commit a project directory, annotated tags, read trees at a commit.

Only local operations: no remote access of any kind. Commits are never signed (a user's global signing setup would
need external programs), and only files inside the project directory are staged."""

import getpass
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dulwich.errors import NotGitRepository
from dulwich.objects import Commit, Tag, Tree
from dulwich.repo import Repo

SKIP_DIRS = {".git", ".rvs-cache"}


class GitError(Exception):
    """A Git operation failed; the message says what to do."""


@dataclass(frozen=True)
class TagInfo:
    name: str
    commit: str
    tagger: str
    time: int
    message: str


def _login() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - no login name on locked-down hosts
        return "unknown"


class GitRepo:
    def __init__(self, repo: Repo) -> None:
        self._repo = repo
        self._refs: Any = repo.refs  # dulwich types refs as a NewType of bytes; plain bytes are fine at runtime
        self.root = Path(repo.path).resolve()

    # construction ##############################################################
    @classmethod
    def discover(cls, path: Path) -> "GitRepo":
        try:
            return cls(Repo.discover(str(path)))
        except NotGitRepository:
            raise GitError(
                f"{path} is not inside a Git repository. Baselines are Git tags: create a repository first "
                "(for example 'git init' in the project folder, or 'rvs baseline create --init-git')."
            ) from None

    @classmethod
    def init(cls, path: Path) -> "GitRepo":
        path.mkdir(parents=True, exist_ok=True)
        return cls(Repo.init(str(path)))

    # helpers ######################################################################
    def relative(self, path: Path) -> str:
        rel = Path(os.path.relpath(Path(path).resolve(), self.root)).as_posix()
        return "" if rel == "." else rel

    def _identity(self, user: str | None) -> bytes:
        name, email = user, None
        cfg = self._repo.get_config_stack()
        try:
            configured = cfg.get((b"user",), b"name").decode()
            name = name or configured
            email = cfg.get((b"user",), b"email").decode()
        except KeyError:
            pass
        name = name or _login()
        return f"{name} <{email or name.replace(' ', '.') + '@localhost'}>".encode()

    def head(self) -> str | None:
        try:
            return str(self._repo.head().decode())
        except KeyError:
            return None

    # committing ###################################################################
    def commit_directory(self, directory: Path, message: str, user: str | None) -> str:
        """Stage everything under ``directory`` (including deletions) and commit; returns the commit id.
        Returns the current head unchanged when there is nothing to commit."""
        directory = Path(directory).resolve()
        rel = self.relative(directory)
        files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(directory):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for f in sorted(filenames):
                files.append(f"{rel}/{Path(dirpath, f).relative_to(directory).as_posix()}".lstrip("/"))
        index = self._repo.open_index()
        prefix = f"{rel}/" if rel else ""
        stale = [p.decode() for p in index if p.decode().startswith(prefix) and p.decode() not in set(files)]
        worktree = self._repo.get_worktree()
        worktree.stage(files + stale)
        before = self.head()
        head_obj = self._repo[before.encode()] if before else None
        tree_before = head_obj.tree if isinstance(head_obj, Commit) else None
        # compare the staged tree against the head tree to decide whether anything changed
        from dulwich.index import commit_index

        staged_tree = commit_index(self._repo.object_store, self._repo.open_index())
        if before and staged_tree == tree_before:
            return before
        who = self._identity(user)
        return str(worktree.commit(message=message.encode(), committer=who, author=who, sign=False).decode())

    def commit_author(self, commit: str) -> str:
        obj = self._repo[commit.encode()]
        assert isinstance(obj, Commit)
        return str(obj.author.decode())

    # tags ############################################################################
    def create_tag(self, name: str, message: str, user: str | None, commit: str) -> None:
        ref = f"refs/tags/{name}".encode()
        if ref in self._refs:
            raise GitError(f"The tag '{name}' already exists; tags are never moved or replaced.")
        tag = Tag()
        tag.name = name.encode()
        tag.message = message.encode()
        tag.tagger = self._identity(user)
        tag.tag_time = int(time.time())
        tag.tag_timezone = 0
        tag.object = (Commit, commit.encode())
        self._repo.object_store.add_object(tag)
        self._refs[ref] = tag.id

    def _tag_info(self, name: str, sha: bytes) -> TagInfo | None:
        obj = self._repo[sha]
        if isinstance(obj, Tag):
            return TagInfo(name, obj.object[1].decode(), obj.tagger.decode(), int(obj.tag_time), obj.message.decode())
        if isinstance(obj, Commit):  # lightweight tag
            return TagInfo(name, sha.decode(), obj.author.decode(), int(obj.commit_time), "")
        return None

    def tag(self, name: str) -> TagInfo | None:
        sha = self._refs.as_dict(b"refs/tags").get(name.encode())
        return self._tag_info(name, sha) if sha else None

    def tags(self, prefix: str = "") -> list[TagInfo]:
        found = []
        for raw, sha in self._refs.as_dict(b"refs/tags").items():
            name = raw.decode()
            if name.startswith(prefix) and (info := self._tag_info(name, sha)):
                found.append(info)
        return sorted(found, key=lambda t: t.name)

    # reading ############################################################################
    def read_tree(self, commit: str, directory: Path) -> dict[str, bytes]:
        """Files of ``directory`` as they were in ``commit``: {path relative to the directory: bytes}."""
        rel = self.relative(directory)
        obj = self._repo[commit.encode()]
        assert isinstance(obj, Commit)
        tree = self._repo[obj.tree]
        assert isinstance(tree, Tree)
        for part in [p for p in rel.split("/") if p]:
            try:
                mode, sha = tree[part.encode()]
            except KeyError:
                return {}
            tree = self._repo[sha]
            assert isinstance(tree, Tree)
        out: dict[str, bytes] = {}

        def walk(t: Tree, prefix: str) -> None:
            for entry in t.items():
                child = self._repo[entry.sha]
                path = f"{prefix}{entry.path.decode()}"
                if isinstance(child, Tree):
                    walk(child, path + "/")
                else:
                    out[path] = child.data  # type: ignore[attr-defined]

        walk(tree, "")
        return out

    def commit_time(self, commit: str) -> int:
        obj = self._repo[commit.encode()]
        assert isinstance(obj, Commit)
        return int(obj.commit_time)
