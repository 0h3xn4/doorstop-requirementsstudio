"""A small Git facade over dulwich: commit a project directory, annotated tags, read trees at a commit.

Only local operations: no remote access of any kind. Commits are never signed (a user's global signing setup would
need external programs), and only files inside the project directory are staged."""

import contextlib
import getpass
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dulwich.errors import NotGitRepository, RefFormatError
from dulwich.ignore import IgnoreFilterManager
from dulwich.index import commit_index
from dulwich.objects import Commit, Tag, Tree
from dulwich.refs import check_ref_format
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

    def close(self) -> None:
        self._repo.close()

    def __del__(self) -> None:  # dulwich warns about packs that are still open when the object store is collected
        with contextlib.suppress(Exception):  # interpreter shutdown, or already closed
            self._repo.close()

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
        name = re.sub(r"[<>\r\n]", "", name or _login()).strip() or "unknown"
        email = re.sub(r"[<>\r\n]", "", email) if email else email
        return f"{name} <{email or name.replace(' ', '.') + '@localhost'}>".encode()

    def head(self) -> str | None:
        try:
            return str(self._repo.head().decode())
        except KeyError:
            return None

    # committing ###################################################################
    def commit_directory(self, directory: Path, message: str, user: str | None) -> str:
        """Commit the files under ``directory`` (deletions included) and nothing else; returns the commit id, or the
        current head when nothing changed.

        Only the project's own subtree of the head tree is replaced: files other people staged elsewhere in the
        repository stay staged and uncommitted. Ignored files, nested repositories and Git's own folders are not
        added. The commit object is written directly, so no Git hook runs and no signing setup is consulted."""
        directory = Path(directory).resolve()
        rel = self.relative(directory)
        parts = [p for p in rel.split("/") if p]
        prefix = f"{rel}/" if rel else ""
        index = self._repo.open_index()
        tracked = {p.decode() for p in index}
        ignore = IgnoreFilterManager.from_repo(self._repo)
        files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(directory):
            dirnames[:] = sorted(
                d
                for d in dirnames
                if d not in SKIP_DIRS and not os.path.lexists(os.path.join(dirpath, d, ".git"))  # nested repository
            )
            for f in sorted(filenames):
                if f == ".git":
                    continue  # a submodule's pointer file
                path = f"{prefix}{Path(dirpath, f).relative_to(directory).as_posix()}"
                if path not in tracked and ignore.is_ignored(path):
                    continue  # ignored files (secrets, build output) are never force-added
                files.append(path)
        stale = [p for p in tracked if p.startswith(prefix) and p not in set(files)]
        worktree = self._repo.get_worktree()
        worktree.stage(files + stale)

        before = self.head()
        head_obj = self._repo[before.encode()] if before else None
        head_tree = self._repo[head_obj.tree] if isinstance(head_obj, Commit) else None
        staged_root = self._repo[commit_index(self._repo.object_store, self._repo.open_index())]
        assert isinstance(staged_root, Tree)
        subtree: Tree = staged_root
        for part in parts:  # the project's own subtree of what is staged
            try:
                node = self._repo[subtree[part.encode()][1]]
            except KeyError:
                raise GitError(f"Nothing under {directory} could be committed.") from None
            assert isinstance(node, Tree)
            subtree = node
        new_root = self._with_subtree(head_tree if isinstance(head_tree, Tree) else None, parts, subtree.id)
        if before and isinstance(head_obj, Commit) and new_root == head_obj.tree:
            return before
        who = self._identity(user)
        commit = Commit()
        commit.tree = new_root
        commit.parents = [before.encode()] if before else []  # type: ignore[list-item]
        commit.author = commit.committer = who
        commit.author_time = commit.commit_time = int(time.time())
        commit.author_timezone = commit.commit_timezone = 0
        commit.encoding = b"UTF-8"
        commit.message = message.encode()
        try:
            self._repo.object_store.add_object(commit)
            self._repo.refs[b"HEAD"] = commit.id  # type: ignore[index]
        except (OSError, KeyError) as exc:
            raise GitError(f"Git could not record the commit: {exc}") from exc
        return str(commit.id.decode())

    def _with_subtree(self, root: Tree | None, parts: list[str], sub_sha: bytes) -> bytes:
        """``root`` with the entry at ``parts`` replaced by ``sub_sha`` (rebuilding the trees on the way down)."""
        if not parts:
            return sub_sha
        tree = Tree()
        child: Tree | None = None
        if root is not None:
            for entry in root.items():
                if entry.path == parts[0].encode():
                    existing = self._repo[entry.sha]
                    child = existing if isinstance(existing, Tree) else None
                else:
                    tree.add(entry.path, entry.mode, entry.sha)
        tree.add(parts[0].encode(), 0o040000, self._with_subtree(child, parts[1:], sub_sha))  # type: ignore[arg-type]
        self._repo.object_store.add_object(tree)
        return bytes(tree.id)

    def commit_author(self, commit: str) -> str:
        obj = self._repo[commit.encode()]
        assert isinstance(obj, Commit)
        return str(obj.author.decode())

    # tags ############################################################################
    @staticmethod
    def valid_tag_name(name: str) -> bool:
        """Whether Git accepts ``name`` as a tag (no '..', no trailing '.' or '.lock', no special characters)."""
        return bool(check_ref_format(f"refs/tags/{name}".encode()))  # type: ignore[arg-type]

    def create_tag(self, name: str, message: str, user: str | None, commit: str) -> None:
        if not self.valid_tag_name(name):
            raise GitError(f"Git does not accept '{name}' as a tag name.")
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
        try:
            self._repo.object_store.add_object(tag)
            self._refs[ref] = tag.id
        except (RefFormatError, OSError) as exc:
            raise GitError(f"Git could not create the tag '{name}': {exc}") from exc

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
    def read_tree(self, commit: str, directory: Path, rel: str | None = None) -> dict[str, bytes]:
        """Files of ``directory`` as they were in ``commit``: {path relative to the directory: bytes}. ``rel`` names
        the folder inside the repository when the project was moved since (default: where it is now)."""
        rel = self.relative(directory) if rel is None else rel
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
                name = entry.path.decode("utf-8", errors="replace")
                if name in ("", ".", "..", ".git") or "/" in name or "\\" in name or "\x00" in name:
                    raise GitError(f"The tagged tree contains an entry named {name!r}, which cannot be a project file.")
                child = self._repo[entry.sha]
                path = f"{prefix}{name}"
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
