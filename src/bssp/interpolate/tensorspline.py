import numpy as np
import numpy.typing as npt
from typing import Sequence, Union, Tuple, cast

from bssp.bases.splinebasis import SplineBasis
from bssp.bases.utils import asbasis
from bssp.modes.extensionmode import ExtensionMode
from bssp.modes.utils import asmode
from bssp.utils.interop import is_ndarray

TSplineBasis = Union[SplineBasis, str]
TSplineBases = Union[TSplineBasis, Sequence[TSplineBasis]]
TExtensionMode = Union[ExtensionMode, str]
TExtensionModes = Union[TExtensionMode, Sequence[TExtensionMode]]


class TensorSpline:
    """
    Represents a tensor spline model for multidimensional data interpolation
    using spline bases and extension modes.

    Attributes:
        coefficients (npt.NDArray): The coefficients of the tensor spline model.
        bases (Tuple[SplineBasis, ...]): The spline bases used for each dimension.
        modes (Tuple[ExtensionMode, ...]): The extension modes used for each dimension.
        ndim (int): The number of dimensions of the input data.

    Args:
        data (npt.NDArray): The data array to fit the tensor spline model.
        coordinates (Union[npt.NDArray, Sequence[npt.NDArray]]): The coordinates
            corresponding to each dimension of the data.
        bases (TSplineBases): Spline bases for each dimension.
        modes (TExtensionModes): Extension modes for each dimension.
    """

    def __init__(
        self,
        data: npt.NDArray,
        # TODO(dperdios): naming convention, used `samples` instead of `data`?
        coordinates: Union[npt.NDArray, Sequence[npt.NDArray]],
        bases: TSplineBases,
        modes: TExtensionModes,
        # TODO(dperdios): extrapolate? only at evaluation time?
        # TODO(dperdios): axis? axes? probably complex
        # TODO(dperdios): optional reduction strategy (e.g., first or last)
    ) -> None:
        """
        Initializes the TensorSpline object by setting up the data structure,
        validating input types, and computing initial coefficients for the tensor spline model.
        """

        # Data
        if not is_ndarray(data):
            raise TypeError("Must be an array.")
        ndim = data.ndim
        self._ndim = ndim

        # TODO(dperdios): make `coordinates` optional?
        # TODO(dperdios): `coordinates` need to define a uniform grid.
        #  Note: this is not straightforward to control (numerical errors)
        # Coordinates
        #   1-D special case (either `array` or `(array,)`)
        if is_ndarray(coordinates) and ndim == 1 and len(coordinates) == len(data):
            # Note: we explicitly cast the type to NDArray
            coordinates = cast(npt.NDArray, coordinates)
            # Convert `array` to `(array,)`
            coordinates = (coordinates,)
        if not all(bool(np.all(np.diff(c) > 0)) for c in coordinates):
            raise ValueError("Coordinates must be strictly ascending.")
        valid_data_shape = tuple([c.size for c in coordinates])
        if data.shape != valid_data_shape:
            raise ValueError(
                f"Incompatible data shape. " f"Expected shape: {valid_data_shape}"
            )
        if not all(np.isrealobj(c) for c in coordinates):
            raise ValueError("Must be sequence of real numbers.")
        # TODO(dperdios): useful to keep initial coordinates as property?

        # Pre-computation based on coordinates
        # TODO(dperdios): convert to Python float?
        bounds = tuple([(c[0], c[-1]) for c in coordinates])
        # TODO(dperdios): `bounds` as a public property?
        self._bounds = bounds
        lengths = valid_data_shape
        self._lengths = lengths
        step_seq = []
        for b, l in zip(bounds, lengths):
            if l > 1:
                step = (b[-1] - b[0]) / (l - 1)
            else:
                # Special case for single-sample signal
                step = 1
            step_seq.append(step)
        steps = tuple(step_seq)  # TODO: convert dtype? (can be promoted)
        self._steps = steps
        # TODO(dperdios): cast scalars to real_dtype?

        # DTypes
        dtype = data.dtype
        if not (
            np.issubdtype(dtype, np.floating)
            or np.issubdtype(dtype, np.complexfloating)
        ):
            raise ValueError("Data must be an array of floating point numbers.")
        real_dtype = data.real.dtype
        coords_dtype_seq = tuple(c.dtype for c in coordinates)
        if len(set(coords_dtype_seq)) != 1:
            raise ValueError(
                "Incompatible dtypes in sequence of coordinates. "
                "Expected a consistent dtype. "
                f"Received different dtypes: {tuple(d.name for d in coords_dtype_seq)}"
            )
        coords_dtype = coords_dtype_seq[0]
        if coords_dtype.itemsize != real_dtype.itemsize:
            # TODO(dperdios): maybe automatic cast in the future?
            raise ValueError("Coordinates and data have different floating precisions.")
        self._dtype = dtype
        self._real_dtype = real_dtype

        # Bases
        if isinstance(bases, (SplineBasis, str)):
            # Explicit type cast (special case)
            bases = cast(str, bases)
            bases = ndim * (bases,)
        bases = tuple(asbasis(b) for b in bases)
        if len(bases) != ndim:
            raise ValueError(f"Length of the sequence must be {ndim}.")
        self._bases = bases

        # Modes
        if isinstance(modes, (ExtensionMode, str)):
            # Explicit type cast (special case)
            modes = cast(str, modes)
            modes = ndim * (modes,)
        modes = tuple(asmode(m) for m in modes)
        if len(modes) != ndim:
            raise ValueError(f"Length of the sequence must be {ndim}.")
        self._modes = modes

        # Compute coefficients
        coefficients = self._compute_coefficients(data=data)
        self._coefficients = coefficients

    # Properties
    @property
    def coefficients(self) -> npt.NDArray:
        """
        Provides a copy of the coefficients of the tensor spline model.

        Returns:
            npt.NDArray: A copy of the model's coefficients.
        """
        return np.copy(self._coefficients)

    @property
    def bases(self) -> Tuple[SplineBasis, ...]:
        """
        Provides the spline bases used in the model.

        Returns:
            Tuple[SplineBasis, ...]: The spline bases for each dimension.
        """
        return self._bases

    @property
    def modes(self) -> Tuple[ExtensionMode, ...]:
        """
        Provides the extension modes used in the model.

        Returns:
            Tuple[ExtensionMode, ...]: The extension modes for each dimension.
        """
        return self._modes

    @property
    def ndim(self):
        """
        Provides the number of dimensions of the input data.

        Returns:
            int: The number of dimensions.
        """
        return self._ndim

    # Methods
    def __call__(
        self,
        coordinates: Union[npt.NDArray, Sequence[npt.NDArray]],
        grid: bool = True,
        # TODO(dperdios): extrapolate?
    ) -> npt.NDArray:
        """
        Evaluates the tensor spline model at given coordinates.

        Args:
            coordinates (Union[npt.NDArray, Sequence[npt.NDArray]]): Coordinates at which to evaluate the model.
            grid (bool): Specifies whether the coordinates represent a regular grid.

        Returns:
            npt.NDArray: The evaluated data at the given coordinates.
        """
        return self.eval(coordinates=coordinates, grid=grid)

    def eval(
        self, coordinates: Union[npt.NDArray, Sequence[npt.NDArray]], grid: bool = True
    ) -> npt.NDArray:
        """
        Evaluates the tensor spline model at given coordinates, explicitly allowing
        control over whether the coordinates are interpreted as a grid.

        Args:
            coordinates (Union[npt.NDArray, Sequence[npt.NDArray]]): Coordinates at which to evaluate the model.
            grid (bool): Specifies whether the coordinates represent a regular grid.

        Returns:
            npt.NDArray: The evaluated data at the given coordinates.
        """

        # Check coordinates
        ndim = self._ndim
        if grid:
            # Special 1-D case: "default" grid=True with a 1-D `coords` NDArray
            if is_ndarray(coordinates):
                # Note: we explicitly cast the type to NDArray
                coordinates = cast(npt.NDArray, coordinates)
                if ndim == 1 and coordinates.ndim == 1:
                    coordinates = (coordinates,)
            # N-D cases
            if len(coordinates) != ndim:
                # TODO(dperdios): Sequence of (..., n) arrays (batch dimensions
                #   must be the same!)
                raise ValueError(f"Must be a {ndim}-length sequence of 1-D arrays.")
            if not all([bool(np.all(np.diff(c, axis=-1) > 0)) for c in coordinates]):
                # TODO(dperdios): do they really need to be ascending?
                raise ValueError("Coordinates must be strictly ascending.")
        else:
            # If not `grid`, a sequence of arrays is expected with a length
            #  equal to the number of dimensions. Each array in the sequence
            #  must be of the same shape.
            coords_shapes = [c.shape for c in coordinates]
            if len(coordinates) != ndim or len(set(coords_shapes)) != 1:
                raise ValueError(
                    f"Incompatible sequence of coordinates. "
                    f"Must be a {ndim}-length sequence of same-shape N-D arrays. "
                    f"Current sequence of array shapes: {coords_shapes}."
                )
        if not all(np.isrealobj(c) for c in coordinates):
            raise ValueError("Must be a sequence of real numbers.")

        # Get properties
        real_dtype = self._real_dtype
        bounds_seq = self._bounds
        length_seq = self._lengths
        step_seq = self._steps
        basis_seq = self._bases
        mode_seq = self._modes
        coefficients = self._coefficients
        ndim = self._ndim

        # Rename
        coords_seq = coordinates

        # For-loop over dimensions
        indexes_seq = []
        weights_seq = []
        for coords, basis, mode, data_lim, dx, data_len in zip(
            coords_seq, basis_seq, mode_seq, bounds_seq, step_seq, length_seq
        ):

            # Data limits
            x_min, x_max = data_lim

            # Indexes
            #   Compute rational indexes
            # TODO(dperdios): no difference in using `* fs` or `/ dx`
            # fs = 1 / dx
            # rat_indexes = (coords - x_min) * fs
            rat_indexes = (coords - x_min) / dx
            #   Compute corresponding integer indexes (including support)
            indexes = basis.compute_support_indexes(x=rat_indexes)
            # TODO(dperdios): specify dtype in compute_support_indexes? cast dtype here?
            #  int32 faster than int64? probably not

            # Evaluate basis function (interpolation weights)
            # indexes_shift = np.subtract(indexes, rat_indexes, dtype=real_dtype)
            # shifted_idx = np.subtract(indexes, rat_indexes, dtype=real_dtype)
            shifted_idx = np.subtract(
                rat_indexes[np.newaxis], indexes, dtype=real_dtype
            )
            # TODO(dperdios): casting rules, do we really want it?
            weights = basis(x=shifted_idx)

            # Signal extension
            indexes_ext, weights_ext = mode.extend_signal(
                indexes=indexes, weights=weights, length=data_len
            )

            # TODO(dperdios): Add extrapolate handling?
            # weights[idx_extra] = cval ?? or within extend_signal?

            # Store
            indexes_seq.append(indexes_ext)
            weights_seq.append(weights_ext)

        # Broadcast arrays for tensor product
        if grid:
            # del_axis_base = np.arange(ndim + 1, step=ndim)
            # del_axes = [del_axis_base + ii for ii in range(ndim)]
            # exp_axis_base = np.arange(2 * ndim)
            # exp_axes = [tuple(np.delete(exp_axis_base, a)) for a in del_axes]
            # Batch-compatible axis expansions
            exp_axis_ind_base = np.arange(ndim)  # from start
            exp_axis_coeffs_base = exp_axis_ind_base - ndim  # from end TODO: reverse?
            exp_axes = []
            for ii in range(ndim):
                a = np.concatenate(
                    [
                        np.delete(exp_axis_ind_base, ii),
                        np.delete(exp_axis_coeffs_base, ii),
                    ]
                )
                exp_axes.append(tuple(a))
        else:
            exp_axis_base = np.arange(ndim)
            exp_axes = [tuple(np.delete(exp_axis_base, a)) for a in range(ndim)]

        indexes_bc = []
        weights_bc = []
        for indexes, weights, a in zip(indexes_seq, weights_seq, exp_axes):
            indexes_bc.append(np.expand_dims(indexes, axis=a))
            weights_bc.append(np.expand_dims(weights, axis=a))
        # Note: for interop (CuPy), cannot use prod with a sequence of arrays.
        #  Need explicit stacking before reduction. It is NumPy compatible.
        weights_tp = np.prod(np.stack(np.broadcast_arrays(*weights_bc), axis=0), axis=0)

        # Interpolation (convolution via reduction)
        # TODO(dperdios): might want to change the default reduction axis
        axes_sum = tuple(range(ndim))  # first axes are the indexes
        data = np.sum(coefficients[tuple(indexes_bc)] * weights_tp, axis=axes_sum)

        return data

    def _compute_coefficients(self, data: npt.NDArray) -> npt.NDArray:
        """
        Computes the coefficients for the tensor spline based on the input data.

        Args:
            data (npt.NDArray): The input data from which to compute the coefficients.

        Returns:
            npt.NDArray: The computed coefficients for the tensor spline model.
        """

        # Prepare data and axes
        # TODO(dperdios): there is probably too many copies along this process
        coefficients = np.copy(data)
        axes = tuple(range(coefficients.ndim))
        axes_roll = tuple(np.roll(axes, shift=-1))

        # TODO(dperdios): could do one less roll by starting with the initial
        #  shape
        for basis, mode in zip(self._bases, self._modes):

            # Roll data w.r.t. dimension
            coefficients = np.transpose(coefficients, axes=axes_roll)

            # Compute coefficients w.r.t. extension `mode` and `basis`
            coefficients = mode.compute_coefficients(data=coefficients, basis=basis)

        return coefficients
