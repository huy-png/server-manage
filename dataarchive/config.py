"""Application configuration and pure formatting/parsing helpers."""
from __future__ import annotations

import os
from pathlib import Path

SERVER = {"host": "100.114.150.77", "port": 22, "username": "servermonitor"}
APP_VERSION = "1.1.1"
SERVER_ACCOUNTS = ("huy1111", "servermonitor", "thacsikhai")
HDD_WRITE_ACCOUNTS = ("servermonitor", "thacsikhai")
HOST_FINGERPRINT = "SHA256:zqJt1jDkuuT+msYXUmDBt5yaXtguJP+qByu2+SyueqU"
DATA_DIRECTORY = "/data"
UPLOAD_DIRECTORY = f"{DATA_DIRECTORY}/uploads"
SSD_DIRECTORY = "thư mục home của tài khoản SSH"
STORAGE_LOCATIONS = {
    "hdd": {"label": "HDD dữ liệu", "root": UPLOAD_DIRECTORY, "writable": True},
    "ssd": {"label": "SSD hệ thống", "root": SSD_DIRECTORY, "writable": False},
}
AUDIT_LOG = f"{UPLOAD_DIRECTORY}/.server-monitor-audit.log"
APP_DIRECTORY = Path(os.getenv("APPDATA", Path.home())) / "ServerMonitorPySide6"
SECURITY_FILE = APP_DIRECTORY / "security.json"
MAX_SSH_LOGIN_ATTEMPTS = 5
MAX_PARALLEL_TRANSFERS = 3
ARCHIVE_EXTENSIONS = ("zip", "zipx", "rar", "7z", "tar", "gz", "gzip", "tgz", "bz2", "bzip2", "tbz", "tbz2", "xz", "txz", "zst", "tzst", "lz", "lzma", "cab")
ARCHIVE_FILE_FILTER = f"Tệp nén ({' '.join(f'*.{extension}' for extension in ARCHIVE_EXTENSIONS)});;Tất cả tệp (*)"


def fmt_bytes(value: float | int | None) -> str:
    if value is None:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    number, index = float(value), 0
    while number >= 1024 and index < len(units) - 1:
        number /= 1024
        index += 1
    return f"{number:.0f} {units[index]}" if number >= 10 or index == 0 else f"{number:.1f} {units[index]}"


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours} giờ {minutes} phút"
    if minutes:
        return f"{minutes} phút {seconds} giây"
    return f"{seconds} giây"


def is_archive_file(name: str) -> bool:
    return name.casefold().rsplit(".", 1)[-1] in ARCHIVE_EXTENSIONS if "." in name else False


def parse_status(output: str) -> dict:
    result: dict = {"errorLog": [], "failedUnitNames": [], "activeUsers": []}
    reading_errors = reading_failed_units = reading_users = False
    for line in output.splitlines():
        if line == "ERROR_LOG_BEGIN": reading_errors = True; continue
        if line == "ERROR_LOG_END": reading_errors = False; continue
        if line == "FAILED_LIST_BEGIN": reading_failed_units = True; continue
        if line == "FAILED_LIST_END": reading_failed_units = False; continue
        if line == "ACTIVE_USERS_BEGIN": reading_users = True; continue
        if line == "ACTIVE_USERS_END": reading_users = False; continue
        if reading_errors:
            if line.strip(): result["errorLog"].append(line)
            continue
        if reading_failed_units:
            if line.strip(): result["failedUnitNames"].append(line.strip())
            continue
        if reading_users:
            if line.strip(): result["activeUsers"].append(line.strip())
            continue
        key, _, value = line.partition("|")
        values = value.split("|")
        if key in {"HOSTNAME", "OS", "KERNEL", "UPTIME", "AUTO_UPDATES", "DATA_DEVICE"}: result[key] = value.strip()
        elif key == "LOAD": result[key] = value.split()[:3]
        elif key in {"CPU", "FAILED_UNITS", "UPDATES"}: result[key] = int(values[0] or 0)
        elif key in {"MEM", "DISK", "INODES", "DATA_DISK"}: result[key] = [int(item or 0) for item in values]
        elif key == "REBOOT": result[key] = value.strip() == "yes"
    return result


STATUS_COMMAND = "; ".join([
    "printf 'HOSTNAME|'; hostname; printf '\\n'",
    ". /etc/os-release 2>/dev/null; printf 'OS|%s\\n' \"${PRETTY_NAME:-Unknown Linux}\"",
    "printf 'KERNEL|'; uname -r; printf '\\n'", "printf 'CPU|'; nproc; printf '\\n'",
    "printf 'UPTIME|'; uptime -p; printf '\\n'", "printf 'LOAD|'; cat /proc/loadavg; printf '\\n'",
    "free -b | awk '/Mem:/ {printf \"MEM|%s|%s\\n\", $2, $3}'",
    "df -B1 / | awk 'NR==2 {printf \"DISK|%s|%s|%s\\n\", $2, $3, $4}'",
    "df -Pi / | awk 'NR==2 {printf \"INODES|%s|%s\\n\", $2, $3}'",
    "printf 'FAILED_UNITS|'; systemctl --failed --no-legend --plain --all 2>/dev/null | awk 'NF {count++} END {print count+0}'; printf '\\n'",
    "printf 'FAILED_LIST_BEGIN\\n'; systemctl --failed --no-legend --plain --all 2>/dev/null | awk 'NF {print $1}' | head -n 4; printf 'FAILED_LIST_END\\n'",
    "printf 'UPDATES|'; apt list --upgradable 2>/dev/null | sed 1d | grep -c . || true; printf '\\n'",
    "printf 'AUTO_UPDATES|'; systemctl is-enabled apt-daily-upgrade.timer 2>/dev/null || true; printf '\\n'",
    "if test -f /var/run/reboot-required; then printf 'REBOOT|yes\\n'; else printf 'REBOOT|no\\n'; fi",
    "df -B1 /data | awk 'NR==2 {printf \"DATA_DISK|%s|%s|%s\\n\", $2, $3, $4}'",
    "printf 'DATA_DEVICE|'; findmnt -n -o SOURCE --target /data 2>/dev/null || true; printf '\\n'",
    "printf 'ACTIVE_USERS_BEGIN\\n'; ps -eo user=,tty=,etime=,args= 2>/dev/null | awk '/sshd: [^ ]+@/ {print}' | head -n 20; printf 'ACTIVE_USERS_END\\n'",
    "printf 'ERROR_LOG_BEGIN\\n'; journalctl -p err..alert -n 20 --no-pager --output=short-iso --quiet 2>&1; printf 'ERROR_LOG_END\\n'",
])
