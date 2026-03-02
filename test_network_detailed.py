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

def test_port_scan(ip, start_port=50000, end_port=60000, step=1000):
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

def test_pyidevice_cli(ip):
    """测试使用py-ios-device的命令行工具"""
    print(f"\n=== 测试py-ios-device命令行工具 ===")
    try:
        # 运行pyidevice命令
        cmd = f"python -m ios_device device info -u {ip} -n"
        print(f"执行命令: {cmd}")
        
        result = subprocess.run(
            cmd, 
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print("命令输出:")
        print(result.stdout)
        print("命令错误:")
        print(result.stderr)
        
        if result.returncode == 0:
            print("✅ py-ios-device命令执行成功！")
            return True
        else:
            print("❌ py-ios-device命令执行失败！")
            return False
    except Exception as e:
        print(f"❌ 执行命令失败: {e}")
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
    
    # 3. 测试py-ios-device命令行工具
    test_pyidevice_cli(ios_ip)
    
    print("\n=== 测试完成 ===")
    print(f"设备IP: {ios_ip}")
    print(f"开放端口: {open_ports}")

if __name__ == "__main__":
    main()
