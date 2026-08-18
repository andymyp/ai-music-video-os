"""Phase 11: trend engine (MASTER §21; MAD-001 §15-16; TDD-001 §27-29, §108; PRD-001 §9, §62, §80).

Covers the configurable weighted scoring model, the multi-provider aggregator,
the short-TTL cache (provider/query/timestamp/result/expiration) that never
serves stale data, the engine facade that drops stale signals, the time-aware
mock provider, and the tool/agent integration over the offline runtime.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from api.agents.runtime import build_agent_runtime
from api.agents.tools import TrendSearchOutput, TrendSearchTool
from api.capabilities import (
    Capability,
    InMemoryProviderRegistry,
    ProviderConfig,
    TrendQuery,
    TrendSignal,
)
from api.core.errors import AgentError, ToolError
from api.domain.agents import TrendResearchRequest
from api.domain.creative import TrendResult
from api.trend.aggregator import TrendAggregator
from api.trend.cache import TrendCache
from api.trend.engine import TrendEngine
from api.trend.scoring import TrendScoringEngine
from api.trend.weights import DEFAULT_TREND_WEIGHTS, COMPONENTS, TrendWeights
from api.providers import register_mock_providers
from api.providers.mock import MockTrendProvider

NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)


def fixed_clock():
    return NOW


def make_registry(*providers) -> InMemoryProviderRegistry:
    registry = InMemoryProviderRegistry()
    for provider in providers:
        registry.register(
            Capability.TREND,
            provider,
            ProviderConfig(
                provider_id=getattr(provider, "model", type(provider).__name__),
                capability=Capability.TREND,
                priority=10,
            ),
        )
    return registry


def signal(topic, *, platform="tiktok", score=0.9, growth=0.5, volume=5000,
           recency=None) -> TrendSignal:
    return TrendSignal(
        topic=topic,
        platform=platform,
        score=score,
        growth=growth,
        volume=volume,
        recency=recency,
        summary=f"signal for {topic}",
    )


# --- Weights (MAD-001 §16) ---------------------------------------------------

def test_default_weights_follow_mad_formula():
    weights = TrendWeights()
    mapping = weights.to_mapping()
    assert mapping == DEFAULT_TREND_WEIGHTS
    assert set(mapping) == set(COMPONENTS)
    assert sum(mapping.values()) == pytest.approx(1.0)


def test_weights_reject_invalid_combinations():
    with pytest.raises(ValidationError):
        TrendWeights(growth=2.0)  # > 1
    with pytest.raises(ValidationError):
        TrendWeights(volume=-0.1)  # negative
    with pytest.raises(ValidationError):
        TrendWeights(growth=0.5)  # sum no longer 1.0


def test_weights_are_configurable():
    weights = TrendWeights(growth=0.1, volume=0.6, cross_platform=0.1,
                           recency=0.1, content_fit=0.1)
    assert weights.growth == pytest.approx(0.1)
    assert weights.composite({"growth": 1.0, "volume": 0.0, "cross_platform": 0.0,
                              "recency": 0.0, "content_fit": 0.0}) == pytest.approx(0.1)


# --- Scoring engine (MAD-001 §16, TDD-001 §29) -------------------------------

def test_scoring_matches_hand_computed_mad_composite():
    engine = TrendScoringEngine(clock=fixed_clock)
    query = TrendQuery(genre="lofi", time_window_days=7)
    result = engine.score(signal("lofi-beats", growth=0.5, volume=5000,
                                 recency=NOW), query, cross_platform=0.25)
    # composite = 0.30*0.5 + 0.25*0.5 + 0.20*0.25 + 0.15*1.0 + 0.10*1.0 = 0.575
    assert result.score == pytest.approx(57.5)
    assert result.confidence == pytest.approx(round(min(0.95, 0.4 + 0.6 * 0.575), 3))
    assert result.growth == pytest.approx(0.5)
    assert result.volume == pytest.approx(0.5)
    assert result.cross_platform == pytest.approx(0.25)
    assert result.content_fit == pytest.approx(1.0)
    assert 0.0 <= result.confidence <= 1.0
    assert 0.0 <= result.score <= 100.0


def test_scoring_clamps_growth_and_normalizes_volume():
    engine = TrendScoringEngine(clock=fixed_clock)
    query = TrendQuery(keyword="x")
    comps = engine.components(signal("x-1", growth=5.0, volume=20000), query, cross_platform=0.0)
    assert comps["growth"] == 1.0  # clamped to [0,1]
    assert comps["volume"] == 1.0  # 20000 / 10000 clamped
    comps2 = engine.components(signal("x-2", growth=0.0, volume=0), query, cross_platform=0.0)
    assert comps2["growth"] == 0.0
    assert comps2["volume"] == 0.0


def test_recency_score_decays_linearly_to_window_edge():
    engine = TrendScoringEngine(clock=fixed_clock)
    query = TrendQuery(keyword="x", time_window_days=7)
    fresh = engine.components(signal("x-a", recency=NOW), query, 0.0)
    assert fresh["recency"] == pytest.approx(1.0)
    half = engine.components(
        signal("x-b", recency=NOW - timedelta(days=3, hours=12)), query, 0.0)
    assert half["recency"] == pytest.approx(0.5, abs=0.001)
    edge = engine.components(signal("x-c", recency=NOW - timedelta(days=7)), query, 0.0)
    assert edge["recency"] == pytest.approx(0.0)
    old = engine.components(signal("x-d", recency=NOW - timedelta(days=20)), query, 0.0)
    assert old["recency"] == pytest.approx(0.0)  # never negative


def test_content_fit_prefers_matching_topic_and_is_deterministic():
    engine = TrendScoringEngine(clock=fixed_clock)
    query = TrendQuery(genre="lofi")
    assert engine.components(signal("lofi-night"), query, 0.0)["content_fit"] == 1.0
    non = engine.components(signal("phonk-bangers"), query, 0.0)["content_fit"]
    assert 0.3 <= non < 1.0
    non2 = engine.components(signal("phonk-bangers"), query, 0.0)["content_fit"]
    assert non2 == non  # deterministic fallback


def test_scoring_is_deterministic_across_calls():
    engine = TrendScoringEngine(clock=fixed_clock)
    query = TrendQuery(genre="lofi")
    first = engine.score(signal("lofi-a"), query, cross_platform=0.4)
    second = engine.score(signal("lofi-a"), query, cross_platform=0.4)
    assert first == second


def test_weights_change_ranking_order():
    engine_default = TrendScoringEngine(clock=fixed_clock)
    custom = TrendWeights(growth=0.20, volume=0.40, cross_platform=0.15,
                          recency=0.15, content_fit=0.10)
    engine_custom = TrendScoringEngine(custom, clock=fixed_clock)
    query = TrendQuery(genre="lofi")
    high_growth = engine_default.score(signal("lofi-g", growth=1.0, volume=0.0), query, 0.0)
    high_volume = engine_default.score(signal("lofi-v", growth=0.0, volume=10000), query, 0.0)
    # Default weights favour growth (0.30) over volume (0.25).
    assert high_growth.score > high_volume.score
    high_growth_c = engine_custom.score(signal("lofi-g", growth=1.0, volume=0.0), query, 0.0)
    high_volume_c = engine_custom.score(signal("lofi-v", growth=0.0, volume=10000), query, 0.0)
    # Custom weights favour volume (0.40) over growth (0.20).
    assert high_volume_c.score > high_growth_c.score


# --- Aggregator (TDD-001 §28) ------------------------------------------------

class FakeTrendProvider:
    def __init__(self, model: str, signals: list[TrendSignal]) -> None:
        self.model = model
        self._signals = signals

    async def discover(self, query: TrendQuery) -> list[TrendSignal]:
        return list(self._signals)


class FailingTrendProvider:
    model = "failing"

    async def discover(self, query: TrendQuery) -> list[TrendSignal]:
        raise ToolError("provider down")


async def test_aggregator_combines_and_dedupes_multiple_providers():
    a = FakeTrendProvider("a", [signal("dup", platform="tiktok", score=0.5),
                                signal("only-a", platform="youtube")])
    b = FakeTrendProvider("b", [signal("dup", platform="tiktok", score=0.9),
                                signal("only-b", platform="instagram")])
    agg = TrendAggregator(make_registry(a, b))
    raw = await agg.discover_all(TrendQuery(keyword="x"))
    topics = {(item.signal.topic, item.signal.platform) for item in raw}
    assert ("dup", "tiktok") in topics  # deduped to a single entry
    dup = next(i for i in raw if i.signal.topic == "dup")
    assert dup.signal.score == 0.9  # highest score kept
    assert ("only-a", "youtube") in topics
    assert ("only-b", "instagram") in topics
    assert len(raw) == 3


async def test_aggregator_cross_platform_presence():
    a = FakeTrendProvider("a", [signal("hot", platform="tiktok"),
                                signal("cold", platform="youtube")])
    b = FakeTrendProvider("b", [signal("hot", platform="instagram")])
    agg = TrendAggregator(make_registry(a, b))
    raw = await agg.discover_all(TrendQuery(keyword="x", platforms=["tiktok", "youtube", "instagram"]))
    cross = agg.cross_platform_scores(raw, TrendQuery(
        keyword="x", platforms=["tiktok", "youtube", "instagram"]))
    assert cross["hot"] == pytest.approx(2 / 3, abs=0.001)
    assert cross["cold"] == pytest.approx(1 / 3, abs=0.001)


async def test_aggregator_skips_failing_provider():
    good = FakeTrendProvider("good", [signal("works")])
    agg = TrendAggregator(make_registry(good, FailingTrendProvider()))
    raw = await agg.discover_all(TrendQuery(keyword="x"))
    assert {i.signal.topic for i in raw} == {"works"}


async def test_aggregator_raises_without_enabled_providers():
    agg = TrendAggregator(InMemoryProviderRegistry())
    with pytest.raises(ToolError, match="no enabled trend provider"):
        await agg.discover_all(TrendQuery(keyword="x"))


# --- Cache (TDD-001 §108) ----------------------------------------------------

class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def test_cache_stores_provider_query_timestamp_result_expiration():
    cache = TrendCache(ttl_seconds=60, clock=fixed_clock)
    query = TrendQuery(genre="lofi")
    result = [TrendResult(source="tiktok", topic="lofi-a")]
    entry = cache.put(["mock-trend"], query, result)
    assert entry.provider_ids == ["mock-trend"]
    assert entry.query == query
    assert entry.timestamp == NOW
    assert entry.result == result
    assert entry.expiration == NOW + timedelta(seconds=60)


def test_cache_returns_fresh_entry_and_misses_when_expired():
    clock = MutableClock(NOW)
    cache = TrendCache(ttl_seconds=60, clock=clock)
    query = TrendQuery(genre="lofi")
    cache.put(["mock-trend"], query, [TrendResult(source="tiktok", topic="lofi-a")])
    assert cache.get(["mock-trend"], query) is not None
    # A different provider set or query is a miss.
    assert cache.get(["other"], query) is None
    assert cache.get(["mock-trend"], TrendQuery(genre="phonk")) is None
    # After the TTL the entry is evicted and never served.
    clock.value = NOW + timedelta(seconds=61)
    assert cache.get(["mock-trend"], query) is None
    assert len(cache) == 0


def test_cache_ttl_must_be_positive():
    with pytest.raises(ValueError):
        TrendCache(ttl_seconds=0)


# --- Engine (MASTER §21; TDD-001 §108) ---------------------------------------

class CountingTrendProvider(FakeTrendProvider):
    def __init__(self, signals: list[TrendSignal]) -> None:
        super().__init__("counting", signals)
        self.calls = 0

    async def discover(self, query: TrendQuery) -> list[TrendSignal]:
        self.calls += 1
        return await super().discover(query)


async def test_engine_ranks_fresh_results_with_all_components():
    engine = TrendEngine(
        make_registry(FakeTrendProvider("mock-trend", [
            signal("lofi-1", recency=NOW),
            signal("lofi-2", recency=NOW - timedelta(days=3)),
        ])),
        clock=fixed_clock,
    )
    results = await engine.search(TrendQuery(genre="lofi"))
    assert results
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    for r in results:
        assert 0.0 <= r.score <= 100.0
        for name in COMPONENTS:
            assert getattr(r, name) is not None, name
        assert r.recency is not None


async def test_engine_caches_results_within_ttl():
    provider = CountingTrendProvider([signal("lofi-1", recency=NOW)])
    engine = TrendEngine(make_registry(provider), clock=fixed_clock)
    query = TrendQuery(genre="lofi")
    first = await engine.search(query)
    second = await engine.search(query)
    assert first == second
    assert provider.calls == 1  # second search served from cache


async def test_engine_drops_stale_signals():
    engine = TrendEngine(
        make_registry(FakeTrendProvider("mock-trend", [
            signal("fresh", recency=NOW - timedelta(days=5)),
            signal("stale", recency=NOW - timedelta(days=40)),
        ])),
        clock=fixed_clock,
        max_signal_age_days=30,
    )
    results = await engine.search(TrendQuery(genre="lofi"))
    assert {r.topic for r in results} == {"fresh"}


async def test_engine_staleness_threshold_is_configurable():
    engine = TrendEngine(
        make_registry(FakeTrendProvider("mock-trend", [
            signal("stale", recency=NOW - timedelta(days=40)),
        ])),
        clock=fixed_clock,
        max_signal_age_days=30,
    )
    assert await engine.search(TrendQuery(genre="lofi")) == []


async def test_engine_is_deterministic():
    registry = make_registry(FakeTrendProvider("mock-trend", [
        signal("lofi-a", recency=NOW),
        signal("lofi-b", recency=NOW - timedelta(days=1)),
    ]))
    first = await TrendEngine(registry, clock=fixed_clock).search(TrendQuery(genre="lofi"))
    second = await TrendEngine(registry, clock=fixed_clock).search(TrendQuery(genre="lofi"))
    assert first == second


# --- Mock provider (time-aware, deterministic) --------------------------------

async def test_mock_trend_recency_is_fresh_and_time_aware():
    provider = MockTrendProvider(clock=fixed_clock)
    query = TrendQuery(genre="lofi", limit=3, time_window_days=7)
    signals = await provider.discover(query)
    assert signals
    for s in signals:
        assert s.recency is not None
        age = NOW - s.recency
        assert timedelta(0) <= age <= timedelta(days=7)
        assert 0 <= s.score <= 1


async def test_mock_trend_is_deterministic_within_minute():
    provider = MockTrendProvider(clock=fixed_clock)
    query = TrendQuery(genre="lofi", limit=3)
    a = await provider.discover(query)
    b = await provider.discover(query)
    assert [s.model_dump() for s in a] == [s.model_dump() for s in b]


async def test_mock_trend_uses_injectable_clock():
    later = NOW + timedelta(hours=2)
    provider = MockTrendProvider(clock=lambda: later)
    signals = await provider.discover(TrendQuery(genre="lofi", limit=1))
    assert signals[0].recency <= later


# --- Tool + agent integration (TDD-001 §93, PRD-001 §62) ---------------------

def test_trend_search_tool_output_carries_scored_results():
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    tool = TrendSearchTool(registry)
    assert tool.output_schema is TrendSearchOutput
    assert tool.input_schema is TrendQuery


async def test_trend_search_tool_returns_ranked_results():
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    tool = TrendSearchTool(registry)
    output = await tool.run(TrendQuery(genre="lofi", limit=5))
    assert isinstance(output, TrendSearchOutput)
    assert output.results
    scores = [r.score for r in output.results]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 100.0 for s in scores)


async def test_trend_research_agent_consumes_scored_results():
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    runtime = build_agent_runtime(registry)
    result = await runtime.run("trend_research", TrendResearchRequest(genre_hint="lofi"))
    assert result.selected_genre == "lofi"
    assert result.recommendations
    assert 0.0 <= result.confidence <= 1.0
    scores = [r.score for r in result.recommendations]
    assert scores == sorted(scores, reverse=True)
    # Every component of the MAD-001 §16 model is present on each row.
    for rec in result.recommendations:
        assert all(getattr(rec, name) is not None for name in COMPONENTS)


async def test_trend_research_agent_is_deterministic():
    registry = InMemoryProviderRegistry()
    register_mock_providers(registry)
    runtime = build_agent_runtime(registry)
    request = TrendResearchRequest(genre_hint="lofi")
    first = await runtime.run("trend_research", request)
    second = await runtime.run("trend_research", request)
    assert first == second


async def test_trend_research_agent_raises_without_fresh_signals():
    old = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    registry = make_registry(FakeTrendProvider("mock-trend", [
        signal("ancient", recency=old - timedelta(days=60)),
    ]))
    engine = TrendEngine(registry, max_signal_age_days=30)
    runtime = build_agent_runtime(registry, trend_engine=engine)

    with pytest.raises(AgentError, match="no fresh signals"):
        await runtime.run("trend_research", TrendResearchRequest(genre_hint="lofi"))
