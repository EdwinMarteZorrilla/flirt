import numpy as np
import pandas as pd
import pyparticleest.utils.kalman as kalman
import pyparticleest.interfaces as interfaces
import pyparticleest.simulator as simulator

from .data_utils import Preprocessor

class Model(interfaces.ParticleFiltering):
    """ x_{k+1} = x_k + v_k, v_k ~ N(0,Q)
        y_k = x_k + e_k, e_k ~ N(0,R),
        x(0) ~ N(0,P0) """

    def __init__(self, P0, Q, R):
        self.P0 = np.copy(P0)
        self.Q = np.copy(Q)
        self.R = np.copy(R)

    def create_initial_estimate(self, N):
        return np.random.normal(0.0, self.P0, (N,)).reshape((-1, 1))

    def sample_process_noise(self, particles, u, t):
        """ Return process noise for input u """
        N = len(particles)
        return np.random.normal(0.0, self.Q, (N,)).reshape((-1, 1))

    def update(self, particles, u, t, noise):
        """ Update estimate using 'data' as input """
        particles += noise

    def measure(self, particles, y, t):
        """ Return the log-pdf value of the measurement """
        logyprob = np.empty(len(particles), dtype=float)
        for k in range(len(particles)):
            logyprob[k] = kalman.lognormpdf_scalar(particles[k].reshape(-1, 1) - y, self.R)
        return logyprob

    def logp_xnext_full(self, part, past_trajs, pind,
                        future_trajs, find, ut, yt, tt, cur_ind):

        diff = future_trajs[0].pa.part[find] - part

        logpxnext = np.empty(len(diff), dtype=float)
        for k in range(len(logpxnext)):
            logpxnext[k] = kalman.lognormpdf(diff[k].reshape(-1, 1), np.asarray(self.Q).reshape(1, 1))
        return logpxnext


class ParticleFilter(Preprocessor):
    """ This class filters the raw EDA data using Particle Filter algorithm, reducing the measurement noise and eliminating motion artifacts. 
    """

    def __init__(self, num_particles: int = 80, num_smoothers: int = 40, P0_variance: float = 0.02, 
                Q_variance: float = 0.02, R_variance: float = 0.06):
        """ Consruct the Particle filtering model.

        Parameters
        -----------
        num_particles : int, optional
            the number of filtering particles initialised for the particle filtering algorithm
        num_smoothers : int, optional
            the number of backward trajectories generated by the smoothing algorithm , which backward evaluates all particle weights
        P0_variance : float, optional
            the process model's initial variance
        Q_variance : float, optional
            the process noise's variance
        R_variance : float, optional
            the measurement noise's variance
        """

        self.num_particles = num_particles
        self.num_smoothers = num_smoothers
        self.P0 = P0_variance
        self.Q = Q_variance
        self.R = np.asarray(((R_variance,),))

    def __process__(self, data: pd.Series) -> pd.Series:
        """ Perform the signal filtering.

        Parameters
        ----------
        data : pd.Series
            raw EDA data , index is a list of timestamps according on the sampling frequency (e.g. 4Hz for Empatica), column is the raw eda data: `eda`

        Returns
        -------
        pd.Series
            series containing the filtered EDA signal using the Particle Filter algorithm

        Notes
        ------
        - Increasing the number of particles will lead to a more accurate result at the expense of computing time.
        - Increasing the variance values will lead to more degenerate results, which might diverge. 

        Examples
        --------
        >>> import flirt.reader.empatica
        >>> import flirt.eda
        >>> eda = flirt.reader.empatica.read_eda_file_into_df('./EDA.csv')
        >>> eda_filtered_pf = flirt.eda.preprocessing.ParticleFilter().__process__(eda['eda'])
        
        References
        ----------
        - https://github.com/jerkern/pyParticleEst
        """

        eda = np.ravel(data)
        eda_len = len(eda)
        
        model = Model(self.P0, self.Q, self.R)
        sim = simulator.Simulator(model, u=None, y=eda)

        sim.simulate(self.num_particles, self.num_smoothers, filter='PF', smoother='full', meas_first = False)

        vals_mean = sim.get_filtered_mean()
        particle_filtered = vals_mean[:, 0]

        # Return SC filtered data as a pd.Series
        return pd.Series(data=particle_filtered, index=data.index, name='filtered_eda')
