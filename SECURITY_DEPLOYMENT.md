# Triển khai bảo mật Server Monitor

Thực hiện theo thứ tự. Không gửi private key, mật khẩu hoặc PIN vào chat.

## 1. Tạo SSH key trên laptop Windows

Mở PowerShell trong VS Code và chạy:

```powershell
$keyDir = Join-Path $env:USERPROFILE '.ssh'
New-Item -ItemType Directory -Force -Path $keyDir | Out-Null
ssh-keygen -t ed25519 -a 100 -f (Join-Path $keyDir 'server_monitor_ed25519') -C 'server-monitor-desktop'
Get-Content (Join-Path $keyDir 'server_monitor_ed25519.pub')
```

Đặt passphrase mạnh cho private key khi `ssh-keygen` hỏi. Chỉ copy **một dòng public key** kết thúc bằng `server-monitor-desktop`.

## 2. Tạo user riêng trên Ubuntu

Đăng nhập bằng `huy1111`, thay `PASTE_PUBLIC_KEY_HERE` bằng public key vừa tạo, rồi chạy:

```bash
sudo adduser --disabled-password --gecos '' servermonitor
sudo install -d -o servermonitor -g servermonitor -m 750 /data/uploads
sudo install -d -o servermonitor -g servermonitor -m 750 /data/uploads/.trash
sudo install -o servermonitor -g servermonitor -m 640 /dev/null /data/uploads/.server-monitor-audit.log
sudo install -d -o servermonitor -g servermonitor -m 700 /home/servermonitor/.ssh
sudo tee /home/servermonitor/.ssh/authorized_keys >/dev/null <<'EOF'
no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty PASTE_PUBLIC_KEY_HERE
EOF
sudo chown -R servermonitor:servermonitor /home/servermonitor/.ssh
sudo chmod 700 /home/servermonitor/.ssh
sudo chmod 600 /home/servermonitor/.ssh/authorized_keys
sudo tee /etc/ssh/sshd_config.d/90-servermonitor.conf >/dev/null <<'EOF'
Match User servermonitor
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AuthenticationMethods publickey
EOF
sudo sshd -t && sudo systemctl reload ssh
```

Lệnh này không tắt mật khẩu SSH của `huy1111`; nó chỉ bắt buộc key với user `servermonitor`. User mới không được cấp `sudo`.

## 3. Lấy và lưu host fingerprint

Trên Ubuntu, chạy:

```bash
sudo ssh-keygen -l -E sha256 -f /etc/ssh/ssh_host_ed25519_key.pub
```

Ghi lại giá trị bắt đầu bằng `SHA256:`. App sẽ pin giá trị này và từ chối server có fingerprint khác.

## 4. Kiểm tra không cần mật khẩu Ubuntu

Trên Windows:

```powershell
ssh -i (Join-Path $env:USERPROFILE '.ssh\server_monitor_ed25519') servermonitor@100.114.150.77
```

Kết nối thành công sẽ hỏi passphrase của key (nếu đã đặt), không hỏi password Ubuntu.

## Ghi chú

- Không xóa `huy1111` trước khi app mới xác thực bằng key thành công.
- Không dùng `chmod 777` cho `/data/uploads`.
- App sẽ dùng thùng rác `/data/uploads/.trash` và ghi audit log tại `/data/uploads/.server-monitor-audit.log`.
