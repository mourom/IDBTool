#!/usr/bin/env python3
"""
测试修复后的网络连接功能
"""
import sys
import os

# 添加当前目录和py-ios-device-main到Python路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

from IDBTOOL import IDBTool

def test_network_connection():
    print("测试修复后的网络连接功能...")
    
    # 测试网络设备连接
    print("\n=== 测试网络设备连接 ===")
    try:
        # 使用已知的iOS设备IP地址
        ios_ip = "192.168.40.245"
        
        print(f"尝试连接到网络设备: {ios_ip}")
        tool = IDBTool(udid=ios_ip, network=True)
        
        # 获取设备信息
        device_info = tool.get_device_info()
        print("\n成功获取设备信息:")
        print(f"设备名称: {device_info.get('DeviceName', 'Unknown')}")
        print(f"设备型号: {device_info.get('ProductType', 'Unknown')}")
        print(f"iOS版本: {device_info.get('ProductVersion', 'Unknown')}")
        print(f"设备UDID: {device_info.get('UniqueDeviceID', 'Unknown')}")
        
        print("\n网络连接测试成功！")
    except Exception as e:
        print(f"网络连接测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_network_connection()
