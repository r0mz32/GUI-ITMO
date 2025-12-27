# виджет для matplotlib

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar


class PlotWidget(QWidget):

    def __init__(self, parent=None, toolbar=True):
        super().__init__(parent)

        # figure и canvas
        self.figure = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.updateGeometry()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # toolbar (опционально)
        if toolbar:
            self.toolbar = NavigationToolbar(self.canvas, self)
            layout.addWidget(self.toolbar)
        else:
            self.toolbar = None

        layout.addWidget(self.canvas)
        self.setLayout(layout)

        # axes создаются по требованию
        self.axes = None

    def clear(self):
        self.figure.clear()
        self.axes = None
        self.canvas.draw()

    def get_axes(self, subplot=(1, 1, 1)):
        if self.axes is None:
            self.axes = self.figure.add_subplot(*subplot)
        return self.axes

    def plot_line(self, x, y, label=None, color=None, linewidth=2, **kwargs):
        ax = self.get_axes()
        line = ax.plot(x, y, label=label, color=color, linewidth=linewidth, **kwargs)
        return line

    def plot_image(self, data, cmap='gray', extent=None, aspect='auto', **kwargs):
        ax = self.get_axes()
        im = ax.imshow(data, cmap=cmap, extent=extent, aspect=aspect, origin='lower', **kwargs)
        return im

    def set_labels(self, xlabel=None, ylabel=None, title=None):
        ax = self.get_axes()
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)

    def set_grid(self, visible=True, **kwargs):
        ax = self.get_axes()
        ax.grid(visible, **kwargs)

    def add_legend(self, **kwargs):
        ax = self.get_axes()
        ax.legend(**kwargs)

    def refresh(self):
        self.canvas.draw()
        self.canvas.flush_events()


class MultiPlotWidget(QWidget):

    def __init__(self, parent=None, rows=1, cols=1, toolbar=True):
        super().__init__(parent)

        # figure и canvas
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.updateGeometry()

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # toolbar (опционально)
        if toolbar:
            self.toolbar = NavigationToolbar(self.canvas, self)
            layout.addWidget(self.toolbar)
        else:
            self.toolbar = None

        layout.addWidget(self.canvas)
        self.setLayout(layout)

        # subplots
        self.rows = rows
        self.cols = cols
        self.axes_list = []
        self._create_subplots()

    def _create_subplots(self):
        self.figure.clear()
        self.axes_list = []
        for i in range(self.rows * self.cols):
            ax = self.figure.add_subplot(self.rows, self.cols, i + 1)
            self.axes_list.append(ax)
        self.figure.tight_layout()

    def get_axes(self, index=0):
        if 0 <= index < len(self.axes_list):
            return self.axes_list[index]
        return None

    def clear(self):
        self.figure.clear()
        self._create_subplots()
        self.canvas.draw()

    def refresh(self):
        self.figure.tight_layout()
        self.canvas.draw()
        self.canvas.flush_events()
