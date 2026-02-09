"""
元数据补充服务
提供股票信息、板块信息、股票-板块关联关系的补充和更新功能
"""
import logging
import time
import random
import json
import urllib.request
import urllib.parse
from datetime import datetime
from collections import defaultdict
from extensions import db
from models.stockbasic import StockBasic
from models.kline import StockSector, StockSectorRelation
from services.metadata_config import (
    get_metadata_config,
    is_auto_supplement_enabled,
    METADATA_SUPPLEMENT_CONFIG
)

logger = logging.getLogger(__name__)


class MetadataService:
    """元数据服务类"""
    
    def __init__(self):
        self.baostock_service = None
        self.akshare_service = None
    
    def _get_baostock_service(self):
        """获取Baostock服务实例（延迟加载）"""
        if self.baostock_service is None:
            from services.baostock_service import get_baostock_service
            self.baostock_service = get_baostock_service()
        return self.baostock_service
    
    def _get_eastmoney_service(self):
        """获取AKShare服务实例（延迟加载）"""
        if self.akshare_service is None:
            try:
                from services.akshare_service import get_eastmoney_service
                self.akshare_service = get_eastmoney_service()
                logger.info("AKShare 服务初始化成功")
            except ImportError as e:
                logger.error(f"AKShare 导入失败: {e}")
                logger.warning("AKShare 未安装，无法使用 AKShare 数据源")
                self.akshare_service = False
            except Exception as e:
                logger.error(f"AKShare 初始化异常: {e}")
                logger.warning("AKShare 服务异常，无法使用")
                self.akshare_service = False
        return self.akshare_service
    
    # ==================== 股票信息补充 ====================
    
    def supplement_stock_basic(self, stock_codes, db_session=None, update_existing=False):
        """
        补充股票基本信息

        Args:
            stock_codes: 股票代码列表
            db_session: 数据库会话
            update_existing: 是否更新已存在的股票信息，默认False（只新增）

        Returns:
            dict: {'added': 新增数量, 'updated': 更新数量, 'skipped': 跳过数量}
        """
        if db_session is None:
            db_session = db.session

        result = {'added': 0, 'updated': 0, 'skipped': 0}

        try:
            bs = self._get_baostock_service()
            bs.login()

            # 1. 获取已有的股票信息
            existing_stocks = db_session.query(StockBasic).filter(
                StockBasic.stock_code.in_(stock_codes)
            ).all()
            existing_map = {s.stock_code: s for s in existing_stocks}

            # 2. 从Baostock获取股票基本信息
            stock_info_list = []
            for code in stock_codes:
                info = bs.get_stock_info(code)
                if info and info.get('code'):
                    stock_info_list.append(info)

            # 3. 保存或更新股票信息
            for info in stock_info_list:
                code = info.get('code', '')

                if code in existing_map:
                    # 已存在，根据配置决定是否更新
                    if update_existing:
                        try:
                            self._update_stock_basic(existing_map[code], info)
                            result['updated'] += 1
                        except Exception as e:
                            logger.error(f"更新股票信息失败 {code}: {e}")
                            result['skipped'] += 1
                    else:
                        result['skipped'] += 1
                else:
                    # 新增
                    try:
                        stock = self._create_stock_basic(info)
                        db_session.add(stock)
                        result['added'] += 1
                    except Exception as e:
                        logger.error(f"保存股票信息失败 {code}: {e}")
                        result['skipped'] += 1

            db_session.commit()
            logger.info(f"股票信息补充完成: 新增{result['added']}条, 更新{result['updated']}条, 跳过{result['skipped']}条")

        except Exception as e:
            db_session.rollback()
            logger.error(f"补充股票信息失败: {e}")
            raise
        finally:
            try:
                bs.logout()
            except:
                pass

        return result

    def _update_stock_basic(self, stock, info):
        """
        更新股票基本信息

        Args:
            stock: 股票基本信息对象
            info: API返回的股票信息字典
        """
        # 判断市场类型
        code = info.get('code', '')
        market = self._get_market_type(code)
        exchange = 'sh' if code.startswith('sh') else 'sz' if code.startswith('sz') else None

        # 更新字段
        stock.stock_name = info.get('name', '') or stock.stock_name
        stock.exchange = exchange or stock.exchange
        stock.market = market or stock.market
        stock.company_name = info.get('company_name', '') or stock.company_name
        stock.industry = info.get('industry', '') or stock.industry
        stock.area = info.get('area', '') or stock.area
        stock.list_date = info.get('list_date', '') or stock.list_date
        stock.delist_date = info.get('delist_date', None) or stock.delist_date
        stock.is_hs = 1 if info.get('is_hs') == '1' else stock.is_hs

        # 更新股本信息（如果API返回了有效值）
        if info.get('total_shares') is not None:
            stock.total_shares = info.get('total_shares')
        if info.get('circulate_shares') is not None:
            stock.circulate_shares = info.get('circulate_shares')

        stock.update_time = datetime.now()
    
    def _create_stock_basic(self, info):
        """
        从API响应创建股票基本信息对象
        
        Args:
            info: API返回的股票信息字典
        
        Returns:
            StockBasic: 股票基本信息对象
        """
        code = info.get('code', '')
        
        # 判断市场类型
        market = self._get_market_type(code)
        exchange = 'sh' if code.startswith('sh') else 'sz' if code.startswith('sz') else None
        
        stock = StockBasic(
            stock_code=code,
            stock_name=info.get('name', ''),
            exchange=exchange,
            market=market,
            company_name=info.get('company_name', ''),
            industry=info.get('industry', ''),
            area=info.get('area', ''),
            list_date=info.get('list_date', ''),
            delist_date=info.get('delist_date', None),
            is_hs=1 if info.get('is_hs') == '1' else 0,
            total_shares=info.get('total_shares') or None,
            circulate_shares=info.get('circulate_shares') or None,
        )
        
        return stock
    
    def _get_market_type(self, code):
        """
        根据股票代码判断市场类型
        
        Args:
            code: 股票代码
        
        Returns:
            str: 市场类型
        """
        if not code:
            return '未知'
        
        code = code.lower()
        if code.startswith('sh.68') or (code.startswith('sh.6') and len(code) == 9 and int(code[3:5]) >= 80):
            return '科创板'
        elif code.startswith('sh.60'):
            return '上海主板'
        elif code.startswith('sz.00'):
            return '深圳主板'
        elif code.startswith('sz.30'):
            return '创业板'
        elif code.startswith('sz'):
            return '深圳其他'
        return '未知'
    
    def get_stock_basic(self, stock_code, db_session=None):
        """
        获取股票基本信息
        
        Args:
            stock_code: 股票代码
            db_session: 数据库会话
        
        Returns:
            StockBasic: 股票基本信息对象或None
        """
        if db_session is None:
            db_session = db.session
        
        return db_session.query(StockBasic).filter(
            StockBasic.stock_code == stock_code
        ).first()
    
    def update_stock_basic(self, stock_code, update_data, db_session=None):
        """
        更新股票基本信息
        
        Args:
            stock_code: 股票代码
            update_data: 更新数据字典
            db_session: 数据库会话
        
        Returns:
            bool: 是否更新成功
        """
        if db_session is None:
            db_session = db.session
        
        stock = self.get_stock_basic(stock_code, db_session)
        if not stock:
            return False
        
        for key, value in update_data.items():
            if hasattr(stock, key):
                setattr(stock, key, value)
        
        stock.update_time = datetime.now()
        db_session.commit()
        
        return True
    
    # ==================== 板块信息补充 ====================
    
    def supplement_sectors(self, sector_type=None, db_session=None):
        """
        补充板块信息
        
        Args:
            sector_type: 板块类型 (industry-行业, concept-概念, area-地区)
            db_session: 数据库会话
        
        Returns:
            dict: {'added': 新增数量, 'updated': 更新数量}
        """
        if db_session is None:
            db_session = db.session
        
        result = {'added': 0, 'updated': 0}
        
        try:
            bs = self._get_baostock_service()
            bs.login()
            
            # 从Baostock获取行业分类
            industry_list = bs.get_industry_classify()
            
            if not industry_list:
                logger.warning("未获取到行业分类数据")
                return result
            
            # 处理行业板块
            self._process_industry_sectors(industry_list, db_session, result)
            
            # 处理概念板块（如果有）
            if sector_type in [None, 'concept']:
                self._process_concept_sectors(industry_list, db_session, result)
            
            # 处理地区板块（如果有）
            if sector_type in [None, 'area']:
                self._process_area_sectors(industry_list, db_session, result)
            
            db_session.commit()
            logger.info(f"板块信息补充完成: 新增{result['added']}条, 更新{result['updated']}条")
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"补充板块信息失败: {e}")
            raise
        finally:
            try:
                bs.logout()
            except:
                pass
        
        return result
    
    def _process_industry_sectors(self, industry_list, db_session, result):
        """处理行业板块"""
        # 按行业分组
        industry_map = defaultdict(list)
        for item in industry_list:
            industry = item.get('industry', '未知')
            industry_map[industry].append(item)
        
        for industry_name, stocks in industry_map.items():
            if not industry_name or industry_name == '未知':
                continue
            
            # 检查是否已存在
            sector = db_session.query(StockSector).filter(
                StockSector.sector_name == industry_name,
                StockSector.sector_type == 'industry'
            ).first()
            
            if sector:
                # 更新
                sector.stock_count = len(stocks)
                sector.update_time = datetime.now()
                result['updated'] += 1
            else:
                # 新增
                sector = StockSector(
                    sector_code=f"ind_{industry_name[:18]}",
                    sector_name=industry_name,
                    sector_type='industry',
                    level=1,
                    stock_count=len(stocks),
                )
                db_session.add(sector)
                result['added'] += 1
    
    def _process_concept_sectors(self, industry_list, db_session, result):
        """处理概念板块（从industry_list提取概念信息）"""
        # 注意：Baostock的query_stock_industry主要返回行业信息
        # 概念板块需要其他数据源，这里暂时不实现
        pass
    
    def _process_area_sectors(self, industry_list, db_session, result):
        """处理地区板块"""
        # 按地区分组
        area_map = defaultdict(list)
        for item in industry_list:
            area = item.get('area', '未知')
            area_map[area].append(item)
        
        for area_name, stocks in area_map.items():
            if not area_name or area_name == '未知':
                continue
            
            # 检查是否已存在
            sector = db_session.query(StockSector).filter(
                StockSector.sector_name == area_name,
                StockSector.sector_type == 'area'
            ).first()
            
            if sector:
                # 更新
                sector.stock_count = len(stocks)
                sector.update_time = datetime.now()
                result['updated'] += 1
            else:
                # 新增
                sector = StockSector(
                    sector_code=f"area_{area_name[:18]}",
                    sector_name=area_name,
                    sector_type='area',
                    level=1,
                    stock_count=len(stocks),
                )
                db_session.add(sector)
                result['added'] += 1
    
    def get_sector(self, sector_code, db_session=None):
        """
        获取板块信息
        
        Args:
            sector_code: 板块代码
            db_session: 数据库会话
        
        Returns:
            StockSector: 板块信息对象或None
        """
        if db_session is None:
            db_session = db.session
        
        return db_session.query(StockSector).filter(
            StockSector.sector_code == sector_code
        ).first()
    
    def get_sectors_by_type(self, sector_type, db_session=None):
        """
        获取指定类型的所有板块
        
        Args:
            sector_type: 板块类型
            db_session: 数据库会话
        
        Returns:
            list: 板块列表
        """
        if db_session is None:
            db_session = db.session
        
        return db_session.query(StockSector).filter(
            StockSector.sector_type == sector_type
        ).all()
    
    # ==================== 股票-板块关联补充 ====================
    
    def supplement_stock_sector_relations(self, stock_codes, db_session=None):
        """
        补充股票-板块关联关系
        
        Args:
            stock_codes: 股票代码列表
            db_session: 数据库会话
        
        Returns:
            dict: {'added': 新增数量, 'updated': 更新数量, 'skipped': 跳过数量}
        """
        if db_session is None:
            db_session = db.session
        
        result = {'added': 0, 'updated': 0, 'skipped': 0}
        
        try:
            bs = self._get_baostock_service()
            bs.login()
            
            # 1. 获取行业分类信息
            industry_list = bs.get_industry_classify()
            
            # 2. 构建股票到板块的映射
            stock_sector_map = defaultdict(list)
            for item in industry_list:
                code = item.get('code')
                if code in stock_codes:
                    # 添加行业关联
                    industry = item.get('industry', '未知')
                    if industry and industry != '未知':
                        stock_sector_map[code].append({
                            'sector_name': industry,
                            'sector_type': 'industry',
                            'is_main': 1
                        })
                    
                    # 添加地区关联
                    area = item.get('area', '未知')
                    if area and area != '未知':
                        stock_sector_map[code].append({
                            'sector_name': area,
                            'sector_type': 'area',
                            'is_main': 0
                        })
            
            # 3. 确保板块信息已存在
            self._ensure_sectors_exist(stock_sector_map, db_session)
            
            # 4. 获取已有的关联关系
            existing_relations = db_session.query(StockSectorRelation.stock_code).distinct().all()
            existing_codes = {r[0] for r in existing_relations}
            
            # 5. 添加新的关联关系
            for code, sectors in stock_sector_map.items():
                if not sectors:
                    result['skipped'] += 1
                    continue
                
                for sector_info in sectors:
                    # 检查是否已存在关联
                    sector = db_session.query(StockSector).filter(
                        StockSector.sector_name == sector_info['sector_name'],
                        StockSector.sector_type == sector_info['sector_type']
                    ).first()
                    
                    if not sector:
                        continue
                    
                    exists = db_session.query(StockSectorRelation).filter(
                        StockSectorRelation.stock_code == code,
                        StockSectorRelation.sector_id == sector.id
                    ).first()
                    
                    if exists:
                        result['skipped'] += 1
                        continue
                    
                    # 新增关联
                    relation = StockSectorRelation(
                        stock_code=code,
                        sector_id=sector.id,
                        is_main=sector_info['is_main'],
                        weight=100.00 if sector_info['is_main'] else 50.00
                    )
                    db_session.add(relation)
                    result['added'] += 1
            
            db_session.commit()
            logger.info(f"股票-板块关联补充完成: 新增{result['added']}条, 更新{result['updated']}条, 跳过{result['skipped']}条")
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"补充股票-板块关联失败: {e}")
            raise
        finally:
            try:
                bs.logout()
            except:
                pass
        
        return result
    
    def _ensure_sectors_exist(self, stock_sector_map, db_session):
        """确保关联的板块信息已存在"""
        # 收集所有需要确保存在的板块
        sector_names = set()
        for sectors in stock_sector_map.values():
            for s in sectors:
                sector_names.add((s['sector_name'], s['sector_type']))
        
        # 检查并创建不存在的板块
        for sector_name, sector_type in sector_names:
            exists = db_session.query(StockSector).filter(
                StockSector.sector_name == sector_name,
                StockSector.sector_type == sector_type
            ).first()
            
            if not exists:
                sector = StockSector(
                    sector_code=f"{sector_type[:3]}_{sector_name[:18]}",
                    sector_name=sector_name,
                    sector_type=sector_type,
                    level=1,
                    stock_count=0,
                )
                db_session.add(sector)
        
        db_session.commit()
    
    def get_stock_sectors(self, stock_code, db_session=None):
        """
        获取股票所属板块
        
        Args:
            stock_code: 股票代码
            db_session: 数据库会话
        
        Returns:
            list: 板块关联列表
        """
        if db_session is None:
            db_session = db.session
        
        relations = db_session.query(StockSectorRelation).filter(
            StockSectorRelation.stock_code == stock_code
        ).all()
        
        return [r.to_dict() for r in relations]
    
    # ==================== 综合补充接口 ====================
    
    def supplement_all_stock_basic(self, db_session=None, update_existing=True):
        """
        通过query_stock_basic API批量补充所有股票基本信息

        Args:
            db_session: 数据库会话
            update_existing: 是否更新已存在的股票信息，默认True

        Returns:
            dict: {'added': 新增数量, 'updated': 更新数量, 'skipped': 跳过数量}
        """
        if db_session is None:
            db_session = db.session

        result = {'added': 0, 'updated': 0, 'skipped': 0}

        try:
            bs = self._get_baostock_service()
            
            # 从Baostock批量获取所有股票基本信息
            stock_info_list = bs.get_stock_basic_batch()
            
            if not stock_info_list:
                logger.warning("未获取到任何股票基本信息")
                return result

            logger.info(f"从Baostock获取到 {len(stock_info_list)} 只股票信息")

            # 获取已有的股票代码
            existing_stocks = db_session.query(StockBasic.stock_code).all()
            existing_codes = {s[0] for s in existing_stocks}
            
            # 过滤掉非A股（代码格式不对的）
            valid_stocks = []
            for info in stock_info_list:
                code = info.get('code', '')
                # 检查代码格式: sh.xxxxxx 或 sz.xxxxxx
                if len(code) >= 8 and code[2:8].isdigit():
                    valid_stocks.append(info)
            
            logger.info(f"有效A股股票数量: {len(valid_stocks)}")

            # 保存或更新股票信息
            for info in valid_stocks:
                code = info.get('code', '')

                if code in existing_codes:
                    # 已存在，根据配置决定是否更新
                    if update_existing:
                        try:
                            stock = db_session.query(StockBasic).filter(
                                StockBasic.stock_code == code
                            ).first()
                            if stock:
                                self._update_stock_basic(stock, info)
                                result['updated'] += 1
                        except Exception as e:
                            logger.error(f"更新股票信息失败 {code}: {e}")
                            result['skipped'] += 1
                    else:
                        result['skipped'] += 1
                else:
                    # 新增
                    try:
                        stock = self._create_stock_basic(info)
                        db_session.add(stock)
                        result['added'] += 1
                    except Exception as e:
                        logger.error(f"保存股票信息失败 {code}: {e}")
                        result['skipped'] += 1

            db_session.commit()
            logger.info(f"股票信息补充完成: 新增{result['added']}条, 更新{result['updated']}条, 跳过{result['skipped']}条")

        except Exception as e:
            db_session.rollback()
            logger.error(f"批量补充股票信息失败: {e}")
            raise

        return result
    
    def supplement_metadata(self, stock_codes=None, db_session=None, context='manual'):
        """
        综合元数据补充接口

        自动补充：
        1. 股票基本信息
        2. 板块信息
        3. 股票-板块关联

        Args:
            stock_codes: 股票代码列表，为None则补充所有板块
            db_session: 数据库会话
            context: 调用场景，'sync'(同步), 'review'(复盘), 'manual'(手动)

        Returns:
            dict: 各部分的补充结果
        """
        if db_session is None:
            db_session = db.session

        # 检查是否启用自动补充
        if not is_auto_supplement_enabled(context) and context != 'manual':
            logger.info(f"场景 '{context}' 已禁用自动元数据补充")
            return {
                'stock_basic': {'added': 0, 'updated': 0, 'skipped': 0, 'message': '自动补充已禁用'},
                'sectors': {'added': 0, 'updated': 0, 'message': '自动补充已禁用'},
                'stock_sector_relations': {'added': 0, 'updated': 0, 'skipped': 0, 'message': '自动补充已禁用'}
            }

        result = {
            'stock_basic': {'added': 0, 'updated': 0, 'skipped': 0},
            'sectors': {'added': 0, 'updated': 0},
            'stock_sector_relations': {'added': 0, 'updated': 0, 'skipped': 0}
        }

        try:
            # 1. 补充板块信息（如果启用）
            if get_metadata_config('supplement_sectors'):
                logger.info("开始补充板块信息...")
                result['sectors'] = self.supplement_sectors(db_session=db_session)

            # 2. 如果指定了股票代码，补充股票和关联
            if stock_codes:
                logger.info(f"开始补充 {len(stock_codes)} 只股票的元数据...")

                # 2.1 补充股票基本信息（如果启用）
                if get_metadata_config('supplement_stock_basic'):
                    update_existing = get_metadata_config('update_existing_stocks')
                    result['stock_basic'] = self.supplement_stock_basic(
                        stock_codes, db_session, update_existing=update_existing
                    )

                # 2.2 补充股票-板块关联（如果启用）
                if get_metadata_config('supplement_relations'):
                    result['stock_sector_relations'] = self.supplement_stock_sector_relations(
                        stock_codes, db_session
                    )

            logger.info(f"元数据补充完成: {result}")
            return result

        except Exception as e:
            logger.error(f"综合元数据补充失败: {e}")
            raise
    
    def sync_stock_with_sectors(self, stock_code, db_session=None):
        """
        同步单只股票的板块信息
        
        Args:
            stock_code: 股票代码
            db_session: 数据库会话
        
        Returns:
            bool: 是否成功
        """
        if db_session is None:
            db_session = db.session
        
        try:
            # 1. 获取股票的板块信息
            bs = self._get_baostock_service()
            bs.login()
            
            industry_list = bs.get_industry_classify()
            
            # 找到该股票的板块信息
            stock_info = None
            for item in industry_list:
                if item.get('code') == stock_code:
                    stock_info = item
                    break
            
            bs.logout()
            
            if not stock_info:
                logger.warning(f"未找到股票 {stock_code} 的板块信息")
                return False
            
            # 2. 确保板块存在
            sectors_to_create = [
                (stock_info.get('industry', '未知'), 'industry'),
                (stock_info.get('area', '未知'), 'area')
            ]
            
            sector_ids = {}
            for sector_name, sector_type in sectors_to_create:
                if sector_name and sector_name != '未知':
                    sector = db_session.query(StockSector).filter(
                        StockSector.sector_name == sector_name,
                        StockSector.sector_type == sector_type
                    ).first()
                    
                    if not sector:
                        sector = StockSector(
                            sector_code=f"{sector_type[:3]}_{sector_name[:18]}",
                            sector_name=sector_name,
                            sector_type=sector_type,
                            level=1,
                        )
                        db_session.add(sector)
                        db_session.flush()
                    
                    sector_ids[sector_type] = sector.id
            
            # 3. 删除旧的关联
            db_session.query(StockSectorRelation).filter(
                StockSectorRelation.stock_code == stock_code
            ).delete()
            
            # 4. 添加新的关联
            for sector_type, sector_id in sector_ids.items():
                is_main = 1 if sector_type == 'industry' else 0
                weight = 100.00 if sector_type == 'industry' else 50.00
                
                relation = StockSectorRelation(
                    stock_code=stock_code,
                    sector_id=sector_id,
                    is_main=is_main,
                    weight=weight
                )
                db_session.add(relation)
            
            # 5. 补充股票基本信息（如果没有）
            stock_basic = self.get_stock_basic(stock_code, db_session)
            if not stock_basic:
                self.supplement_stock_basic([stock_code], db_session)
            
            db_session.commit()
            return True
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"同步股票板块信息失败 {stock_code}: {e}")
            return False
    
    def get_metadata_summary(self, db_session=None):
        """
        获取元数据统计摘要
        
        Args:
            db_session: 数据库会话
        
        Returns:
            dict: 统计信息
        """
        if db_session is None:
            db_session = db.session
        
        return {
            'stock_basic_count': db_session.query(StockBasic).count(),
            'sector_count': db_session.query(StockSector).count(),
            'sector_industry_count': db_session.query(StockSector).filter(
                StockSector.sector_type == 'industry'
            ).count(),
            'sector_area_count': db_session.query(StockSector).filter(
                StockSector.sector_type == 'area'
            ).count(),
            'sector_concept_count': db_session.query(StockSector).filter(
                StockSector.sector_type == 'concept'
            ).count(),
            'stock_sector_relation_count': db_session.query(StockSectorRelation).count(),
        }
    
    # ==================== AKShare 板块补充 ====================
    
    def _convert_code_to_baostock_format(self, code):
        """
        转换股票代码格式（AKShare格式 -> Baostock格式）
        
        Args:
            code: AKShare格式代码，如 '600000'
            
        Returns:
            str: Baostock格式代码，如 'sh.600000'
        """
        if not code:
            return ''
        if code.startswith('sh.') or code.startswith('sz.'):
            return code
        if len(code) == 6 and code.isdigit():
            if code.startswith('6'):
                return f'sh.{code}'
            else:
                return f'sz.{code}'
        return code
    
    def supplement_industry_sectors_from_akshare(self, db_session=None):
        """
        使用AKShare补充行业板块和成分股
        
        Args:
            db_session: 数据库会话
            
        Returns:
            dict: {'sectors': 板块结果, 'relations': 关联结果}
        """
        if db_session is None:
            db_session = db.session
        
        sector_result = {'added': 0, 'updated': 0, 'skipped': 0}
        relation_result = {'added': 0, 'updated': 0, 'skipped': 0}
        
        try:
            aks = self._get_eastmoney_service()
            if not aks:
                logger.warning("AKShare 服务不可用")
                return {'sectors': sector_result, 'relations': relation_result}
            
            logger.info("开始通过东方财富补充行业板块...")

            # 1. 获取所有行业分类
            industry_list = aks.get_industry_classify()

            if not industry_list:
                logger.warning("未获取到行业分类数据")
                return {'sectors': sector_result, 'relations': relation_result}

            logger.info(f"获取到 {len(industry_list)} 个行业分类")

            # 2. 获取所有行业成分股
            all_stocks = aks.get_industry_stocks()

            if not all_stocks:
                logger.warning("未获取到行业成分股数据")
                return {'sectors': sector_result, 'relations': relation_result}

            # 3. 按行业名称分组
            industry_stocks = defaultdict(list)
            for stock in all_stocks:
                industry_name = stock.get('industry', '')
                if industry_name and industry_name != '未知':
                    code = self._convert_code_to_baostock_format(stock.get('code', ''))
                    if code:
                        industry_stocks[industry_name].append(code)

            logger.info(f"成分股分组完成: 共 {len(industry_stocks)} 个行业有成分股")

            # 4. 创建板块并添加关联
            for industry_name, stock_codes in industry_stocks.items():
                stock_codes = list(set(stock_codes))  # 去重

                # 检查板块是否存在
                sector = db_session.query(StockSector).filter(
                    StockSector.sector_name == industry_name,
                    StockSector.sector_type == 'industry'
                ).first()

                if sector:
                    # 更新
                    sector.stock_count = len(stock_codes)
                    sector.update_time = datetime.now()
                    sector_result['updated'] += 1
                else:
                    # 新增
                    sector = StockSector(
                        sector_code=f"ind_{industry_name[:18]}",
                        sector_name=industry_name,
                        sector_type='industry',
                        level=1,
                        stock_count=len(stock_codes),
                    )
                    db_session.add(sector)
                    db_session.flush()  # 获取 sector.id
                    sector_result['added'] += 1

                # 添加股票-板块关联
                for stock_code in stock_codes:
                    exists = db_session.query(StockSectorRelation).filter(
                        StockSectorRelation.stock_code == stock_code,
                        StockSectorRelation.sector_id == sector.id
                    ).first()

                    if not exists:
                        relation = StockSectorRelation(
                            stock_code=stock_code,
                            sector_id=sector.id,
                            is_main=1,
                            weight=100.00
                        )
                        db_session.add(relation)
                        relation_result['added'] += 1
                    else:
                        relation_result['skipped'] += 1
            
            db_session.commit()
            logger.info(f"行业板块补充完成: 新增{sector_result['added']}个板块, 新增{relation_result['added']}条关联")
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"通过AKShare补充行业板块失败: {e}")
        
        return {'sectors': sector_result, 'relations': relation_result}
    
    def supplement_concept_sectors_from_akshare(self, db_session=None):
        """
        使用AKShare补充概念板块和成分股
        
        Args:
            db_session: 数据库会话
            
        Returns:
            dict: {'sectors': 板块结果, 'relations': 关联结果}
        """
        if db_session is None:
            db_session = db.session
        
        sector_result = {'added': 0, 'updated': 0, 'skipped': 0}
        relation_result = {'added': 0, 'updated': 0, 'skipped': 0}
        
        try:
            aks = self._get_eastmoney_service()
            if not aks:
                logger.warning("AKShare 服务不可用")
                return {'sectors': sector_result, 'relations': relation_result}
            
            logger.info("开始通过东方财富补充概念板块...")

            # 东方财富 API 不支持按概念过滤成分股，需要遍历每个概念
            # 使用 EastMoneyHTTP 直接调用

            # 1. 获取概念列表
            concept_list = aks.get_concept_classify()

            if not concept_list:
                logger.warning("未获取到概念分类数据")
                return {'sectors': sector_result, 'relations': relation_result}

            logger.info(f"获取到 {len(concept_list)} 个概念板块")

            # 2. 遍历每个概念，获取成分股
            http = aks.http  # 使用服务类的 HTTP 实例

            for i, concept in enumerate(concept_list):
                concept_name = concept.get('concept_name', '')
                concept_code = concept.get('code', '')

                if not concept_name:
                    continue

                logger.info(f"[{i+1}/{len(concept_list)}] 获取概念 {concept_name} 的成分股...")

                try:
                    # 直接调用 API 获取概念成分股
                    data = http.request(
                        fs="m:90+t:1+f:!50",
                        fields="f2,f12,f14,f4,f8"
                    )

                    if data and data.get('data', {}).get('diff'):
                        diff = data['data']['diff']
                        # 过滤属于该概念的股票（东方财富返回的数据不包含概念代码，需要全部保存）
                        stocks = []
                        for item in diff:
                            code = str(item.get('f12', ''))
                            if code and len(code) == 6 and code.isdigit():
                                stocks.append({
                                    'code': code,
                                    'name': str(item.get('f14', '')),
                                })
                        stock_codes = [self._convert_code_to_baostock_format(s['code']) for s in stocks if s.get('code')]
                        logger.info(f"  概念 {concept_name} 包含 {len(stock_codes)} 只成分股")
                    else:
                        stock_codes = []

                except Exception as e:
                    logger.warning(f"  获取概念 {concept_name} 成分股失败: {e}")
                    stock_codes = []

                # 检查板块是否存在
                sector = db_session.query(StockSector).filter(
                    StockSector.sector_name == concept_name,
                    StockSector.sector_type == 'concept'
                ).first()

                if sector:
                    # 更新
                    sector.stock_count = len(stock_codes)
                    sector.update_time = datetime.now()
                    sector_result['updated'] += 1
                else:
                    # 新增
                    sector = StockSector(
                        sector_code=f"con_{concept_code[:10] if concept_code else concept_name[:18]}",
                        sector_name=concept_name,
                        sector_type='concept',
                        level=1,
                        stock_count=len(stock_codes),
                    )
                    db_session.add(sector)
                    db_session.flush()  # 获取 sector.id
                    sector_result['added'] += 1

                # 添加股票-板块关联
                for stock_code in stock_codes:
                    if not stock_code:
                        continue
                    exists = db_session.query(StockSectorRelation).filter(
                        StockSectorRelation.stock_code == stock_code,
                        StockSectorRelation.sector_id == sector.id
                    ).first()

                    if not exists:
                        relation = StockSectorRelation(
                            stock_code=stock_code,
                            sector_id=sector.id,
                            is_main=0,
                            weight=50.00
                        )
                        db_session.add(relation)
                        relation_result['added'] += 1
                    else:
                        relation_result['skipped'] += 1
            
            db_session.commit()
            logger.info(f"概念板块补充完成: 新增{sector_result['added']}个板块, 新增{relation_result['added']}条关联")
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"通过AKShare补充概念板块失败: {e}")
        
        return {'sectors': sector_result, 'relations': relation_result}
    
    def init_all_metadata_from_akshare(self, db_session=None):
        """
        使用AKShare初始化所有板块元数据（行业板块 + 概念板块）
        
        Args:
            db_session: 数据库会话
            
        Returns:
            dict: 各部分的补充结果
        """
        if db_session is None:
            db_session = db.session
        
        result = {
            'industry_sectors': {'added': 0, 'updated': 0},
            'concept_sectors': {'added': 0, 'updated': 0},
            'industry_relations': {'added': 0, 'skipped': 0},
            'concept_relations': {'added': 0, 'skipped': 0},
        }
        
        try:
            # 1. 补充行业板块
            industry_result = self.supplement_industry_sectors_from_akshare(db_session)
            result['industry_sectors'] = industry_result['sectors']
            result['industry_relations'] = industry_result['relations']
            
            # 2. 补充概念板块
            concept_result = self.supplement_concept_sectors_from_akshare(db_session)
            result['concept_sectors'] = concept_result['sectors']
            result['concept_relations'] = concept_result['relations']
            
            logger.info(f"AKShare元数据初始化完成: {result}")
            
        except Exception as e:
            logger.error(f"AKShare元数据初始化失败: {e}")
            raise
        
        return result


