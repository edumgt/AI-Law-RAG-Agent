"""
KB증권 Open API 클라이언트
공식 포털: https://developer.kbsec.com

인증(OAuth2 client_credentials)은 KB Open API 공통 규격을 따르며 검증된 엔드포인트다.
반면 시세/잔고/주문/일봉 API는 증권사 포털에서 서비스 단위로 승인된 API 그룹·URI를
발급받아야 호출 가능하고, 신청 계정마다 그룹이 다르게 열린다. 승인 없이 URI를
추측해서 호출하면 조용히 실패하거나 잘못된 데이터를 반환할 수 있으므로,
이 클라이언트는 포털에서 승인받은 실제 경로를 `KBClient`에 채워 넣기 전까지는
명확한 안내 메시지로 실패하도록 만들어졌다 (Mockup으로 조용히 대체되지 않음).
"""
import httpx
from datetime import datetime, timezone
from .base import BrokerClient, TokenInfo, PriceInfo, AccountBalance, BalanceItem

KB_API_BASE_URL = "https://developer.kbsec.com:32484"


class KBClient(BrokerClient):
    def __init__(self, app_key: str, app_secret: str, paper: bool = True):
        self.app_key    = app_key
        self.app_secret = app_secret
        self.paper      = paper
        self._token: str | None = None
        self._token_exp: datetime | None = None

    def _not_ready(self, api_name: str):
        raise RuntimeError(
            f"KB증권 인증은 성공했지만 '{api_name}' API 경로가 이 앱에 아직 설정되지 않았습니다. "
            "KB Open API 포털(developer.kbsec.com)에서 해당 API 그룹을 승인받은 뒤 "
            "app/services/brokers/kb.py 에 실제 엔드포인트를 채워 넣으세요."
        )

    async def get_token(self) -> TokenInfo:
        async with httpx.AsyncClient(timeout=20) as cli:
            r = await cli.post(
                f"{KB_API_BASE_URL}/oauth2/token",
                headers={"Content-Type": "application/json"},
                json={
                    "grant_type": "client_credentials",
                    "appKey":     self.app_key,
                    "appSecret":  self.app_secret,
                },
            )
            r.raise_for_status()
            d = r.json()

        token = d.get("access_token") or d.get("dataBody", {}).get("access_token")
        if not token:
            header = d.get("dataHeader", {})
            code = header.get("processCode") or d.get("error") or "unknown"
            message = header.get("processMessage") or d.get("error_description") or "토큰 발급 실패"
            raise RuntimeError(f"KB증권 인증 실패 ({code}): {message}")

        self._token = token
        expires_in = int(d.get("expires_in", 86400))
        self._token_exp = datetime.now(timezone.utc)
        return TokenInfo(access_token=token, expires_in=expires_in)

    async def _ensure_token(self):
        if not self._token:
            await self.get_token()

    async def get_price(self, symbol: str) -> PriceInfo:
        await self._ensure_token()
        self._not_ready("현재가 조회")

    async def get_balance(self, account_no: str) -> AccountBalance:
        await self._ensure_token()
        self._not_ready("잔고 조회")

    async def place_order(
        self, account_no: str, symbol: str, side: str, quantity: int, price: float
    ) -> dict:
        await self._ensure_token()
        self._not_ready("주문")

    async def get_daily_ohlcv(self, symbol: str, start: str, end: str) -> list[dict]:
        await self._ensure_token()
        self._not_ready("일봉 시세 조회")
