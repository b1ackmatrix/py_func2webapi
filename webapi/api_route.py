#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2017/5/5 下午3:29
# @Author  : Matrix
# @Site    : 
# @File    : api_route.py
# @Software: PyCharm
import json
import copy
import hashlib
from json import JSONDecodeError
from webapi.api_list import api_version
from inspect import signature, Parameter
from webapi.api_base import ApiBaseHandler
from webapi.api_error import ApiSysError, ApiBaseError

__author__ = 'matrix'


class WebApiRoute(ApiBaseHandler):

    def call_api_func(self):

        def is_float(num):
            try:
                float(num)
                return True
            except (TypeError, ValueError):
                return False

        # API专属关键字
        api_keyword = ('access_token', 'method', 'app_key', 'sign', 'timestamp', 'format', 'v')

        # 接口名称
        self._method = self.get_argument('method')
        # 接口版本
        self._v = self.get_argument('v')
        # 数据格式
        self._format = self.get_argument('format', 'json').lower()
        # access_token
        self._access_token = self.get_argument('access_token', None)
        # app_key
        self._app_key = self.get_argument('app_key', None)
        # 签名
        self._sign = self.get_argument('sign', None)
        # 时间戳
        self._timestamp = self.get_argument('timestamp', None)

        # 检查请求的格式
        if self._format not in ('json', 'xml'):
            raise ApiSysError.invalid_format

        # 检查版本号
        if not is_float(self._v):
            raise ApiSysError.invalid_version
        elif self._v not in api_version:
            raise ApiSysError.unsupported_version

        # hash方法名
        _hash_method = 'x_{hash_method}'.format(
            hash_method=hashlib.sha1(self._method.encode('utf-8')).hexdigest())

        # 检查方法名是否存在
        if not hasattr(api_version[self._v], _hash_method):
            raise ApiSysError.invalid_method
        # 检查方法是否停用
        elif not getattr(api_version[self._v], _hash_method).get('enable', True):
            raise ApiSysError.api_stop
        # 检查方法是否允许以某种请求方式调用
        elif self.request.method.lower() not in \
                getattr(api_version[self._v], _hash_method).get('method', ['get', 'post']):
            raise ApiSysError.not_allowed_request

        # 函数参数
        func_args = {}

        # 获取body
        body_data = self.request.body.decode()
        content_type = self.request.headers['Content-Type'].lower() if 'Content-Type' in self.request.headers else None
        if content_type == 'application/json' and body_data:
                body_json = json.loads(body_data)
        else:
            body_json = None

        # 获取函数对象
        method_func = getattr(api_version[self._v], _hash_method).get('func', None)
        # 检查函数对象是否有效
        if not method_func or not callable(method_func):
            raise ApiSysError.error_api_config
        # 获取函数签名
        func_signature = signature(method_func)
        # 接口函数如果存在Api关键字，则直接抛出异常，函数不符合规范
        for key in func_signature.parameters.keys():
            if key in api_keyword:
                raise ApiSysError.error_api_config

        # 使用Type Hints判断接口处理函数限制的参数类型
        def set_method_args(arg_key, arg_value, type_hints=None):
            _arg_value = copy.copy(arg_value)
            try:
                converter = {
                    'int': lambda: int(_arg_value) if isinstance(arg_value, str) else _arg_value,
                    'float': lambda:  float(_arg_value),
                    'str': lambda: str(_arg_value),
                    'list': lambda: json.loads(_arg_value) if isinstance(arg_value, str) else _arg_value,
                    'dict': lambda: json.loads(_arg_value) if isinstance(arg_value, str) else _arg_value,
                    'tuple': lambda: tuple(json.loads(_arg_value) if isinstance(arg_value, str) else _arg_value)
                }
                type_hints_name = type_hints.__name__.lower()
                if type_hints and type_hints != Parameter.empty and type_hints_name in converter:
                    _arg_value = converter[type_hints_name]()
                    if not isinstance(_arg_value, type_hints):
                        raise ValueError
            # JSONDecodeError是ValueError的子类
            # 如果不先做解析异常的判断，会显示参数类型错误，虽然看起来也没什么不对
            except JSONDecodeError:
                raise ApiSysError.invalid_json
            except ValueError:
                message = '{0}：{1} <{2}>'.format(ApiSysError.error_args_type.message, arg_key, type_hints.__name__)
                api_ex = ApiBaseError(
                    err_code=ApiSysError.error_args_type.err_code,
                    status_code=ApiSysError.error_args_type.status_code,
                    message=message)
                raise api_ex
            else:
                func_args[arg_key] = _arg_value

        # 检查函数参数
        for k, v in func_signature.parameters.items():
            # *args的函数参数
            if str(v.kind) == 'VAR_POSITIONAL' and isinstance(body_json, (list, tuple)):
                raise ApiSysError.error_api_config
            # 参数没有默认值的情况
            elif str(v.kind) in ('POSITIONAL_OR_KEYWORD', 'KEYWORD_ONLY') and v.default == Parameter.empty:
                if self.request.method == 'POST' \
                            and body_json \
                            and hasattr(body_json, 'keys') \
                            and k in body_json.keys():
                    set_method_args(k, body_json.get(k), v.annotation)
                else:
                    set_method_args(k, self.get_argument(k), v.annotation)
            # 参数有默认值的情况
            elif str(v.kind) in ('POSITIONAL_OR_KEYWORD', 'KEYWORD_ONLY'):
                if self.request.method == 'POST' \
                        and body_json \
                        and hasattr(body_json, 'keys') \
                        and k in body_json.keys():
                    set_method_args(k, body_json.get(k, v.default), v.annotation)
                else:
                    set_method_args(k,  self.get_argument(k, v.default), v.annotation)
            # **kwargs的情况
            elif str(v.kind) == 'VAR_KEYWORD':
                # 检查body里的json，如果有多余的参数，则传给函数
                if self.request.method == 'POST' \
                        and content_type == 'application/json' \
                        and body_json \
                        and hasattr(body_json, 'items'):
                    func_args.update({k: v for k, v in body_json.items()
                                      if k not in api_keyword
                                      and k not in func_signature.parameters.keys()})
                # 再次检查 arguments里，如果有多余的参数，则传给函数
                func_args.update({k: self.get_argument(k) for k in self.request.arguments.keys()
                                  if k not in api_keyword
                                  and k not in func_signature.parameters.keys()})

        return method_func(**func_args)

    def get(self):
        self.format_retinfo()

    def post(self):
        self.format_retinfo()


if __name__ == '__main__':
    pass

