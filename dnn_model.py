
import tensorflow as tf
import tools
import numpy as np
import logging
from loss_pkg import loss as mylos

logger = logging.getLogger('main.dnn_model')


class DGCNN:
    def __init__(self, hyper_params=None):

        tf.reset_default_graph()
        if hyper_params and not isinstance(hyper_params, tools.Parameters):
            raise Exception(f'hyper_params must be an object of {type(tools.Parameters)} --- by LIC')


        default_params = {
            'gcnn_dims': (32, 32, 32, 1)
        }
        hyper_params.default(default_params)
        self.hypers = hyper_params

    def weight_matrix(self, shape, name=None):
        """
        权值矩阵及初始化
        Glorot & Bengio (AISTATS 2010) init.
        """
        init_range = np.sqrt(6.0 / (shape[0] + shape[1]))
        initial = tf.random_uniform(shape, minval=-init_range, maxval=init_range, dtype=tf.float32)
        return tf.Variable(initial, name=name)

    def set_public(self):
        '''
        placeholder 参数
        '''
        with tf.name_scope("place_hoders"):
            self.learning_rate = tf.placeholder_with_default(0.01, shape=(), name='learning_rate')
            self.keep_prob = tf.placeholder_with_default(1.0, shape=(), name='keep_prob')
            self.l2reg = tf.placeholder_with_default(0.0, shape=(), name='L2reg')
            self.ajacent = tf.sparse_placeholder(tf.float32, name="batch_adjacent")
            self.features = tf.placeholder(tf.float32, (None, self.hypers.feature_dim),
                                           name="batch_node_features")
            self.dgree_inv = tf.sparse_placeholder(tf.float32, name="batch_degree_inv")
            self.graph_indexes = tf.placeholder(tf.int32, (None, 2), name="batch_indecis")
            self.labels = tf.placeholder(tf.float32, [None, self.hypers.class_num], name='labels')

    def gcnn_layer(self, input_Z, in_dim, out_dim, layer_id):
        """
        一个DGCNN层
        """
        with tf.name_scope(f"gcnn_layer_{layer_id}"):
            W = self.weight_matrix(shape=(in_dim, out_dim), name=f"dgcnn_W_{layer_id}")
            AZ = tf.sparse_tensor_dense_matmul(self.ajacent, input_Z)
            AZ = tf.add(AZ, input_Z)
            AZW = tf.matmul(AZ, W)
            DAZW = tf.sparse_tensor_dense_matmul(self.dgree_inv, AZW)

        return tf.nn.tanh(DAZW)

    def gcnn_layers(self):
        """
        多个gcnn层
        """
        with tf.name_scope("gcnn_layers"):
            Z1_h = []
            in_dim = self.hypers.feature_dim
            Z = self.features
            for i, dim in enumerate(self.hypers.gcnn_dims):
                out_dim = dim
                Z = self.gcnn_layer(Z, in_dim, out_dim, i)
                in_dim = out_dim
                Z1_h.append(Z)
            Z1_h = tf.concat(Z1_h, 1)
        return Z1_h

    def sortpooling_layer(self, gcnn_out):
        def sort_a_graph(index_span):
            indices = tf.range(index_span[0], index_span[1])
            graph_feature = tf.gather(gcnn_out, indices)

            graph_size = index_span[1] - index_span[0]
            k = tf.cond(self.hypers.k > graph_size, lambda: graph_size, lambda: self.hypers.k)

            top_k = tf.gather(graph_feature, tf.nn.top_k(graph_feature[:, -1], k=k).indices)


            zeros = tf.zeros([self.hypers.k - k, sum(self.hypers.gcnn_dims)], dtype=tf.float32)
            top_k = tf.concat([top_k, zeros], 0)
            return top_k

        with tf.name_scope("sort_pooling_layer"):
            sort_pooling = tf.map_fn(sort_a_graph, self.graph_indexes, dtype=tf.float32)
        return sort_pooling

    def cnn1d_layers(self, inputs):
        """
        两个1维cnn层
        """
        with tf.name_scope("cnn1d_layers"):
            total_dim = sum(self.hypers.gcnn_dims)
            graph_embeddings = tf.reshape(inputs, [-1, self.hypers.k * total_dim, 1])  # (batch, width, channel)


            if self.hypers.conv1d_kernel_size[0] == 0:
                self.hypers.conv1d_kernel_size[0] = total_dim
            cnn1 = tf.layers.conv1d(graph_embeddings,
                                    self.hypers.conv1d_channels[0],
                                    self.hypers.conv1d_kernel_size[0],
                                    self.hypers.conv1d_kernel_size[0])
            act1 = tf.nn.relu(cnn1)
            pooling1 = tf.layers.max_pooling1d(act1, 2, 2)


            cnn2 = tf.layers.conv1d(pooling1, self.hypers.conv1d_channels[1], self.hypers.conv1d_kernel_size[1], 1)
            act2 = tf.nn.relu(cnn2)

        return act2

    def fc_layer(self, inputs):

        with tf.name_scope("fc_layer"):
            # for batch data reshape
            batchsize = tf.shape(self.graph_indexes)[0]
            graph_embed_dim = int((self.hypers.k - 2) / 2 + 1)
            graph_embed_dim = (graph_embed_dim - self.hypers.conv1d_kernel_size[1] + 1) * self.hypers.conv1d_channels[1]
            # reshape batch data
            cnn1d_embed = tf.reshape(inputs, [batchsize, graph_embed_dim])
            outputs = tf.layers.dense(cnn1d_embed, self.hypers.dense_dim, activation=tf.nn.relu)
        return outputs

    def output_layer(self, inputs):

        with tf.name_scope("output_layer"):
            drop_out = tf.nn.dropout(inputs, keep_prob=self.keep_prob)  # dropout

            outputs = tf.layers.dense(drop_out, self.hypers.class_num, activation=None)
        return outputs

    def set_loss(self):

        with tf.name_scope("loss_scope"):
            self.loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits_v2(
                logits=self.logits, labels=self.labels))
    def set_google_loss(self):

        with tf.name_scope("loss_scope"):
            self.loss = tf.reduce_mean(mylos.bi_tempered_logistic_loss(self.logits, self.labels, 0.5, 1.5))

    def set_accuracy(self):

        with tf.name_scope("accuracy_scope"):
            correct_pred = tf.equal(tf.argmax(self.logits, axis=1), tf.argmax(self.labels, axis=1))
            self.accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))  # ---GLOBAL---准确率

    def set_optimizer(self):

        with tf.name_scope("optimizer"):
            # self.optimizer = tf.train.AdadeltaOptimizer(self.learning_rate).minimize(self.loss)
            self.optimizer = tf.train.AdamOptimizer(self.learning_rate).minimize(self.loss)
            # self.optimizer = tf.train.AdagradOptimizer(self.learning_rate).minimize(self.loss)
            # self.optimizer = tf.train.MomentumOptimizer(self.learning_rate, 0.9).minimize(self.loss)
            # self.optimizer = tf.train.GradientDescentOptimizer(self.learning_rate).minimize(self.loss)
            # self.optimizer = tf.train.RMSPropOptimizer(self.learning_rate).minimize(self.loss)

    def build(self,loss_id):

        self.set_public()
        gcnns_outputs = self.gcnn_layers()
        emmbed = self.sortpooling_layer(gcnns_outputs)
        cnn_1d = self.cnn1d_layers(emmbed)
        fc = self.fc_layer(cnn_1d)
        output = self.output_layer(fc)
        self.logits = output
        self.predicts = tf.argmax(output, 1)
        if loss_id==0:
            self.set_loss()
        else:
            self.set_google_loss()
        self.set_accuracy()
        self.set_optimizer()


