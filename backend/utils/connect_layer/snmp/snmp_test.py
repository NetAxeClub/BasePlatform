# -*- coding: utf-8 -*-
"""
SNMP协议探测工具
支持pysnmp 7.x (异步API) 和 4.x-6.x (同步API)
"""
import logging
import asyncio
from typing import Tuple, Optional, Any

logger = logging.getLogger(__name__)

PYSNMP_AVAILABLE = False
_pysnmp_error = None
_pysnmp_version = None  # '7.x' 或 '4.x-6.x'

# 尝试导入pysnmp 7.x版本（异步API）
try:
    from pysnmp.hlapi.v1arch.asyncio import (
        get_cmd,
        CommunityData,
        UdpTransportTarget,
        ObjectType,
        ObjectIdentity,
        SnmpDispatcher,
    )
    from pysnmp.hlapi.v3arch.asyncio.auth import UsmUserData
    from pysnmp.hlapi.v3arch.asyncio import get_cmd as get_cmd_v3

    PYSNMP_AVAILABLE = True
    _pysnmp_version = "7.x"
    logger.debug("使用pysnmp 7.x (异步API)版本")
except ImportError as e1:
    # # 如果7.x导入失败，尝试旧版本pysnmp (4.x-6.x) - 同步API
    # try:
    #     from pysnmp.hlapi import (
    #         getCmd as get_cmd,
    #         SnmpEngine,
    #         CommunityData,
    #         UsmUserData,
    #         UdpTransportTarget,
    #         ContextData,
    #         ObjectType,
    #         ObjectIdentity,
    #     )
    #
    #     PYSNMP_AVAILABLE = True
    #     _pysnmp_version = "4.x-6.x"
    #     logger.debug("使用pysnmp 4.x-6.x (同步API)版本")
    # except ImportError as e2:
    #     _pysnmp_error = f"v1arch/v3arch导入失败: {e1}; 标准导入失败: {e2}"
    PYSNMP_AVAILABLE = False
    logger.warning(f"pysnmp库导入失败: {_pysnmp_error}")
# except Exception as e:
#     _pysnmp_error = str(e)
#     PYSNMP_AVAILABLE = False
#     logger.warning(f"pysnmp库导入异常: {_pysnmp_error}")


