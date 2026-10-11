import asyncio
import logging
import random
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

logger = logging.getLogger("anti_detect_proxy.proxy")

class ProxyRotator:
    def __init__(self) -> None:
        self.proxies: list[str] = []
        self._lock = asyncio.Lock()
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._refresh_loop())
        logger.info("ProxyRotator background loop started.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ProxyRotator background loop stopped.")

    async def _refresh_loop(self) -> None:
        while self._running:
            await self.refresh_proxies()
            # Refresh the proxy list every 20 minutes
            logger.info("Next proxy harvest scheduled in 20 minutes.")
            await asyncio.sleep(1200)

    async def refresh_proxies(self) -> None:
        logger.info("harvesting free public proxies...")
        try:
            raw_proxies: list[str] = []
            
            # Fetch the public proxy list
            async with AsyncSession(impersonate="chrome120", timeout=15) as session:
                resp = await session.get("https://free-proxy-list.net/")
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    textarea = soup.find("textarea", class_="form-control")
                    
                    if textarea:
                        # Extract from raw text lines
                        for line in textarea.text.splitlines():
                            line_str = line.strip()
                            if line_str and not line_str.startswith("#"):
                                parts = line_str.split(":")
                                if len(parts) == 2:
                                    raw_proxies.append(f"http://{line_str}")
                    else:
                        # Fallback: Extract from the table
                        table = soup.find("table")
                        if table:
                            for row in table.find_all("tr")[1:]:
                                cols = row.find_all("td")
                                if len(cols) >= 2:
                                    ip = cols[0].text.strip()
                                    port = cols[1].text.strip()
                                    raw_proxies.append(f"http://{ip}:{port}")
                                    
            if not raw_proxies:
                logger.warning("No proxies found from harvest source.")
                return

            logger.info("harvested %d total raw proxies. Testing a sample for connectivity...", len(raw_proxies))
            
            # Randomly sample 60 proxies to test concurrently
            test_sample = random.sample(raw_proxies, min(60, len(raw_proxies)))
            working_proxies: list[str] = []

            async def test_single_proxy(proxy_url: str) -> None:
                try:
                    # Test using HTTP to avoid SSL handshake overhead on slow proxies
                    async with AsyncSession(proxy=proxy_url, timeout=6) as test_session:
                        test_resp = await test_session.get("http://httpbin.org/ip")
                        if test_resp.status_code == 200:
                            working_proxies.append(proxy_url)
                except Exception:
                    pass

            await asyncio.gather(*(test_single_proxy(p) for p in test_sample))

            async with self._lock:
                self.proxies = working_proxies
                logger.info("harvest complete. Built working proxy pool size: %d", len(self.proxies))

        except Exception as e:
            logger.error("error harvesting public proxies: %s", e)

    async def get_proxy(self) -> str | None:
        async with self._lock:
            if self.proxies:
                chosen = random.choice(self.proxies)
                logger.info("routing request via fallback proxy: %s", chosen)
                return chosen
            return None

    async def remove_proxy(self, proxy_url: str) -> None:
        async with self._lock:
            if proxy_url in self.proxies:
                self.proxies.remove(proxy_url)
                logger.info("removed dead proxy from active pool: %s. Remaining: %d", proxy_url, len(self.proxies))
