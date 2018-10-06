#=================================================================================================#
# Implementation of Progressive Growing GAN
#
# 2018/10/01 Hiroki Sakuma
# (https://github.com/skmhrk1209/GAN)
#
# original papers
# [Are GANs Created Equal? A Large-Scale Study]
# (https://arxiv.org/pdf/1711.10337.pdf)
# [The GAN Landscape: Losses, Architectures, Regularization, and Normalization]
# (https://arxiv.org/pdf/1807.04720.pdf)
#=================================================================================================#

import tensorflow as tf
import argparse
from models import gan
from networks import dcgan, resnet
from data import celeba
from utils import attr_dict

parser = argparse.ArgumentParser()
parser.add_argument("--model_dir", type=str, default="celeba_dcgan_model", help="model directory")
parser.add_argument('--filenames', type=str, nargs="+", default=["celeba.tfrecord"], help="tfrecord filenames")
parser.add_argument("--num_epochs", type=int, default=100, help="number of training epochs")
parser.add_argument("--batch_size", type=int, default=64, help="batch size")
parser.add_argument("--buffer_size", type=int, default=100000, help="buffer size to shuffle dataset")
parser.add_argument('--data_format', type=str, choices=["channels_first", "channels_last"], default="channels_last", help="data_format")
parser.add_argument('--train', action="store_true", help="training mode")
parser.add_argument('--generate', action="store_true", help="generation mode")
parser.add_argument('--gpu', type=str, default="0", help="gpu id")
args = parser.parse_args()

tf.logging.set_verbosity(tf.logging.INFO)

gan_models = [
    gan.Model(
        dataset=celeba.Dataset(
            image_size=[64, 64],
            data_format=args.data_format
        ),
        generator=dcgan.Generator(
            min_resolution=4,
            max_resolution=64,
            min_filters=32,
            max_filters=512,
            data_format=args.data_format,
        ),
        discriminator=dcgan.Discriminator(
            min_resolution=4,
            max_resolution=64,
            min_filters=32,
            max_filters=512,
            data_format=args.data_format
        ),
        loss_function=gan.Model.LossFunction.NS_GAN,
        gradient_penalty=gan.Model.GradientPenalty.ONE_CENTERED,
        hyper_parameters=attr_dict.AttrDict(
            latent_size=128,
            gradient_coefficient=1.0,
            learning_rate=0.0002,
            beta1=0.5,
            beta2=0.999
        ),
        name=args.model_dir
    ),
    gan.Model(
        dataset=celeba.Dataset(
            image_size=[128, 128],
            data_format=args.data_format
        ),
        generator=dcgan.Generator(
            min_resolution=4,
            max_resolution=128,
            min_filters=16,
            max_filters=512,
            data_format=args.data_format,
        ),
        discriminator=dcgan.Discriminator(
            min_resolution=4,
            max_resolution=128,
            min_filters=16,
            max_filters=512,
            data_format=args.data_format
        ),
        loss_function=gan.Model.LossFunction.NS_GAN,
        gradient_penalty=gan.Model.GradientPenalty.ONE_CENTERED,
        hyper_parameters=attr_dict.AttrDict(
            latent_size=128,
            gradient_coefficient=1.0,
            learning_rate=0.0002,
            beta1=0.5,
            beta2=0.999
        ),
        name=args.model_dir,
        reuse=tf.AUTO_REUSE
    ),
]

config = tf.ConfigProto(
    gpu_options=tf.GPUOptions(
        visible_device_list=args.gpu,
        allow_growth=True
    ),
    log_device_placement=False,
    allow_soft_placement=True
)

with tf.Session(config=config) as session:

    for gan_model in gan_models[:1]:

        gan_model.initialize()
        
        if args.train:

            gan_model.train(
                filenames=args.filenames,
                num_epochs=args.num_epochs,
                batch_size=args.batch_size,
                buffer_size=args.buffer_size
            )

        if args.generate:

            gan_model.generate(
                batch_size=args.batch_size
            )
        
    for gan_model in gan_models[1:]:

        gan_model.reinitialize()

        if args.train:

            gan_model.train(
                filenames=args.filenames,
                num_epochs=args.num_epochs,
                batch_size=args.batch_size,
                buffer_size=args.buffer_size
            )

        if args.generate:

            gan_model.generate(
                batch_size=args.batch_size
            )
