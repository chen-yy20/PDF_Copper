import sys
import os
from pathlib import Path

import fitz
import PySide6


def bootstrap_qt_plugin_paths() -> None:
    pyside_root = Path(PySide6.__file__).resolve().parent
    plugin_root = pyside_root / "Qt" / "plugins"
    platform_root = plugin_root / "platforms"

    if plugin_root.is_dir():
        if not os.environ.get("QT_PLUGIN_PATH"):
            os.environ["QT_PLUGIN_PATH"] = str(plugin_root)

    # Keep platform plugins in-place. Moving/copying can break dylib relative deps on macOS.
    if platform_root.is_dir() and not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_root)


# Ensure Qt sees plugin paths before importing QtCore/QtWidgets modules.
bootstrap_qt_plugin_paths()

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QImage, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QMainWindow,
    QMessageBox,
    QRubberBand,
    QStatusBar,
    QToolBar,
)


class PdfGraphicsView(QGraphicsView):
    selectionChanged = Signal(QRectF)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self.viewport())
        self._origin = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._origin = event.position().toPoint()
            self._rubber_band.setGeometry(QRect(self._origin, self._origin))
            self._rubber_band.show()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None:
            current = event.position().toPoint()
            self._rubber_band.setGeometry(QRect(self._origin, current).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._origin is not None:
            self._rubber_band.hide()
            rect = self._rubber_band.geometry()
            if rect.width() > 1 and rect.height() > 1:
                scene_rect = self.mapToScene(rect).boundingRect()
                self.selectionChanged.emit(scene_rect)
            self._origin = None
        super().mouseReleaseEvent(event)


class PDFCropperWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PDF矢量截图工具")
        self.resize(1200, 800)

        self.doc = None
        self.current_page_index = 0
        self.current_page = None
        self.zoom = 1.5
        self.current_pixmap = None
        self.selection_scene_rect = None
        self.selection_item = None
        self.interaction_mode = "crop"

        self.scene = QGraphicsScene(self)
        self.view = PdfGraphicsView(self)
        self.view.setScene(self.scene)
        self.view.selectionChanged.connect(self.on_selection_changed)
        self.setCentralWidget(self.view)

        self._create_toolbar()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("请选择一个 PDF 文件（当前：截图模式）")

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("打开PDF", self)
        open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_action)

        prev_action = QAction("上一页", self)
        prev_action.triggered.connect(self.prev_page)
        toolbar.addAction(prev_action)

        next_action = QAction("下一页", self)
        next_action.triggered.connect(self.next_page)
        toolbar.addAction(next_action)

        export_action = QAction("导出选区PDF", self)
        export_action.triggered.connect(self.export_selection)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        crop_mode_action = QAction("截图模式", self)
        crop_mode_action.setShortcut("C")
        crop_mode_action.triggered.connect(self.set_crop_mode)
        toolbar.addAction(crop_mode_action)

        zoom_mode_action = QAction("选区缩放模式", self)
        zoom_mode_action.setShortcut("Z")
        zoom_mode_action.triggered.connect(self.set_zoom_mode)
        toolbar.addAction(zoom_mode_action)

        reset_view_action = QAction("重置视图", self)
        reset_view_action.triggered.connect(self.reset_view)
        toolbar.addAction(reset_view_action)

    def set_crop_mode(self) -> None:
        self.interaction_mode = "crop"
        self.statusBar().showMessage("已切换到截图模式：拖拽框选后可导出选区 PDF")

    def set_zoom_mode(self) -> None:
        self.interaction_mode = "zoom"
        self.statusBar().showMessage("已切换到选区缩放模式：拖拽框选后放大查看，不影响导出选区")

    def reset_view(self) -> None:
        if self.current_pixmap is None:
            return
        self.view.resetTransform()
        self.view.ensureVisible(self.scene.sceneRect(), 20, 20)
        self.statusBar().showMessage("视图已重置")

    def open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择PDF文件",
            "",
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not path:
            return

        try:
            if self.doc is not None:
                self.doc.close()
            self.doc = fitz.open(path)
            self.current_page_index = 0
            self.clear_selection()
            self.render_current_page()
            self.statusBar().showMessage(f"已打开：{path}")
        except Exception as exc:
            QMessageBox.critical(self, "打开失败", f"无法打开 PDF 文件:\n{exc}")
            self.doc = None

    def render_current_page(self) -> None:
        if self.doc is None or self.doc.page_count == 0:
            return

        self.current_page = self.doc.load_page(self.current_page_index)
        pix = self.current_page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=False)
        q_image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        self.current_pixmap = QPixmap.fromImage(q_image)

        self.scene.clear()
        self.scene.addPixmap(self.current_pixmap)
        self.scene.setSceneRect(0, 0, self.current_pixmap.width(), self.current_pixmap.height())
        self.selection_item = None
        self.selection_scene_rect = None
        self.view.resetTransform()

        self.setWindowTitle(f"PDF矢量截图工具 - 第 {self.current_page_index + 1}/{self.doc.page_count} 页")
        if self.interaction_mode == "crop":
            self.statusBar().showMessage("截图模式：拖动鼠标框选后，点击“导出选区PDF”")
        else:
            self.statusBar().showMessage("选区缩放模式：拖动鼠标框选后将放大查看")

    def prev_page(self) -> None:
        if self.doc is None:
            return
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.clear_selection()
            self.render_current_page()

    def next_page(self) -> None:
        if self.doc is None:
            return
        if self.current_page_index < self.doc.page_count - 1:
            self.current_page_index += 1
            self.clear_selection()
            self.render_current_page()

    def on_selection_changed(self, scene_rect: QRectF) -> None:
        if self.current_pixmap is None:
            return

        clamped = scene_rect.intersected(self.scene.sceneRect())
        if clamped.width() < 2 or clamped.height() < 2:
            self.statusBar().showMessage("选区过小，请重新框选")
            return

        if self.interaction_mode == "zoom":
            self.view.fitInView(clamped, Qt.KeepAspectRatio)
            self.statusBar().showMessage("已按选区放大（缩放模式，不影响导出选区）")
            return

        self.selection_scene_rect = clamped

        if self.selection_item is not None:
            self.scene.removeItem(self.selection_item)

        self.selection_item = QGraphicsRectItem(clamped)
        pen = QPen(Qt.red)
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        self.selection_item.setPen(pen)
        self.scene.addItem(self.selection_item)

        self.statusBar().showMessage("已选区，点击“导出选区PDF”开始导出")

    def _get_pdf_clip_rect(self):
        if self.current_page is None or self.current_pixmap is None or self.selection_scene_rect is None:
            return None

        page_rect = self.current_page.rect
        scale_x = self.current_pixmap.width() / page_rect.width
        scale_y = self.current_pixmap.height() / page_rect.height

        x0 = max(0.0, min(self.current_pixmap.width(), self.selection_scene_rect.left()))
        y0 = max(0.0, min(self.current_pixmap.height(), self.selection_scene_rect.top()))
        x1 = max(0.0, min(self.current_pixmap.width(), self.selection_scene_rect.right()))
        y1 = max(0.0, min(self.current_pixmap.height(), self.selection_scene_rect.bottom()))

        pdf_x0 = max(0.0, min(page_rect.width, x0 / scale_x))
        pdf_y0 = max(0.0, min(page_rect.height, y0 / scale_y))
        pdf_x1 = max(0.0, min(page_rect.width, x1 / scale_x))
        pdf_y1 = max(0.0, min(page_rect.height, y1 / scale_y))

        clip = fitz.Rect(pdf_x0, pdf_y0, pdf_x1, pdf_y1)
        if clip.width <= 0 or clip.height <= 0:
            return None
        return clip

    def export_selection(self) -> None:
        if self.doc is None:
            QMessageBox.warning(self, "未打开文件", "请先打开 PDF 文件")
            return

        clip_rect = self._get_pdf_clip_rect()
        if clip_rect is None:
            QMessageBox.warning(self, "未选区", "请先框选要导出的区域")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存裁剪后的 PDF",
            "cropped.pdf",
            "PDF Files (*.pdf)",
        )
        if not output_path:
            return

        try:
            out_doc = fitz.open()
            out_page = out_doc.new_page(width=clip_rect.width, height=clip_rect.height)

            # 从源 PDF 页面矢量拷贝裁剪区域到新页面，避免位图化。
            out_page.show_pdf_page(out_page.rect, self.doc, self.current_page_index, clip=clip_rect)

            out_doc.save(output_path, deflate=True)
            out_doc.close()

            self.statusBar().showMessage(f"导出成功：{output_path}")
            QMessageBox.information(self, "导出成功", f"文件已保存到:\n{output_path}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"导出时出错:\n{exc}")

    def clear_selection(self) -> None:
        self.selection_scene_rect = None
        if self.selection_item is not None:
            self.scene.removeItem(self.selection_item)
            self.selection_item = None


def main() -> None:
    app = QApplication(sys.argv)
    window = PDFCropperWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
