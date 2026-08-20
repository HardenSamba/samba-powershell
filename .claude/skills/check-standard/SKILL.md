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

    modulekit lint src
    python -m modulekit.norms tests --require-headers --max-functions 50 --max-classes 5

Verifies contract section 8: one class and five functions per file, twenty line
functions, two levels of nesting, one hundred character lines, and a header
comment above every class and function.

Test files take the second command, not the first. They are exempt from the
function count, so ``lint src tests`` reports every test module as a violation
and tells you nothing.

## If modulekit is not installed

    git clone https://github.com/HardenSamba/hardensamba-modulekit /tmp/mk
    PYTHONPATH=/tmp/mk/src python -m modulekit.cli validate .
    PYTHONPATH=/tmp/mk/src python -m modulekit.cli lint src
    PYTHONPATH=/tmp/mk/src python -m modulekit.norms tests --require-headers --max-functions 50 --max-classes 5

## Reading the output

`modulekit lint` prints one line per violation, with the file, the line and the
rule. A violation is not a suggestion: the standard is normative. Continuous
integration does not check it, so this local run is the only thing that catches
a violation before review.

Vendored third-party code is exempt. Pass it with `--exclude` rather than
disabling the check.
