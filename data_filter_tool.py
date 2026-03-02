#!/usr/bin/env python3
import json
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime
import os

class DataFilterTool:
    def __init__(self, root):
        self.root = root
        self.root.title("IDB数据筛选工具")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        
        # 数据存储
        self.data = []
        self.filtered_data = []
        
        # 展开/收起状态跟踪
        self.expanded_states = {}
        
        # 字段列表项映射（显示文本 -> 原始路径）
        self.field_map = {}
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建顶部工具栏
        self.toolbar = ttk.Frame(self.main_frame)
        self.toolbar.pack(fill=tk.X, pady=5)
        
        # 加载文件按钮
        self.load_btn = ttk.Button(self.toolbar, text="加载数据文件", command=self.load_file)
        self.load_btn.pack(side=tk.LEFT, padx=5)
        
        # 导出CSV按钮
        self.export_btn = ttk.Button(self.toolbar, text="导出CSV", command=self.export_csv, state=tk.DISABLED)
        self.export_btn.pack(side=tk.RIGHT, padx=5)
        
        # 创建筛选框架
        self.filter_frame = ttk.LabelFrame(self.main_frame, text="数据筛选", padding="10")
        self.filter_frame.pack(fill=tk.X, pady=5)
        
        # 数据类型选择
        self.data_types = {
            "disk": "磁盘",
            "network": "网络",
            "memory": "内存",
            "cpu": "CPU",
            "battery": "电池",
            "gpu": "GPU"
        }
        
        # 字段中文说明映射
        self.field_descriptions = {
            # 基础字段
            "timestamp": "时间戳",
            "elapsed_time": "经过时间",
            
            # disk 字段
            "Data Read": "数据读取总量",
            "Data Read/sec": "每秒数据读取量",
            "Data Written": "数据写入总量",
            "Data Written/sec": "每秒数据写入量",
            "Reads in": "读取次数",
            "Reads in/sec": "每秒读取次数",
            "Writes Out": "写入次数",
            "Writes Out/sec": "每秒写入次数",
            
            # network 字段
            "Data Received": "接收数据总量",
            "Data Received/sec": "每秒接收数据量",
            "Data Sent": "发送数据总量",
            "Data Sent/sec": "每秒发送数据量",
            "Packets in": "接收数据包数",
            "Packets in/sec": "每秒接收数据包数",
            "Packets Out": "发送数据包数",
            "Packets Out/sec": "每秒发送数据包数",
            
            # memory 字段
            "App Memory": "应用内存",
            "Free Memory": "空闲内存",
            "Cached Files": "缓存文件",
            "Compressed": "压缩内存",
            "Memory Used": "已用内存",
            "Wired Memory": "有线内存",
            "Swap Used": "交换空间使用",
            
            # cpu 字段
            "CPU_NiceLoad": "CPU Nice负载",
            "CPU_SystemLoad": "CPU 系统负载",
            "CPU_TotalLoad": "CPU 总负载",
            "CPU_UserLoad": "CPU 用户负载",
            
            # battery 字段
            "AbsoluteCapacity": "绝对容量",
            "AdapterDetails": "适配器详情",
            "AdapterInfo": "适配器信息",
            "Amperage": "电流",
            "AppleChargeRateLimitIndex": "苹果充电速率限制索引",
            "AppleRawAdapterDetails": "苹果原始适配器详情",
            "AppleRawBatteryVoltage": "苹果原始电池电压",
            "AppleRawCurrentCapacity": "苹果原始当前容量",
            "AppleRawExternalConnected": "苹果原始外部连接状态",
            "AppleRawMaxCapacity": "苹果原始最大容量",
            "AtCriticalLevel": "是否处于临界水平",
            "AvgTimeToEmpty": "平均剩余时间",
            "BatteryCellDisconnectCount": "电池单元断开计数",
            "BatteryData": "电池数据",
            "BatteryInstalled": "电池是否安装",
            "BatteryInvalidWakeSeconds": "电池无效唤醒秒数",
            "BestAdapterIndex": "最佳适配器索引",
            "BootPathUpdated": "启动路径更新时间",
            "BootVoltage": "启动电压",
            "CarrierMode": "运营商模式",
            "ChargerConfiguration": "充电器配置",
            "ChargerData": "充电器数据",
            "ChargingOverride": "充电覆盖",
            "CurrentCapacity": "当前容量",
            "CycleCount": "循环次数",
            "DesignCapacity": "设计容量",
            "ExternalChargeCapable": "外部充电能力",
            "ExternalConnected": "外部连接状态",
            "FullPathUpdated": "完整路径更新时间",
            "FullyCharged": "是否充满",
            "GasGaugeFirmwareVersion": "电量计固件版本",
            "IOGeneralInterest": "IO通用兴趣",
            "IOReportLegend": "IOReport图例",
            "IOReportLegendPublic": "IOReport公共图例",
            "InductiveData": "感应数据",
            "InstantAmperage": "即时电流",
            "IsCharging": "是否正在充电",
            "KioskMode": " kiosk模式",
            "Location": "位置",
            "ManufacturerData": "制造商数据",
            "MaxCapacity": "最大容量",
            "NominalChargeCapacity": "标称充电容量",
            "PostChargeWaitSeconds": "充电后等待秒数",
            "PostDischargeWaitSeconds": "放电后等待秒数",
            "Serial": "序列号",
            "Temperature": "温度",
            "TimeRemaining": "剩余时间",
            "UpdateTime": "更新时间",
            "UserVisiblePathUpdated": "用户可见路径更新时间",
            "VirtualTemperature": "虚拟温度",
            "Voltage": "电压",
            "built-in": "内置",
            
            # gpu 字段
            "gpu[0]": "GPU核心数",
            "gpu[1]": "GPU内存使用"
        }
        
        self.type_vars = {}
        self.type_checkbuttons = {}
        
        type_frame = ttk.Frame(self.filter_frame)
        type_frame.pack(fill=tk.X, pady=5)
        
        for i, (key, value) in enumerate(self.data_types.items()):
            var = tk.BooleanVar(value=False)
            self.type_vars[key] = var
            
            btn = ttk.Checkbutton(type_frame, text=value, variable=var, command=self.update_fields)
            btn.grid(row=0, column=i, padx=10)
            self.type_checkbuttons[key] = btn
        
        # 字段选择 - 使用Treeview代替Listbox，以树形结构展示
        self.fields_frame = ttk.LabelFrame(self.filter_frame, text="字段选择", padding="10")
        self.fields_frame.pack(fill=tk.X, pady=5)
        
        # 创建Treeview组件
        self.fields_tree = ttk.Treeview(self.fields_frame, selectmode="extended")
        self.fields_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 添加滚动条
        scrollbar_y = ttk.Scrollbar(self.fields_frame, orient=tk.VERTICAL, command=self.fields_tree.yview)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollbar_x = ttk.Scrollbar(self.fields_frame, orient=tk.HORIZONTAL, command=self.fields_tree.xview)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.fields_tree.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 设置Treeview列
        self.fields_tree["columns"] = ("description",)
        self.fields_tree["show"] = "tree"
        self.fields_tree.heading("#0", text="字段路径")
        self.fields_tree.heading("description", text="说明")
        
        # 字段路径到Treeview节点ID的映射
        self.path_to_item = {}
        
        # Treeview节点ID到字段路径的映射
        self.item_to_path = {}
        
        # 选中的字段路径
        self.selected_fields = []
        
        # 时间范围筛选
        time_frame = ttk.Frame(self.filter_frame)
        time_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(time_frame, text="时间范围筛选:").pack(side=tk.LEFT, padx=5)
        
        self.time_filter_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(time_frame, text="启用", variable=self.time_filter_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(time_frame, text="起始时间:").pack(side=tk.LEFT, padx=5)
        self.start_time_entry = ttk.Entry(time_frame, width=20)
        self.start_time_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(time_frame, text="结束时间:").pack(side=tk.LEFT, padx=5)
        self.end_time_entry = ttk.Entry(time_frame, width=20)
        self.end_time_entry.pack(side=tk.LEFT, padx=5)
        
        # 应用筛选按钮
        self.apply_filter_btn = ttk.Button(self.filter_frame, text="应用筛选", command=self.apply_filter, state=tk.DISABLED)
        self.apply_filter_btn.pack(side=tk.RIGHT, padx=5)
        
        # 预览框架
        self.preview_frame = ttk.LabelFrame(self.main_frame, text="数据预览", padding="10")
        self.preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建表格
        self.tree = ttk.Treeview(self.preview_frame)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar_x = ttk.Scrollbar(self.preview_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        scrollbar_y = ttk.Scrollbar(self.preview_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.config(xscrollcommand=scrollbar_x.set, yscrollcommand=scrollbar_y.set)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def load_file(self):
        """加载JSON数据文件"""
        file_path = filedialog.askopenfilename(
            title="选择数据文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(__file__))
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            self.status_var.set(f"成功加载 {len(self.data)} 条数据")
            
            # 启用筛选按钮
            self.apply_filter_btn.config(state=tk.NORMAL)
            
            # 更新时间范围输入框
            if self.data:
                start_time = datetime.datetime.fromtimestamp(self.data[0]['timestamp'])
                end_time = datetime.datetime.fromtimestamp(self.data[-1]['timestamp'])
                
                self.start_time_entry.delete(0, tk.END)
                self.start_time_entry.insert(0, start_time.strftime("%Y-%m-%d %H:%M:%S"))
                
                self.end_time_entry.delete(0, tk.END)
                self.end_time_entry.insert(0, end_time.strftime("%Y-%m-%d %H:%M:%S"))
            
            # 重置字段列表
            self.update_fields()
            
        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败: {str(e)}")
            self.status_var.set("加载失败")
    
    def update_fields(self):
        """根据选择的数据类型更新字段列表"""
        # 保存当前的选择
        selected_paths = []
        for item in self.fields_tree.selection():
            if item in self.item_to_path:
                selected_paths.append(self.item_to_path[item])
        
        # 清空Treeview
        for item in self.fields_tree.get_children():
            self.fields_tree.delete(item)
        
        # 重置映射
        self.path_to_item = {}
        self.item_to_path = {}
        
        # 获取选中的数据类型
        selected_types = [key for key, var in self.type_vars.items() if var.get()]
        
        if not selected_types:
            return
        
        # 如果没有数据，无法更新字段
        if not self.data:
            return
        
        # 获取第一个数据点的结构
        first_data = self.data[0]
        
        # 添加基础字段
        timestamp_item = self.fields_tree.insert("", tk.END, text="timestamp", values=["时间戳"])
        self.path_to_item["timestamp"] = timestamp_item
        self.item_to_path[timestamp_item] = "timestamp"
        
        elapsed_item = self.fields_tree.insert("", tk.END, text="elapsed_time", values=["经过时间"])
        self.path_to_item["elapsed_time"] = elapsed_item
        self.item_to_path[elapsed_item] = "elapsed_time"
        
        # 添加选中类型的字段
        for data_type in selected_types:
            if data_type in first_data:
                # 创建数据类型节点
                type_desc = self.data_types.get(data_type, data_type)
                type_item = self.fields_tree.insert("", tk.END, text=data_type, values=[type_desc])
                self.path_to_item[data_type] = type_item
                self.item_to_path[type_item] = data_type
                
                # 递归添加子字段
                if isinstance(first_data[data_type], dict):
                    self._add_tree_fields(data_type, first_data[data_type], type_item, f"{data_type}.")
                elif isinstance(first_data[data_type], list):
                    for i in range(len(first_data[data_type])):
                        list_key = f"{data_type}[{i}]"
                        list_desc = self.field_descriptions.get(list_key, "")
                        list_item = self.fields_tree.insert(type_item, tk.END, text=f"[{i}]", values=[list_desc])
                        self.path_to_item[list_key] = list_item
                        self.item_to_path[list_item] = list_key
        
        # 恢复之前的选择
        for path in selected_paths:
            if path in self.path_to_item:
                self.fields_tree.selection_add(self.path_to_item[path])
        
        # 展开所有节点
        for item in self.fields_tree.get_children():
            self.fields_tree.item(item, open=True)
            self._expand_all_children(item)
    
    def _expand_all_children(self, parent_item):
        """递归展开所有子节点"""
        for item in self.fields_tree.get_children(parent_item):
            self.fields_tree.item(item, open=True)
            self._expand_all_children(item)
    
    def _add_tree_fields(self, data_type, data_dict, parent_item, prefix, level=1):
        """递归添加Treeview字段，构建完整的树形结构"""
        # 按字母顺序排序字段
        sorted_items = sorted(data_dict.items(), key=lambda x: x[0])
        
        for key, value in sorted_items:
            full_path = f"{prefix}{key}"
            
            # 只在一级字段显示中文翻译
            desc = ""
            if level == 1:
                desc = self.field_descriptions.get(key, "")
            
            # 创建节点，显示相对路径避免冲突
            parent_text = self.fields_tree.item(parent_item, "text")
            # 检查父节点是否是列表索引
            if parent_text.startswith("[") and parent_text.endswith("]"):
                # 如果父节点是列表索引，获取祖父节点的文本
                grandparent_item = self.fields_tree.parent(parent_item)
                if grandparent_item:
                    grandparent_text = self.fields_tree.item(grandparent_item, "text")
                    display_text = f"{grandparent_text}{parent_text}.{key}"
                else:
                    display_text = key
            else:
                # 显示相对路径，如 "parent.key"
                display_text = f"{parent_text}.{key}" if parent_text and not parent_text.startswith("[") else key
            
            item = self.fields_tree.insert(parent_item, tk.END, text=display_text, values=[desc])
            self.path_to_item[full_path] = item
            self.item_to_path[item] = full_path
            
            # 递归处理嵌套字典
            if isinstance(value, dict):
                self._add_tree_fields(data_type, value, item, f"{full_path}.", level + 1)
            # 处理嵌套列表
            elif isinstance(value, list):
                for i, list_item_value in enumerate(value):
                    list_item_path = f"{full_path}[{i}]"
                    list_item = self.fields_tree.insert(item, tk.END, text=f"[{i}]", values=[""])
                    self.path_to_item[list_item_path] = list_item
                    self.item_to_path[list_item] = list_item_path
                    
                    # 如果列表项是字典，递归处理
                    if isinstance(list_item_value, dict):
                        self._add_tree_fields(data_type, list_item_value, list_item, f"{list_item_path}.", level + 1)
    

    
    def apply_filter(self):
        """应用筛选条件"""
        if not self.data:
            messagebox.showwarning("警告", "请先加载数据文件")
            return
        
        # 获取选中的字段
        selected_items = self.fields_tree.selection()
        selected_fields = []
        selected_paths = []
        
        for item in selected_items:
            if item in self.item_to_path:
                path = self.item_to_path[item]
                selected_paths.append(path)
                # 获取字段的显示文本
                text = self.fields_tree.item(item, "text")
                values = self.fields_tree.item(item, "values")
                desc = values[0] if values else ""
                
                if desc:
                    selected_fields.append(f"{path} ({desc})")
                else:
                    selected_fields.append(path)
        
        if not selected_fields:
            messagebox.showwarning("警告", "请至少选择一个字段")
            return
        
        # 应用时间范围筛选
        if self.time_filter_var.get():
            try:
                start_time_str = self.start_time_entry.get()
                end_time_str = self.end_time_entry.get()
                
                start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S").timestamp()
                end_time = datetime.datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S").timestamp()
                
                filtered_data = [item for item in self.data if start_time <= item['timestamp'] <= end_time]
            except Exception as e:
                messagebox.showerror("错误", f"时间格式错误: {str(e)}")
                return
        else:
            filtered_data = self.data
        
        # 转换字段格式
        self.filtered_data = []
        
        for item in filtered_data:
            row = {}
            
            for i, field in enumerate(selected_fields):
                path = selected_paths[i]
                
                # 处理基础字段
                if path == "timestamp":
                    # 使用完整路径作为键，确保唯一性
                    timestamp_value = item.get("timestamp", "")
                    # 转换为人类可读的时间字符串
                    if timestamp_value and isinstance(timestamp_value, (int, float)):
                        try:
                            time_str = datetime.datetime.fromtimestamp(timestamp_value).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            row[path] = time_str
                        except:
                            row[path] = timestamp_value
                    else:
                        row[path] = timestamp_value
                elif path == "elapsed_time":
                    row[path] = item.get("elapsed_time", "")
                else:
                    # 处理嵌套字段
                    if "." in path:
                        # 处理多级嵌套
                        parts = path.split(".")
                        data_type = parts[0]
                        
                        if data_type in item:
                            # 从第一层开始遍历
                            current_data = item[data_type]
                            valid_path = True
                            
                            # 遍历剩余的路径部分
                            for part in parts[1:]:
                                # 检查是否包含列表索引
                                if "[" in part and "]" in part:
                                    # 处理列表索引，如 device_info[0]
                                    list_part = part.split("[")
                                    list_name = list_part[0]
                                    index = int(list_part[1].rstrip("]"))
                                    
                                    if isinstance(current_data, dict) and list_name in current_data:
                                        list_data = current_data[list_name]
                                        if isinstance(list_data, list) and index < len(list_data):
                                            current_data = list_data[index]
                                        else:
                                            valid_path = False
                                            break
                                    else:
                                        valid_path = False
                                        break
                                elif isinstance(current_data, dict) and part in current_data:
                                    current_data = current_data[part]
                                else:
                                    valid_path = False
                                    break
                            
                            if valid_path:
                                # 使用完整路径作为键，确保唯一性
                                row[path] = current_data
                    elif "[" in path and "]" in path:
                        # 处理列表字段
                        parts = path.split("[")
                        data_type = parts[0]
                        index = int(parts[1].rstrip("]"))
                        
                        if data_type in item and isinstance(item[data_type], list) and index < len(item[data_type]):
                            # 使用完整路径作为键，确保唯一性
                            row[path] = item[data_type][index]
            
            self.filtered_data.append(row)
        
        # 更新预览表格
        self.update_preview()
        
        # 启用导出按钮
        self.export_btn.config(state=tk.NORMAL)
        
        self.status_var.set(f"筛选完成，共 {len(self.filtered_data)} 条数据")
    
    def update_preview(self):
        """更新预览表格"""
        # 清空现有表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not self.filtered_data:
            return
        
        # 获取列名
        columns = list(self.filtered_data[0].keys())
        
        # 设置表格列
        self.tree["columns"] = columns
        self.tree["show"] = "headings"
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        # 添加数据
        for i, row in enumerate(self.filtered_data[:100]):  # 只显示前100条
            values = [row.get(col, "") for col in columns]
            self.tree.insert("", tk.END, values=values)
    
    def export_csv(self):
        """导出为CSV文件"""
        if not self.filtered_data:
            messagebox.showwarning("警告", "请先应用筛选条件")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="导出CSV文件",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            initialdir=os.path.dirname(os.path.abspath(__file__))
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                if self.filtered_data:
                    writer = csv.DictWriter(f, fieldnames=self.filtered_data[0].keys())
                    writer.writeheader()
                    writer.writerows(self.filtered_data)
            
            messagebox.showinfo("成功", f"数据已成功导出到 {file_path}")
            self.status_var.set(f"导出成功: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
            self.status_var.set("导出失败")

if __name__ == "__main__":
    root = tk.Tk()
    app = DataFilterTool(root)
    root.mainloop()