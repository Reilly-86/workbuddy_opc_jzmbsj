#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BD 评分模块
根据 config.json 中定义的评分规则，自动计算项目 BD 优先级
"""

import re
from datetime import datetime
from typing import Optional

from config import get


def parse_area(area_value) -> Optional[float]:
    """解析面积字段，返回平方米数值"""
    if area_value is None:
        return None
    if isinstance(area_value, (int, float)):
        return float(area_value)
    if isinstance(area_value, str):
        # 尝试提取数字
        match = re.search(r'[\d,]+\.?\d*', area_value.replace(',', ''))
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass
    return None


def parse_investment(inv_value) -> Optional[float]:
    """解析投资额字段，返回万元数值"""
    if inv_value is None:
        return None
    if isinstance(inv_value, (int, float)):
        return float(inv_value)
    if isinstance(inv_value, str):
        # 提取数字和单位
        match = re.search(r'([\d,]+\.?\d*)\s*(万|亿)?', inv_value.replace(',', ''))
        if match:
            try:
                num = float(match.group(1))
                unit = match.group(2)
                if unit == '亿':
                    num *= 10000  # 亿转万
                return num
            except (ValueError, IndexError):
                pass
    return None


def parse_months_since_start(start_date: str) -> Optional[int]:
    """解析开工日期，返回距今月数"""
    if not start_date:
        return None
    
    # 尝试提取年份
    year_match = re.search(r'(20\d{2})', str(start_date))
    if not year_match:
        return None
    
    year = int(year_match.group(1))
    current_year = datetime.now().year
    
    # 尝试提取月份
    month_match = re.search(r'(\d{1,2})月', str(start_date))
    if month_match:
        month = int(month_match.group(1))
    else:
        month = 1  # 默认1月
    
    # 计算月数差
    months = (current_year - year) * 12 + (datetime.now().month - month)
    return max(0, months)


def parse_qualification(qualification: str) -> str:
    """解析资质等级，返回标准化等级"""
    if not qualification:
        return "其他"
    
    qual = str(qualification)
    if '特级' in qual:
        return "特级资质"
    elif '一级' in qual or '壹级' in qual:
        return "一级资质"
    elif '二级' in qual or '贰级' in qual:
        return "二级资质"
    else:
        return "其他"


def evaluate_rule(value: Optional[float], rules: list) -> int:
    """根据规则列表评估分值"""
    if value is None:
        return 0
    
    for rule in rules:
        condition = rule.get("condition", "")
        score = rule.get("score", 0)
        
        # 解析条件表达式
        try:
            if ">" in condition and "=" in condition:
                # >=
                threshold = float(re.search(r'>=?\s*([\d.]+)', condition).group(1))
                if value >= threshold:
                    return score
            elif "<" in condition and "=" in condition:
                # <=
                if "<=" in condition:
                    threshold = float(re.search(r'<=?\s*([\d.]+)', condition).group(1))
                    if value <= threshold:
                        return score
                else:
                    # < x
                    threshold = float(re.search(r'<\s*([\d.]+)', condition).group(1))
                    if value < threshold:
                        return score
            elif "<" in condition:
                threshold = float(re.search(r'<\s*([\d.]+)', condition).group(1))
                if value < threshold:
                    return score
            elif ">" in condition:
                threshold = float(re.search(r'>\s*([\d.]+)', condition).group(1))
                if value > threshold:
                    return score
        except (AttributeError, ValueError):
            continue
    
    return 0


def evaluate_qualification_rule(qual: str, rules: list) -> int:
    """根据资质等级评估分值"""
    for rule in rules:
        condition = rule.get("condition", "")
        score = rule.get("score", 0)
        
        if condition in qual or qual in condition:
            return score
    
    return 0


def calculate_project_score(project: dict) -> dict:
    """
    计算单个项目的 BD 评分
    
    Returns:
        {
            "total_score": float,  # 总分 0-10
            "volume_score": int,   # 体量分 0-10
            "timeliness_score": int,  # 时效分 0-10
            "contractor_score": int,  # 承建方分 0-10
            "priority_level": int,    # 优先级 1-3 (1=低, 2=中, 3=高)
            "priority_text": str,     # "⭐" 星级文本
            "details": dict,          # 评分详情
        }
    """
    # 获取评分配置
    weights = get("scoring.weights", {})
    volume_rules = get("scoring.volume_rules", [])
    timeliness_rules = get("scoring.timeliness_rules", [])
    contractor_rules = get("scoring.contractor_rules", [])
    thresholds = get("scoring.priority_thresholds", {"high": 8, "medium": 5, "low": 3})
    
    # 解析字段
    area = parse_area(project.get("area"))
    investment = parse_investment(project.get("investment"))
    months = parse_months_since_start(project.get("start_date", ""))
    qualification = parse_qualification(project.get("contractor_qualification", ""))
    
    # 计算各项得分
    volume_score = 0
    if area is not None:
        volume_score = evaluate_rule(area, volume_rules)
    elif investment is not None:
        # 如果没有面积，用投资额估算（假设 1万㎡ ≈ 5000万投资）
        estimated_area = investment * 10000 / 5000  # 万转元后估算
        volume_score = evaluate_rule(estimated_area, volume_rules)
    
    timeliness_score = evaluate_rule(months, timeliness_rules) if months is not None else 5
    contractor_score = evaluate_qualification_rule(qualification, contractor_rules)
    
    # 加权总分（0-10 分制）
    total = (
        volume_score * weights.get("volume", 0.4) +
        timeliness_score * weights.get("timeliness", 0.3) +
        contractor_score * weights.get("contractor", 0.3)
    )
    
    # 确定优先级
    if total >= thresholds.get("high", 8):
        priority_level = 3
        priority_text = "⭐⭐⭐"
    elif total >= thresholds.get("medium", 5):
        priority_level = 2
        priority_text = "⭐⭐"
    else:
        priority_level = 1
        priority_text = "⭐"
    
    return {
        "total_score": round(total, 1),
        "volume_score": volume_score,
        "timeliness_score": timeliness_score,
        "contractor_score": contractor_score,
        "priority_level": priority_level,
        "priority_text": priority_text,
        "details": {
            "area_parsed": area,
            "investment_parsed": investment,
            "months_since_start": months,
            "qualification_parsed": qualification,
        }
    }


def score_projects(projects: list) -> list:
    """
    批量计算项目评分，更新项目数据
    
    Returns:
        更新后的项目列表（添加了评分字段）
    """
    for p in projects:
        score_result = calculate_project_score(p)
        p["bd_priority"] = score_result["priority_level"]
        p["bd_priority_text"] = score_result["priority_text"]
        p["bd_score"] = score_result["total_score"]
        p["bd_score_details"] = {
            "volume": score_result["volume_score"],
            "timeliness": score_result["timeliness_score"],
            "contractor": score_result["contractor_score"],
        }
    
    return projects


if __name__ == "__main__":
    # 测试
    test_project = {
        "name": "测试项目",
        "area": "30000",
        "investment": "50000万",
        "start_date": "2026年1月",
        "contractor_qualification": "一级资质",
    }
    result = calculate_project_score(test_project)
    print(f"项目评分结果: {result}")
