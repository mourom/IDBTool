#!/usr/bin/env python3
"""
测试网络设备发现功能
"""
import sys
import os

# 添加py-ios-device-main到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

from ios_device.util.usbmux import USBMux

def test_network_discovery():
    print("测试网络设备发现...")
    
    # 测试USB设备发现
    print("\n=== 测试USB设备发现 ===")
    try:
        with USBMux() as usb_mux:
            devices = usb_mux.get_devices(network=False)
            print(f"找到 {len(devices)} 个USB设备:")
            for i, device in enumerate(devices):
                print(f"设备 {i+1}: {device}")
    except Exception as e:
        print(f"USB设备发现失败: {e}")
    
    # 测试网络设备发现
    print("\n=== 测试网络设备发现 ===")
    try:
        with USBMux() as usb_mux:
            # 清空之前的设备列表
            usb_mux.devices = []
            devices = usb_mux.get_devices(network=True)
            print(f"找到 {len(devices)} 个网络设备:")
            for i, device in enumerate(devices):
                print(f"设备 {i+1}: {device}")
                print(f"  设备ID: {device.device_id}")
                print(f"  序列号: {device.serial}")
                print(f"  连接类型: {device.connection_type}")
    except Exception as e:
        print(f"网络设备发现失败: {e}")

if __name__ == "__main__":
    test_network_discovery()
