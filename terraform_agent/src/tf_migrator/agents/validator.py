from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from anthropic import Anthropic

from ..core.state import AgentState


class ValidatorAgent:
    """Agent responsible for validating converted Terraform."""

    def __init__(self, client: Anthropic):
        self.client = client

    def validate(self, state: AgentState) -> AgentState:
        """Validate the converted Terraform configuration."""
        state.validation_errors = []

        # Step 1: Syntax validation with terraform fmt
        syntax_errors = self._validate_syntax(state)
        if syntax_errors:
            state.validation_errors.extend(syntax_errors)

        # Step 2: terraform validate
        validate_errors = self._terraform_validate(state)
        if validate_errors:
            state.validation_errors.extend(validate_errors)

        # Step 3: Semantic validation with Claude
        semantic_issues = self._semantic_validation(state)
        if semantic_issues:
            state.validation_errors.extend(semantic_issues)

        return state

    def _validate_syntax(self, state: AgentState) -> list[dict]:
        """Run terraform fmt to check syntax."""
        errors = []

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write converted files
            for filename, content in state.converted_files.items():
                filepath = tmppath / filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content)

            # Run terraform fmt -check
            result = subprocess.run(
                ["terraform", "fmt", "-check", "-recursive", "-diff"],
                cwd=tmppath,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                errors.append({
                    "type": "syntax",
                    "message": "Terraform fmt check failed",
                    "details": result.stdout or result.stderr,
                })

        return errors

    def _terraform_validate(self, state: AgentState) -> list[dict]:
        """Run terraform validate."""
        errors = []

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Write converted files
            for filename, content in state.converted_files.items():
                filepath = tmppath / filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content)

            # Add minimal provider configuration for validation
            provider_config = self._generate_provider_stub(state)
            (tmppath / "provider.tf").write_text(provider_config)

            # terraform init
            init_result = subprocess.run(
                ["terraform", "init", "-backend=false"],
                cwd=tmppath,
                capture_output=True,
                text=True,
            )

            if init_result.returncode != 0:
                errors.append({
                    "type": "init",
                    "message": "Terraform init failed",
                    "details": init_result.stderr,
                })
                return errors

            # terraform validate
            validate_result = subprocess.run(
                ["terraform", "validate", "-json"],
                cwd=tmppath,
                capture_output=True,
                text=True,
            )

            try:
                validation_output = json.loads(validate_result.stdout)
                if not validation_output.get("valid", False):
                    for diag in validation_output.get("diagnostics", []):
                        errors.append({
                            "type": "validation",
                            "severity": diag.get("severity", "error"),
                            "message": diag.get("summary", ""),
                            "details": diag.get("detail", ""),
                            "range": diag.get("range", {}),
                        })
            except json.JSONDecodeError:
                if validate_result.returncode != 0:
                    errors.append({
                        "type": "validation",
                        "message": "Terraform validate failed",
                        "details": validate_result.stderr,
                    })

        return errors

    def _generate_provider_stub(self, state: AgentState) -> str:
        """Generate minimal provider configuration for validation."""
        provider = state.target_provider.value

        stubs = {
            "aws": """
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
}
""",
            "gcp": """
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "validation-project"
  region  = "us-central1"
}
""",
            "azure": """
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
  skip_provider_registration = true
}
""",
        }

        return stubs.get(provider, "")

    def _semantic_validation(self, state: AgentState) -> list[dict]:
        """Use Claude to perform semantic validation."""
        if not state.converted_files:
            return []

        # Combine converted files for review
        combined_hcl = "\n\n".join(
            f"# File: {name}\n{content}"
            for name, content in list(state.converted_files.items())[:5]
        )

        prompt = f"""Review this converted Terraform configuration for semantic issues:

```hcl
{combined_hcl[:8000]}  # Truncate for context limits
