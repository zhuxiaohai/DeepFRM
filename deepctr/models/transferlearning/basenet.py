# -*- coding:utf-8 -*-
"""
Author:
    Xiaohai Zhu
"""
from itertools import chain
import tensorflow as tf

from deepctr.feature_column import build_input_features, get_linear_logit, DEFAULT_GROUP_NAME, input_from_feature_columns
from deepctr.layers.core import PredictionLayer, ModifiedPredictionLayer, DNN
from deepctr.layers.interaction import FM
from deepctr.layers.utils import concat_func, add_func, combined_dnn_input
from deepctr.models.multitask_modified.multitaskbase import MultiTaskModelBase


def SimpleDNN(dnn_feature_columns, tasks, num_outdim=1, dnn_hidden_units=(128, 128), dnn_use_bn=False,
              l2_reg_embedding=1e-5, l2_reg_dnn=0, dnn_dropout=0, dnn_activation='relu', seed=1024):
    """Instantiates the Multi-gate Mixture-of-Experts architecture.

    :param dnn_feature_columns: An iterable containing all the features used by deep part of the model.
    :param tasks: dict, indicating the loss of each tasks, ``"binary"`` for  binary logloss, ``"regression"``
    for regression loss. e.g. {'task1': 'binary', 'task2': 'regression'}
    :param dnn_hidden_units: list,list of positive integer or empty list, the layer number and units in each layer
    of shared-bottom DNN
    :param dnn_use_bn: bool
    :param l2_reg_embedding: float. L2 regularizer strength applied to embedding vector
    :param l2_reg_dnn: float. L2 regularizer strength applied to DNN
    :param seed: integer ,to use as random seed.
    :param dnn_dropout: float in [0,1), the probability we will drop out a given DNN coordinate.
    :param dnn_activation: Activation function to use in DNN

    :return: If use_uncertainty is False, return a Keras model instance, otherwise,
    return a tuple (prediction_model, train_model).
    train_model should be compiled and fit data first, and then prediction_model is used for prediction.
    """
    features = build_input_features(dnn_feature_columns)

    inputs_list = list(features.values())

    sparse_embedding_list, dense_value_list = input_from_feature_columns(features, dnn_feature_columns,
                                                                         l2_reg_embedding, seed)
    dnn_input = combined_dnn_input(sparse_embedding_list, dense_value_list)
    dnn_outs = DNN(dnn_hidden_units, dnn_activation, l2_reg_dnn, dnn_dropout,
                   dnn_use_bn, seed=seed, name='bottom_shared_dnn')(dnn_input)
    dnn_outs = [dnn_outs]
    task_outputs = {}
    for dnn_out, task_name, task_type in zip(dnn_outs, tasks.keys(), tasks.values()):
        logit = tf.keras.layers.Dense(
            num_outdim, use_bias=False, activation=None)(dnn_out)
        output = ModifiedPredictionLayer(task_type, name=task_name, multiclass_num=num_outdim)(logit)
        task_outputs[task_name] = output
    model = MultiTaskModelBase(inputs=inputs_list, outputs=task_outputs)
    return model


def DeepFM(linear_feature_columns, dnn_feature_columns, fm_group=[DEFAULT_GROUP_NAME], dnn_hidden_units=(128, 128),
           l2_reg_linear=0.00001, l2_reg_embedding=0.00001, l2_reg_dnn=0, seed=1024, dnn_dropout=0,
           dnn_activation='relu', dnn_use_bn=False, tasks={'fpd4': 'binary'}):
    """Instantiates the DeepFM Network architecture.

    :param linear_feature_columns: An iterable containing all the features used by linear part of the model.
    :param dnn_feature_columns: An iterable containing all the features used by deep part of the model.
    :param fm_group: list, group_name of features that will be used to do feature interactions.
    :param dnn_hidden_units: list,list of positive integer or empty list, the layer number and units in each layer of DNN
    :param l2_reg_linear: float. L2 regularizer strength applied to linear part
    :param l2_reg_embedding: float. L2 regularizer strength applied to embedding vector
    :param l2_reg_dnn: float. L2 regularizer strength applied to DNN
    :param seed: integer ,to use as random seed.
    :param dnn_dropout: float in [0,1), the probability we will drop out a given DNN coordinate.
    :param dnn_activation: Activation function to use in DNN
    :param dnn_use_bn: bool. Whether use BatchNormalization before activation or not in DNN
    :param task: str, ``"binary"`` for  binary logloss or  ``"regression"`` for regression loss
    :return: A Keras model instance.
    """

    features = build_input_features(
        linear_feature_columns + dnn_feature_columns)

    inputs_list = list(features.values())

    linear_logit = get_linear_logit(features, linear_feature_columns, seed=seed, prefix='linear',
                                    l2_reg=l2_reg_linear)

    group_embedding_dict, dense_value_list = input_from_feature_columns(features, dnn_feature_columns, l2_reg_embedding,
                                                                        seed, support_group=True)

    fm_logit = add_func([FM()(concat_func(v, axis=1))
                         for k, v in group_embedding_dict.items() if k in fm_group])

    dnn_input = combined_dnn_input(list(chain.from_iterable(
        group_embedding_dict.values())), dense_value_list)
    dnn_output = DNN(dnn_hidden_units, dnn_activation, l2_reg_dnn, dnn_dropout, dnn_use_bn, seed=seed,
                     name='bottom_shared_dnn')(dnn_input)
    dnn_logit = tf.keras.layers.Dense(
        1, use_bias=False, kernel_initializer=tf.keras.initializers.glorot_normal(seed=seed))(dnn_output)

    final_logit = add_func([linear_logit, fm_logit, dnn_logit])

    outputs = {}
    for task_name, task_type in tasks.items():
        outputs[task_name] = PredictionLayer(task_type, name=task_name)(final_logit)
    model = MultiTaskModelBase(inputs=inputs_list, outputs=outputs)
    return model


