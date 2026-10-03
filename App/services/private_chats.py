"""Password-sealed anonymous chats, isolated from normal SQLCipher history.

Keys and decrypted state belong to one UI session. Temporary chats never write
their transcript/draft/Canvas to disk. Attachments are encrypted at rest in
persistent chats and unpacked into an owner-only scratch folder while unlocked.
"""
import base64
import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import threading
import time
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from filelock import FileLock, Timeout

from .paths import app_data_dir


class LockedChatError(RuntimeError):
    pass


def is_private(chat_id):
    return isinstance(chat_id, int) and chat_id < 0


def _key(password, salt):
    if len(password) < 8:
        raise ValueError("Пароль должен содержать не меньше 8 символов.")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode("utf-8"))


def _aad(chat_id, kind="chat"):
    return f"Xopilot/private/v1/{chat_id}/{kind}".encode()


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass
class PrivateMessage:
    id: int
    role: str
    content: str
    attachments: list
    quote: str | None = None
    reply_to: str | None = None
    created_at: str = ""


class PrivateChatSession:
    def __init__(self, root=None):
        self.root = Path(root) if root else app_data_dir() / "private-chats"
        self._opened = {}
        self._volatile = {}
        self._attempts = {}
        self._mutex = threading.RLock()
        self._scratch = None
        self._scratch_lease = None
        self._reclaim_scratch()

    @staticmethod
    def _reclaim_scratch():
        # Recover on startup, even when the user never opens another attachment.
        for old in Path(tempfile.gettempdir()).glob('xopilot-private-*'):
            try:
                if old.is_symlink() or not (old / '.owner.lock').is_file():
                    continue
                lease = FileLock(str(old / '.owner.lock'), thread_local=False)
                lease.acquire(timeout=0)
            except (Timeout, OSError):
                continue
            else:
                # Windows cannot remove a directory containing an open lock file.
                lease.release()
                shutil.rmtree(old, ignore_errors=True)

    def _path(self, cid):
        if not is_private(cid):
            raise ValueError("Это не анонимный чат.")
        return self.root / f"{abs(cid):x}" / "chat.sealed"

    def _folder(self, cid):
        if self._scratch is None:
            self._scratch = tempfile.TemporaryDirectory(prefix="xopilot-private-")
            self._scratch_lease = FileLock(str(Path(self._scratch.name) / '.owner.lock'), thread_local=False)
            self._scratch_lease.acquire(timeout=0)
        folder = Path(self._scratch.name) / f"{abs(cid):x}"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        return folder

    def _state(self, cid):
        if cid not in self._opened:
            raise LockedChatError("Чат закрыт. Введите его пароль.")
        return self._opened[cid]

    def opened(self, cid):
        return cid in self._opened

    def temporary(self, cid):
        return cid in self._volatile

    def create(self, password, temporary=False):
        salt = os.urandom(16)
        key = _key(password, salt)
        with self._mutex:
            cid = -secrets.randbelow(2**62) - 1
            while self._path(cid).exists() or cid in self._volatile:
                cid = -secrets.randbelow(2**62) - 1
            lease = None
            if not temporary:
                self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
                self._path(cid).parent.mkdir(parents=True, mode=0o700)
                lease = FileLock(str(self._path(cid).parent / "session.lock"), thread_local=False)
                lease.acquire(timeout=0)
            else:
                self._volatile[cid] = b""
            self._opened[cid] = {"key": key, "salt": salt, "lease": lease, "data": {
                "title": "Временный анонимный чат" if temporary else "Анонимный чат",
                "messages": [], "draft": {"text": "", "files": []}, "files": {}, "canvases": []}}
            try:
                self._save(cid)
            except Exception:
                self.close(cid)
                shutil.rmtree(self._path(cid).parent, ignore_errors=True)
                raise
            return cid

    def _save(self, cid):
        state = self._state(cid)
        try:
            nonce = os.urandom(12)
            plaintext = json.dumps(state['data'], ensure_ascii=False).encode('utf-8')
            ciphertext = AESGCM(state['key']).encrypt(nonce, plaintext, _aad(cid))
            envelope = json.dumps({'version': 1, 'salt': base64.b64encode(state['salt']).decode(),
                'nonce': base64.b64encode(nonce).decode(), 'ciphertext': base64.b64encode(ciphertext).decode()}).encode()
            if cid in self._volatile:
                self._volatile[cid] = envelope
            else:
                _atomic(self._path(cid), envelope)
        except Exception:
            if 'committed' in state:
                state['data'] = copy.deepcopy(state['committed'])
            raise
        state['committed'] = copy.deepcopy(state['data'])

    def unlock(self, cid, password):
        with self._mutex:
            if self.opened(cid):
                return
            attempts, until = self._attempts.get(cid, (0, 0))
            if until > time.monotonic():
                raise LockedChatError("Слишком много попыток. Подождите немного и повторите.")
            lease = None
            try:
                if cid not in self._volatile:
                    lease = FileLock(str(self._path(cid).parent / "session.lock"), thread_local=False)
                    lease.acquire(timeout=0)
                raw = self._volatile[cid] if cid in self._volatile else self._path(cid).read_bytes()
                envelope = json.loads(raw)
                if envelope["version"] != 1:
                    raise ValueError("Неподдерживаемая версия чата")
                salt = base64.b64decode(envelope["salt"], validate=True)
                key = _key(password, salt)
                data = AESGCM(key).decrypt(base64.b64decode(envelope["nonce"], validate=True),
                    base64.b64decode(envelope["ciphertext"], validate=True), _aad(cid))
                payload = json.loads(data)
                self._opened[cid] = {"key": key, "salt": salt, "lease": lease, "data": payload}
                self._restore_files(cid)
                self._opened[cid]["committed"] = copy.deepcopy(payload)
                self._attempts.pop(cid, None)
            except Timeout:
                raise LockedChatError("Чат уже открыт в другом окне. Закройте его там.") from None
            except Exception as exc:
                self._opened.pop(cid, None)
                if self._scratch:
                    shutil.rmtree(Path(self._scratch.name) / f"{abs(cid):x}", ignore_errors=True)
                if lease:
                    lease.release()
                if isinstance(exc, (InvalidTag, ValueError, KeyError)):
                    attempts += 1
                    self._attempts[cid] = (attempts, time.monotonic() + (min(60, 2**min(attempts-3, 6)) if attempts >= 3 else 0))
                    raise LockedChatError("Неверный пароль или повреждённый файл чата.") from None
                raise

    def items(self):
        with self._mutex:
            ids = set(self._volatile)
            if self.root.exists():
                for p in self.root.glob('*/chat.sealed'):
                    try:
                        value = -int(p.parent.name, 16)
                        if value < 0:
                            ids.add(value)
                    except ValueError:
                        continue
            result = []
            for cid in sorted(ids):
                if self.opened(cid):
                    payload = self._state(cid)["data"]
                    title = payload["title"]
                    subtitle = "Временный · до выхода" if self.temporary(cid) else "Анонимный · открыт"
                else:
                    title, subtitle = "Защищённый анонимный чат", "Закрыт паролем"
                result.append((cid, title, subtitle, False))
            return result

    def _asset_path(self, cid, asset):
        info = self._state(cid)["data"]["files"][asset]
        if len(asset) != 32 or any(c not in '0123456789abcdef' for c in asset) or Path(info['name']).name != info['name'] or '\\' in info['name'] or info['name'] in {'', '.', '..'}:
            raise ValueError('Повреждённые данные вложения')
        return self._folder(cid) / asset / info["name"]

    def _asset_id(self, cid, path):
        for asset in self._state(cid)["data"]["files"]:
            if self._asset_path(cid, asset) == Path(path):
                return asset
        raise ValueError("Файл не принадлежит этому анонимному чату.")

    def store_material(self, cid, name, *, path=None, data=None):
        with self._mutex:
            state = self._state(cid)
            name = Path(name.replace("\\", "/")).name
            if not name or name in {".", ".."}:
                raise ValueError("Укажите имя файла.")
            asset = uuid.uuid4().hex
            destination = self._folder(cid) / asset / name
            destination.parent.mkdir(mode=0o700)
            try:
                if data is not None:
                    destination.write_bytes(data)
                elif path:
                    shutil.copyfile(path, destination)
                else:
                    raise ValueError('Не удалось прочитать файл.')
                os.chmod(destination, 0o600)
                if not self.temporary(cid):
                    self._encrypt_file(cid, asset, destination)
                state['data']['files'][asset] = {'name': name, 'size': destination.stat().st_size}
                self._save(cid)
            except Exception:
                shutil.rmtree(destination.parent, ignore_errors=True)
                (self._path(cid).parent / (asset + '.sealed')).unlink(missing_ok=True)
                raise
            return str(destination)

    def _encrypt_file(self, cid, asset, source):
        nonce = os.urandom(12)
        encryptor = Cipher(algorithms.AES(self._state(cid)["key"]), modes.GCM(nonce)).encryptor()
        encryptor.authenticate_additional_data(_aad(cid, asset))
        target = self._path(cid).parent / (asset + ".sealed")
        fd, staging = tempfile.mkstemp(dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as output, source.open("rb") as input_file:
                output.write(nonce)
                while block := input_file.read(1024 * 1024):
                    output.write(encryptor.update(block))
                output.write(encryptor.finalize())
                output.write(encryptor.tag)
            os.replace(staging, target)
        finally:
            Path(staging).unlink(missing_ok=True)

    def _restore_files(self, cid):
        # A locked temporary chat keeps its scratch files until the session ends.
        if self.temporary(cid):
            return
        for asset in self._state(cid)["data"]["files"]:
            target = self._asset_path(cid, asset)
            target.parent.mkdir(exist_ok=True, mode=0o700)
            source = self._path(cid).parent / (asset + ".sealed")
            if source.stat().st_size < 28:
                raise ValueError('Повреждённое вложение')
            with source.open("rb") as encrypted:
                nonce = encrypted.read(12)
                encrypted.seek(-16, 2)
                decryptor = Cipher(algorithms.AES(self._state(cid)["key"]), modes.GCM(nonce, encrypted.read(16))).decryptor()
                decryptor.authenticate_additional_data(_aad(cid, asset))
                remaining = source.stat().st_size - 28
                encrypted.seek(12)
                try:
                    with target.open("wb") as output:
                        os.chmod(target, 0o600)
                        while remaining:
                            block = encrypted.read(min(1024 * 1024, remaining))
                            if not block:
                                raise ValueError("Повреждённое вложение")
                            output.write(decryptor.update(block))
                            remaining -= len(block)
                        output.write(decryptor.finalize())
                except Exception:
                    target.unlink(missing_ok=True)
                    raise

    def messages(self, cid):
        with self._mutex:
            return [PrivateMessage(**{**copy.deepcopy(message), "attachments": [
                (name, str(self._asset_path(cid, asset))) for name, asset in message["attachments"]]})
                for message in self._state(cid)["data"]["messages"]]

    def add_message(self, cid, role, text, quote=None, reply_to=None, attachments=None):
        with self._mutex:
            mid = -secrets.randbelow(2**62) - 1
            state = self._state(cid)["data"]
            state["messages"].append(dict(id=mid, role=role, content=text, quote=quote, reply_to=reply_to,
                attachments=[(name, self._asset_id(cid, path)) for name, path in attachments or []],
                created_at=str(time.time())))
            self._save(cid)
            return mid

    def edit_message(self, mid, text=None, attachments=None, delete=False):
        with self._mutex:
            for cid, state in self._opened.items():
                for message in state["data"]["messages"]:
                    if message["id"] == mid:
                        if delete:
                            state["data"]["messages"].remove(message)
                        else:
                            message["content"] = text
                            if attachments is not None:
                                message["attachments"] = [(n, self._asset_id(cid, p)) for n, p in attachments]
                        self._save(cid)
                        return True
            return False

    def clear(self, cid):
        with self._mutex:
            state = self._state(cid)["data"]
            state["messages"].clear()
            self._save(cid)

    def rename(self, cid, title):
        if not title.strip():
            raise ValueError("Введите название чата.")
        with self._mutex:
            self._state(cid)["data"]["title"] = title.strip()
            self._save(cid)
        return title.strip()

    def draft(self, cid, text=None, files=None):
        with self._mutex:
            payload = self._state(cid)["data"]
            if text is not None:
                payload["draft"] = {"text": text, "files": [self._asset_id(cid, p) for p in files or []]}
                self._save(cid)
            draft = payload["draft"]
            return {"text": draft["text"], "files": [str(self._asset_path(cid, a)) for a in draft["files"]]}

    def close(self, cid):
        with self._mutex:
            state = self._opened.pop(cid, None)
            if state and state["lease"]:
                state["lease"].release()
            self._volatile.pop(cid, None)
            if self._scratch:
                shutil.rmtree(Path(self._scratch.name) / f"{abs(cid):x}", ignore_errors=True)

    def delete(self, cid):
        exists = self._path(cid).exists() or cid in self._volatile
        if not self.opened(cid) and self._path(cid).exists():
            raise LockedChatError("Откройте чат паролем перед удалением.")
        self.close(cid)
        shutil.rmtree(self._path(cid).parent, ignore_errors=False) if self._path(cid).parent.exists() else None
        return exists

    def close_all(self):
        for cid in list(self._opened):
            self.close(cid)
        self._volatile.clear()
        if self._scratch:
            self._scratch_lease.release()
            self._scratch_lease = None
            self._scratch.cleanup()
            self._scratch = None


class PrivateCanvasStore:
    def __init__(self, session, cid):
        self.session, self.cid = session, cid

    def list_documents(self, *_):
        with self.session._mutex:
            return copy.deepcopy(self.session._state(self.cid)["data"]["canvases"])

    def create_document(self, title="Новый Canvas", kind="text", content="", **_):
        if kind not in {"text", "code", "drawing"}:
            raise ValueError("Неизвестный тип Canvas")
        doc = dict(id=uuid.uuid4().hex, title=title.strip() or "Новый Canvas", kind=kind, content=content, strokes=[],
                   chat_id=self.cid, workspace_id="all", updated_at=time.time())
        with self.session._mutex:
            self.session._state(self.cid)["data"]["canvases"].append(doc)
            self.session._save(self.cid)
        return copy.deepcopy(doc)

    def get_document(self, identifier):
        return next(doc for doc in self.list_documents() if doc["id"] == identifier)

    def save_document(self, document):
        if document.get("kind") not in {"text", "code", "drawing"} or not document.get("title", "").strip():
            raise ValueError("Введите название Canvas.")
        with self.session._mutex:
            docs = self.session._state(self.cid)["data"]["canvases"]
            index = next(i for i, doc in enumerate(docs) if doc["id"] == document["id"])
            docs[index] = {**copy.deepcopy(document), "updated_at": time.time()}
            self.session._save(self.cid)
            return copy.deepcopy(docs[index])

    def export_document(self, document):
        from .canvases import export_document
        return export_document(document)
