from ioabench.generation.dedup import Deduplicator
from ioabench.suites.t312.generation import T312Generator, T312_WORLDS


def test_t312_formal_pool_has_90_distinct_risk_payloads() -> None:
    generator = T312Generator()
    deduplicator = Deduplicator()
    assert all(
        deduplicator.add(
            generator.generate(
                mechanism_index=(index // 9) % 5,
                world_id=T312_WORLDS[(index // 3) % len(T312_WORLDS)],
                difficulty=("easy", "medium", "hard")[index % 3],
                seed=index + 1,
                condition="RISK",
            ).sut_payload
        )
        for index in range(90)
    )
