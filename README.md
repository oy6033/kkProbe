# kkProbe

一个很轻量的 VPS 延迟探针面板。它可以在多台 VPS 上部署探针节点，然后在一个中心页面里查看“不同 VPS 到目标服务器”的延迟曲线。

项目特性：

- 无数据库，无复杂依赖，只需要 Python 3 和系统 `ping`
- 支持 `ICMP`、`HTTP`、`TCP` 三种目标探测
- 支持多个 VPS 节点聚合展示
- 支持前端页面添加 VPS 节点和目标服务器
- 支持管理 Token，避免公网页面被陌生人修改配置
- systemd 常驻运行，适合 Debian / Ubuntu / CentOS 等 VPS

## 目录结构

```text
vps-latency-probe/
├── app.py                         # 后端探针和 API 服务
├── static/index.html              # 前端页面
├── config.example.json            # 配置模板，不含密钥
├── install.sh                     # 一键安装脚本
└── vps-latency-probe.service      # systemd 服务模板
```

运行时配置文件位于：

```bash
/opt/vps-latency-probe/config.json
```

这个文件包含管理 Token，不建议提交到 Git。

## 快速部署

在每台 VPS 上执行：

```bash
git clone https://github.com/oy6033/kkProbe.git
cd kkProbe
sudo bash install.sh
```

脚本会安装到：

```bash
/opt/vps-latency-probe
```

并创建 systemd 服务：

```bash
vps-latency-probe.service
```

安装完成后会输出：

- 面板访问地址
- 管理 Token
- 安装目录
- 服务名

请保存每台 VPS 的管理 Token。如果你希望中心面板新增目标时自动同步到远端 VPS，需要在添加 VPS 节点时填写远端 VPS 的管理 Token。

## 自定义安装参数

可以用环境变量指定节点名称、位置和端口：

```bash
sudo NODE_NAME="Tokyo VPS" LOCATION="Tokyo / JP" PORT=8099 bash install.sh
```

常用参数：

```bash
NODE_NAME="Singapore VPS"
LOCATION="Singapore / SG"
PORT=8099
INSTALL_DIR="/opt/vps-latency-probe"
```

## 使用方式

打开中心面板：

```text
http://你的中心VPS-IP:8099/
```

页面上有两个按钮：

- `Add VPS`：添加其他 VPS 探针节点
- `Add Target`：添加目标服务器

第一次保存时会要求输入 `Admin token`，填中心 VPS 安装时输出的管理 Token。

### 添加 VPS 节点

先在另一台 VPS 上部署同样的探针，然后在中心面板点击 `Add VPS`。

示例：

```text
Probe URL: http://203.0.113.10:8099
Name: Tokyo VPS
Location: Tokyo / JP
Remote Admin Token: 远端VPS安装时输出的Token
```

`Remote Admin Token` 可以为空。为空时，中心面板仍然可以读取远端节点数据，但新增目标不会自动同步到那台远端 VPS。

### 添加目标服务器

点击 `Add Target`，选择探测类型：

```text
ICMP: 适合探测 IP 或域名 ping 延迟
HTTP: 适合探测网站或接口响应延迟
TCP: 适合探测指定端口连接延迟
```

示例目标：

```text
Name: Origin Server
Kind: ICMP
Host / URL: 198.51.100.20
```

```text
Name: API Server
Kind: HTTP
Host / URL: https://api.example.com/health
```

```text
Name: Game Port
Kind: TCP
Host / URL: 198.51.100.20
TCP Port: 443
```

如果远端 VPS 节点保存了 `Remote Admin Token`，新增目标会自动同步到远端节点；否则需要到远端节点页面手动添加同样的目标。

## 配置文件说明

配置文件路径：

```bash
/opt/vps-latency-probe/config.json
```

示例：

