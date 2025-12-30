# PSF computation thread

import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal
import numpy as np
from psf_wrapper import PSFCalculator

logger = logging.getLogger(__name__)


class PSFComputeThread(QThread):
    """background thread for PSF computation"""

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
