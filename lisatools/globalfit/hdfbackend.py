import numpy as np
from eryn.backends import HDFBackend as eryn_HDFBackend
from .state import State

class HDFBackend(eryn_HDFBackend):
    
    def reset(self, nwalkers, *args, ntemps=1, num_bands=None, band_edges=None, **kwargs):
        if num_bands is None or band_edges is None:
            raise ValueError("Must provide num_bands and band_edges kwargs.")

        # regular reset
        super().reset(nwalkers, *args, ntemps=ntemps, **kwargs)

        # open file in append mode
        with self.open("a") as f:
            g = f[self.name]

            band_info = g.create_group("band_info")

            band_info.create_dataset(
                "band_edges",
                data=band_edges,
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

            band_info.attrs["num_bands"] = len(band_edges)

            band_info.create_dataset(
                "band_temps",
                (0, num_bands, ntemps),
                maxshape=(None, num_bands, ntemps),
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

            band_info.create_dataset(
                "band_swaps_proposed",
                (0, num_bands, ntemps - 1),
                maxshape=(None, num_bands, ntemps - 1),
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

            band_info.create_dataset(
                "band_swaps_accepted",
                (0, num_bands, ntemps - 1),
                maxshape=(None, num_bands, ntemps - 1),
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

            band_info.create_dataset(
                "band_num_proposed",
                (0, num_bands, ntemps),
                maxshape=(None, num_bands, ntemps),
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

            band_info.create_dataset(
                "band_num_accepted",
                (0, num_bands, ntemps),
                maxshape=(None, num_bands, ntemps),
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

            band_info.create_dataset(
                "band_num_proposed_rj",
                (0, num_bands, ntemps),
                maxshape=(None, num_bands, ntemps),
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

            band_info.create_dataset(
                "band_num_accepted_rj",
                (0, num_bands, ntemps),
                maxshape=(None, num_bands, ntemps),
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

            band_info.create_dataset(
                "band_num_binaries",
                (0, ntemps, nwalkers, num_bands),
                maxshape=(None, ntemps, nwalkers, num_bands),
                dtype=self.dtype,
                compression=self.compression,
                compression_opts=self.compression_opts,
            )

    @property
    def num_bands(self):
        """Get num_bands from h5 file."""
        with self.open() as f:
            return f[self.name]["band_info"].attrs["num_bands"]

    @property
    def band_edges(self):
        """Get num_bands from h5 file."""
        with self.open() as f:
            return f[self.name].attrs["num_bands"]

    @property
    def reset_kwargs(self):
        """Get reset_kwargs from h5 file."""
        return dict(
            nleaves_max=self.nleaves_max,
            ntemps=self.ntemps,
            branch_names=self.branch_names,
            rj=self.rj,
            moves=self.moves,
            num_bands=self.num_bands
        )

    def grow(self, ngrow, *args):

        super().grow(ngrow, *args)
        
        # open the file in append mode
        with self.open("a") as f:
            g = f[self.name]

            # resize all the arrays accordingly
            ntot = g.attrs["iteration"] + ngrow
            for key in g["band_info"]:
                g["band_info"][key].resize(ntot, axis=0)

    def get_value(self, name, thin=1, discard=0, slice_vals=None):
        """Returns a requested value to user.

        This function helps to streamline the backend for both
        basic and hdf backend.

        Args:
            name (str): Name of value requested.
            thin (int, optional): Take only every ``thin`` steps from the
                chain. (default: ``1``)
            discard (int, optional): Discard the first ``discard`` steps in
                the chain as burn-in. (default: ``0``)
            slice_vals (indexing np.ndarray or slice, optional): If provided, slice the array directly
                from the HDF5 file with slice = ``slice_vals``. ``thin`` and ``discard`` will be 
                ignored if slice_vals is not ``None``. This is particularly useful if files are 
                very large and the user only wants a small subset of the overall array.
                (default: ``None``)

        Returns:
            dict or np.ndarray: Values requested.

        """
        # check if initialized
        if not self.initialized:
            raise AttributeError(
                "You must run the sampler with "
                "'store == True' before accessing the "
                "results"
            )

        if name != "band_info":
            return super().get_value(name, thin=thin, discard=discard, slice_vals=slice_vals) 

        if slice_vals is None:
            slice_vals = slice(discard + thin - 1, self.iteration, thin)

        # open the file wrapped in a "with" statement
        with self.open() as f:
            # get the group that everything is stored in
            g = f[self.name]
            iteration = g.attrs["iteration"]
            if iteration <= 0:
                raise AttributeError(
                    "You must run the sampler with "
                    "'store == True' before accessing the "
                    "results"
                )

            v_all = {key: g["band_info"][key][slice_vals] for key in g["band_info"]}
        return v_all

    def get_band_info(self, **kwargs):
        """Get the stored chain of MCMC samples

        Args:
            thin (int, optional): Take only every ``thin`` steps from the
                chain. (default: ``1``)
            discard (int, optional): Discard the first ``discard`` steps in
                the chain as burn-in. (default: ``0``)
            slice_vals (indexing np.ndarray or slice, optional): This is only available in :class:`eryn.backends.hdfbackend`.
                If provided, slice the array directly from the HDF5 file with slice = ``slice_vals``. 
                ``thin`` and ``discard`` will be ignored if slice_vals is not ``None``. 
                This is particularly useful if files are very large and the user only wants a 
                small subset of the overall array. (default: ``None``)

        Returns:
            dict: MCMC samples
                The dictionary contains np.ndarrays of samples
                across the branches.

        """
        return self.get_value("band_info", **kwargs)

    def save_step(
        self,
        state,
        *args, 
        **kwargs
    ):
        """Save a step to the backend

        Args:
            state (State): The :class:`State` of the ensemble.
            accepted (ndarray): An array of boolean flags indicating whether
                or not the proposal for each walker was accepted.
            rj_accepted (ndarray, optional): An array of the number of accepted steps
                for the reversible jump proposal for each walker.
                If :code:`self.rj` is True, then rj_accepted must be an array with
                :code:`rj_accepted.shape == accepted.shape`. If :code:`self.rj`
                is False, then rj_accepted must be None, which is the default.
            swaps_accepted (ndarray, optional): 1D array with number of swaps accepted
                for the in-model step. (default: ``None``)
            moves_accepted_fraction (dict, optional): Dict of acceptance fraction arrays for all of the 
                moves in the sampler. This dict must have the same keys as ``self.move_keys``.
                (default: ``None``)

        """

        super().save_step(state, *args, **kwargs)
        
        # open for appending in with statement
        with self.open("a") as f:
            g = f[self.name]
            # get the iteration left off on
            # minus one because it was updated in the super function
            iteration = g.attrs["iteration"] - 1

            # make sure the backend has all the information needed to store everything
            for key in [
                "num_bands",
            ]:
                if not hasattr(self, key):
                    setattr(self, key, g.attrs[key])

            # branch-specific
            for name, dat in state.band_info.items():
                if not isinstance(dat, np.ndarray) or name == "band_edges":
                    continue
                g["band_info"][name][iteration] = dat

        # reset the counter for band info
        state.reset_band_counters()

    def get_a_sample(self, it):
        """Access a sample in the chain

        Args:
            it (int): iteration of State to return.

        Returns:
            State: :class:`eryn.state.State` object containing the sample from the chain.

        Raises:
            AttributeError: Backend is not initialized.

        """
        sample = State(super().get_a_sample(it))

        thin = self.iteration - it if it != self.iteration else 1

        sample.band_info = self.get_band_info(discard=it - 1, thin=thin)
        sample.band_info["initialized"] = True

        return sample

    