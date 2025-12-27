from psf_wrapper import PSFCalculator, compute_psf
import sys
import os
import numpy as np
import time
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QLabel, QPushButton, QRadioButton,
    QButtonGroup, QProgressDialog, QComboBox, QDoubleSpinBox,
    QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


logger = logging.getLogger(__name__)


sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', '..', 'backend'))


class PSFComputeThread(QThread):

    result_ready = pyqtSignal(np.ndarray, float, dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            start_time = time.time()

            logger.info(f"Starting PSF computation with params: {self.params}")

            calc = PSFCalculator()
            psf_data = calc.compute(**self.params)

            elapsed_time = time.time() - start_time

            step_microns = calc.get_step_microns()

            logger.info(
                f"PSF computation completed: {psf_data.shape}, {elapsed_time:.3f}s")

            self.result_ready.emit(psf_data, elapsed_time, {
                                   'step_microns': step_microns})
        except Exception as e:
            logger.error(f"PSF computation failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))


class PSFTab(QWidget):

    psf_computed = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Initializing PSF Calculator tab...")

        self.psf_calculator = PSFCalculator()
        logger.info("PSF Calculator backend initialized")

        self.current_psf = None
        self.current_params = None
        self.current_step_microns = None
        self.current_compute_time = None

        self.compute_thread = None

        self.current_units = 'microns'

        self._create_ui()
        logger.info("PSF Calculator tab UI created")

    def _create_ui(self):
        main_layout = QVBoxLayout()

        top_widget = self._create_visualization_panel()

        bottom_widget = self._create_parameter_panel()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def _create_parameter_panel(self):
        widget = QWidget()
        main_layout = QVBoxLayout()

        group1 = QGroupBox("Main Parameters")
        main_layout_group1 = QVBoxLayout()

        row1 = QFormLayout()
        self.param_choice_combo = QComboBox()
        self.param_choice_combo.addItems([
            'Diam pupil [c.u.]',
            'Step pupil [c.u.]',
            'Step object [c.u.]',
            'Step image [c.u.]'
        ])
        self.param_choice_combo.currentTextChanged.connect(
            self._on_param_choice_changed)
        row1.addRow("Source param:", self.param_choice_combo)
        main_layout_group1.addLayout(row1)

        row2 = QHBoxLayout()
        row2_col1 = QFormLayout()
        self.size_combo = QComboBox()
        self.size_combo.addItems(['128', '256', '512', '1024', '2048'])
        self.size_combo.setCurrentText('512')
        self.size_combo.currentTextChanged.connect(self._recalculate_params)
        row2_col1.addRow("Sample size:", self.size_combo)

        row2_col2 = QFormLayout()
        self.wavelength_spin = QDoubleSpinBox()
        self.wavelength_spin.setRange(0.1, 5.0)
        self.wavelength_spin.setValue(0.555)
        self.wavelength_spin.setDecimals(3)
        self.wavelength_spin.setSingleStep(0.001)
        self.wavelength_spin.setSuffix(" μm")
        self.wavelength_spin.valueChanged.connect(self._recalculate_params)
        row2_col2.addRow("Wavelength λ:", self.wavelength_spin)

        row2.addLayout(row2_col1)
        row2.addLayout(row2_col2)
        main_layout_group1.addLayout(row2)

        row3 = QHBoxLayout()
        row3_col1 = QFormLayout()
        self.back_aperture_spin = QDoubleSpinBox()
        self.back_aperture_spin.setRange(0.1, 5.0)
        self.back_aperture_spin.setValue(1.2)
        self.back_aperture_spin.setDecimals(2)
        self.back_aperture_spin.setSingleStep(0.1)
        self.back_aperture_spin.valueChanged.connect(self._recalculate_params)
        row3_col1.addRow("Back aperture NA:", self.back_aperture_spin)

        row3_col2 = QFormLayout()
        self.magnification_spin = QDoubleSpinBox()
        self.magnification_spin.setRange(1.0, 1000.0)
        self.magnification_spin.setValue(100.0)
        self.magnification_spin.setDecimals(1)
        self.magnification_spin.setSingleStep(1.0)
        self.magnification_spin.setSuffix(" x")
        self.magnification_spin.valueChanged.connect(self._recalculate_params)
        row3_col2.addRow("Magnification:", self.magnification_spin)

        row3.addLayout(row3_col1)
        row3.addLayout(row3_col2)
        main_layout_group1.addLayout(row3)

        row4 = QHBoxLayout()
        row4_col1 = QFormLayout()
        self.defocus_spin = QDoubleSpinBox()
        self.defocus_spin.setRange(-10.0, 10.0)
        self.defocus_spin.setValue(0.0)
        self.defocus_spin.setDecimals(2)
        self.defocus_spin.setSingleStep(0.1)
        self.defocus_spin.setSuffix(" λ")
        row4_col1.addRow("Defocus:", self.defocus_spin)

        row4_col2 = QFormLayout()
        self.astigmatism_spin = QDoubleSpinBox()
        self.astigmatism_spin.setRange(-10.0, 10.0)
        self.astigmatism_spin.setValue(0.0)
        self.astigmatism_spin.setDecimals(2)
        self.astigmatism_spin.setSingleStep(0.1)
        self.astigmatism_spin.setSuffix(" λ")
        row4_col2.addRow("Astigmatism:", self.astigmatism_spin)

        row4.addLayout(row4_col1)
        row4.addLayout(row4_col2)
        main_layout_group1.addLayout(row4)

        group1.setLayout(main_layout_group1)

        group2 = QGroupBox("Computed Parameters")
        main_layout_group2 = QVBoxLayout()

        comp_row1 = QFormLayout()
        step_obj_widget = QWidget()
        step_obj_layout = QHBoxLayout(step_obj_widget)
        step_obj_layout.setContentsMargins(0, 0, 0, 0)
        self.step_obj_can_spin = QDoubleSpinBox()
        self.step_obj_can_spin.setRange(0.0, 1000.0)
        self.step_obj_can_spin.setDecimals(6)
        self.step_obj_can_spin.setReadOnly(True)
        self.step_obj_can_spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.step_obj_can_spin.valueChanged.connect(self._on_step_obj_changed)
        step_obj_layout.addWidget(self.step_obj_can_spin)
        self.step_obj_unit_combo = QComboBox()
        self.step_obj_unit_combo.addItems(['c.u.', 'μm'])
        self.step_obj_unit_combo.currentTextChanged.connect(
            self._on_step_obj_unit_changed)
        step_obj_layout.addWidget(self.step_obj_unit_combo)
        comp_row1.addRow("Step object:", step_obj_widget)
        main_layout_group2.addLayout(comp_row1)

        comp_row2 = QFormLayout()
        step_im_widget = QWidget()
        step_im_layout = QHBoxLayout(step_im_widget)
        step_im_layout.setContentsMargins(0, 0, 0, 0)
        self.step_im_can_spin = QDoubleSpinBox()
        self.step_im_can_spin.setRange(0.0, 1000.0)
        self.step_im_can_spin.setDecimals(6)
        self.step_im_can_spin.setReadOnly(True)
        self.step_im_can_spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.step_im_can_spin.valueChanged.connect(self._on_step_im_changed)
        step_im_layout.addWidget(self.step_im_can_spin)
        self.step_im_unit_combo = QComboBox()
        self.step_im_unit_combo.addItems(['c.u.', 'μm'])
        self.step_im_unit_combo.currentTextChanged.connect(
            self._on_step_im_unit_changed)
        step_im_layout.addWidget(self.step_im_unit_combo)
        comp_row2.addRow("Step image:", step_im_widget)
        main_layout_group2.addLayout(comp_row2)

        comp_row3 = QFormLayout()
        step_pupil_widget = QWidget()
        step_pupil_layout = QHBoxLayout(step_pupil_widget)
        step_pupil_layout.setContentsMargins(0, 0, 0, 0)
        self.step_pupil_spin = QDoubleSpinBox()
        self.step_pupil_spin.setRange(0.0, 1000.0)
        self.step_pupil_spin.setDecimals(6)
        self.step_pupil_spin.setReadOnly(True)
        self.step_pupil_spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.step_pupil_spin.valueChanged.connect(self._on_step_pupil_changed)
        step_pupil_layout.addWidget(self.step_pupil_spin)
        self.step_pupil_unit_combo = QComboBox()
        self.step_pupil_unit_combo.addItems(['c.u.'])
        step_pupil_layout.addWidget(self.step_pupil_unit_combo)
        comp_row3.addRow("Step pupil:", step_pupil_widget)
        main_layout_group2.addLayout(comp_row3)

        comp_row4 = QFormLayout()
        diam_pupil_widget = QWidget()
        diam_pupil_layout = QHBoxLayout(diam_pupil_widget)
        diam_pupil_layout.setContentsMargins(0, 0, 0, 0)
        self.aperture_spin = QDoubleSpinBox()
        self.aperture_spin.setRange(0.1, 1000.0)
        self.aperture_spin.setValue(7.5)
        self.aperture_spin.setDecimals(3)
        self.aperture_spin.setSingleStep(0.1)
        self.aperture_spin.setReadOnly(True)
        self.aperture_spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.aperture_spin.valueChanged.connect(self._recalculate_params)
        diam_pupil_layout.addWidget(self.aperture_spin)
        self.diam_pupil_unit_combo = QComboBox()
        self.diam_pupil_unit_combo.addItems(['c.u.'])
        diam_pupil_layout.addWidget(self.diam_pupil_unit_combo)
        comp_row4.addRow("Diam pupil:", diam_pupil_widget)
        main_layout_group2.addLayout(comp_row4)

        group2.setLayout(main_layout_group2)

        params_horizontal = QHBoxLayout()
        params_horizontal.addWidget(group1, stretch=1)
        params_horizontal.addWidget(group2, stretch=1)
        main_layout.addLayout(params_horizontal)

        buttons_layout = QHBoxLayout()
        compute_btn = QPushButton("Compute PSF")
        compute_btn.clicked.connect(self._on_compute_clicked)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._on_reset_clicked)
        buttons_layout.addWidget(compute_btn)
        buttons_layout.addWidget(reset_btn)
        buttons_layout.addStretch()
        main_layout.addLayout(buttons_layout)

        widget.setLayout(main_layout)

        self._on_param_choice_changed()
        self._recalculate_params()

        return widget

    def _create_visualization_panel(self):
        widget = QWidget()
        layout = QVBoxLayout()

        plots_layout = QHBoxLayout()

        from frontend.widgets.plot_widget import PlotWidget
        self.plot_cross_sections = PlotWidget(toolbar=True)
        plots_layout.addWidget(self.plot_cross_sections, stretch=1)

        self.plot_2d_psf = PlotWidget(toolbar=True)
        plots_layout.addWidget(self.plot_2d_psf, stretch=1)

        layout.addLayout(plots_layout, stretch=1)

        bottom_controls_layout = QHBoxLayout()

        display_group = QGroupBox("Display Options")
        display_layout = QHBoxLayout()

        units_label = QLabel("Units:")
        display_layout.addWidget(units_label)

        self.units_group = QButtonGroup()
        self.radio_microns = QRadioButton("μm")
        self.radio_canonical = QRadioButton("Canonical")
        self.radio_pixels = QRadioButton("Pixels")

        self.radio_microns.setChecked(True)

        self.units_group.addButton(self.radio_microns, 0)
        self.units_group.addButton(self.radio_canonical, 1)
        self.units_group.addButton(self.radio_pixels, 2)

        self.radio_microns.toggled.connect(self._on_units_changed)
        self.radio_canonical.toggled.connect(self._on_units_changed)
        self.radio_pixels.toggled.connect(self._on_units_changed)

        display_layout.addWidget(self.radio_microns)
        display_layout.addWidget(self.radio_canonical)
        display_layout.addWidget(self.radio_pixels)

        display_layout.addStretch()
        display_group.setLayout(display_layout)
        bottom_controls_layout.addWidget(display_group)

        info_group = QGroupBox("Information")
        info_layout = QHBoxLayout()

        self.info_max = QLabel("Max intensity: N/A")
        self.info_strehl = QLabel("Strehl ratio: N/A")
        self.info_time = QLabel("Computation time: N/A")

        info_layout.addWidget(self.info_max)
        info_layout.addWidget(QLabel(" | "))
        info_layout.addWidget(self.info_strehl)
        info_layout.addWidget(QLabel(" | "))
        info_layout.addWidget(self.info_time)
        info_layout.addStretch()

        info_group.setLayout(info_layout)
        bottom_controls_layout.addWidget(info_group)

        layout.addLayout(bottom_controls_layout, stretch=0)

        widget.setLayout(layout)
        return widget

    def _on_compute_clicked(self):
        logger.info("Compute PSF button clicked")
        params = {
            'sample_size': int(self.size_combo.currentText()),
            'wavelength': self.wavelength_spin.value(),
            'back_aperture': self.back_aperture_spin.value(),
            'magnification': self.magnification_spin.value(),
            'defocus': self.defocus_spin.value(),
            'astigmatism': self.astigmatism_spin.value(),
            'aperture': self.aperture_spin.value()
        }
        logger.info(f"PSF parameters: {params}")

        calc_params = {
            'size': params['sample_size'],
            'wavelength': params['wavelength'],
            'back_aperture': params['back_aperture'],
            'magnification': params['magnification'],
            'defocus': params['defocus'],
            'astigmatism': params['astigmatism'],
            'diam_pupil': params['aperture']
        }

        self.current_params = calc_params

        self.compute_thread = PSFComputeThread(calc_params)
        self.compute_thread.result_ready.connect(self._on_computation_finished)
        self.compute_thread.error_occurred.connect(self._on_computation_error)

        self._set_params_enabled(False)

        if params['sample_size'] >= 512:
            self.progress = QProgressDialog(
                "Computing PSF...", "Cancel", 0, 0, self)
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress.show()

        self.compute_thread.start()

    def _on_computation_finished(self, psf_data, elapsed_time, info):
        logger.info(f"PSF computation finished in {elapsed_time:.3f}s")
        logger.info(
            f"PSF size: {psf_data.shape}, step: {info['step_microns']:.6f} μm")

        self.current_psf = psf_data
        self.current_compute_time = elapsed_time
        self.current_step_microns = info['step_microns']

        if hasattr(self, 'progress'):
            self.progress.close()

        self._set_params_enabled(True)

        self._update_plots()

        self._update_info()

        self.psf_computed.emit(psf_data)
        logger.info("PSF transmitted to Image Processing")

    def _on_computation_error(self, error_msg):
        logger.error(f"PSF computation error: {error_msg}")

        if hasattr(self, 'progress'):
            self.progress.close()

        self._set_params_enabled(True)

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Computation Error",
                             f"Error during PSF computation:\n{error_msg}")

    def _on_reset_clicked(self):
        self.size_combo.setCurrentText('512')
        self.wavelength_spin.setValue(0.555)
        self.back_aperture_spin.setValue(1.2)
        self.magnification_spin.setValue(100.0)
        self.defocus_spin.setValue(0.0)
        self.astigmatism_spin.setValue(0.0)
        self.aperture_spin.setValue(7.5)
        logger.info("Parameters reset to defaults")

    def _set_params_enabled(self, enabled: bool):
        self.param_choice_combo.setEnabled(enabled)
        self.size_combo.setEnabled(enabled)
        self.wavelength_spin.setEnabled(enabled)
        self.back_aperture_spin.setEnabled(enabled)
        self.magnification_spin.setEnabled(enabled)
        self.defocus_spin.setEnabled(enabled)
        self.astigmatism_spin.setEnabled(enabled)

    def _on_step_obj_changed(self):
        if self.param_choice_combo.currentText() == 'Step object [c.u.]':
            self._recalculate_params()

    def _on_step_im_changed(self):
        if self.param_choice_combo.currentText() == 'Step image [c.u.]':
            self._recalculate_params()

    def _on_step_pupil_changed(self):
        if self.param_choice_combo.currentText() == 'Step pupil [c.u.]':
            self._recalculate_params()

    def _on_step_obj_unit_changed(self, unit: str):
        wavelength = self.wavelength_spin.value()
        magnification = self.magnification_spin.value()
        back_aperture = self.back_aperture_spin.value()
        aperture = magnification * back_aperture

        current_value = self.step_obj_can_spin.value()

        self.step_obj_can_spin.blockSignals(True)
        try:
            if unit == 'μm':
                new_value = current_value * wavelength / aperture
                self.step_obj_can_spin.setValue(new_value)
                logger.info(
                    f"Converted step_obj: {current_value:.6f} c.u. -> {new_value:.6f} μm")
            else:
                new_value = current_value * aperture / wavelength
                self.step_obj_can_spin.setValue(new_value)
                logger.info(
                    f"Converted step_obj: {current_value:.6f} μm -> {new_value:.6f} c.u.")
        finally:
            self.step_obj_can_spin.blockSignals(False)

    def _on_step_im_unit_changed(self, unit: str):
        wavelength = self.wavelength_spin.value()
        back_aperture = self.back_aperture_spin.value()

        current_value = self.step_im_can_spin.value()

        self.step_im_can_spin.blockSignals(True)
        try:
            if unit == 'μm':
                new_value = current_value * wavelength / back_aperture
                self.step_im_can_spin.setValue(new_value)
                logger.info(
                    f"Converted step_im: {current_value:.6f} c.u. -> {new_value:.6f} μm")
            else:
                new_value = current_value * back_aperture / wavelength
                self.step_im_can_spin.setValue(new_value)
                logger.info(
                    f"Converted step_im: {current_value:.6f} μm -> {new_value:.6f} c.u.")
        finally:
            self.step_im_can_spin.blockSignals(False)

    def _on_param_choice_changed(self):
        choice = self.param_choice_combo.currentText()

        READONLY_STYLE = "QDoubleSpinBox { background-color: #E0E0E0; color: #606060; }"
        EDITABLE_STYLE = ""

        self.aperture_spin.setReadOnly(True)
        self.step_pupil_spin.setReadOnly(True)
        self.step_obj_can_spin.setReadOnly(True)
        self.step_im_can_spin.setReadOnly(True)

        self.aperture_spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.step_pupil_spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.step_obj_can_spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.step_im_can_spin.setButtonSymbols(
            QDoubleSpinBox.ButtonSymbols.NoButtons)

        self.aperture_spin.setStyleSheet(READONLY_STYLE)
        self.step_pupil_spin.setStyleSheet(READONLY_STYLE)
        self.step_obj_can_spin.setStyleSheet(READONLY_STYLE)
        self.step_im_can_spin.setStyleSheet(READONLY_STYLE)

        if choice == 'Diam pupil [c.u.]':
            self.aperture_spin.setReadOnly(False)
            self.aperture_spin.setButtonSymbols(
                QDoubleSpinBox.ButtonSymbols.UpDownArrows)
            self.aperture_spin.setStyleSheet(EDITABLE_STYLE)
        elif choice == 'Step pupil [c.u.]':
            self.step_pupil_spin.setReadOnly(False)
            self.step_pupil_spin.setButtonSymbols(
                QDoubleSpinBox.ButtonSymbols.UpDownArrows)
            self.step_pupil_spin.setStyleSheet(EDITABLE_STYLE)
        elif choice == 'Step object [c.u.]':
            self.step_obj_can_spin.setReadOnly(False)
            self.step_obj_can_spin.setButtonSymbols(
                QDoubleSpinBox.ButtonSymbols.UpDownArrows)
            self.step_obj_can_spin.setStyleSheet(EDITABLE_STYLE)
        elif choice == 'Step image [c.u.]':
            self.step_im_can_spin.setReadOnly(False)
            self.step_im_can_spin.setButtonSymbols(
                QDoubleSpinBox.ButtonSymbols.UpDownArrows)
            self.step_im_can_spin.setStyleSheet(EDITABLE_STYLE)

        self._recalculate_params()
        logger.info(f"Changed source parameter to: {choice}")

    def _recalculate_params(self):
        choice = self.param_choice_combo.currentText()

        sample_size = int(self.size_combo.currentText())
        wavelength = self.wavelength_spin.value()
        back_aperture = self.back_aperture_spin.value()
        magnification = self.magnification_spin.value()

        aperture = magnification * back_aperture

        self.aperture_spin.blockSignals(True)
        self.step_pupil_spin.blockSignals(True)
        self.step_obj_can_spin.blockSignals(True)
        self.step_im_can_spin.blockSignals(True)

        try:
            step_obj_unit = self.step_obj_unit_combo.currentText()
            step_im_unit = self.step_im_unit_combo.currentText()

            if choice == 'Diam pupil [c.u.]':
                diam_pupil = self.aperture_spin.value()
                step_pupil = diam_pupil / sample_size
                step_im_can = 1 / step_pupil / sample_size
                step_obj_can = step_im_can

                self.step_pupil_spin.setValue(step_pupil)

                if step_obj_unit == 'μm':
                    self.step_obj_can_spin.setValue(
                        step_obj_can * wavelength / aperture)
                else:
                    self.step_obj_can_spin.setValue(step_obj_can)

                if step_im_unit == 'μm':
                    self.step_im_can_spin.setValue(
                        step_im_can * wavelength / back_aperture)
                else:
                    self.step_im_can_spin.setValue(step_im_can)

            elif choice == 'Step pupil [c.u.]':
                step_pupil = self.step_pupil_spin.value()
                if step_pupil == 0:
                    step_pupil = 0.001
                diam_pupil = step_pupil * sample_size
                step_im_can = 1 / step_pupil / sample_size
                step_obj_can = step_im_can

                self.aperture_spin.setValue(diam_pupil)

                if step_obj_unit == 'μm':
                    self.step_obj_can_spin.setValue(
                        step_obj_can * wavelength / aperture)
                else:
                    self.step_obj_can_spin.setValue(step_obj_can)

                if step_im_unit == 'μm':
                    self.step_im_can_spin.setValue(
                        step_im_can * wavelength / back_aperture)
                else:
                    self.step_im_can_spin.setValue(step_im_can)

            elif choice == 'Step object [c.u.]':
                if step_obj_unit == 'μm':
                    step_obj_microns = self.step_obj_can_spin.value()
                    step_obj_can = step_obj_microns * aperture / wavelength
                else:
                    step_obj_can = self.step_obj_can_spin.value()

                if step_obj_can == 0:
                    step_obj_can = 0.001
                step_pupil = 1 / step_obj_can / sample_size
                diam_pupil = step_pupil * sample_size
                step_im_can = step_obj_can

                self.aperture_spin.setValue(diam_pupil)
                self.step_pupil_spin.setValue(step_pupil)

                if step_im_unit == 'μm':
                    self.step_im_can_spin.setValue(
                        step_im_can * wavelength / back_aperture)
                else:
                    self.step_im_can_spin.setValue(step_im_can)

            elif choice == 'Step image [c.u.]':
                if step_im_unit == 'μm':
                    step_im_microns = self.step_im_can_spin.value()
                    step_im_can = step_im_microns * back_aperture / wavelength
                else:
                    step_im_can = self.step_im_can_spin.value()

                if step_im_can == 0:
                    step_im_can = 0.001
                step_obj_can = step_im_can
                step_pupil = 1 / step_im_can / sample_size
                diam_pupil = step_pupil * sample_size

                self.aperture_spin.setValue(diam_pupil)
                self.step_pupil_spin.setValue(step_pupil)

                if step_obj_unit == 'μm':
                    self.step_obj_can_spin.setValue(
                        step_obj_can * wavelength / aperture)
                else:
                    self.step_obj_can_spin.setValue(step_obj_can)

        finally:
            self.aperture_spin.blockSignals(False)
            self.step_pupil_spin.blockSignals(False)
            self.step_obj_can_spin.blockSignals(False)
            self.step_im_can_spin.blockSignals(False)

    def _on_units_changed(self):
        if self.radio_microns.isChecked():
            self.current_units = 'microns'
        elif self.radio_canonical.isChecked():
            self.current_units = 'canonical'
        else:
            self.current_units = 'pixels'

        if self.current_psf is not None:
            self._update_plots()

    def _update_plots(self):
        if self.current_psf is None:
            return

        psf = self.current_psf
        size = psf.shape[0]

        if self.current_units == 'microns':
            coords = np.arange(size) * self.current_step_microns
            coords = coords - coords[size // 2]
            unit_label = 'μm'
        elif self.current_units == 'canonical':
            step_canonical = (
                self.current_params['wavelength'] / self.current_params['back_aperture']) / size
            coords = np.arange(size) * step_canonical
            coords = coords - coords[size // 2]
            unit_label = 'canonical units'
        else:
            coords = np.arange(size)
            coords = coords - size // 2
            unit_label = 'pixels'

        self.plot_cross_sections.clear()
        self.plot_2d_psf.clear()

        ax0 = self.plot_cross_sections.get_axes()
        center_idx = size // 2

        x_section = psf[center_idx, :]
        ax0.plot(coords, x_section, 'r-', label='X section', linewidth=2)

        y_section = psf[:, center_idx]
        ax0.plot(coords, y_section, 'b-', label='Y section', linewidth=2)

        ax0.set_xlabel(f'Position [{unit_label}]')
        ax0.set_ylabel('Intensity')
        ax0.set_title('PSF Cross-Sections')
        ax0.legend()
        ax0.grid(True, alpha=0.3)

        ax0.set_aspect('auto')

        ax1 = self.plot_2d_psf.get_axes()
        extent = [coords[0], coords[-1], coords[0], coords[-1]]

        im = ax1.imshow(psf, cmap='gray', extent=extent,
                        origin='lower', aspect='equal')
        ax1.set_xlabel(f'X [{unit_label}]')
        ax1.set_ylabel(f'Y [{unit_label}]')
        ax1.set_title('2D PSF (Grayscale)')

        ax1.set_aspect('equal', adjustable='box')

        self.plot_cross_sections.refresh()
        self.plot_2d_psf.refresh()

    def _update_info(self):
        if self.current_psf is None:
            return

        max_intensity = np.max(self.current_psf)
        self.info_max.setText(f"Max intensity: {max_intensity:.6f}")

        center_idx = self.current_psf.shape[0] // 2
        center_intensity = self.current_psf[center_idx, center_idx]

        strehl_ratio = center_intensity / max_intensity if max_intensity > 0 else 0.0
        self.info_strehl.setText(f"Strehl ratio: {strehl_ratio:.4f}")

        self.info_time.setText(
            f"Computation time: {self.current_compute_time:.3f} s")
