#!/usr/bin/env python3
"""
测试通过USB连接启用网络调试
"""
import sys
import os

# 添加当前目录和py-ios-device-main到Python路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

from IDBTOOL import IDBTool

def test_usb_connection():
    """测试USB连接并启用网络调试"""
    print("测试通过USB连接启用网络调试...")
    
    try:
        # 首先尝试USB连接
        print("\n=== 测试USB设备连接 ===")
        tool = IDBTool(network=False)
        
        # 获取设备信息
        device_info = tool.get_device_info()
        print("成功通过USB连接获取设备信息:")
        print(f"设备名称: {device_info.get('DeviceName', 'Unknown')}")
        print(f"设备型号: {device_info.get('ProductType', 'Unknown')}")
        print(f"iOS版本: {device_info.get('ProductVersion', 'Unknown')}")
        print(f"设备UDID: {device_info.get('UniqueDeviceID', 'Unknown')}")
        
        # 尝试启用网络调试
        print("\n=== 尝试启用网络调试 ===")
        from ios_device.util.lockdown import LockdownClient
        
        lockdown = LockdownClient(udid=device_info.get('UniqueDeviceID'))
        # 启用网络连接
        lockdown.enable_wireless(True)
        print("✅ 成功启用网络调试！")
        
        # 获取WiFi地址
        wifi_address = lockdown.get_value(key="WiFiAddress")
        print(f"设备WiFi地址: {wifi_address}")
        
        print("\n请断开USB连接，然后按Enter键继续测试网络连接...")
        input()
        
        # 测试网络连接
        print("\n=== 测试网络连接 ===")
        network_tool = IDBTool(udid=wifi_address, network=True)
        network_info = network_tool.get_device_info()
        print("成功通过网络连接获取设备信息:")
        print(f"设备名称: {network_info.get('DeviceName', 'Unknown')}")
        print(f"设备型号: {network_info.get('ProductType', 'Unknown')}")
        print(f"iOS版本: {network_info.get('ProductVersion', 'Unknown')}")
        print(f"设备UDID: {network_info.get('UniqueDeviceID', 'Unknown')}")
        
        print("\n✅ 网络连接测试成功！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    test_usb_connection()

if __name__ == "__main__":
    main()
