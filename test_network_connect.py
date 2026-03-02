#!/usr/bin/env python3
"""
测试网络设备连接
"""
import sys
import os

# 添加当前目录和py-ios-device-main到Python路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

from IDBTOOL import IDBTool

def test_network_connection():
    """测试网络设备连接"""
    print("测试网络设备连接...")
    
    try:
        # 使用之前测试过的iOS设备IP地址
        ios_ip = "192.168.40.245"
        device_udid = "fc68768d07c970f50c6f83c5b9c3c2eefa82c004"
        
        print(f"\n=== 测试网络设备连接: {ios_ip} ===")
        print(f"设备UDID: {device_udid}")
        
        # 测试网络设备连接
        tool = IDBTool(udid=ios_ip, network=True)
        
        # 获取设备信息
        device_info = tool.get_device_info()
        print("\n成功通过网络获取设备信息:")
        print(f"设备名称: {device_info.get('DeviceName', 'Unknown')}")
        print(f"设备型号: {device_info.get('ProductType', 'Unknown')}")
        print(f"iOS版本: {device_info.get('ProductVersion', 'Unknown')}")
        print(f"设备UDID: {device_info.get('UniqueDeviceID', 'Unknown')}")
        
        print("\n✅ 网络连接测试成功！")
        return True
        
    except Exception as e:
        print(f"\n❌ 网络连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    test_network_connection()

if __name__ == "__main__":
    main()
