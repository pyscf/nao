from __future__ import print_function, division
import numpy as np
from numpy import zeros, dot

def omask2wgts_loops(mf, omask, over):
  """ Finds weights """
  ksn2w = zeros(mf.mo_energy.shape[:])
  for k in range(mf.nkpoints):
    for s in range(mf.nspin):
      for n in range(mf.norbs):
        ksn2w[k,s,n] = dot( dot(omask*mf.mo_coeff[k,s,n,:,0], over), mf.mo_coeff[k,s,n,:,0])
  return ksn2w


def omask_dos(mf, zomegas, omask, over=None, nkpoints=1): 
  """ Compute some partial Density of States """
  over = mf.hsx.s4_csr.toarray() if over is None else over
  ksn2w = omask2wgts_loops(mf, omask, over)
  mdos = zeros(len(zomegas))
  for iw,zw in enumerate(zomegas):
    mdos[iw] = (ksn2w[:,:,:]/(zw - mf.wfsx.ksn2e[:,:,:])).sum().imag

  return -mdos/np.pi/nkpoints


def lsoa_dos(mf, zomegas, lsoa=None, nkpoints=1): 
  """ Compute the Partial Density of States according to a list of atoms """
  lsoa = range(mf.natoms) if lsoa is None else lsoa

  mask = zeros(mf.norbs)
  for a in lsoa: mask[mf.atom2s[a]:mf.atom2s[a+1]] = 1.0

  over = mf.hsx.s4_csr.toarray()
  dos = omask_dos(mf, zomegas, mask, over, nkpoints)
  return dos


def pdos(mf, zomegas, nkpoints=1): 
  """ Compute the Partial Density of States (resolved in angular momentum of the orbitals) using the eigenvalues and eigenvectors in wfsx """
  
  jmx = mf.ao_log.jmx
  over = mf.hsx.s4_csr.toarray()
  orb2j = mf.get_orb2j()
  
  pdos = zeros((jmx+1,len(zomegas)))
  for j in range(jmx+1):
    mask = (orb2j==j)
    pdos[j] = omask_dos(mf, zomegas, mask, over, nkpoints)

  return pdos