```json
{
  "node_id": "singapore-vps",
  "node_name": "Singapore VPS",
  "location": "Singapore / SG",
  "bind_host": "0.0.0.0",
  "port": 8099,
  "admin_token": "replace-with-a-random-token",
  "interval_seconds": 5,
  "history_minutes": 60,
  "targets": [
    {
      "id": "cloudflare-dns",
      "name": "Cloudflare DNS",
      "kind": "icmp",
      "host": "1.1.1.1",
      "timeout_seconds": 2
    }
  ],
  "remote_nodes": [
    {
      "id": "tokyo-vps",
      "name": "Tokyo VPS",
      "location": "Tokyo / JP",
      "url": "http://203.0.113.10:8099",
      "admin_token": "remote-node-token"
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `node_id` | 当前 VPS 节点 ID，建议全局唯一 |
| `node_name` | 页面展示名称 |
| `location` | 节点位置描述 |
| `bind_host` | 监听地址，默认 `0.0.0.0` |
| `port` | 服务端口，默认 `8099` |
| `admin_token` | 管理 Token，用于添加节点和目标 |
| `interval_seconds` | 探测间隔 |
| `history_minutes` | 页面保留的历史数据分钟数 |
| `targets` | 当前节点探测的目标列表 |
| `remote_nodes` | 中心面板聚合的其他 VPS 节点 |

## API

### 健康检查

```bash
curl http://127.0.0.1:8099/api/health
```

### 获取当前节点数据

```bash
curl http://127.0.0.1:8099/api/local
```

### 获取聚合数据

```bash
curl http://127.0.0.1:8099/api/snapshot
```

### 添加 VPS 节点

```bash
curl -X POST http://127.0.0.1:8099/api/nodes \
  -H 'Content-Type: application/json' \
  -d '{
    "admin_token": "CENTER_ADMIN_TOKEN",
    "node": {
      "url": "http://203.0.113.10:8099",
      "name": "Tokyo VPS",
      "location": "Tokyo / JP",
      "admin_token": "REMOTE_ADMIN_TOKEN"
    }
  }'
```

### 添加目标

```bash
curl -X POST http://127.0.0.1:8099/api/targets \
  -H 'Content-Type: application/json' \
  -d '{
    "admin_token": "CENTER_ADMIN_TOKEN",
    "sync": true,
    "target": {
      "name": "Origin Server",
      "kind": "icmp",
      "host": "198.51.100.20",
      "timeout_seconds": 2
    }
  }'
```

## 服务管理

查看状态：

```bash
systemctl status vps-latency-probe
```

查看日志：

```bash
journalctl -u vps-latency-probe -f
```

重启：

```bash
systemctl restart vps-latency-probe
```

停止：

```bash
systemctl stop vps-latency-probe
```

卸载：

```bash
systemctl disable --now vps-latency-probe
rm -f /etc/systemd/system/vps-latency-probe.service
systemctl daemon-reload
rm -rf /opt/vps-latency-probe
```

## 防火墙

如果 VPS 开了防火墙，需要放行端口：

```bash
ufw allow 8099/tcp
```

或只允许你的中心 VPS 访问远端节点：

```bash
ufw allow from <中心VPS-IP> to any port 8099 proto tcp
```

## 安全建议

- 不要把 `/opt/vps-latency-probe/config.json` 提交到 Git
- 每台 VPS 使用不同的 `admin_token`
- 公网部署时建议用防火墙限制访问来源
- 如果只想中心面板访问远端节点，远端节点端口只放行中心 VPS IP
- 如果要上域名和 HTTPS，可以用 Caddy 或 Nginx 反代到 `127.0.0.1:8099`

## 常见问题

### 页面能打开，但没有数据

检查服务状态：

```bash
systemctl status vps-latency-probe
```

检查 API：

```bash
curl http://127.0.0.1:8099/api/snapshot
```

### ICMP 一直失败

确认系统有 `ping`：

```bash
command -v ping
```

Debian / Ubuntu 可以安装：

```bash
apt update
apt install -y iputils-ping
```

### 添加远端 VPS 后显示 offline

在中心 VPS 上测试：

```bash
curl http://远端IP:8099/api/local
```

如果无法访问，通常是远端防火墙、云安全组或服务没启动。

### 添加目标没有同步到远端 VPS

确认添加 VPS 时填写了远端 VPS 的 `Remote Admin Token`。如果没填，中心面板只能读取远端已有数据，不能写入远端配置。
