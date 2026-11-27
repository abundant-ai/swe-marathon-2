"""The online editor receives each RGB frame after its prediction."""


class Updater:
    def __init__(self, model):
        self.model = model

    def update(self, image):
        """image is a CPU float32 tensor shaped (1,3,32,32), with values in [0,1]."""
