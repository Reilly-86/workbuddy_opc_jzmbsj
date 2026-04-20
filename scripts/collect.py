#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2 数据采集模块（骨架）

目标：从上海各数据源自动抓取在建项目信息
当前状态：框架搭建中，具体采集逻辑待实现

数据源：
- 全国建筑市场监管公共服务平台（jzsc.mohurd.gov.cn）
- 上海市建设工程交易服务中心（www.shcpe.cn）
- 上海工程建设领域信息公开共享平台
- 采招网（www.bidcenter.com.cn）
- 上海市住建委施工许可公告

TODO:
1. 实现上海住建委施工许可公告抓取
2. 实现采招网上海地区招标信息抓取
3. 实现全国建筑市场监管平台项目查询
4. 数据清洗与标准化
5. 与现有 Pipeline 集成
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from config import get, get_path


# ─────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────

class ProjectData:
    """项目数据模型（标准化字段）"""
    
    # 必填字段
    REQUIRED_FIELDS = ["name", "region", "start_date", "contractor"]
    
    # 完整字段列表
    ALL_FIELDS = [
        "id",                    # 项目唯一ID（MD5哈希）
        "name",                  # 项目名称
        "category",              # 项目类别
        "sub_category",          # 子类别
        "region",                # 所属区域
        "address",               # 项目地址
        "start_date",            # 开工时间
        "end_date",              # 预计完工时间
        "status",                # 项目状态
        "investment",            # 项目总投资（万元）
        "area",                  # 建筑面积（㎡）
        "template_estimate",     # 模板需求预估
        "contractor",            # 承建单位
        "contractor_website",    # 承建方官网
        "contractor_credit_code", # 统一社会信用代码
        "contractor_qualification", # 资质等级
        "contractor_phone",      # 承建方电话
        "contact_person",        # 采购负责人
        "bid_amount",            # 中标金额
        "bid_date",              # 中标日期
        "bid_source",            # 招标公示网站
        "bid_link",              # 招标公告链接
        "bid_result_link",       # 中标公示链接
        "first_seen",            # 首次发现日期
        "is_new",                # 是否新增
        "notes",                 # 备注
    ]
    
    def __init__(self, data: dict):
        self.data = data
        self.validate()
    
    def validate(self):
        """验证必填字段"""
        missing = [f for f in self.REQUIRED_FIELDS if not self.data.get(f)]
        if missing:
            raise ValueError(f"缺少必填字段: {missing}")
    
    def to_dict(self) -> dict:
        """转换为标准字典格式"""
        return {k: self.data.get(k) for k in self.ALL_FIELDS}


# ─────────────────────────────────────────────
# 采集器基类
# ─────────────────────────────────────────────

