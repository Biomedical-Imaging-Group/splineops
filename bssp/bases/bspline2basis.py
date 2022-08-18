import numpy as np
import numpy.typing as npt

from bssp.bases.splinebasis import SplineBasis


class BSpline2Basis(SplineBasis):

    def __init__(self):

        # Support and poles
        support = 3
        poles = (2 * np.sqrt(2) - 3,)

        # Call super constructor
        super(BSpline2Basis, self).__init__(support=support, poles=poles)

    # Methods
    @staticmethod
    def eval(x: npt.ArrayLike) -> npt.NDArray:

        # Pre-computations
        x = np.asarray(x)
        x_abs = np.abs(x)

        # Case 3/2 <= |x|
        # TODO(dperdios): specified dtype? output allocated in base class?
        #  Using the dtype of x may not be the smartest idea
        y = np.zeros_like(x)

        # Case |x| < 3/2 (i.e. 1/2 <= |x| < 3/2)
        y = np.where(
            np.logical_and(x_abs >= 1 / 2, x_abs < 3 / 2),
            # 1 / 8 * (3 - 2 * x_abs) * (3 - 2 * x_abs),
            9 / 8 - (3 * x_abs) / 2 + x_abs * x_abs / 2,
            y
        )

        # Case |x| < 1/2 (i.e. 0 <= |x| < 1/2)
        y = np.where(x_abs < 1 / 2, 3 / 4 - x_abs * x_abs, y)

        return y