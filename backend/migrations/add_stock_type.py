"""
数据库迁移脚本：添加 stock_type 字段
"""
import logging

logger = logging.getLogger(__name__)


def migrate(db):
    """执行迁移"""
    try:
        # 检查 stock_basic 表是否有 stock_type 字段
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('stock_basic')]
        
        if 'stock_type' not in columns:
            logger.info("添加 stock_type 字段到 stock_basic 表...")
            
            # 添加 stock_type 字段
            db.session.execute(db.text("""
                ALTER TABLE stock_basic 
                ADD COLUMN stock_type VARCHAR(20) COMMENT '证券类型: stock-股票, index-指数, other-其它, bond-可转债, etf-ETF'
            """))
            
            # 更新现有数据：根据 market 字段推断 stock_type
            db.session.execute(db.text("""
                UPDATE stock_basic 
                SET stock_type = 'index' 
                WHERE market LIKE 'index_%'
            """))
            
            db.session.execute(db.text("""
                UPDATE stock_basic 
                SET stock_type = 'bond' 
                WHERE market LIKE 'bond_%'
            """))
            
            db.session.execute(db.text("""
                UPDATE stock_basic 
                SET stock_type = 'etf' 
                WHERE market LIKE 'etf_%'
            """))
            
            db.session.execute(db.text("""
                UPDATE stock_basic 
                SET stock_type = 'other' 
                WHERE market LIKE 'other_%'
            """))
            
            db.session.execute(db.text("""
                UPDATE stock_basic 
                SET stock_type = 'stock' 
                WHERE stock_type IS NULL
            """))
            
            db.session.commit()
            logger.info("✅ stock_type 字段添加成功")
        else:
            logger.info("stock_type 字段已存在")
            
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        db.session.rollback()
        raise


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    
    from extensions import db
    from app import create_app
    
    app = create_app()
    with app.app_context():
        migrate(db)

