from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import collections
import gan


class Model(gan.Model):

    HyperParam = collections.namedtuple("HyperParam", ("latent_size", "gradient_coefficient"))

    def __init__(self, dataset, generator, discriminator, hyper_param):

        self.gradient_coefficient = tf.constant(value=hyper_param.gradient_coefficient, dtype=tf.float32)

        super().__init__(dataset, generator, discriminator, hyper_param)

    def generator_loss(self):

        loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(
            logits=self.fake_logits, labels=tf.ones_like(self.fake_logits)
        ))

        return loss

    def discriminator_loss(self):

        loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(
            logits=self.real_logits, labels=tf.ones_like(self.real_logits)
        ))
        loss += tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(
            logits=self.fake_logits, labels=tf.zeros_like(self.fake_logits)
        ))
        loss += self.gradient_penalty() * self.gradient_coefficient

        return loss

    def gradient_penalty(self):

        interpolate_coefficients = tf.random_uniform(shape=[self.batch_size, 1, 1, 1], dtype=tf.float32)
        interpolates = self.reals + (self.fakes - self.reals) * interpolate_coefficients
        interpolate_logits = self.discriminator(inputs=interpolates, training=self.training, reuse=True)

        gradients = tf.gradients(ys=interpolate_logits, xs=interpolates)[0]
        slopes = tf.sqrt(tf.reduce_sum(tf.square(gradients), axis=[1, 2, 3]) + 0.0001)
        gradient_penalty = tf.reduce_mean(tf.square(slopes - 1.0))

        return gradient_penalty