def probe_snmp(
    ip: str,
    snmp_version: str,
    snmp_community: str,
    port: int = 161,
    timeout: int = 5,
    retries: int = 1,
    auth_key: Optional[str] = None,
    priv_key: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    探测指定IP的SNMP协议是否正常

    Args:
        ip: 目标设备IP地址
        snmp_version: SNMP版本，支持 'v2c' 或 'v3'
        snmp_community: SNMP团体字（v2c）或用户名（v3）
        port: SNMP端口，默认161
        timeout: 超时时间（秒），默认5秒
        retries: 重试次数，默认1次
        auth_key: SNMP v3认证密钥（仅v3需要，可选）
        priv_key: SNMP v3加密密钥（仅v3需要，可选）

    Returns:
        Tuple[bool, Optional[str]]: (是否成功, system_name或错误信息)
        - 成功: (True, system_name) - system_name为设备的系统名称
        - 失败: (False, 错误描述)

    Examples:
        >>> # v2c示例
        >>> success, error = probe_snmp('192.168.1.1', 'v2c', 'public')
        >>> if success:
        >>>     print("SNMP连接正常")
        >>> else:
        >>>     print(f"SNMP连接失败: {error}")

        >>> # v3示例（noAuthNoPriv模式）
        >>> success, error = probe_snmp('192.168.1.1', 'v3', 'username')

        >>> # v3示例（authNoPriv模式）
        >>> success, error = probe_snmp('192.168.1.1', 'v3', 'username', auth_key='authpass')

        >>> # v3示例（authPriv模式）
        >>> success, error = probe_snmp('192.168.1.1', 'v3', 'username',
        >>>                             auth_key='authpass', priv_key='privpass')
    """
    if not PYSNMP_AVAILABLE:
        error_msg = "pysnmp库未安装或导入失败"
        if _pysnmp_error:
            error_msg += f": {_pysnmp_error}"
        error_msg += "。请检查: 1) pip install pysnmp 2) pip install --upgrade pyasn1"
        return False, error_msg

    if not ip:
        return False, "IP地址不能为空"

    snmp_version_lower = snmp_version.lower()
    if snmp_version_lower not in ["v2c", "v3"]:
        return False, f"不支持的SNMP版本: {snmp_version}，仅支持 'v2c' 或 'v3'"

    if not snmp_community:
        return False, "SNMP团体字/用户名不能为空"

    # 如果是v3版本，使用专门的v3探测函数
    if snmp_version_lower == "v3":
        return probe_snmp_v3(
            ip=ip,
            username=snmp_community,
            auth_key=auth_key,
            priv_key=priv_key,
            port=port,
            timeout=timeout,
            retries=retries,
        )

    return _probe_snmp_v2c_async(ip, snmp_community, port, timeout, retries)


def _probe_snmp_v2c_async(
    ip: str, snmp_community: str, port: int, timeout: int, retries: int
) -> Tuple[bool, Optional[str]]:
    """使用pysnmp 7.x异步API探测SNMP v2c"""
    try:

        async def _async_probe():
            dispatcher = SnmpDispatcher()
            auth_data = CommunityData(snmp_community, mpModel=1)
            transport = await UdpTransportTarget.create((ip, port))

            error_indication, error_status, error_index, var_binds = await get_cmd(
                dispatcher,
                auth_data,
                transport,
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.5.0")),  # sysName OID
            )
            return error_indication, error_status, error_index, var_binds

        # 运行异步函数
        error_indication, error_status, error_index, var_binds = asyncio.run(
            _async_probe()
        )

        if error_indication:
            return False, f"SNMP错误: {error_indication}"

        if error_status:
            return False, f"SNMP错误状态: {error_status.prettyPrint()}"

        # 从var_binds中提取system name
        # var_binds格式: ((ObjectType(ObjectIdentity(...), OctetString('system_name')),),)
        # var_binds[0]是元组，包含ObjectType: (ObjectType,)
        # var_binds[0][0]是ObjectType对象
        # var_binds[0][0][1]是值部分
        system_name = None
        if var_binds and len(var_binds) > 0:
            try:
                # var_binds[0]是元组，包含ObjectType
                obj_type = (
                    var_binds[0][0] if isinstance(var_binds[0], tuple) else var_binds[0]
                )
                # ObjectType[1]是值部分
                if hasattr(obj_type, "__getitem__"):
                    value_obj = obj_type[1]
                    system_name = str(value_obj) if value_obj else None
            except (IndexError, TypeError, AttributeError) as e:
                logger.warning(f"提取system name失败: {e}")
                system_name = None

        return True, system_name

    except Exception as e:
        logger.exception(f"SNMP v2c探测异常: IP={ip}")
        return False, f"连接异常: {str(e)}"


def probe_snmp_v3(
    ip: str,
    username: str,
    auth_key: Optional[str] = None,
    priv_key: Optional[str] = None,
    auth_protocol: str = "usmHMACMD5AuthProtocol",
    priv_protocol: str = "usmDESPrivProtocol",
    port: int = 161,
    timeout: int = 5,
    retries: int = 1,
) -> Tuple[bool, Optional[str]]:
    """
    探测SNMP v3协议（完整版本，支持认证和加密）

    Args:
        ip: 目标设备IP地址
        username: SNMP v3用户名
        auth_key: 认证密钥（可选，如果为None则使用noAuthNoPriv模式）
        priv_key: 加密密钥（可选，如果为None则使用noAuthNoPriv或authNoPriv模式）
        auth_protocol: 认证协议，默认'usmHMACMD5AuthProtocol'
                      可选: 'usmHMACMD5AuthProtocol', 'usmHMACSHAAuthProtocol'
        priv_protocol: 加密协议，默认'usmDESPrivProtocol'
                      可选: 'usmDESPrivProtocol', 'usm3DESEDEPrivProtocol', 'usmAesCfb128Protocol'
        port: SNMP端口，默认161
        timeout: 超时时间（秒），默认5秒
        retries: 重试次数，默认1次

    Returns:
        Tuple[bool, Optional[str]]: (是否成功, system_name或错误信息)
        - 成功: (True, system_name) - system_name为设备的系统名称
        - 失败: (False, 错误描述)
    """
    if not PYSNMP_AVAILABLE:
        error_msg = "pysnmp库未安装或导入失败"
        if _pysnmp_error:
            error_msg += f": {_pysnmp_error}"
        error_msg += "。请检查: 1) pip install pysnmp 2) pip install --upgrade pyasn1"
        return False, error_msg

    if _pysnmp_version == "7.x":
        return _probe_snmp_v3_async(
            ip,
            username,
            auth_key,
            priv_key,
            auth_protocol,
            priv_protocol,
            port,
            timeout,
            retries,
        )
    else:
        return _probe_snmp_v3_sync(
            ip,
            username,
            auth_key,
            priv_key,
            auth_protocol,
            priv_protocol,
            port,
            timeout,
            retries,
        )


def _probe_snmp_v3_async(
    ip: str,
    username: str,
    auth_key: Optional[str],
    priv_key: Optional[str],
    auth_protocol: str,
    priv_protocol: str,
    port: int,
    timeout: int,
    retries: int,
) -> Tuple[bool, Optional[str]]:
    """使用pysnmp 7.x异步API探测SNMP v3"""
    try:
        from pysnmp.hlapi.v3arch.asyncio.auth import (
            usmHMACMD5AuthProtocol,
            usmHMACSHAAuthProtocol,
            usmDESPrivProtocol,
            usm3DESEDEPrivProtocol,
            usmAesCfb128Protocol,
        )
        from pysnmp.hlapi.v3arch.asyncio.dispatch import (
            SnmpDispatcher as SnmpDispatcherV3,
        )

        auth_protocol_map = {
            "usmHMACMD5AuthProtocol": usmHMACMD5AuthProtocol,
            "usmHMACSHAAuthProtocol": usmHMACSHAAuthProtocol,
        }

        priv_protocol_map = {
            "usmDESPrivProtocol": usmDESPrivProtocol,
            "usm3DESEDEPrivProtocol": usm3DESEDEPrivProtocol,
            "usmAesCfb128Protocol": usmAesCfb128Protocol,
        }

        async def _async_probe():
            dispatcher = SnmpDispatcherV3()

            # 构建认证数据
            if auth_key and priv_key:
                auth_proto = auth_protocol_map.get(
                    auth_protocol, usmHMACMD5AuthProtocol
                )
                priv_proto = priv_protocol_map.get(priv_protocol, usmDESPrivProtocol)
                auth_data = UsmUserData(
                    username,
                    authKey=auth_key,
                    privKey=priv_key,
                    authProtocol=auth_proto(),
                    privProtocol=priv_proto(),
                )
            elif auth_key:
                auth_proto = auth_protocol_map.get(
                    auth_protocol, usmHMACMD5AuthProtocol
                )
                auth_data = UsmUserData(
                    username, authKey=auth_key, authProtocol=auth_proto()
                )
            else:
                auth_data = UsmUserData(username)

            transport = await UdpTransportTarget.create((ip, port))

            error_indication, error_status, error_index, var_binds = await get_cmd_v3(
                dispatcher,
                auth_data,
                transport,
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.5.0")),  # sysName OID
            )
            return error_indication, error_status, error_index, var_binds

        error_indication, error_status, error_index, var_binds = asyncio.run(
            _async_probe()
        )

        if error_indication:
            return False, f"SNMP错误: {error_indication}"

        if error_status:
            return False, f"SNMP错误状态: {error_status.prettyPrint()}"

        # 从var_binds中提取system name
        # var_binds格式: ((ObjectType(ObjectIdentity(...), OctetString('system_name')),),)
        # var_binds[0]是元组，包含ObjectType: (ObjectType,)
        # var_binds[0][0]是ObjectType对象
        # var_binds[0][0][1]是值部分
        system_name = None
        if var_binds and len(var_binds) > 0:
            try:
                # var_binds[0]是元组，包含ObjectType
                obj_type = (
                    var_binds[0][0] if isinstance(var_binds[0], tuple) else var_binds[0]
                )
                # ObjectType[1]是值部分
                if hasattr(obj_type, "__getitem__"):
                    value_obj = obj_type[1]
                    system_name = str(value_obj) if value_obj else None
            except (IndexError, TypeError, AttributeError) as e:
                logger.warning(f"提取system name失败: {e}")
                system_name = None

        return True, system_name

    except Exception as e:
        logger.exception(f"SNMP v3探测异常: IP={ip}, Username={username}")
        return False, f"连接异常: {str(e)}"


def snmp_get_oid(
    ip: str,
    snmp_version: str,
    snmp_community: str,
    oid: str,
    port: int = 161,
    timeout: int = 5,
    retries: int = 1,
    auth_key: Optional[str] = None,
    priv_key: Optional[str] = None,
) -> Tuple[bool, Any]:
    """
    查询指定 OID 的 SNMP 值

    Args:
        ip: 目标设备IP地址
        snmp_version: SNMP版本，支持 'v2c' 或 'v3'
        snmp_community: SNMP团体字（v2c）或用户名（v3）
        oid: 要查询的 OID，如 '1.3.6.1.2.1.1.1.0'
        port: SNMP端口，默认161
        timeout: 超时时间（秒），默认5秒
        retries: 重试次数，默认1次
        auth_key: SNMP v3认证密钥（仅v3需要，可选）
        priv_key: SNMP v3加密密钥（仅v3需要，可选）

    Returns:
        Tuple[bool, Any]: (是否成功, 值或错误信息)
    """
    if not PYSNMP_AVAILABLE:
        error_msg = "pysnmp库未安装或导入失败"
        if _pysnmp_error:
            error_msg += f": {_pysnmp_error}"
        return False, error_msg

    if not ip:
        return False, "IP地址不能为空"

    if not oid:
        return False, "OID不能为空"

    snmp_version_lower = snmp_version.lower()
    if snmp_version_lower not in ["v2c", "v3"]:
        return False, f"不支持的SNMP版本: {snmp_version}"

    if not snmp_community:
        return False, "SNMP团体字/用户名不能为空"

    return _snmp_get_oid_async(
        ip, snmp_version_lower, snmp_community, oid, port, timeout, retries,
        auth_key, priv_key
    )


def _snmp_get_oid_async(
    ip: str,
    snmp_version: str,
    snmp_community: str,
    oid: str,
    port: int,
    timeout: int,
    retries: int,
    auth_key: Optional[str],
    priv_key: Optional[str],
) -> Tuple[bool, Any]:
    """使用 pysnmp 7.x 异步 API 查询指定 OID 的值"""
    try:
        async def _async_get():
            if snmp_version == "v2c":
                dispatcher = SnmpDispatcher()
                auth_data = CommunityData(snmp_community, mpModel=1)
                get_cmd_func = get_cmd
            else:
                from pysnmp.hlapi.v3arch.asyncio.dispatch import (
                    SnmpDispatcher as SnmpDispatcherV3,
                )

                dispatcher = SnmpDispatcherV3()
                if auth_key and priv_key:
                    auth_data = UsmUserData(
                        snmp_community,
                        authKey=auth_key,
                        privKey=priv_key,
                    )
                elif auth_key:
                    auth_data = UsmUserData(snmp_community, authKey=auth_key)
                else:
                    auth_data = UsmUserData(snmp_community)
                get_cmd_func = get_cmd_v3

            transport = await UdpTransportTarget.create((ip, port))
            error_indication, error_status, error_index, var_binds = await get_cmd_func(
                dispatcher,
                auth_data,
                transport,
                ObjectType(ObjectIdentity(oid)),
            )
            return error_indication, error_status, error_index, var_binds

        error_indication, error_status, error_index, var_binds = asyncio.run(_async_get())

        if error_indication:
            return False, f"SNMP错误: {error_indication}"
        if error_status:
            return False, f"SNMP错误状态: {error_status.prettyPrint()}"

        value = None
        if var_binds and len(var_binds) > 0:
            try:
                obj_type = (
                    var_binds[0][0] if isinstance(var_binds[0], tuple) else var_binds[0]
                )
                if hasattr(obj_type, "__getitem__"):
                    value_obj = obj_type[1]
                    value = str(value_obj) if value_obj is not None else None
            except (IndexError, TypeError, AttributeError) as e:
                logger.warning(f"提取OID值失败: {e}")

        return True, value

    except Exception as e:
        logger.exception(f"SNMP GET OID异常: IP={ip}, OID={oid}")
        return False, f"连接异常: {str(e)}"


def _probe_snmp_v3_sync(
    ip: str,
    username: str,
    auth_key: Optional[str],
    priv_key: Optional[str],
    auth_protocol: str,
    priv_protocol: str,
    port: int,
    timeout: int,
    retries: int,
) -> Tuple[bool, Optional[str]]:
    """使用pysnmp 4.x-6.x同步API探测SNMP v3"""
    try:
        from pysnmp.hlapi import (
            usmHMACMD5AuthProtocol,
            usmHMACSHAAuthProtocol,
            usmDESPrivProtocol,
            usm3DESEDEPrivProtocol,
            usmAesCfb128Protocol,
        )

        auth_protocol_map = {
            "usmHMACMD5AuthProtocol": usmHMACMD5AuthProtocol,
            "usmHMACSHAAuthProtocol": usmHMACSHAAuthProtocol,
        }

        priv_protocol_map = {
            "usmDESPrivProtocol": usmDESPrivProtocol,
            "usm3DESEDEPrivProtocol": usm3DESEDEPrivProtocol,
            "usmAesCfb128Protocol": usmAesCfb128Protocol,
        }

        transport = UdpTransportTarget((ip, port), timeout=timeout, retries=retries)

        # 构建认证数据
        if auth_key and priv_key:
            auth_proto = auth_protocol_map.get(auth_protocol, usmHMACMD5AuthProtocol)
            priv_proto = priv_protocol_map.get(priv_protocol, usmDESPrivProtocol)
            auth_data = UsmUserData(
                username,
                authKey=auth_key,
                privKey=priv_key,
                authProtocol=auth_proto(),
                privProtocol=priv_proto(),
            )
        elif auth_key:
            auth_proto = auth_protocol_map.get(auth_protocol, usmHMACMD5AuthProtocol)
            auth_data = UsmUserData(
                username, authKey=auth_key, authProtocol=auth_proto()
            )
        else:
            auth_data = UsmUserData(username)

        error_indication, error_status, error_index, var_binds = next(
            get_cmd(
                SnmpEngine(),
                auth_data,
                transport,
                ContextData(),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0")),
            )
        )

        if error_indication:
            return False, f"SNMP错误: {error_indication}"

        if error_status:
            return False, f"SNMP错误状态: {error_status.prettyPrint()}"

        return True, None

    except Exception as e:
        logger.exception(f"SNMP v3探测异常: IP={ip}, Username={username}")
        return False, f"连接异常: {str(e)}"
