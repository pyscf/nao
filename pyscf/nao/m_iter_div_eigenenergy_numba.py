from __future__ import division
import numba as nb
import numpy as np

@nb.jit(nopython=True)
def div_eigenenergy_numba(ksn2e, ksn2f, nfermi, vstart, comega, nm2v_re, nm2v_im, norbs):
    """
        multiply the temporary matrix by (fn - fm) (frac{1.0}{w - (Em-En) -1} -
            frac{1.0}{w + (Em - En)})
        using numba
    """

    for n in range(nfermi):
        en = ksn2e[n]
        fn = ksn2f[n]
        for m in range(norbs-vstart):
            em = ksn2e[m+vstart]
            fm = ksn2f[m+vstart]

            nm2v = nm2v_re[n, m] + 1.0j*nm2v_im[n, m]
            nm2v = nm2v * (fn-fm) * ( 1.0 / (comega - (em - en)) - 1.0 /\
                    (comega + (em - en)) )

            nm2v_re[n, m] = nm2v.real
            nm2v_im[n, m] = nm2v.imag

    for n in range(vstart+1, nfermi):
        for m in range(n-vstart):
            nm2v_re[n, m] = 0.0 
            nm2v_im[n, m] = 0.0


@nb.jit(nopython=True)
def mat_mul_numba(a, b):
    return a*b
