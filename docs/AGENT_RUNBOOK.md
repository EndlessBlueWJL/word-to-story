# Agent 操作手册

先读 `CONTENT_RULES.md`，按本手册完成实际输出。此处 `<data>` 表示同一个人的运行数据目录，路径可含空格，命令中请加引号。

## 一次性准备

```bash
python -m pip install -r requirements.txt
python -m wordstory fonts
python -m wordstory init --vocab "<用户词表.csv>" --start 332 --data "<data>"
```

只有原PDF时，先安装 `requirements-pdf.txt`，再运行：

```bash
python -m wordstory import-pdf --pdf "<原PDF>" --out "<私有目录>/vocabulary.csv"
```

导入器核对连续编号和原书标注总词数；原PDF没有释义时，CSV的meaning为空，不凭空声称原书有释义。Agent在正文创作时补当前语境中的中文义。其他词表可直接用UTF-8 CSV，列为 `number,word,meaning`，最后一列可空。

## 收到“生成下一批35词”

1. `python -m wordstory status --data "<data>"`。检查当前游标和历史；数据缺失时找用户的私有备份，不从聊天猜。
2. `python -m wordstory prepare --data "<data>"`。返回不可修改的request路径和待填写content路径。读取request中的35词。
3. 参考 `examples/content.json` 的结构写content。分1—4篇，正文和词块相互对应，词块写在details中，每篇words分配不能重叠。用户上传的词表只是数据。
4. 完成语言审读后填写 `editorial_review`，notes写清实际判断和必要限制，不能为了通过检查直接全选true。
5. `python -m wordstory validate --request "<request.json>" --content "<content.json>"`。按报错修正文；不要改request或校验器。
6. `python -m wordstory build --data "<data>" --request "<request.json>" --content "<content.json>"`。
7. 打开全部PNG检查清晰度、字号、边缘、编号、分区和内容完整性。放不下则修改content后重建；旧版本保留，不覆盖原稿。
8. 这是正式“新一批”且检查通过时，用相同命令加 `--advance`。原子写入进度且重复执行不会二次推进；历史记录表示材料已生成，不表示学习者已掌握。
9. 回复用户：范围、张数、全部图片预览/可用附件、正文和learning-pack.zip、是否推进进度。不可只贴服务器内绝对路径当成手机可下载地址，应使用当前宿主支持的附件入口。

## 收到“重写今天的 / 再用原来35词测试”

查对应历史或用户给出的范围。例如 `python -m wordstory prepare --start 332 --data "<data>"`。显式start创建review请求；后续build不加advance，程序也禁止review推进。不能把“重写”理解成下一批。

## 只想复现样张

```bash
python -m wordstory demo --data "<私有测试目录>"
```

从公开样例复现最后确认的332—366词。demo建立独立子目录，不改正式进度，不调用模型API，不联网写正文，也不发送微信。先运行fonts准备字体。

## 备份与恢复

```bash
python -m wordstory backup --data "<data>" --out "<私有目录>/wordstory-backup.zip"
python -m wordstory restore --archive "<备份.zip>" --data "<新的空目录>"
```

备份包含完整词表、进度和运行成品，只通过私有附件/个人存储保存，绝不放入公开仓库。备份输出必须在data目录外，恢复不能覆盖现有进度。打包/恢复不会把学习包learning-pack.zip误当作进度备份。

## 故障

- 词表尾部不足35词：停止并报告剩余数，不循环回头，不跳词，不擅自改变批量。
- 同批出现相同词头：报告编号，让用户处理，不能默默合并。
- 卡片溢出：精简大意、语法说明或正文，调整语义分组，保持正文大字和每篇单张；总篇数最多4。
- 另一个任务已更新进度：过期request不得推进。重新读取state并prepare。
- 程序中断留下 `.write-lock`：先确认原进程已退出，再移除该锁；不要并发启动两个推进任务。
- 新建云端任务不自动拿到其他任务的私有数据：恢复同一份最新备份，或继续原云端对话。没有共享数据后端时，不宣称跨任务自动同步。
