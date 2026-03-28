"""Pytest fixtures for Terraform migration tests."""

import pytest


@pytest.fixture
def sample_terraform_code() -> str:
    return "resource \"aws_instance\" \"example\" {}"
