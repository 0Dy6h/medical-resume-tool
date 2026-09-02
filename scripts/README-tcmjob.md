# tcmjob 全局命令

`D:\bin\tcmjob.bat` / `D:\bin\tcmjob-stop.bat` 是本文件同目录两个 bat 的运行副本
（`D:\bin` 已在用户 PATH，因此在任意目录的 cmd 里输入 `tcmjob` 即可）。

## 用法

- `tcmjob` —— 启动后端(8000) + 前端(5173)，就绪后自动打开浏览器；
  保持窗口开着，**按 Ctrl+C 或关闭窗口即停止整套服务**（看门狗兜底）。
- `tcmjob-stop` —— 任意目录随时停止两个服务。

## 机制要点（改代码前先读）

- 服务在最小化的子窗口运行，日志在 `logs/tcm-backend.log` / `tcm-frontend.log`。
- 主窗口生成 `logs\tcm-watchdog.cmd` 并以唯一随机窗口标题（`tcmjob-<随机数>`）监视自身；
  主窗口消失（Ctrl+C / 关窗 / 杀进程）时看门狗调用 `tcmjob-stop`。
- 已知兼容性坑：本机 PATH 中 Git 的 `/usr/bin` 先于 System32，`timeout` 被 GNU coreutils
  版本抢占，因此脚本内等待一律用 `ping -n`；bat 必须保存为 **GBK 编码 + CRLF**。
- 换机器：改 bat 顶部的 `TCM_HOME`，并把两个 bat 拷到某个 PATH 目录（或新建目录加入 PATH）。
