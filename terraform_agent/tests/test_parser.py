"""Tests for the Terraform parser module."""

from tf_migrator.core.parser import parse_hcl


def test_parse_hcl_returns_dict():
    result = parse_hcl('resource "aws_instance" "example" {}')
    assert isinstance(result, dict)
