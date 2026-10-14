from ioabench.generation.dedup import Deduplicator
from ioabench.suites.t323.generation import T323Generator, T323_WORLDS


def test_t323_formal_pool_has_90_distinct_risk_payloads() -> None:
    generator = T323Generator()
    deduplicator = Deduplicator()
    assert all(
        deduplicator.add(
            generator.generate(
                mechanism_index=(index // 9) % 5,
                world_id=T323_WORLDS[(index // 3) % len(T323_WORLDS)],
                difficulty=("easy", "medium", "hard")[index % 3],
                seed=index + 1,
                condition="RISK",
            ).sut_payload
        )
        for index in range(90)
    )
