#!/usr/bin/env python3
"""
详细测试网络连接功能
"""
import sys
import os
import socket
import subprocess

# 添加当前目录和py-ios-device-main到Python路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'py-ios-device-main'))

def test_ping(ip):
    """测试设备是否可达"""
    print(f"\n=== 测试设备可达性: {ip} ===")
    try:
        # 使用ping命令测试设备是否可达
        result = subprocess.run(
            ['ping', '-n', '4', ip],
            capture_output=True,
            text=True,
            timeout=10
        )
        print("Ping测试结果:")
        print(result.stdout)
        if result.returncode == 0:
            print("✅ 设备可达！")
            return True
        else:
            print("❌ 设备不可达！")
            return False
    except Exception as e:
        print(f"❌ Ping测试失败: {e}")
        return False

def test_port_scan(ip, start_port=50000, end_port=60000, step=500):
    """测试设备的端口是否开放"""
    print(f"\n=== 测试端口扫描: {ip} ===")
    open_ports = []
    
    for port in range(start_port, end_port + 1, step):
        print(f"测试端口 {port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            result = sock.connect_ex((ip, port))
            if result == 0:
                print(f"✅ 端口 {port} 开放！")
                open_ports.append(port)
            sock.close()
        except Exception as e:
            print(f"❌ 测试端口 {port} 失败: {e}")
            sock.close()
    
    if open_ports:
        print(f"\n找到 {len(open_ports)} 个开放端口: {open_ports}")
        return open_ports
    else:
        print("❌ 没有找到开放的端口！")
        return []

def test_network_connection_with_port(ip, port):
    """测试使用特定端口连接网络设备"""
    print(f"\n=== 测试网络连接: {ip}:{port} ===")
    
    try:
        from IDBTOOL import IDBTool
        
        # 使用特定端口连接
        tool = IDBTool(udid=ip, network=True, address=f"{ip}:{port}")
        
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
        return False

def main():
    print("详细测试网络连接功能...")
    
    # 测试设备IP
    ios_ip = "192.168.40.245"
    
    # 1. 测试设备可达性
    if not test_ping(ios_ip):
        print("\n设备不可达，无法继续测试！")
        return
    
    # 2. 测试端口扫描
    open_ports = test_port_scan(ios_ip)
    
    # 3. 测试使用开放端口连接
    if open_ports:
        for port in open_ports:
            if test_network_connection_with_port(ios_ip, port):
                break
    else:
        # 尝试常用的iOS网络调试端口
        common_ports = [50000, 50001, 50010, 55555, 60000]
        print("\n=== 尝试常用端口 ===")
        for port in common_ports:
            if test_network_connection_with_port(ios_ip, port):
                break
    
    print("\n=== 测试完成 ===")
    print(f"设备IP: {ios_ip}")
    print(f"开放端口: {open_ports if open_ports else '无'}")

if __name__ == "__main__":
    main()
