from __future__ import division
import numpy as np
from pyscf.nao import scf
from pyscf.nao.m_tools import find_nearrest_index
import h5py
from pyscf.nao.m_libnao import libnao
from ctypes import POINTER, c_int, c_int32, c_int64, c_float, c_double

#try:
#    import numba as nb
#    from pyscf.nao.m_comp_spatial_numba import get_spatial_density_numba, get_spatial_density_numba_parallel
#    use_numba = True
#except:
#    use_numba = False


class spatial_distribution(scf):
    """
        class to calculate spatial distribution of
            * density change
            * induce potential
            * induce electric field
            * intensity of the induce Efield

        Example:
        from __future__ import print_function, division
        import numpy as np
        from pyscf.nao import tddft_iter
        from pyscf.nao.m_comp_spatial_distributions import spatial_distribution

        from ase.units import Ry, eV, Ha, Bohr


        # run tddft calculation
        td = tddft_iter(label="siesta", iter_broadening=0.15/Ha, xc_code='LDA,PZ')

        omegas = np.linspace(0.0, 10.0, 200)/Ha + 1j*td.eps
        td.comp_dens_inter_along_Eext(omegas, Eext=np.array([1.0, 0.0, 0.0]))

        box = np.array([[-10.0, 10.0],
                        [-10.0, 10.0],
                        [-10.0, 10.0]])/Bohr
        dr = np.array([0.5, 0.5, 0.5])/Bohr

        # initialize spatial calculations
        spd = spatial_distribution(td.dn, omegas, box, dr = dr, label="siesta")

        # compute spatial density change distribution
        spd.get_spatial_density(3.5/Ha, Eext=np.array([1.0, 0.0, 0.0]))

        # computer Efield
        Efield = spd.comp_induce_field()
        
        # compute potential
        pot = spd.comp_induce_potential()
        
        # coompute intensity
        intensity = spd.comp_intensity_Efield(Efield)
    """

    def __init__(self, dn, freq, box, **kw):
        """
            initialize the class aith scf.__init__, checking arguments
            All quantites must be given in a.u.

            Warning: the same kw parameters used for the densit calculations must be used

            dn (complex array calculated from tddft_iter, dim: [3, nfreq, nprod]): the induce density
                    in the product basis calulated from comp_dens_inter_along_Eext in tddft_iter.
            freq (real array, dim: [nfreq]): the frequency range for which dn was computed
            w0 (real): frequency at which you want to computer the spatial quantities
            box (real array, dim: [3, 2]): spatial boundaries of the box in which you want
                        to compute the spatial quantities, first index run over x, y, z axis,
                        second index stand for lower and upper boundaries.
        """

        self.dr = kw['dr'] if 'dr' in kw else np.array([0.3, 0.3, 0.3])

        assert self.dr.size == 3
        assert box.shape == (3, 2)

        self.box = box
        self.mesh = np.array([np.arange(box[0, 0], box[0, 1]+self.dr[0], self.dr[0]),
                              np.arange(box[1, 0], box[1, 1]+self.dr[1], self.dr[1]),
                              np.arange(box[2, 0], box[2, 1]+self.dr[2], self.dr[2])])
        self.freq = freq
        self.dn = dn

        scf.__init__(self, **kw)

        self.nprod = dn.shape[2]

    def get_spatial_density(self, w0, ao_log=None, Eext = np.array([1.0, 1.0, 1.0])):
        """
            Compute the density change fromm the product basis
            to cartesian bais for the frequency w0 and the external
            field directed along Eext
        """

        assert Eext.size == 3
        self.Eext = Eext/np.sqrt(np.dot(Eext, Eext))

        from pyscf.nao.m_ao_matelem import ao_matelem_c
        from pyscf.nao.m_csphar import csphar
        from pyscf.nao.m_rsphar_libnao import rsphar
        from pyscf.nao.m_log_interp import comp_coeffs_


        iw = find_nearrest_index(self.freq, w0)
        self.mu2dn_re = np.dot(self.Eext, self.dn[:, iw, :].real)
        self.mu2dn_im = np.dot(self.Eext, self.dn[:, iw, :].imag)

        Nx, Ny, Nz = self.mesh[0].size, self.mesh[1].size, self.mesh[2].size 

        dn_spatial_re = np.zeros((Nx, Ny, Nz), dtype=np.float32)
        dn_spatial_im = np.zeros((Nx, Ny, Nz), dtype=np.float32)

        # Aligning the data is important to avoid troubles in the fortran side!
        atoms2sp = np.require(self.atom2sp, dtype=self.atom2sp.dtype, requirements=["A", "O"])

        libnao.get_spatial_density_parallel(dn_spatial_re.ctypes.data_as(POINTER(c_float)),
                dn_spatial_im.ctypes.data_as(POINTER(c_float)),
                self.mu2dn_re.ctypes.data_as(POINTER(c_double)),
                self.mu2dn_im.ctypes.data_as(POINTER(c_double)),
                self.mesh[0].ctypes.data_as(POINTER(c_double)), 
                self.mesh[1].ctypes.data_as(POINTER(c_double)), 
                self.mesh[2].ctypes.data_as(POINTER(c_double)), 
                atoms2sp.ctypes.data_as(POINTER(c_int64)), 
                c_int(Nx), c_int(Ny), c_int(Nz), 
                c_int(self.nprod), c_int(self.natoms))

        # sum(dn) =  77.8299 63.8207
        # print(np.sum(abs(dn_spatial_re)), np.sum(abs(dn_spatial_im)))
        self.dn_spatial = dn_spatial_re + 1.0j*dn_spatial_im

    def comp_induce_potential(self):
        """
            Compute the induce potential corresponding to the density change
            calculated in get_spatial_density
        """

        from scipy.signal import fftconvolve

        Nx, Ny, Nz = self.mesh[0].size, self.mesh[1].size, self.mesh[2].size

        # Need to initialize the fft operation, the grid should be enlarge
        # (2, 3) to be in same order than fortran
        self.id = np.zeros((2, 3), dtype=np.int32)
        self.ip = np.zeros((2, 3), dtype=np.int32)
        for i in range(3):
            self.id[:, i] = np.rint(self.box[i, :]/self.dr[i])
            self.ip[:, i] = np.rint((self.box[i, :] - self.dr[i]/2)/self.dr[i])

        nffr = np.zeros((3), dtype=np.int32)
        nffc = np.zeros((3), dtype=np.int32)
        n1 = np.zeros((3), dtype=np.int32)
        libnao.initialize_fft(self.id.ctypes.data_as(POINTER(c_int)),
                self.ip.ctypes.data_as(POINTER(c_int)),
                nffr.ctypes.data_as(POINTER(c_int)),
                nffc.ctypes.data_as(POINTER(c_int)),
                n1.ctypes.data_as(POINTER(c_int)),
                )
        
        grid = np.zeros((nffr[0], nffr[1], nffr[2]), dtype = np.float64)

        libnao.comp_spatial_grid_pot(
            self.dr.ctypes.data_as(POINTER(c_double)), 
            grid.ctypes.data_as(POINTER(c_double)))

        return fftconvolve(grid, self.dn_spatial, mode="valid")[0:Nx, 0:Ny, 0:Nz]


    def comp_induce_field(self):
        """
            Compute the induce Electric field corresponding to the density change
            calculated in get_spatial_density
        """


        from scipy.signal import fftconvolve

        Nx, Ny, Nz = self.mesh[0].size, self.mesh[1].size, self.mesh[2].size

        # Need to initialize the fft operation, the grid should be enlarge
        # (2, 3) to be in same order than fortran
        self.id = np.zeros((2, 3), dtype=np.int32)
        self.ip = np.zeros((2, 3), dtype=np.int32)
        for i in range(3):
            self.id[:, i] = np.rint(self.box[i, :]/self.dr[i])
            self.ip[:, i] = np.rint((self.box[i, :] - self.dr[i]/2)/self.dr[i])

        nffr = np.zeros((3), dtype=np.int32)
        nffc = np.zeros((3), dtype=np.int32)
        n1 = np.zeros((3), dtype=np.int32)
        libnao.initialize_fft(self.id.ctypes.data_as(POINTER(c_int)),
                self.ip.ctypes.data_as(POINTER(c_int)),
                nffr.ctypes.data_as(POINTER(c_int)),
                nffc.ctypes.data_as(POINTER(c_int)),
                n1.ctypes.data_as(POINTER(c_int)),
                )
        
        Efield = []# np.zeros((3, Nx, Ny, Nz), dtype = np.complex64)
        grid = np.zeros((nffr[0], nffr[1], nffr[2]), dtype = np.float64)

        for xyz in range(3):
            grid.fill(0.0)
            libnao.comp_spatial_grid(
                self.dr.ctypes.data_as(POINTER(c_double)), 
                c_int(xyz+1), 
                grid.ctypes.data_as(POINTER(c_double)))

            Efield.append(fftconvolve(grid, self.dn_spatial, mode="valid")[0:Nx, 0:Ny, 0:Nz])

        return np.array(Efield)

    def comp_intensity_Efield(self, Efield):
        """
            Compute the intesity of the induce electric field
        """
        return np.sum(Efield.real**2, axis=0) + np.sum(Efield.imag**2, axis=0)
