# -*- coding: utf-8 -*-
# HORTON: Helpful Open-source Research TOol for N-fermion systems.
# Copyright (C) 2011-2017 The HORTON Development Team
#
# This file is part of HORTON.
#
# HORTON is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# HORTON is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>
#
# --
import shutil
import tempfile
from contextlib import contextmanager

import numpy as np
from os import path

from horton.cext import compute_nucnuc
from horton.meanfield.hamiltonian import REffHam, \
    UEffHam
from horton.meanfield.observable import RTwoIndexTerm, \
    RDirectTerm, RExchangeTerm, UTwoIndexTerm, \
    UDirectTerm, UExchangeTerm
from horton.part.mulliken import get_mulliken_operators

__all__ = ['compute_mulliken_charges', 'compute_hf_energy']


def get_fn(fn):
    cur_pth = path.split(__file__)[0]
    return cur_pth + "/cached/{}".format(fn)


def compute_mulliken_charges(obasis, pseudo_numbers, dm):
    operators = get_mulliken_operators(obasis)
    populations = np.array([np.einsum('ab,ba', operator, dm) for operator in operators])
    assert pseudo_numbers.shape == populations.shape
    return pseudo_numbers - np.array(populations)


@contextmanager
def tmpdir(name):
    dn = tempfile.mkdtemp(name)
    try:
        yield dn
    finally:
        shutil.rmtree(dn)


@contextmanager
def truncated_file(name, fn_orig, nline, nadd):
    """Make a temporary truncated copy of a file.

    Parameters
    ----------
    name : str
           The name of test, used to make a unique temporary directory
    fn_orig : str
              The file to be truncated.
    nline : int
            The number of lines to retain.
    nadd : int
           The number of empty lines to add.
    """
    with tmpdir(name) as dn:
        fn_truncated = '%s/truncated_%i_%s' % (dn, nline, path.basename(fn_orig))
        with open(fn_orig) as f_orig, open(fn_truncated, 'w') as f_truncated:
            for counter, line in enumerate(f_orig):
                if counter >= nline:
                    break
                f_truncated.write(line)
            for _ in xrange(nadd):
                f_truncated.write('\n')
        yield fn_truncated


def compare_orbs(mol1, mol2):
    assert (mol1.orb_alpha == mol2.orb_alpha).all()
    assert (mol1.orb_alpha_coeffs == mol2.orb_alpha_coeffs).all()
    assert (mol1.orb_alpha_energies == mol2.orb_alpha_energies).all()
    assert (mol1.orb_alpha_occs == mol2.orb_alpha_occs).all()
    if hasattr(mol1, "orb_beta") is not None:
        assert (mol1.orb_beta == mol2.orb_beta).all()
        assert (mol1.orb_beta_coeffs == mol2.orb_beta_coeffs).all()
        assert (mol1.orb_beta_energies == mol2.orb_beta_energies).all()
        assert (mol1.orb_beta_occs == mol2.orb_beta_occs).all()


def compare_dict_floats(d1, d2):
    for i, j in zip(d1.values(), d2.values()):
        assert abs(i - j).max() < 1e-8


def compare_mols(mol1, mol2):
    assert (getattr(mol1, 'title') == getattr(mol2, 'title'))
    assert (mol1.numbers == mol2.numbers).all()
    assert (mol1.coordinates == mol2.coordinates).all()
    # orbital basis
    if mol1.obasis is not None:
        compare_dict_floats(mol1.obasis, mol2.obasis)
    else:
        assert mol2.obasis is None
    # wfn
    assert (mol1.orb_alpha == mol2.orb_alpha).all()
    assert (mol1.orb_alpha_coeffs == mol2.orb_alpha_coeffs).all()
    assert (mol1.orb_alpha_energies == mol2.orb_alpha_energies).all()
    assert (mol1.orb_alpha_occs == mol2.orb_alpha_occs).all()
    if hasattr(mol1, "orb_beta") is not None:
        assert (mol1.orb_beta == mol2.orb_beta).all()
        assert (mol1.orb_beta_coeffs == mol2.orb_beta_coeffs).all()
        assert (mol1.orb_beta_energies == mol2.orb_beta_energies).all()
        assert (mol1.orb_beta_occs == mol2.orb_beta_occs).all()

    # operators
    for key in 'olp', 'kin', 'na', 'er', 'dm_full_mp2', 'dm_spin_mp2', \
               'dm_full_mp3', 'dm_spin_mp3', 'dm_full_ci', 'dm_spin_ci', \
               'dm_full_cc', 'dm_spin_cc', 'dm_full_scf', 'dm_spin_scf':
        if hasattr(mol1, key):
            assert hasattr(mol2, key)
            np.testing.assert_equal(getattr(mol1, key), getattr(mol2, key))
        else:
            assert not hasattr(mol2, key)


def get_random_cell(a, nvec):
    if nvec == 0:
        return None
    if a <= 0:
        raise ValueError('The first argument must be strictly positive.')
    return np.random.uniform(0, a, (nvec, 3))


def check_orthonormal(occupations, coeffs, overlap, eps=1e-4):
    """Check that the occupied orbitals are orthogonal and normalized.

    When the orbitals are not orthonormal, an AssertionError is raised.

    Parameters
    ----------
    occupations : np.ndarray, shape=(nfn, )
        The orbital occupations.
    coeffs : np.ndarray, shape=(nbasis, nfn)
        The orbital coefficients.
    overlap : np.ndarray, shape=(nbasis, nbasis)
        The overlap matrix.
    eps : float
        The allowed deviation from unity, very loose by default.
    """
    for i0 in xrange(occupations.size):
        if occupations[i0] == 0:
            continue
        for i1 in xrange(i0+1):
            if occupations[i1] == 0:
                continue
            dot = np.dot(coeffs[:,i0], np.dot(overlap, coeffs[:,i1]))
            if i0 == i1:
                assert abs(dot-1) < eps
            else:
                assert abs(dot) < eps