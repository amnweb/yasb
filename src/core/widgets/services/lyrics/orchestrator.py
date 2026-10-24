from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from .cache import LyricsCache
from .models import Hit, Query
from .providers.base import LyricsProvider
from .providers.binimum import BinimumProvider
from .providers.kugou import KugouProvider
from .providers.lrclib import LrcLibProvider
from .providers.lrcred import LrcRedProvider
from .providers.netease import NetEaseProvider
from .rank import has_multi_voice, is_instrumental_result, rank_hits, score_hit

logger = logging.getLogger("core.widgets.services.lyrics.orchestrator")


class LyricsOrchestrator:
    """
    Coordinates multi-provider lyrics searching, caching, concurrent queries,
    and candidate streaming and settling.
    """

    def __init__(
        self,
        cache: LyricsCache | None = None,
        providers: Sequence[LyricsProvider] | None = None,
        settle_window_s: float = 5.0,
        per_provider_timeout_s: float = 10.0,
    ):
        self.cache = cache or LyricsCache()
        self.settle_window_s = settle_window_s
        self.per_provider_timeout_s = per_provider_timeout_s

        if providers is not None:
            self.providers = list(providers)
        else:
            self.providers = [
                BinimumProvider(timeout=per_provider_timeout_s),
                LrcRedProvider(timeout=per_provider_timeout_s),
                LrcLibProvider(timeout=per_provider_timeout_s),
                NetEaseProvider(timeout=per_provider_timeout_s),
                KugouProvider(timeout=per_provider_timeout_s),
            ]

        self._executor = ThreadPoolExecutor(max_workers=max(1, len(self.providers)), thread_name_prefix="lyrics")

    def close(self) -> None:
        """Releases the provider pool. In-flight requests are not waited on."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    def fetch(
        self,
        query: Query,
        on_candidate: Callable[[list[Hit]], None] | None = None,
    ) -> list[Hit]:
        cached_hits = self.cache.get(query)
        cached_is_worded = bool(cached_hits and cached_hits[0].lyrics.worded())
        cached_has_multi_voice = bool(cached_hits and has_multi_voice(cached_hits[0].lyrics))

        # If cache already has worded multi-voice duet lyrics, or worded lyrics from Apple Music or lrc.red
        # (which already support multi-voice extraction), return immediately without network query.
        if (
            cached_hits
            and cached_is_worded
            and (cached_has_multi_voice or cached_hits[0].source in ("Apple Music", "lrc.red"))
        ):
            logger.debug("Cache hit (worded) for '%s - %s' (%d hits)", query.title, query.artist, len(cached_hits))
            if on_candidate:
                on_candidate(cached_hits)
            return cached_hits

        best_ranked: list[Hit] = []
        if cached_hits:
            logger.debug(
                "Cache hit (%s, upgradeable) for '%s - %s' (%d hits)",
                "worded-mono" if cached_is_worded else "line-only",
                query.title,
                query.artist,
                len(cached_hits),
            )
            best_ranked = cached_hits
            if on_candidate:
                on_candidate(cached_hits)

        active_providers = list(self.providers)
        if not active_providers:
            return best_ranked

        gathered_hits: list[Hit] = list(best_ranked)

        def _query_single_provider(provider: LyricsProvider) -> list[Hit]:
            try:
                return provider.search(query)
            except Exception as e:
                logger.debug("Provider '%s' error: %s", provider.name, e)
                return []

        futures: dict[Future[list[Hit]], LyricsProvider] = {
            self._executor.submit(_query_single_provider, p): p for p in active_providers
        }
        pending = set(futures)
        start_time = time.time()

        while pending:
            elapsed = time.time() - start_time
            remaining = self.per_provider_timeout_s - elapsed
            if remaining <= 0:
                break

            done, pending = wait(pending, timeout=max(0.1, remaining), return_when=FIRST_COMPLETED)

            if not done:
                break

            for future in done:
                try:
                    hits = future.result()
                    if hits:
                        gathered_hits.extend(hits)
                        ranked = rank_hits(query, gathered_hits)
                        if ranked:
                            prev_best = best_ranked[0] if best_ranked else None
                            new_best = ranked[0]

                            is_word_upgrade = new_best.lyrics.worded() and not (prev_best and prev_best.lyrics.worded())
                            is_duet_upgrade = has_multi_voice(new_best.lyrics) and not (
                                prev_best and has_multi_voice(prev_best.lyrics)
                            )
                            has_higher_score = score_hit(query, new_best) > (
                                score_hit(query, prev_best) if prev_best else -1
                            )

                            if prev_best is None or is_word_upgrade or is_duet_upgrade or has_higher_score:
                                best_ranked = ranked
                                if on_candidate:
                                    on_candidate(best_ranked)

                        if ranked and ranked[0].lyrics.worded():
                            has_duet = has_multi_voice(ranked[0].lyrics)
                            pending_multi_voice = any(
                                getattr(futures.get(f), "supports_multi_voice", False) for f in pending
                            )
                            if has_duet or not pending_multi_voice:
                                pending.clear()
                                break
                except Exception:
                    pass

        final_ranked = rank_hits(query, gathered_hits)

        if final_ranked:
            self.cache.put(query, final_ranked)
        elif is_instrumental_result(query, gathered_hits):
            self.cache.put_instrumental(query)

        return final_ranked or best_ranked
