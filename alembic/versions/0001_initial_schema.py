"""initial schema (Mongo -> PostgreSQL 전환)

Revision ID: 0001
Revises:
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("client_id", sa.String(32), nullable=False),
        sa.Column("roles", postgresql.ARRAY(sa.String), nullable=False, server_default=sa.text("ARRAY['user']::varchar[]")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_client_id", "users", ["client_id"], unique=True)

    op.create_table(
        "portfolio",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_price", sa.Float, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "symbol", name="uq_portfolio_user_symbol"),
    )
    op.create_index("ix_portfolio_user_id", "portfolio", ["user_id"])

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("order_type", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="filled"),
        sa.Column("broker", sa.String(20), nullable=False, server_default="virtual"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_orders_user_created", "orders", ["user_id", "created_at"])

    op.create_table(
        "broker_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("broker", sa.String(20), nullable=False, server_default="mock"),
        sa.Column("app_key", sa.String(200), nullable=False, server_default=""),
        sa.Column("app_secret", sa.String(200), nullable=False, server_default=""),
        sa.Column("account_no", sa.String(50), nullable=False, server_default=""),
        sa.Column("paper", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("quant_mode", sa.String(10), nullable=False, server_default="paper"),
        sa.Column("quant_symbol_source", sa.String(10), nullable=False, server_default="ai"),
        sa.Column("quant_selected_symbols", postgresql.ARRAY(sa.String), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("quant_ai_top_n", sa.Integer, nullable=False, server_default="3"),
        sa.Column("quant_per_trade_budget", sa.Float, nullable=False, server_default="1000000"),
        sa.Column("quant_buy_ratio", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("quant_sell_ratio", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "quant_virtual_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("initial_capital", sa.Float, nullable=False, server_default="10000000"),
        sa.Column("cash_balance", sa.Float, nullable=False, server_default="10000000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "custom_indicators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("base", sa.String(20), nullable=False, server_default="rsi_ma"),
        sa.Column("short_window", sa.Integer, nullable=False, server_default="5"),
        sa.Column("mid_window", sa.Integer, nullable=False, server_default="20"),
        sa.Column("rsi_period", sa.Integer, nullable=False, server_default="14"),
        sa.Column("buy_threshold", sa.Float, nullable=False, server_default="35.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_custom_indicators_user_created", "custom_indicators", ["user_id", "created_at"])

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default="새 대화"),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"])

    op.create_table(
        "chats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_id", sa.String(32), nullable=False, server_default=""),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("steps", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("citations", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chats_user_created", "chats", ["user_id", "created_at"])
    op.create_index("ix_chats_conversation_created", "chats", ["conversation_id", "created_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("client_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_user_created", "audit_events", ["user_id", "created_at"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])

    op.create_table(
        "notification_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("channels", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("telegram_token", sa.String(200), nullable=False, server_default=""),
        sa.Column("telegram_chat_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("slack_webhook_url", sa.String(300), nullable=False, server_default=""),
        sa.Column("email_to", sa.String(200), nullable=False, server_default=""),
        sa.Column("email_host", sa.String(200), nullable=False, server_default=""),
        sa.Column("email_port", sa.Integer, nullable=False, server_default="587"),
        sa.Column("email_user", sa.String(200), nullable=False, server_default=""),
        sa.Column("email_password", sa.String(200), nullable=False, server_default=""),
        sa.Column("email_from", sa.String(200), nullable=False, server_default=""),
        sa.Column("kakao_api_key", sa.String(200), nullable=False, server_default=""),
        sa.Column("kakao_api_secret", sa.String(200), nullable=False, server_default=""),
        sa.Column("kakao_sender_key", sa.String(200), nullable=False, server_default=""),
        sa.Column("kakao_phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("sms_api_key", sa.String(200), nullable=False, server_default=""),
        sa.Column("sms_api_secret", sa.String(200), nullable=False, server_default=""),
        sa.Column("sms_from", sa.String(30), nullable=False, server_default=""),
        sa.Column("sms_to", sa.String(30), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "notification_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("subject", sa.String(300), nullable=False, server_default=""),
        sa.Column("message", sa.String(500), nullable=False, server_default=""),
        sa.Column("channels", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notification_log_user_created", "notification_log", ["user_id", "created_at"])

    op.create_table(
        "crawled_docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("url", sa.String(1000), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("source", sa.String(200), nullable=False, server_default=""),
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_crawled_docs_crawled_at", "crawled_docs", ["crawled_at"])

    op.create_table(
        "uploaded_docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("uploader", sa.String(320), nullable=False, server_default=""),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_key", sa.String(400), nullable=False),
        sa.Column("chunks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("file_size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ext", sa.String(20), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_uploaded_docs_user_created", "uploaded_docs", ["user_id", "created_at"])

    op.create_table(
        "personal_cb_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("stdt", sa.String(20), nullable=False),
        sa.Column("gender", sa.Integer, nullable=False),
        sa.Column("age_band", sa.Integer, nullable=False),
        sa.Column("cnt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_score", sa.Float, nullable=True),
        sa.Column("avg_score_6m", sa.Float, nullable=True),
        sa.Column("default_rate_1", sa.Float, nullable=True),
        sa.Column("default_rate_2", sa.Float, nullable=True),
    )
    op.create_index("ix_personal_cb_stats_stdt", "personal_cb_stats", ["stdt"])
    op.create_index("ix_personal_cb_stats_gender_age", "personal_cb_stats", ["gender", "age_band"])

    op.create_table(
        "corporate_cb_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bs_dt", sa.String(20), nullable=False),
        sa.Column("sic_cd", sa.String(10), nullable=False),
        sa.Column("wg_gb", sa.Integer, nullable=False),
        sa.Column("cnt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_corp_grad", sa.Float, nullable=True),
        sa.Column("default_rate", sa.Float, nullable=True),
    )
    op.create_index("ix_corporate_cb_stats_bs_dt", "corporate_cb_stats", ["bs_dt"])
    op.create_index("ix_corporate_cb_stats_sic_wg", "corporate_cb_stats", ["sic_cd", "wg_gb"])

    op.create_table(
        "bank_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bank_code", sa.String(20), nullable=False, server_default=""),
        sa.Column("bank_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("product_code", sa.String(50), nullable=False, server_default=""),
        sa.Column("product_name", sa.String(300), nullable=False, server_default=""),
        sa.Column("product_group", sa.String(100), nullable=False, server_default=""),
        sa.Column("min_period", sa.String(50), nullable=False, server_default=""),
        sa.Column("max_period", sa.String(50), nullable=False, server_default=""),
        sa.Column("min_amount", sa.String(50), nullable=False, server_default=""),
        sa.Column("max_amount", sa.String(50), nullable=False, server_default=""),
        sa.Column("base_rate", sa.Float, nullable=True),
        sa.Column("max_rate", sa.Float, nullable=True),
        sa.Column("deposit_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("maturity", sa.String(100), nullable=False, server_default=""),
        sa.Column("deposit_protection", sa.String(100), nullable=False, server_default=""),
        sa.Column("product_summary", sa.String(500), nullable=False, server_default=""),
    )
    op.create_index("ix_bank_products_base_rate", "bank_products", ["base_rate"])

    op.create_table(
        "fund_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("eval_date", sa.String(20), nullable=False, server_default=""),
        sa.Column("fund_code", sa.String(50), nullable=False, server_default=""),
        sa.Column("fund_name", sa.String(300), nullable=False, server_default=""),
        sa.Column("company_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("main_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("mid_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("sub_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("strategy", sa.String(300), nullable=False, server_default=""),
        sa.Column("aum", sa.Float, nullable=True),
        sa.Column("risk_grade", sa.Integer, nullable=True),
        sa.Column("nav", sa.Float, nullable=True),
        sa.Column("return_1y", sa.Float, nullable=True),
        sa.Column("expense_ratio", sa.Float, nullable=True),
        sa.Column("is_retirement", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_esg", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_fund_products_main_type", "fund_products", ["main_type"])
    op.create_index("ix_fund_products_return_1y", "fund_products", ["return_1y"])

    op.create_table(
        "data_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(200), nullable=False, unique=True),
        sa.Column("data", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_data_cache_updated_at", "data_cache", ["updated_at"])

    # 시스템 유저 seed (Mongo 시절 "quant_system" sentinel user_id를 대체)
    op.execute(
        f"""
        INSERT INTO users (id, name, email, password_hash, client_id, roles, created_at)
        VALUES ('{SYSTEM_USER_ID}', '자동매매 시스템', 'system@internal.local', '', 'SYSTEMUSER00000000', ARRAY['system'], now())
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("data_cache")
    op.drop_table("fund_products")
    op.drop_table("bank_products")
    op.drop_table("corporate_cb_stats")
    op.drop_table("personal_cb_stats")
    op.drop_table("uploaded_docs")
    op.drop_table("crawled_docs")
    op.drop_table("notification_log")
    op.drop_table("notification_settings")
    op.drop_table("audit_events")
    op.drop_table("chats")
    op.drop_table("conversations")
    op.drop_table("custom_indicators")
    op.drop_table("quant_virtual_accounts")
    op.drop_table("broker_settings")
    op.drop_table("orders")
    op.drop_table("portfolio")
    op.drop_table("users")
