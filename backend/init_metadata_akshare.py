#!/usr/bin/env python3
"""
AKShare 元数据初始化脚本
使用东方财富数据源初始化股票、行业板块、概念板块和成分股
"""
import sys
import os

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from flask import Flask
from config import config
from extensions import db
from services.metadata_service import (
    get_metadata_service,
    supplement_stock_basic_from_akshare,
    init_all_metadata_from_akshare_full
)


def init_all_metadata():
    """初始化所有元数据（股票 + 板块）"""
    app = Flask(__name__)
    app.config.from_object(config['development'])
    db.init_app(app)

    with app.app_context():
        print("=" * 60)
        print("开始通过 AKShare 初始化全部元数据...")
        print("=" * 60)
        
        # 测试 AKShare 连接
        print("\n1. 测试 AKShare 连接...")
        try:
            from services.akshare_service import get_akshare_service
            aks = get_akshare_service()
            industries = aks.get_all_industries()
            concepts = aks.get_all_concepts()
            stocks = aks.get_stock_basics()
            print(f"   - 行业分类: {len(industries)} 个")
            print(f"   - 概念板块: {len(concepts)} 个")
            print(f"   - A股股票: {len(stocks)} 只")
            print("   ✓ AKShare 连接成功")
        except ImportError:
            print("   ✗ AKShare 未安装，请运行: pip install akshare")
            return
        except Exception as e:
            print(f"   ✗ AKShare 连接失败: {e}")
            return
        
        # 全部初始化
        print("\n2. 开始初始化全部元数据...")
        result = init_all_metadata_from_akshare_full()
        
        # 显示结果
        print(f"\n   - 股票: 新增 {result['stocks']['added']} 只, 更新 {result['stocks']['updated']} 只")
        print(f"   - 行业板块: 新增 {result['industry_sectors']['added']} 个")
        print(f"   - 概念板块: 新增 {result['concept_sectors']['added']} 个")
        print(f"   - 行业关联: 新增 {result['industry_relations']['added']} 条")
        print(f"   - 概念关联: 新增 {result['concept_relations']['added']} 条")
        
        # 显示统计信息
        print("\n3. 元数据统计...")
        service = get_metadata_service()
        summary = service.get_metadata_summary()
        print(f"   - 股票总数: {summary['stock_basic_count']}")
        print(f"   - 行业板块: {summary['sector_industry_count']}")
        print(f"   - 概念板块: {summary.get('sector_concept_count', 0)}")
        print(f"   - 地区板块: {summary['sector_area_count']}")
        print(f"   - 关联总数: {summary['stock_sector_relation_count']}")
        
        print("\n" + "=" * 60)
        print("全部元数据初始化完成!")
        print("=" * 60)


def init_stock_only():
    """仅初始化股票"""
    app = Flask(__name__)
    app.config.from_object(config['development'])
    db.init_app(app)

    with app.app_context():
        print("=" * 60)
        print("开始初始化股票基本信息...")
        print("=" * 60)
        
        # 测试 AKShare 连接
        print("\n1. 测试 AKShare 连接...")
        try:
            from services.akshare_service import get_akshare_service
            aks = get_akshare_service()
            stocks = aks.get_stock_basics()
            print(f"   - A股股票: {len(stocks)} 只")
            print("   ✓ AKShare 连接成功")
        except ImportError:
            print("   ✗ AKShare 未安装，请运行: pip install akshare")
            return
        except Exception as e:
            print(f"   ✗ AKShare 连接失败: {e}")
            return
        
        # 初始化股票
        print("\n2. 开始初始化股票...")
        result = supplement_stock_basic_from_akshare()
        print(f"\n   - 新增: {result['added']} 只")
        print(f"   - 更新: {result['updated']} 只")
        print(f"   - 跳过: {result['skipped']} 只")
        
        # 显示统计信息
        print("\n3. 统计...")
        service = get_metadata_service()
        summary = service.get_metadata_summary()
        print(f"   - 股票总数: {summary['stock_basic_count']}")
        
        print("\n" + "=" * 60)
        print("股票基本信息初始化完成!")
        print("=" * 60)


def init_industry_only():
    """仅初始化行业板块"""
    app = Flask(__name__)
    app.config.from_object(config['development'])
    db.init_app(app)

    with app.app_context():
        service = get_metadata_service()
        
        print("=" * 60)
        print("开始初始化行业板块...")
        print("=" * 60)
        
        result = service.supplement_industry_sectors_from_akshare()
        print(f"\n新增板块: {result['sectors']['added']}")
        print(f"更新板块: {result['sectors']['updated']}")
        print(f"新增关联: {result['relations']['added']}")
        
        print("\n行业板块初始化完成!")


def init_concept_only():
    """仅初始化概念板块"""
    app = Flask(__name__)
    app.config.from_object(config['development'])
    db.init_app(app)

    with app.app_context():
        service = get_metadata_service()
        
        print("=" * 60)
        print("开始初始化概念板块...")
        print("=" * 60)
        
        result = service.supplement_concept_sectors_from_akshare()
        print(f"\n新增板块: {result['sectors']['added']}")
        print(f"更新板块: {result['sectors']['updated']}")
        print(f"新增关联: {result['relations']['added']}")
        
        print("\n概念板块初始化完成!")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='AKShare 元数据初始化脚本')
    parser.add_argument('--type', choices=['all', 'stock', 'industry', 'concept'], 
                        default='all', help='初始化类型: all=全部, stock=股票, industry=行业板块, concept=概念板块')
    
    args = parser.parse_args()
    
    if args.type == 'all':
        init_all_metadata()
    elif args.type == 'stock':
        init_stock_only()
    elif args.type == 'industry':
        init_industry_only()
    else:
        init_concept_only()
