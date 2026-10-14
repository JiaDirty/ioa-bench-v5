from ioabench.generation.dedup import Deduplicator
from ioabench.suites.t322.generation import T322Generator, T322_WORLDS


def test_t322_formal_pool_has_90_distinct_risk_payloads() -> None:
    generator = T322Generator()
    deduplicator = Deduplicator()
    assert all(
        deduplicator.add(
            generator.generate(
                mechanism_index=(index // 9) % 5,
                world_id=T322_WORLDS[(index // 3) % len(T322_WORLDS)],
                difficulty=("easy", "medium", "hard")[index % 3],
                seed=index + 1,
                condition="RISK",
            ).sut_payload
        )
        for index in range(90)
    )
