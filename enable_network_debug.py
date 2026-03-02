#!/usr/bin/env python3
"""
通过USB连接启用网络调试功能
"""
import sys
import os

# 添加当前目录和py-ios-device-main到Python路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

def enable_network_debug(udid):
    """通过USB连接启用网络调试功能"""
    print("通过USB连接启用网络调试功能...")
    
    try:
        from ios_device.util.lockdown import LockdownClient
        
        print(f"\n=== 启用网络调试: {udid} ===")
        
        # 创建LockdownClient实例
        lockdown = LockdownClient(udid=udid)
        
        # 启用网络连接
        print("正在启用网络调试...")
        lockdown.enable_wireless(True)
        print("✅ 成功启用网络调试！")
        
        # 获取WiFi地址
        wifi_address = lockdown.get_value(key="WiFiAddress")
        print(f"\n设备WiFi地址: {wifi_address}")
        
        # 获取设备信息
        device_info = lockdown.get_value()
        print(f"设备名称: {device_info.get('DeviceName', 'Unknown')}")
        print(f"iOS版本: {device_info.get('ProductVersion', 'Unknown')}")
        
        print("\n=== 网络调试启用成功 ===")
        print("现在可以断开USB连接，通过网络连接设备")
        print(f"网络连接命令示例: python IDBTOOL.py -u {wifi_address} -n device info")
        
        return wifi_address
        
    except Exception as e:
        print(f"❌ 启用网络调试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    # 使用之前获取的设备UDID
    device_udid = "fc68768d07c970f50c6f83c5b9c3c2eefa82c004"
    enable_network_debug(device_udid)

if __name__ == "__main__":
    main()
