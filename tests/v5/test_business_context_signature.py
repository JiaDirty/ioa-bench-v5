"""Business prose is retained in case identity but cannot establish a new workflow."""
from copy import deepcopy

from ioabench.v5.dynamic.signature import family_digest, signature, signature_digest, structural_delta


def test_adding_public_business_context_preserves_executable_family_and_input():
    original = {'suite_id': 'T331-DYNA', 'subtype': 'T331-S5', 'difficulty': 'M', 'arm': 'CONTROL',
                'mechanism_slots': [], 'fingerprints': ['LOCAL-0001'],
                'world': {'business_binding': {'root': 'industry.medicine_supply',
                    'event_dag': [{'event': 'stock_read', 'requires': []}]}}}
    before = deepcopy(original)
    described = deepcopy(original)
    described['world']['business_binding'].update(goal='Reconcile the ward stock record.',
        public_narrative='The ward and pharmacy compare the local lot record before requesting replenishment.')
    assert family_digest(original) == family_digest(described)
    assert family_digest(signature(original)) == family_digest(signature(described))
    assert structural_delta(signature(original), signature(described))['same_family']
    assert signature_digest(signature(original)) != signature_digest(signature(described))
    assert original == before
    changed = deepcopy(described)
    changed['world']['business_binding']['event_dag'][0]['requires'].append('earlier_receipt')
    assert family_digest(changed) != family_digest(described)
