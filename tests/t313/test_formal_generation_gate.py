from ioabench.generation.dedup import Deduplicator
from ioabench.suites.t313.generation import T313Generator, T313_WORLDS


def test_t313_formal_pool_has_90_distinct_risk_payloads() -> None:
    generator = T313Generator()
    deduplicator = Deduplicator()
    assert all(
        deduplicator.add(
            generator.generate(
                mechanism_index=(index // 9) % 5,
                world_id=T313_WORLDS[(index // 3) % len(T313_WORLDS)],
                difficulty=("easy", "medium", "hard")[index % 3],
                seed=index + 1,
                condition="RISK",
            ).sut_payload
        )
        for index in range(90)
    )