def get_metadata_service():
    """获取元数据服务实例"""
    return MetadataService()


# ==================== 股票元数据初始化 ====================

def supplement_stock_basic_from_akshare(db_session=None, update_existing=True):
    """
    使用AKShare补充股票基本信息

    Args:
        db_session: 数据库会话
        update_existing: 是否更新已存在的股票信息，默认True

    Returns:
        dict: {'added': 新增数量, 'updated': 更新数量, 'skipped': 跳过数量}
    """
    if db_session is None:
        db_session = db.session

    result = {'added': 0, 'updated': 0, 'skipped': 0}

    try:
        # 获取AKShare服务
        try:
            from services.akshare_service import get_eastmoney_service
            aks = get_eastmoney_service()
        except ImportError:
            logger.error("AKShare 未安装，无法补充股票信息")
            return result

        logger.info("开始通过AKShare补充股票基本信息...")

        # 1. 获取所有A股股票列表
        stock_list = aks.get_stock_basics()

        if not stock_list:
            logger.warning("未获取到股票列表数据")
            return result

        logger.info(f"获取到 {len(stock_list)} 只A股股票")

        # 2. 获取已有的股票代码
        existing_stocks = db_session.query(StockBasic.stock_code).all()
        existing_codes = {s[0] for s in existing_stocks}
        logger.info(f"数据库中已有 {len(existing_codes)} 只股票")

        # 3. 保存或更新股票信息
        for stock in stock_list:
            code = stock.get('code', '')

            if not code:
                continue

            if code in existing_codes:
                # 已存在，根据配置决定是否更新
                if update_existing:
                    try:
                        stock_obj = db_session.query(StockBasic).filter(
                            StockBasic.stock_code == code
                        ).first()
                        if stock_obj:
                            # 更新字段
                            stock_obj.stock_name = stock.get('name', '') or stock_obj.stock_name
                            stock_obj.market = stock.get('market', '') or stock_obj.market
                            stock_obj.exchange = stock.get('exchange', '') or stock_obj.exchange
                            stock_obj.update_time = datetime.now()
                            result['updated'] += 1
                    except Exception as e:
                        logger.error(f"更新股票信息失败 {code}: {e}")
                        result['skipped'] += 1
                else:
                    result['skipped'] += 1
            else:
                # 新增
                try:
                    new_stock = StockBasic(
                        stock_code=code,
                        stock_name=stock.get('name', ''),
                        exchange=stock.get('exchange', ''),
                        market=stock.get('market', ''),
                        area=stock.get('area', '') or None,
                        industry=stock.get('industry', '') or None,
                        company_name=None,
                        list_date=None,
                        delist_date=None,
                        is_hs=0,
                        total_shares=None,
                        circulate_shares=None,
                    )
                    db_session.add(new_stock)
                    result['added'] += 1
                except Exception as e:
                    logger.error(f"保存股票信息失败 {code}: {e}")
                    result['skipped'] += 1

        db_session.commit()
        logger.info(f"股票信息补充完成: 新增{result['added']}只, 更新{result['updated']}只, 跳过{result['skipped']}只")

    except Exception as e:
        db_session.rollback()
        logger.error(f"通过AKShare补充股票信息失败: {e}")

    return result


def init_all_metadata_from_akshare_full(db_session=None, update_existing=True):
    """
    使用AKShare初始化所有元数据（股票 + 行业板块 + 概念板块）

    Args:
        db_session: 数据库会话
        update_existing: 是否更新已存在的信息，默认True

    Returns:
        dict: 各部分的补充结果
    """
    if db_session is None:
        db_session = db.session

    result = {
        'stocks': {'added': 0, 'updated': 0, 'skipped': 0},
        'industry_sectors': {'added': 0, 'updated': 0},
        'concept_sectors': {'added': 0, 'updated': 0},
        'industry_relations': {'added': 0, 'skipped': 0},
        'concept_relations': {'added': 0, 'skipped': 0},
    }

    try:
        service = MetadataService()

        # 1. 补充股票基本信息
        logger.info("步骤1/3: 补充股票基本信息...")
        stock_result = supplement_stock_basic_from_akshare(db_session, update_existing)
        result['stocks'] = stock_result

        # 2. 补充行业板块
        logger.info("步骤2/3: 补充行业板块...")
        industry_result = service.supplement_industry_sectors_from_akshare(db_session)
        result['industry_sectors'] = industry_result['sectors']
        result['industry_relations'] = industry_result['relations']

        # 3. 补充概念板块
        logger.info("步骤3/3: 补充概念板块...")
        concept_result = service.supplement_concept_sectors_from_akshare(db_session)
        result['concept_sectors'] = concept_result['sectors']
        result['concept_relations'] = concept_result['relations']

        logger.info(f"全部元数据初始化完成: {result}")

    except Exception as e:
        logger.error(f"全部元数据初始化失败: {e}")
        raise

    return result

