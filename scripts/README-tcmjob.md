# tcmjob 全局命令

`D:\bin\tcmjob.bat` / `D:\bin\tcmjob-stop.bat` 是本文件同目录两个 bat 的运行副本
（`D:\bin` 已在用户 PATH，因此在任意目录的 cmd 里输入 `tcmjob` 即可）。

## 用法

- `tcmjob` —— 启动后端(8000) + 前端(5173)，就绪后自动打开浏览器；
  保持窗口开着，**按 Ctrl+C 或关闭窗口即停止整套服务**（看门狗兜底）。
- `tcmjob-stop` —— 任意目录随时停止两个服务。

## 机制要点（改代码前先读）

- 服务在最小化的子窗口运行，日志在 `logs/tcm-backend.log` / `tcm-frontend.log`。
- **看门狗 = 心跳文件 + 独立窗口轮询**：主窗口就绪后每 ~1 秒用 `echo x>` 实打实写
  `logs\tcm-heartbeat.flag`（截断式触摸在本机不更新 mtime，必须真写字节）；独立的
  最小化看门狗窗口每 ~3 秒用 PowerShell 检查该文件 mtime，**停滞超过 8 秒即判定
  主窗口已死（Ctrl+C / 关窗 / 杀进程），调用 `tcmjob-stop` 后自退**。因此 Ctrl+C 后
  端口要 ~8-12 秒才释放，期间重跑 `tcmjob` 会提示端口占用，稍等即可。
- 历史教训（勿回退）：①旧版靠窗口标题监视自身，但 `%1` 在生成时展开成空参数、
  `title` 又把引号写进标题，看门狗从未工作过；窗口标题在交互式 cmd 里 Ctrl+C 后
  仍残留，标题/PID 监视路线天然不可行。②生成看门狗脚本时 `if x call y & exit`
  的 `& exit` 不归属 if（每拍无条件执行），必须用 `goto :stop` 分支。③多实例并发
  共享同一心跳文件语义收敛：任一 tcmjob 窗口存活即持跳，全部死亡才停栈。
- 就绪后会先用 `curl` 请求一次前端首页再开浏览器（Vite 开发模式首次命中才编译，
  冷启动首监听本身可达 20-30 秒），预热可显著缩短浏览器里的首屏白屏。
- 已知兼容性坑：本机 PATH 中 Git 的 `/usr/bin` 先于 System32，`timeout` 被 GNU coreutils
  版本抢占，因此脚本内等待一律用 `ping -n`；bat 必须保存为 **GBK 编码 + CRLF**
  （行尾在 git diff 里不可见，审计须直接数 CR/LF 字节）。
- 换机器：改 bat 顶部的 `TCM_HOME`，并把两个 bat 拷到某个 PATH 目录（或新建目录加入 PATH）。
