# -*- coding: utf-8 -*-
"""
设备连接管理器
确保单设备采集时只建立一次连接，实现连接复用机制
支持 Netmiko、NETCONF、SNMP、RESTCONF、Telemetry 五种采集方式
"""
import logging
import os
import time
from typing import Optional, Dict, Any, List
from ncclient import manager
import requests
from requests.auth import HTTPBasicAuth
try:
    import grpc
except ImportError:
    grpc = None  # Telemetry 功能需要安装 grpcio

from utils.connect_layer.zetmiko import ConnectHandler as ZetmikoConnectHandler
from utils.connect_layer.NETCONF.netconf_connect import (
    H3CNetconf,
    HuaweiyangNetconfConnect,
    CiscoNetconfConnect,
)
from utils.connect_layer.snmp.snmp_test import snmp_get_oid
from apps.device_api.common import device_type_map

logger = logging.getLogger(__name__)


class DeviceConnectionManager:
    """设备连接管理器，确保单设备采集时只建立一次连接"""
    DEFAULT_NETMIKO_TIMEOUT = 5
    DEFAULT_NETMIKO_CONN_TIMEOUT = 10
    DEFAULT_NETMIKO_AUTH_TIMEOUT = 15
    DEFAULT_NETMIKO_BANNER_TIMEOUT = 20
    DEFAULT_NETMIKO_BLOCKING_TIMEOUT = 20
    DEFAULT_NETMIKO_SESSION_TIMEOUT = 20
    DEFAULT_NETCONF_TIMEOUT = 30
    DEFAULT_RESTCONF_TIMEOUT = 10
    DEFAULT_PROTOCOL_RETRIES = 1
    DEFAULT_RETRY_BACKOFF_SECONDS = 0.5

    def __init__(self, device_ip: str, device_info: Dict[str, Any]):
        """
        初始化连接管理器

        Args:
            device_ip: 设备IP地址
            device_info: 设备信息字典，包含账号信息等
        """
        self.device_ip = device_ip
        self.device_info = device_info
        self._netmiko_conn = None
        self._netconf_conn = None
        self._snmp_session = None
        self._restconf_session = None
        self._telemetry_channel = None

    def _read_connection_policy(self) -> Dict[str, Any]:
        policy = self.device_info.get("connection_policy", {})
        if not isinstance(policy, dict):
            return {}
        return policy

    def _get_protocol_host(self, protocol_name: str) -> str:
        if protocol_name == "netconf":
            return (
                self.device_info.get("netconf_manage_ip")
                or self.device_info.get("bind_ip__ipaddr")
                or self.device_ip
            )
        return self.device_ip

    def _get_retry_times(self, protocol_name: str, default: int = DEFAULT_PROTOCOL_RETRIES) -> int:
        policy = self._read_connection_policy()
        global_retry = policy.get("retry_times")
        protocol_retry = policy.get(f"{protocol_name}_retry_times")
        value = protocol_retry if protocol_retry is not None else global_retry
        if value is None:
            return default
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    def _get_timeout_seconds(self, protocol_name: str, default: int) -> int:
        policy = self._read_connection_policy()
        global_timeout = policy.get("timeout_seconds")
        protocol_timeout = policy.get(f"{protocol_name}_timeout_seconds")
        value = protocol_timeout if protocol_timeout is not None else global_timeout
        if value is None:
            return default
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    def _with_retry(self, protocol_name: str, operation_name: str, func, *args, **kwargs):
        retry_times = self._get_retry_times(protocol_name)
        attempts = retry_times + 1
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                logger.warning(
                    "%s 执行失败，准备重试: device=%s operation=%s attempt=%s/%s error=%s",
                    protocol_name.upper(),
                    self.device_ip,
                    operation_name,
                    attempt,
                    attempts,
                    exc,
                )
                time.sleep(self.DEFAULT_RETRY_BACKOFF_SECONDS)
        raise last_error

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，自动关闭所有连接"""
        try:
            if self._netmiko_conn:
                try:
                    self._netmiko_conn.disconnect()
                    logger.debug(f"Netmiko连接已关闭: {self.device_ip}")
                except Exception as e:
                    logger.warning(f"关闭Netmiko连接异常: {self.device_ip}, {str(e)}")

            if self._netconf_conn:
                try:
                    if hasattr(self._netconf_conn, "closed"):
                        self._netconf_conn.closed()
                    elif hasattr(self._netconf_conn, "close_session"):
                        self._netconf_conn.close_session()
                    logger.debug(f"NETCONF连接已关闭: {self.device_ip}")
                except Exception as e:
                    logger.warning(f"关闭NETCONF连接异常: {self.device_ip}, {str(e)}")

            if self._restconf_session:
                try:
                    self._restconf_session.close()
                    logger.debug(f"RESTCONF会话已关闭: {self.device_ip}")
                except Exception as e:
                    logger.warning(f"关闭RESTCONF会话异常: {self.device_ip}, {str(e)}")

            if self._telemetry_channel:
                try:
                    self._telemetry_channel.close()
                    logger.debug(f"Telemetry通道已关闭: {self.device_ip}")
                except Exception as e:
                    logger.warning(f"关闭Telemetry通道异常: {self.device_ip}, {str(e)}")

            # SNMP是无状态协议，无需关闭连接
            if self._snmp_session:
                logger.debug(f"SNMP会话已清理: {self.device_ip}")

        except Exception as e:
            logger.error(
                f"关闭连接时发生异常: {self.device_ip}, {str(e)}", exc_info=True
            )

        return False  # 不抑制异常

    def get_netmiko_connection(self):
        """获取Netmiko连接（懒加载，只建立一次）"""
        if self._netmiko_conn is None:
            try:
                account = self.device_info.get("ssh")
                access_protocol = "ssh"
                if not account:
                    account = self.device_info.get("telnet")
                    access_protocol = "telnet"
                if not account:
                    raise ValueError("SSH/Telnet账号信息不存在")

                vendor_alias = self.device_info.get("vendor__alias", "Huawei")
                device_type = device_type_map.get(vendor_alias, "huawei")
                if access_protocol == "telnet" and not device_type.endswith("_telnet"):
                    device_type = f"{device_type}_telnet"

                connection_kwargs = {
                    "device_type": device_type,
                    "host": self.device_ip,
                    "username": account.get("username"),
                    "password": account.get("password"),
                    "port": account.get("port", 22),
                    "timeout": self._get_timeout_seconds(
                        "netmiko", self.DEFAULT_NETMIKO_TIMEOUT
                    ),
                    "conn_timeout": self._get_timeout_seconds(
                        "netmiko_conn", self.DEFAULT_NETMIKO_CONN_TIMEOUT
                    ),
                    "auth_timeout": self._get_timeout_seconds(
                        "netmiko_auth", self.DEFAULT_NETMIKO_AUTH_TIMEOUT
                    ),
                    "banner_timeout": self._get_timeout_seconds(
                        "netmiko_banner", self.DEFAULT_NETMIKO_BANNER_TIMEOUT
                    ),
                    "blocking_timeout": self._get_timeout_seconds(
                        "netmiko_blocking", self.DEFAULT_NETMIKO_BLOCKING_TIMEOUT
                    ),
                    "session_timeout": self._get_timeout_seconds(
                        "netmiko_session", self.DEFAULT_NETMIKO_SESSION_TIMEOUT
                    ),
                }

                self._netmiko_conn = self._with_retry(
                    "netmiko",
                    "connect",
                    ZetmikoConnectHandler,
                    **connection_kwargs,
                )
                logger.info(
                    f"Netmiko连接已建立: {self.device_ip}, device_type={device_type}"
                )
            except Exception as e:
                logger.error(
                    f"建立Netmiko连接失败: {self.device_ip}, {str(e)}", exc_info=True
                )
                raise

        return self._netmiko_conn

    def get_netconf_connection(self):
        """获取NETCONF连接（懒加载，只建立一次）"""
        if self._netconf_conn is None:
            try:
                account = self.device_info.get("netconf")
                if not account:
                    raise ValueError("NETCONF账号信息不存在")
                netconf_host = self._get_protocol_host("netconf")

                vendor_alias = self.device_info.get("vendor__alias", "H3C")

                # 根据厂商选择对应的NETCONF连接类
                if vendor_alias == "H3C":
                    self._netconf_conn = H3CNetconf(
                        host=netconf_host,
                        user=account.get("username"),
                        password=account.get("password"),
                        port=account.get("port", 830),
                        device_params="h3c",
                        timeout=self._get_timeout_seconds("netconf", self.DEFAULT_NETCONF_TIMEOUT),
                    )
                elif vendor_alias == "Huawei":
                    self._netconf_conn = HuaweiyangNetconfConnect(
                        host=netconf_host,
                        user=account.get("username"),
                        password=account.get("password"),
                        port=account.get("port", 830),
                        timeout=self._get_timeout_seconds("netconf", self.DEFAULT_NETCONF_TIMEOUT),
                    )
                elif vendor_alias == "Cisco":
                    self._netconf_conn = CiscoNetconfConnect(
                        host=netconf_host,
                        user=account.get("username"),
                        password=account.get("password"),
                        port=account.get("port", 830),
                        timeout=self._get_timeout_seconds("netconf", self.DEFAULT_NETCONF_TIMEOUT),
                    )
                else:
                    # 默认使用 ncclient manager
                    device_params_map = {
                        "H3C": "h3c",
                        "Huawei": "huaweiyang",
                        "Cisco": "nexus",
                    }
                    device_params_name = device_params_map.get(vendor_alias, "h3c")
                    self._netconf_conn = manager.connect(
                        host=netconf_host,
                        username=account.get("username"),
                        password=account.get("password"),
                        port=account.get("port", 830),
                        hostkey_verify=False,
                        device_params={"name": device_params_name},
                        timeout=self._get_timeout_seconds("netconf", self.DEFAULT_NETCONF_TIMEOUT),
                    )

                logger.info(
                    "NETCONF连接已建立: 逻辑设备=%s, 目标地址=%s, vendor=%s",
                    self.device_ip,
                    netconf_host,
                    vendor_alias,
                )
            except Exception as e:
                logger.error(
                    f"建立NETCONF连接失败: {self.device_ip}, {str(e)}", exc_info=True
                )
                raise

        return self._netconf_conn

    def get_snmp_session(self) -> Dict[str, Any]:
        """获取SNMP会话配置（懒加载，只建立一次）"""
        if self._snmp_session is None:
            try:
                # 从设备信息中获取SNMP配置
                snmp_version = self.device_info.get("snmp_version", "v2c")
                snmp_community = self.device_info.get("snmp_community", "public")
                snmp_port = self.device_info.get("snmp_port", 161)

                # SNMP是无状态协议，这里只保存配置信息
                self._snmp_session = {
                    "ip": self.device_ip,
                    "version": snmp_version,
                    "community": snmp_community,
                    "port": snmp_port,
                    "timeout": self._get_timeout_seconds("snmp", 5),
                    "retries": self._get_retry_times("snmp"),
                }

                # 如果是v3，还需要保存认证信息
                if snmp_version == "v3":
                    self._snmp_session.update(
                        {
                            "username": self.device_info.get("snmp_username", ""),
                            "auth_key": self.device_info.get("snmp_auth_key"),
                            "priv_key": self.device_info.get("snmp_priv_key"),
                        }
                    )

                logger.info(
                    f"SNMP会话配置已创建: {self.device_ip}, version={snmp_version}"
                )
            except Exception as e:
                logger.error(
                    f"创建SNMP会话配置失败: {self.device_ip}, {str(e)}", exc_info=True
                )
                raise

        return self._snmp_session

    def get_restconf_session(self):
        """获取RESTCONF会话（懒加载，只建立一次）"""
        if self._restconf_session is None:
            try:
                # 从设备信息中获取RESTCONF配置
                restconf_config = self.device_info.get("restconf_config", {})
                base_url = (
                    f"https://{self.device_ip}:{restconf_config.get('port', 443)}"
                )

                self._restconf_session = requests.Session()
                self._restconf_session.base_url = base_url
                self._restconf_session.headers.update(
                    {
                        "Accept": "application/yang-data+json",
                        "Content-Type": "application/yang-data+json",
                    }
                )

                # 配置认证
                auth_type = restconf_config.get("auth_type", "basic")
                if auth_type == "basic":
                    self._restconf_session.auth = HTTPBasicAuth(
                        restconf_config.get("username", ""),
                        restconf_config.get("password", ""),
                    )
                elif auth_type == "token":
                    self._restconf_session.headers["Authorization"] = (
                        f"Bearer {restconf_config.get('token', '')}"
                    )

                # 配置SSL验证
                self._restconf_session.verify = restconf_config.get("verify_ssl", False)

                logger.info(
                    f"RESTCONF会话已创建: {self.device_ip}, base_url={base_url}"
                )
            except Exception as e:
                logger.error(
                    f"创建RESTCONF会话失败: {self.device_ip}, {str(e)}", exc_info=True
                )
                raise

        return self._restconf_session

    def get_telemetry_channel(self):
        """获取Telemetry gRPC通道（懒加载，只建立一次）"""
        if grpc is None:
            raise ImportError("使用 Telemetry 采集需安装 grpcio: pip install grpcio")
        if self._telemetry_channel is None:
            try:
                # 从设备信息中获取Telemetry配置
                telemetry_config = self.device_info.get("telemetry_config", {})
                port = telemetry_config.get("port", 50051)

                # 创建gRPC通道
                self._telemetry_channel = grpc.insecure_channel(
                    f"{self.device_ip}:{port}"
                )

                logger.info(f"Telemetry gRPC通道已创建: {self.device_ip}, port={port}")
            except Exception as e:
                logger.error(
                    f"创建Telemetry通道失败: {self.device_ip}, {str(e)}", exc_info=True
                )
                raise

        return self._telemetry_channel

    def execute_netmiko_command(
        self,
        command: str,
        use_textfsm: bool = True,
        textfsm_template: Optional[str] = None,
    ) -> Any:
        """
        执行Netmiko命令（本地模式下 TextFSM 解析入口）。

        TextFSM 解析由 netmiko 的 send_command(use_textfsm=True) 内部完成，会读取
        环境变量 NET_TEXTFSM 指向的目录下的 index 文件，按 (device_type, command) 匹配
        模板；若传入了 textfsm_template 则直接使用该模板文件。模板目录在 zetmiko 加载时
        通过 utils/connect_layer/zetmiko/__init__.py 设置。

        Args:
            command: 要执行的命令
            use_textfsm: 是否使用TextFSM解析
            textfsm_template: TextFSM模板路径（可选，如 hp_comware_display_arp.textfsm）

        Returns:
            解析成功为 list[dict]，失败则 netmiko 返回原始字符串。
        """
        conn = self.get_netmiko_connection()
        if textfsm_template:
            # 相对路径按 NET_TEXTFSM 解析，便于方案中只填模板文件名即可用
            template_str = (textfsm_template or "").strip()
            if template_str and not os.path.isabs(template_str):
                template_dir = os.environ.get("NET_TEXTFSM") or os.environ.get("NTC_TEMPLATES_DIR")
                if template_dir:
                    template_str = os.path.join(template_dir, template_str)
            return self._with_retry(
                "netmiko",
                "send_command_with_textfsm",
                conn.send_command,
                command,
                use_textfsm=True,
                textfsm_template=template_str or None,
            )
        return self._with_retry(
            "netmiko",
            "send_command",
            conn.send_command,
            command,
            use_textfsm=use_textfsm,
        )

    def execute_netconf_get(self, xml_template: str) -> Any:
        """
        执行NETCONF GET操作

        Args:
            xml_template: XML模板内容

        Returns:
            NETCONF查询结果
        """
        conn = self.get_netconf_connection()
        if hasattr(conn, "netconf_get"):
            return self._with_retry(
                "netconf",
                "netconf_get",
                conn.netconf_get,
                xml_template,
            )
        # 使用标准ncclient manager
        return self._with_retry(
            "netconf",
            "ncclient_get",
            conn.get,
            ("subtree", xml_template),
        )

    def execute_netconf_get_config(self, xml_template: Optional[str] = None) -> Any:
        """
        执行NETCONF GET_CONFIG操作

        Args:
            xml_template: XML模板内容（可选）

        Returns:
            NETCONF配置查询结果
        """
        conn = self.get_netconf_connection()
        if hasattr(conn, "netconfig_get_config"):
            if xml_template:
                return self._with_retry(
                    "netconf",
                    "netconfig_get_config_with_filter",
                    conn.netconfig_get_config,
                    xml_template,
                )
            return self._with_retry(
                "netconf",
                "netconfig_get_config",
                conn.netconfig_get_config,
            )
        # 使用标准ncclient manager
        if xml_template:
            return self._with_retry(
                "netconf",
                "ncclient_get_config_with_filter",
                conn.get_config,
                source="running",
                filter=("subtree", xml_template),
            )
        return self._with_retry(
            "netconf",
            "ncclient_get_config",
            conn.get_config,
            source="running",
        )

    def execute_snmp_get(self, oids: List[str]) -> Dict[str, Any]:
        """
        执行SNMP GET操作

        Args:
            oids: OID列表

        Returns:
            SNMP查询结果字典，格式: {oid: value}
        """
        session = self.get_snmp_session()
        results = {}
        snmp_identity = (
            session.get("username", "")
            if str(session.get("version", "")).lower() == "v3"
            else session.get("community", "")
        )

        for oid in oids:
            try:
                success, result = snmp_get_oid(
                    ip=session["ip"],
                    snmp_version=session["version"],
                    snmp_community=snmp_identity,
                    oid=oid,
                    port=session["port"],
                    timeout=session["timeout"],
                    retries=session["retries"],
                    auth_key=session.get("auth_key"),
                    priv_key=session.get("priv_key"),
                )
                if success:
                    results[oid] = result
                else:
                    results[oid] = None
                    logger.warning(
                        f"SNMP GET失败: {self.device_ip}, OID={oid}, error={result}"
                    )
            except Exception as e:
                logger.error(
                    f"SNMP GET异常: {self.device_ip}, OID={oid}, {str(e)}",
                    exc_info=True,
                )
                results[oid] = None

        return results

    def execute_restconf_get(self, endpoint: str) -> Dict[str, Any]:
        """
        执行RESTCONF GET操作

        Args:
            endpoint: RESTCONF端点路径

        Returns:
            RESTCONF查询结果
        """
        session = self.get_restconf_session()
        url = f"{session.base_url}{endpoint}"
        response = self._with_retry(
            "restconf",
            "restconf_get",
            session.get,
            url,
            timeout=self._get_timeout_seconds("restconf", self.DEFAULT_RESTCONF_TIMEOUT),
        )
        response.raise_for_status()
        return response.json()

    def execute_telemetry_subscribe(
        self, subscription_path: str, sampling_interval: int = 10
    ) -> Any:
        """
        执行Telemetry订阅

        Args:
            subscription_path: 订阅路径
            sampling_interval: 采样间隔（秒）

        Returns:
            Telemetry订阅结果
        """
        self.get_telemetry_channel()
        raise NotImplementedError(
            f"telemetry_not_implemented: device={self.device_ip}, "
            f"path={subscription_path}, interval={sampling_interval}"
        )
