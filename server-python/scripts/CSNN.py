# Author: Acer Zhang
# Datetime:2020/1/29 21:00
# Copyright belongs to the author.
# Please indicate the source for reprinting.

# Attention Scoring Neural Networks

import numpy as np
import paddle.fluid.layers as layers
from ERNIE.ERNIE_Tiny import ErnieModel, ErnieConfig

ignore_loss_max = 0.15


def _gt_score_loss(out_score, target_loss):
    out_score = np.array(out_score)
    target_loss = np.array(target_loss)
    cost = np.square(out_score - target_loss)
    cost[cost < np.square(ignore_loss_max)] = 0.
    return cost


def _backward_gt_score(out_score, target_score, loss, d_higher):
    out_score = np.array(out_score)
    target_score = np.array(target_score)
    d_higher = np.array(d_higher)
    d_out = 2 * (out_score - target_score)
    d_out[abs(d_out) < ignore_loss_max * 2] = 0.
    return d_higher * d_out, 0


def kea_layer(ipt_a, ipt_b):
    def input_layers(ipt):
        emb = layers.embedding(ipt, [50006, 1024], is_sparse=True)
        tmp_f = layers.fc(emb, 300)
        tmp_b = layers.fc(emb, 300)
        tmp_f = layers.dynamic_gru(tmp_f, 100)
        tmp_b = layers.dynamic_gru(tmp_b, 100, is_reverse=True)
        tmp = layers.fc([tmp_b, tmp_f], 300)
        tmp = layers.fc(tmp, 128)
        tmp = layers.sequence_pool(tmp, "max")
        return tmp

    def conv_layers(ipt):
        emb = layers.embedding(ipt, [50006, 1024], is_sparse=True)
        tmp_f = layers.sequence_conv(emb, 32, act="relu")
        tmp_f = layers.sequence_conv(tmp_f, 64, act="relu")
        tmp_f = layers.sequence_conv(tmp_f, 128, act="relu")
        tmp_f = layers.sequence_conv(tmp_f, 256, act="relu")
        tmp_f = layers.sequence_conv(tmp_f, 512, act="relu")
        tmp = layers.fc(tmp_f, 300)
        tmp = layers.fc(tmp, 128)
        tmp = layers.sequence_pool(tmp, "max")
        return tmp

    ra_a = input_layers(ipt_a)
    ra_b = input_layers(ipt_b)
    rb_a = conv_layers(ipt_a)
    rb_b = conv_layers(ipt_b)
    sim_a = layers.fc([ra_a, ra_b], 32)
    sim_b = layers.fc([rb_a, rb_b], 32)
    out = layers.fc([sim_a, sim_b], 11, act="softmax")
    return out


def keb_layer(ipt_a, ipt_b):
    def tmp_layers(ipt):
        tmp = layers.fc(ipt, 512)
        tmp = layers.fc(tmp, 256)
        return tmp

    conv_a = tmp_layers(ipt_a)
    conv_b = tmp_layers(ipt_b)
    div = layers.cos_sim(conv_b, conv_a)
    out = layers.fc(div, 1)
    return out


class CSNN:
    conf_path = None

    def __init__(self):
        self.layers_out = None

    def define_network(self, l_src_ids, l_position_ids, l_sentence_ids, l_input_mask,
                       r_src_ids, r_position_ids, r_sentence_ids, r_input_mask,
                       ori_sentence, sentence):
        # conf = ErnieConfig(self.conf_path)
        # l_model = ErnieModel(l_src_ids,
        #                      l_position_ids,
        #                      l_sentence_ids,
        #                      task_ids=None,
        #                      input_mask=l_input_mask,
        #                      config=conf)
        # l_pool_feature = l_model.get_pooled_output()
        # r_model = ErnieModel(r_src_ids,
        #                      r_position_ids,
        #                      r_sentence_ids,
        #                      task_ids=None,
        #                      input_mask=r_input_mask,
        #                      config=conf)
        # r_pool_feature = r_model.get_pooled_output()

        word_feature = kea_layer(ori_sentence, sentence)
        # sentence_sim = keb_layer(l_pool_feature, r_pool_feature)
        # out = layers.elementwise_mul(word_feature, sentence_sim, 1)
        # self.layers_out = layers.fc(out, 1, name="csnn_out")
        self.layers_out = word_feature
        layers_out = layers.argmax(self.layers_out, axis=1)
        return layers_out

    def req_cost(self, program, score):
        # loss = program.current_block().create_var(name="cosnn_loss_tmp", dtype="float32", shape=[1])
        # layers.py_func(func=_gt_score_loss,
        #                x=[self.layers_out, score],
        #                out=loss,
        #                backward_func=_backward_gt_score)
        # loss = layers.smooth_l1(self.layers_out, score)
        loss = layers.cross_entropy(self.layers_out, score)
        return layers.mean(loss)

# debug
# import paddle.fluid as fluid
# data = fluid.data(name="test1", shape=[-1, 128, 1], dtype="int64")
# data2 = fluid.data(name="test2", shape=[-1, 128, 1], dtype="float32")
# s = fluid.data(name="test3", shape=[1], dtype="float32")
# net = CSNN()
# net.conf_path = r"D:\a13\server-python/ERNIE/ernie_tiny_config.json"
# a = net.define_network(data, data, data, data2, data, data, data, data2)
