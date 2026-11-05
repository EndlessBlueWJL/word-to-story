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
7. 打开delivery.json列出的全部PNG检查清晰度、字号、边缘、编号、分区和内容完整性，并查看360px/390px宽度的手机模拟预览。逐行检查朗读和遮词正文的基线，特别看we、a、加粗词、句号及带下伸部的字母；普通词不得像编号一样上浮。放不下则修改content后重建；旧版本保留，不覆盖原稿。抽查与答案顺序必须一致，遮词卡不得泄露目标词英文。
8. 这是正式“新一批”且检查通过时，用相同命令加 `--advance`。原子写入进度且重复执行不会二次推进；历史记录表示材料已生成，不表示学习者已掌握。
9. 按delivery.json的groups顺序交付全部图片。每组先写用途和实际张数，再逐张嵌图。每张图前加一行可见的短编号/标题，再空行嵌图，图后再空行；下一张必须再次有文字标题。不能只用alt或连续纯图片段落，宿主会把它们并排缩成小图。组内编号与图上页码一致。默认示例是“下面4张：朗读背词”“下面4张：遮词回忆”“下面2张：单词抽查”“下面2张：对照答案”。其他批次用实际张数。不能并排拼图或只给目录、文件名、下载链接。正文、练习、答案都应在聊天里直接看图完成；Markdown/CSV/ZIP等后台文件默认不附。其他文字保持简短。

实际回复优先读取构建目录中的后台模板 `image-reply.md`，按里面由程序生成的真实绝对PNG路径和可见标题直接展示；不能手抄长路径或把 `story-01.png` 猜成其他文件名。模板本身不是给学习者下载的文件。若宿主需要原生图片导出引用，用实际导出返回值替换路径，并核实图片已加载；灰色占位不算交付完成。

## 收到“重写今天的 / 再用原来35词测试”

查对应历史或用户给出的范围。例如 `python -m wordstory prepare --start 332 --data "<data>"`。显式start创建review请求；后续build不加advance，程序也禁止review推进。不能把“重写”理解成下一批。

## 只想复现样张

```bash
python -m wordstory demo --data "<私有测试目录>"
```

从公开样例复现最后确认的332—366词，生成四组完整图片。demo建立独立子目录，不改正式进度，不调用模型API，不联网写正文，也不发送微信。先运行fonts准备字体。

## 备份与恢复

```bash
python -m wordstory backup --data "<data>" --out "<私有目录>/wordstory-backup.zip"
python -m wordstory restore --archive "<备份.zip>" --data "<新的空目录>"
```

备份包含完整词表、进度和运行成品，只通过私有附件/个人存储保存，绝不放入公开仓库。仅在用户明确索要备份/源文件时交付，不能用备份替代日常图片。备份输出必须在data目录外，恢复不能覆盖现有进度。打包/恢复不会把学习包learning-pack.zip误当作进度备份。

## 故障

- 词表尾部不足35词：停止并报告剩余数，不循环回头，不跳词，不擅自改变批量。
- 同批出现相同词头：报告编号，让用户处理，不能默默合并。
- 卡片溢出：精简大意、语法说明或正文，调整语义分组，保持正文大字和每篇单张；总篇数最多4。
- 另一个任务已更新进度：过期request不得推进。重新读取state并prepare。
- 程序中断留下 `.write-lock`：先确认原进程已退出，再移除该锁；不要并发启动两个推进任务。
- 新建云端任务不自动拿到其他任务的私有数据：恢复同一份最新备份，或继续原云端对话。没有共享数据后端时，不宣称跨任务自动同步。
