from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base, UUIDPkMixin


class PersonalCbStat(Base, UUIDPkMixin):
    __tablename__ = "personal_cb_stats"
    __table_args__ = (
        Index("ix_personal_cb_stats_stdt", "stdt"),
        Index("ix_personal_cb_stats_gender_age", "gender", "age_band"),
    )

    stdt: Mapped[str] = mapped_column(String(20), nullable=False)
    gender: Mapped[int] = mapped_column(Integer, nullable=False)
    age_band: Mapped[int] = mapped_column(Integer, nullable=False)
    cnt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_score: Mapped[float] = mapped_column(Float, nullable=True)
    avg_score_6m: Mapped[float] = mapped_column(Float, nullable=True)
    default_rate_1: Mapped[float] = mapped_column(Float, nullable=True)
    default_rate_2: Mapped[float] = mapped_column(Float, nullable=True)


class CorporateCbStat(Base, UUIDPkMixin):
    __tablename__ = "corporate_cb_stats"
    __table_args__ = (
        Index("ix_corporate_cb_stats_bs_dt", "bs_dt"),
        Index("ix_corporate_cb_stats_sic_wg", "sic_cd", "wg_gb"),
    )

    bs_dt: Mapped[str] = mapped_column(String(20), nullable=False)
    sic_cd: Mapped[str] = mapped_column(String(10), nullable=False)
    wg_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    cnt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_corp_grad: Mapped[float] = mapped_column(Float, nullable=True)
    default_rate: Mapped[float] = mapped_column(Float, nullable=True)


class BankProduct(Base, UUIDPkMixin):
    __tablename__ = "bank_products"
    __table_args__ = (Index("ix_bank_products_base_rate", "base_rate"),)

    bank_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    product_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    product_group: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    min_period: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    max_period: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    min_amount: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    max_amount: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    base_rate: Mapped[float] = mapped_column(Float, nullable=True)
    max_rate: Mapped[float] = mapped_column(Float, nullable=True)
    deposit_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    maturity: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    deposit_protection: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    product_summary: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class FundProduct(Base, UUIDPkMixin):
    __tablename__ = "fund_products"
    __table_args__ = (
        Index("ix_fund_products_main_type", "main_type"),
        Index("ix_fund_products_return_1y", "return_1y"),
    )

    eval_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    fund_code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    fund_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    main_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    mid_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    sub_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    strategy: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    aum: Mapped[float] = mapped_column(Float, nullable=True)
    risk_grade: Mapped[int] = mapped_column(Integer, nullable=True)
    nav: Mapped[float] = mapped_column(Float, nullable=True)
    return_1y: Mapped[float] = mapped_column(Float, nullable=True)
    expense_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    is_retirement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_esg: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DataCache(Base, UUIDPkMixin):
    __tablename__ = "data_cache"

    key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, index=True
    )
