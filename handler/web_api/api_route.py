#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2017/5/5 下午3:29
# @Author  : Matrix
# @Site    : 
# @File    : api_route.py
# @Software: PyCharm
import json
import inspect
from webapi.api_list import api_version
from json import JSONDecodeError
from ..base import ApiBaseHandler
from webapi.api_retinfo import api_retinfo
from tornado.web import MissingArgumentError
from webapi.api_error import ApiBaseError, ApiSysError

__author__ = 'matrix'


class WebApiRoute(ApiBaseHandler):

    @api_retinfo
    def func(self):

        def is_float(num):
            try:
                float(num)
                return True
            except (TypeError, ValueError):
                return False

        # API专属关键字
        api_keyword = ('access_token', 'method', 'app_key', 'sign', 'timestamp', 'response_format', 'v', 'client_id')

        # access_token
        _access_token = self.get_argument('access_token', None)
        # 接口名称
        _method = self.get_argument('method', None)
        # app_key
        _app_key = self.get_argument('app_key', None)
        # 签名
        _sign = self.get_argument('sign', None)
        # 时间戳
        _timestamp = self.get_argument('timestamp', None)
        # 数据格式
        _response_format = self.get_argument('response_format', 'json')
        # 接口版本
        _v = self.get_argument('v', None)
        # client_id
        _client_id = self.get_argument('client_id', None)

        # 检查版本号
        if not _v:
            raise ApiSysError.missing_version
        elif not is_float(_v):
            raise ApiSysError.invalid_version
        elif _v not in api_version:
            raise ApiSysError.unsupported_version

        # 检查方法名
        if not _method:
            raise ApiSysError.missing_method
        elif _method not in api_version[_v].api_methods:
            raise ApiSysError.invalid_method
        elif not api_version[_v].api_methods[_method].get('enable', True):
            raise ApiSysError.api_stop
        elif self.request.method.lower() not in \
                api_version[_v].api_methods[_method].get('method', ['get', 'post']):
            raise ApiSysError.not_allowed_request

        # 函数参数
        func_args = {}

        # 获取body
        body_data = self.request.body.decode()
        content_type = self.request.headers['Content-Type'].lower() if 'Content-Type' in self.request.headers else None
        if body_data and content_type == 'application/json':
            try:
                body_json = json.loads(body_data)
            except JSONDecodeError:
                raise ApiSysError.invalid_json
        else:
            body_json = None

        # 获取函数对象
        method_func = api_version[_v].api_methods[_method]['func']
        # 检查函数对象是否有效
        if not method_func or not callable(method_func):
            raise ApiSysError.error_api_config
        # 获取函数签名
        func_signature = inspect.signature(method_func)
        # 接口函数如果存在Api关键字，则直接抛出异常，函数不符合规范
        for key in func_signature.parameters.keys():
            if key in api_keyword:
                raise ApiSysError.error_api_config

        # 检查函数参数
        for k, v in func_signature.parameters.items():
            try:
                # *args的函数参数
                if str(v.kind) == 'VAR_POSITIONAL' and isinstance(body_json, (list, tuple)):
                    raise ApiSysError.error_api_config
                # 参数没有默认值的情况
                elif str(v.kind) in ('POSITIONAL_OR_KEYWORD', 'KEYWORD_ONLY') \
                        and hasattr(v.default, '__name__') \
                        and v.default.__name__ == '_empty':
                    if self.request.method == 'POST' \
                                and body_json \
                                and hasattr(body_json, 'keys') \
                                and k in body_json.keys():
                            func_args[k] = body_json.get(k)
                    else:
                        func_args[k] = self.get_argument(k)
                # 参数有默认值的情况
                elif str(v.kind) in ('POSITIONAL_OR_KEYWORD', 'KEYWORD_ONLY'):
                    if self.request.method == 'POST' \
                            and body_json \
                            and hasattr(body_json, 'keys') \
                            and k in body_json.keys():
                        func_args[k] = body_json.setdefault(k, v.default)
                    else:
                        func_args[k] = self.get_argument(k, v.default)
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
                    func_args.update({k: v for k, v in self.request.arguments.items()
                                      if k not in api_keyword
                                      and k not in func_signature.parameters.keys()})
            except MissingArgumentError:
                ex = ApiBaseError(err_code=ApiSysError.missing_arguments.err_code,
                                  status_code=ApiSysError.missing_arguments.status_code,
                                  message='{message}:{key_name}'.format(
                                      message=ApiSysError.missing_arguments.message, key_name=v.name))
                raise ex
        return method_func(**func_args)

    def get(self):
        self.func()

    def post(self):
        self.func()

    def check_xsrf_cookie(self):
        pass


if __name__ == '__main__':
    pass

