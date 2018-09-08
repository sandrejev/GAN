from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import functools


def batch_normalization(data_format):

    return functools.partial(
        tf.layers.batch_normalization,
        axis=(1 if data_format == "channels_first" else 3)
    )


def global_average_pooling2d(data_format):

    return functools.partial(
        tf.reduce_mean,
        axis=([2, 3] if data_format == "channels_first" else [1, 2])
    )


def up_sampling2d(size, data_format):

    return tf.keras.layers.UpSampling2D(
        size=size,
        data_format=data_format
    )


def flatten_images(inputs, data_format):

    shape = inputs.get_shape().as_list()

    return tf.reshape(
        tensor=inputs,
        shape=([-1, shape[1], shape[2] * shape[3]] if data_format == "channels_first" else
               [-1, shape[1] * shape[2], shape[3]])
    )


def chunk_images(inputs, image_size, data_format):

    shape = inputs.get_shape().as_list()

    return tf.reshape(
        tensor=inputs,
        shape=([-1, shape[1] // (image_size[0] * image_size[1]), image_size[0], image_size[1]] if data_format == "channels_first" else
               [-1, image_size[0], image_size[1], shape[1] // (image_size[0] * image_size[1])])
    )


def get_channels(inputs, data_format):

    return inputs.get_shape().as_list()[(1 if data_format == "channels_first" else 3)]
