"""当前号码预览的返回值适配；无旧PoC采集入口。"""

import json

def _bool_result(value, name):
    """PyGenUtil 会去掉 bool return：成功只返回 OutError，失败返回 None。"""
    if value != "":
        raise RuntimeError("{} 失败或反射结构不符: {!r}".format(name, value))

def _capture_result(value):
    """bool + int64& + FString& 在 Python 中为 (frame,error) 或 None。"""
    if not isinstance(value, tuple) or len(value) != 2:
        raise RuntimeError("MANUAL_REQUIRED: capture 失败或反射返回结构不符: {!r}".format(value))
    frame, error = value
    if type(frame) is not int or frame < 0 or error != "":
        raise RuntimeError("capture 返回无效帧或错误: {!r}".format(value))
    return frame

def _result(value, name):
    """新反射 API 的预期返回对象和 OutError；结构不符时立即停止。"""
    if not isinstance(value, tuple) or len(value) != 2:
        raise RuntimeError("MANUAL_REQUIRED: {} 反射返回结构未验证: {!r}".format(name, value))
    result, error = value
    if not result or error:
        raise RuntimeError("{}: {}".format(name, error))
    return result
