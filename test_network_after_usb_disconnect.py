#!/usr/bin/env python3
"""
断开USB后测试网络设备连接
"""
import sys
import os
import time

# 添加当前目录和py-ios-device-main到Python路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

def test_network_after_usb_disconnect():
    """断开USB后测试网络设备连接"""
    print("断开USB后测试网络设备连接...")
    
    # 提示用户断开USB连接
    print("\n=== 准备测试 ===")
    print("请断开iOS设备的USB连接，然后按Enter键继续...")
    input()
    
    # 等待几秒钟让设备切换到网络模式
    print("\n等待设备切换到网络模式...")
    time.sleep(5)
    
    try:
        # 使用之前测试过的iOS设备IP地址
        ios_ip = "192.168.40.245"
        device_udid = "fc68768d07c970f50c6f83c5b9c3c2eefa82c004"
        
        print(f"\n=== 测试网络设备连接: {ios_ip} ===")
        print(f"设备UDID: {device_udid}")
        
        # 测试网络设备连接
        from IDBTOOL import IDBTool
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
    test_network_after_usb_disconnect()

if __name__ == "__main__":
    main()
