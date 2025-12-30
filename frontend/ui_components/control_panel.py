# control panel UI components

from PyQt6.QtWidgets import (QWidget, QGroupBox, QHBoxLayout, QVBoxLayout,
                             QRadioButton, QButtonGroup, QLabel, QComboBox, QDoubleSpinBox)
from PyQt6.QtCore import pyqtSignal


class ControlPanel(QWidget):
    """control panel for units, source parameter, and information display"""

    units_changed = pyqtSignal(str)
    source_param_changed = pyqtSignal(str)
    source_units_changed = pyqtSignal(str)
    source_value_changed = pyqtSignal(float)
    sample_size_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._create_ui()
        # initialize units combo state based on default parameter (Diam pupil)
        self._on_param_changed(self.param_choice_combo.currentText())

    def _create_ui(self):
        """create control panel UI"""
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        # sample size (1 part)
        layout.addWidget(self.create_sample_size_group(), stretch=1)

        # units (1 part)
        layout.addWidget(self.create_units_group(), stretch=1)

        # source parameter (2 parts = size of sample + units)
        layout.addWidget(self.create_source_param_group(), stretch=2)

        # information (rest of space)
        layout.addWidget(self.create_info_group(), stretch=3)

        self.setLayout(layout)

    def create_sample_size_group(self) -> QGroupBox:
        """create sample size selection group"""
        group = QGroupBox("Sample Size")
        layout = QHBoxLayout()

        self.sample_size_combo = QComboBox()
        self.sample_size_combo.addItems(['512', '1024', '2048'])
        self.sample_size_combo.setCurrentText('512')
        self.sample_size_combo.currentTextChanged.connect(
            lambda text: self.sample_size_changed.emit(int(text)))

        layout.addWidget(self.sample_size_combo)
        group.setLayout(layout)

        return group

    def create_units_group(self) -> QGroupBox:
        """create units selection group"""
        group = QGroupBox("Units")
        layout = QHBoxLayout()

        self.units_group = QButtonGroup()
        self.radio_microns = QRadioButton("μm")
        self.radio_canonical = QRadioButton("Can")
        self.radio_pixels = QRadioButton("Pix")

        self.radio_microns.setChecked(True)

        self.units_group.addButton(self.radio_microns, 0)
        self.units_group.addButton(self.radio_canonical, 1)
        self.units_group.addButton(self.radio_pixels, 2)

        self.radio_microns.toggled.connect(self._on_units_toggled)
        self.radio_canonical.toggled.connect(self._on_units_toggled)
        self.radio_pixels.toggled.connect(self._on_units_toggled)

        layout.addWidget(self.radio_microns)
        layout.addWidget(self.radio_canonical)
        layout.addWidget(self.radio_pixels)
        group.setLayout(layout)

        return group

    def create_info_group(self) -> QGroupBox:
        """create information display group"""
        from PyQt6.QtCore import Qt

        group = QGroupBox("Information")
        layout = QVBoxLayout()
        layout.setSpacing(2)

        self.info_label = QLabel("Max: N/A | Time: N/A | Strehl: N/A")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.info_label)
        group.setLayout(layout)

        return group

    def create_source_param_group(self) -> QGroupBox:
        """create source parameter group"""
        group = QGroupBox("Source Parameter")
        layout = QHBoxLayout()

        # parameter selection
        layout.addWidget(QLabel("Param:"))
        self.param_choice_combo = QComboBox()
        self.param_choice_combo.addItems([
            'Diam pupil',
            'Step pupil',
            'Step object',
            'Step image'
        ])
        self.param_choice_combo.currentTextChanged.connect(self._on_param_changed)
        layout.addWidget(self.param_choice_combo, stretch=1)

        # units selection
        self.units_label = QLabel("Units:")
        layout.addWidget(self.units_label)
        self.source_param_units_combo = QComboBox()
        self.source_param_units_combo.addItems(['c.u.', 'μm'])
        self.source_param_units_combo.currentTextChanged.connect(
            lambda t: self.source_units_changed.emit(t))
        layout.addWidget(self.source_param_units_combo)

        # value input
        layout.addWidget(QLabel("Value:"))
        self.source_param_spin = QDoubleSpinBox()
        self.source_param_spin.setRange(0.001, 1000.0)
        self.source_param_spin.setValue(7.5)
        self.source_param_spin.setDecimals(6)
        self.source_param_spin.setSingleStep(0.1)
        self.source_param_spin.setMinimumWidth(100)
        self.source_param_spin.valueChanged.connect(
            lambda v: self.source_value_changed.emit(v))
        layout.addWidget(self.source_param_spin, stretch=1)

        group.setLayout(layout)
        return group

    def _on_units_toggled(self):
        """handle units radio button toggle"""
        if self.radio_microns.isChecked():
            self.units_changed.emit('microns')
        elif self.radio_canonical.isChecked():
            self.units_changed.emit('canonical')
        elif self.radio_pixels.isChecked():
            self.units_changed.emit('pixels')

    def _on_param_changed(self, param: str):
        """handle source parameter change"""
        # adjust spinbox settings based on parameter
        if param in ['Diam pupil', 'Step pupil']:
            # only c.u. is available
            self.source_param_units_combo.setEnabled(False)
            self.source_param_units_combo.setCurrentText('c.u.')
            self.units_label.setEnabled(False)

            # set range and default value
            if param == 'Diam pupil':
                self.source_param_spin.setRange(0.1, 100.0)
                self.source_param_spin.setValue(7.5)
                self.source_param_spin.setDecimals(3)
                self.source_param_spin.setSingleStep(0.1)
            else:  # Step pupil
                self.source_param_spin.setRange(0.001, 1.0)
                self.source_param_spin.setValue(0.015)
                self.source_param_spin.setDecimals(6)
                self.source_param_spin.setSingleStep(0.001)
        else:
            # for Step object and Step image, both c.u. and μm are available
            self.source_param_units_combo.setEnabled(True)
            self.units_label.setEnabled(True)

            # get current units
            units = self.source_param_units_combo.currentText()

            if param == 'Step object':
                if units == 'c.u.':
                    self.source_param_spin.setRange(0.001, 10.0)
                    self.source_param_spin.setValue(0.133)
                else:  # μm
                    self.source_param_spin.setRange(0.001, 100.0)
                    self.source_param_spin.setValue(0.073)
                self.source_param_spin.setDecimals(6)
                self.source_param_spin.setSingleStep(0.01)
            else:  # Step image
                if units == 'c.u.':
                    self.source_param_spin.setRange(0.001, 10.0)
                    self.source_param_spin.setValue(0.133)
                else:  # μm
                    self.source_param_spin.setRange(0.001, 100.0)
                    self.source_param_spin.setValue(0.462)
                self.source_param_spin.setDecimals(6)
                self.source_param_spin.setSingleStep(0.01)

        # emit signal after updating units state
        self.source_param_changed.emit(param)

    def update_source_param_for_units_change(self, units: str):
        """update source param spinbox when units change"""
        param = self.param_choice_combo.currentText()

        if param not in ['Step object', 'Step image']:
            return

        self.source_param_spin.blockSignals(True)

        if param == 'Step object':
            if units == 'c.u.':
                self.source_param_spin.setRange(0.001, 10.0)
                self.source_param_spin.setValue(0.133)
            else:  # μm
                self.source_param_spin.setRange(0.001, 100.0)
                self.source_param_spin.setValue(0.073)
        else:  # Step image
            if units == 'c.u.':
                self.source_param_spin.setRange(0.001, 10.0)
                self.source_param_spin.setValue(0.133)
            else:  # μm
                self.source_param_spin.setRange(0.001, 100.0)
                self.source_param_spin.setValue(0.462)

        self.source_param_spin.blockSignals(False)

    def update_info(self, max_intensity: float, compute_time: float, strehl_ratio: float = None):
        """update information label"""
        if max_intensity is None or compute_time is None:
            self.info_label.setText("Max: N/A | Time: N/A | Strehl: N/A")
        else:
            if strehl_ratio is not None:
                self.info_label.setText(
                    f"Max: {max_intensity:.6f} | Time: {compute_time:.3f} s | Strehl: {strehl_ratio:.4f}")
            else:
                self.info_label.setText(
                    f"Max: {max_intensity:.6f} | Time: {compute_time:.3f} s | Strehl: N/A")
