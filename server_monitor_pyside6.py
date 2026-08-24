"""Server Monitor — desktop client built with PySide6.

Run from VS Code:  python -m pip install -r requirements-pyside6.txt
                    python server_monitor_pyside6.py
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pathlib import Path, PurePosixPath
from typing import Callable

import paramiko
from PySide6.QtCore import QThreadPool, Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QInputDialog, QMenu, QPlainTextEdit, QProgressBar, QScrollArea, QSizePolicy, QStackedWidget,
    QTableWidget, QTableWidgetItem, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from dataarchive.config import (
    APP_DIRECTORY, APP_VERSION, ARCHIVE_FILE_FILTER, AUDIT_LOG, DATA_DIRECTORY,
    HDD_WRITE_ACCOUNTS, HOST_FINGERPRINT, MAX_PARALLEL_TRANSFERS, MAX_SSH_LOGIN_ATTEMPTS,
    SECURITY_FILE, SERVER, SERVER_ACCOUNTS, SSD_DIRECTORY, STATUS_COMMAND,
    STORAGE_LOCATIONS, UPLOAD_DIRECTORY, fmt_bytes, fmt_duration, is_archive_file,
    parse_status,
)
from dataarchive.workers import Worker

APP_STYLE = """
QMainWindow { background: #f6f8fc; }
QWidget { color: #17233b; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
#sidebar { background: #062451; border: none; }
#brand { color: white; font-size: 21px; font-weight: 800; } #subtitle { color: #a7c0e8; }
#topbar { background: white; border-bottom: 1px solid #e5eaf3; }
#accountChip { background: #f5fbf8; border: 1px solid #dcefe4; border-radius: 12px; min-width: 168px; }
#accountChip:hover { background: #eff9f3; border-color: #b9dfc8; }
#accountAvatar, #settingsAvatar { background: #ddf5e6; color: #117849; border-radius: 17px; font-size: 15px; font-weight: 800; }
#accountName { color: #18384c; font-size: 12px; font-weight: 800; }
#accountState { color: #6a8277; font-size: 10px; }
#settingsHero { background: #102f60; border: none; border-radius: 16px; }
#settingsHero QLabel { color: white; }
#settingsHeroNote { color: #bcd3f5; font-size: 12px; }
#settingsCard { background: white; border: 1px solid #e3eaf4; border-radius: 14px; }
#settingsCard:hover { border-color: #c9d9ee; }
#settingsIcon { background: #eaf3ff; color: #0967e8; border-radius: 11px; font-size: 18px; font-weight: 800; }
#settingsTitle { color: #1b2c48; font-size: 15px; font-weight: 800; }
#settingsDescription { color: #71819a; font-size: 12px; }
#settingsStatus { background: #ecf8f0; color: #14804a; border-radius: 8px; padding: 5px 8px; font-size: 11px; font-weight: 700; }
#topTitle { color: #14213b; font-size: 24px; font-weight: 800; } #muted { color: #70809a; }
QPushButton, QToolButton { background: white; color: #25405f; border: 1px solid #dce4ef; border-radius: 8px; padding: 9px 13px; font-weight: 600; }
QPushButton:hover, QToolButton:hover { border-color: #1263df; color: #075bd8; background: #f7faff; }
QPushButton:pressed, QToolButton:pressed { background: #edf4ff; }
QPushButton#primary, QToolButton#primary { background: #0967e8; color: white; border: none; } QPushButton#primary:hover, QToolButton#primary:hover { background: #0759c9; color: white; }
QPushButton#danger { color: #c02f3c; border-color: #f2c7cd; } QPushButton#danger:hover { background: #fff4f5; }
QToolButton { padding-right: 34px; } QToolButton::menu-indicator { subcontrol-origin: padding; subcontrol-position: right center; right: 10px; width: 12px; height: 12px; }
QMenu { background: #ffffff; color: #1d2e49; border: 1px solid #d9e3f0; border-radius: 10px; padding: 6px; }
QMenu::item { background: transparent; color: #1d2e49; border-radius: 6px; padding: 10px 34px 10px 12px; margin: 1px 2px; min-width: 210px; }
QMenu::item:selected { background: #eaf3ff; color: #075bd8; }
QMenu::item:disabled { color: #9aa8bc; background: transparent; }
QMenu::separator { height: 1px; background: #e7edf5; margin: 6px 8px; }
QPushButton#nav { background: transparent; border: none; color: #dce9ff; text-align: left; padding: 12px 15px; border-radius: 8px; font-size: 14px; }
QPushButton#nav:hover, QPushButton#nav:checked { background: #0d65df; color: white; }
QFrame#card, QFrame#panel, QFrame#storageCard { background: white; border: 1px solid #e6ebf3; border-radius: 13px; }
QFrame#actionBox { background: #f8faff; border: 1px solid #e2e9f3; border-radius: 10px; }
QLabel#actionTitle { color: #71819a; font-size: 10px; font-weight: 800; }
QLabel#metricTitle { color: #5d6d87; font-size: 13px; } QLabel#metricValue { color: #15233e; font-size: 25px; font-weight: 800; }
QLabel#metricNote { color: #159a60; font-size: 12px; } QLabel#pageTitle { color: #16233d; font-size: 26px; font-weight: 800; }
QLabel#status { border-radius: 12px; padding: 6px 11px; font-weight: 700; }
QLineEdit, QPlainTextEdit, QComboBox { background: white; border: 1px solid #dbe3ef; border-radius: 8px; padding: 9px; color: #1d2e49; selection-background-color: #cfe2ff; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 2px solid #78aef8; }
QDialog, QMessageBox { background: #ffffff; color: #17233b; }
QDialog QLabel, QMessageBox QLabel { background: transparent; color: #17233b; }
QMessageBox QPushButton { min-width: 76px; background: #ffffff; color: #075bd8; border: 1px solid #cdd9e8; border-radius: 8px; padding: 9px 14px; }
QMessageBox QPushButton:hover { background: #eef5ff; border-color: #0967e8; }
QTableWidget { background: white; alternate-background-color: #fbfcfe; border: 1px solid #e5eaf2; border-radius: 10px; gridline-color: #edf0f5; selection-background-color: #e6f0ff; selection-color: #12213c; }
QTreeWidget { background: #ffffff; color: #1d2e49; border: 1px solid #e5eaf2; border-radius: 8px; alternate-background-color: #fbfcfe; outline: none; }
QTreeWidget::item { color: #1d2e49; min-height: 30px; padding: 3px 5px; } QTreeWidget::item:hover { background: #f0f6ff; } QTreeWidget::item:selected { background: #e2efff; color: #075bd8; }
QTableCornerButton::section { background: #f8faff; border: none; border-bottom: 1px solid #e5eaf2; }
QHeaderView::section { background: #f8faff; color: #50617b; border: none; border-bottom: 1px solid #e5eaf2; padding: 11px; font-weight: 800; }
QProgressBar { border: 0; background: #e6edf7; border-radius: 5px; height: 8px; text-align: center; color: transparent; } QProgressBar::chunk { background: #1268e8; border-radius: 5px; }
QScrollArea { border: none; background: #f6f8fc; } QScrollArea > QWidget > QWidget { background: #f6f8fc; }
QScrollBar:vertical { background: transparent; width: 10px; } QScrollBar::handle:vertical { background: #c8d2e2; border-radius: 5px; min-height: 25px; }
"""


class SshLoginError(RuntimeError):
    """The selected SSH account could not be authenticated."""


class SshService:
    def __init__(self): self.username = SERVER["username"]; self.auth_method = "password"; self.secret = ""
    def clear_credentials(self): self.secret = ""
    @staticmethod
    def key_path() -> Path: return Path.home() / ".ssh" / "server_monitor_ed25519"
    def connect(self):
        client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # Paramiko expects ``hostname`` (not ``host`` as used by ssh2/Electron).
        try:
            if self.auth_method == "key":
                path = self.key_path()
                if not path.exists(): raise SshLoginError(f"SSH_LOGIN_INVALID: Không tìm thấy SSH key: {path}")
                try: key = paramiko.Ed25519Key.from_private_key_file(str(path), password=self.secret or None)
                except (paramiko.SSHException, ValueError) as error: raise SshLoginError(f"SSH_LOGIN_INVALID: Không thể mở SSH key: {error}") from error
                client.connect(hostname=SERVER["host"], port=SERVER["port"], username=self.username, pkey=key,
                               timeout=12, banner_timeout=12, auth_timeout=12, look_for_keys=False, allow_agent=False)
            else:
                client.connect(hostname=SERVER["host"], port=SERVER["port"], username=self.username, password=self.secret,
                               timeout=12, banner_timeout=12, auth_timeout=12, look_for_keys=False, allow_agent=False)
        except paramiko.AuthenticationException as error:
            raise SshLoginError("SSH_LOGIN_INVALID: Tên đăng nhập hoặc mật khẩu SSH không đúng.") from error
        remote_key = client.get_transport().get_remote_server_key()
        digest = base64.b64encode(hashlib.sha256(remote_key.asbytes()).digest()).decode().rstrip("=")
        if f"SHA256:{digest}" != HOST_FINGERPRINT:
            client.close(); raise RuntimeError("Host fingerprint SSH không khớp. Kết nối đã bị từ chối.")
        return client
    def command(self, command: str) -> str:
        client = self.connect()
        try:
            return self._command_on_client(client, command)
        finally: client.close()
    def audit(self, action: str, detail: str):
        command = f"umask 027; touch {shlex.quote(AUDIT_LOG)}; printf '%s|%s|%s|%s\\n' \"$(date -Is)\" \"$USER\" {shlex.quote(action)} {shlex.quote(detail)} >> {shlex.quote(AUDIT_LOG)}"
        try: self.command(command)
        except Exception: pass  # A completed data operation must not be marked failed only because logging failed.
    def read_audit(self) -> list[str]:
        output = self.command(f"tail -n 30 {shlex.quote(AUDIT_LOG)} 2>/dev/null || true")
        return [line for line in output.splitlines() if line.strip()]
    def configure_shared_hdd_access(self, sudo_password: str):
        """Give the configured SSH accounts read-only access to the shared HDD.

        The command is deliberately fixed: it cannot be repurposed to run an
        arbitrary privileged command from the UI.  servermonitor and
        thacsikhai are the archive editors; huy1111 stays read-only.
        """
        script = " ".join([
            "set -eu;",
            "command -v setfacl >/dev/null || { echo 'Server chưa có tiện ích ACL (setfacl).' >&2; exit 1; };",
            "getent group dataarchive-editors >/dev/null || groupadd --system dataarchive-editors;",
            "getent group dataarchive-viewers >/dev/null || groupadd --system dataarchive-viewers;",
            "for user in servermonitor thacsikhai; do id \\\"$user\\\" >/dev/null 2>&1 && usermod -a -G dataarchive-editors \\\"$user\\\"; done;",
            "id huy1111 >/dev/null 2>&1 && usermod -a -G dataarchive-viewers huy1111;",
            f"test -d {shlex.quote(UPLOAD_DIRECTORY)};",
            f"chgrp -R dataarchive-editors {shlex.quote(UPLOAD_DIRECTORY)};",
            f"find {shlex.quote(UPLOAD_DIRECTORY)} -type d -exec chmod g+rwx,o-rwx,g+s {{}} +;",
            f"find {shlex.quote(UPLOAD_DIRECTORY)} -type f -exec chmod g+rw,o-rwx {{}} +;",
            f"setfacl -m g:dataarchive-viewers:--x {shlex.quote(DATA_DIRECTORY)};",
            f"setfacl -R -m g:dataarchive-viewers:rX {shlex.quote(UPLOAD_DIRECTORY)};",
            f"find {shlex.quote(UPLOAD_DIRECTORY)} -type d -exec setfacl -m d:g:dataarchive-viewers:rx,d:m::rwx {{}} +;",
        ])
        client = self.connect()
        try:
            command = f"sudo -S -p '' -- /bin/sh -c {shlex.quote(script)}"
            stdin, stdout, stderr = client.exec_command(command, timeout=40)
            stdin.write(f"{sudo_password}\\n"); stdin.flush()
            output, errors = stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")
            if stdout.channel.recv_exit_status() != 0:
                raise RuntimeError(errors.strip() or "Không thể cấu hình quyền chia sẻ HDD. Tài khoản này cần quyền sudo.")
            return output
        finally:
            client.close()
    def check_hdd_access(self) -> dict:
        """Inspect effective access, groups and modes without changing the server."""
        root = shlex.quote(UPLOAD_DIRECTORY)
        command = " ".join([
            "printf 'ACCESS|'; if test -r " + root + " -a -x " + root + "; then printf 'yes\\n'; else printf 'no\\n'; fi;",
            "printf 'GROUPS|'; id -nG;",
            "printf 'PATH|'; stat -c '%a|%U|%G' " + root + " 2>&1 || true;",
            "printf 'ACL|'; getfacl -cp " + root + " 2>/dev/null | tr '\\n' ';' || true; printf '\\n';",
        ])
        result = {"access": False, "groups": "", "path": "", "acl": ""}
        for line in self.command(command).splitlines():
            key, _, value = line.partition("|")
            if key == "ACCESS": result["access"] = value.strip() == "yes"
            elif key == "GROUPS": result["groups"] = value.strip()
            elif key == "PATH": result["path"] = value.strip()
            elif key == "ACL": result["acl"] = value.strip()
        return result
    @staticmethod
    def _command_on_client(client, command: str) -> str:
        _, stdout, stderr = client.exec_command(command, timeout=20)
        text, errors = stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")
        if stdout.channel.recv_exit_status() != 0: raise RuntimeError(errors.strip() or "Lệnh SSH thất bại.")
        return text
    @staticmethod
    def ensure_writable_directory(client, directory: str):
        command = f"test -d {shlex.quote(directory)} && test -w {shlex.quote(directory)} && test -x {shlex.quote(directory)} || {{ echo 'Tài khoản hiện tại không có quyền ghi vào thư mục này.' >&2; exit 1; }}"
        SshService._command_on_client(client, command)
    def status(self) -> dict:
        # Same model as the Electron version: one SSH command produces one
        # complete status snapshot; the UI updates only after it is parsed.
        return parse_status(self.command(STATUS_COMMAND))
    @staticmethod
    def safe_storage_path(relative_path: str) -> str:
        normalized = str(relative_path or "").replace("\\", "/").strip("/")
        if not normalized: return ""
        parts = PurePosixPath(normalized).parts
        if any(part in {".", ".."} or "\x00" in part for part in parts):
            raise RuntimeError("Đường dẫn kho dữ liệu không hợp lệ.")
        return "/".join(parts)
    @staticmethod
    def storage_location(location: str) -> dict:
        try: return STORAGE_LOCATIONS[location]
        except KeyError as error: raise RuntimeError("Vị trí lưu trữ không hợp lệ.") from error
    def storage_root(self, location: str, client=None) -> str:
        configured_root = self.storage_location(location)["root"]
        if location != "ssd": return configured_root
        if client:
            root = self._command_on_client(client, "pwd -P").strip()
        else:
            root = self.command("pwd -P").strip()
        if not root.startswith("/"):
            raise RuntimeError("Không xác định được thư mục home của tài khoản SSH.")
        return root
    def list_storage(self, location: str, relative_path: str = "") -> dict:
        relative_path = self.safe_storage_path(relative_path)
        client = self.connect()
        try:
            root = self.storage_root(location, client)
            remote_directory = f"{root}/{relative_path}" if relative_path else root
            if location == "hdd" and relative_path == ".trash":
                try: self._command_on_client(client, f"mkdir -p -- {shlex.quote(remote_directory)}")
                except RuntimeError as error: raise RuntimeError("STORAGE_ACCESS_DENIED: Tài khoản này không có quyền mở thùng rác trên HDD.") from error
            sftp = client.open_sftp(); entries = []
            try: raw_entries = sftp.listdir_attr(remote_directory)
            except FileNotFoundError as error:
                raise RuntimeError(f"Không tìm thấy thư mục {remote_directory} trên {self.storage_location(location)['label']}.") from error
            except PermissionError as error:
                raise RuntimeError(f"STORAGE_ACCESS_DENIED: Tài khoản {self.username} không có quyền truy cập {remote_directory}.") from error
            for item in raw_entries:
                if item.filename in {".", ".."}: continue
                entries.append({"name": item.filename, "is_dir": stat.S_ISDIR(item.st_mode), "size": item.st_size, "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(item.st_mtime))})
            sftp.close()
            entries.sort(key=lambda item: (not item["is_dir"], item["name"].lower()))
            return {"location": location, "root": root, "path": relative_path, "entries": entries}
        finally: client.close()
    def list_data_tree(self, location: str) -> dict:
        """Read-only folder overview for the selected storage location."""
        root = self.storage_root(location)
        output = self.command(f"find {shlex.quote(root)} -mindepth 1 -maxdepth 3 -type d -printf '%P\\n' 2>/dev/null | sort | head -n 160")
        return {"location": location, "root": root, "paths": [line for line in output.splitlines() if line.strip()]}
    def upload(self, paths: list[str], relative_path: str = "", progress: Callable[[dict], None] | None = None) -> list[dict]:
        relative_path = self.safe_storage_path(relative_path)
        destination = f"{UPLOAD_DIRECTORY}/{relative_path}" if relative_path else UPLOAD_DIRECTORY
        total_bytes = sum(Path(local).stat().st_size for local in paths); transferred_by_file: dict[int, int] = {}; progress_lock = Lock(); last_report = 0.0
        def report(index: int, transferred: int, _file_total: int):
            nonlocal last_report
            if not progress: return
            now = time.monotonic()
            with progress_lock:
                transferred_by_file[index] = transferred
                if transferred < _file_total and now - last_report < 0.25: return
                last_report = now; completed = sum(transferred_by_file.values())
            progress({"completed": completed, "total": total_bytes})
        client = self.connect()
        try:
            _, stdout, stderr = client.exec_command(f"mkdir -p -- {shlex.quote(destination)}", timeout=20)
            if stdout.channel.recv_exit_status() != 0: raise RuntimeError(stderr.read().decode("utf-8", "replace") or "Không thể tạo thư mục đích.")
            self.ensure_writable_directory(client, destination)
        finally: client.close()
        def upload_one(item: tuple[int, str]) -> dict:
            index, local = item
            transfer_client = self.connect()
            try:
                sftp = transfer_client.open_sftp()
                name = Path(local).name.replace(" ", "_")
                remote_path = f"{destination}/{time.time_ns()}-{index}-{name}"
                temporary_path = f"{remote_path}.part"
                local_size = Path(local).stat().st_size
                try:
                    sftp.put(local, temporary_path, callback=lambda transferred, file_total: report(index, transferred, file_total))
                    # A completed SFTP transfer is not enough feedback for the UI:
                    # verify the exact remote object before exposing it in the folder.
                    remote_size = sftp.stat(temporary_path).st_size
                    if remote_size != local_size: raise RuntimeError(f"Tệp {name} có dung lượng không khớp sau khi tải lên.")
                    sftp.rename(temporary_path, remote_path)
                except Exception:
                    try: sftp.remove(temporary_path)
                    except Exception: pass
                    raise
                sftp.close(); return {"name": name, "remote_path": remote_path, "size": remote_size}
            finally: transfer_client.close()
        items = list(enumerate(paths))
        if len(items) == 1: return [upload_one(items[0])]
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_TRANSFERS, len(items)), thread_name_prefix="sftp-upload") as executor:
            return list(executor.map(upload_one, items))
    def upload_folder(self, local_folder: str, relative_path: str = "") -> list[dict]:
        root = Path(local_folder)
        if not root.is_dir(): raise RuntimeError("Thư mục trên laptop không hợp lệ.")
        relative_path = self.safe_storage_path(relative_path)
        destination = f"{UPLOAD_DIRECTORY}/{relative_path}" if relative_path else UPLOAD_DIRECTORY
        files = [item for item in root.rglob("*") if item.is_file()]
        if not files: raise RuntimeError("Thư mục được chọn không có tệp để tải lên.")
        if len(files) > 500: raise RuntimeError("Mỗi lần chỉ tải tối đa 500 tệp trong một thư mục.")
        if any(item.stat().st_size > 2 * 1024 * 1024 * 1024 for item in files): raise RuntimeError("Một hoặc nhiều tệp vượt quá 2 GB.")
        client = self.connect()
        try:
            _, stdout, stderr = client.exec_command(f"mkdir -p -- {shlex.quote(destination)}", timeout=20)
            if stdout.channel.recv_exit_status() != 0: raise RuntimeError(stderr.read().decode("utf-8", "replace") or "Không thể tạo thư mục đích.")
            self.ensure_writable_directory(client, destination)
            sftp = client.open_sftp(); uploaded = []; made_directories = set()
            for local_file in files:
                child_path = local_file.relative_to(root).as_posix(); parent = str(PurePosixPath(child_path).parent)
                if parent != "." and parent not in made_directories:
                    remote_parent = f"{destination}/{parent}"
                    self._command_on_client(client, f"mkdir -p -- {shlex.quote(remote_parent)}")
                    made_directories.add(parent)
                remote_path = f"{destination}/{child_path}"; local_size = local_file.stat().st_size
                sftp.put(str(local_file), remote_path); remote_size = sftp.stat(remote_path).st_size
                if remote_size != local_size: raise RuntimeError(f"Tệp {child_path} có dung lượng không khớp sau khi tải lên.")
                uploaded.append({"name": child_path, "remote_path": remote_path, "size": remote_size})
            sftp.close(); return uploaded
        finally: client.close()
    @staticmethod
    def entry_name(value: str) -> str:
        value = str(value or "").strip()
        if not value or value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
            raise RuntimeError("Tên tệp hoặc thư mục không hợp lệ.")
        return value
    def create_folder(self, relative_path: str, name: str):
        relative_path = self.safe_storage_path(relative_path); name = self.entry_name(name)
        target = f"{UPLOAD_DIRECTORY}/{relative_path}/{name}" if relative_path else f"{UPLOAD_DIRECTORY}/{name}"
        client = self.connect()
        try:
            sftp = client.open_sftp(); sftp.mkdir(target)
            created = sftp.stat(target)
            if not stat.S_ISDIR(created.st_mode): raise RuntimeError("Đường dẫn vừa tạo không phải là thư mục.")
            sftp.close(); return {"name": name, "path": target}
        finally: client.close()
    def rename_storage_entry(self, relative_path: str, old_name: str, new_name: str):
        relative_path = self.safe_storage_path(relative_path); old_name = self.entry_name(old_name); new_name = self.entry_name(new_name)
        directory = f"{UPLOAD_DIRECTORY}/{relative_path}" if relative_path else UPLOAD_DIRECTORY
        client = self.connect()
        try:
            sftp = client.open_sftp()
            try:
                sftp.stat(f"{directory}/{new_name}")
                raise RuntimeError("Tên mới đã tồn tại trong thư mục này.")
            except FileNotFoundError:
                pass
            sftp.rename(f"{directory}/{old_name}", f"{directory}/{new_name}"); sftp.close()
        finally: client.close()
    def trash_storage_entries(self, relative_path: str, names: list[str]) -> int:
        relative_path = self.safe_storage_path(relative_path); names = [self.entry_name(name) for name in names]
        if not names: raise RuntimeError("Hãy chọn ít nhất một mục để chuyển vào thùng rác.")
        directory = f"{UPLOAD_DIRECTORY}/{relative_path}" if relative_path else UPLOAD_DIRECTORY
        trash = f"{UPLOAD_DIRECTORY}/.trash"
        client = self.connect()
        try:
            _, stdout, stderr = client.exec_command(f"mkdir -p -- {shlex.quote(trash)}", timeout=20)
            if stdout.channel.recv_exit_status() != 0: raise RuntimeError(stderr.read().decode("utf-8", "replace") or "Không thể mở thùng rác trên server.")
            sftp = client.open_sftp()
            for index, name in enumerate(names):
                sftp.rename(f"{directory}/{name}", f"{trash}/{time.time_ns()}-{index}-{name}")
            sftp.close(); return len(names)
        finally: client.close()
    def restore_trash_entries(self, names: list[str]) -> int:
        names = [self.entry_name(name) for name in names]
        if not names: raise RuntimeError("Hãy chọn ít nhất một mục để khôi phục.")
        trash = f"{UPLOAD_DIRECTORY}/.trash"; targets = []
        for name in names:
            prefix, separator, original_name = name.partition("-")
            if not separator or not prefix.isdigit() or not original_name: raise RuntimeError(f"Mục {name} không có thông tin khôi phục hợp lệ.")
            # New entries use timestamp-index-name; older entries used
            # timestamp-name, so retain compatibility with both formats.
            possible_index, second_separator, remainder = original_name.partition("-")
            if second_separator and possible_index.isdigit(): original_name = remainder
            targets.append(self.entry_name(original_name))
        if len(set(targets)) != len(targets): raise RuntimeError("Các mục khôi phục có tên đích trùng nhau.")
        client = self.connect()
        try:
            sftp = client.open_sftp()
            for target in targets:
                try: sftp.stat(f"{UPLOAD_DIRECTORY}/{target}"); raise RuntimeError(f"Không thể khôi phục vì {target} đã tồn tại trong kho HDD.")
                except FileNotFoundError: pass
            for name, target in zip(names, targets): sftp.rename(f"{trash}/{name}", f"{UPLOAD_DIRECTORY}/{target}")
            sftp.close(); return len(names)
        finally: client.close()
    def permanently_delete_trash_entries(self, names: list[str]) -> int:
        names = [self.entry_name(name) for name in names]
        if not names: raise RuntimeError("Hãy chọn ít nhất một mục để xóa vĩnh viễn.")
        trash = f"{UPLOAD_DIRECTORY}/.trash"; targets = [f"{trash}/{name}" for name in names]
        self.command(f"rm -rf -- {' '.join(shlex.quote(target) for target in targets)}")
        return len(names)
    def empty_trash(self) -> None:
        trash = f"{UPLOAD_DIRECTORY}/.trash"
        self.command(f"mkdir -p -- {shlex.quote(trash)}; find {shlex.quote(trash)} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +")
    def download_storage_entries(self, relative_path: str, names: list[str], local_directory: str, progress: Callable[[dict], None] | None = None) -> int:
        relative_path = self.safe_storage_path(relative_path)
        names = [self.entry_name(name) for name in names]
        destination = Path(local_directory)
        if not destination.is_dir(): raise RuntimeError("Thư mục lưu trên máy tính không hợp lệ.")
        remote_directory = f"{UPLOAD_DIRECTORY}/{relative_path}" if relative_path else UPLOAD_DIRECTORY
        reserved_paths: set[Path] = set(); transfers = []
        for name in names:
            candidate = destination / name; index = 1
            while candidate.exists() or candidate in reserved_paths:
                candidate = destination / f"{Path(name).stem} ({index}){Path(name).suffix}"; index += 1
            reserved_paths.add(candidate); transfers.append((name, candidate))
        size_client = self.connect()
        try:
            size_sftp = size_client.open_sftp(); sizes = [size_sftp.stat(f"{remote_directory}/{name}").st_size for name, _ in transfers]; size_sftp.close()
        finally: size_client.close()
        total_bytes = sum(sizes); transferred_by_file: dict[int, int] = {}; progress_lock = Lock(); last_report = 0.0
        def report(index: int, transferred: int, file_total: int):
            nonlocal last_report
            if not progress: return
            now = time.monotonic()
            with progress_lock:
                transferred_by_file[index] = transferred
                if transferred < file_total and now - last_report < 0.25: return
                last_report = now; completed = sum(transferred_by_file.values())
            progress({"completed": completed, "total": total_bytes})
        def download_one(item: tuple[int, tuple[str, Path]]):
            index, (name, local_path) = item; transfer_client = self.connect()
            try:
                sftp = transfer_client.open_sftp(); temporary_path = local_path.with_name(f"{local_path.name}.part")
                try:
                    sftp.get(f"{remote_directory}/{name}", str(temporary_path), callback=lambda transferred, file_total: report(index, transferred, file_total)); temporary_path.replace(local_path)
                except Exception:
                    try: temporary_path.unlink(missing_ok=True)
                    except OSError: pass
                    raise
                sftp.close()
            finally: transfer_client.close()
        items = list(enumerate(transfers))
        if len(items) == 1: download_one(items[0]); return 1
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_TRANSFERS, len(transfers)), thread_name_prefix="sftp-download") as executor:
            list(executor.map(download_one, items))
        return len(transfers)
    def download_storage_folder(self, relative_path: str, name: str, local_directory: str) -> int:
        """Copy one selected HDD folder recursively without following symlinks."""
        relative_path = self.safe_storage_path(relative_path); name = self.entry_name(name)
        destination_root = Path(local_directory)
        if not destination_root.is_dir(): raise RuntimeError("Thư mục lưu trên máy tính không hợp lệ.")
        remote_parent = f"{UPLOAD_DIRECTORY}/{relative_path}" if relative_path else UPLOAD_DIRECTORY
        client = self.connect()
        try:
            sftp = client.open_sftp(); remote_source = f"{remote_parent}/{name}"
            if not stat.S_ISDIR(sftp.stat(remote_source).st_mode): raise RuntimeError("Mục đã chọn không phải là thư mục.")
            local_target = destination_root / name; index = 1
            while local_target.exists():
                local_target = destination_root / f"{name} ({index})"; index += 1
            copied = 0
            def copy_directory(remote_directory: str, local_directory_path: Path):
                nonlocal copied
                local_directory_path.mkdir(parents=True, exist_ok=False)
                for item in sftp.listdir_attr(remote_directory):
                    remote_item = f"{remote_directory}/{item.filename}"
                    if stat.S_ISDIR(item.st_mode): copy_directory(remote_item, local_directory_path / item.filename)
                    elif stat.S_ISREG(item.st_mode):
                        sftp.get(remote_item, str(local_directory_path / item.filename)); copied += 1
            copy_directory(remote_source, local_target); sftp.close(); return copied
        finally: client.close()


class PinDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Bảo mật ứng dụng"); self.setModal(True); self.setMinimumWidth(390)
        layout = QVBoxLayout(self); layout.setSpacing(12)
        layout.addWidget(QLabel("MỞ KHÓA SERVER MONITOR", objectName="subtitle")); self.title = QLabel(); self.title.setObjectName("pageTitle"); layout.addWidget(self.title)
        self.description = QLabel(); self.description.setWordWrap(True); self.description.setObjectName("muted"); layout.addWidget(self.description)
        self.pin = QLineEdit(); self.pin.setEchoMode(QLineEdit.Password); self.pin.setPlaceholderText("PIN gồm 6–12 chữ số")
        self.confirm = QLineEdit(); self.confirm.setEchoMode(QLineEdit.Password); self.confirm.setPlaceholderText("Nhập lại PIN")
        self.form = QFormLayout(); self.form.addRow("PIN", self.pin); self.form.addRow("Xác nhận", self.confirm); layout.addLayout(self.form)
        self.error = QLabel(); self.error.setStyleSheet("color: #fca5a5;"); layout.addWidget(self.error)
        self.submit = QPushButton(); self.submit.setObjectName("primary"); self.submit.clicked.connect(self.validate); layout.addWidget(self.submit)
        self.setup = not SECURITY_FILE.exists(); self.configure()
    def configure(self):
        self.title.setText("Tạo PIN bảo vệ" if self.setup else "Mở khóa ứng dụng")
        self.description.setText("PIN được lưu dưới dạng hash trên laptop này. PIN không phải mật khẩu SSH.")
        # Hide the entire confirmation row after a PIN has already been made.
        self.form.setRowVisible(self.confirm, self.setup)
        self.submit.setText("Tạo PIN" if self.setup else "Mở khóa")
    def validate(self):
        pin = self.pin.text()
        if self.setup:
            if not (pin.isdigit() and 6 <= len(pin) <= 12 and pin == self.confirm.text()): self.error.setText("PIN phải có 6–12 chữ số và khớp xác nhận."); return
            APP_DIRECTORY.mkdir(parents=True, exist_ok=True); salt = os.urandom(16)
            digest = hashlib.scrypt(pin.encode(), salt=salt, n=2**14, r=8, p=1).hex()
            SECURITY_FILE.write_text(json.dumps({"salt": salt.hex(), "hash": digest}), encoding="utf-8"); self.accept(); return
        try:
            config = json.loads(SECURITY_FILE.read_text(encoding="utf-8")); digest = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(config["salt"]), n=2**14, r=8, p=1).hex()
            if digest == config["hash"]: self.accept()
            else: self.error.setText("PIN không đúng.")
        except Exception: self.error.setText("Không thể đọc cấu hình bảo mật.")


class ChangePinDialog(QDialog):
    """Require the current local PIN before replacing its scrypt hash."""
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Đổi mã PIN"); self.setModal(True); self.setMinimumWidth(410)
        layout = QVBoxLayout(self); layout.addWidget(QLabel("ĐỔI MÃ PIN ỨNG DỤNG", objectName="pageTitle")); note = QLabel("PIN mới gồm 6–12 chữ số. PIN SSH không bị thay đổi.", objectName="muted"); note.setWordWrap(True); layout.addWidget(note)
        self.current = QLineEdit(); self.current.setEchoMode(QLineEdit.Password); self.new = QLineEdit(); self.new.setEchoMode(QLineEdit.Password); self.confirm = QLineEdit(); self.confirm.setEchoMode(QLineEdit.Password)
        form = QFormLayout(); form.addRow("PIN hiện tại", self.current); form.addRow("PIN mới", self.new); form.addRow("Nhập lại PIN mới", self.confirm); layout.addLayout(form)
        self.error = QLabel(); self.error.setStyleSheet("color:#c02f3c;"); layout.addWidget(self.error); save = QPushButton("Lưu PIN mới", objectName="primary"); save.clicked.connect(self.change_pin); self.confirm.returnPressed.connect(self.change_pin); layout.addWidget(save)
    def change_pin(self):
        new_pin = self.new.text()
        if not (new_pin.isdigit() and 6 <= len(new_pin) <= 12 and new_pin == self.confirm.text()): self.error.setText("PIN mới phải có 6–12 chữ số và khớp xác nhận."); return
        try:
            config = json.loads(SECURITY_FILE.read_text(encoding="utf-8")); current_hash = hashlib.scrypt(self.current.text().encode(), salt=bytes.fromhex(config["salt"]), n=2**14, r=8, p=1).hex()
            if current_hash != config["hash"]: self.error.setText("PIN hiện tại không đúng."); return
            salt = os.urandom(16); digest = hashlib.scrypt(new_pin.encode(), salt=salt, n=2**14, r=8, p=1).hex()
            SECURITY_FILE.write_text(json.dumps({"salt": salt.hex(), "hash": digest}), encoding="utf-8"); self.accept()
        except Exception: self.error.setText("Không thể cập nhật cấu hình PIN.")


class StorageRing(QWidget):
    """Small read-only storage visualization for the overview dashboard."""
    def __init__(self):
        super().__init__(); self.used = 0; self.total = 0; self.setMinimumSize(150, 150)
    def set_values(self, used: int, total: int):
        self.used, self.total = used, total; self.update()
    def paintEvent(self, _event):
        side = min(self.width(), self.height()) - 18
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#e7edf5"), 12, Qt.SolidLine, Qt.RoundCap)); painter.drawArc(rect, 0, 360 * 16)
        ratio = min(1, self.used / self.total) if self.total else 0
        painter.setPen(QPen(QColor("#0967e8"), 12, Qt.SolidLine, Qt.RoundCap)); painter.drawArc(rect, 90 * 16, -int(360 * ratio * 16))
        painter.setPen(QColor("#15233e")); painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, f"{fmt_bytes(self.used)}\n/ {fmt_bytes(self.total)}")


class PerformanceChart(QWidget):
    """In-session CPU, RAM, and disk history; samples are captured on refresh."""
    def __init__(self):
        super().__init__(); self.samples = []; self.setMinimumHeight(185)
    def add_sample(self, cpu: int, ram: int, disk: int):
        self.samples.append((cpu, ram, disk)); self.samples = self.samples[-30:]; self.update()
    def paintEvent(self, _event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing); area = self.rect().adjusted(38, 14, -12, -28)
        painter.setFont(QFont("Segoe UI", 9)); painter.setPen(QColor("#90a0b8"))
        for value in range(0, 101, 25):
            y = area.bottom() - area.height() * value / 100; painter.drawLine(area.left(), int(y), area.right(), int(y)); painter.drawText(1, int(y) + 4, f"{value}%")
        if len(self.samples) < 2:
            painter.drawText(area, Qt.AlignCenter, "Dữ liệu hiệu năng sẽ xuất hiện sau các lần làm mới."); return
        colors = (QColor("#0967e8"), QColor("#12a66a"), QColor("#f59e0b"))
        for series, color in enumerate(colors):
            points = [QPointF(area.left() + area.width() * index / (len(self.samples) - 1), area.bottom() - area.height() * sample[series] / 100) for index, sample in enumerate(self.samples)]
            painter.setPen(QPen(color, 2)); painter.drawPolyline(points)
        painter.setPen(QColor("#71819a")); painter.drawText(area.left(), self.height() - 6, "Lần làm mới cũ hơn"); painter.drawText(area.right() - 115, self.height() - 6, "Hiện tại")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.ssh = SshService(); self.pool = QThreadPool.globalInstance(); self._workers = set(); self._status_refreshing = False; self.ssh_login_attempts = 0; self.transfer_started_at = None; self.transfer_kind = ""; self.last_transfer_message = ""; self.storage_permission_message = ""; self.setWindowTitle(f"DataArchive · Server Monitor {APP_VERSION}"); self.resize(1440, 900); self.setMinimumSize(1080, 700)
        root = QWidget(); self.setCentralWidget(root); layout = QHBoxLayout(root); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        sidebar = self.make_sidebar(); layout.addWidget(sidebar)
        content = QWidget(); content_layout = QVBoxLayout(content); content_layout.setContentsMargins(0, 0, 0, 0); content_layout.setSpacing(0); content_layout.addWidget(self.make_topbar())
        self.pages = QStackedWidget(); content_layout.addWidget(self.pages, 1); layout.addWidget(content, 1)
        self.dashboard = self.make_dashboard(); self.storage = self.make_storage(); self.terminal = self.make_terminal(); self.settings = self.make_settings()
        self.pages.addWidget(self.make_scroll_page(self.dashboard)); self.pages.addWidget(self.make_scroll_page(self.storage)); self.pages.addWidget(self.make_scroll_page(self.terminal)); self.pages.addWidget(self.make_scroll_page(self.settings))
        self.logs.setPlainText("Đang chuẩn bị kết nối SSH…")
        # Ask for SSH credentials once after the PIN dialog, before any
        # dashboard refresh. They remain in memory for this app session only.
        self.status_refresh_timer = QTimer(self); self.status_refresh_timer.setInterval(5 * 60 * 1000); self.status_refresh_timer.timeout.connect(self.refresh_status)
        QTimer.singleShot(0, self.refresh_status)
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # On compact windows, removing the global search prevents the account
        # chip and header actions from being compressed or clipped.
        if hasattr(self, "global_search"):
            self.global_search.setVisible(self.width() >= 1260)
    @staticmethod
    def make_scroll_page(page):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded); scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding); scroll.setWidget(page)
        return scroll
    def make_sidebar(self):
        side = QFrame(objectName="sidebar"); side.setFixedWidth(248); box = QVBoxLayout(side); box.setContentsMargins(16, 24, 16, 18); box.setSpacing(5)
        brand_row = QHBoxLayout(); logo = QLabel("☁"); logo.setStyleSheet("color:#2c88ff; font-size:31px;"); brand_row.addWidget(logo); names = QVBoxLayout(); names.addWidget(QLabel("DataArchive", objectName="brand")); names.addWidget(QLabel("Kho dữ liệu máy chủ", objectName="subtitle")); brand_row.addLayout(names); brand_row.addStretch(); box.addLayout(brand_row); box.addSpacing(26)
        self.nav_buttons = []
        for text, page in [("▣   Tổng quan", 0), ("▤   Kho lưu trữ", 1), ("⌘   PowerShell", 2), ("⚙   Cài đặt", 3)]:
            button = QPushButton(text, objectName="nav"); button.setCheckable(True); button.setChecked(page == 0); button.clicked.connect(lambda checked=False, index=page: self.select_page(index)); self.nav_buttons.append(button); box.addWidget(button)
        self.trash_nav_button = QPushButton("🗑   Thùng rác", objectName="nav"); self.trash_nav_button.clicked.connect(self.open_trash); box.addWidget(self.trash_nav_button)
        box.addStretch(); capacity = QFrame(objectName="storageCard"); capacity.setStyleSheet("QFrame#storageCard { background:#0b376f; border-color:#24558f; } QLabel { color:#dbeaff; }"); capacity_box = QVBoxLayout(capacity); capacity_box.addWidget(QLabel("DUNG LƯỢNG LƯU TRỮ")); self.sidebar_storage = QLabel("— / —"); self.sidebar_storage.setStyleSheet("font-size:17px; font-weight:800; color:white;"); capacity_box.addWidget(self.sidebar_storage); self.sidebar_bar = QProgressBar(); self.sidebar_bar.setRange(0, 100); self.sidebar_bar.setTextVisible(False); capacity_box.addWidget(self.sidebar_bar); box.addWidget(capacity)
        box.addSpacing(8); self.connection = QLabel("● Chưa kết nối", objectName="status"); self.connection.setStyleSheet("background:#123f76; color:#cce3ff;"); box.addWidget(self.connection); return side
    def make_topbar(self):
        top = QFrame(objectName="topbar"); top.setFixedHeight(88); row = QHBoxLayout(top); row.setContentsMargins(30, 14, 30, 14); row.setSpacing(16)
        labels = QVBoxLayout(); labels.setSpacing(1); labels.addWidget(QLabel("Tổng quan", objectName="topTitle")); labels.addWidget(QLabel("Theo dõi và quản lý dữ liệu trên server", objectName="muted")); row.addLayout(labels); row.addStretch()
        self.global_search = QLineEdit(); self.global_search.setPlaceholderText("⌕  Tìm kiếm dữ liệu, tài liệu…"); self.global_search.setMinimumWidth(220); self.global_search.setMaximumWidth(360); self.global_search.returnPressed.connect(self.open_storage_search); row.addWidget(self.global_search)
        actions = QHBoxLayout(); actions.setSpacing(10)
        self.account_chip = QFrame(objectName="accountChip"); self.account_chip.setFixedWidth(168); self.account_chip.setFixedHeight(52); self.account_chip.setToolTip("Tài khoản SSH đang sử dụng"); chip_layout = QHBoxLayout(self.account_chip); chip_layout.setContentsMargins(8, 6, 10, 6); chip_layout.setSpacing(8)
        self.account_avatar = QLabel("?"); self.account_avatar.setObjectName("accountAvatar"); self.account_avatar.setFixedSize(34, 34); self.account_avatar.setAlignment(Qt.AlignCenter); chip_layout.addWidget(self.account_avatar)
        account_text = QVBoxLayout(); account_text.setContentsMargins(0, 0, 0, 0); account_text.setSpacing(1); self.account_label = QLabel("Chưa đăng nhập", objectName="accountName"); self.account_state = QLabel("● Chưa kết nối", objectName="accountState"); account_text.addWidget(self.account_label); account_text.addWidget(self.account_state); chip_layout.addLayout(account_text, 1); actions.addWidget(self.account_chip)
        self.header_refresh = QPushButton("↻  Làm mới", objectName="primary"); self.header_refresh.setToolTip("Làm mới trạng thái server"); self.header_refresh.clicked.connect(self.refresh_status); actions.addWidget(self.header_refresh); self.logout_button = QPushButton("Đăng xuất"); self.logout_button.setDisabled(True); self.logout_button.clicked.connect(self.logout_ssh); actions.addWidget(self.logout_button); row.addLayout(actions); return top
    def select_page(self, index):
        self.pages.setCurrentIndex(index)
        for position, button in enumerate(self.nav_buttons): button.setChecked(position == index)
        if index == 1: QTimer.singleShot(0, self.refresh_files)
    def open_storage_search(self):
        self.select_page(1); self.storage_search.setText(self.global_search.text()); self.storage_search.setFocus()
    def set_account_identity(self, username: str | None = None):
        if username:
            self.account_avatar.setText(username[:1].upper()); self.account_label.setText(username); self.account_state.setText("● Đang hoạt động")
            self.account_chip.setStyleSheet("background:#f5fbf8; border:1px solid #bfe6cf; border-radius:12px;")
            self.account_avatar.setStyleSheet("background:#d9f4e3; color:#137a46; border-radius:16px; font-size:15px; font-weight:800;")
            if hasattr(self, "settings_avatar"):
                self.settings_avatar.setText(username[:1].upper()); self.settings_account.setText(username); self.settings_session_badge.setText("Đang hoạt động")
        else:
            self.account_avatar.setText("?"); self.account_label.setText("Chưa đăng nhập"); self.account_state.setText("● Chưa kết nối")
            self.account_chip.setStyleSheet("background:#f8fbff; border:1px solid #dce7f4; border-radius:12px;")
            self.account_avatar.setStyleSheet("background:#dbeafe; color:#1764cc; border-radius:16px; font-size:15px; font-weight:800;")
            if hasattr(self, "settings_avatar"):
                self.settings_avatar.setText("?"); self.settings_account.setText("Chưa đăng nhập SSH"); self.settings_session_badge.setText("Chưa kết nối")
    def logout_ssh(self):
        if self._workers:
            QMessageBox.information(self, "Đang có thao tác", "Hãy chờ các tác vụ SSH đang chạy hoàn tất trước khi đăng xuất."); return
        self.ssh.clear_credentials(); self.ssh.username = SERVER["username"]; self.ssh.auth_method = "password"; self.status_refresh_timer.stop(); self.logout_button.setDisabled(True)
        self.connection.setText("● Đã đăng xuất"); self.connection.setStyleSheet("background:#123f76; color:#cce3ff;")
        self.set_account_identity()
        self.settings_account.setText("Chưa đăng nhập SSH")
        self.logged_users.setText("Đăng nhập lại để xem các phiên SSH/SFTP."); self.storage_note.setText("Đăng nhập SSH để mở kho dữ liệu.")
    def open_change_pin(self):
        if ChangePinDialog(self).exec() == QDialog.Accepted:
            QMessageBox.information(self, "Đổi mã PIN", "Đã đổi mã PIN cục bộ thành công.")
    def configure_shared_hdd_access(self):
        if not self.ensure_ssh_credentials(): return
        answer = QMessageBox.question(self, "Chia sẻ HDD", "Thiết lập này cho huy1111 quyền xem/tải xuống và cấp thacsikhai quyền quản lý ngang servermonitor trên /data/uploads. Tiếp tục?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes: return
        sudo_password, accepted = QInputDialog.getText(self, "Xác nhận quyền sudo", f"Mật khẩu sudo của {self.ssh.username}:", QLineEdit.Password)
        if not accepted or not sudo_password: return
        self.shared_hdd_button.setDisabled(True); self.shared_hdd_note.setText("Đang cấu hình quyền truy cập HDD trên server…")
        def done(_result):
            self.shared_hdd_button.setDisabled(False); self.shared_hdd_note.setText("✓ Đã cập nhật quyền HDD: thacsikhai và servermonitor có thể quản lý; huy1111 chỉ xem/tải xuống.")
            if self.current_storage_location == "hdd": self.refresh_files(self.current_storage_path)
        def failed(message):
            self.shared_hdd_button.setDisabled(False); self.shared_hdd_note.setText("Không thể thay đổi quyền HDD."); self.show_error(f"Không thể cấu hình chia sẻ HDD: {message}")
        self.async_call(lambda: self.ssh.configure_shared_hdd_access(sudo_password), done, failed)
    def check_hdd_access(self):
        if not self.ensure_ssh_credentials(): return
        self.hdd_access_check_button.setDisabled(True); self.hdd_access_result.setText("Đang kiểm tra quyền HDD của tài khoản hiện tại…")
        def done(result):
            self.hdd_access_check_button.setDisabled(False)
            if result["access"]:
                role = "quản lý" if self.ssh.username in HDD_WRITE_ACCOUNTS else "chỉ đọc"
                self.hdd_access_result.setText(f"✓ {self.ssh.username} có quyền {role} trên HDD. Nhóm hiện tại: {result['groups']}")
            else:
                self.hdd_access_result.setText(f"✕ {self.ssh.username} chưa có quyền mở /data/uploads. Nhóm hiện tại: {result['groups'] or 'không xác định'}. Hãy chạy “Thiết lập quyền HDD” bằng tài khoản có sudo, sau đó đăng xuất và đăng nhập lại.")
        def failed(message):
            self.hdd_access_check_button.setDisabled(False); self.hdd_access_result.setText(f"Không thể kiểm tra quyền HDD: {message}")
        self.async_call(self.ssh.check_hdd_access, done, failed)
    def open_trash(self):
        if self.storage_location.currentData() != "hdd":
            self.storage_location.blockSignals(True); self.storage_location.setCurrentIndex(self.storage_location.findData("hdd")); self.storage_location.blockSignals(False)
            self.current_storage_location = "hdd"
        self.select_page(1); self.refresh_files(".trash")
    def change_dashboard_disk(self):
        self.update_dashboard_storage()
    def open_selected_storage(self):
        location = self.dashboard_disk_choice.currentData()
        if self.storage_location.currentData() != location:
            self.storage_location.setCurrentIndex(self.storage_location.findData(location))
        self.select_page(1); self.refresh_files("")
    def update_dashboard_storage(self):
        status = getattr(self, "last_status", None)
        if not status: return [0, 0]
        location = self.dashboard_disk_choice.currentData(); key = "DATA_DISK" if location == "hdd" else "DISK"; values = status.get(key, [0, 0]); total, used = values[0], values[1]
        label = "HDD dữ liệu · /data" if location == "hdd" else "SSD hệ thống · /"
        percent = int(used / total * 100) if total else 0
        self.dashboard_disk_title.setText(label); self.storage_ring.set_values(used, total); self.storage_used.setText(f"{fmt_bytes(used)} đã dùng"); self.storage_free.setText(f"Còn trống {fmt_bytes(max(0, total - used))} · {percent}%")
        self.sidebar_storage.setText(f"{fmt_bytes(used)} / {fmt_bytes(total)}"); self.sidebar_bar.setValue(percent)
        if hasattr(self, "metrics"): self.metrics["Dung lượng đã dùng"][0].setText(fmt_bytes(used))
        return [total, used]
    def page_shell(self, title, description, with_header=True):
        page = QWidget(); page.setMinimumWidth(760); box = QVBoxLayout(page); box.setContentsMargins(28, 26, 28, 28); box.setSpacing(18)
        if not with_header: return page, box, None
        top = QHBoxLayout(); top.setSpacing(16); labels = QVBoxLayout(); labels.addWidget(QLabel(title, objectName="pageTitle")); labels.addWidget(QLabel(description, objectName="muted")); top.addLayout(labels); top.addStretch(); page_button = QPushButton("↻  Làm mới"); page_button.setMinimumWidth(118); top.addWidget(page_button); box.addLayout(top); return page, box, page_button
    def metric_card(self, title, icon):
        card = QFrame(objectName="card"); card.setMinimumHeight(154); box = QVBoxLayout(card); heading = QHBoxLayout(); badge = QLabel(icon); badge.setAlignment(Qt.AlignCenter); badge.setFixedSize(38, 38); badge.setStyleSheet("background:#e8f1ff; color:#0967e8; border-radius:9px; font-size:19px;"); heading.addWidget(badge); heading.addWidget(QLabel(title, objectName="metricTitle")); heading.addStretch(); box.addLayout(heading); value = QLabel("—", objectName="metricValue"); value.setWordWrap(True); box.addWidget(value); note = QLabel("● Cập nhật khi kết nối", objectName="metricNote"); box.addWidget(note); return card, value, note
    @staticmethod
    def action_box(title, buttons):
        frame = QFrame(objectName="actionBox"); box = QVBoxLayout(frame); box.setContentsMargins(10, 8, 10, 10); box.setSpacing(6)
        box.addWidget(QLabel(title, objectName="actionTitle")); row = QHBoxLayout(); row.setSpacing(6)
        for button in buttons: row.addWidget(button)
        box.addLayout(row); return frame
    def make_dashboard(self):
        # The global top bar already owns the dashboard title and refresh
        # control, so the page itself deliberately has no duplicate header.
        page, box, _ = self.page_shell("Tổng quan", "", with_header=False); self.dashboard_refresh = self.header_refresh
        overview = QHBoxLayout(); overview.setSpacing(16); grid = QGridLayout(); grid.setHorizontalSpacing(16); grid.setVerticalSpacing(16); self.metrics = {}
        for index, (name, icon) in enumerate([("Thời gian hoạt động", "◷"), ("CPU tải", "⌁"), ("Dung lượng đã dùng", "▣"), ("Cập nhật chờ", "↟")]):
            card, value, note = self.metric_card(name, icon); self.metrics[name] = (value, note); grid.addWidget(card, index // 2, index % 2)
        overview.addLayout(grid, 3); storage = QFrame(objectName="panel"); storage_box = QVBoxLayout(storage); storage_heading = QHBoxLayout(); self.dashboard_disk_title = QLabel("Dung lượng HDD", objectName="metricTitle"); storage_heading.addWidget(self.dashboard_disk_title); storage_heading.addStretch(); self.dashboard_disk_choice = QComboBox(); self.dashboard_disk_choice.addItem("HDD dữ liệu", "hdd"); self.dashboard_disk_choice.addItem("SSD hệ thống", "ssd"); self.dashboard_disk_choice.currentIndexChanged.connect(self.change_dashboard_disk); storage_heading.addWidget(self.dashboard_disk_choice); storage_box.addLayout(storage_heading); ring_row = QHBoxLayout(); self.storage_ring = StorageRing(); ring_row.addWidget(self.storage_ring); details = QVBoxLayout(); self.storage_used = QLabel("—", objectName="metricValue"); self.storage_free = QLabel("Đang chờ dữ liệu", objectName="muted"); details.addWidget(self.storage_used); details.addWidget(self.storage_free); open_storage = QPushButton("Mở kho đã chọn"); open_storage.clicked.connect(self.open_selected_storage); details.addWidget(open_storage); details.addStretch(); ring_row.addLayout(details); storage_box.addLayout(ring_row); overview.addWidget(storage, 2); box.addLayout(overview)
        activity_row = QHBoxLayout(); activity_row.setSpacing(16)
        performance = QFrame(objectName="panel"); performance_box = QVBoxLayout(performance); heading = QHBoxLayout(); heading.addWidget(QLabel("Hiệu năng hệ thống", objectName="metricTitle")); heading.addStretch(); heading.addWidget(QLabel("CPU  ·  RAM  ·  Ổ dữ liệu", objectName="muted")); performance_box.addLayout(heading); self.performance_chart = PerformanceChart(); performance_box.addWidget(self.performance_chart); activity_row.addWidget(performance, 3)
        alerts = QFrame(objectName="panel"); alerts_box = QVBoxLayout(alerts); alerts_box.addWidget(QLabel("Cảnh báo gần đây", objectName="metricTitle")); self.alert_list = QVBoxLayout(); self.alert_list.setSpacing(7); alerts_box.addLayout(self.alert_list); alerts_box.addStretch(); activity_row.addWidget(alerts, 2); box.addLayout(activity_row)
        health_row = QHBoxLayout(); health_row.setSpacing(16); health = QFrame(objectName="panel"); hbox = QHBoxLayout(health); self.health = QLabel("Chưa có dữ liệu"); self.health.setWordWrap(True); hbox.addWidget(self.health); health_row.addWidget(health, 3)
        users = QFrame(objectName="panel"); users_box = QVBoxLayout(users); users_box.addWidget(QLabel("Phiên SSH/SFTP đang hoạt động", objectName="metricTitle")); self.logged_users = QLabel("Đang chờ dữ liệu phiên SSH/SFTP…", objectName="muted"); self.logged_users.setWordWrap(True); self.logged_users.setTextInteractionFlags(Qt.TextSelectableByMouse); users_box.addWidget(self.logged_users); health_row.addWidget(users, 2); box.addLayout(health_row)
        info = QFrame(objectName="panel"); ibox = QFormLayout(info); self.os = QLabel("—"); self.kernel = QLabel("—"); self.updated = QLabel("—"); ibox.addRow("Hệ điều hành", self.os); ibox.addRow("Kernel", self.kernel); ibox.addRow("Cập nhật", self.updated); box.addWidget(info)
        logs = QFrame(objectName="panel"); lbox = QVBoxLayout(logs); lbox.addWidget(QLabel("Nhật ký lỗi gần nhất")); self.logs = QPlainTextEdit(); self.logs.setReadOnly(True); self.logs.setMinimumHeight(175); lbox.addWidget(self.logs); box.addWidget(logs, 1); return page
    def make_storage(self):
        page, box, refresh = self.page_shell("Kho dữ liệu", "Chọn HDD hoặc SSD để xem dữ liệu qua SFTP"); refresh.hide()
        self.current_storage_path = ""; self.current_storage_location = "hdd"; self.selected_upload_paths = []
        location_row = QHBoxLayout(); location_row.addWidget(QLabel("Vị trí dữ liệu", objectName="metricTitle"))
        self.storage_location = QComboBox(); self.storage_location.addItem("HDD dữ liệu  ·  /data/uploads", "hdd"); self.storage_location.addItem("SSD hệ thống  ·  home SSH (chỉ xem)", "ssd")
        self.storage_location.currentIndexChanged.connect(self.change_storage_location); location_row.addWidget(self.storage_location); location_row.addStretch(); box.addLayout(location_row)
        up = QPushButton("Thư mục cha"); up.clicked.connect(self.go_storage_up); reload = QPushButton("Làm mới"); reload.clicked.connect(self.refresh_files)
        create = QPushButton("Tạo thư mục"); create.clicked.connect(self.create_storage_folder)
        rename = QPushButton("Đổi tên"); rename.clicked.connect(self.rename_storage_selection); self.delete_button = QPushButton("Chuyển vào thùng rác", objectName="danger"); self.delete_button.clicked.connect(self.delete_storage_selection)
        self.download_menu_button = QToolButton(); self.download_menu_button.setText("Tải xuống"); self.download_menu_button.setToolTip("Chọn tải tệp đã chọn hoặc thư mục đã chọn"); self.download_menu_button.setToolButtonStyle(Qt.ToolButtonTextOnly); self.download_menu_button.setPopupMode(QToolButton.InstantPopup)
        download_menu = QMenu(self.download_menu_button); self.download_files_action = download_menu.addAction("Tải tệp đã chọn"); self.download_files_action.triggered.connect(self.download_storage_selection); self.download_folder_action = download_menu.addAction("Tải thư mục đã chọn"); self.download_folder_action.triggered.connect(self.download_storage_folder_selection); self.download_menu_button.setMenu(download_menu)
        self.upload_menu_button = QToolButton(objectName="primary"); self.upload_menu_button.setText("Tải lên"); self.upload_menu_button.setToolTip("Chọn tệp hoặc thư mục để tải lên"); self.upload_menu_button.setToolButtonStyle(Qt.ToolButtonTextOnly); self.upload_menu_button.setPopupMode(QToolButton.InstantPopup)
        upload_menu = QMenu(self.upload_menu_button); self.choose_upload_action = upload_menu.addAction("Chọn tệp để tải lên…"); self.choose_upload_action.triggered.connect(self.select_upload_files); self.confirm_upload_action = upload_menu.addAction("Tải tệp đã chọn"); self.confirm_upload_action.triggered.connect(self.upload_files); upload_menu.addSeparator(); self.choose_folder_upload_action = upload_menu.addAction("Chọn thư mục để tải lên…"); self.choose_folder_upload_action.triggered.connect(self.select_upload_folder); self.upload_menu_button.setMenu(upload_menu)
        self.trash_menu_button = QToolButton(); self.trash_menu_button.setText("Thùng rác"); self.trash_menu_button.setToolTip("Khôi phục hoặc xóa vĩnh viễn dữ liệu trong thùng rác"); self.trash_menu_button.setToolButtonStyle(Qt.ToolButtonTextOnly); self.trash_menu_button.setPopupMode(QToolButton.InstantPopup)
        trash_menu = QMenu(self.trash_menu_button); self.restore_trash_action = trash_menu.addAction("Khôi phục mục đã chọn"); self.restore_trash_action.triggered.connect(self.restore_trash_selection); self.permanent_delete_action = trash_menu.addAction("Xóa vĩnh viễn mục đã chọn"); self.permanent_delete_action.triggered.connect(self.permanently_delete_trash_selection); trash_menu.addSeparator(); self.empty_trash_action = trash_menu.addAction("Dọn sạch toàn bộ thùng rác"); self.empty_trash_action.triggered.connect(self.empty_trash); self.trash_menu_button.setMenu(trash_menu)
        toolbar = QHBoxLayout(); toolbar.setSpacing(8); toolbar.addWidget(up); toolbar.addWidget(reload); toolbar.addWidget(create); toolbar.addStretch(); toolbar.addWidget(self.download_menu_button); toolbar.addWidget(rename); toolbar.addWidget(self.delete_button); toolbar.addWidget(self.trash_menu_button); toolbar.addWidget(self.upload_menu_button); box.addLayout(toolbar)
        self.storage_path_label = QLabel("HDD  /  data  /  uploads", objectName="muted"); self.storage_path_label.setStyleSheet("font-weight:700; color:#426184;"); self.storage_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse); box.addWidget(self.storage_path_label)
        finder_row = QHBoxLayout(); self.storage_search = QLineEdit(); self.storage_search.setPlaceholderText("⌕  Tìm theo tên tệp hoặc thư mục…"); self.storage_search.setClearButtonEnabled(True); self.storage_search.textChanged.connect(self.apply_storage_filters); self.storage_sort = QComboBox(); self.storage_sort.addItems(["Tên A–Z", "Mới cập nhật", "Dung lượng"]); self.storage_sort.currentIndexChanged.connect(self.apply_storage_filters); finder_row.addWidget(self.storage_search, 1); finder_row.addWidget(self.storage_sort); box.addLayout(finder_row)
        storage_body = QHBoxLayout(); storage_body.setSpacing(14); tree_panel = QFrame(objectName="panel"); tree_box = QVBoxLayout(tree_panel); tree_box.addWidget(QLabel("Cây thư mục", objectName="metricTitle")); self.data_tree = QTreeWidget(); self.data_tree.setHeaderHidden(True); self.data_tree.setMinimumWidth(210); self.data_tree.itemActivated.connect(self.open_tree_folder); tree_box.addWidget(self.data_tree); storage_body.addWidget(tree_panel, 1)
        self.file_table = QTableWidget(0, 4); self.file_table.setHorizontalHeaderLabels(["Tên", "Loại", "Dung lượng", "Cập nhật"]); self.file_table.setAlternatingRowColors(True); self.file_table.setEditTriggers(QTableWidget.NoEditTriggers); self.file_table.setSelectionBehavior(QTableWidget.SelectRows); self.file_table.setSelectionMode(QAbstractItemView.ExtendedSelection); self.file_table.horizontalHeader().setStretchLastSection(True); self.file_table.cellDoubleClicked.connect(self.open_storage_item); self.file_table.itemSelectionChanged.connect(self.update_storage_selection_note); storage_body.addWidget(self.file_table, 3); box.addLayout(storage_body, 1); self.storage_note = QLabel("Kết nối SSH để mở kho dữ liệu.", objectName="muted"); box.addWidget(self.storage_note)
        audit_panel = QFrame(objectName="panel"); audit_box = QVBoxLayout(audit_panel); audit_box.addWidget(QLabel("Nhật ký thao tác kho dữ liệu", objectName="metricTitle")); self.storage_audit = QPlainTextEdit(); self.storage_audit.setReadOnly(True); self.storage_audit.setMaximumHeight(125); self.storage_audit.setPlaceholderText("Làm mới kho lưu trữ để xem nhật ký thao tác."); audit_box.addWidget(self.storage_audit); box.addWidget(audit_panel)
        self.storage_action_buttons = {"create": create, "rename": rename, "delete": self.delete_button, "trash_menu": self.trash_menu_button, "restore": self.restore_trash_action, "permanent_delete": self.permanent_delete_action, "empty_trash": self.empty_trash_action, "download_menu": self.download_menu_button, "download_files": self.download_files_action, "download_folder": self.download_folder_action, "upload_menu": self.upload_menu_button, "choose_upload": self.choose_upload_action, "choose_folder_upload": self.choose_folder_upload_action, "upload": self.confirm_upload_action}; self.storage_entries = []; self.pending_focus_entry = None; self.update_storage_action_buttons(); return page
    def make_terminal(self):
        page, box, run = self.page_shell("Windows PowerShell", "Chạy cục bộ trên laptop — kiểm tra kỹ lệnh trước khi chạy") ; run.setText("▶  Chạy lệnh"); run.clicked.connect(self.run_powershell)
        self.command = QPlainTextEdit(); self.command.setPlaceholderText("Ví dụ: Get-Date; Get-ChildItem"); self.command.setFixedHeight(120); box.addWidget(self.command); self.terminal_output = QPlainTextEdit(); self.terminal_output.setReadOnly(True); self.terminal_output.setPlaceholderText("Kết quả lệnh sẽ hiển thị ở đây."); box.addWidget(self.terminal_output, 1); return page
    def make_settings(self):
        page, box, refresh = self.page_shell("Cài đặt", "Thiết lập bảo mật cục bộ và phiên đăng nhập SSH"); refresh.hide()
        hero = QFrame(objectName="settingsHero"); hero_box = QHBoxLayout(hero); hero_box.setContentsMargins(20, 18, 20, 18); hero_box.setSpacing(14)
        self.settings_avatar = QLabel("?"); self.settings_avatar.setObjectName("settingsAvatar"); self.settings_avatar.setFixedSize(48, 48); self.settings_avatar.setAlignment(Qt.AlignCenter); hero_box.addWidget(self.settings_avatar)
        hero_text = QVBoxLayout(); hero_text.setSpacing(2); hero_text.addWidget(QLabel("TÀI KHOẢN ĐANG SỬ DỤNG", objectName="settingsHeroNote")); self.settings_account = QLabel("Chưa đăng nhập SSH"); self.settings_account.setStyleSheet("font-size:18px; font-weight:800;"); hero_text.addWidget(self.settings_account); hero_text.addWidget(QLabel("Thông tin xác thực chỉ được giữ trong bộ nhớ khi ứng dụng đang mở.", objectName="settingsHeroNote")); hero_box.addLayout(hero_text, 1); self.settings_session_badge = QLabel("Chưa kết nối", objectName="settingsStatus"); hero_box.addWidget(self.settings_session_badge, alignment=Qt.AlignTop); box.addWidget(hero)
        def settings_card(icon, title, description):
            card = QFrame(objectName="settingsCard"); card_box = QVBoxLayout(card); card_box.setContentsMargins(18, 16, 18, 16); card_box.setSpacing(8); heading = QHBoxLayout(); mark = QLabel(icon, objectName="settingsIcon"); mark.setFixedSize(38, 38); mark.setAlignment(Qt.AlignCenter); heading.addWidget(mark); title_box = QVBoxLayout(); title_box.setSpacing(1); title_box.addWidget(QLabel(title, objectName="settingsTitle")); detail = QLabel(description, objectName="settingsDescription"); detail.setWordWrap(True); title_box.addWidget(detail); heading.addLayout(title_box, 1); card_box.addLayout(heading); return card, card_box
        security, security_box = settings_card("⌑", "Bảo mật ứng dụng", "PIN bảo vệ ứng dụng trên máy này và không làm thay đổi mật khẩu SSH."); change_pin = QPushButton("Đổi mã PIN", objectName="primary"); change_pin.clicked.connect(self.open_change_pin); security_box.addWidget(change_pin, alignment=Qt.AlignLeft); box.addWidget(security)
        session, session_box = settings_card("⌁", "Phiên SSH", "Đóng phiên sau khi dùng xong trên máy dùng chung để xóa thông tin xác thực khỏi bộ nhớ."); logout = QPushButton("Đăng xuất SSH"); logout.clicked.connect(self.logout_ssh); session_box.addWidget(logout, alignment=Qt.AlignLeft); box.addWidget(session)
        sharing, sharing_box = settings_card("▣", "Quyền truy cập kho HDD", "servermonitor và thacsikhai có quyền quản lý; huy1111 chỉ xem và tải xuống."); actions = QHBoxLayout(); actions.setSpacing(8); self.shared_hdd_button = QPushButton("Thiết lập quyền HDD", objectName="primary"); self.shared_hdd_button.clicked.connect(self.configure_shared_hdd_access); actions.addWidget(self.shared_hdd_button); self.hdd_access_check_button = QPushButton("Kiểm tra quyền"); self.hdd_access_check_button.clicked.connect(self.check_hdd_access); actions.addWidget(self.hdd_access_check_button); actions.addStretch(); sharing_box.addLayout(actions); self.shared_hdd_note = QLabel("Thao tác thiết lập cần mật khẩu sudo và không lưu lại mật khẩu.", objectName="settingsDescription"); self.shared_hdd_note.setWordWrap(True); sharing_box.addWidget(self.shared_hdd_note); self.hdd_access_result = QLabel("Chưa kiểm tra quyền HDD của phiên hiện tại.", objectName="muted"); self.hdd_access_result.setWordWrap(True); sharing_box.addWidget(self.hdd_access_result); box.addWidget(sharing); box.addStretch(); return page
    def async_call(self, task, done, on_error=None):
        worker = Worker(task)
        # Keep a Python reference until the task completes; otherwise Qt may
        # delete the signal source before the worker tries to report a result.
        self._workers.add(worker)
        def release_worker(*_): self._workers.discard(worker)
        worker.signals.done.connect(done); worker.signals.done.connect(release_worker)
        worker.signals.error.connect(on_error or self.show_error); worker.signals.error.connect(release_worker)
        self.pool.start(worker)
    def async_call_with_progress(self, task, done, on_progress, on_error=None):
        # The task receives a thread-safe callback; Qt delivers updates back
        # to the UI thread through the worker signal.
        worker = Worker(lambda: task(lambda update: worker.signals.progress.emit(update)))
        self._workers.add(worker)
        def release_worker(*_): self._workers.discard(worker)
        worker.signals.done.connect(done); worker.signals.done.connect(release_worker)
        worker.signals.progress.connect(on_progress)
        worker.signals.error.connect(on_error or self.show_error); worker.signals.error.connect(release_worker)
        self.pool.start(worker)
    def start_transfer(self, kind: str):
        self.transfer_kind = kind; self.transfer_started_at = time.monotonic(); self.last_transfer_message = ""
    def render_transfer_progress(self, update):
        completed, total = update.get("completed", 0), update.get("total", 0)
        if not total or self.transfer_started_at is None: return
        elapsed = max(0.1, time.monotonic() - self.transfer_started_at); speed = completed / elapsed
        remaining = max(0, total - completed); eta = remaining / speed if speed else 0; percent = min(100, int(completed / total * 100))
        self.storage_note.setText(f"{self.transfer_kind}: {percent}% · {fmt_bytes(completed)} / {fmt_bytes(total)} · {fmt_bytes(speed)}/giây · còn khoảng {fmt_duration(eta)}")
    def complete_transfer(self, message: str):
        self.transfer_started_at = None; self.last_transfer_message = message; self.storage_note.setText(message)
    def handle_transfer_error(self, message: str):
        self.transfer_started_at = None; self.last_transfer_message = ""; self.show_error(message)
    def audited_action(self, task, action: str, detail: str):
        result = task(); self.ssh.audit(action, detail); return result
    def ensure_ssh_credentials(self):
        if self.ssh.secret: return True
        dialog = QDialog(self); dialog.setWindowTitle("Đăng nhập SSH"); dialog.setMinimumWidth(400); layout = QVBoxLayout(dialog); layout.addWidget(QLabel("Chọn tài khoản server và nhập thông tin xác thực."))
        form = QFormLayout(); account = QComboBox(); [account.addItem(name, name) for name in SERVER_ACCOUNTS]; method = QComboBox(); method.addItem("Mật khẩu tài khoản", "password"); method.addItem("Passphrase SSH key", "key"); field = QLineEdit(); field.setEchoMode(QLineEdit.Password); form.addRow("Tài khoản", account); form.addRow("Phương thức", method); form.addRow("Mật khẩu", field); layout.addLayout(form)
        note = QLabel("Mật khẩu chỉ được giữ trong bộ nhớ đến khi đóng ứng dụng.", objectName="muted"); note.setWordWrap(True); layout.addWidget(note); error = QLabel(); error.setStyleSheet("color: #c02f3c;"); layout.addWidget(error); button = QPushButton("Đăng nhập", objectName="primary")
        def update_method():
            is_key = method.currentData() == "key"; field.setPlaceholderText("Passphrase của SSH key" if is_key else "Mật khẩu tài khoản trên server"); form.labelForField(field).setText("Passphrase key" if is_key else "Mật khẩu")
        def accept_credentials():
            if not field.text(): error.setText("Hãy nhập thông tin xác thực SSH."); return
            dialog.accept()
        method.currentIndexChanged.connect(update_method); update_method(); button.clicked.connect(accept_credentials); field.returnPressed.connect(accept_credentials); layout.addWidget(button)
        if dialog.exec() != QDialog.Accepted: return False
        self.ssh.username = account.currentData(); self.ssh.auth_method = method.currentData(); self.ssh.secret = field.text(); return True
    def refresh_status(self):
        if self._status_refreshing: return
        if not self.ensure_ssh_credentials(): return
        self._status_refreshing = True; self.dashboard_refresh.setDisabled(True); self.header_refresh.setDisabled(True)
        self.connection.setText("◌ Đang kết nối"); self.async_call(self.ssh.status, self.render_status, self.handle_status_error)
    def render_status(self, status):
        # Freeze painting while all widgets receive the same SSH snapshot.
        # This guarantees users never see cards change one by one.
        self.dashboard.setUpdatesEnabled(False)
        try:
            self.connection.setText("● Online"); self.connection.setStyleSheet("background:#14532d; color:#bbf7d0;")
            self.logout_button.setDisabled(False)
            self.set_account_identity(self.ssh.username)
            self.ssh_login_attempts = 0
            self.last_status = status; mem = status.get("MEM", [0, 0]); disk = status.get("DISK", [0, 0]); data = status.get("DATA_DISK", [0, 0]); selected_disk = self.update_dashboard_storage(); values = {
                "Thời gian hoạt động": status.get("UPTIME", "—"), "CPU tải": " · ".join(status.get("LOAD", [])) or "—",
                "Dung lượng đã dùng": f"{fmt_bytes(selected_disk[1])}", "Cập nhật chờ": f"{status.get('UPDATES', 0)} gói"}
            for name, text in values.items(): self.metrics[name][0].setText(text)
            data_percent = int(data[1] / data[0] * 100) if data[0] else 0
            ram_percent = int(mem[1] / mem[0] * 100) if mem[0] else 0
            cpu_percent = min(100, int(float(status.get("LOAD", [0])[0]) / max(1, status.get("CPU", 1)) * 100))
            self.performance_chart.add_sample(cpu_percent, ram_percent, data_percent); self.update_alerts(status, data_percent)
            self.health.setText(f"Systemd lỗi: {status.get('FAILED_UNITS', 0)}   •   Reboot: {'Cần khởi động lại' if status.get('REBOOT') else 'Không cần'}   •   Auto updates: {status.get('AUTO_UPDATES', '—')}")
            sessions = status.get("activeUsers", [])
            self.logged_users.setText("\n".join(f"• {session}" for session in sessions[:6]) if sessions else "Không phát hiện phiên SSH/SFTP đang hoạt động.")
            self.os.setText(status.get("OS", "—")); self.kernel.setText(status.get("KERNEL", "—")); self.updated.setText(time.strftime("%H:%M:%S · %d/%m/%Y")); self.logs.setPlainText("\n".join(status.get("errorLog", [])) or "Không có lỗi mức err đến alert gần đây.")
            if not self.status_refresh_timer.isActive(): self.status_refresh_timer.start()
        finally:
            self.dashboard.setUpdatesEnabled(True); self.dashboard.update()
            self._status_refreshing = False; self.dashboard_refresh.setDisabled(False); self.header_refresh.setDisabled(False)
    def update_alerts(self, status, data_percent):
        while self.alert_list.count():
            item = self.alert_list.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        alerts = []
        failed_names = status.get("failedUnitNames", [])
        if failed_names:
            shown = ", ".join(failed_names[:2]); extra = f" và {len(failed_names) - 2} mục khác" if len(failed_names) > 2 else ""
            alerts.append(("●", "Sự cố", f"Lỗi dịch vụ: {shown}{extra}.", "#dc3545"))
        elif status.get("FAILED_UNITS", 0): alerts.append(("●", "Sự cố", f"Có {status['FAILED_UNITS']} systemd unit cần xử lý.", "#dc3545"))
        if data_percent >= 85: alerts.append(("▲", "Cảnh báo", f"Ổ dữ liệu đang dùng {data_percent}% dung lượng.", "#e79b12"))
        if status.get("REBOOT"): alerts.append(("●", "Thông tin", "Server cần khởi động lại để hoàn tất cập nhật.", "#0967e8"))
        if status.get("UPDATES", 0): alerts.append(("●", "Thông tin", f"Có {status['UPDATES']} gói cập nhật đang chờ.", "#0967e8"))
        if not alerts: alerts.append(("●", "Ổn định", "Không có cảnh báo mới từ server.", "#12a66a"))
        for icon, kind, text, color in alerts[:4]:
            row = QFrame(); row.setStyleSheet("background:#fbfcff; border:1px solid #e7edf5; border-radius:7px;"); layout = QHBoxLayout(row); layout.setContentsMargins(9, 7, 9, 7); mark = QLabel(icon); mark.setStyleSheet(f"color:{color}; font-size:17px; font-weight:800;"); layout.addWidget(mark); message = QLabel(text); message.setWordWrap(True); layout.addWidget(message, 1); badge = QLabel(kind); badge.setStyleSheet(f"background:{color}18; color:{color}; border-radius:5px; padding:3px 6px;"); layout.addWidget(badge); self.alert_list.addWidget(row)
    def handle_status_error(self, message):
        self._status_refreshing = False; self.dashboard_refresh.setDisabled(False); self.header_refresh.setDisabled(False)
        self.logout_button.setDisabled(not bool(self.ssh.secret))
        if not message.startswith("SSH_LOGIN_INVALID:"):
            self.show_error(message); return
        self.ssh.clear_credentials()
        self.ssh_login_attempts += 1
        if self.ssh_login_attempts >= MAX_SSH_LOGIN_ATTEMPTS:
            QMessageBox.critical(self, "Server Monitor", "Bạn đã đăng nhập SSH không thành công 5 lần. Ứng dụng sẽ tự đóng để bảo vệ kết nối.")
            QApplication.quit(); return
        remaining = MAX_SSH_LOGIN_ATTEMPTS - self.ssh_login_attempts
        QMessageBox.warning(self, "Đăng nhập SSH không thành công", f"Tên tài khoản, mật khẩu hoặc SSH key không đúng. Bạn còn {remaining} lần thử.")
        QTimer.singleShot(0, self.refresh_status)
    def refresh_files(self, relative_path=None):
        if not self.ensure_ssh_credentials(): return
        if relative_path is not None: self.current_storage_path = relative_path
        self.storage_note.setText("Đang tải danh sách tệp…")
        location = self.current_storage_location
        self.async_call(lambda: self.ssh.list_storage(location, self.current_storage_path), self.render_files, self.handle_storage_error)
        self.async_call(lambda: self.ssh.list_data_tree(location), self.render_data_tree)
        if location == "hdd": self.async_call(self.ssh.read_audit, self.render_storage_audit)
        else: self.storage_audit.setPlainText("Nhật ký thao tác chỉ áp dụng cho kho HDD có thể ghi.")

    def change_storage_location(self):
        self.current_storage_location = self.storage_location.currentData()
        self.current_storage_path = ""; self.pending_focus_entry = None; self.storage_search.clear()
        self.refresh_files("")

    def handle_storage_error(self, message: str):
        if not message.startswith("STORAGE_ACCESS_DENIED:"):
            self.show_error(message); return
        detail = message.removeprefix("STORAGE_ACCESS_DENIED: ").strip()
        if self.current_storage_location == "hdd":
            self.storage_permission_message = f"{detail} Đã chuyển sang SSD (thư mục home) để bạn tiếp tục làm việc."
            self.storage_location.setCurrentIndex(self.storage_location.findData("ssd"))
        else:
            self.storage_note.setText(detail)

    def render_storage_audit(self, lines):
        self.storage_audit.setPlainText("\n".join(lines) if lines else "Chưa có thao tác nào được ghi nhận.")
    def render_files(self, listing):
        if listing["location"] != self.current_storage_location: return
        self.current_storage_path = listing["path"]; location = self.ssh.storage_location(listing["location"]); suffix = f"/{self.current_storage_path}" if self.current_storage_path else ""; self.storage_path_label.setText(f"{location['label']}  /  {listing['root']}{suffix}")
        self.storage_entries = listing["entries"]
        self.apply_storage_filters()
        self.focus_created_entry()
        if self.storage_permission_message:
            self.storage_note.setText(self.storage_permission_message); self.storage_permission_message = ""
        if self.last_transfer_message:
            self.storage_note.setText(self.last_transfer_message); self.last_transfer_message = ""

    def focus_created_entry(self):
        if not self.pending_focus_entry: return
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0); entry = item.data(Qt.UserRole) if item else None
            if entry and entry["name"] == self.pending_focus_entry:
                self.file_table.selectRow(row); self.file_table.scrollToItem(item); self.storage_note.setText(f"✓ Đã xác minh và tạo thư mục: {entry['name']}"); self.pending_focus_entry = None; return
        self.storage_note.setText(f"Đã tạo {self.pending_focus_entry}, nhưng bộ lọc hiện tại đang không hiển thị mục này.")

    def apply_storage_filters(self):
        if not hasattr(self, "file_table"): return
        query = self.storage_search.text().strip().casefold()
        entries = [entry for entry in getattr(self, "storage_entries", []) if query in entry["name"].casefold()]
        mode = self.storage_sort.currentText()
        if mode == "Mới cập nhật":
            entries.sort(key=lambda entry: entry["modified"], reverse=True); entries.sort(key=lambda entry: not entry["is_dir"])
        elif mode == "Dung lượng":
            entries.sort(key=lambda entry: entry["size"], reverse=True); entries.sort(key=lambda entry: not entry["is_dir"])
        else: entries.sort(key=lambda entry: (not entry["is_dir"], entry["name"].casefold()))
        self.file_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            is_archive = not entry["is_dir"] and is_archive_file(entry["name"])
            values = (f"📁  {entry['name']}" if entry["is_dir"] else f"🗜️  {entry['name']}" if is_archive else f"📄  {entry['name']}", "Thư mục" if entry["is_dir"] else "Tệp nén" if is_archive else "Tệp", "—" if entry["is_dir"] else fmt_bytes(entry["size"]), entry["modified"])
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setData(Qt.UserRole, entry); self.file_table.setItem(row, column, item)
        total = len(self.storage_entries)
        read_only_note = " Bạn đang ở chế độ chỉ đọc; có thể xem và tải xuống." if self.current_storage_location == "hdd" and self.ssh.username not in HDD_WRITE_ACCOUNTS else ""
        self.storage_note.setText(f"Hiển thị {len(entries)}/{total} mục. Nhấp đúp vào thư mục để mở.{read_only_note}")
        self.update_storage_action_buttons()

    def update_storage_selection_note(self):
        entries = self.selected_storage_entries()
        if entries:
            files = sum(not entry["is_dir"] for entry in entries)
            folders = len(entries) - files
            details = []
            if files: details.append(f"{files} tệp")
            if folders: details.append(f"{folders} thư mục")
            self.storage_note.setText(f"✓ Đã chọn {len(entries)} mục ({', '.join(details)}).")
        self.update_storage_action_buttons(entries)

    def update_storage_action_buttons(self, entries=None):
        if not hasattr(self, "storage_action_buttons"): return
        entries = self.selected_storage_entries() if entries is None else entries
        writable = self.current_storage_location == "hdd" and self.ssh.username in HDD_WRITE_ACCOUNTS; readable = self.current_storage_location in STORAGE_LOCATIONS; trash_view = self.is_trash_view()
        self.delete_button.setText("Xóa vĩnh viễn" if trash_view else "Chuyển vào thùng rác")
        self.storage_action_buttons["create"].setEnabled(writable and not trash_view)
        self.storage_action_buttons["choose_upload"].setEnabled(writable and not trash_view)
        self.storage_action_buttons["choose_folder_upload"].setEnabled(writable and not trash_view)
        self.storage_action_buttons["upload"].setEnabled(writable and not trash_view and bool(self.selected_upload_paths))
        self.storage_action_buttons["rename"].setEnabled(writable and not trash_view and len(entries) == 1)
        self.storage_action_buttons["delete"].setEnabled(writable and bool(entries))
        self.storage_action_buttons["trash_menu"].setEnabled(writable)
        self.storage_action_buttons["restore"].setEnabled(writable and trash_view and bool(entries))
        self.storage_action_buttons["permanent_delete"].setEnabled(writable and trash_view and bool(entries))
        self.storage_action_buttons["empty_trash"].setEnabled(writable and trash_view)
        # Keep the menu reachable even before a row is selected. Its handlers
        # explain the required selection instead of leaving a dead-looking UI.
        self.storage_action_buttons["download_menu"].setEnabled(readable)
        self.storage_action_buttons["download_files"].setEnabled(readable)
        self.storage_action_buttons["download_folder"].setEnabled(readable)
        self.storage_action_buttons["upload_menu"].setEnabled(writable and not trash_view)
    def is_trash_view(self) -> bool:
        return self.current_storage_location == "hdd" and self.current_storage_path == ".trash"
    def render_data_tree(self, listing):
        if listing["location"] != self.current_storage_location: return
        self.data_tree.clear(); location = self.ssh.storage_location(listing["location"]); root = QTreeWidgetItem([f"📁  {location['label']}"]); root.setData(0, Qt.UserRole, ""); self.data_tree.addTopLevelItem(root); nodes = {"": root}
        for full_path in listing["paths"]:
            parent_path = ""
            for part in full_path.split("/"):
                child_path = f"{parent_path}/{part}" if parent_path else part
                if child_path not in nodes:
                    label = "🗑️  Thùng rác" if child_path == ".trash" and self.current_storage_location == "hdd" else f"📁  {part}"
                    node = QTreeWidgetItem([label]); node.setData(0, Qt.UserRole, child_path); nodes[parent_path].addChild(node); nodes[child_path] = node
                parent_path = child_path
        root.setExpanded(True); self.data_tree.expandToDepth(2)
    def open_tree_folder(self, item, _column):
        self.refresh_files(item.data(0, Qt.UserRole) or "")
    def open_storage_item(self, row, _column):
        item = self.file_table.item(row, 0)
        if not item: return
        entry = item.data(Qt.UserRole)
        if entry and entry["is_dir"]:
            next_path = f"{self.current_storage_path}/{entry['name']}" if self.current_storage_path else entry["name"]
            self.refresh_files(next_path)
    def go_storage_up(self):
        if not self.current_storage_path: return
        parent = str(PurePosixPath(self.current_storage_path).parent)
        self.refresh_files("" if parent == "." else parent)
    def selected_storage_entry(self):
        row = self.file_table.currentRow()
        item = self.file_table.item(row, 0) if row >= 0 else None
        return item.data(Qt.UserRole) if item else None
    def selected_storage_entries(self):
        entries = []
        for model_index in self.file_table.selectionModel().selectedRows():
            item = self.file_table.item(model_index.row(), 0)
            if item: entries.append(item.data(Qt.UserRole))
        return [entry for entry in entries if entry]
    def create_storage_folder(self):
        name, accepted = QInputDialog.getText(self, "Tạo thư mục", "Tên thư mục mới:")
        if not accepted or not name.strip(): return
        self.storage_note.setText("Đang tạo và xác minh thư mục trên server…")
        def created(result):
            self.pending_focus_entry = result["name"]
            self.storage_search.clear()
            self.storage_note.setText(f"Đã tạo {result['name']}. Đang làm mới danh sách…")
            self.refresh_files()
        self.async_call(lambda: self.audited_action(lambda: self.ssh.create_folder(self.current_storage_path, name), "folder_create", f"{self.current_storage_path}/{name}"), created)
    def rename_storage_selection(self):
        entry = self.selected_storage_entry()
        if not entry: self.show_error("Hãy chọn một tệp hoặc thư mục để đổi tên."); return
        name, accepted = QInputDialog.getText(self, "Đổi tên", "Tên mới:", text=entry["name"])
        if not accepted or not name.strip() or name == entry["name"]: return
        self.storage_note.setText("Đang đổi tên…")
        self.async_call(lambda: self.audited_action(lambda: self.ssh.rename_storage_entry(self.current_storage_path, entry["name"], name), "entry_rename", f"{self.current_storage_path}/{entry['name']} -> {name}"), lambda _: self.refresh_files())
    def delete_storage_selection(self):
        entries = self.selected_storage_entries()
        if not entries: self.show_error("Hãy chọn ít nhất một tệp hoặc thư mục để xóa."); return
        if self.is_trash_view(): self.permanently_delete_trash_selection(); return
        files = sum(not entry["is_dir"] for entry in entries); folders = len(entries) - files; details = []
        if files: details.append(f"{files} tệp")
        if folders: details.append(f"{folders} thư mục")
        choice = QMessageBox.question(self, "Xác nhận chuyển vào thùng rác", f"Chuyển {', '.join(details)} đã chọn vào thùng rác trên server?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if choice != QMessageBox.Yes: return
        self.storage_note.setText("Đang chuyển vào thùng rác…")
        names = [entry["name"] for entry in entries]
        self.async_call(lambda: self.audited_action(lambda: self.ssh.trash_storage_entries(self.current_storage_path, names), "entry_trash", ", ".join(f"{self.current_storage_path}/{name}" for name in names)), lambda _: self.refresh_files())
    def restore_trash_selection(self):
        if not self.is_trash_view(): self.show_error("Mở Thùng rác trong cây thư mục trước khi khôi phục."); return
        entries = self.selected_storage_entries()
        if not entries: self.show_error("Hãy chọn ít nhất một mục để khôi phục."); return
        names = [entry["name"] for entry in entries]
        choice = QMessageBox.question(self, "Xác nhận khôi phục", f"Khôi phục {len(names)} mục đã chọn về thư mục gốc của kho HDD?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if choice != QMessageBox.Yes: return
        self.storage_note.setText("Đang khôi phục từ thùng rác…")
        self.async_call(lambda: self.audited_action(lambda: self.ssh.restore_trash_entries(names), "entry_restore", ", ".join(names)), lambda _: self.refresh_files())
    def permanently_delete_trash_selection(self):
        if not self.is_trash_view(): self.show_error("Mở Thùng rác trong cây thư mục trước khi xóa vĩnh viễn."); return
        entries = self.selected_storage_entries()
        if not entries: self.show_error("Hãy chọn ít nhất một mục để xóa vĩnh viễn."); return
        names = [entry["name"] for entry in entries]
        choice = QMessageBox.question(self, "Xóa vĩnh viễn", f"Xóa vĩnh viễn {len(names)} mục đã chọn? Hành động này không thể hoàn tác.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if choice != QMessageBox.Yes: return
        self.storage_note.setText("Đang xóa vĩnh viễn các mục đã chọn…")
        self.async_call(lambda: self.audited_action(lambda: self.ssh.permanently_delete_trash_entries(names), "trash_delete", ", ".join(names)), lambda _: self.refresh_files())
    def empty_trash(self):
        if not self.is_trash_view(): self.show_error("Mở Thùng rác trong cây thư mục trước khi dọn sạch."); return
        choice = QMessageBox.question(self, "Dọn sạch thùng rác", "Xóa vĩnh viễn toàn bộ dữ liệu trong thùng rác? Hành động này không thể hoàn tác.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if choice != QMessageBox.Yes: return
        self.storage_note.setText("Đang dọn sạch toàn bộ thùng rác…")
        self.async_call(lambda: self.audited_action(self.ssh.empty_trash, "trash_empty", "all"), lambda _: self.refresh_files())
    def download_storage_selection(self):
        entries = self.selected_storage_entries()
        if not entries: self.show_error("Hãy chọn ít nhất một tệp để tải xuống."); return
        if any(entry["is_dir"] for entry in entries): self.show_error("Chỉ có thể tải xuống tệp. Hãy bỏ chọn thư mục."); return
        directory = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu tệp tải xuống")
        if not directory: return
        names = [entry["name"] for entry in entries]; self.start_transfer("Tải xuống"); self.storage_note.setText(f"Đang tải {len(names)} tệp về máy tính (tối đa {MAX_PARALLEL_TRANSFERS} luồng song song)…")
        def finish_download(count): self.complete_transfer(f"✓ Đã tải {count} tệp về {directory}. Hoàn thành lúc {time.strftime('%H:%M:%S · %d/%m/%Y')}.")
        self.async_call_with_progress(lambda report: self.audited_action(lambda: self.ssh.download_storage_entries(self.current_storage_path, names, directory, report), "download", ", ".join(names)), finish_download, self.render_transfer_progress, self.handle_transfer_error)
    def download_storage_folder_selection(self):
        entry = self.selected_storage_entry()
        if not entry or not entry["is_dir"]: self.show_error("Hãy chọn đúng một thư mục để tải xuống."); return
        directory = QFileDialog.getExistingDirectory(self, "Chọn nơi lưu thư mục tải xuống")
        if not directory: return
        self.storage_note.setText(f"Đang tải thư mục {entry['name']} về máy tính…")
        def finish_download(count): self.storage_note.setText(f"✓ Đã tải thư mục {entry['name']} ({count} tệp) về {directory}. Hoàn thành lúc {time.strftime('%H:%M:%S · %d/%m/%Y')}.")
        self.async_call(lambda: self.audited_action(lambda: self.ssh.download_storage_folder(self.current_storage_path, entry["name"], directory), "folder_download", f"{self.current_storage_path}/{entry['name']}"), finish_download)
    def select_upload_files(self):
        if not self.ensure_ssh_credentials(): return
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn tệp tải lên (hỗ trợ tệp nén)", "", ARCHIVE_FILE_FILTER)
        if not files: return
        if len(files) > 20:
            self.show_error("Mỗi lần chỉ được chọn tối đa 20 tệp."); return
        self.selected_upload_paths = files; self.confirm_upload_action.setEnabled(True)
        names = ", ".join(Path(path).name for path in files[:3]); extra = f" và {len(files) - 3} tệp khác" if len(files) > 3 else ""
        self.storage_note.setText(f"Đã chọn {len(files)} tệp: {names}{extra}. Nhấn “Tải tệp đã chọn” để xác nhận.")
    def select_upload_folder(self):
        if not self.ensure_ssh_credentials(): return
        local_folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục trên laptop để tải lên")
        if not local_folder: return
        default_target = self.current_storage_path or Path(local_folder).name
        target, accepted = QInputDialog.getText(self, "Thư mục đích trên server", "Đường dẫn trong /data/uploads:", text=default_target)
        if not accepted: return
        try: target = self.ssh.safe_storage_path(target)
        except RuntimeError as error: self.show_error(str(error)); return
        self.storage_note.setText(f"Đang tải thư mục {Path(local_folder).name} lên /data/uploads/{target or ''}…")
        def finish_folder_upload(uploaded):
            self.pending_focus_entry = Path(uploaded[0]["name"]).parts[0] if "/" in uploaded[0]["name"] else None
            self.storage_note.setText(f"✓ Đã xác minh và tải {len(uploaded)} tệp từ thư mục {Path(local_folder).name}. Hoàn thành lúc {time.strftime('%H:%M:%S · %d/%m/%Y')}. Đang mở thư mục đích…")
            self.refresh_files(target)
        self.async_call(lambda: self.audited_action(lambda: self.ssh.upload_folder(local_folder, target), "folder_upload", f"{Path(local_folder).name} -> {target}"), finish_folder_upload)
    def upload_files(self):
        if not self.selected_upload_paths:
            self.select_upload_files(); return
        files = list(self.selected_upload_paths); self.confirm_upload_action.setDisabled(True); self.start_transfer("Tải lên")
        self.storage_note.setText(f"Đang tải {len(files)} tệp lên server (tối đa {MAX_PARALLEL_TRANSFERS} luồng song song)…")
        def finish_upload(uploaded):
            self.selected_upload_paths = []; self.confirm_upload_action.setDisabled(True)
            names = ", ".join(item["name"] for item in uploaded[:3]); extra = f" và {len(uploaded) - 3} tệp khác" if len(uploaded) > 3 else ""
            self.complete_transfer(f"✓ Đã tải thành công {len(uploaded)} tệp: {names}{extra}. Hoàn thành lúc {time.strftime('%H:%M:%S · %d/%m/%Y')}. Đang làm mới thư mục…")
            self.refresh_files()
        def upload_error(message):
            self.transfer_started_at = None; self.confirm_upload_action.setEnabled(True); self.storage_note.setText("Tải tệp chưa hoàn tất. Bạn có thể thử lại."); self.show_error(message)
        self.async_call_with_progress(lambda report: self.audited_action(lambda: self.ssh.upload(files, self.current_storage_path, report), "upload", ", ".join(Path(file).name for file in files)), finish_upload, self.render_transfer_progress, upload_error)
    def run_powershell(self):
        command = self.command.toPlainText().strip()
        if not command: self.show_error("Hãy nhập lệnh PowerShell."); return
        self.terminal_output.setPlainText("Đang chạy…")
        def execute():
            result = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return f"{result.stdout}{result.stderr}\nExit code: {result.returncode}"
        self.async_call(execute, self.terminal_output.setPlainText)
    def show_error(self, message):
        self._status_refreshing = False
        if hasattr(self, "dashboard_refresh"): self.dashboard_refresh.setDisabled(False)
        if hasattr(self, "header_refresh"): self.header_refresh.setDisabled(False)
        self.connection.setText("● Không kết nối được"); self.connection.setStyleSheet("background:#7f1d1d; color:#fecaca;"); QMessageBox.critical(self, "Server Monitor", message)


def main():
    app = QApplication(sys.argv); app.setApplicationName("Server Monitor"); app.setStyleSheet(APP_STYLE)
    lock = PinDialog()
    if lock.exec() != QDialog.Accepted: return 0
    window = MainWindow(); window.show(); return app.exec()


if __name__ == "__main__": sys.exit(main())
