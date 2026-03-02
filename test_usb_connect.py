#!/usr/bin/env python3
"""
测试USB设备连接
"""
import sys
import os

# 添加当前目录和py-ios-device-main到Python路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

from IDBTOOL import IDBTool

def test_usb_connection():
    """测试USB设备连接"""
    print("测试USB设备连接...")
    
    try:
        # 测试USB设备连接
        print("\n=== 测试USB设备连接 ===")
        tool = IDBTool(network=False)
        
        # 获取设备列表
        devices = tool.get_devices()
        print(f"找到 {len(devices)} 个USB设备:")
        for i, device in enumerate(devices):
            print(f"设备 {i+1}:")
            print(f"  UDID: {device.get('UniqueDeviceID')}")
            print(f"  名称: {device.get('DeviceName')}")
            print(f"  连接类型: {device.get('ConnectionType')}")
        
        if not devices:
            print("没有找到USB设备！")
            return False
        
        # 获取设备信息
        device_info = tool.get_device_info()
        print("\n成功获取设备信息:")
        print(f"设备名称: {device_info.get('DeviceName', 'Unknown')}")
        print(f"设备型号: {device_info.get('ProductType', 'Unknown')}")
        print(f"iOS版本: {device_info.get('ProductVersion', 'Unknown')}")
        print(f"设备UDID: {device_info.get('UniqueDeviceID', 'Unknown')}")
        print(f"设备ID: {device_info.get('DeviceID', 'Unknown')}")
        
        print("\n✅ USB设备连接测试成功！")
        return device_info
    except Exception as e:
        print(f"❌ USB设备连接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    return test_usb_connection()

if __name__ == "__main__":
    main()
