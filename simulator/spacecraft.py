from datetime import datetime, timedelta

import astrodynamics as astro
import drag as drag
import numpy as np
from brahe import frames
from brahe.epoch import Epoch

from brahe.orbit_dynamics.gravity import accel_gravity, accel_thirdbody_moon, accel_thirdbody_sun
from scipy.linalg import expm
from transformations import L, R

from brahe import EOP
EOP.load("simulation/data/finals.all.iau2000.txt")

class Spacecraft:

    REQUIRED_KEYS = ["mass", "dt"]
    H = np.vstack([np.zeros(3), np.eye(3)])

    DEFAULTS = {
        "epoch": datetime(2024, 1, 1, 0, 0, 0, 0),
        "gravity_order": 10,  # Setting both order and degree at once
        "drag": True,
        "third-body": True,
        "solar-radiation": True,
        "gravity-gradient": True,
        "inertia": np.array([[0.0033, 0.0, 0.0], [0.0, 0.0033, 0.0], [0.0, 0.0, 0.0033]]),
        "Cd": 2,
        "crossA": 0.01,  # m^2
        "flexible": False
    }

    µ = 3.986004418e14

    # Normalized surface normals
    __surface_normals = np.array([
                        [1.0, 0.0, 0.0],
                        [-1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, -1.0, 0.0],
                        [0.0, 0.0, 1.0],
                        [0.0, 0.0, -1.0]
                    ])

    def __init__(self, configuration):

        # Check if all required keys are provided in the configuration
        missing_keys = [key for key in self.REQUIRED_KEYS if key not in configuration]
        if missing_keys:
            raise ValueError(f"Missing required keys: {', '.join(missing_keys)}")

        # Initial state
        if "initial_attitude" not in configuration:
            raise ValueError("Missing required 'initial_attitude'.")

        if "initial_orbit_eci" not in configuration and "initial_orbit_oe" not in configuration:
            raise ValueError("Missing required initial orbit: 'initial_orbit_eci' or 'initial_orbit_oe'.")

        orbit = None
        if "initial_orbit_oe" in configuration:
            orbit = astro.get_CART_from_OSC(configuration["initial_orbit_oe"])
        else:
            orbit = np.array(configuration["initial_orbit_eci"])

        # TODO check sizes
        self._state = np.concatenate((orbit, np.array(configuration["initial_attitude"])))

        # Mass
        if configuration["mass"] >= 0.0:
            self._mass = configuration["mass"]
        else:
            raise ValueError("Negative mass value")

        # Timestep
        if configuration["dt"] >= 0.0:
            self._dt = configuration["dt"]
        else:
            raise ValueError("Negative dt value")
        
        # Epoch
        if "epoch" in configuration:
            if isinstance(configuration["epoch"], datetime):
                self._epoch = Epoch(configuration["epoch"])
                self.epoch_dt = configuration["epoch"]
            else:
                raise ValueError("Epoch must be a datetime object.")
        else:
            self._epoch = Epoch(self.DEFAULTS["epoch"])
            self.epoch_dt = self.DEFAULTS["epoch"]

        # Inertia
        if "inertia" in configuration:
            if len(configuration["inertia"]) == 6:

                Iv = configuration["inertia"]
                inertia = np.array([[Iv[0],Iv[3],Iv[4]],[Iv[3], Iv[1], Iv[5]],[Iv[4], Iv[5], Iv[2]]])

                # Check positive-definiteness
                if np.all(np.linalg.eigvals(inertia) > 0):
                    self.J = np.array(inertia)
                    self.invJ = np.linalg.inv(self.J)
                else:
                    raise ValueError("Inertia is not positive-definite.")

            else:
                raise ValueError("Need a array of 6 elements to define the inertia: [Ixx, Iyy, Izz, Ixy, Ixz, Iyz].")

        else:
            self.J = self.DEFAULTS["inertia"]
            self.invJ = np.linalg.inv(self.J)

        if "gravity_order" in configuration:
            self._gravity_order = configuration["gravity_order"]
        else:
            self._gravity_order = self.DEFAULTS["gravity_order"]

        if "drag" in configuration:
            self._drag = configuration["drag"]
        else:
            self._drag = self.DEFAULTS["drag"]

        if "third_body" in configuration:
            self._third_body = configuration["third_body"]
        else:
            self._third_body = self.DEFAULTS["third-body"]

        # TODO check
        if "crossA" in configuration:
            self._crossA = configuration["crossA"]
        else:
            self._crossA = self.DEFAULTS["crossA"]

        # TODO check
        if "Cd" in configuration:
            self._Cd = configuration["Cd"]
        else:
            self._Cd = self.DEFAULTS["Cd"]

        if "flexible" in configuration:
            self._flexible = configuration["flexible"]
        else:
            self._flexible = self.DEFAULTS["flexible"]

    @property
    def state(self):
        return self._state

    @property
    def epoch(self):
        return self._epoch

    @property
    def attitude_states(self):
        return self._state[6:13]

    @property
    def attitude(self):
        return self._state[6:10]
    
    @property
    def angular_velocity(self):
        return self._state[10:13]

    @property
    def orbit_eci(self):
        return self._state[0:6]
    
    @property
    def surface_normals(self):
        return self.__surface_normals

    @property
    def orbit_oe(self):
        """
        1. _a_, Semi-major axis [m]
        2. _e_, Eccentricity [dimensionless]
        3. _i_, Inclination [rad]
        4. _Ω_, Right Ascension of the Ascending Node (RAAN) [rad]
        5. _ω_, Argument of Perigee [ramd]
        6. _M_, Mean anomaly [rad]
        """
        return astro.get_OSC_from_CART(self._state[0:6])

    def orbital_accelerations(self):

        x_eci = self._state
        a = np.zeros(3)

        R_i2b = frames.rECItoECEF(self._epoch)

        a += accel_gravity(
            x_eci[0:6],
            R_i2b,
            n_max=self._gravity_order,
            m_max=self._gravity_order,
        )

        if self._drag:
            a += drag.accel_drag(
                self.epoch_dt,
                x_eci[0:6],
                self._mass,
                self._crossA,
                self._Cd,
                R_i2b
            )

        if self._third_body:
            # acc due to third body moon
            a += accel_thirdbody_moon(self._epoch, x_eci[0:6])
            # acc due to third body sun
            a += accel_thirdbody_sun(self._epoch, x_eci[0:6])

        return a

    def dynamics(self, x, torque):
        if len(torque) != 3:
            raise ValueError("Torque must be an array of 3 elements.")
        xdot = np.zeros(13)
        xdot[0:3] = x[3:6]
        xdot[3:6] = self.orbital_accelerations()
        xdot[6:10] = 0.5 * L(x[6:10]) @ self.H @ x[10:13]
        xdot[10:13] = self.invJ.dot(torque - np.cross(x[10:13], np.dot(self.J, x[10:13])))
        return xdot

    def set_dt(self, new_dt):
        if new_dt <= 0:
            raise ValueError("dt must be positive.")
        self.dt = new_dt

    def advance(self, u_torque):

        q = self._state[6:10]
        ω = self._state[10:13]

        k1 = self._dt * self.dynamics(self._state, u_torque)
        k2 = self._dt * self.dynamics(self._state + k1 * 0.5, u_torque)
        k3 = self._dt * self.dynamics(self._state + k2 * 0.5, u_torque)
        k4 = self._dt * self.dynamics(self._state + k3, u_torque)

        self._state = self._state + (1 / 6) * (k1 + 2 * k2 + 2 * k3 + k4)
        self._state[6:10] = np.dot(
            expm(R(self.H.dot(0.5 * self._dt * ω + (self._dt / 6) * (k1[10:13] + k2[10:13] + k3[10:13])))), q
        )

        self._advance_epoch()

    def _advance_epoch(self):
        self._epoch += self._dt
        self.epoch_dt += timedelta(seconds=self._dt)


