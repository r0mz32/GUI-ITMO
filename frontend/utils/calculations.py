# optical parameter calculations

import logging

logger = logging.getLogger(__name__)


def calculate_step_params(row, source_param: str, source_units: str) -> dict:
    """
    calculate all step parameters based on source parameter

    args:
        row: OpticalSystemRow instance
        source_param: which parameter is the source ('Diam pupil', 'Step pupil', 'Step object', 'Step image')
        source_units: units for step parameters ('c.u.' or 'μm')

    returns:
        dict with keys: diam_pupil, step_pupil, step_obj_can, step_obj_microns, step_im_can, step_im_microns
    """
    sample_size = row.sample_size

    # prevent division by zero
    wavelength = max(row.wavelength, 0.001)
    back_aperture = max(row.back_aperture, 0.001)
    magnification = max(row.magnification, 0.001)
    aperture = magnification * back_aperture

    result = {}

    if source_param == 'Diam pupil':
        diam_pupil = max(row.diam_pupil, 0.001)
        step_pupil = diam_pupil / max(sample_size, 1)
        step_im_can = 1 / max(step_pupil * sample_size, 0.001)
        step_obj_can = step_im_can

        result['diam_pupil'] = diam_pupil
        result['step_pupil'] = step_pupil
        result['step_obj_can'] = step_obj_can
        result['step_im_can'] = step_im_can

    elif source_param == 'Step pupil':
        step_pupil = max(row.step_pupil, 0.001)
        diam_pupil = step_pupil * sample_size
        step_im_can = 1 / max(step_pupil * sample_size, 0.001)
        step_obj_can = step_im_can

        result['diam_pupil'] = diam_pupil
        result['step_pupil'] = step_pupil
        result['step_obj_can'] = step_obj_can
        result['step_im_can'] = step_im_can

    elif source_param == 'Step object':
        if source_units == 'c.u.':
            step_obj_can = max(row.step_obj_can, 0.001)
        else:  # μm
            step_obj_microns = max(row.step_obj_microns, 0.001)
            step_obj_can = step_obj_microns * aperture / wavelength

        step_pupil = 1 / max(step_obj_can * sample_size, 0.001)
        diam_pupil = step_pupil * sample_size
        step_im_can = step_obj_can

        result['diam_pupil'] = diam_pupil
        result['step_pupil'] = step_pupil
        result['step_obj_can'] = step_obj_can
        result['step_im_can'] = step_im_can

    elif source_param == 'Step image':
        if source_units == 'c.u.':
            step_im_can = max(row.step_im_can, 0.001)
        else:  # μm
            step_im_microns = max(row.step_im_microns, 0.001)
            step_im_can = step_im_microns * back_aperture / wavelength

        step_obj_can = step_im_can
        step_pupil = 1 / max(step_im_can * sample_size, 0.001)
        diam_pupil = step_pupil * sample_size

        result['diam_pupil'] = diam_pupil
        result['step_pupil'] = step_pupil
        result['step_obj_can'] = step_obj_can
        result['step_im_can'] = step_im_can

    else:
        logger.warning(f"Unknown source parameter: {source_param}")
        return {}

    # calculate microns from canonical units
    result['step_obj_microns'] = result['step_obj_can'] * wavelength / aperture
    result['step_im_microns'] = result['step_im_can'] * wavelength / back_aperture

    logger.debug(f"Calculated step params for {source_param}: {result}")
    return result


def calculate_strehl_ratio(psf_data) -> float:
    """
    calculate Strehl ratio from PSF data

    Strehl = center_intensity / (total_energy / N_pixels)
    """
    if psf_data is None or psf_data.size == 0:
        return 0.0

    import numpy as np

    size = psf_data.shape[0]
    center_idx = size // 2
    center_intensity = float(psf_data[center_idx, center_idx])

    total_energy = float(np.sum(psf_data))
    avg_intensity = total_energy / psf_data.size

    if avg_intensity > 0:
        strehl = center_intensity / avg_intensity
    else:
        strehl = 0.0

    return strehl
