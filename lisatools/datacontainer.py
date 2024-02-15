import warnings
from abc import ABC
from typing import Any, Tuple, Optional, List

import math
import numpy as np
from numpy.typing import ArrayLike
from scipy import interpolate

try:
    import cupy as cp

except (ModuleNotFoundError, ImportError):
    import numpy as cp

from . import detector as lisa_models
from .utils.utility import AET, get_array_module
from .utils.constants import *
from .stochastic import (
    StochasticContribution,
    FittedHyperbolicTangentGalacticForeground,
)


class DataResidualArray:
    pass


class DataResidualArray:
    """Container to hold sensitivity information.

    Args:
        f: Frequency array.
        sens_mat: Input sensitivity list. The shape of the nested lists should represent the shape of the
            desired matrix. Each entry in the list must be an array, :class:`Sensitivity`-derived object,
            or a string corresponding to the :class:`Sensitivity` object.
        **sens_kwargs: Keyword arguments to pass to :method:`Sensitivity.get_Sn`.

    """

    def __init__(
        self,
        data_res_in: List[np.ndarray] | np.ndarray | DataResidualArray,
        dt: Optional[float] = None,
        f_arr: Optional[np.ndarray] = None,
        df: Optional[float] = None,
        **kwargs: dict,
    ) -> None:
        if isinstance(data_res_in, DataResidualArray):
            for key, item in data_res_in.__dict__.items():
                setattr(self, key, item)

        else:
            self._check_inputs(dt=dt, f_arr=f_arr, df=df)
            self.data_res_arr = data_res_in
            self._store_time_and_frequency_information(dt=dt, f_arr=f_arr, df=df)

    def _check_inputs(
        self,
        dt: Optional[float] = None,
        f_arr: Optional[np.ndarray] = None,
        df: Optional[float] = None,
    ):
        number_of_none = 0

        number_of_none += 1 if dt is None else 0
        number_of_none += 1 if f_arr is None else 0
        number_of_none += 1 if df is None else 0

        if number_of_none == 3:
            raise ValueError("Must provide either df, dt, or f_arr.")

        elif number_of_none == 1:
            raise ValueError(
                "Can only provide one of dt, f_arr, or df. Not more than one."
            )

    def _store_time_and_frequency_information(
        self,
        dt: Optional[float] = None,
        f_arr: Optional[np.ndarray] = None,
        df: Optional[float] = None,
    ):
        if dt is not None:
            self._dt = dt
            self._Tobs = self.data_length * dt
            self._df = 1 / self._Tobs
            self._fmax = 1 / (2 * dt)
            self._f_arr = np.fft.rfftfreq(self.data_length, dt)

            # transform data
            tmp = get_array_module(self.data_res_arr).fft.rfft(
                self.data_res_arr, axis=-1
            )
            del self._data_res_arr
            self._data_res_arr = tmp
            self.data_length = self._data_res_arr.shape[-1]

        elif df is not None:
            self._df = df
            self._Tobs = 1 / self._df
            self._fmax = (self.data_length - 1) * df
            self._dt = 1 / (2 * self._fmax)
            self._f_arr = np.arange(0.0, self._fmax, self._df)

        elif f_arr is not None:
            self._f_arr = f_arr
            self._fmax = f_arr.max()
            # constant spacing
            if np.all(np.diff(f_arr) == np.diff(f_arr)[0]):
                self._df = np.diff(f_arr)[0].item()

                if f_arr[0] == 0.0:
                    # could be fft because of constant spacing and f_arr[0] == 0.0
                    self._Tobs = 1 / self._df
                    self._dt = 1 / (2 * self._fmax)

                else:
                    # cannot be fft basis
                    self._Tobs = None
                    self._dt = None

            else:
                self._df = None
                self._Tobs = None
                self._dt = None

        if len(self.f_arr) != self.data_length:
            raise ValueError(
                "Entered or determined f_arr does not have the same length as the data channel inputs."
            )

    @property
    def fmax(self):
        return self._fmax

    @property
    def f_arr(self):
        return self._f_arr

    @property
    def dt(self):
        if self._dt is None:
            raise ValueError("dt cannot be determined from this f_arr input.")

        return self._dt

    @property
    def Tobs(self):
        if self._Tobs is None:
            raise ValueError("Tobs cannot be determined from this f_arr input.")

        return self._Tobs

    @property
    def df(self):
        if self._df is None:
            raise ValueError("df cannot be determined from this f_arr input.")

        return self._df

    @property
    def frequency_arr(self) -> np.ndarray:
        return self._f_arr

    @property
    def data_res_arr(self) -> np.ndarray:
        return self._data_res_arr

    @data_res_arr.setter
    def data_res_arr(self, data_res_arr: List[np.ndarray] | np.ndarray) -> None:
        self._data_res_arr_input = data_res_arr

        if (
            isinstance(data_res_arr, np.ndarray) or isinstance(data_res_arr, cp.ndarray)
        ) and data_res_arr.ndim == 1:
            data_res_arr = [data_res_arr]

        elif (
            isinstance(data_res_arr, np.ndarray) or isinstance(data_res_arr, cp.ndarray)
        ) and data_res_arr.ndim == 2:
            data_res_arr = list(data_res_arr)

        new_out = np.full(len(data_res_arr), None, dtype=object)
        self.data_length = None
        for i in range(len(data_res_arr)):
            current_data = data_res_arr[i]
            if isinstance(current_data, np.ndarray) or isinstance(
                current_data, cp.ndarray
            ):
                if self.data_length is None:
                    self.data_length = len(current_data)
                else:
                    assert len(current_data) == self.data_length

                new_out[i] = current_data
            else:
                raise ValueError

        self.nchannels = len(new_out)
        self._data_res_arr = np.asarray(list(new_out), dtype=complex)

    def __getitem__(self, index: tuple) -> np.ndarray:
        return self.data_res_arr[index]

    @property
    def ndim(self) -> int:
        return self.data_res_arr.ndim

    def flatten(self) -> np.ndarray:
        return self.data_res_arr.flatten()

    @property
    def shape(self) -> tuple:
        return self.data_res_arr.shape