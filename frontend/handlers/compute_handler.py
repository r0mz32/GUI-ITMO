# computation handler for PSF calculations

import logging
import numpy as np
import time
from typing import List
from PyQt6.QtWidgets import QMessageBox, QProgressDialog
from PyQt6.QtCore import Qt
from scipy.signal import fftconvolve
from frontend.models.compute_thread import PSFComputeThread
from frontend.utils.calculations import calculate_strehl_ratio

logger = logging.getLogger(__name__)


class ComputeHandler:
    """handles PSF computations"""

    def __init__(self, psf_calculator, psf_tab_ref):
        self.calculator = psf_calculator
        self.parent = psf_tab_ref
        self.compute_thread = None
        self.computing_rows = []
        self.computation_cancelled = False
        self.progress_dialog = None

    def compute_row(self, idx: int):
        """compute PSF for one row"""
        if idx < 0 or idx >= len(self.parent.table_rows):
            return

        row = self.parent.table_rows[idx]

        # validate row using validators module
        from frontend.utils.validators import validate_row_params
        is_valid, error_msg = validate_row_params(row)

        if not is_valid:
            row.status = "error"
            row.error_message = error_msg
            self.parent.table_handler.update_table_row(idx)
            QMessageBox.critical(self.parent, "Validation Error", error_msg)
            logger.error(f"Row {idx + 1} validation failed: {error_msg}")
            return

        row.status = "computing"
        self.parent.table_handler.update_table_row(idx)

        params = row.get_params()

        thread = PSFComputeThread(params)
        thread.result_ready.connect(
            lambda psf, time, info: self.on_row_computed(idx, psf, time, info))
        thread.error_occurred.connect(
            lambda err: self.on_row_error(idx, err))

        self.compute_thread = thread
        thread.start()

    def compute_multiple_rows(self, indices: List[int]):
        """compute multiple rows sequentially"""
        if not indices:
            return

        indices = [i for i in indices if 0 <= i < len(self.parent.table_rows)]
        if not indices:
            return

        self.computing_rows = indices.copy()
        self.computation_cancelled = False

        self.progress_dialog = QProgressDialog(
            f"Computing PSF 0/{len(indices)}...",
            "Cancel",
            0, len(indices),
            self.parent
        )
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.canceled.connect(self._on_computation_cancelled)
        self.progress_dialog.show()

        self._compute_next_in_queue()

    def _compute_next_in_queue(self):
        """compute next row in queue"""
        if self.computation_cancelled or not self.computing_rows:
            if self.progress_dialog:
                self.progress_dialog.close()
            logger.info("Computation queue finished")
            return

        idx = self.computing_rows.pop(0)

        if self.progress_dialog:
            total_rows = self.progress_dialog.maximum()
            current_row = total_rows - len(self.computing_rows)
            self.progress_dialog.setValue(current_row)
            self.progress_dialog.setLabelText(
                f"Computing PSF {current_row}/{total_rows}...")

        self.compute_row(idx)

    def on_row_computed(self, idx: int, psf_data: np.ndarray, elapsed_time: float, info: dict):
        """callback when row computation finishes"""
        if idx < 0 or idx >= len(self.parent.table_rows):
            return

        row = self.parent.table_rows[idx]
        row.psf_data = psf_data
        row.compute_time = elapsed_time
        row.status = "complete"
        row.error_message = ""

        logger.info(
            f"Row {idx + 1} PSF computed: defocus={row.defocus}, max={np.max(psf_data):.6f}")

        # calculate Strehl ratio
        row.strehl_ratio = calculate_strehl_ratio(psf_data)

        self.parent.table_handler.update_table_row(idx)

        logger.info(
            f"Row {idx + 1} computed: Strehl={row.strehl_ratio:.4f}, time={elapsed_time:.3f}s")

        # update plots only if this is the selected row AND not computing for system PSF
        if idx == self.parent.selected_row_idx and not self.parent.compute_system_after:
            self.parent.current_psf = psf_data
            self.parent.current_params = row.get_params()
            self.parent.current_step_microns = info['step_microns']
            self.parent.current_compute_time = elapsed_time
            self.parent.current_strehl_ratio = row.strehl_ratio
            self.parent._update_plots()
            self.parent._update_info()

        if self.computing_rows:
            self._compute_next_in_queue()
        else:
            if self.progress_dialog:
                # disconnect canceled signal before closing
                self.progress_dialog.canceled.disconnect()
                self.progress_dialog.close()
            # check if we need to compute system PSF after all rows
            if self.parent.compute_system_after:
                self.parent.compute_system_after = False
                logger.info("All rows computed, computing system PSF...")
                self.compute_system_psf()

    def on_row_error(self, idx: int, error_msg: str):
        """callback when row computation fails"""
        if idx < 0 or idx >= len(self.parent.table_rows):
            return

        row = self.parent.table_rows[idx]
        row.status = "error"
        row.error_message = error_msg
        self.parent.table_handler.update_table_row(idx)

        logger.error(f"Row {idx + 1} computation error: {error_msg}")

        if self.computing_rows:
            self._compute_next_in_queue()
        else:
            if self.progress_dialog:
                # disconnect canceled signal before closing
                self.progress_dialog.canceled.disconnect()
                self.progress_dialog.close()

    def _on_computation_cancelled(self):
        """cancel computation"""
        self.computation_cancelled = True
        self.computing_rows.clear()
        self.parent.compute_system_after = False  # reset flag
        logger.info("Computation cancelled by user")

    def compute_system_psf(self):
        """compute system PSF by convolving all row PSFs"""
        if not self.parent.table_rows:
            return

        start_time = time.time()

        # start with first row PSF (already normalized to energy=1)
        result_psf = self.parent.table_rows[0].psf_data.copy()

        # convolve with each subsequent row
        for idx in range(1, len(self.parent.table_rows)):
            row = self.parent.table_rows[idx]
            result_psf = fftconvolve(result_psf, row.psf_data, mode='same')
            # normalize to energy=1 after each convolution (physically correct)
            total_energy = np.sum(result_psf)
            if total_energy > 0:
                result_psf = result_psf / total_energy

        self.parent.system_psf = result_psf
        self.parent.system_psf_valid = True
        self.parent.system_compute_time = time.time() - start_time

        # calculate Strehl ratio for system PSF
        self.parent.system_strehl_ratio = calculate_strehl_ratio(result_psf)

        logger.info(
            f"System PSF computed from {len(self.parent.table_rows)} rows in {self.parent.system_compute_time:.3f}s, Strehl={self.parent.system_strehl_ratio:.4f}")

        # display system PSF
        self.display_system_psf()

    def display_system_psf(self):
        """display system PSF on plots"""
        if self.parent.system_psf is None:
            return

        # use parameters from first row for display
        first_row = self.parent.table_rows[0]
        self.parent.current_psf = self.parent.system_psf
        self.parent.current_params = first_row.get_params()
        self.parent.current_step_microns = first_row.step_obj_microns
        self.parent.current_compute_time = self.parent.system_compute_time
        self.parent.current_strehl_ratio = self.parent.system_strehl_ratio

        self.parent._update_plots()
        self.parent._update_info()
