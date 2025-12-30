# file operations handler (save/load/export)

import logging
import json
import numpy as np
from datetime import datetime
from PyQt6.QtWidgets import QFileDialog, QMessageBox

logger = logging.getLogger(__name__)


class FileHandler:
    """handles file operations (save, load, export)"""

    def __init__(self, psf_tab_ref):
        self.parent = psf_tab_ref

    def save_config(self, filename: str = None):
        """save configuration to JSON"""
        if not self.parent.table_rows:
            QMessageBox.information(self.parent, "No Data", "No rows to save.")
            return

        if not filename:
            # default filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"optical_system_config_{timestamp}.json"

            filename, _ = QFileDialog.getSaveFileName(
                self.parent, "Save Configuration", default_filename,
                "JSON Files (*.json)"
            )

        if not filename:
            return

        try:
            config = {
                'version': '1.0',
                'sample_size': int(self.parent.control_panel.sample_size_combo.currentText()),
                'source_param': self.parent.param_choice_combo.currentText(),
                'source_param_value': self.parent.source_param_spin.value(),
                'source_param_units': self.parent.source_param_units_combo.currentText(),
                'rows': [row.to_dict() for row in self.parent.table_rows]
            }

            with open(filename, 'w') as f:
                json.dump(config, f, indent=2)

            logger.info(f"Saved configuration to {filename}")
            QMessageBox.information(
                self.parent, "Saved", f"Configuration saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            QMessageBox.critical(
                self.parent, "Error", f"Failed to save configuration:\n{e}")

    def load_config(self, filename: str = None):
        """load configuration from JSON"""
        from frontend.models.optical_row import OpticalSystemRow

        if not filename:
            filename, _ = QFileDialog.getOpenFileName(
                self.parent, "Load Configuration", "", "JSON Files (*.json)"
            )

        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                config = json.load(f)

            # validate config format
            if 'version' not in config:
                raise ValueError("Missing 'version' field in config file")
            if 'rows' not in config:
                raise ValueError("Missing 'rows' field in config file")
            if not isinstance(config['rows'], list):
                raise ValueError("'rows' must be a list")
            if len(config['rows']) == 0:
                raise ValueError("Config file contains no rows")

            # validate each row has required fields
            required_fields = ['wavelength', 'back_aperture',
                             'magnification', 'sample_size']
            for i, row_dict in enumerate(config['rows']):
                for field in required_fields:
                    if field not in row_dict:
                        raise ValueError(
                            f"Row {i+1} missing required field '{field}'")

            # if validation passed, load config
            self.parent.table_rows.clear()
            self.parent.table.setRowCount(0)

            # restore source parameter settings (block signals)
            self.parent.param_choice_combo.blockSignals(True)
            self.parent.source_param_units_combo.blockSignals(True)
            self.parent.source_param_spin.blockSignals(True)
            self.parent.control_panel.sample_size_combo.blockSignals(True)

            if 'sample_size' in config:
                self.parent.control_panel.sample_size_combo.setCurrentText(str(config['sample_size']))
            if 'source_param' in config:
                self.parent.param_choice_combo.setCurrentText(config['source_param'])
                # trigger _on_param_changed to adjust spinbox settings
                self.parent.control_panel._on_param_changed(config['source_param'])
            if 'source_param_units' in config:
                self.parent.source_param_units_combo.setCurrentText(
                    config['source_param_units'])
            if 'source_param_value' in config:
                self.parent.source_param_spin.setValue(config['source_param_value'])

            self.parent.param_choice_combo.blockSignals(False)
            self.parent.source_param_units_combo.blockSignals(False)
            self.parent.source_param_spin.blockSignals(False)
            self.parent.control_panel.sample_size_combo.blockSignals(False)

            # load rows
            for row_dict in config['rows']:
                row = OpticalSystemRow.from_dict(row_dict)
                self.parent.table_handler.add_row(row)

            # invalidate system PSF
            self.parent.system_psf_valid = False

            # select first row if available
            if self.parent.table_rows:
                self.parent.table.selectRow(0)

            logger.info(f"Loaded configuration from {filename}: {len(self.parent.table_rows)} rows")
            QMessageBox.information(
                self.parent, "Loaded",
                f"Configuration loaded successfully:\n"
                f"File: {filename}\n"
                f"Rows: {len(self.parent.table_rows)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON file: {e}")
            QMessageBox.critical(
                self.parent, "Invalid File",
                f"Failed to parse JSON file:\n{e}")
        except ValueError as e:
            logger.error(f"Invalid config format: {e}")
            QMessageBox.critical(
                self.parent, "Invalid Configuration",
                f"Configuration file validation failed:\n{e}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            QMessageBox.critical(
                self.parent, "Error", f"Failed to load configuration:\n{e}")

    def export_plots(self, filename: str = None):
        """export plots to PNG"""
        # check if there's data to export
        if self.parent.current_psf is None:
            QMessageBox.warning(
                self.parent, "No Data",
                "No PSF data to export.\n\n"
                "Please compute PSF for at least one row or select a computed row.")
            logger.warning("Export plots attempted with no PSF data")
            return

        if not filename:
            # default filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"psf_plot_{timestamp}.png"

            filename, _ = QFileDialog.getSaveFileName(
                self.parent, "Export Plots", default_filename, "PNG Files (*.png)"
            )

        if not filename:
            return

        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg

            fig = Figure(figsize=(16, 8), dpi=100)

            # add title with parameters
            if (self.parent.selected_row_idx >= 0 and
                self.parent.selected_row_idx < len(self.parent.table_rows)):
                row = self.parent.table_rows[self.parent.selected_row_idx]
                title = (f"PSF: λ={row.wavelength:.3f}μm, NA={row.back_aperture:.2f}, "
                        f"Mag={row.magnification:.1f}x, Defoc={row.defocus:.2f}λ, "
                        f"Astig={row.astigmatism:.2f}λ, Strehl={row.strehl_ratio:.4f}")
                fig.suptitle(title, fontsize=14)

            psf = self.parent.current_psf
            size = psf.shape[0]

            # normalize PSF for visualization
            psf_normalized = psf / np.max(psf) if np.max(psf) > 0 else psf

            # calculate coordinates
            if self.parent.current_units == 'microns':
                coords = np.arange(size) * self.parent.current_step_microns
                coords = coords - coords[size // 2]
                unit_label = 'μm'
            elif self.parent.current_units == 'canonical':
                step_canonical = (self.parent.current_params['wavelength'] /
                                self.parent.current_params['back_aperture']) / size
                coords = np.arange(size) * step_canonical
                coords = coords - coords[size // 2]
                unit_label = 'canonical units'
            else:
                coords = np.arange(size)
                coords = coords - size // 2
                unit_label = 'pixels'

            # subplot 1: cross-sections
            ax1 = fig.add_subplot(1, 2, 1)
            center_idx = size // 2
            x_section = psf_normalized[center_idx, :]
            ax1.plot(coords, x_section, 'r-', label='X section', linewidth=2)
            y_section = psf_normalized[:, center_idx]
            ax1.plot(coords, y_section, 'b-', label='Y section', linewidth=2)
            ax1.set_xlabel(f'Position [{unit_label}]')
            ax1.set_ylabel('Normalized Intensity')
            ax1.set_title('PSF Cross-Sections')
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # subplot 2: 2D PSF
            ax2 = fig.add_subplot(1, 2, 2)
            extent = [coords[0], coords[-1], coords[0], coords[-1]]
            im = ax2.imshow(psf_normalized, cmap='gray', extent=extent,
                          origin='lower', aspect='equal', vmin=0, vmax=1)
            ax2.set_xlabel(f'X [{unit_label}]')
            ax2.set_ylabel(f'Y [{unit_label}]')
            ax2.set_title('2D PSF')
            fig.colorbar(im, ax=ax2, label='Normalized Intensity')

            fig.tight_layout()

            canvas = FigureCanvasAgg(fig)
            canvas.print_png(filename)

            logger.info(f"Plots exported to {filename}")
            QMessageBox.information(
                self.parent, "Exported", f"Plots saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to export plots: {e}")
            QMessageBox.critical(
                self.parent, "Error", f"Failed to export plots:\n{e}")