# Temporary local testing
if __name__ == "__main__":

    config = {
        "mass": 2.0,
        "inertia": [10, 20, 30, 0.0, 0.0, 0.0],
        "dt": 1.0,
        "epoch": datetime(2024, 6, 1, 12, 0, 0, 0),
        "initial_attitude": [1.0, 0, 0, 0, 0.1, -0.2, 0.3],
        "initial_orbit_oe": [6.92e6, 0, 0, 0, 0, 0],
        "gravity_order": 5,
        "gravity_degree": 5,
        "drag": True,
        "third_body": True
    }

    spacecraft = Spacecraft(config)
    u = np.zeros(3)

    from sensors import Magnetometer, Gyroscope, SunVector, GPS
    mag = Magnetometer(2.0)
    gyro = Gyroscope(0.01, 0.2, 0.5)
    sun_vec = SunVector(0.1, 0.0)
    gps = GPS(10, 0.1)
    from magnetorquer import Magnetorquer
    torquer = Magnetorquer()


    for i in range(10):
        spacecraft.advance(u)
        print("Orbit (ECI): ", spacecraft.orbit_eci)
        print("Attitude: ", spacecraft.attitude)
        print("Angular Velocity: ", spacecraft.angular_velocity)
        print("Gyroscope: ", gyro.measure(spacecraft))
        print("Magnetometer: ", mag.measure(spacecraft))
        print("Measured Lux: ", sun_vec.measure_lux(spacecraft))
        print("Measured Sun Vector: ", sun_vec.measure(spacecraft))
        print("GPS (ECEF): ", gps.measure(spacecraft))
        print("Dipole Moment (voltage): ", torquer.set_dipole_moment_voltage(4))
        print("Dipole Moment (current): ", torquer.set_dipole_moment_current(0.32))
        
