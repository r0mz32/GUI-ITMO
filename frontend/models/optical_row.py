# optical system row data model

import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class OpticalSystemRow:
    """data class for one row in the optical system table"""

    # input params
    wavelength: float = 0.555  # microns
    back_aperture: float = 1.2  # NA
    magnification: float = 100.0
    defocus: float = 0.0  # wavelengths
    astigmatism: float = 0.0  # wavelengths
    sample_size: int = 512  # pixels

    # computed params
    step_obj_can: float = 0.0  # canonical units
    step_obj_microns: float = 0.0  # microns
    step_im_can: float = 0.0  # canonical units
    step_im_microns: float = 0.0  # microns
    diam_pupil: float = 7.5  # canonical units
    step_pupil: float = 0.0  # canonical units

    # results
    psf_data: Optional[np.ndarray] = None
    strehl_ratio: float = 0.0
    status: str = "not_computed"  # not_computed, computing, complete, error
    error_message: str = ""
    compute_time: float = 0.0

    def get_params(self) -> dict:
        """returns params for PSFCalculator"""
        return {
            'size': self.sample_size,
            'wavelength': self.wavelength,
            'back_aperture': self.back_aperture,
            'magnification': self.magnification,
            'defocus': self.defocus,
            'astigmatism': self.astigmatism,
            'diam_pupil': self.diam_pupil
        }

    def to_dict(self) -> dict:
        """save to json (without psf_data)"""
        return {
            'wavelength': self.wavelength,
            'back_aperture': self.back_aperture,
            'magnification': self.magnification,
            'defocus': self.defocus,
            'astigmatism': self.astigmatism,
            'sample_size': self.sample_size
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'OpticalSystemRow':
        """load from json"""
        # use OpticalLimits defaults if available
        try:
            from main import OpticalLimits
            defaults = {
                'wavelength': OpticalLimits.WAVELENGTH_DEFAULT,
                'back_aperture': OpticalLimits.NA_DEFAULT,
                'magnification': OpticalLimits.MAG_DEFAULT,
                'defocus': OpticalLimits.DEFOCUS_DEFAULT,
                'astigmatism': OpticalLimits.ASTIG_DEFAULT,
                'sample_size': OpticalLimits.SAMPLE_SIZE_DEFAULT
            }
        except ImportError:
            defaults = {
                'wavelength': 0.555,
                'back_aperture': 1.2,
                'magnification': 100.0,
                'defocus': 0.0,
                'astigmatism': 0.0,
                'sample_size': 512
            }

        return cls(
            wavelength=data.get('wavelength', defaults['wavelength']),
            back_aperture=data.get('back_aperture', defaults['back_aperture']),
            magnification=data.get('magnification', defaults['magnification']),
            defocus=data.get('defocus', defaults['defocus']),
            astigmatism=data.get('astigmatism', defaults['astigmatism']),
            sample_size=data.get('sample_size', defaults['sample_size'])
        )
