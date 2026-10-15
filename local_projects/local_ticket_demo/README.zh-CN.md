# 本地工单系统接入练习

本项目提供只读模拟 HTTP API、Hermes 原生插件、报告技能和真实 HTTP 测试。仅使用 Python 标准库；测试使用 Hermes 已有 pytest 环境。

## 文件与调用链

```text
用户 → 加载 ticket-report 技能 → local_ticket_get
     → __init__.py 的 query → client.py 的 get_ticket
     → GET /api/tickets/TASK-101 → mock_server.py
     → JSON 工单 → 工具结果 → 模型整理中文回答
```

- `plugin.yaml`：身份、工具清单和配置项。
- `__init__.py`：注册工具与技能，读取当前插件配置和凭据。
- `client.py`：编号校验、Bearer 鉴权、请求超时和响应校验。
- `mock_server.py`：只绑定 127.0.0.1 的模拟工单服务。
- `skills/ticket-report/SKILL.md`：查询与报告流程。
- `tests/test_integration.py`：启动真实本地 HTTP 服务，测试正常及异常路径。

`local-demo-token` 是本练习公开的演示令牌，不是真实业务凭据。

## 1. 启动服务（终端 A）

```bash
cd /Users/admin/Documents/github/hermes-agent
export HERMES_HOME="$PWD/.hermes-study-data"
export HERMES_RUNTIME_DIR="$HERMES_HOME/tools"
source ./activate
LOCAL_TICKET_API_KEY=local-demo-token python /Users/admin/Documents/github/hermes-agent/local_projects/local_ticket_demo/mock_server.py
```

保持终端开启，Ctrl+C 停止。端口占用时用 `--port 8766`，同时调整插件 base_url。

## 2. 直接验收 API（终端 B）

```bash
curl -i -H 'Authorization: Bearer local-demo-token' http://127.0.0.1:8765/api/tickets/TASK-101
curl -i -H 'Authorization: Bearer local-demo-token' http://127.0.0.1:8765/api/tickets/TASK-999
curl -i -H 'Authorization: Bearer wrong-token' http://127.0.0.1:8765/api/tickets/TASK-101
```

依次预期 HTTP 200、404、401。存在的工单是 TASK-101（处理中）和 TASK-102（待处理）。

## 3. 安装插件到学习环境

在终端 B 中同样进入仓库、设置 HERMES_HOME/HERMES_RUNTIME_DIR 并 `source ./activate`。

```bash
demo_source=/Users/admin/Documents/github/hermes-agent/local_projects/local_ticket_demo
mkdir -p "$HERMES_HOME/plugins"
if [ ! -e "$HERMES_HOME/plugins/local_ticket_demo" ]; then
  cp -R "$demo_source" "$HERMES_HOME/plugins/local_ticket_demo"
else
  echo '插件目录已存在，请先核对内容，不自动覆盖。'
fi
hermes plugins doctor "$HERMES_HOME/plugins/local_ticket_demo" --ci
hermes plugins list
hermes plugins enable local-ticket-demo
```

在当前学习环境的 `.env` 中添加或更新（不要重复添加同名项）：

```dotenv
LOCAL_TICKET_API_KEY=local-demo-token
```

默认地址和超时无需配置。需要修改时，将以下字段合并进现有 `config.yaml` 的 `plugins`，保留已有 enabled 等字段，避免产生重复顶层键：

```yaml
plugins:
  entries:
    local-ticket-demo:
      settings:
        base_url: http://127.0.0.1:8765
        timeout: 3.0
```

插件仅允许本机回环 HTTP 地址。真实业务系统接入时应调整客户端为经过确认的 HTTPS 域名与鉴权方式，不直接沿用演示令牌。

## 4. Hermes 交互验收

启动新的 `hermes` 会话。若此前限定过工具集，在 `hermes tools` 中检查 `local_tickets` 是否启用。

输入：

```text
请使用 skill_view 加载 local-ticket-demo:ticket-report，查询 TASK-101，用中文说明状态、负责人和后续建议。
```

成功标准：记录中出现 local_ticket_get，编号为 TASK-101；回答中的状态为“处理中”，负责人为“小林”。后续建议须标注为建议。

再查询 TASK-999，应说明不存在。停止终端 A 中的服务再查询，应说明无法连接，而不是编造工单结果。

## 5. 自动化测试

从已激活的 Hermes 仓库终端执行官方入口：

```bash
scripts/run_tests.sh /Users/admin/Documents/github/hermes-agent/local_projects/local_ticket_demo/tests/test_integration.py -v
```

测试自行使用随机本地端口，自动清理服务，不依赖手动启动的 8765 服务，也不调用模型。覆盖成功、404、401、缺少令牌、非法编号、非 JSON、字段缺失、超时以及插件 handler 到 HTTP 的集成。

## 6. 调试与下一步

断点依次设置在 `__init__.py` 的 query、`client.py` 的 Request 构造处、`mock_server.py` 的 do_GET，以及 get_ticket 返回结果处。

可检查 args、ticket_id、response.status 和 body；不要输出实际业务系统的令牌。

下一步接真实系统时，保留工具和技能的职责划分，按实际文档调整 URL、鉴权、响应字段映射，并复用这些错误处理测试。
