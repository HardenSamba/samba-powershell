---
name: check-standard
description: >
  Audit this module against the HardenSamba coding standard and the module
  contract, using modulekit. Use before committing, after changing code, or
  when asked to lint, to check the norms, the conventions or the standards.
---

# Check the standard

Two checks, both of which must pass before a commit.

## 1. The contract

    modulekit validate .

Verifies the manifest, the declared write surface, the repository layout, the
name consistency between the manifest and the Debian source package, and the
absence of forbidden provenance markers.

## 2. The coding standard

    modulekit lint src tests

Verifies contract section 8: one class and five functions per file, twenty line
functions, two levels of nesting, one hundred character lines, and a header
comment above every class and function.

## If modulekit is not installed

    git clone https://github.com/HardenSamba/hardensamba-modulekit /tmp/mk
    PYTHONPATH=/tmp/mk/src python -m modulekit.cli validate .
    PYTHONPATH=/tmp/mk/src python -m modulekit.cli lint src tests

## Reading the output

`modulekit lint` prints one line per violation, with the file, the line and the
rule. A violation is not a suggestion: the standard is enforced in continuous
integration, so a build fails on it.

Vendored third-party code is exempt. Pass it with `--exclude` rather than
disabling the check.
