import pandas as pd
import numpy as np
import cobra

from pyefm.ElementaryFluxModes import EFMToolWrapper


class EFVWrapper(EFMToolWrapper):

    def create_matrices(self):

        # Create stoichiometric matrix, get key dimensions
        N = cobra.util.create_stoichiometric_matrix(self.model)
        nm, nr = N.shape
        self.nm = nm
        self.nr = nr

        # Construct full G and h matrices, then drop homogeneous (or near
        # homogeneous) entries
        g_full = np.vstack([np.eye(nr), -np.eye(nr)])
        h_full = np.array([(r.lower_bound, -r.upper_bound)
                           for r in self.model.reactions]).T.flatten()

        inhomogeneous = ~((h_full <= -1000) | np.isclose(h_full, 0))
        h = h_full[inhomogeneous]
        G = g_full[inhomogeneous]

        self.nt = nt = len(h)

        self.D = np.vstack([
            np.hstack([N, np.zeros((nm, nt)), np.zeros((nm, 1))]),
            np.hstack([G, -np.eye(nt), np.atleast_2d(-h).T])
        ])

    def create_model_files(self, temp_dir):
        
        self.create_matrices()

        # Stoichiometric Matrix
        np.savetxt(temp_dir + '/stoich.txt', self.D, delimiter='\t')

        # Reaction reversibilities
        np.savetxt(temp_dir + '/revs.txt',
                   np.hstack([
                    np.array([r.reversibility for r in self.model.reactions]),
                    np.zeros((self.nt + 1))]),
                   delimiter='\t', fmt='%d', newline='\t')

        # Reaction Names
        r_names = np.hstack([
                np.array([r.id for r in self.model.reactions]),
                np.array(['s{}'.format(i) for i in range(self.nt)]),
                np.array(['lambda'])
            ])
        with open(temp_dir + '/rnames.txt', 'w') as f:
            f.write('\t'.join(('"{}"'.format(name) for name in r_names)))

        # Metabolite Names
        m_names = np.hstack([
                np.array([m.id for m in self.model.metabolites]),
                np.array(['s{}'.format(i) for i in range(self.nt)]),
            ])
        with open(temp_dir + '/mnames.txt', 'w') as f:
            f.write('\t'.join(('"{}"'.format(name) for name in m_names)))

        pass

    def read_double_out(self, out_file):
        with open(out_file, 'rb') as f:
            out_arr = np.fromstring(f.read()[13:], dtype='>d').reshape(
                (-1, self.nt + self.nr + 1)).T
            out_arr = np.asarray(out_arr, dtype=np.float64).T

        unbounded = out_arr[np.isclose(out_arr[:,-1], 0.)]
        bounded = out_arr[~np.isclose(out_arr[:,-1], 0.)]

        if bounded.size:  # Test if its empty
            bounded /= np.atleast_2d(bounded[:,-1]).T

        unbounded_df = pd.DataFrame(
            unbounded[:, :self.nr], 
            columns=[r.id for r in self.model.reactions],
            index=['UEV{}'.format(i) 
                   for i in range(1, unbounded.shape[0] + 1)])

        bounded_df = pd.DataFrame(
            bounded[:, :self.nr], 
            columns=[r.id for r in self.model.reactions],
            index=('BEV{}'.format(i) 
                   for i in range(1, bounded.shape[0] + 1)))

        return unbounded_df.append(bounded_df)
 

def calculate_elementary_vectors(cobra_model, opts=None, verbose=True):
    """Calculate elementary flux vectors, which capture arbitrary linear
    constraints. Approach as detailed in S. Klamt et al., PLoS Comput Biol. 13,
    e1005409–22 (2017)."""
    return EFVWrapper(cobra_model, opts, verbose)()
    

