# kkProbe

轻量 VPS 延迟探针面板。中心 VPS 只负责展示和管理，其它 VPS 可以只部署探针，不需要前端页面。

## 功能

- 支持中心面板和纯探针两种部署模式
- 支持 ICMP、HTTP、TCP 三种 target
- 支持给每个 target 指定要探测的 VPS 节点
- 支持编辑和删除 Probe Nodes、Targets
- 支持实时显示 Probe Nodes 上行和下行速率
- 前端使用轻量实时轮询，避免频繁下载完整 24 小时历史
- 登录后管理，不再每次操作都输入 token
- Target 下拉选择保存到后端，多设备打开保持一致
- Latency Timeline 保留并渲染最近 24 小时数据
- Latency Timeline 支持 Peak 开关，开启后会隐藏异常高延迟点

## 文件

```text
app.py                         # 后端 API、中心聚合、探针逻辑
static/index.html              # 中心面板前端
config.example.json            # 配置模板，不包含真实 token
install.sh                     # 一键安装脚本
vps-latency-probe.service      # systemd 服务模板
```

运行时配置在：

```bash
/opt/vps-latency-probe/config.json
```

这个文件包含管理 token，不要提交到 GitHub。

## 中心面板安装

有 git 的 VPS：

```bash
apt update
apt install -y git python3 iputils-ping
git clone https://github.com/oy6033/kkProbe.git
cd kkProbe
bash install.sh
```

没有 git 的 VPS：

```bash
apt update
apt install -y wget unzip python3 iputils-ping
wget -O kkProbe.zip https://github.com/oy6033/kkProbe/archive/refs/heads/main.zip
unzip kkProbe.zip
cd kkProbe-main
bash install.sh
```

安装完成后会输出：

- 面板地址
- Admin token
- 安装目录
- systemd 服务名

打开：

```text
http://中心VPS-IP:8099/
```

用中心 VPS 输出的 Admin token 登录。

## 纯探针安装

其它 VPS 只需要部署探针，不需要前端：

```bash
apt update
apt install -y wget unzip python3 iputils-ping
wget -O kkProbe.zip https://github.com/oy6033/kkProbe/archive/refs/heads/main.zip
unzip kkProbe.zip
cd kkProbe-main
DASHBOARD_ENABLED=false NODE_NAME="JP VPS" LOCATION="Japan / JP" bash install.sh
```

纯探针模式下：

- `http://探针IP:8099/` 会返回 404
- `http://探针IP:8099/api/local` 会正常返回探针数据
- 安装输出的 Admin token 用作中心面板添加节点时的 Remote Admin Token

## 添加探针到中心面板

在中心面板点击 `Add VPS`：

```text
Probe URL: http://探针IP:8099
Name: JP VPS
Location: Japan / JP
Remote Admin Token: 纯探针安装时输出的 token
```

保存后，中心面板会读取这个探针的 `/api/local` 数据。

## 管理 target

在中心面板点击 `Add Target` 添加目标。每个 target 可以选择要分配到哪些 VPS 节点，未分配的 VPS 不会探测这个 target。

常见 target：

```text
Kind: ICMP
Name: Cloudflare DNS
Host / URL: 1.1.1.1
```

```text
Kind: HTTP
Name: Website
Host / URL: https://example.com
```

```text
Kind: TCP
Name: HTTPS Port
Host / URL: example.com
TCP Port: 443
```

## 常用环境变量

```bash
NODE_NAME="JP VPS"
LOCATION="Japan / JP"
PORT=8099
INSTALL_DIR="/opt/vps-latency-probe"
DASHBOARD_ENABLED=false
```

`DASHBOARD_ENABLED=true` 是中心面板模式，`false` 是纯探针模式。

## 配置字段

```json
{
  "node_id": "jp-vps",
  "node_name": "JP VPS",
  "location": "Japan / JP",
  "bind_host": "0.0.0.0",
  "port": 8099,
  "admin_token": "replace-with-token",
  "dashboard_enabled": false,
  "interval_seconds": 5,
  "history_minutes": 1440,
  "selected_target": "__all__",
  "targets": [],
  "remote_nodes": []
}
```

## 服务管理

```bash
systemctl status vps-latency-probe
systemctl restart vps-latency-probe
journalctl -u vps-latency-probe -f
```

## API 检查

```bash
curl http://127.0.0.1:8099/api/health
curl http://127.0.0.1:8099/api/local
curl http://127.0.0.1:8099/api/snapshot
```
