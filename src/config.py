#!/usr/bin/env python3
"""
配置模块
"""

import os
import yaml
from pathlib import Path

class Config:
    def __init__(self):
        # 配置文件路径
        self.config_dir = Path.home() / '.podcli'
        self.config_file = self.config_dir / 'config.yaml'
        
        # 默认配置
        self.default_config = {
            'whisper': {
                'model': 'base',          # tiny/base/small/medium/large
                'device': 'cpu',          # cpu/cuda
                'language': 'auto'        # auto/en/zh 等
            },
            'output': {
                'dir': str(Path.home() / 'Podcasts'),  # 输出根目录
                'save_audio': True        # 是否保留音频文件
            }
        }
        
        # 加载配置
        self.config = self._load_config()
        
        # 初始化属性
        self.whisper_model = self.config['whisper']['model']
        self.whisper_device = self.config['whisper']['device']
        self.whisper_language = self.config['whisper']['language']
        self.output_dir = Path(self.config['output']['dir'])
        self.save_audio = self.config['output']['save_audio']
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self):
        """加载配置文件"""
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 如果配置文件不存在，创建默认配置
        if not self.config_file.exists():
            self._save_config(self.default_config)
            return self.default_config
        
        # 读取配置文件
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 合并默认配置
            return self._merge_configs(self.default_config, config)
        except Exception as e:
            print(f"配置文件读取失败: {e}")
            return self.default_config
    
    def _save_config(self, config):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            print(f"配置文件保存失败: {e}")
    
    def _merge_configs(self, default, user):
        """合并配置"""
        if not isinstance(user, dict):
            return default
        
        merged = default.copy()
        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    def update_config(self, key, value):
        """更新配置"""
        # 简单的键值更新（支持嵌套键，如 'whisper.model'）
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self._save_config(self.config)
        
        # 更新属性
        self.__init__()
    
    def get_config_path(self):
        """获取配置文件路径"""
        return str(self.config_file)
