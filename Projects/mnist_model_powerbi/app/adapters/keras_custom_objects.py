from __future__ import annotations

import tensorflow as tf


@tf.keras.utils.register_keras_serializable(
    package="MNIST",
    name="grayscale_to_rgb_layer",
)
def grayscale_to_rgb_layer(inputs):
    return tf.image.grayscale_to_rgb(inputs)


@tf.keras.utils.register_keras_serializable(
    package="MNIST",
    name="ApplicationPreprocess",
)
class ApplicationPreprocess(tf.keras.layers.Layer):
    def __init__(self, application: str, **kwargs):
        super().__init__(**kwargs)
        self.application = str(application).lower()

    def call(self, inputs):
        if self.application in {"mobilenetv2", "mobilenet_v2"}:
            return tf.keras.applications.mobilenet_v2.preprocess_input(
                inputs
            )

        if self.application == "resnet50":
            return tf.keras.applications.resnet50.preprocess_input(
                inputs
            )

        if self.application in {
            "efficientnetb0",
            "efficientnet_b0",
        }:
            return tf.keras.applications.efficientnet.preprocess_input(
                inputs
            )

        raise ValueError(
            f"Unsupported application: {self.application}"
        )

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "application": self.application,
            }
        )
        return config

    @classmethod
    def from_config(cls, config):
        return cls(**config)


@tf.keras.utils.register_keras_serializable(
    package="MNIST",
    name="Patches",
)
class Patches(tf.keras.layers.Layer):
    def __init__(self, patch_size: int, **kwargs):
        super().__init__(**kwargs)
        self.patch_size = int(patch_size)

    def call(self, images):
        batch_size = tf.shape(images)[0]

        patches = tf.image.extract_patches(
            images=images,
            sizes=[
                1,
                self.patch_size,
                self.patch_size,
                1,
            ],
            strides=[
                1,
                self.patch_size,
                self.patch_size,
                1,
            ],
            rates=[1, 1, 1, 1],
            padding="VALID",
        )

        patch_dimensions = tf.shape(patches)[-1]

        return tf.reshape(
            patches,
            [
                batch_size,
                -1,
                patch_dimensions,
            ],
        )

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "patch_size": self.patch_size,
            }
        )
        return config

    @classmethod
    def from_config(cls, config):
        return cls(**config)


@tf.keras.utils.register_keras_serializable(
    package="MNIST",
    name="PatchEncoder",
)
class PatchEncoder(tf.keras.layers.Layer):
    def __init__(
        self,
        num_patches: int | None = None,
        projection_dim: int | None = None,
        number_of_patches: int | None = None,
        projection_dimension: int | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        if num_patches is None:
            num_patches = number_of_patches

        if projection_dim is None:
            projection_dim = projection_dimension

        if num_patches is None:
            raise ValueError("num_patches is required")

        if projection_dim is None:
            raise ValueError("projection_dim is required")

        self.num_patches = int(num_patches)
        self.projection_dim = int(projection_dim)

        self.projection = tf.keras.layers.Dense(
            units=self.projection_dim,
            name="projection",
        )

        self.position_embedding = tf.keras.layers.Embedding(
            input_dim=self.num_patches,
            output_dim=self.projection_dim,
            name="position_embedding",
        )

    def call(self, patches):
        positions = tf.range(
            start=0,
            limit=self.num_patches,
            delta=1,
        )

        return (
            self.projection(patches)
            + self.position_embedding(positions)
        )

    def get_config(self):
        config = super().get_config()
        config.update(
            {
                "num_patches": self.num_patches,
                "projection_dim": self.projection_dim,
            }
        )
        return config

    @classmethod
    def from_config(cls, config):
        return cls(**config)


CUSTOM_OBJECTS = {
    "ApplicationPreprocess": ApplicationPreprocess,
    "Patches": Patches,
    "PatchEncoder": PatchEncoder,
    "grayscale_to_rgb_layer": grayscale_to_rgb_layer,

    "MNIST>ApplicationPreprocess": ApplicationPreprocess,
    "MNIST>Patches": Patches,
    "MNIST>PatchEncoder": PatchEncoder,
    "MNIST>grayscale_to_rgb_layer": grayscale_to_rgb_layer,
}