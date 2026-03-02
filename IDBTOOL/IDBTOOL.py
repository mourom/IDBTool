#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IDB Tool (Ios Debug Bridge Tool)

整合了 py-ios-device 的所有主要功能，提供简单易用的接口
支持定时采样、数据采样暂停/继续/停止/清除、本地 JSON/TXT 导出等功能
适用于性能监控与调试场景
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Any

# 添加 py-ios-device 到系统路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

# 导入必要的模块
from ios_device.servers.Instrument import InstrumentServer
from ios_device.servers.screenshotr import screenshotr
from ios_device.servers.syslog import SyslogServer
from ios_device.servers.crash_log import CrashLogService
from ios_device.servers.pcapd import PcapdService, PCAPPacketDumper
from ios_device.servers.Installation import InstallationProxyService
from ios_device.servers.simulate_location import SimulateLocation
from ios_device.servers.diagnostics_relay import DiagnosticsRelayService
from ios_device.util.lockdown import LockdownClient
from ios_device.util.usbmux import USBMux
from ios_device.cli.base import InstrumentsBase
from ios_device.util.dtx_msg import DTXMessage
from ios_device.util.utils import convertBytes
from ios_device.remote.remote_lockdown import RemoteLockdownClient

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('IDBTool')


class IDBTool:
    """IDB Tool 主类，整合了所有功能"""
    
    def __init__(self, udid: Optional[str] = None, network: bool = False, address: Optional[str] = None):
        """
        初始化 IDBTool
        
        Args:
            udid: 设备的 UDID，如果不指定则使用第一个连接的设备
            network: 是否使用网络连接
            address: 网络设备地址（IP:端口），如果不指定则自动发现
        """
        self.udid = udid
        self.network = network
        self.address = address
        self.instrument_server = None
        self.syslog_server = None
        self.crash_log_service = None
        self.installation_service = None
        self.simulate_location = None
        self.diagnostics_service = None
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_all()
    
    def stop_all(self):
        """停止所有服务"""
        if self.instrument_server:
            try:
                self.instrument_server.stop()
            except Exception as e:
                logger.error(f"停止 InstrumentServer 时出错: {e}")
        if self.syslog_server:
            try:
                self.syslog_server.stop()
            except Exception as e:
                logger.error(f"停止 SyslogServer 时出错: {e}")
    
    # ==================== 设备管理 ====================
    
    def get_devices(self) -> List[Dict[str, str]]:
        """
        获取连接的设备列表
        
        Returns:
            设备列表，每个设备包含 udid 和 name
        """
        with USBMux() as usb_mux:
            mux_devices = usb_mux.get_devices(self.network)
        
        # 转换 MuxDevice 对象为字典列表
        devices = []
        for device in mux_devices:
            devices.append({
                'UniqueDeviceID': device.serial,
                'DeviceName': device.device.get('Properties', {}).get('DeviceName', 'Unknown'),
                'ConnectionType': device.connection_type
            })
        return devices
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        try:
            if self.network:
                if self.address:
                    # 使用RemoteLockdownClient直接连接网络设备
                    host, port = self.address.split(':') if ':' in self.address else (self.address, 62078)
                    device_info = RemoteLockdownClient((host, int(port))).get_value()
                else:
                    # 尝试使用RemoteLockdownClient连接网络设备
                    logger.info("尝试使用RemoteLockdownClient连接网络设备...")
                    # 尝试常见的iOS网络调试端口范围
                    for port in range(50000, 60001, 1000):
                        try:
                            device_info = RemoteLockdownClient((self.udid, port)).get_value()
                            logger.info(f"成功连接到 {self.udid}:{port}")
                            break
                        except:
                            continue
                    else:
                        raise Exception("无法连接到网络设备，请确保设备IP地址正确且网络调试已开启")
            else:
                # 使用传统的LockdownClient
                device_info = LockdownClient(udid=self.udid, network=self.network).get_value()
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
            raise
        
        # 递归转换 bytes 类型为字符串
        def convert_bytes(obj):
            if isinstance(obj, dict):
                return {k: convert_bytes(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_bytes(item) for item in obj]
            elif isinstance(obj, bytes):
                try:
                    return obj.decode('utf-8')
                except UnicodeDecodeError:
                    return str(obj)
            else:
                return obj
        
        return convert_bytes(device_info)
    
    # ==================== 性能监控 ====================
    
    def start_system_monitor(self, callback, interval: int = 1000, filter: str = 'all'):
        """
        开始系统性能监控
        
        Args:
            callback: 回调函数，接收监控数据
            interval: 采样间隔（毫秒）
            filter: 过滤条件，可选值：all, memory, cpu, disk, network
        """
        from ios_device.util.utils import DumpDisk, DumpNetwork, DumpMemory
        
        disk = DumpDisk()
        network = DumpNetwork()
        memory = DumpMemory()
        
        def on_callback_message(res: DTXMessage):
            data = {}
            system_cpu_usage = {}
            if isinstance(res.selector, list):
                for index, row in enumerate(res.selector):
                    if 'System' in row:
                        data = dict(zip(self.instrument_server.system_attributes, row['System']))
                    if "SystemCPUUsage" in row:
                        system_cpu_usage = row["SystemCPUUsage"]
                if not data:
                    return
                
                result = {}
                if 'disk' == filter.lower() or 'all' == filter.lower():
                    result['disk'] = disk.decode(data)
                if 'network' == filter.lower() or 'all' == filter.lower():
                    result['network'] = network.decode(data)
                if 'memory' == filter.lower() or 'all' == filter.lower():
                    result['memory'] = memory.decode(data)
                if 'cpu' == filter.lower() or 'all' == filter.lower():
                    result['cpu'] = system_cpu_usage
                
                callback(result)
        
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            self.instrument_server = rpc
            rpc.process_attributes = ['name', 'pid']
            rpc.system_attributes = rpc.device_info.sysmonSystemAttributes()
            rpc.sysmontap(on_callback_message)
    
    def start_app_monitor(self, bundle_id: str, callback, interval: int = 1000):
        """
        开始应用性能监控
        
        Args:
            bundle_id: 应用的 Bundle ID
            callback: 回调函数，接收监控数据
            interval: 采样间隔（毫秒）
        """
        import dataclasses
        from packaging.version import Version
        
        proc_filter = ['pid', 'name', 'cpuUsage', 'physFootprint', 'diskBytesRead', 'diskBytesWritten', 'threadCount']
        
        def on_callback_message(res: DTXMessage):
            if isinstance(res.selector, list):
                for index, row in enumerate(res.selector):
                    if 'Processes' in row:
                        for _pid, process in row['Processes'].items():
                            # 构建进程属性对象
                            process_attrs = {
                                'pid': process[0],
                                'name': process[1],
                                'cpuUsage': process[2],
                                'physFootprint': process[3],
                                'diskBytesRead': process[4],
                                'diskBytesWritten': process[5],
                                'threadCount': process[6]
                            }
                            
                            # 根据 bundle_id 过滤进程
                            # 注意：这里需要根据实际情况实现，因为进程名称可能与 bundle_id 不完全匹配
                            # 为了演示，我们先返回所有进程的数据
                            result = {
                                'pid': process_attrs['pid'],
                                'name': process_attrs['name'],
                                'cpu': f'{round(process_attrs["cpuUsage"] * 100, 2)} %',
                                'memory': convertBytes(process_attrs['physFootprint']),
                                'disk_reads': convertBytes(process_attrs['diskBytesRead']),
                                'disk_writes': convertBytes(process_attrs['diskBytesWritten']),
                                'threads': process_attrs['threadCount']
                            }
                            callback(result)
        
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            self.instrument_server = rpc
            rpc.process_attributes = ['pid', 'name', 'cpuUsage', 'physFootprint',
                                      'diskBytesRead', 'diskBytesWritten', 'threadCount']
            rpc.sysmontap(on_callback_message, interval)
    
    def start_fps_monitor(self, callback, interval: int = 1000):
        """
        开始 FPS 监控
        
        Args:
            callback: 回调函数，接收监控数据
            interval: 采样间隔（毫秒）
        """
        def on_callback_message(res: DTXMessage):
            data = res.selector
            result = {
                'current_time': str(datetime.now()),
                'fps': data['CoreAnimationFramesPerSecond']
            }
            callback(result)
        
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            self.instrument_server = rpc
            rpc.graphics(on_callback_message, interval)
    
    def start_gpu_monitor(self, callback):
        """
        开始 GPU 监控
        
        Args:
            callback: 回调函数，接收监控数据
        """
        from ios_device.util.dtx_msg import RawInt64sl, RawInt32sl
        from ios_device.util.gpu_decode import JSEvn, TraceData, GRCDecodeOrder, GRCDisplayOrder
        
        decode_key_list = []
        js_env = None
        display_key_list = []
        mach_time_factor = 1.0
        parsed_gpu_data = {}
        
        def on_callback_message(res):
            nonlocal js_env, decode_key_list, display_key_list, parsed_gpu_data
            if res.selector[0] == 1:
                # 处理GPU数据
                if js_env:
                    # 使用JSEvn处理GPU数据
                    js_env.dump_trace(TraceData(*res.selector[:6]))
                    # 这里可以添加更多解析逻辑，例如获取具体的GPU性能指标
                    # 目前我们只是保存原始数据
                    parsed_gpu_data['raw_data'] = res.selector
                    parsed_gpu_data['timestamp'] = time.time()
                    callback(parsed_gpu_data)
            elif res.selector[0] == 0:
                # 初始化GPU环境
                _data = res.selector[4]
                decode_key_list = GRCDecodeOrder.decode(_data.get(1))
                display_key_list = GRCDisplayOrder.decode(_data.get(0))
                js_env = JSEvn(_data.get(2), display_key_list, decode_key_list, mach_time_factor)
                # 保存GPU环境信息
                parsed_gpu_data['gpu_info'] = {
                    'decode_key_list': [{'key': item.key, 'require': item.require} for item in decode_key_list],
                    'display_key_list': [{'display': item.display, 'scale': item.scale, 'content': item.content, 'method': item.method, 'mix': item.mix, 'min': item.min} for item in display_key_list]
                }
                callback(parsed_gpu_data)
        
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            self.instrument_server = rpc
            
            # 注册未定义回调
            rpc.instruments.register_undefined_callback(on_callback_message)
            
            # 获取mach时间信息
            machTimeInfo = rpc.instruments.call("com.apple.instruments.server.services.deviceinfo", "machTimeInfo").selector
            mach_time_factor = machTimeInfo[1] / machTimeInfo[2]
            parsed_gpu_data['mach_time_factor'] = mach_time_factor
            
            # 获取GPU设备信息
            requestDeviceGPUInfo = rpc.instruments.call('com.apple.instruments.server.services.gpu', 'requestDeviceGPUInfo').selector
            min_collection_interval = requestDeviceGPUInfo[0].get('min-collection-interval')
            parsed_gpu_data['device_info'] = requestDeviceGPUInfo
            
            # 配置GPU计数器
            rpc.instruments.call("com.apple.instruments.server.services.gpu",
                     "configureCounters:counterProfile:interval:windowLimit:tracingPID:",
                     RawInt64sl(min_collection_interval, 3, 0, 0), RawInt32sl(-1))
            
            # 开始采集GPU计数器数据
            rpc.instruments.call('com.apple.instruments.server.services.gpu', 'startCollectingCounters')
            logger.info('GPU 监控已启动，开始采集GPU性能数据')
            
            # 保持运行，直到用户中断
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                # 停止采集
                rpc.instruments.call('com.apple.instruments.server.services.gpu', 'stopCollectingCounters')
                # 获取剩余数据
                data = rpc.instruments.call('com.apple.instruments.server.services.gpu', 'flushRemainingData').selector
                if js_env and data:
                    js_env.dump_trace(TraceData(*data[0][:6]))
                    parsed_gpu_data['final_data'] = data
                    callback(parsed_gpu_data)
                # 停止服务
                rpc.instruments.stop()
                logger.info('GPU 监控已停止')
    
    def stop_gpu_monitor(self):
        """
        停止 GPU 监控
        """
        if self.instrument_server:
            try:
                # 停止GPU采集
                self.instrument_server.instruments.call('com.apple.instruments.server.services.gpu', 'stopCollectingCounters')
                # 获取剩余数据
                self.instrument_server.instruments.call('com.apple.instruments.server.services.gpu', 'flushRemainingData')
                # 停止服务
                self.instrument_server.instruments.stop()
                self.instrument_server = None
                logger.info('GPU 监控已停止')
            except Exception as e:
                logger.error(f"停止 GPU 监控时出错: {e}")
    
    def get_gpu_info(self):
        """
        获取 GPU 设备信息
        
        Returns:
            GPU 设备信息
        """
        try:
            with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
                # 获取 GPU 设备信息
                result = rpc.instruments.call('com.apple.instruments.server.services.gpu', 'requestDeviceGPUInfo').selector
                return result
        except Exception as e:
            logger.error(f"获取 GPU 信息失败: {e}")
            return None
    
    def start_network_monitor(self, callback):
        """
        开始网络监控
        
        Args:
            callback: 回调函数，接收监控数据
        """
        def _callback(res: DTXMessage):
            from ios_device.util.api_util import network_caller
            network_caller(res, callback)
        
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            self.instrument_server = rpc
            rpc.networking(_callback)
    
    # ==================== 应用管理 ====================
    
    def list_apps(self, user: bool = True, system: bool = False, size: bool = False) -> List[Dict[str, Any]]:
        """
        列出已安装的应用
        
        Args:
            user: 是否包含用户应用
            system: 是否包含系统应用
            size: 是否获取应用大小
            
        Returns:
            应用列表
        """
        options = {}
        app_types = []
        if user:
            app_types.append('User')
        if system:
            app_types.append('System')
        if not app_types:
            app_types.append('User')
        if size:
            options['ReturnAttributes'] = ['CFBundleIdentifier', 'CFBundleVersion',
                                           'CFBundleDisplayName',
                                           'StaticDiskUsage', 'DynamicDiskUsage']
        
        service = InstallationProxyService(udid=self.udid, network=self.network)
        apps_info = service.apps_info(options)
        
        # 转换字典为列表，并根据应用类型过滤
        apps = []
        if isinstance(apps_info, dict):
            for app in apps_info.values():
                if app.get('ApplicationType') in app_types:
                    apps.append(app)
        elif isinstance(apps_info, list):
            for app in apps_info:
                if app.get('ApplicationType') in app_types:
                    apps.append(app)
        
        return apps
    
    def install_app(self, ipa_path: str) -> Dict[str, Any]:
        """
        安装应用
        
        Args:
            ipa_path: IPA 文件路径
            
        Returns:
            安装结果
        """
        service = InstallationProxyService(udid=self.udid, network=self.network)
        return service.install(ipa_path)
    
    def uninstall_app(self, bundle_id: str) -> Dict[str, Any]:
        """
        卸载应用
        
        Args:
            bundle_id: 应用的 Bundle ID
            
        Returns:
            卸载结果
        """
        service = InstallationProxyService(udid=self.udid, network=self.network)
        return service.uninstall(bundle_id)
    
    def launch_app(self, bundle_id: str, app_env: Optional[Dict[str, Any]] = None) -> int:
        """
        启动应用
        
        Args:
            bundle_id: 应用的 Bundle ID
            app_env: 应用启动环境变量
            
        Returns:
            进程 ID
        """
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            return rpc.launch_app(bundle_id=bundle_id, app_env=app_env)
    
    def kill_app(self, bundle_id: Optional[str] = None, name: Optional[str] = None, pid: Optional[int] = None):
        """
        停止应用
        
        Args:
            bundle_id: 应用的 Bundle ID
            name: 应用名称
            pid: 进程 ID
        """
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            if bundle_id or name:
                pid = rpc.get_pid(bundle_id, name)
            if not pid:
                logger.error(f'无法找到进程: {bundle_id}, {name}, {pid}')
                return
            rpc.kill_app(pid)
            logger.info(f'已停止进程: {pid}')
    
    # ==================== 系统管理 ====================
    
    def get_syslog(self, callback, filter: Optional[str] = None):
        """
        获取系统日志
        
        Args:
            callback: 回调函数，接收日志数据
            filter: 过滤条件
        """
        self.syslog_server = SyslogServer(udid=self.udid, network=self.network)
        
        # 创建一个包装类，将回调函数包装成具有write方法的对象
        class CallbackWrapper:
            def __init__(self, callback_func):
                self.callback_func = callback_func
            
            def write(self, data):
                # 处理数据并调用回调函数
                lines = data.strip().split('\n')
                for line in lines:
                    if line:
                        self.callback_func(line)
        
        # 使用包装器调用watch方法
        wrapper = CallbackWrapper(callback)
        self.syslog_server.watch(wrapper, filter)
    
    def list_crash_logs(self) -> List[str]:
        """
        列出崩溃日志
        
        Returns:
            崩溃日志列表
        """
        service = CrashLogService(udid=self.udid, network=self.network)
        return service.get_list()
    
    def export_crash_log(self, name: str):
        """
        导出崩溃日志
        
        Args:
            name: 崩溃日志名称
        """
        service = CrashLogService(udid=self.udid, network=self.network)
        service.export_crash(name)
    
    def delete_crash_log(self, name: str):
        """
        删除崩溃日志
        
        Args:
            name: 崩溃日志名称
        """
        service = CrashLogService(udid=self.udid, network=self.network)
        service.delete_crash(name)
    
    def get_battery_info(self) -> Dict[str, Any]:
        """
        获取电池信息
        
        Returns:
            电池信息
        """
        service = DiagnosticsRelayService(udid=self.udid, network=self.network)
        info = service.get_battery()
        
        # 递归转换 bytes 类型为字符串
        def convert_bytes(obj):
            if isinstance(obj, dict):
                return {k: convert_bytes(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_bytes(item) for item in obj]
            elif isinstance(obj, bytes):
                try:
                    return obj.decode('utf-8')
                except UnicodeDecodeError:
                    return str(obj)
            else:
                return obj
        
        return convert_bytes(info)
    
    # ==================== 高级功能 ====================
    
    def take_screenshot(self, output_path: str = None, scale: float = 1.0) -> bool:
        """
        拍摄屏幕截图
        
        Args:
            output_path: 输出路径，如果为None则自动生成带时间戳的文件名
            scale: 分辨率缩放倍数，默认1.0（原始大小），0.5表示缩小到一半大小
            
        Returns:
            是否成功
        """
        try:
            # 如果未指定输出路径，生成带时间戳的文件名
            if output_path is None:
                # 使用包含毫秒的时间戳格式，确保唯一性和连续性
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                output_path = f'screenshot_{timestamp}.png'
            
            screenshot = screenshotr(udid=self.udid)
            screen_data = screenshot.take_screenshot()
            if screen_data:
                # 检查是否需要缩放
                if scale == 1.0:
                    # 不需要缩放，直接保存
                    with open(output_path, 'wb') as f:
                        f.write(screen_data)
                else:
                    # 需要缩放，使用PIL库处理
                    try:
                        from PIL import Image
                        from io import BytesIO
                        
                        # 读取原始图像
                        image = Image.open(BytesIO(screen_data))
                        
                        # 计算新尺寸
                        new_width = int(image.width * scale)
                        new_height = int(image.height * scale)
                        
                        # 缩放图像
                        resized_image = image.resize((new_width, new_height), Image.LANCZOS)
                        
                        # 保存缩放后的图像
                        resized_image.save(output_path, 'PNG', optimize=True, compress_level=9)
                        logger.info(f'屏幕截图已缩放并保存为: {output_path} (缩放比例: {scale})')
                    except ImportError:
                        # PIL库未安装，直接保存原始图像
                        with open(output_path, 'wb') as f:
                            f.write(screen_data)
                        logger.warning('PIL库未安装，无法缩放截图，已保存原始大小截图')
                    except Exception as e:
                        # 缩放过程中出错，直接保存原始图像
                        with open(output_path, 'wb') as f:
                            f.write(screen_data)
                        logger.warning(f'缩放截图时出错: {e}，已保存原始大小截图')
                
                return True
            else:
                logger.error('无法获取屏幕截图')
                return False
        except Exception as e:
            logger.error(f'拍摄屏幕截图时出错: {e}')
            return False
    
    def start_pcapd(self, outfile: str):
        """
        开始网络抓包
        
        Args:
            outfile: 输出文件路径，或 "-" 表示输出到 stdout
        """
        if outfile == '-':
            out_file = sys.stdout.buffer
        else:
            out_file = open(outfile, 'wb', 0)
        
        try:
            packet_extractor = PcapdService(udid=self.udid, network=self.network)
            packet_dumper = PCAPPacketDumper(packet_extractor, out_file)
            
            def packet_callback(pkt):
                logger.info(f'捕获到数据包: {len(pkt)} bytes')
            
            packet_dumper.run(packet_callback)
        except KeyboardInterrupt:
            logger.info('抓包已停止')
        finally:
            if outfile != '-':
                out_file.close()
    
    def set_simulate_location(self, latitude: float, longitude: float):
        """
        设置模拟定位
        
        Args:
            latitude: 纬度
            longitude: 经度
        """
        service = SimulateLocation(udid=self.udid, network=self.network)
        service.set(latitude, longitude)
        logger.info(f'已设置模拟定位: {latitude}, {longitude}')
    
    def clear_simulate_location(self):
        """
        清除模拟定位
        """
        service = SimulateLocation(udid=self.udid, network=self.network)
        service.clear()
        logger.info('已清除模拟定位')
    
    # ==================== 设备状态模拟 ====================
    
    def get_condition_inducer(self) -> Dict[str, Any]:
        """
        获取设备条件诱导器配置
        
        Returns:
            条件诱导器配置
        """
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            return rpc.get_condition_inducer()
    
    def set_condition_inducer(self, condition_id: str, profile_id: str = '') -> Dict[str, Any]:
        """
        设置设备条件诱导器
        
        Args:
            condition_id: 条件 ID，例如: SlowNetworkCondition, ThermalCondition
            profile_id: 配置文件 ID，例如: SlowNetwork2GUrban, ThermalCritical
            
        Returns:
            设置结果
        """
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            result = rpc.set_condition_inducer(condition_id, profile_id)
            logger.info(f'已设置设备条件: {condition_id}, 配置: {profile_id}')
            return result
    
    # ==================== 应用生命周期监控 ====================
    
    def start_app_notifications_monitor(self, callback):
        """
        开始监控应用通知（启动、退出、后台等状态）
        
        Args:
            callback: 回调函数，接收通知数据
        """
        def on_callback_message(res: DTXMessage):
            data = res.auxiliaries[0]
            callback(data)
        
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            rpc.mobile_notifications(on_callback_message)
    
    def analyze_app_lifecycle(self, bundle_id: str):
        """
        分析应用启动生命周期
        
        Args:
            bundle_id: 应用的 Bundle ID
        """
        with InstrumentsBase(udid=self.udid, network=self.network) as rpc:
            rpc.app_launch_lifecycle(bundle_id)
    
    # ==================== 数据采集与导出 ====================
    
    def start_data_collection(self, bundle_id: Optional[str] = None, 
                             duration: int = 60, 
                             interval: int = 1000, 
                             screenshot_scale: float = 0.5, 
                             output_file: str = 'idb_data'):
        """
        开始数据采集
        
        Args:
            bundle_id: 应用的 Bundle ID，如果不指定则监控系统
            duration: 采集持续时间（秒）
            interval: 采样间隔（毫秒）
            screenshot_scale: 截图分辨率缩放倍数
            output_file: 输出文件路径（不含扩展名）
        """
        collected_data = []
        start_time = time.time()
        # 增加0.5秒缓冲，确保能采集到足够的数据
        end_time = start_time + duration + 0.5
        collecting = True  # 控制是否继续采集的标志
        rpc = None
        gpu_data = None
        
        def callback(data):
            if not collecting:  # 如果已经停止采集，则直接返回
                return
                
            # 获取当前时间，确保数据采集和截图使用相同的时间
            current_time = time.time()
            # 使用包含毫秒的时间戳格式，确保唯一性和连续性
            time_str = datetime.fromtimestamp(current_time).strftime('%Y%m%d_%H%M%S_%f')[:-3]
            
            # 获取电池信息
            try:
                battery_info = self.get_battery_info()
                data['battery'] = battery_info
            except Exception as e:
                logger.warning(f'获取电池信息失败: {e}')
                data['battery'] = '获取失败'
            
            # 添加GPU数据
            if gpu_data:
                data['gpu'] = gpu_data
            
            # 拍摄屏幕截图
            try:
                screenshot_path = f'screenshot_{time_str}.png'
                screenshot_success = self.take_screenshot(screenshot_path, scale=screenshot_scale)
                if screenshot_success:
                    data['screenshot'] = screenshot_path
                    logger.info(f'已拍摄屏幕截图: {screenshot_path} (缩放: {screenshot_scale}x)')
                else:
                    logger.warning('拍摄屏幕截图失败')
            except Exception as e:
                logger.warning(f'拍摄屏幕截图时出错: {e}')
            
            # 使用相同的时间戳
            data['timestamp'] = current_time
            data['time_str'] = time_str  # 添加可读的时间字符串
            data['elapsed_time'] = current_time - start_time
            collected_data.append(data)
            logger.info(f'采集到数据: {json.dumps(data, ensure_ascii=False)}')
        
        def gpu_callback(data):
            nonlocal gpu_data
            if collecting:
                gpu_data = data
        
        logger.info(f'开始数据采集，持续时间: {duration}秒，间隔: {interval}毫秒')
        
        try:
            # 初始化InstrumentsBase
            from ios_device.cli.base import InstrumentsBase
            import threading
            rpc = InstrumentsBase(udid=self.udid, network=self.network)
            self.instrument_server = rpc
            
            # 启动GPU监控
            try:
                from ios_device.util.dtx_msg import RawInt64sl, RawInt32sl
                from ios_device.util.gpu_decode import JSEvn, TraceData, GRCDecodeOrder, GRCDisplayOrder
                
                decode_key_list = []
                js_env = None
                display_key_list = []
                mach_time_factor = 1.0
                parsed_gpu_data = {}
                
                # 获取mach时间信息
                machTimeInfo = rpc.instruments.call("com.apple.instruments.server.services.deviceinfo", "machTimeInfo").selector
                mach_time_factor = machTimeInfo[1] / machTimeInfo[2]
                parsed_gpu_data['mach_time_factor'] = mach_time_factor
                
                # 注册未定义回调
                def on_gpu_message(res):
                    nonlocal js_env, decode_key_list, display_key_list, parsed_gpu_data
                    if collecting:
                        if res.selector[0] == 1:
                            # 处理GPU数据
                            if js_env:
                                js_env.dump_trace(TraceData(*res.selector[:6]))
                                # 保存解析后的GPU数据
                                parsed_gpu_data['raw_data'] = res.selector
                                parsed_gpu_data['timestamp'] = time.time()
                                # 添加包含毫秒的可读时间字符串
                                parsed_gpu_data['time_str'] = datetime.fromtimestamp(time.time()).strftime('%Y%m%d_%H%M%S_%f')[:-3]
                                gpu_callback(parsed_gpu_data)
                        elif res.selector[0] == 0:
                            # 初始化GPU环境
                            _data = res.selector[4]
                            decode_key_list = GRCDecodeOrder.decode(_data.get(1))
                            display_key_list = GRCDisplayOrder.decode(_data.get(0))
                            js_env = JSEvn(_data.get(2), display_key_list, decode_key_list, mach_time_factor)
                            # 保存GPU环境信息
                            parsed_gpu_data['gpu_info'] = {
                                'decode_key_list': [{'key': item.key, 'require': item.require} for item in decode_key_list],
                                'display_key_list': [{'display': item.display, 'scale': item.scale, 'content': item.content, 'method': item.method, 'mix': item.mix, 'min': item.min} for item in display_key_list]
                            }
                            gpu_callback(parsed_gpu_data)
                rpc.instruments.register_undefined_callback(on_gpu_message)
                
                # 获取GPU设备信息
                requestDeviceGPUInfo = rpc.instruments.call('com.apple.instruments.server.services.gpu', 'requestDeviceGPUInfo').selector
                min_collection_interval = requestDeviceGPUInfo[0].get('min-collection-interval')
                parsed_gpu_data['device_info'] = requestDeviceGPUInfo
                
                # 配置GPU计数器
                rpc.instruments.call("com.apple.instruments.server.services.gpu",
                         "configureCounters:counterProfile:interval:windowLimit:tracingPID:",
                         RawInt64sl(min_collection_interval, 3, 0, 0), RawInt32sl(-1))
                
                # 开始采集GPU计数器数据
                rpc.instruments.call('com.apple.instruments.server.services.gpu', 'startCollectingCounters')
                logger.info('GPU 监控已启动，开始采集GPU性能数据')
            except Exception as e:
                logger.warning(f'启动 GPU 监控失败: {e}')
            
            # 创建一个线程来运行sysmontap
            sysmontap_thread = None
            
            if bundle_id:
                # 监控应用性能
                def on_callback_message(res):
                    if not collecting:  # 如果已经停止采集，则直接返回
                        return
                        
                    if isinstance(res.selector, list):
                        for index, row in enumerate(res.selector):
                            if 'Processes' in row:
                                for _pid, process in row['Processes'].items():
                                    process_attrs = {
                                        'pid': process[0],
                                        'name': process[1],
                                        'cpuUsage': process[2],
                                        'physFootprint': process[3],
                                        'diskBytesRead': process[4],
                                        'diskBytesWritten': process[5],
                                        'threadCount': process[6]
                                    }
                                    result = {
                                        'pid': process_attrs['pid'],
                                        'name': process_attrs['name'],
                                        'cpu': f'{round(process_attrs["cpuUsage"] * 100, 2)} %',
                                        'memory': convertBytes(process_attrs['physFootprint']),
                                        'disk_reads': convertBytes(process_attrs['diskBytesRead']),
                                        'disk_writes': convertBytes(process_attrs['diskBytesWritten']),
                                        'threads': process_attrs['threadCount']
                                    }
                                    callback(result)
                
                rpc.process_attributes = ['pid', 'name', 'cpuUsage', 'physFootprint',
                                          'diskBytesRead', 'diskBytesWritten', 'threadCount']
                
                # 在单独的线程中运行sysmontap
                def run_sysmontap():
                    try:
                        rpc.sysmontap(on_callback_message, interval)
                    except Exception as e:
                        logger.error(f"sysmontap运行出错: {e}")
                
                sysmontap_thread = threading.Thread(target=run_sysmontap)
                sysmontap_thread.daemon = True
                sysmontap_thread.start()
            else:
                # 监控系统性能
                from ios_device.util.utils import DumpDisk, DumpNetwork, DumpMemory
                
                disk = DumpDisk()
                network = DumpNetwork()
                memory = DumpMemory()
                
                def on_callback_message(res):
                    if not collecting:  # 如果已经停止采集，则直接返回
                        return
                        
                    data = {}
                    system_cpu_usage = {}
                    if isinstance(res.selector, list):
                        for index, row in enumerate(res.selector):
                            if 'System' in row:
                                data = dict(zip(rpc.system_attributes, row['System']))
                            if "SystemCPUUsage" in row:
                                system_cpu_usage = row["SystemCPUUsage"]
                        if not data:
                            return
                        
                        result = {}
                        result['disk'] = disk.decode(data)
                        result['network'] = network.decode(data)
                        result['memory'] = memory.decode(data)
                        result['cpu'] = system_cpu_usage
                        
                        callback(result)
                
                rpc.process_attributes = ['name', 'pid']
                rpc.system_attributes = rpc.device_info.sysmonSystemAttributes()
                
                # 在单独的线程中运行sysmontap
                def run_sysmontap():
                    try:
                        rpc.sysmontap(on_callback_message, interval)
                    except Exception as e:
                        logger.error(f"sysmontap运行出错: {e}")
                
                sysmontap_thread = threading.Thread(target=run_sysmontap)
                sysmontap_thread.daemon = True
                sysmontap_thread.start()
            
            # 等待指定时间
            logger.info(f"开始等待指定的采集持续时间: {duration}秒")
            while time.time() < end_time and collecting:
                time.sleep(0.1)
            
            # 时间到，等待当前采集完成后再停止
            if collecting:
                logger.info("采集持续时间已结束，等待当前采集完成")
                # 等待一小段时间，确保当前正在处理的采集完成
                time.sleep(0.5)
                logger.info("准备停止采集")
                collecting = False
        except KeyboardInterrupt:
            logger.info('数据采集被用户中断')
            collecting = False  # 立即设置标志为False，阻止后续数据采集
            # 短暂延时，确保所有消息都被处理完毕
            time.sleep(0.5)
        finally:
            collecting = False  # 确保标志为False
            # 清理所有资源
            if self.instrument_server:
                try:
                    # 停止GPU监控
                    try:
                        self.instrument_server.instruments.call('com.apple.instruments.server.services.gpu', 'stopCollectingCounters')
                        self.instrument_server.instruments.call('com.apple.instruments.server.services.gpu', 'flushRemainingData')
                    except Exception as e:
                        logger.warning(f"停止 GPU 监控时出错: {e}")
                    # 停止InstrumentServer
                    if hasattr(self.instrument_server, 'stop'):
                        self.instrument_server.stop()
                    else:
                        self.instrument_server.instruments.stop()
                    self.instrument_server = None
                except Exception as e:
                    logger.error(f"停止 InstrumentServer 时出错: {e}")
            if rpc:
                try:
                    if hasattr(rpc, 'stop'):
                        rpc.stop()
                    if hasattr(rpc, 'close'):
                        rpc.close()
                except Exception as e:
                    logger.error(f"关闭 RPC 连接时出错: {e}")
            # 导出数据到 JSON 和 TXT 文件
            self.export_data(collected_data, output_file)
            logger.info(f'数据采集完成，已导出到: {output_file}.json 和 {output_file}.txt')
            logger.info(f'共采集到 {len(collected_data)} 条数据')
    
    def export_data(self, data: List[Dict[str, Any]], output_file: str):
        """
        导出数据到 JSON 和 TXT 文件
        
        Args:
            data: 要导出的数据
            output_file: 输出文件路径（不含扩展名）
        """
        if not data:
            logger.warning('没有数据可导出')
            return
        
        # 导出为 JSON 文件
        json_file = f'{output_file}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f'数据已成功导出到: {json_file}')
        
        # 导出为 TXT 文件
        txt_file = f'{output_file}.txt'
        with open(txt_file, 'w', encoding='utf-8') as f:
            for i, item in enumerate(data):
                f.write(f'=== 数据 #{i+1} ===\n')
                for key, value in item.items():
                    if isinstance(value, dict):
                        f.write(f'{key}:\n')
                        for sub_key, sub_value in value.items():
                            f.write(f'  {sub_key}: {sub_value}\n')
                    else:
                        f.write(f'{key}: {value}\n')
                f.write('\n')
        logger.info(f'数据已成功导出到: {txt_file}')


def interactive_menu():
    """
    交互式菜单，让小白用户可以直接输入功能序号来执行相应操作
    """
    def print_menu():
        """打印主菜单"""
        print("========================================")
        print("          IDB Tool - 交互式菜单          ")
        print("========================================")
        print("请输入功能序号，按 Enter 键执行：")
        print("")
        print("1. 设备管理")
        print("2. 性能监控")
        print("3. 数据采集")
        print("4. 高级功能")
        print("5. 设备状态模拟")
        print("6. 应用生命周期监控")
        print("7. 系统命令")
        print("8. 应用管理")
        print("9. 帮助与设置")
        print("0. 退出")
        print("")
    
    def select_device():
        """选择设备，增强网络设备发现"""
        print("=== 选择设备 ===")
        
        # 首先尝试通过USB连接
        print("正在搜索USB连接的设备...")
        usb_tool = IDBTool(network=False)
        usb_devices = usb_tool.get_devices()
        
        # 然后尝试通过网络连接
        print("正在搜索网络连接的设备...")
        network_tool = IDBTool(network=True)
        network_devices = network_tool.get_devices()
        
        # 合并设备列表，去重
        all_devices = []
        seen_udids = set()
        
        for device in usb_devices + network_devices:
            udid = device.get('UniqueDeviceID')
            if udid not in seen_udids:
                seen_udids.add(udid)
                all_devices.append(device)
        
        if not all_devices:
            print("未找到连接的设备")
            print("请检查：")
            print("1. 设备是否已启用开发者模式和网络连接")
            print("2. 设备和电脑是否在同一网络")
            print("3. 防火墙是否阻止了连接")
            return None
        
        print("可用设备：")
        for i, device in enumerate(all_devices):
            conn_type = "USB" if device.get('ConnectionType') == 'usb' else "Network"
            print(f"{i+1}. {device.get('DeviceName')} (UDID: {device.get('UniqueDeviceID')}, 连接方式: {conn_type})")
        
        while True:
            choice = input("请输入设备序号（0 取消）: ")
            if choice == '0':
                return None
            try:
                index = int(choice) - 1
                if 0 <= index < len(all_devices):
                    selected_device = all_devices[index]
                    conn_type = "USB" if selected_device.get('ConnectionType') == 'usb' else "Network"
                    print(f"已选择设备: {selected_device.get('DeviceName')} (连接方式: {conn_type})")
                    return selected_device.get('UniqueDeviceID')
                else:
                    print("无效的设备序号，请重新输入")
            except ValueError:
                print("请输入数字序号")
    
    def get_user_input(prompt, default=None, input_type=str, min_value=None, max_value=None):
        """获取用户输入，支持类型转换和范围检查"""
        while True:
            try:
                user_input = input(prompt)
                if not user_input and default is not None:
                    # 将默认值转换为指定的类型
                    if input_type == bool:
                        return default.lower() in ('y', 'yes', 'true', '1')
                    elif input_type in (int, float):
                        return input_type(default)
                    else:
                        return default
                
                if input_type == bool:
                    return user_input.lower() in ('y', 'yes', 'true', '1')
                elif input_type == int:
                    value = int(user_input)
                    if min_value is not None and value < min_value:
                        print(f"输入值必须大于等于 {min_value}")
                        continue
                    if max_value is not None and value > max_value:
                        print(f"输入值必须小于等于 {max_value}")
                        continue
                    return value
                elif input_type == float:
                    return float(user_input)
                else:
                    return user_input
            except ValueError:
                print(f"请输入有效的{input_type.__name__}")
    
    def show_help():
        """显示帮助信息"""
        print("=== 帮助信息 ===")
        print("IDB Tool (Ios Debug Bridge Tool) 是一个用于调试和监控 iOS 设备的工具。")
        print("\n主要功能：")
        print("1. 设备管理：查看和管理连接的 iOS 设备")
        print("2. 性能监控：监控系统和应用的性能指标")
        print("3. 数据采集：采集性能数据并导出为 JSON 和 TXT 文件")
        print("4. 高级功能：屏幕截图、网络抓包、模拟定位等")
        print("5. 设备状态模拟：模拟网络和热状态条件")
        print("6. 应用生命周期监控：监控应用状态变化和启动时间")
        print("7. 系统命令：查看系统日志、电池信息和崩溃日志")
        print("8. 应用管理：安装、卸载、启动和停止应用")
        print("\n使用方法：")
        print("- 在菜单中输入功能序号来执行相应操作")
        print("- 在子菜单中输入 0 可返回上一级菜单")
        print("- 按 Ctrl+C 可停止正在执行的操作")
        print("\n常见问题：")
        print("Q: 无法连接设备？")
        print("A: 请确保设备已解锁并信任此电脑")
        print("Q: 无法获取应用性能数据？")
        print("A: 请确保应用已安装并正在运行")
        input("\n按 Enter 键返回主菜单...")
    
    # 创建 IDBTool 实例
    tool = IDBTool()
    current_udid = None
    
    while True:
        try:
            print_menu()
            choice = get_user_input("请输入功能序号: ")
            print("")
            
            if choice == '0':
                print("感谢使用 IDB Tool，再见！")
                break
            elif choice == '1':
                # 设备管理
                print("=== 设备管理 ===")
                print("1. 列出连接的设备")
                print("2. 选择设备")
                print("3. 获取设备信息")
                print("0. 返回主菜单")
                sub_choice = get_user_input("请输入选项序号: ")
                
                if sub_choice == '0':
                    continue
                elif sub_choice == '1':
                    print("=== 列出连接的设备 ===")
                    devices = tool.get_devices()
                    if devices:
                        for device in devices:
                            print(f"UDID: {device.get('UniqueDeviceID')}, Name: {device.get('DeviceName')}")
                    else:
                        print("未找到连接的设备")
                elif sub_choice == '2':
                    udid = select_device()
                    if udid:
                        current_udid = udid
                        tool = IDBTool(udid=current_udid)
                elif sub_choice == '3':
                    print("=== 获取设备信息 ===")
                    info = tool.get_device_info()
                    print(json.dumps(info, ensure_ascii=False, indent=2))
                else:
                    print("无效的选项，请重新输入")
            elif choice == '2':
                # 性能监控
                print("=== 性能监控 ===")
                print("1. 系统级监控")
                print("2. 应用级监控")
                print("3. 其他监控")
                print("0. 返回主菜单")
                sub_choice = get_user_input("请输入选项序号: ")
                
                if sub_choice == '0':
                    continue
                elif sub_choice == '1':
                    # 系统级监控
                    print("=== 系统级监控 ===")
                    print("1. 监控系统整体性能")
                    print("2. 监控网络")
                    print("3. 监控 GPU")
                    print("0. 返回上一级菜单")
                    system_sub_choice = get_user_input("请输入选项序号: ")
                    
                    if system_sub_choice == '0':
                        continue
                    elif system_sub_choice == '1':
                        print("=== 监控系统整体性能 ===")
                        print("请选择监控类型：")
                        print("1. 全部")
                        print("2. 内存")
                        print("3. CPU")
                        print("4. 磁盘")
                        print("5. 网络")
                        filter_choice = get_user_input("请输入监控类型序号: ")
                        filter_map = {'1': 'all', '2': 'memory', '3': 'cpu', '4': 'disk', '5': 'network'}
                        filter_type = filter_map.get(filter_choice, 'all')
                        
                        def callback(data):
                            print(json.dumps(data, ensure_ascii=False))
                        
                        print(f"开始监控系统整体性能（类型：{filter_type}），按 Ctrl+C 停止...")
                        try:
                            tool.start_system_monitor(callback, filter=filter_type)
                        except KeyboardInterrupt:
                            print("监控已停止")
                    elif system_sub_choice == '2':
                        print("=== 监控网络 ===")
                        def callback(data):
                            print(json.dumps(data, ensure_ascii=False))
                        
                        print("开始监控网络，按 Ctrl+C 停止...")
                        try:
                            tool.start_network_monitor(callback)
                        except KeyboardInterrupt:
                            print("监控已停止")
                    elif system_sub_choice == '3':
                        print("=== 监控 GPU ===")
                        def callback(data):
                            print(json.dumps(data, ensure_ascii=False))
                        
                        print("开始监控 GPU，按 Ctrl+C 停止...")
                        try:
                            tool.start_gpu_monitor(callback)
                        except KeyboardInterrupt:
                            print("监控已停止")
                    else:
                        print("无效的选项，请重新输入")
                elif sub_choice == '2':
                    # 应用级监控
                    print("=== 应用级监控 ===")
                    print("1. 监控应用性能")
                    print("2. 监控 FPS")
                    print("0. 返回上一级菜单")
                    app_sub_choice = get_user_input("请输入选项序号: ")
                    
                    if app_sub_choice == '0':
                        continue
                    elif app_sub_choice == '1':
                        print("=== 监控应用性能 ===")
                        bundle_id = input("请输入应用的 Bundle ID: ")
                        if not bundle_id:
                            print("Bundle ID 不能为空")
                            continue
                        
                        def callback(data):
                            print(json.dumps(data, ensure_ascii=False))
                        
                        print(f"开始监控应用性能（Bundle ID：{bundle_id}），按 Ctrl+C 停止...")
                        try:
                            tool.start_app_monitor(bundle_id, callback)
                        except KeyboardInterrupt:
                            print("监控已停止")
                    elif app_sub_choice == '2':
                        print("=== 监控 FPS ===")
                        def callback(data):
                            print(json.dumps(data, ensure_ascii=False))
                        
                        print("开始监控 FPS，按 Ctrl+C 停止...")
                        try:
                            tool.start_fps_monitor(callback)
                        except KeyboardInterrupt:
                            print("监控已停止")
                    else:
                        print("无效的选项，请重新输入")
                elif sub_choice == '3':
                    # 其他监控
                    print("=== 其他监控 ===")
                    print("1. 监控电池")
                    print("0. 返回上一级菜单")
                    other_sub_choice = get_user_input("请输入选项序号: ")
                    
                    if other_sub_choice == '0':
                        continue
                    elif other_sub_choice == '1':
                        print("=== 监控电池 ===")
                        print("开始监控电池，按 Ctrl+C 停止...")
                        try:
                            def callback(data):
                                print(json.dumps(data, ensure_ascii=False))
                            
                            # 这里可以添加电池监控的实现
                            # 目前我们只是获取一次电池信息
                            battery_info = tool.get_battery_info()
                            print(json.dumps(battery_info, ensure_ascii=False, indent=2))
                            print("电池信息获取完成")
                        except KeyboardInterrupt:
                            print("监控已停止")
                    else:
                        print("无效的选项，请重新输入")
                else:
                    print("无效的选项，请重新输入")
            elif choice == '3':
                # 数据采集
                print("=== 数据采集 ===")
                bundle_id = input("请输入应用的 Bundle ID（留空则监控系统）: ")
                duration = get_user_input("请输入采集持续时间（秒，默认 60）: ", default="60", input_type=int, min_value=1)
                interval = get_user_input("请输入采样间隔（毫秒，默认 1000）: ", default="1000", input_type=int, min_value=100)
                screenshot_scale = get_user_input("请输入截图分辨率缩放倍数（默认 0.5，0.1-2.0）: ", default="0.5", input_type=float, min_value=0.1, max_value=2.0)
                output = input("请输入输出文件路径（默认 idb_data，无需扩展名）: ")
                output = output if output else 'idb_data'
                
                print(f"开始数据采集，持续时间：{duration}秒，间隔：{interval}毫秒，截图缩放：{screenshot_scale}x，输出文件：{output}.json 和 {output}.txt")
                tool.start_data_collection(
                    bundle_id=bundle_id if bundle_id else None,
                    duration=duration,
                    interval=interval,
                    screenshot_scale=screenshot_scale,
                    output_file=output
                )
            elif choice == '4':
                # 高级功能
                print("=== 高级功能 ===")
                print("1. 拍摄屏幕截图")
                print("2. 网络抓包")
                print("3. 设置模拟定位")
                print("0. 返回主菜单")
                sub_choice = get_user_input("请输入选项序号: ")
                
                if sub_choice == '0':
                    continue
                elif sub_choice == '1':
                    print("=== 拍摄屏幕截图 ===")
                    output = input("请输入输出文件路径（留空自动生成带时间戳的文件名）: ")
                    output = output if output else None
                    
                    # 获取缩放倍数
                    scale = get_user_input("请输入分辨率缩放倍数（默认1.0，0.1-2.0）: ", default="1.0", input_type=float, min_value=0.1, max_value=2.0)
                    
                    success = tool.take_screenshot(output, scale=scale)
                    if success:
                        print(f"屏幕截图已成功保存")
                    else:
                        print("拍摄屏幕截图失败")
                elif sub_choice == '2':
                    print("=== 网络抓包 ===")
                    outfile = input("请输入输出文件路径（默认 capture.pcap）: ")
                    outfile = outfile if outfile else 'capture.pcap'
                    print(f"开始网络抓包，输出文件：{outfile}，按 Ctrl+C 停止...")
                    try:
                        tool.start_pcapd(outfile)
                    except KeyboardInterrupt:
                        print("抓包已停止")
                elif sub_choice == '3':
                    print("=== 设置模拟定位 ===")
                    print("1. 设置模拟定位")
                    print("2. 清除模拟定位")
                    print("0. 返回上一级菜单")
                    loc_choice = get_user_input("请输入选项序号: ")
                    if loc_choice == '0':
                        continue
                    elif loc_choice == '1':
                        latitude = get_user_input("请输入纬度: ", input_type=float)
                        longitude = get_user_input("请输入经度: ", input_type=float)
                        tool.set_simulate_location(latitude, longitude)
                    elif loc_choice == '2':
                        tool.clear_simulate_location()
                    else:
                        print("无效的选项，请重新输入")
                else:
                    print("无效的选项，请重新输入")
            elif choice == '5':
                # 设备状态模拟
                print("=== 设备状态模拟 ===")
                print("1. 获取条件诱导器配置")
                print("2. 设置网络条件")
                print("3. 设置热状态")
                print("0. 返回主菜单")
                sub_choice = get_user_input("请输入选项序号: ")
                
                if sub_choice == '0':
                    continue
                elif sub_choice == '1':
                    print("=== 获取条件诱导器配置 ===")
                    config = tool.get_condition_inducer()
                    print(json.dumps(config, ensure_ascii=False, indent=2))
                elif sub_choice == '2':
                    print("=== 设置网络条件 ===")
                    print("请选择网络条件：")
                    print("1. 2G 网络")
                    print("2. 3G 网络")
                    print("3. 4G/LTE 网络")
                    print("4. WiFi 网络")
                    print("5. 100% 丢包")
                    print("0. 返回上一级菜单")
                    net_choice = get_user_input("请输入选项序号: ")
                    if net_choice == '0':
                        continue
                    net_map = {
                        '1': 'SlowNetwork2GUrban',
                        '2': 'SlowNetwork3G',
                        '3': 'SlowNetworkLTE',
                        '4': 'SlowNetworkWiFi',
                        '5': 'SlowNetwork100PctLoss'
                    }
                    profile_id = net_map.get(net_choice, 'SlowNetworkWiFi')
                    tool.set_condition_inducer('SlowNetworkCondition', profile_id)
                elif sub_choice == '3':
                    print("=== 设置热状态 ===")
                    print("请选择热状态：")
                    print("1. Fair（轻微）")
                    print("2. Serious（严重）")
                    print("3. Critical（危急）")
                    print("0. 返回上一级菜单")
                    thermal_choice = get_user_input("请输入选项序号: ")
                    if thermal_choice == '0':
                        continue
                    thermal_map = {
                        '1': 'ThermalFair',
                        '2': 'ThermalSerious',
                        '3': 'ThermalCritical'
                    }
                    profile_id = thermal_map.get(thermal_choice, 'ThermalFair')
                    tool.set_condition_inducer('ThermalCondition', profile_id)
                else:
                    print("无效的选项，请重新输入")
            elif choice == '6':
                # 应用生命周期监控
                print("=== 应用生命周期监控 ===")
                print("1. 监控应用状态变化")
                print("2. 分析应用启动生命周期")
                print("0. 返回主菜单")
                sub_choice = get_user_input("请输入选项序号: ")
                
                if sub_choice == '0':
                    continue
                elif sub_choice == '1':
                    def callback(data):
                        print(json.dumps(data, ensure_ascii=False, indent=2))
                    print("开始监控应用状态变化，按 Ctrl+C 停止...")
                    try:
                        tool.start_app_notifications_monitor(callback)
                    except KeyboardInterrupt:
                        print("监控已停止")
                elif sub_choice == '2':
                    bundle_id = input("请输入应用的 Bundle ID: ")
                    if not bundle_id:
                        print("Bundle ID 不能为空")
                        continue
                    print(f"开始分析应用启动生命周期（Bundle ID：{bundle_id}）...")
                    tool.analyze_app_lifecycle(bundle_id)
                else:
                    print("无效的选项，请重新输入")
            elif choice == '7':
                # 系统命令
                print("=== 系统命令 ===")
                print("1. 获取系统日志")
                print("2. 管理崩溃日志")
                print("3. 获取GPU信息")
                print("0. 返回主菜单")
                sub_choice = get_user_input("请输入选项序号: ")
                
                if sub_choice == '0':
                    continue
                elif sub_choice == '1':
                    print("开始获取系统日志，按 Ctrl+C 停止...")
                    def callback(line):
                        print(line)
                    try:
                        tool.get_syslog(callback)
                    except KeyboardInterrupt:
                        print("已停止获取系统日志")
                elif sub_choice == '2':
                    print("=== 管理崩溃日志 ===")
                    print("1. 列出崩溃日志")
                    print("2. 导出崩溃日志")
                    print("3. 删除崩溃日志")
                    print("0. 返回上一级菜单")
                    crash_choice = get_user_input("请输入选项序号: ")
                    if crash_choice == '0':
                        continue
                    elif crash_choice == '1':
                        logs = tool.list_crash_logs()
                        if logs:
                            for log in logs:
                                print(log)
                        else:
                            print("未找到崩溃日志")
                    elif crash_choice == '2':
                        name = input("请输入崩溃日志名称: ")
                        if name:
                            tool.export_crash_log(name)
                    elif crash_choice == '3':
                        name = input("请输入崩溃日志名称: ")
                        if name:
                            tool.delete_crash_log(name)
                    else:
                        print("无效的选项，请重新输入")
                elif sub_choice == '3':
                    print("=== 获取GPU信息 ===")
                    info = tool.get_gpu_info()
                    if info:
                        print(json.dumps(info, ensure_ascii=False, indent=2))
                    else:
                        print("获取GPU信息失败")
                else:
                    print("无效的选项，请重新输入")
            elif choice == '8':
                # 应用管理
                print("=== 应用管理 ===")
                print("1. 列出已安装的应用")
                print("2. 安装应用")
                print("3. 卸载应用")
                print("4. 启动应用")
                print("5. 停止应用")
                print("0. 返回主菜单")
                sub_choice = get_user_input("请输入选项序号: ")
                
                if sub_choice == '0':
                    continue
                elif sub_choice == '1':
                    print("=== 列出已安装的应用 ===")
                    apps = tool.list_apps()
                    if apps:
                        print(f"共找到 {len(apps)} 个应用：")
                        for i, app in enumerate(apps):
                            app_name = app.get('CFBundleDisplayName', app.get('CFBundleName', 'Unknown'))
                            bundle_id = app.get('CFBundleIdentifier', 'Unknown')
                            print(f"{i+1}. {app_name} (Bundle ID: {bundle_id})")
                    else:
                        print("未找到应用")
                elif sub_choice == '2':
                    ipa_path = input("请输入 IPA 文件路径: ")
                    if ipa_path:
                        result = tool.install_app(ipa_path)
                        print(json.dumps(result, ensure_ascii=False, indent=2))
                    else:
                        print("IPA 文件路径不能为空")
                elif sub_choice == '3':
                    bundle_id = input("请输入应用的 Bundle ID: ")
                    if bundle_id:
                        result = tool.uninstall_app(bundle_id)
                        print(json.dumps(result, ensure_ascii=False, indent=2))
                    else:
                        print("Bundle ID 不能为空")
                elif sub_choice == '4':
                    bundle_id = input("请输入应用的 Bundle ID: ")
                    if bundle_id:
                        pid = tool.launch_app(bundle_id)
                        print(f"应用已启动，PID: {pid}")
                    else:
                        print("Bundle ID 不能为空")
                elif sub_choice == '5':
                    bundle_id = input("请输入应用的 Bundle ID: ")
                    if bundle_id:
                        tool.kill_app(bundle_id)
                        print(f"应用已停止")
                    else:
                        print("Bundle ID 不能为空")
                else:
                    print("无效的选项，请重新输入")
            elif choice == '9':
                # 帮助与设置
                print("=== 帮助与设置 ===")
                print("1. 查看帮助信息")
                print("2. 查看当前设置")
                print("3. 重新选择设备")
                print("0. 返回主菜单")
                sub_choice = get_user_input("请输入选项序号: ")
                
                if sub_choice == '0':
                    continue
                elif sub_choice == '1':
                    show_help()
                elif sub_choice == '2':
                    print("=== 当前设置 ===")
                    print(f"当前设备 UDID: {current_udid or '未选择'}")
                    print(f"当前工具版本: 1.0.0")
                    print(f"py-ios-device 路径: {os.path.join(os.path.dirname(__file__), 'py-ios-device-main')}")
                    input("\n按 Enter 键返回...")
                elif sub_choice == '3':
                    udid = select_device()
                    if udid:
                        current_udid = udid
                        tool = IDBTool(udid=current_udid)
                else:
                    print("无效的选项，请重新输入")
            else:
                print("无效的选项，请重新输入")
            
            print("\n" + "="*40 + "\n")
            input("按 Enter 键继续...")
            print("\n")
            
        except KeyboardInterrupt:
            print("\n操作已取消")
            print("\n" + "="*40 + "\n")
        except Exception as e:
            print(f"执行过程中出错: {e}")
            print("\n" + "="*40 + "\n")
            input("按 Enter 键继续...")
            print("\n")


# 命令行接口
if __name__ == '__main__':
    import argparse
    
    # 检查是否有命令行参数，如果没有则启动交互式菜单
    if len(sys.argv) == 1:
        interactive_menu()
    else:
        # 原有命令行接口
        parser = argparse.ArgumentParser(description='IDB Tool - iOS Debug Bridge Tool')
        parser.add_argument('-u', '--udid', help='设备 UDID')
        parser.add_argument('-n', '--network', action='store_true', help='使用网络连接')
        parser.add_argument('-a', '--address', help='网络设备地址（IP:端口），如果不指定则自动发现')
        
        subparsers = parser.add_subparsers(dest='command', help='命令')
        
        # 设备管理命令
        device_parser = subparsers.add_parser('device', help='设备管理')
        device_subparsers = device_parser.add_subparsers(dest='device_command')
        device_subparsers.add_parser('list', help='列出设备')
        device_subparsers.add_parser('info', help='获取设备信息')
        
        # 应用管理命令
        app_parser = subparsers.add_parser('app', help='应用管理')
        app_subparsers = app_parser.add_subparsers(dest='app_command')
        app_subparsers.add_parser('list', help='列出应用')
        install_parser = app_subparsers.add_parser('install', help='安装应用')
        install_parser.add_argument('ipa_path', help='IPA 文件路径')
        uninstall_parser = app_subparsers.add_parser('uninstall', help='卸载应用')
        uninstall_parser.add_argument('bundle_id', help='应用 Bundle ID')
        launch_parser = app_subparsers.add_parser('launch', help='启动应用')
        launch_parser.add_argument('bundle_id', help='应用 Bundle ID')
        kill_parser = app_subparsers.add_parser('kill', help='停止应用')
        kill_parser.add_argument('bundle_id', help='应用 Bundle ID')
        
        # 性能监控命令
        monitor_parser = subparsers.add_parser('monitor', help='性能监控')
        monitor_subparsers = monitor_parser.add_subparsers(dest='monitor_command')
        system_parser = monitor_subparsers.add_parser('system', help='监控系统性能')
        system_parser.add_argument('--filter', default='all', choices=['all', 'memory', 'cpu', 'disk', 'network'], help='过滤条件')
        app_parser = monitor_subparsers.add_parser('app', help='监控应用性能')
        app_parser.add_argument('bundle_id', help='应用 Bundle ID')
        fps_parser = monitor_subparsers.add_parser('fps', help='监控 FPS')
        network_parser = monitor_subparsers.add_parser('network', help='监控网络')
        
        # 数据采集命令
        collect_parser = subparsers.add_parser('collect', help='数据采集')
        collect_parser.add_argument('--bundle_id', help='应用 Bundle ID')
        collect_parser.add_argument('--duration', type=int, default=60, help='采集持续时间（秒）')
        collect_parser.add_argument('--interval', type=int, default=1000, help='采样间隔（毫秒）')
        collect_parser.add_argument('--output', default='idb_data', help='输出文件路径（不含扩展名）')
        
        # 高级功能命令
        advanced_parser = subparsers.add_parser('advanced', help='高级功能')
        advanced_subparsers = advanced_parser.add_subparsers(dest='advanced_command')
        screenshot_parser = advanced_subparsers.add_parser('screenshot', help='拍摄屏幕截图')
        screenshot_parser.add_argument('--output', default='screenshot.png', help='输出文件路径')
        pcapd_parser = advanced_subparsers.add_parser('pcapd', help='网络抓包')
        pcapd_parser.add_argument('outfile', help='输出文件路径')
        location_parser = advanced_subparsers.add_parser('location', help='设置模拟定位')
        location_parser.add_argument('latitude', type=float, help='纬度')
        location_parser.add_argument('longitude', type=float, help='经度')
        clear_location_parser = advanced_subparsers.add_parser('clear_location', help='清除模拟定位')
        
        # 设备状态模拟命令
        condition_parser = subparsers.add_parser('condition', help='设备状态模拟')
        condition_subparsers = condition_parser.add_subparsers(dest='condition_command')
        condition_get_parser = condition_subparsers.add_parser('get', help='获取设备条件诱导器配置')
        condition_set_parser = condition_subparsers.add_parser('set', help='设置设备条件诱导器')
        condition_set_parser.add_argument('-c', '--condition_id', required=True, help='条件 ID，例如: SlowNetworkCondition, ThermalCondition')
        condition_set_parser.add_argument('-p', '--profile_id', default='', help='配置文件 ID，例如: SlowNetwork2GUrban, ThermalCritical')
        
        # 应用生命周期命令
        lifecycle_parser = subparsers.add_parser('lifecycle', help='应用生命周期监控')
        lifecycle_subparsers = lifecycle_parser.add_subparsers(dest='lifecycle_command')
        lifecycle_notifications_parser = lifecycle_subparsers.add_parser('notifications', help='监控应用通知（启动、退出、后台等状态）')
        lifecycle_analyze_parser = lifecycle_subparsers.add_parser('analyze', help='分析应用启动生命周期')
        lifecycle_analyze_parser.add_argument('-b', '--bundle_id', required=True, help='应用的 Bundle ID')
        
        # 系统命令
        system_parser = subparsers.add_parser('system', help='系统命令')
        system_subparsers = system_parser.add_subparsers(dest='system_command')
        syslog_parser = system_subparsers.add_parser('syslog', help='获取系统日志')
        battery_parser = system_subparsers.add_parser('battery', help='获取电池信息')
        crash_parser = system_subparsers.add_parser('crash', help='崩溃日志')
        crash_parser.add_argument('action', choices=['list', 'export', 'delete'], help='操作')
        crash_parser.add_argument('--name', help='崩溃日志名称')
        
        args = parser.parse_args()
        
        # 创建 IDBTool 实例
        tool = IDBTool(udid=args.udid, network=args.network, address=args.address)
        
        # 处理命令
        if args.command == 'device':
            if args.device_command == 'list':
                devices = tool.get_devices()
                for device in devices:
                    print(f"UDID: {device.get('UniqueDeviceID')}, Name: {device.get('DeviceName')}")
            elif args.device_command == 'info':
                info = tool.get_device_info()
                print(json.dumps(info, ensure_ascii=False, indent=2))
        
        elif args.command == 'app':
            if args.app_command == 'list':
                apps = tool.list_apps()
                for app in apps:
                    print(f"Bundle ID: {app.get('CFBundleIdentifier')}, Name: {app.get('CFBundleDisplayName', app.get('CFBundleName'))}")
            elif args.app_command == 'install':
                result = tool.install_app(args.ipa_path)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.app_command == 'uninstall':
                result = tool.uninstall_app(args.bundle_id)
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.app_command == 'launch':
                pid = tool.launch_app(args.bundle_id)
                print(f"应用已启动，PID: {pid}")
            elif args.app_command == 'kill':
                tool.kill_app(args.bundle_id)
                print(f"应用已停止")
        
        elif args.command == 'monitor':
            def callback(data):
                print(json.dumps(data, ensure_ascii=False))
            
            if args.monitor_command == 'system':
                tool.start_system_monitor(callback, filter=args.filter)
            elif args.monitor_command == 'app':
                tool.start_app_monitor(args.bundle_id, callback)
            elif args.monitor_command == 'fps':
                tool.start_fps_monitor(callback)
            elif args.monitor_command == 'network':
                tool.start_network_monitor(callback)
        
        elif args.command == 'collect':
            tool.start_data_collection(
                bundle_id=args.bundle_id,
                duration=args.duration,
                interval=args.interval,
                output_file=args.output
            )
        
        elif args.command == 'advanced':
            if args.advanced_command == 'screenshot':
                tool.take_screenshot(args.output)
            elif args.advanced_command == 'pcapd':
                tool.start_pcapd(args.outfile)
            elif args.advanced_command == 'location':
                tool.set_simulate_location(args.latitude, args.longitude)
            elif args.advanced_command == 'clear_location':
                tool.clear_simulate_location()
        
        elif args.command == 'condition':
            if args.condition_command == 'get':
                config = tool.get_condition_inducer()
                print(json.dumps(config, ensure_ascii=False, indent=2))
            elif args.condition_command == 'set':
                result = tool.set_condition_inducer(args.condition_id, args.profile_id)
                print(json.dumps(result, ensure_ascii=False, indent=2))
        
        elif args.command == 'lifecycle':
            if args.lifecycle_command == 'notifications':
                def callback(data):
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                tool.start_app_notifications_monitor(callback)
            elif args.lifecycle_command == 'analyze':
                tool.analyze_app_lifecycle(args.bundle_id)
        
        elif args.command == 'system':
            if args.system_command == 'syslog':
                def callback(line):
                    print(line)
                tool.get_syslog(callback)
            elif args.system_command == 'battery':
                info = tool.get_battery_info()
                print(json.dumps(info, ensure_ascii=False, indent=2))
            elif args.system_command == 'crash':
                if args.action == 'list':
                    logs = tool.list_crash_logs()
                    for log in logs:
                        print(log)
                elif args.action == 'export' and args.name:
                    tool.export_crash_log(args.name)
                elif args.action == 'delete' and args.name:
                    tool.delete_crash_log(args.name)
