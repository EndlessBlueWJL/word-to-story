# 在Codex Cloud使用

此文区分“代码可在云端运行”和“你的账户已完成部署”。仓库本身不会创建云端环境，也不包含本机登录态。

## 1. 创建环境

在网页或桌面端选择 **Work in → Cloud → Select environment → Create environment**，选择本仓库。也可从 **Settings → Codex Cloud → Environments** 进入。界面与可用性以账户实际显示为准。

让环境设置Agent执行以下准备：

```bash
python -m pip install -r requirements.txt
python -m wordstory fonts
python -m unittest discover -s tests -v
```

需要导入PDF再安装 `requirements-pdf.txt`；仅恢复CSV备份不需要PDF依赖。首次字体下载需要访问 `raw.githubusercontent.com`，Python依赖需要PyPI；准备完成后取词、排版和检查可离线执行。字体固定版本和哈希，安装成功后可随已发布环境复用。

可直接给设置Agent这段话：

> 为这个仓库准备Python运行环境，阅读AGENTS.md。安装requirements.txt和经校验的Noto字体，运行单元测试，然后执行demo并检查4张图片。只准备和验证环境，不推进学习进度，不创建定时任务，不发送微信。完成后报告检查结果。

确认设置结果后发布环境。以后在手机上选择该已发布环境发起任务，本机无需保持开机。

## 2. 首次带入自己的词表和进度

公开仓库只有35词样例。完整红宝书词表、个人进度和成品，通过**私有附件或个人存储**交给云端任务；不要上传到公开GitHub仓库。

推荐使用本项目生成的 `wordstory-backup.zip`。上传到云端任务后，让Agent运行：

```bash
python -m wordstory restore --archive "<上传附件的实际路径>" --data ./data
python -m wordstory status --data ./data
```

恢复后的词表、游标和历史需与备份一致。测试状态的next_number保持332；只有用户正式开始新批次才推进，不能因为样例已生成就自动改成367。

没有备份时，上传自有CSV，按照操作手册init；不要假设云端能读取这台电脑的D盘。

## 3. 日常用法

继续同一个云端对话：

> 按项目最终要求生成下一批35词，先读进度，完成后给我图片和练习包。

重写：

> 重写今天这35词，让表达更口语，保持原编号，不推进进度。

一个工作区内串行执行，不同时启动两个推进任务。结束时请Agent提供最新私有备份：

```bash
python -m wordstory backup --data ./data --out ./private/wordstory-backup.zip
```

使用当前宿主的附件下载功能领取。上例中private在data外，两个目录均被Git忽略。

## 4. 换新任务或设备

设备本身不决定进度，实际使用的云端工作区和备份决定进度。已有任务保存自己的工作文件；新任务不自动获得其他任务中的个人数据。优先继续原任务，换新任务就恢复**最新**备份。旧备份不会自动合并新进度。

如果以后需要多个云端任务共同读写进度，再增加经过授权的独立存储后端。当前版本不声称已实现这个能力。

## 5. 定时与微信

此版本完成按需生成。定时运行需要另外配置真正的云端触发器，并验证它能访问同一份个人数据；本机目录上的桌面定时任务仍然依赖电脑开机。

官方Codex Cloud当前未提供电脑/浏览器操作，不能照搬本机点击微信发送的方式。微信投递需单独配置可用渠道，并以实际收件结果验收。没有配置和测试前，不报告“已发送”。

依据：[OpenAI官方云端环境说明](https://learn.chatgpt.com/docs/environments/cloud-environments)、[定时任务说明](https://learn.chatgpt.com/docs/automations)。产品行为可能变化，以实际账户和官方文档为准。
