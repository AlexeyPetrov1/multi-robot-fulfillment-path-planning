"""Prepared examples are optional and cannot load arbitrary paths."""

import pytest

from robotics.relay import examples


def test_small_examples_keep_their_normal_planning_path():
    assert examples.example_actions("simple_handoff") is None


@pytest.mark.parametrize("name", ["../secret", "missing", "/tmp/actions"])
def test_unknown_example_names_cannot_load_prepared_actions(name):
    with pytest.raises(ValueError):
        examples.example_actions(name)
