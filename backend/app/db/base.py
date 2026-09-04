"""SQLAlchemy 声明式基类，供各模型模块继承，供 Alembic 迁移扫描。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass