# parameter validation utilities

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def validate_row_params(row) -> Tuple[bool, str]:
    """
    validate all parameters in an OpticalSystemRow
    returns: (is_valid, error_message)
    """
    try:
        from main import OpticalLimits
    except ImportError:
        logger.warning("Could not import OpticalLimits from main, using basic validation")
        # basic validation without limits
        if row.wavelength <= 0:
            return False, "Wavelength must be positive (> 0)"
        if row.back_aperture <= 0:
            return False, "NA must be positive (> 0)"
        if row.magnification <= 0:
            return False, "Magnification must be positive (> 0)"
        if row.diam_pupil <= 0:
            return False, "Pupil diameter must be positive (> 0)"
        return True, ""

    # validate wavelength
    valid, msg = OpticalLimits.validate_wavelength(row.wavelength)
    if not valid:
        return False, f"Wavelength: {msg}"

    # validate NA
    valid, msg = OpticalLimits.validate_na(row.back_aperture)
    if not valid:
        return False, f"NA: {msg}"

    # validate magnification
    valid, msg = OpticalLimits.validate_magnification(row.magnification)
    if not valid:
        return False, f"Magnification: {msg}"

    # validate defocus
    valid, msg = OpticalLimits.validate_defocus(row.defocus)
    if not valid:
        return False, f"Defocus: {msg}"

    # validate astigmatism
    valid, msg = OpticalLimits.validate_astigmatism(row.astigmatism)
    if not valid:
        return False, f"Astigmatism: {msg}"

    # validate pupil diameter
    valid, msg = OpticalLimits.validate_diam_pupil(row.diam_pupil)
    if not valid:
        return False, f"Pupil diameter: {msg}"

    # validate computed steps if they are non-zero
    if row.step_obj_can != 0:
        valid, msg = OpticalLimits.validate_step(row.step_obj_can, in_microns=False)
        if not valid:
            return False, f"Step object (c.u.): {msg}"

    if row.step_obj_microns != 0:
        valid, msg = OpticalLimits.validate_step(row.step_obj_microns, in_microns=True)
        if not valid:
            return False, f"Step object (μm): {msg}"

    if row.step_im_can != 0:
        valid, msg = OpticalLimits.validate_step(row.step_im_can, in_microns=False)
        if not valid:
            return False, f"Step image (c.u.): {msg}"

    if row.step_im_microns != 0:
        valid, msg = OpticalLimits.validate_step(row.step_im_microns, in_microns=True)
        if not valid:
            return False, f"Step image (μm): {msg}"

    if row.step_pupil != 0:
        valid, msg = OpticalLimits.validate_step(row.step_pupil, in_microns=False)
        if not valid:
            return False, f"Step pupil: {msg}"

    logger.debug(f"Row parameters validated successfully")
    return True, ""


def validate_numeric_input(text: str, param_name: str = "Value") -> Tuple[bool, float, str]:
    """
    validate numeric input from table/spinbox
    returns: (is_valid, value, error_message)
    """
    try:
        value = float(text)
        return True, value, ""
    except ValueError:
        error_msg = f"Cannot convert '{text}' to a number.\n\nPlease enter a valid numeric value for {param_name} (e.g., 0.555, 1.2, 100)."
        return False, 0.0, error_msg
