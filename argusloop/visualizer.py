import time
import numpy as np

import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf


class Visualizer:

    visualization_modes = ["attitude", "position"]

    def __init__(self, mesh_stl_path, visualization_mode="attitude"):
        self.viz = meshcat.Visualizer()
        self.mesh = meshcat.geometry.StlMeshGeometry.from_file(mesh_stl_path)
        self.viz["spacecraft"].set_object(self.mesh)

        if visualization_mode not in self.visualization_modes:
            raise ValueError("Invalid visualization mode. Choose from: {}".format(self.visualization_modes))


    def start_visualization(self):
        self.viz.open()
        self.viz["/Background"].set_property("top_color", [0, 0, 0.1])
        self.viz["/Background"].set_property("bottom_color", [0, 0, 0.1])
        self.set_grid(False)
        time.sleep(2)

    def set_grid(self, on):
        self.viz["/Grid"].set_property("visible", on)

    def set_position(self, translation_vector):
        # [x, y, z] position
        self.viz["spacecraft"].set_transform(tf.translation_matrix(translation_vector))

    def set_attitude(self, quat):
        self.viz["spacecraft"].set_transform(tf.quaternion_matrix(quat))



# Temporary local testing
if __name__ == "__main__":
    stl_filename = "assets/argus_v0.STL"
    viz = Visualizer(stl_filename)
    viz.start_visualization()

    viz.set_position([1,0,0])
    q = np.random.rand(4)
    q = q / np.linalg.norm(q)
    q = [0.7071068, 0.7071068, 0, 0]
    viz.set_attitude(q)
    time.sleep(2)
    viz.set_attitude(q)
    time.sleep(2)