def DeepFM_modified(linear_feature_columns, dnn_feature_columns, fm_group=[DEFAULT_GROUP_NAME], dnn_hidden_units=(128, 128),
           l2_reg_linear=0.00001, l2_reg_embedding=0.00001, l2_reg_dnn=0, seed=1024, dnn_dropout=0,
           dnn_activation='relu', dnn_use_bn=False, task='binary'):
    """Instantiates the DeepFM Network architecture.

    :param linear_feature_columns: An iterable containing all the features used by linear part of the model.
    :param dnn_feature_columns: An iterable containing all the features used by deep part of the model.
    :param fm_group: list, group_name of features that will be used to do feature interactions.
    :param dnn_hidden_units: list,list of positive integer or empty list, the layer number and units in each layer of DNN
    :param l2_reg_linear: float. L2 regularizer strength applied to linear part
    :param l2_reg_embedding: float. L2 regularizer strength applied to embedding vector
    :param l2_reg_dnn: float. L2 regularizer strength applied to DNN
    :param seed: integer ,to use as random seed.
    :param dnn_dropout: float in [0,1), the probability we will drop out a given DNN coordinate.
    :param dnn_activation: Activation function to use in DNN
    :param dnn_use_bn: bool. Whether use BatchNormalization before activation or not in DNN
    :param task: str, ``"binary"`` for  binary logloss or  ``"regression"`` for regression loss
    :return: A Keras model instance.
    """

    features = build_input_features(
        linear_feature_columns + dnn_feature_columns)

    inputs_list = list(features.values())

    linear_logit = get_linear_logit(features, linear_feature_columns, seed=seed, prefix='linear',
                                    l2_reg=l2_reg_linear)

    group_embedding_dict, dense_value_list = input_from_feature_columns(features, dnn_feature_columns, l2_reg_embedding,
                                                                        seed, support_group=True)

    fm_logit = add_func([FM()(concat_func(v, axis=1))
                         for k, v in group_embedding_dict.items() if k in fm_group])

    dnn_input = combined_dnn_input(list(chain.from_iterable(
        group_embedding_dict.values())), dense_value_list)
    dnn_output = DNN(dnn_hidden_units, dnn_activation, l2_reg_dnn, dnn_dropout, dnn_use_bn, seed=seed,
                     name='bottom_shared_dnn')(dnn_input)
    dnn_logit = tf.keras.layers.Dense(1,
                                      use_bias=False,
                                      kernel_initializer=tf.keras.initializers.glorot_normal(seed=seed))(dnn_output)

    final_logit = add_func([linear_logit, fm_logit, dnn_logit])

    output = PredictionLayer(task)(final_logit)
    model = tf.keras.models.Model(inputs=inputs_list, outputs=output)
    return model


def DeepFM_VAE2(linear_feature_columns, dnn_feature_columns, fm_group=[DEFAULT_GROUP_NAME], dnn_hidden_units=(128, 128),
           l2_reg_linear=0.00001, l2_reg_embedding=0.00001, l2_reg_dnn=0, seed=1024, dnn_dropout=0,
           dnn_activation='relu', dnn_use_bn=False, task='binary'):
    """Instantiates the DeepFM Network architecture.

    :param linear_feature_columns: An iterable containing all the features used by linear part of the model.
    :param dnn_feature_columns: An iterable containing all the features used by deep part of the model.
    :param fm_group: list, group_name of features that will be used to do feature interactions.
    :param dnn_hidden_units: list,list of positive integer or empty list, the layer number and units in each layer of DNN
    :param l2_reg_linear: float. L2 regularizer strength applied to linear part
    :param l2_reg_embedding: float. L2 regularizer strength applied to embedding vector
    :param l2_reg_dnn: float. L2 regularizer strength applied to DNN
    :param seed: integer ,to use as random seed.
    :param dnn_dropout: float in [0,1), the probability we will drop out a given DNN coordinate.
    :param dnn_activation: Activation function to use in DNN
    :param dnn_use_bn: bool. Whether use BatchNormalization before activation or not in DNN
    :param task: str, ``"binary"`` for  binary logloss or  ``"regression"`` for regression loss
    :return: A Keras model instance.
    """

    features = build_input_features(
        linear_feature_columns + dnn_feature_columns)

    inputs_list = list(features.values())

    linear_logit = get_linear_logit(features, linear_feature_columns,
                                    seed=seed,
                                    prefix='linear',
                                    l2_reg=l2_reg_linear)

    group_embedding_dict, dense_value_list = input_from_feature_columns(features, dnn_feature_columns, l2_reg_embedding,
                                                                        seed, support_group=True)

    fm_logit = add_func([FM()(concat_func(v, axis=1))
                         for k, v in group_embedding_dict.items() if k in fm_group])

    dnn_input = combined_dnn_input(list(chain.from_iterable(
        group_embedding_dict.values())), dense_value_list)

    dnn_input = tf.keras.layers.BatchNormalization(name='real_input')(dnn_input)

    z_mean, z_log_var, z = VAEEncoder(dnn_hidden_units, dnn_activation, l2_reg_dnn, dnn_dropout, dnn_use_bn, seed,
                                      name='vae_encoder')(dnn_input)

    dnn_logit = tf.keras.layers.Dense(1,
                                      use_bias=False,
                                      kernel_initializer=tf.keras.initializers.glorot_normal(seed=seed))(z)

    final_logit = add_func([linear_logit, fm_logit, dnn_logit])

    output = PredictionLayer(task)(final_logit)

    model = tf.keras.models.Model(inputs=inputs_list, outputs=output)

    return model

