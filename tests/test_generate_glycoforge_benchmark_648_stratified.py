from collections import Counter, defaultdict

from data.generate_data.generate_glycoforge_benchmark_648_stratified import _build_case_specs


def test_stratified_648_case_specs_are_balanced():
    specs = _build_case_specs(24)
    assert len(specs) == 648
    assert len({spec.seed for spec in specs}) == 648

    by_cluster = defaultdict(list)
    for spec in specs:
        by_cluster[spec.cluster_id].append(spec)

    assert len(by_cluster) == 27
    for cluster_specs in by_cluster.values():
        assert len(cluster_specs) == 24
        assert Counter(spec.base_mode for spec in cluster_specs) == {"synthetic": 12, "templated": 12}
        assert Counter(spec.missing_level for spec in cluster_specs) == {"low": 8, "medium": 8, "high": 8}
        assert Counter(spec.batch_level for spec in cluster_specs) == {"light": 12, "elevated": 12}
        assert Counter(spec.motif_driven for spec in cluster_specs) == {False: 12, True: 12}


def test_smaller_debug_build_uses_unique_blueprints():
    specs = _build_case_specs(3)
    assert len(specs) == 81
    for offset in range(0, len(specs), 3):
        blueprints = {
            (spec.base_mode, spec.missing_level, spec.batch_level, spec.motif_driven)
            for spec in specs[offset: offset + 3]
        }
        assert len(blueprints) == 3
