# обработка изображений

import os
import numpy as np
import logging
from scipy.signal import fftconvolve
from PIL import Image
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QFileDialog,
    QMessageBox, QScrollArea, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

from frontend.widgets.plot_widget import PlotWidget

logger = logging.getLogger(__name__)


class ImageViewer(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(300, 300)
        self.setText("No image")
        self.setStyleSheet(
            "border: 1px solid gray; background-color: #2b2b2b;")
        self.current_image = None
        self.setScaledContents(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

    def set_image(self, image_data: np.ndarray):
        if image_data is None or image_data.size == 0:
            self.setText("No image")
            self.current_image = None
            return
        self.current_image = image_data
        self._update_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_image is not None:
            self._update_pixmap()

    def _update_pixmap(self):
        if self.current_image is None:
            return

        # нормализация
        img_normalized = self.current_image.copy()

        if img_normalized.dtype == np.float64 or img_normalized.dtype == np.float32:
            img_min = img_normalized.min()
            img_max = img_normalized.max()
            if img_max > img_min:
                img_normalized = ((img_normalized - img_min) /
                                  (img_max - img_min) * 255).astype(np.uint8)
            else:
                img_normalized = np.zeros_like(img_normalized, dtype=np.uint8)
        else:
            img_normalized = img_normalized.astype(np.uint8)

        # чтоб не рассыпалось
        if not img_normalized.flags['C_CONTIGUOUS']:
            img_normalized = np.ascontiguousarray(img_normalized)

        # в QImage
        height, width = img_normalized.shape[:2]

        if len(img_normalized.shape) == 2:
            bytes_per_line = img_normalized.strides[0]
            qimage = QImage(img_normalized.data, width, height,
                            bytes_per_line, QImage.Format.Format_Grayscale8)
        elif len(img_normalized.shape) == 3:
            if img_normalized.shape[2] == 3:
                bytes_per_line = img_normalized.strides[0]
                qimage = QImage(img_normalized.data, width, height,
                                bytes_per_line, QImage.Format.Format_RGB888)
            elif img_normalized.shape[2] == 4:
                bytes_per_line = img_normalized.strides[0]
                qimage = QImage(img_normalized.data, width, height,
                                bytes_per_line, QImage.Format.Format_RGBA8888)
            else:
                return
        else:
            return

        qimage = qimage.copy()

        # масштабируем
        pixmap = QPixmap.fromImage(qimage)
        scaled_pixmap = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled_pixmap)

    def clear_image(self):
        self.setText("No image")
        self.current_image = None
        self.setPixmap(QPixmap())


class ImageTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Initializing Image Processing tab...")

        # данные
        self.original_image = None
        self.processed_image = None
        self.current_psf = None

        # путь
        self.last_directory = os.path.expanduser("~")
        self.current_filename = None

        # UI
        self._create_ui()
        logger.info("Image Processing tab UI created")

    def _create_ui(self):
        main_layout = QVBoxLayout()

        # верх: картинки и гистограмма
        top_layout = QHBoxLayout()

        # оригинал
        self.original_viewer = ImageViewer()
        original_group = QGroupBox("Original Image")
        original_layout = QVBoxLayout()
        original_layout.addWidget(self.original_viewer)
        original_group.setLayout(original_layout)
        top_layout.addWidget(original_group, stretch=1)

        # обработанная
        self.processed_viewer = ImageViewer()
        processed_group = QGroupBox("PSF Result")
        processed_layout = QVBoxLayout()
        processed_layout.addWidget(self.processed_viewer)
        processed_group.setLayout(processed_layout)
        top_layout.addWidget(processed_group, stretch=1)

        # гистограмма
        histogram_widget = self._create_histogram_widget()
        top_layout.addWidget(histogram_widget, stretch=1)

        main_layout.addLayout(top_layout, stretch=10)

        # середина: инфо
        info_widget = self._create_info_panel()
        main_layout.addWidget(info_widget)

        # низ: кнопки
        buttons_widget = self._create_buttons_panel()
        main_layout.addWidget(buttons_widget)

        self.setLayout(main_layout)

    def _create_info_panel(self) -> QGroupBox:
        group = QGroupBox("Image Information")
        layout = QVBoxLayout()

        self.info_label = QLabel("No image loaded")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        group.setLayout(layout)
        return group

    def _create_buttons_panel(self) -> QWidget:
        widget = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(5, 5, 5, 5)

        # лево: Load и Save
        load_btn = QPushButton("Load Image")
        load_btn.clicked.connect(self._on_load_clicked)
        grid_layout.addWidget(load_btn, 0, 0)

        save_btn = QPushButton("Save Image")
        save_btn.clicked.connect(self._on_save_clicked)
        grid_layout.addWidget(save_btn, 1, 0)

        # центр: Apply PSF (2 ряда)
        apply_psf_btn = QPushButton("Apply PSF")
        apply_psf_btn.clicked.connect(self._on_apply_psf_clicked)
        apply_psf_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;")
        apply_psf_btn.setToolTip("Apply PSF to ORIGINAL image")
        grid_layout.addWidget(apply_psf_btn, 0, 1, 2, 1)

        # право: Reset и Clear
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._on_reset_clicked)
        grid_layout.addWidget(reset_btn, 0, 2)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_clicked)
        grid_layout.addWidget(clear_btn, 1, 2)

        widget.setLayout(grid_layout)
        return widget

    def _create_histogram_widget(self) -> QGroupBox:
        group = QGroupBox("Histogram")
        layout = QVBoxLayout()

        self.histogram_plot = PlotWidget(toolbar=False)
        self.histogram_plot.figure.set_size_inches(4, 3)
        self.histogram_plot.figure.set_tight_layout(
            {'pad': 0.5, 'w_pad': 0.5, 'h_pad': 0.5})
        self.histogram_plot.setMinimumWidth(150)
        self.histogram_plot.setMinimumHeight(150)

        layout.addWidget(self.histogram_plot)

        group.setLayout(layout)
        return group

    def _on_load_clicked(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Image",
            self.last_directory,
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif);;All Files (*)"
        )

        if not filename:
            return

        logger.info(f"Loading image: {filename}")

        # запоминаем путь и имя
        self.last_directory = os.path.dirname(filename)
        self.current_filename = os.path.basename(filename)

        if not os.path.exists(filename):
            logger.error(f"File does not exist: {filename}")
            QMessageBox.critical(self, "Error", f"File not found:\n{filename}")
            return

        try:
            # загрузка через PIL
            pil_img = Image.open(filename)
            logger.info(f"PIL loaded: {pil_img.mode}, size: {pil_img.size}")

            # PIL в numpy
            img_data = np.array(pil_img)
            logger.info(f"Loaded: {img_data.shape}, dtype: {img_data.dtype}")

            if img_data is not None and img_data.size > 0:
                # автоматом в grayscale
                if len(img_data.shape) == 3:
                    logger.info(
                        f"Auto-converting RGB to grayscale (shape: {img_data.shape})...")
                    if img_data.shape[2] == 4:  # RGBA
                        img_data = img_data[:, :, :3]
                    # grayscale: 0.299*R + 0.587*G + 0.114*B
                    img_data = np.dot(img_data[..., :3], [
                                      0.299, 0.587, 0.114]).astype(np.uint8)
                    logger.info(f"Converted to grayscale: {img_data.shape}")

                self.original_image = img_data.copy()
                self.processed_image = img_data.copy()
                logger.info(
                    f"Image ready: {img_data.shape}, dtype: {img_data.dtype}")

                # показываем
                self.original_viewer.set_image(self.original_image)
                self.processed_viewer.set_image(self.processed_image)

                # обновляем инфо
                self._update_info()
                self._update_histogram()
            else:
                logger.error(f"Failed to load image: {filename}")
                QMessageBox.critical(
                    self, "Error", f"Failed to load image.\n\nFile: {filename}")
        except ImportError:
            logger.error("PIL/Pillow not installed")
            QMessageBox.critical(
                self, "Error", "PIL/Pillow is required.\n\nInstall: pip install Pillow")
        except Exception as e:
            logger.error(f"Error loading image: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error", f"Error loading image:\n{str(e)}")

    def _on_save_clicked(self):
        if self.processed_image is None:
            QMessageBox.warning(self, "No Image", "No processed image to save")
            return

        # имя по умолчанию
        if self.current_filename:
            name_without_ext = os.path.splitext(self.current_filename)[0]
            default_name = f"{name_without_ext}_processed.png"
            default_path = os.path.join(self.last_directory, default_name)
        else:
            default_path = os.path.join(
                self.last_directory, "processed_image.png")

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            default_path,
            "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp);;TIFF (*.tif);;All Files (*)"
        )

        if not filename:
            return

        logger.info(f"Saving image to: {filename}")
        try:
            # сохраняем через PIL
            if self.processed_image.dtype != np.uint8:
                img_normalized = self.processed_image.copy()
                img_min = img_normalized.min()
                img_max = img_normalized.max()
                if img_max > img_min:
                    img_normalized = (
                        (img_normalized - img_min) / (img_max - img_min) * 255).astype(np.uint8)
                else:
                    img_normalized = np.zeros_like(
                        img_normalized, dtype=np.uint8)
            else:
                img_normalized = self.processed_image

            pil_img = Image.fromarray(img_normalized)
            pil_img.save(filename)

            logger.info(f"Image saved: {filename}")
        except ImportError:
            logger.error("PIL/Pillow not installed")
            QMessageBox.critical(
                self, "Error", "PIL/Pillow is required.\n\nInstall: pip install Pillow")
        except Exception as e:
            logger.error(f"Error saving image: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error", f"Error saving image:\n{str(e)}")

    def _on_reset_clicked(self):
        if self.original_image is None:
            QMessageBox.warning(
                self, "No Image", "No original image available")
            logger.warning("Attempted reset without original image")
            return

        self.processed_image = self.original_image.copy()
        self.processed_viewer.set_image(self.processed_image)
        self._update_histogram()
        logger.info("Reset to original image")

    def _on_clear_clicked(self):
        self.original_image = None
        self.processed_image = None
        self.original_viewer.clear_image()
        self.processed_viewer.clear_image()
        self.info_label.setText("No image loaded")
        self.histogram_plot.clear()

    def _update_info(self):
        if self.original_image is None:
            self.info_label.setText("No image loaded")
            return

        height, width = self.original_image.shape[:2]
        channels = self.original_image.shape[2] if len(
            self.original_image.shape) == 3 else 1
        dtype = self.original_image.dtype

        value_range = f"[{self.original_image.min():.2f}, {self.original_image.max():.2f}]"

        # инфа в строчку
        info_text = (
            f"<b>Dimensions:</b> {width} x {height}  |  "
            f"<b>Channels:</b> {channels}  |  "
            f"<b>Data type:</b> {dtype}  |  "
            f"<b>Value range:</b> {value_range}"
        )

        self.info_label.setText(info_text)

    def _update_histogram(self):
        if self.processed_image is None:
            self.histogram_plot.clear()
            return

        self.histogram_plot.clear()
        ax = self.histogram_plot.get_axes()

        # гистограмма
        img_flat = self.processed_image.flatten()

        if img_flat.dtype == np.float64 or img_flat.dtype == np.float32:
            hist, bins = np.histogram(img_flat, bins=50)
        else:
            hist, bins = np.histogram(img_flat, bins=50, range=(0, 255))

        # рисуем
        ax.bar(bins[:-1], hist, width=np.diff(bins),
               edgecolor='black', alpha=0.7)
        ax.set_xlabel('Pixel value', fontsize=9)
        ax.set_ylabel('Frequency', fontsize=9)
        ax.set_title('Histogram', fontsize=10)
        ax.tick_params(labelsize=8)
        ax.grid(True, alpha=0.3)

        self.histogram_plot.refresh()

    def set_psf(self, psf_data: np.ndarray):
        self.current_psf = psf_data
        logger.info(f"PSF received: shape {psf_data.shape}")

    def _on_apply_psf_clicked(self):
        # применяем PSF к оригинальному изображению (blur)
        if self.original_image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first!")
            logger.warning("Attempted PSF convolution without image")
            return

        if self.current_psf is None:
            QMessageBox.warning(
                self, "Warning", "Please compute PSF in PSF Calculator tab first!")
            logger.warning("Attempted PSF convolution without PSF")
            return

        try:
            logger.info("Applying PSF convolution to ORIGINAL image...")

            # всегда работаем с original_image
            source_image = self.original_image

            # нормализуем PSF (сумма = 1)
            psf_normalized = self.current_psf / np.sum(self.current_psf)

            # свертка через scipy.signal.fftconvolve (быстро!)
            if len(source_image.shape) == 2:
                # grayscale
                logger.info("Processing grayscale image...")
                convolved = fftconvolve(source_image.astype(
                    float), psf_normalized, mode='same')
            else:
                # RGB - применяем к каждому каналу
                logger.info(
                    f"Processing RGB image ({source_image.shape[2]} channels)...")
                convolved = np.zeros_like(source_image, dtype=float)
                for i in range(source_image.shape[2]):
                    convolved[:, :, i] = fftconvolve(
                        source_image[:, :, i].astype(float),
                        psf_normalized,
                        mode='same'
                    )
                    logger.debug(f"  Channel {i} processed")

            # нормализация обратно к диапазону
            convolved = np.clip(convolved, 0, 255).astype(np.uint8)

            self.processed_image = convolved
            self.processed_viewer.set_image(self.processed_image)
            self._update_histogram()

            logger.info("PSF convolution applied successfully")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Error applying PSF:\n{str(e)}")
            logger.error(f"Error applying PSF: {e}", exc_info=True)
