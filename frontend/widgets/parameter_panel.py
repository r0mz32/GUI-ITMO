# панель параметров

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
    QGroupBox, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal, Qt
from typing import Dict, Any, List, Tuple


class ParameterPanel(QWidget):

    # сигнал при изменении
    parameters_changed = pyqtSignal(dict)

    def __init__(self, parent=None, title="Parameters"):
        super().__init__(parent)

        # виджеты: {name: widget}
        self.widgets = {}

        # конфиги: {name: config}
        self.configs = {}

        # layout
        main_layout = QVBoxLayout()

        # группа
        self.group_box = QGroupBox(title)
        self.form_layout = QFormLayout()
        self.group_box.setLayout(self.form_layout)

        main_layout.addWidget(self.group_box)
        main_layout.addStretch()

        self.setLayout(main_layout)

    def add_parameter(self, name: str, label: str, widget_type: str,
                     default_value: Any = None, **kwargs):
        widget = None

        if widget_type == 'int':
            widget = QSpinBox()
            widget.setMinimum(kwargs.get('min', 0))
            widget.setMaximum(kwargs.get('max', 10000))
            widget.setSingleStep(kwargs.get('step', 1))
            if default_value is not None:
                widget.setValue(int(default_value))
            widget.valueChanged.connect(lambda: self._on_value_changed())

        elif widget_type == 'double':
            widget = QDoubleSpinBox()
            widget.setMinimum(kwargs.get('min', 0.0))
            widget.setMaximum(kwargs.get('max', 10000.0))
            widget.setSingleStep(kwargs.get('step', 0.1))
            widget.setDecimals(kwargs.get('decimals', 3))
            if default_value is not None:
                widget.setValue(float(default_value))
            widget.valueChanged.connect(lambda: self._on_value_changed())

        elif widget_type == 'combo':
            widget = QComboBox()
            items = kwargs.get('items', [])
            widget.addItems([str(item) for item in items])
            if default_value is not None:
                index = widget.findText(str(default_value))
                if index >= 0:
                    widget.setCurrentIndex(index)
            widget.currentTextChanged.connect(lambda: self._on_value_changed())

        elif widget_type == 'text':
            widget = QLineEdit()
            if default_value is not None:
                widget.setText(str(default_value))
            widget.textChanged.connect(lambda: self._on_value_changed())

        if widget is not None:
            # единицы измерения
            if 'suffix' in kwargs and hasattr(widget, 'setSuffix'):
                widget.setSuffix(f" {kwargs['suffix']}")

            # добавляем в form
            self.form_layout.addRow(f"{label}:", widget)
            self.widgets[name] = widget
            self.configs[name] = {
                'type': widget_type,
                'label': label,
                **kwargs
            }

    def get_value(self, name: str) -> Any:
        if name not in self.widgets:
            return None

        widget = self.widgets[name]
        config = self.configs[name]

        if config['type'] == 'int':
            return widget.value()
        elif config['type'] == 'double':
            return widget.value()
        elif config['type'] == 'combo':
            return widget.currentText()
        elif config['type'] == 'text':
            return widget.text()

        return None

    def set_value(self, name: str, value: Any):
        if name not in self.widgets:
            return

        widget = self.widgets[name]
        config = self.configs[name]

        if config['type'] == 'int':
            widget.setValue(int(value))
        elif config['type'] == 'double':
            widget.setValue(float(value))
        elif config['type'] == 'combo':
            index = widget.findText(str(value))
            if index >= 0:
                widget.setCurrentIndex(index)
        elif config['type'] == 'text':
            widget.setText(str(value))

    def get_all_values(self) -> Dict[str, Any]:
        return {name: self.get_value(name) for name in self.widgets.keys()}

    def set_all_values(self, values: Dict[str, Any]):
        for name, value in values.items():
            self.set_value(name, value)

    def _on_value_changed(self):
        self.parameters_changed.emit(self.get_all_values())

    def set_enabled(self, name: str, enabled: bool):
        if name in self.widgets:
            self.widgets[name].setEnabled(enabled)

    def set_visible(self, name: str, visible: bool):
        if name in self.widgets:
            self.widgets[name].setVisible(visible)
