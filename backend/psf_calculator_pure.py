# расчет PSF на numpy

import numpy as np
from typing import Optional
from dataclasses import dataclass


@dataclass
class PSFParams:
    size: int = 512
    wavelength: float = 0.555
    back_aperture: float = 0.5
    magnification: float = 1.0
    defocus: float = 0.0
    astigmatism: float = 0.0
    diam_pupil: float = 8.0


class PSFCalculator:

    def __init__(self):
        self.last_pupil: Optional[np.ndarray] = None
        self.last_params: Optional[PSFParams] = None
        self._step_im_microns: float = 0.0

    def compute(
        self,
        size: int = 512,
        wavelength: float = 0.555,
        back_aperture: float = 0.5,
        magnification: float = 1.0,
        defocus: float = 0.0,
        astigmatism: float = 0.0,
        diam_pupil: float = 8.0
    ) -> np.ndarray:

        params = PSFParams(
            size=size,
            wavelength=wavelength,
            back_aperture=back_aperture,
            magnification=magnification,
            defocus=defocus,
            astigmatism=astigmatism,
            diam_pupil=diam_pupil
        )

        # считаем параметры
        aperture = magnification * back_aperture
        step_pupil = diam_pupil / size
        step_obj_can = 1.0 / (step_pupil * size)
        step_im_can = step_obj_can

        self.last_params = params
        self._step_im_microns = step_im_can * wavelength / back_aperture

        # зрачковая функция
        pupil = self._calc_pupil_function(
            size, step_pupil, defocus, astigmatism
        )
        self.last_pupil = pupil.copy()

        # FFT и всякое
        pupil = np.fft.ifftshift(pupil)
        field = np.fft.ifft2(pupil)
        field = np.fft.fftshift(field)

        # нормировка
        field *= (step_pupil / step_obj_can)

        # интенсивность
        intensity = np.abs(field) ** 2

        # normalize to total energy = 1 (physically correct)
        total_energy = np.sum(intensity)
        if total_energy > 0:
            psf = intensity / total_energy
        else:
            psf = intensity

        return psf

    def _calc_pupil_function(
        self,
        size: int,
        step_pupil: float,
        defocus: float,
        astigmatism: float
    ) -> np.ndarray:

        # сетка
        idx = np.arange(size)
        coords = (idx - size // 2) * step_pupil
        X, Y = np.meshgrid(coords, coords)

        # полярные координаты
        rho2 = X**2 + Y**2
        phi = np.arctan2(X, Y)

        # маска зрачка
        mask = rho2 <= 1.0

        # аберрация
        W = 2.0 * np.pi * (
            defocus * (2.0 * rho2 - 1.0) +
            astigmatism * rho2 * np.cos(2.0 * phi)
        )

        pupil = np.exp(1j * W) * mask

        return pupil

    def get_pupil(self, size: int) -> np.ndarray:
        if self.last_pupil is None:
            raise RuntimeError("No pupil computed yet")

        intensity = np.abs(self.last_pupil) ** 2

        if intensity.shape[0] != size:
            from scipy.ndimage import zoom
            scale = size / intensity.shape[0]
            intensity = zoom(intensity, scale, order=1)

        return intensity

    def get_step_microns(self) -> float:
        if self.last_params is None:
            raise RuntimeError("No computation performed yet")
        return self._step_im_microns


def compute_psf(
    size: int = 512,
    wavelength: float = 0.555,
    back_aperture: float = 0.5,
    magnification: float = 1.0,
    defocus: float = 0.0,
    astigmatism: float = 0.0,
    diam_pupil: float = 8.0
) -> np.ndarray:
    calc = PSFCalculator()
    return calc.compute(
        size=size,
        wavelength=wavelength,
        back_aperture=back_aperture,
        magnification=magnification,
        defocus=defocus,
        astigmatism=astigmatism,
        diam_pupil=diam_pupil
    )


def get_version() -> str:
    return "2.0.0-pure-python"


def get_last_error() -> str:
    return ""