# code for debugging
if __name__ == '__main__':
    param = tools.Parameters()
    param.set("feature_dim", 3)
    param.set("k", 10)  # 不能小于conv1d_kernel_size[1]*2，否则没法做第2个1d卷积
    param.set("class_num", 3)
    param.set("conv1d_channels", [16, 32])
    param.set("conv1d_kernel_size", [0, 5])
    param.set("dense_dim", 128)
    param.set("gcnn_dims", [32, 32, 32, 1])

    model = DGCNN(param)
    model.build()

    indices = np.array([[0, 1],
                        [1, 0],
                        [1, 2],
                        [2, 1],
                        [3, 4],
                        [3, 6],
                        [4, 3],
                        [4, 5],
                        [5, 4],
                        [6, 3],
                        ],
                       dtype=np.int64)
    values = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1, 1], dtype=np.float32)
    shape = np.array([7, 7], dtype=np.int64)

    A_sparse = tf.SparseTensorValue(indices, values, shape)

    feature = np.array([[0.1, 0.2, 0.3], [0.3, 0.2, 0.1], [0.2, 0.1, 0.3],
                        [0.1, 0.2, 0.3], [0.3, 0.2, 0.1], [0.2, 0.1, 0.3],
                        [0.2, 0.1, 0.3]])

    indices = np.array([[0, 0], [1, 1], [2, 2], [3, 3], [4, 4], [5, 5], [6, 6]], dtype=np.int64)
    values = np.array([1, 0.5, 1, 0.5, 0.5, 1, 1], dtype=np.float32)
    shape = np.array([7, 7], dtype=np.int64)
    D_inv_sparse = tf.SparseTensorValue(indices, values, shape)

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())

        summary_writer = tf.summary.FileWriter('./log', sess.graph)

        r = sess.run([model.logits, model.predicts], feed_dict={
            model.ajacent: A_sparse,
            model.features: feature,
            model.dgree_inv: D_inv_sparse,
            model.graph_indexes: [[0, 3], [3, 7]]
        })
        print(r)
