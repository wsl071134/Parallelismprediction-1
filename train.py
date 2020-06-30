

import tools
import random
import math
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn import metrics
import dnn_model as dm
# import data_prepare as dp
import data_util as wd
import os
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s')
logger = logging.getLogger('main')


def loop_dataset(model, params, g_list, sess, batch_size=50, train=True):

    total_loss = []
    total_iters = math.ceil(len(g_list) / batch_size)
    total_labels = []
    total_predicts = []
    if train:
        random.shuffle(g_list)
    for pos in range(total_iters):
        batch_graphs = g_list[pos * batch_size: (pos + 1) * batch_size]

        ajacent, features, batch_label, dgree_inv, graph_indexes = wd.batching(batch_graphs, params)
        total_labels += batch_label

        feed_dict = {
            model.ajacent: ajacent,
            model.features: features,
            model.labels: batch_label,
            model.dgree_inv: dgree_inv,
            model.graph_indexes: graph_indexes,
        }

        if train:
            feed_dict[model.keep_prob] = params.keep_prob
            feed_dict[model.learning_rate] = params.learning_rate
            to_run = [model.predicts, model.loss, model.accuracy, model.optimizer]
            predicts, loss, acc, _ = sess.run(to_run, feed_dict=feed_dict)
        else:
            feed_dict[model.keep_prob] = 1
            to_run = [model.predicts, model.loss, model.accuracy]
            predicts, loss, acc = sess.run(to_run, feed_dict=feed_dict)

        total_predicts.extend(predicts)

        total_loss.append(np.array([loss, acc]) * len(batch_graphs))

    total_loss = np.array(total_loss)
    avg_loss = np.sum(total_loss, 0) / len(g_list)

    total_labels = np.argmax(total_labels, 1)
    fpr, tpr, _ = metrics.roc_curve(total_labels, total_predicts, pos_label=1)
    auc = metrics.auc(fpr, tpr)
    loss_acc_auc = np.concatenate((avg_loss, [auc]))
    return loss_acc_auc



params = tools.Parameters()
params.set("k", 0.9)
params.set("conv1d_channels", [16, 32])
params.set("conv1d_kernel_size", [0, 5])
params.set("dense_dim", 128)
params.set("gcnn_dims", [32, 32, 32, 1])
params.set("learning_rate", 0.0001)
params.set("keep_prob", 1)
epoch_num = 100
batch_size = 1
print(epoch_num, batch_size)

train_set, test_set, param = wd.load_data('data/parallel_NPB/1','data/parallel_NPB/2')
logger.info(f"训练数据量 {len(train_set)}，测试数据量 {len(test_set)}")
params.extend(param)
print(params)

if params.k <= 1:
    num_nodes_list = sorted([g.num_nodes for g in train_set + test_set])
    params.k = num_nodes_list[int(math.ceil(params.k * len(num_nodes_list))) - 1]
    params.k = max(10, params.k)
    print('k used in SortPooling is: ' + str(params.k))

# loss_fun='cross_entropy'
loss_fun_list = ['cross_entropy', 'bi_logistic']


def train(loss_fun,i):
    model = dm.DGCNN(params)
    model.build(i)
    best_acc = 0

    fig_loss1 = np.zeros([epoch_num])
    fig_loss2 = np.zeros([epoch_num])
    fig_acc1 = np.zeros([epoch_num])
    fig_acc2 = np.zeros([epoch_num])

    '''设置模型保存器'''
    m_saver = tf.train.Saver()

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        summary_writer = tf.summary.FileWriter('./log', sess.graph)

        # train
        for i in range(epoch_num):
            loss, acc, auc = loop_dataset(model, params, train_set, sess, batch_size)
            logger.info(f"train epoch {i:<3}/{epoch_num:<3} -- loss-{loss:<9.6} -- acc-{acc:<9.6} -- auc-{auc:<9.6}")
            fig_loss1[i] = loss
            fig_acc1[i] = acc
            # test
            loss, acc, auc = loop_dataset(model, params, test_set, sess, train=False)
            logger.info(f"TEST {'>' * 14} -- loss-{loss:<9.6} -- acc-{acc:<9.6} -- auc-{auc:<9.6}")
            fig_loss2[i] = loss
            fig_acc2[i] = acc
            if acc > best_acc:
                best_acc = acc

    print(best_acc)



train('sigmoid',1)