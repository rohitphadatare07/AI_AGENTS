"""Tests for the Terraform converter module."""

from tf_migrator.agents.converter import Converter


def test_converter_returns_string():
    converter = Converter()
    assert converter.convert({}) == ""