class BaseCollector:
    """采集器基类"""
    
    def __init__(self, name: str, source_url: str):
        self.name = name
        self.source_url = source_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
    
    def collect(self) -> List[ProjectData]:
        """执行采集，子类必须实现"""
        raise NotImplementedError
    
    def save_raw(self, data: list, suffix: str = ""):
        """保存原始数据（用于调试）"""
        raw_dir = get_path("paths.history_dir").parent / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.name}_{timestamp}{suffix}.json"
        
        with open(raw_dir / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[DEBUG] 原始数据已保存: {raw_dir / filename}")


# ─────────────────────────────────────────────
# 具体采集器（待实现）
# ─────────────────────────────────────────────

class SHConstructionPermitCollector(BaseCollector):
    """
    上海市住建委施工许可公告采集器
    数据源：上海市建设工程交易服务中心
    """
    
    def __init__(self):
        super().__init__(
            name="sh_construction_permit",
            source_url="https://www.shcpe.cn"
        )
    
    def collect(self) -> List[ProjectData]:
        """
        TODO: 实现施工许可公告抓取
        
        步骤：
        1. 访问施工许可公告页面
        2. 解析列表页，获取项目链接
        3. 逐个访问详情页
        4. 提取项目信息
        5. 返回 ProjectData 列表
        """
        print(f"[{self.name}] 采集器尚未实现")
        return []


class BidCenterCollector(BaseCollector):
    """
    采招网上海地区采集器
    数据源：采招网（sh.bidcenter.com.cn）
    """
    
    def __init__(self):
        super().__init__(
            name="bidcenter_sh",
            source_url="https://sh.bidcenter.com.cn"
        )
    
    def collect(self) -> List[ProjectData]:
        """
        TODO: 实现采招网招标信息抓取
        
        步骤：
        1. 搜索上海地区建筑工程招标
        2. 解析列表页
        3. 访问详情页获取完整信息
        4. 返回 ProjectData 列表
        """
        print(f"[{self.name}] 采集器尚未实现")
        return []


class NationalPlatformCollector(BaseCollector):
    """
    全国建筑市场监管公共服务平台采集器
    数据源：jzsc.mohurd.gov.cn
    
    注意：该平台有反爬机制，可能需要特殊处理
    """
    
    def __init__(self):
        super().__init__(
            name="national_platform",
            source_url="https://jzsc.mohurd.gov.cn"
        )
    
    def collect(self) -> List[ProjectData]:
        """
        TODO: 实现全国平台项目查询
        
        注意：该平台可能有：
        - 验证码
        - 登录限制
        - 请求频率限制
        
        可能需要：
        - 使用 Selenium/Playwright
        - 代理池
        - 打码服务
        """
        print(f"[{self.name}] 采集器尚未实现（需处理反爬）")
        return []


# ─────────────────────────────────────────────
# 采集编排
# ─────────────────────────────────────────────

class CollectionPipeline:
    """采集 Pipeline，协调多个采集器"""
    
    def __init__(self):
        self.collectors: List[BaseCollector] = [
            SHConstructionPermitCollector(),
            BidCenterCollector(),
            # NationalPlatformCollector(),  # 反爬较强，暂缓
        ]
    
    def run(self, dry_run: bool = False) -> List[ProjectData]:
        """
        执行所有采集器
        
        Args:
            dry_run: 是否仅测试，不保存结果
        
        Returns:
            合并后的项目列表
        """
        all_projects = []
        
        print("=" * 52)
        print("Phase 2 数据采集 Pipeline")
        print("=" * 52)
        
        for collector in self.collectors:
            print(f"\n[RUN] 启动采集器: {collector.name}")
            try:
                projects = collector.collect()
                print(f"[OK] {collector.name} 采集到 {len(projects)} 条")
                all_projects.extend(projects)
            except Exception as e:
                print(f"[ERROR] {collector.name} 采集失败: {e}")
            
            # 礼貌等待，避免请求过快
            time.sleep(1)
        
        # 去重（按项目名称）
        seen = set()
        unique_projects = []
        for p in all_projects:
            name = p.data.get("name", "")
            if name and name not in seen:
                seen.add(name)
                unique_projects.append(p)
        
        print(f"\n[SUMMARY] 总计采集: {len(all_projects)} 条，去重后: {len(unique_projects)} 条")
        
        if not dry_run:
            self.save_results(unique_projects)
        
        return unique_projects
    
    def save_results(self, projects: List[ProjectData]):
        """保存采集结果到 projects.json"""
        projects_file = get_path("paths.projects")
        
        # 转换为字典列表
        data = [p.to_dict() for p in projects]
        
        with open(projects_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 结果已保存: {projects_file}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 2 数据采集")
    parser.add_argument("--dry-run", action="store_true", help="测试模式，不保存结果")
    parser.add_argument("--source", type=str, help="指定采集源（sh_construction_permit/bidcenter_sh）")
    args = parser.parse_args()
    
    if args.source:
        # 单独运行某个采集器
        collector_map = {
            "sh_construction_permit": SHConstructionPermitCollector,
            "bidcenter_sh": BidCenterCollector,
            "national_platform": NationalPlatformCollector,
        }
        
        if args.source not in collector_map:
            print(f"[ERROR] 未知采集源: {args.source}")
            print(f"可用选项: {list(collector_map.keys())}")
            return
        
        collector = collector_map[args.source]()
        projects = collector.collect()
        print(f"[OK] 采集完成: {len(projects)} 条")
    else:
        # 运行完整 Pipeline
        pipeline = CollectionPipeline()
        pipeline.run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
