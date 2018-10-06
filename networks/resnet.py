#=================================================================================================#
# SNDCGAN Architecture
# [Spectral Normalization for Generative Adversarial Networks]
# (https://arxiv.org/pdf/1802.05957.pdf)
#=================================================================================================#

import tensorflow as tf
import numpy as np
from . import ops


class Generator(object):

    def __init__(self, min_resolution, max_resolution, min_filters, max_filters, data_format):

        if (max_resolution // min_resolution) != (max_filters // min_filters):
            raise ValueError("Invalid number of filters")

        self.min_resolution = min_resolution
        self.max_resolution = max_resolution
        self.min_filters = min_filters
        self.max_filters = max_filters
        self.data_format = data_format
        self.num_layers = int(np.log2(max_resolution // min_resolution)) + 2

    def __call__(self, inputs, training, name="generator", reuse=None):

        with tf.variable_scope(name, reuse=reuse):

            for index in range(self.num_layers)[::+1]:

                with tf.variable_scope("layer_{}".format(index)):

                    if index == 0:

                        inputs = self.dense_block(
                            inputs=inputs,
                            index=index,
                            training=training
                        )

                    elif index == self.num_layers - 1:

                        inputs = self.color_block(
                            inputs=inputs,
                            index=index,
                            training=training
                        )

                    else:

                        inputs = self.deconv2d_block(
                            inputs=inputs,
                            index=index,
                            training=training
                        )

            return inputs

    def dense_block(self, inputs, index, training, name="dense_block", reuse=None):

        with tf.variable_scope(name, reuse=None):

            resolution = self.min_resolution << index
            filters = self.max_filters >> index

            inputs = ops.dense(
                inputs=inputs,
                units=resolution * resolution * filters,
                name="dense_0"
            )

            inputs = tf.reshape(
                tensor=inputs,
                shape=[-1, resolution, resolution, filters]
            )

            if self.data_format == "channels_first":

                inputs = tf.transpose(inputs, [0, 3, 1, 2])

            return inputs

    def deconv2d_block(self, inputs, index, training, name="deconv2d_block", reuse=None):

        with tf.variable_scope(name, reuse=reuse):

            filters = self.max_filters >> index

            inputs = ops.upsampling2d(
                inputs=inputs,
                factors=[2, 2],
                data_format=self.data_format,
                dynamic=False
            )

            inputs = ops.residual_block(
                inputs=inputs,
                filters=filters,
                strides=[1, 1],
                normalization=ops.batch_normalization,
                activation=tf.nn.relu,
                data_format=self.data_format,
                training=training,
                name="residual_block_0"
            )

            return inputs

    def color_block(self, inputs, index, training, name="color_block", reuse=None):

        with tf.variable_scope(name, reuse=reuse):

            inputs = ops.batch_normalization(
                inputs=inputs,
                data_format=self.data_format,
                training=training,
                name="batch_normalization_0"
            )

            inputs = tf.nn.relu(inputs)

            inputs = ops.conv2d(
                inputs=inputs,
                filters=3,
                kernel_size=[3, 3],
                strides=[1, 1],
                data_format=self.data_format,
                name="conv2d_0"
            )

            inputs = tf.nn.sigmoid(inputs)

            return inputs


class Discriminator(object):

    def __init__(self, min_resolution, max_resolution, min_filters, max_filters, data_format):

        if (max_resolution // min_resolution) != (max_filters // min_filters):
            raise ValueError("Invalid number of filters")

        self.min_resolution = min_resolution
        self.max_resolution = max_resolution
        self.min_filters = min_filters
        self.max_filters = max_filters
        self.data_format = data_format
        self.num_layers = int(np.log2(max_resolution // min_resolution)) + 2

    def __call__(self, inputs, training, name="discriminator", reuse=None):

        with tf.variable_scope(name, reuse=reuse):

            for index in range(self.num_layers)[::-1]:

                with tf.variable_scope("layer_{}".format(index)):

                    if index == 0:

                        inputs = self.dense_block(
                            inputs=inputs,
                            index=index,
                            training=training
                        )

                    elif index == self.num_layers - 1:

                        inputs = self.color_block(
                            inputs=inputs,
                            index=index,
                            training=training
                        )

                    else:

                        inputs = self.conv2d_block(
                            inputs=inputs,
                            index=index,
                            training=training
                        )

            return inputs

    def dense_block(self, inputs, index, training, name="dense_block", reuse=None):

        with tf.variable_scope(name, reuse=reuse):

            inputs = tf.nn.relu(inputs)

            inputs = ops.global_average_pooling2d(
                inputs=inputs,
                data_format=self.data_format
            )

            inputs = ops.dense(
                inputs=inputs,
                units=1,
                apply_spectral_normalization=True,
                name="dense_0"
            )

            return inputs

    def conv2d_block(self, inputs, index, training, name="conv2d_block", reuse=None):

        with tf.variable_scope(name, reuse=reuse):

            filters = self.max_filters >> (index - 1)

            inputs = ops.residual_block(
                inputs=inputs,
                filters=filters,
                strides=[1, 1],
                data_format=self.data_format,
                apply_spectral_normalization=True,
                normalization=None,
                training=training,
                activation=tf.nn.relu,
                name="residual_block_0"
            )

            inputs = ops.downsampling2d(
                inputs=inputs,
                factors=[2, 2],
                data_format=self.data_format
            )

            return inputs

    def color_block(self, inputs, index, training, name="color_block", reuse=None):

        with tf.variable_scope(name, reuse=reuse):

            filters = self.max_filters >> (index - 1)

            inputs = ops.conv2d(
                inputs=inputs,
                filters=filters,
                kernel_size=[3, 3],
                strides=[1, 1],
                data_format=self.data_format,
                apply_spectral_normalization=True,
                name="conv2d_0"
            )

            inputs = tf.nn.leaky_relu(inputs)

            return inputs
