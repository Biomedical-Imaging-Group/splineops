import numpy as np
import numpy.typing as npt

from bssp.bases.splinebasis import SplineBasis


class BSpline4Basis(SplineBasis):

    def __init__(self):

        # Support and poles
        support = 5
        poles = (
            np.sqrt(664 - np.sqrt(438976)) + np.sqrt(304) - 19,
            np.sqrt(664 + np.sqrt(438976)) - np.sqrt(304) - 19
        )

        # Call super constructor
        super(BSpline4Basis, self).__init__(support=support, poles=poles)

    # Methods
    @staticmethod
    def eval(x: npt.ArrayLike) -> npt.NDArray:

        # Pre-computations
        x = np.asarray(x)
        x_abs = np.abs(x)

        # Case 5/2 <= |x|
        # TODO(dperdios): specified dtype? output allocated in base class?
        #  Using the dtype of x may not be the smartest idea
        y = np.zeros_like(x)

        # Case |x| < 5/2 (i.e. 3/2 <= |x| < 5/2)
        y = np.where(
            np.logical_and(x_abs >= 3 / 2, x_abs < 5 / 2),
            1 / 384 * (625 + x_abs * (
                    -1000 + x_abs * (600 + x_abs * (-160 + 16 * x_abs)))),
            y
        )

        # Case |x| < 3/2 (i.e. 1/2 <= |x| < 3/2)
        y = np.where(
            np.logical_and(x_abs >= 1 / 2, x_abs < 3 / 2),
            1 / 96 * (55 + x_abs * (
                    20 + x_abs * (-120 + x_abs * (80 - 16 * x_abs)))),
            y
        )

        # Case |x| < 1/2 (i.e. 0 <= |x| < 1/2)
        y = np.where(
            x_abs < 1 / 2,
            1 / 192 * (115 + x_abs * x_abs * (-120 + 48 * x_abs * x_abs)),
            y
        )

        return y