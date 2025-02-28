# Copyright (C) 2018-2023 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import pytest
from common.mo_convert_test_class import CommonMOConvertTest

import openvino.runtime as ov
from openvino.runtime import PartialShape, Model

def make_pd_dynamic_graph_model():
    import paddle
    paddle.disable_static()
    class NeuralNetwork(paddle.nn.Layer):
        def __init__(self):
            super(NeuralNetwork, self).__init__()
            self.relu_sigmoid_stack = paddle.nn.Sequential(
                paddle.nn.ReLU(),
                paddle.nn.Sigmoid())
        def forward(self, input):
            return self.relu_sigmoid_stack(input)
    return NeuralNetwork()

def make_pd_static_graph_model(shape):
    import paddle
    import paddle.nn

    paddle.enable_static()

    x = paddle.static.data(name="x", shape=shape)
    y = paddle.static.data(name="y", shape=shape)
    relu = paddle.nn.ReLU()
    sigmoid = paddle.nn.Sigmoid()
    y = sigmoid(relu(x))
    
    exe = paddle.static.Executor(paddle.CPUPlace())
    exe.run(paddle.static.default_startup_program())
    return exe, x, y


def make_pd_hapi_graph_model(shape):
    import paddle
    paddle.disable_static()
    from paddle.static import InputSpec
    net = paddle.nn.Sequential(
        paddle.nn.ReLU(),
        paddle.nn.Sigmoid())
    input = InputSpec(shape, 'float32', 'x')
    label = InputSpec(shape, 'float32', 'label')
    
    model = paddle.Model(net, input, label)
    optim = paddle.optimizer.SGD(learning_rate=1e-3,
        parameters=model.parameters())
    model.prepare(optim, paddle.nn.CrossEntropyLoss(), paddle.metric.Accuracy())
    return model


def make_ref_graph_model(shape, dtype=np.float32):
    shape = PartialShape(shape)
    param = ov.opset8.parameter(shape, name="x", dtype=dtype)

    relu = ov.opset8.relu(param)
    sigm = ov.opset8.sigmoid(relu)

    model = Model([sigm], [param], "test")
    return model

def create_paddle_dynamic_module(tmp_dir):
    import paddle
    shape = [2,3,4]
    pd_model = make_pd_dynamic_graph_model()
    ref_model = make_ref_graph_model(shape)

    x = paddle.static.InputSpec(shape=shape, dtype='float32', name='x')
    return pd_model, ref_model, {"example_input": [x]}

def create_paddle_static_module(tmp_dir):
    shape = [2,3,4]
    pd_model, x, y = make_pd_static_graph_model(shape)
    ref_model = make_ref_graph_model(shape)

    return pd_model, ref_model, {"example_input": [x], "output": [y]}

def create_paddle_hapi_module(tmp_dir):
    shape = [2,3,4]
    pd_model = make_pd_hapi_graph_model(shape)
    ref_model = make_ref_graph_model(shape)

    return pd_model, ref_model, {}

class TestMoConvertPaddle(CommonMOConvertTest):
    test_data = [
        create_paddle_dynamic_module,
        create_paddle_static_module,
        create_paddle_hapi_module
    ]
    test_ids = ["Test{}".format(id) for id in range(len(test_data))]
    
    @pytest.mark.skip(reason="Paddlepaddle has incompatible protobuf. Ticket: 95904")
    @pytest.mark.parametrize("create_model", test_data, ids=test_ids)
    def test_mo_import_from_memory_paddle_fe(self, create_model, ie_device, precision, ir_version,
                                             temp_dir):
        fw_model, graph_ref, mo_params = create_model(temp_dir)
        test_params = {'input_model': fw_model}
        if mo_params is not None:
            test_params.update(mo_params)
        self._test_by_ref_graph(temp_dir, test_params, graph_ref, compare_tensor_names=False)


class TestPaddleConversionParams(CommonMOConvertTest):
    paddle_is_imported = False
    try:
        import paddle
        paddle_is_imported = True
    except ImportError:
        pass

    test_data = [
        {'params_test': {'input': {'tensor_shape':[2, 3, 4]}},
         'fw_model': make_pd_hapi_graph_model([1, 2]),
         'ref_model': make_ref_graph_model([2, 3, 4])},
        {'params_test': {'input': {'tensor_shape':[5,6]}},
         'fw_model': make_pd_hapi_graph_model([1, 2, 3]),
         'ref_model': make_ref_graph_model([5, 6])},
        {'params_test': {'input': {'tensor_shape':[4,2,7], 'dtype': paddle.int32 }},
         'fw_model': make_pd_hapi_graph_model([2, 3]),
         'ref_model': make_ref_graph_model([4, 2, 7], np.int32)},
    ] if paddle_is_imported else []


    test_ids = ["Test{}".format(id) for id in range(len(test_data))]
    @pytest.mark.parametrize("params", test_data,ids=test_ids)
    @pytest.mark.nightly
    def test_conversion_params(self, params, ie_device, precision, ir_version,
                                 temp_dir, use_legacy_frontend):
        
        fw_model = params['fw_model']
        ref_model = params['ref_model']        
        if 'dtype' in params['params_test']['input'].keys():
            test_params={'input' : (self.paddle.to_tensor(np.random.rand(*params['params_test']['input']['tensor_shape'])).shape, params['params_test']['input']['dtype'])}
        else:
            test_params={'input' : self.paddle.to_tensor(np.random.rand(*params['params_test']['input']['tensor_shape'])).shape}
                
        test_params.update({'input_model': fw_model})
        self._test_by_ref_graph(temp_dir, test_params, ref_model, compare_tensor_names=False)
