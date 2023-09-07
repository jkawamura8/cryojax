"""
Abstraction of electron detectors in a cryo-EM image.
"""

__all__ = [
    "Detector",
    "NullDetector",
    "CountingDetector",
    "WhiteDetector",
]

import jax
import jax.numpy as jnp

from abc import ABCMeta, abstractmethod
from typing import Any
from functools import partial

from .noise import GaussianNoise, Noise
from ..utils import scale
from ..core import dataclass, field, Array, ArrayLike, Parameter, CryojaxObject
from .kernel import Constant


@partial(dataclass, kw_only=True)
class Detector(CryojaxObject, metaclass=ABCMeta):
    """
    Base class for an electron detector.
    """

    @abstractmethod
    def measure(self, image: ArrayLike, resolution: float) -> Array:
        """Measure the `perfect` detector readout."""
        raise NotImplementedError

    @abstractmethod
    def sample(self, *args: Any, **kwargs: Any) -> Array:
        """Sample a realization from the detector model."""
        raise NotImplementedError


@partial(dataclass, kw_only=True)
class NullDetector(Noise, Detector):
    """
    A 'null' detector.
    """

    def measure(self, image: ArrayLike, resolution: float) -> Array:
        return image

    def sample(self, freqs: ArrayLike) -> Array:
        shape = freqs.shape[0:-1]
        return jnp.zeros(shape)


@partial(dataclass, kw_only=True)
class CountingDetector(Detector):
    """
    A noiseless detector that counts electrons
    at a given pixel size.

    Attributes
    ----------
    pixel_size : `cryojax.core.Parameter`
        The pixel size measured by the detector.
        This is in dimensions of physical length.
    method : `bool`, optional
        The interpolation method used for measuring
        the image at the ``pixel_size``.
    """

    pixel_size: Parameter
    method: str = field(pytree_node=False, default="lanczos5")

    def measure(self, image: ArrayLike, resolution: float) -> Array:
        """
        Measure an image at the detector pixel size using interpolation.

        The image must be given in real space.
        """
        measured = measure_image(
            image,
            resolution,
            self.pixel_size,
            method=self.method,
            antialias=False,
        )
        return measured

    def sample(self, freqs: ArrayLike) -> Array:
        shape = freqs.shape[0:-1]
        return jnp.zeros(shape)


@partial(dataclass, kw_only=True)
class WhiteDetector(GaussianNoise, CountingDetector):
    """
    A detector with a gaussian white noise model.

    Attributes
    ----------
    lambda_d : `cryojax.core.Parameter`
        Variance of the detector noise.
    """

    kernel: Constant = field(pytree_node=False, init=False, encode=False)

    lambda_d: Parameter = 1.0

    def __post_init__(self):
        object.__setattr__(self, "kernel", Constant(self.lambda_d))

    def variance(self, freqs: ArrayLike) -> Array:
        """Flat power spectrum."""
        return self.kernel(freqs)


@partial(jax.jit, static_argnames=["method", "antialias"])
def measure_image(
    image: ArrayLike, resolution: float, pixel_size: float, **kwargs
):
    """
    Measure an image at a given pixel size using interpolation.

    For more detail, see ``cryojax.utils.interpolation.scale``.

    Parameters
    ----------
    image : `Array`, shape `(N1, N2)`
        The image to be magnified.
    resolution : `float`
        The resolution, in physical length, of
        the image.
    pixel_size : `float`
        The pixel size of the detector.
    """
    scale_factor = resolution / pixel_size
    s = jnp.array([scale_factor, scale_factor])
    return scale(image, image.shape, s, **kwargs)
