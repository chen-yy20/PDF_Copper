# PDF矢量截图工具

一个基于 Python 的图形化 PDF 截图工具。

## 功能

- 打开 PDF 文件
- 鼠标拖拽框选页面区域
- 导出当前选区为新的 PDF
- 导出采用矢量裁剪方式，尽量保留原始矢量效果

## 环境要求

- Python 3.10+
- macOS / Linux / Windows
- PySide6 运行环境

说明：当前项目在 macOS 上已验证 `PySide6==6.7.3` 可正常启动。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

## 运行

```bash
python app.py
```

如果你遇到 Qt 插件报错（例如 `Could not find the Qt platform plugin "cocoa"`），先确保使用虚拟环境解释器运行：

```bash
.venv/bin/python app.py
```

若仍失败，可执行以下命令检查插件目录：

```bash
.venv/bin/python -c "import PySide6, pathlib; p=pathlib.Path(PySide6.__file__).resolve().parent/'Qt/plugins/platforms'; print(p, p.exists())"
```

如果仍然报 `cocoa` 插件错误，通常是当前 `.venv` 中 PySide6 安装损坏。可直接重建环境：

```bash
rm -rf .venv
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -U pip setuptools wheel
.venv/bin/pip install --no-compile -r requirements.txt
.venv/bin/python app.py
```

## 使用步骤

1. 点击“打开PDF”选择文件。
2. 在页面上按住鼠标左键拖动，框选目标区域。
3. 点击“导出选区PDF”。
4. 选择保存路径，完成导出。

## 实现说明

- 页面显示：通过 PyMuPDF 渲染预览图，显示到 PySide6 图形视图。
- 坐标换算：将画布选区坐标按缩放比映射回 PDF 页面坐标。
- 矢量导出：使用 `show_pdf_page(..., clip=...)` 从源页直接裁剪写入新页，避免位图化导出。

## 已知限制

- 当前版本每次导出仅针对当前页面的一个选区。
- 复杂 PDF（透明、混合模式、特殊字体）在不同阅读器中显示可能存在细微差异。
