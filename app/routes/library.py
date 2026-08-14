from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.postgres import get_pg_session
from app.lib.session import get_current_user
from app.lib.financial_tools import search_bank_products, search_funds
from app.models import CrawledDoc

router = APIRouter(prefix="/api")


@router.get("/library/search")
async def library_search(
    q: str = Query(""),
    category: str = Query("all"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_pg_session),
):
    items = []

    if category in ("all", "bank"):
        result = await search_bank_products(db, {"keyword": q, "limit": 5})
        items.append({"type": "은행상품", "content": result})

    if category in ("all", "fund"):
        result = await search_funds(db, {"keyword": q, "limit": 5})
        items.append({"type": "펀드상품", "content": result})

    if category in ("all", "news"):
        result = await db.execute(
            select(CrawledDoc)
            .where(or_(CrawledDoc.title.ilike(f"%{q}%"), CrawledDoc.content.ilike(f"%{q}%")))
            .order_by(CrawledDoc.crawled_at.desc())
            .limit(5)
        )
        rows = result.scalars().all()
        if rows:
            news_text = "\n".join(
                f"[{r.title}] {(r.content or '')[:200]}..." for r in rows
            )
            items.append({"type": "크롤링 문서", "content": news_text})

    return {"items": items, "query": q}
