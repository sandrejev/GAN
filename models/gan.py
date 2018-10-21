import tensorflow as tf
import numpy as np
import os
import itertools
import time
import cv2


def lerp(a, b, t):
    return a + (b - a) * t


class Model(object):

    class LossFunction:
        NS_GAN, WGAN = range(2)

    class GradientPenalty:
        ZERO_CENTERED, ONE_CENTERED = range(2)

    def __init__(self, dataset, generator, discriminator, loss_function,
                 gradient_penalty, hyper_params, name="gan", reuse=None):

        # if train this model in PGGAN style
        # set reuse=tf.AUTO_REUSE
        with tf.variable_scope(name, reuse=reuse):

            self.name = name
            self.dataset = dataset
            self.generator = generator
            self.discriminator = discriminator
            self.hyper_parameters = hyper_params

            self.batch_size = tf.placeholder(
                dtype=tf.int32,
                shape=[],
                name="batch_size"
            )
            self.training = tf.placeholder(
                dtype=tf.bool,
                shape=[],
                name="training"
            )

            self.next_reals = self.dataset.get_next()
            self.next_latents = tf.random_normal(shape=[self.batch_size, self.hyper_parameters.latent_size])

            self.reals = tf.placeholder(
                dtype=tf.float32,
                shape=self.next_reals.shape,
                name="reals"
            )
            self.latents = tf.placeholder(
                dtype=tf.float32,
                shape=[None, self.hyper_parameters.latent_size],
                name="latents"
            )

            self.fakes = generator(
                inputs=self.latents,
                training=self.training,
                name="generator"
            )

            self.real_logits = discriminator(
                inputs=self.reals,
                training=self.training,
                name="discriminator"
            )
            self.fake_logits = discriminator(
                inputs=self.fakes,
                training=self.training,
                name="discriminator",
                reuse=True
            )

            #========================================================================#
            # two types of loss function
            # 1. NS-GAN loss function (https://arxiv.org/pdf/1406.2661.pdf)
            # 2. WGAN loss function (https://arxiv.org/pdf/1701.07875.pdf)
            #========================================================================#
            if loss_function == Model.LossFunction.NS_GAN:

                self.generator_loss = tf.reduce_mean(
                    tf.nn.sigmoid_cross_entropy_with_logits(
                        logits=self.fake_logits,
                        labels=tf.ones_like(self.fake_logits)
                    )
                )

                self.discriminator_loss = tf.reduce_mean(
                    tf.nn.sigmoid_cross_entropy_with_logits(
                        logits=self.real_logits,
                        labels=tf.ones_like(self.real_logits)
                    )
                )
                self.discriminator_loss += tf.reduce_mean(
                    tf.nn.sigmoid_cross_entropy_with_logits(
                        logits=self.fake_logits,
                        labels=tf.zeros_like(self.fake_logits)
                    )
                )

            elif loss_function == Model.LossFunction.WGAN:

                self.generator_loss = -tf.reduce_mean(self.fake_logits)

                self.discriminator_loss = -tf.reduce_mean(self.real_logits)
                self.discriminator_loss += tf.reduce_mean(self.fake_logits)

            else:
                raise ValueError("Invalid loss function")

            #========================================================================#
            # linear interpolation for gradient penalty
            #========================================================================#
            self.lerp_coefficients = tf.random_uniform(shape=[self.batch_size, 1, 1, 1])
            self.lerped = lerp(self.reals, self.fakes, self.lerp_coefficients)
            self.lerped_logits = discriminator(
                inputs=self.lerped,
                training=self.training,
                name="discriminator",
                reuse=True
            )
            #========================================================================#
            # two types of gradient penalty
            # 1. zero-centered gradient penalty (https://openreview.net/pdf?id=ByxPYjC5KQ)
            # -> NOT EFFECTIVE FOR NOW
            # 2. one-centered gradient penalty (https://arxiv.org/pdf/1704.00028.pdf)
            # to avoid NaN exception, add epsilon inside sqrt()
            # (https://github.com/tdeboissiere/DeepLearningImplementations/issues/68)
            #========================================================================#
            self.gradients = tf.gradients(ys=self.lerped_logits, xs=self.lerped)[0]
            self.slopes = tf.sqrt(tf.reduce_sum(tf.square(self.gradients), axis=[1, 2, 3]) + 0.0001)

            if gradient_penalty == Model.GradientPenalty.ZERO_CENTERED:

                self.gradient_penalty = tf.reduce_mean(tf.square(self.slopes - 0.0))

            elif gradient_penalty == Model.GradientPenalty.ONE_CENTERED:

                self.gradient_penalty = tf.reduce_mean(tf.square(self.slopes - 1.0))

            else:
                raise ValueError("Invalid gradient penalty")

            self.discriminator_loss += self.gradient_penalty * self.hyper_parameters.gradient_coefficient

            self.generator_variables = tf.get_collection(
                key=tf.GraphKeys.TRAINABLE_VARIABLES,
                scope="{}/generator".format(self.name)
            )
            self.discriminator_variables = tf.get_collection(
                key=tf.GraphKeys.TRAINABLE_VARIABLES,
                scope="{}/discriminator".format(self.name)
            )

            self.generator_global_step = tf.get_variable(
                name="generator_global_step",
                shape=[],
                dtype=tf.int32,
                initializer=tf.zeros_initializer(),
                trainable=False
            )
            self.discriminator_global_step = tf.get_variable(
                name="discriminator_global_step",
                shape=[],
                dtype=tf.int32,
                initializer=tf.zeros_initializer(),
                trainable=False
            )

            self.generator_optimizer = tf.train.AdamOptimizer(
                learning_rate=self.hyper_parameters.learning_rate,
                beta1=self.hyper_parameters.beta1,
                beta2=self.hyper_parameters.beta2
            )
            self.discriminator_optimizer = tf.train.AdamOptimizer(
                learning_rate=self.hyper_parameters.learning_rate,
                beta1=self.hyper_parameters.beta1,
                beta2=self.hyper_parameters.beta2
            )

            #========================================================================#
            # to update moving_mean and moving_variance
            # for batch normalization when trainig,
            # run update operation before train operation
            # update operation is placed in tf.GraphKeys.UPDATE_OPS
            #========================================================================#
            with tf.control_dependencies(tf.get_collection(tf.GraphKeys.UPDATE_OPS)):

                self.generator_train_op = self.generator_optimizer.minimize(
                    loss=self.generator_loss,
                    var_list=self.generator_variables,
                    global_step=self.generator_global_step
                )

                self.discriminator_train_op = self.discriminator_optimizer.minimize(
                    loss=self.discriminator_loss,
                    var_list=self.discriminator_variables,
                    global_step=self.discriminator_global_step
                )

            self.saver = tf.train.Saver()

            self.summary = tf.summary.merge([
                tf.summary.image("reals", self.reals, max_outputs=10),
                tf.summary.image("fakes", self.fakes, max_outputs=10),
                tf.summary.scalar("generator_loss", self.generator_loss),
                tf.summary.scalar("discriminator_loss", self.discriminator_loss),
                tf.summary.scalar("gradient_penalty", self.gradient_penalty),
            ])

    # call this when train model untrained or still training
    # in this case, model can restore variables from checkpoint.
    def initialize(self):

        session = tf.get_default_session()

        checkpoint = tf.train.latest_checkpoint(self.name)

        if checkpoint:
            self.saver.restore(session, checkpoint)
            print(checkpoint, "loaded")

        else:
            global_variables = tf.global_variables(scope=self.name)
            session.run(tf.variables_initializer(global_variables))
            print("global variables in {} initialized".format(self.name))

    # call this when train model using pre-trained model
    # in this case, initialize only uninitialized variables
    def reinitialize(self):

        session = tf.get_default_session()

        uninitialized_variables = [
            variable for variable in tf.global_variables(self.name)
            if not session.run(tf.is_variable_initialized(variable))
        ]

        session.run(tf.variables_initializer(uninitialized_variables))
        print("uninitialized variables in {} initialized".format(self.name))

    def train(self, filenames, num_epochs, batch_size, buffer_size):

        session = tf.get_default_session()
        writer = tf.summary.FileWriter(self.name, session.graph)

        print("training started")

        start = time.time()

        self.dataset.initialize(
            filenames=filenames,
            num_epochs=num_epochs,
            batch_size=batch_size,
            buffer_size=buffer_size
        )

        feed_dict = {
            self.batch_size: batch_size,
            self.training: True
        }

        ### [CAUTION] ###
        # variables in pre-trained model depends placeholders that doesn't exist in this instance.
        # so, search those placeholders in graph, and feed values to them.
        latents_placeholder_names = [
            "{}:0".format(operation.name)
            for operation in tf.get_default_graph().get_operations()
            if "latents" in operation.name
        ]

        training_placeholder_names = [
            "{}:0".format(operation.name)
            for operation in tf.get_default_graph().get_operations()
            if "training" in operation.name
        ]

        latents_placeholders = [
            tf.get_default_graph().get_tensor_by_name(latents_placeholder_name)
            for latents_placeholder_name in latents_placeholder_names
        ]

        training_placeholders = [
            tf.get_default_graph().get_tensor_by_name(training_placeholder_name)
            for training_placeholder_name in training_placeholder_names
        ]

        for i in itertools.count():

            try:
                reals, latents = session.run(
                    [self.next_reals, self.next_latents],
                    feed_dict=feed_dict
                )

            except tf.errors.OutOfRangeError:
                print("training ended")
                break

            else:
                if reals.shape[0] != batch_size:
                    break

            feed_dict.update({
                self.reals: reals,
                self.latents: latents
            })

            feed_dict.update({
                latents_placeholder: latents
                for latents_placeholder in latents_placeholders
            })

            feed_dict.update({
                training_placeholder: True
                for training_placeholder in training_placeholders
            })

            session.run(
                [self.generator_train_op, self.discriminator_train_op],
                feed_dict=feed_dict
            )

            if i % 100 == 0:

                generator_global_step, generator_loss = session.run(
                    [self.generator_global_step, self.generator_loss],
                    feed_dict=feed_dict
                )
                print("global_step: {}, generator_loss: {:.2f}".format(
                    generator_global_step,
                    generator_loss
                ))

                discriminator_global_step, discriminator_loss = session.run(
                    [self.discriminator_global_step, self.discriminator_loss],
                    feed_dict=feed_dict
                )
                print("global_step: {}, discriminator_loss: {:.2f}".format(
                    discriminator_global_step,
                    discriminator_loss
                ))

                summary = session.run(self.summary, feed_dict=feed_dict)
                writer.add_summary(summary, global_step=generator_global_step)

                if i % 100000 == 0:

                    checkpoint = self.saver.save(
                        sess=session,
                        save_path=os.path.join(self.name, "model.ckpt"),
                        global_step=generator_global_step
                    )

                    stop = time.time()
                    print("{} saved ({:.2f} sec)".format(checkpoint, stop - start))
                    start = time.time()

    def generate(self, batch_size):

        session = tf.get_default_session()

        latents = session.run(self.next_latents, feed_dict={self.batch_size: batch_size})
        fakes = session.run(self.fakes, feed_dict={self.latents: latents, self.training: False})

        for i, fake in enumerate(fakes):

            fake = cv2.cvtColor(fake, cv2.COLOR_RGB2BGR)
            cv2.imwrite("generated/fake_{}.png".format(i), fake * 255.0)
